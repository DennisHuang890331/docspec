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
from dspx.glossary import GLOSSARY_INDEX_FIELDS, load_glossary
from dspx.layout import Layout
from dspx.model import (
    ACTIVE_DECISION_STATUSES,
    ASSET_DIR_NAME,
    Leaf,
    ancestor_leaves,
    decision_index,
    docs_asset_files,
    docs_drawio_files,
    realized_statements,
)
from dspx.schema import Schema

# apply（rewrite 模式）讀 concept 的准投欄位（治理欄 realizes 不投）
_DRAFT_CONCEPT_FIELDS = ("concept", "brief", "must_cover", "sources")
# glossary 注入＝精瘦索引（省 token）；definition/english 是下鑽欄（`docspec show <id>`），不注入。
# 白名單單一來源住 glossary.GLOSSARY_INDEX_FIELDS——style 面 gloss 子軸指紋（model）同源共用，
# 「投給 agent 的術語義務」與「入帳的術語義務」不可能漂移。
_GLOSSARY_INDEX_FIELDS = GLOSSARY_INDEX_FIELDS
# draft 讀 decisions 的 active 狀態（單一來源住 model.ACTIVE_DECISION_STATUSES；norm 軸同源共用）
_ACTIVE_STATUS = ACTIVE_DECISION_STATUSES


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
    document_map: list = field(default_factory=list)  # 本文件章節骨架（draft 看整篇架構：每節 section/title/order/number/role；number＝render 同源推導章號；只結構、不含 sibling 散文）
    coverage_contract: dict | None = None             # factcheck 完整性契約前景化：{must_cover:[...], layout, kind}（W3；餵非阻塞 audit）
    coherence_contract: dict | None = None            # factcheck 語義一致性探針：列出該核對「該一致的對」（title/framing/own-brief/decision/figure ↔ prose/祖先 brief）；純 projection、餵非阻塞 audit、零 gate（revision-coherence-probes）

# 注入寫作守則的 skill（連貫靠它替代跨節脈絡）：apply（rewrite 盲寫靠它、align 逐節核一致）
_GUIDE_SKILLS = ("apply",)
# 注入術語權威的 skill：apply 寫前用正名/對照、factcheck 核對＋拿 english 映回英文來源
_GLOSSARY_SKILLS = ("apply", "factcheck")
# 需要看到「本節 realizes 的共享真相」的 skill：apply（rewrite）要渲染它、factcheck 要核對它
_REALIZED_SKILLS = ("apply", "factcheck")
# 需要知道「本節可放哪些圖」的 skill：apply（rewrite 放圖、align 核對引用不斷）
_ASSET_SKILLS = ("apply",)
# 需要看到「整篇章節骨架」的 skill：apply（rewrite）寫角色開場（structure-visible / prose-blind）
_DOCUMENT_MAP_SKILLS = ("apply",)
# 需要祖先鏈 normative 決策的 skill：factcheck 做語義對抗稽核；**apply（rewrite）落筆時遵守 ruling**
# （M4：盲寫對父 ruling 全盲＝低層輸出不連貫的根源）。純供料、非阻塞——子違抗父仍只由 audit 表達。
_INHERITANCE_SKILLS = ("factcheck", "apply")
# 看得到森林整體目標（config.purpose）的 skill：develop 開工脈絡、apply 寫定向 overview 的北極星（W2）
_PURPOSE_SKILLS = ("develop", "apply")


def _yaml_text(obj: object) -> str:
    return yaml.safe_dump(obj, allow_unicode=True, sort_keys=False).strip()


def _read_concept(leaf: Leaf, skill: str) -> object:
    if leaf.concept is None:
        return None
    if skill == "apply":
        return {k: leaf.concept[k] for k in _DRAFT_CONCEPT_FIELDS if k in leaf.concept}
    return leaf.concept


def _read_decisions(leaf: Leaf, skill: str) -> object:
    if skill == "apply":
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
        proj.image_assets = [f"{ASSET_DIR_NAME}/{p.name}"
                             for p in docs_asset_files(layout, leaf.article)]

    # ── 整篇章節骨架（draft：structure-visible / prose-blind）──
    # 投本文件每節的 section/title/order/role（concept 一句話）＋分組節點列（group.yaml
    # title/order、無 role），依共用 outline 排序器（同 render 交付物順序，含 group order 合併）；
    # 只含結構，絕不含 sibling 的散文/decisions/material——draft 用它寫「角色開場」、不指名鄰節。
    if skill in _DOCUMENT_MAP_SKILLS:
        from dspx.render import (_group_order, _group_title, outline_group_nodes,
                                 outline_numbering, outline_order_by_section,
                                 outline_sort_key)
        article = leaf.article
        art_leaves = [lf for lf in leaves if lf.article == article]
        order_by_section = outline_order_by_section(layout, art_leaves)
        # 章號同源：與 render 交付物、`docspec list` 走同一 outline_numbering（單一真相＝order＋
        # 樹位置＋numbering 政策）；draft 看得到每節推導章號（None＝根節/numbering:none＝不編號）。
        numbers = outline_numbering(layout, art_leaves, article)
        rows = [
            {"section": lf.section, "title": lf.title, "order": lf.order,
             "number": numbers.get(lf.section),
             "role": (lf.concept.get("concept") or ""), "kind": "leaf"}
            for lf in art_leaves if lf.concept is not None
        ] + [
            {"section": gs, "title": _group_title(layout, gs, gs.rsplit("/", 1)[-1]),
             "order": _group_order(layout, gs),
             "number": numbers.get(gs), "role": None, "kind": "group"}
            for gs in outline_group_nodes(art_leaves)
        ]
        rows.sort(key=lambda r: outline_sort_key(r["section"], order_by_section))
        proj.document_map = rows

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

        # ── 語義一致性探針（revision-coherence-probes）：確定性列出「該保持一致的對」，
        #    factcheck 逐對讀 prose（已在 reads[docs]）/祖先 brief（已在 parent_briefs）判矛盾、
        #    非阻塞 audit raise。引擎只列、不判（語意判斷違鐵律1）。缺側者省略、不留空鷹架。
        coh: dict = {}
        title = leaf.concept.get("title")
        if isinstance(title, str) and title.strip():
            coh["title"] = title.strip()                       # ↔ 本節 prose
        framing = leaf.concept.get("concept")
        if isinstance(framing, str) and framing.strip():
            coh["framing"] = framing.strip()                   # concept 一句話框架 ↔ prose
        own_bd = {k: brief[k] for k in ("audience", "depth")
                  if isinstance(brief.get(k), str) and brief.get(k).strip()}
        if own_bd and proj.parent_briefs:                      # ↔ 祖先 brief（已在 parent_briefs）
            coh["own_brief"] = own_bd
        decs = [{"id": e.get("id"), "statement": e.get("statement"),
                 "rationale": e.get("rationale")}
                for e in leaf.decisions
                if e.get("statement") or e.get("rationale")]
        if decs:
            coh["decisions"] = decs                            # statement/rationale 框架 ↔ prose
        drawios = [p.name for p in docs_drawio_files(layout, leaf.article)]
        if drawios:
            coh["figures"] = [f"{ASSET_DIR_NAME}/{n}" for n in drawios]  # 圖框架 ↔ prose
        if proj.realized:
            # 本節 realizes 的跨文件共享真相 ↔ 本節 prose（多文件治理最易語義漂移處：上游 supersede
            # 後下游散文仍實現舊真相；hash 帳本只在 statement bytes 變時觸發重渲、不判 prose 是否還對齊）。
            coh["realized"] = [{"id": r.get("id"), "from_section": r.get("from_section"),
                                "statement": r.get("statement"), "status": r.get("status"),
                                "kind": r.get("kind"), "superseded_by": r.get("superseded_by"),
                                "successor_statement": r.get("successor_statement")}
                               for r in proj.realized]
        if coh:
            proj.coherence_contract = coh

    # ── 森林地圖（derive；只投 develop——確認本文件在森林位置/被誰治理/跟誰平行）──
    if skill == "develop":
        proj.forest = forest_view(leaves, layout)
        # ── 待辦 backlog（derive；只投 develop——開工先看計劃了還沒做的工作）──
        # reuse build_backlog_view（統無狀態模型：在檔皆待辦、算 blocked/unblocked、按文件分組），
        # 只取「本文件 target」桶 ＋ forest 桶；其餘文件的 backlog 不投（aperture 紀律）。
        from dspx.commands.roadmap import FOREST_GROUP, build_backlog_view
        groups = build_backlog_view(layout, leaves)["groups"]
        proj.roadmap = list(groups.get(leaf.article, [])) + list(groups.get(FOREST_GROUP, []))

    return proj
