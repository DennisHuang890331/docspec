"""aperture 投影：把「對的檔」按 skill 白名單投給 agent。

這是 docspec 的存在理由——控制生成當下的 context。引擎不寫一個字，只裁切轉交。
硬規則（engine-spec §4）：
  - draft 讀 concept 只投 concept/brief/must_cover/sources；decisions 只投 active 條目的 statement；
    絕不投 develop.md / history.yaml。
  - 不在 skill 白名單的檔，引擎不遞、不揭露路徑。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import yaml

from dspx.forest import forest_view
from dspx.glossary import load_glossary
from dspx.layout import Layout
from dspx.model import (
    ASSET_DIR_NAME,
    Leaf,
    ancestor_leaves,
    decision_index,
    realized_statements,
)
from dspx.schema import Schema

# draft 讀 concept 的准投欄位（治理欄 realizes 不投）
_DRAFT_CONCEPT_FIELDS = ("concept", "brief", "must_cover", "sources")
# glossary 注入＝精瘦索引（省 token）；definition/english 是下鑽欄（`docspec show <id>`），不注入
_GLOSSARY_INDEX_FIELDS = ("id", "canonical", "bucket", "code", "aliases_forbidden")
# draft 讀 decisions 的 active 狀態
_ACTIVE_STATUS = ("proposed", "accepted")


class ApertureError(Exception):
    """skill 未知或 section 不存在。"""


@dataclass
class Projection:
    skill: str
    section: str
    reads: dict = field(default_factory=dict)     # artifact id -> 投影內容
    writes: list = field(default_factory=list)    # [{id, instruction, template, generates}]
    parent_briefs: list = field(default_factory=list)  # [{section, concept, brief, governed}]
    writing_guide: str | None = None              # 專案級寫作守則（draft/edit 注入）
    glossary: list = field(default_factory=list)  # 專案術語權威（draft 寫前拿正名/edit 對照；非事後 WARN）
    realized: list = field(default_factory=list)  # 本節 realizes 的共享決策 statement（跨文件真相）
    ancestor_normative: list = field(default_factory=list)  # [{section, decisions:[{id,statement}]}] 供 factcheck 核繼承一致性（非阻塞）
    forest: dict | None = None                    # 森林地圖（derive；只投 develop）：documents/hierarchy/parallel
    roadmap: list | None = None                   # 待辦 backlog（derive；只投 develop）：本文件＋forest 的 open/doing entry
    project_purpose: str | None = None            # config.purpose（森林整體目標；只投 develop 開工脈絡）
    image_assets: list = field(default_factory=list)  # 本節可用圖片（draft 放圖只能用這些；ref 形如 assets/<file>）
    document_map: list = field(default_factory=list)  # 本文件章節骨架（draft 看整篇架構：每節 section/title/order/role；只結構、不含 sibling 散文）
    coverage_contract: dict | None = None             # factcheck 完整性契約前景化：{must_cover:[...], layout, kind}（W3；餵非阻塞 audit）

# 注入寫作守則的 skill（連貫靠它替代跨節脈絡）
_GUIDE_SKILLS = ("draft", "edit")
# 注入術語權威的 skill：draft 寫前用正名、edit 對照、factcheck 核對＋拿 english 映回英文來源
_GLOSSARY_SKILLS = ("draft", "edit", "factcheck")
# 需要看到「本節 realizes 的共享真相」的 skill：draft 要渲染它、factcheck 要核對它
_REALIZED_SKILLS = ("draft", "factcheck")
# 需要知道「本節可放哪些圖」的 skill：draft 放圖、edit 核對引用不斷
_ASSET_SKILLS = ("draft", "edit")
# 需要看到「整篇章節骨架」的 skill：draft 寫角色開場（structure-visible / prose-blind）
_DOCUMENT_MAP_SKILLS = ("draft",)
# 需要祖先鏈 normative 決策的 skill：factcheck 做語義對抗稽核；**draft 落筆時遵守 ruling**
# （M4：draft 對父 ruling 全盲＝低層輸出不連貫的根源）。純供料、非阻塞——子違抗父仍只由 audit 表達。
_INHERITANCE_SKILLS = ("factcheck", "draft")
# 看得到森林整體目標（config.purpose）的 skill：develop 開工脈絡、draft 寫定向 overview 的北極星（W2）
_PURPOSE_SKILLS = ("develop", "draft")


def _yaml_text(obj: object) -> str:
    return yaml.safe_dump(obj, allow_unicode=True, sort_keys=False).strip()


def _read_concept(leaf: Leaf, skill: str) -> object:
    if leaf.concept is None:
        return None
    if skill == "draft":
        return {k: leaf.concept[k] for k in _DRAFT_CONCEPT_FIELDS if k in leaf.concept}
    return leaf.concept


def _read_decisions(leaf: Leaf, skill: str) -> object:
    if skill == "draft":
        # 只投 active 條目的 statement（剝 rationale/why/rejected/trace）
        return [
            {"id": e.get("id"), "statement": e.get("statement")}
            for e in leaf.decisions
            if str(e.get("status")) in _ACTIVE_STATUS
        ]
    return leaf.decisions


def _read_file(leaf: Leaf, filename: str) -> str | None:
    path = leaf.dir / filename
    return path.read_text(encoding="utf-8") if path.is_file() else None


def _read_docs(layout: Layout, leaf: Leaf) -> str | None:
    path = layout.docs_latest(leaf.article)
    return path.read_text(encoding="utf-8") if path.is_file() else None


def project(layout: Layout, schema: Schema, skill: str, section: str,
            leaves: list[Leaf], config: dict | None = None) -> Projection:
    if skill not in schema.skills:
        raise ApertureError(
            f"unknown skill \"{skill}\". Available: {', '.join(sorted(schema.skills))}"
        )
    by_section = {leaf.section: leaf for leaf in leaves}
    concept_by_id = {lf.concept["id"]: lf for lf in leaves
                     if lf.concept and lf.concept.get("id")}
    leaf = by_section.get(section)
    if leaf is None:
        raise ApertureError(f"leaf section not found \"{section}\"")

    spec = schema.skills[skill]
    proj = Projection(skill=skill, section=section)

    # ── reads（白名單裁切）──
    for art_id in spec.get("reads", []):
        if art_id == "concept":
            content = _read_concept(leaf, skill)
            if content:
                proj.reads["concept"] = _yaml_text(content)
        elif art_id == "decisions":
            content = _read_decisions(leaf, skill)
            if content:
                proj.reads["decisions"] = _yaml_text(content)
        elif art_id == "material":
            content = _read_file(leaf, "material.md")
            if content:
                proj.reads["material"] = content
        elif art_id == "develop":
            content = _read_file(leaf, "develop.md")
            if content:
                proj.reads["develop"] = content
        elif art_id == "history":
            content = _read_file(leaf, "history.yaml")
            if content:
                proj.reads["history"] = content
        elif art_id == "docs":
            content = _read_docs(layout, leaf)
            if content:
                proj.reads["docs"] = content

    # ── writes（artifact 的 instruction + template）──
    for art_id in spec.get("writes", []):
        artifact = schema.by_id(art_id)
        if artifact is None:
            continue
        proj.writes.append({
            "id": art_id,
            "generates": artifact.generates,
            "instruction": artifact.instruction.read_text(encoding="utf-8")
                           if artifact.instruction else None,
            "template": artifact.template.read_text(encoding="utf-8")
                        if artifact.template else None,
        })

    # ── realizes 撈共享真相（跨文件；draft 要渲染、factcheck 要核對）──
    # 只投 statement（與自己的決策同紀律）；是「該實現的真相」非「偷看鄰節散文」。
    if skill in _REALIZED_SKILLS:
        proj.realized = realized_statements(leaf, decision_index(leaves))

    # ── 本節圖片資產（draft 放圖只能用這些、edit 核引用；ref 形如 assets/<file>，backend-neutral）──
    if skill in _ASSET_SKILLS:
        proj.image_assets = [f"{ASSET_DIR_NAME}/{p.name}" for p in leaf.asset_files()]

    # ── 整篇章節骨架（draft：structure-visible / prose-blind）──
    # 投本文件每節的 section/title/order/role（concept 一句話），依 outline 順序；
    # 只含結構，絕不含 sibling 的散文/decisions/material——draft 用它寫「角色開場」、不指名鄰節。
    if skill in _DOCUMENT_MAP_SKILLS:
        article = leaf.article
        art_leaves = [lf for lf in leaves
                      if lf.article == article and lf.concept is not None]
        order_by_section = {lf.section: lf.order for lf in art_leaves}

        def _okey(sec: str) -> list:
            parts = [p for p in sec.split("/") if p]
            return [(order_by_section.get("/".join(parts[:i]), 0.0), parts[i - 1])
                    for i in range(1, len(parts) + 1)]

        art_leaves.sort(key=lambda lf: _okey(lf.section))
        proj.document_map = [
            {"section": lf.section, "title": lf.title, "order": lf.order,
             "role": (lf.concept.get("concept") or "")}
            for lf in art_leaves
        ]

    # ── 寫作守則（專案級、一份；draft/edit 注入，連貫靠它）──
    if skill in _GUIDE_SKILLS and layout.writing_guide.is_file():
        proj.writing_guide = layout.writing_guide.read_text(encoding="utf-8")

    # ── 術語權威（專案級；draft 寫前拿正名→不靠事後 lint WARN，閉合 writing-guide「術語→glossary」迴圈）──
    # 注入＝精瘦索引（canonical/bucket/code/aliases_forbidden）；definition/english＝下鑽（`docspec show <id>`），不 slurp。
    if skill in _GLOSSARY_SKILLS:
        proj.glossary = [
            {k: t[k] for k in _GLOSSARY_INDEX_FIELDS if k in t}
            for t in load_glossary(layout)
        ]

    # ── 父鏈 brief（agent 自己讀，引擎只遞）＋祖先鏈 normative 決策（factcheck 核繼承一致性）──
    # 疑問1 結論：scope 看父即可（可遞移），但 decision 不繼承→要看 root 起全祖先鏈 normative。
    # 引擎只「往上 glob 組裝、擺到 factcheck 桌上」＝供料；判矛盾/越界是 factcheck 的語義工作、非阻塞。
    # 祖先集＝路徑父鏈 ∪ governed-by 鏈（跨樹）；reuse 樹內繼承語義，governed 標來源。
    for anc, is_governed in ancestor_leaves(section, by_section, concept_by_id):
        if not anc.concept:
            continue
        proj.parent_briefs.append({
            "section": anc.section,
            "concept": anc.concept.get("concept"),
            "brief": anc.concept.get("brief"),
            "governed": is_governed,
        })
        if skill in _INHERITANCE_SKILLS:
            norms = [{"id": e.get("id"), "statement": e.get("statement")}
                     for e in anc.decisions
                     if e.get("kind") == "normative" and str(e.get("status")) in _ACTIVE_STATUS]
            if norms:
                proj.ancestor_normative.append({"section": anc.section, "decisions": norms})

    # ── 森林整體目標（config.purpose）：develop 開工脈絡 ＋ draft 寫定向 overview 的北極星（W2）──
    if skill in _PURPOSE_SKILLS and config:
        proj.project_purpose = config.get("purpose") or None

    # ── factcheck 完整性契約前景化（W3）：把 must_cover ＋ 有效 layout/kind 拉成獨立區塊，
    #    不埋在 raw concept dump 裡——完整性稽核最該打的攻擊面。純供料、餵非阻塞 audit。
    if skill == "factcheck" and leaf.concept is not None:
        brief = leaf.concept.get("brief")
        brief = brief if isinstance(brief, dict) else {}
        must = leaf.concept.get("must_cover")   # 頂層 concept 欄（非 brief 子欄）
        cc: dict = {}
        if isinstance(must, list) and must:
            cc["must_cover"] = list(must)
        if brief.get("layout"):
            cc["layout"] = brief.get("layout")
        if brief.get("kind"):
            cc["kind"] = brief.get("kind")
        if cc:
            proj.coverage_contract = cc

    # ── 森林地圖（derive；只投 develop——確認本文件在森林位置/被誰治理/跟誰平行）──
    if skill == "develop":
        proj.forest = forest_view(leaves)
        # ── 待辦 backlog（derive；只投 develop——開工先看計劃了還沒做的工作）──
        # reuse build_backlog_view（已掉 done/dropped、算 blocked/unblocked、按文件分組），
        # 只取「本文件 target」桶 ＋ forest 桶；其餘文件的 backlog 不投（aperture 紀律）。
        from dspx.commands.roadmap import FOREST_GROUP, build_backlog_view
        groups = build_backlog_view(layout, leaves)["groups"]
        proj.roadmap = list(groups.get(leaf.article, [])) + list(groups.get(FOREST_GROUP, []))

    return proj
