"""check：結構性層級不變量（⑦，root-brief 完整 / 兄弟 order 唯一 / supersede 一致性 / 標題深度上界）。"""

from __future__ import annotations

from dspx.model import Leaf
from dspx.render import MAX_HEADING_LEVEL, _depth


def _check_hierarchy(leaves: list[Leaf]) -> list[str]:
    """結構性層級不變量（確定性，複用 section 路徑＋全專案 id index）：
    (a) root-brief 完整——只有 article root（section 無 '/'）必填 audience/depth/breadth；
    (b) 兄弟 order 唯一——同父群組 order 不可撞號（否則 TOC 排序不確定）；
    (c) supersede 一致性——A.supersedes B ⟹ B.status∈{superseded,deprecated} 且 B.superseded-by==A；
    (d) 標題深度上界——末節映出的標題層級（depth+1）不得超過 MAX_HEADING_LEVEL（四級）；
        更深 render 會吐 `#######`＝CommonMark 字面文字、靜默破版。與 render 共用同一 `_depth`。
    語義（子是否真的窄於父等）不在此——那是 audit。"""
    errs: list[str] = []
    required_brief = ("audience", "depth", "breadth")
    by_parent: dict[str, dict] = {}
    entry_by_id: dict[str, dict] = {}
    for leaf in leaves:
        for e in (*leaf.decisions, *leaf.history):
            if e.get("id"):
                entry_by_id[str(e["id"])] = e

    for leaf in leaves:
        if leaf.concept is None:
            continue
        sec = leaf.section
        # (d) 標題深度上界（四級＝1.1.1.1；更深→#######=字面文字、破版）；與 render 同一 _depth 定義
        level = _depth(leaf.article, sec) + 1
        if level > MAX_HEADING_LEVEL:
            errs.append(f"{sec}: section nests too deep -> heading level {level} exceeds the H{MAX_HEADING_LEVEL} cap "
                        f"(deepest allowed is level {MAX_HEADING_LEVEL}, 四級/1.1.1.1). Flatten the section tree.")
        # (a) root-brief 完整（root＝section 無 '/'；子節省略＝繼承，不查）
        if "/" not in sec:
            brief = leaf.concept.get("brief")
            if not isinstance(brief, dict):
                errs.append(f"{sec}: root section missing brief (root must fill in the writing envelope; child sections inherit)")
            else:
                for f in required_brief:
                    v = brief.get(f)
                    if v is None or (isinstance(v, str) and not v.strip()):
                        errs.append(f"{sec}: root section brief.{f} missing or empty (root must be fully filled in; child sections inherit)")
        # (b) 兄弟 order 唯一
        order = leaf.concept.get("order")
        if order is not None:
            parent = sec.rsplit("/", 1)[0] if "/" in sec else ""
            grp = by_parent.setdefault(parent, {})
            if order in grp:
                errs.append(f"{sec}: order {order!r} collides with sibling \"{grp[order]}\" -> TOC ordering is nondeterministic")
            else:
                grp[order] = sec

    # (c) supersede 一致性（全專案 id index，非祖先走鏈）
    for leaf in leaves:
        for e in (*leaf.decisions, *leaf.history):
            sup = e.get("supersedes")
            if not sup:
                continue
            a_id = str(e.get("id", "?"))
            b = entry_by_id.get(str(sup))
            if b is None:
                continue                      # 死引用已另報
            if str(b.get("status")) not in ("superseded", "deprecated"):
                errs.append(f"{leaf.section}: \"{a_id}\" supersedes \"{sup}\", but \"{sup}\""
                            f" status should be superseded/deprecated (currently {b.get('status')})")
            if str(b.get("superseded-by") or "") != a_id:
                errs.append(f"{leaf.section}: \"{sup}\"'s superseded-by should point back to \"{a_id}\""
                            f" (currently {b.get('superseded-by')!r})")
    return errs
