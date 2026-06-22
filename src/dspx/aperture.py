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
from dspx.model import Leaf, decision_index, realized_statements
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

# 注入寫作守則的 skill（連貫靠它替代跨節脈絡）
_GUIDE_SKILLS = ("draft", "edit")
# 注入術語權威的 skill：draft 寫前用正名、edit 對照、factcheck 核對＋拿 english 映回英文來源
_GLOSSARY_SKILLS = ("draft", "edit", "factcheck")
# 需要看到「本節 realizes 的共享真相」的 skill：draft 要渲染它、factcheck 要核對它
_REALIZED_SKILLS = ("draft", "factcheck")
# 需要祖先鏈 normative 決策當「繼承一致性」核對料的 skill（純供料、非阻塞；P3-lite）
_INHERITANCE_SKILLS = ("factcheck",)


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


def _path_parents(section: str, by_section: dict) -> list[Leaf]:
    """路徑父鏈（不含自己），由淺到深；只回有 leaf 的祖先。"""
    parts = section.split("/")
    out = []
    for depth in range(1, len(parts)):
        anc = by_section.get("/".join(parts[:depth]))
        if anc is not None:
            out.append(anc)
    return out


def _ancestor_leaves(section: str, by_section: dict,
                     concept_by_id: dict) -> list[tuple[Leaf, bool]]:
    """祖先集＝對「路徑父邊 ∪ governed-by 邊」做遞移閉包。

    回傳 [(ancestor_leaf, is_governed)]，依「先路徑父鏈、再跨樹治理」的順序：
    路徑父鏈優先且保持淺→深，確保無 governed-by 的單樹 path-only 行為逐欄等價。
    visited（by section）防環/去重——即使 check 未先擋環也不會無限。
    """
    result: list[tuple[Leaf, bool]] = []
    visited: set[str] = {section}      # 自己不算祖先（self-governed 環自保）

    def collect(leaf: Leaf, is_governed: bool) -> None:
        if leaf.section in visited:
            return
        visited.add(leaf.section)
        result.append((leaf, is_governed))

    # 種子＝起始節（不進 result、只供其 governed-by 邊被探索）＋路徑父鏈（淺→深）
    self_leaf = by_section.get(section)
    queue: list[Leaf] = [self_leaf] if self_leaf is not None else []
    for anc in _path_parents(section, by_section):
        collect(anc, False)
        queue.append(anc)

    # BFS：解析 governed-by → 跨樹父（is_governed=True），並折入其路徑父鏈
    i = 0
    while i < len(queue):
        leaf = queue[i]
        i += 1
        if not leaf.concept:
            continue
        for target_id in (leaf.concept.get("governed-by") or []):
            gov = concept_by_id.get(str(target_id))
            if gov is None or gov.section in visited:
                continue
            collect(gov, True)
            queue.append(gov)
            # 折入跨樹父自己的路徑父鏈（同樣標 governed＝來自治理鏈）
            for anc in _path_parents(gov.section, by_section):
                if anc.section not in visited:
                    collect(anc, True)
                    queue.append(anc)
    return result


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
    for anc, is_governed in _ancestor_leaves(section, by_section, concept_by_id):
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

    # ── 森林地圖（derive；只投 develop——確認本文件在森林位置/被誰治理/跟誰平行）──
    if skill == "develop":
        # 森林整體目標（config.purpose）——開工脈絡看得到整座森林/專案在幹嘛
        if config:
            proj.project_purpose = config.get("purpose") or None
        proj.forest = forest_view(leaves)
        # ── 待辦 backlog（derive；只投 develop——開工先看計劃了還沒做的工作）──
        # reuse build_backlog_view（已掉 done/dropped、算 blocked/unblocked、按文件分組），
        # 只取「本文件 target」桶 ＋ forest 桶；其餘文件的 backlog 不投（aperture 紀律）。
        from dspx.commands.roadmap import FOREST_GROUP, build_backlog_view
        groups = build_backlog_view(layout, leaves)["groups"]
        proj.roadmap = list(groups.get(leaf.article, [])) + list(groups.get(FOREST_GROUP, []))

    return proj
