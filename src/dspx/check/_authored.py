"""check：手寫規定檔紀律的機械後盾（agent-contract ★#27 / ★#6.2b；皆 WARN、非阻塞）。

紀律本身是 runtime 行為（agent 該不該停下問人、該不該手勾），引擎測不到；但兩件事引擎**看得到**：
- ★#27 繼承信封矛盾：某節的祖先集（樹內父鏈 ∪ governed-by 遞移閉包）對**同一 brief 欄**由兩個
  來源給出 byte 相異的值——結構性矛盾。引擎不裁決（語義→人），只 WARN 吵鬧，即使 agent 沒停下
  也抓得到。
- ★#6.2b 手寫規定檔帶狀態：brief / writing-guide.md / change notes.md 出現 checkbox（`- [ ]`／
  `- [x]`）或 `status:` 欄——完成度永遠導出，規定檔不得帶狀態。
"""

from __future__ import annotations

import re

from dspx.model import Leaf, ancestor_leaves

# brief 可比對子欄（differential brief；跨來源同欄異值＝矛盾）
_BRIEF_FIELDS = ("audience", "depth", "breadth", "forbidden", "layout", "kind")
_CHECKBOX_RE = re.compile(r"^\s*[-*]\s*\[[ xX]\]", re.MULTILINE)
_STATUS_LINE_RE = re.compile(r"^\s*status\s*:", re.MULTILINE)


def _brief_of(leaf: Leaf) -> dict:
    if leaf.concept is None:
        return {}
    b = leaf.concept.get("brief")
    return b if isinstance(b, dict) else {}


def check_inherited_conflicts(leaves: list[Leaf]) -> list[str]:
    """★#27 後盾：祖先集同一 brief 欄兩來源 byte 相異 → WARN（列兩來源；不裁決）。

    紀律：differential brief 沿路徑父鏈是「就近覆寫」（正常、非矛盾）；真矛盾＝路徑父鏈的有效值
    與某 governed-by 跨樹治理者不同，或兩個治理者彼此不同（無 precedence、語義判斷→人）。"""
    by_section = {lf.section: lf for lf in leaves}
    concept_by_id = {lf.concept["id"]: lf for lf in leaves
                     if lf.concept and lf.concept.get("id")}
    warns: list[str] = []
    for leaf in leaves:
        ancs = ancestor_leaves(leaf.section, by_section, concept_by_id)
        # 路徑父鏈（is_governed=False）依由淺到深，最深提供者＝有效值；governed 各自為來源。
        path_ancs = [(a, g) for a, g in ancs if not g]
        gov_ancs = [(a, g) for a, g in ancs if g]
        for field in _BRIEF_FIELDS:
            path_val = None
            path_src = None
            for a, _g in path_ancs:      # 由淺到深；後者覆蓋前者＝就近有效值
                v = _brief_of(a).get(field)
                if v is not None:
                    path_val, path_src = v, a.section
            gov_vals: list[tuple[str, object]] = []
            for a, _g in gov_ancs:
                v = _brief_of(a).get(field)
                if v is not None:
                    gov_vals.append((a.section, v))
            # 路徑有效值 vs 每個治理者
            for gsrc, gval in gov_vals:
                if path_val is not None and gval != path_val:
                    warns.append(
                        f"{leaf.section}/concept.yaml: inherited brief.{field} CONFLICT — "
                        f"tree-parent [{path_src}]={path_val!r} vs cross-tree governor "
                        f"[{gsrc}]={gval!r}; the engine does not adjudicate — surface both to the "
                        "human (agent-contract #27)")
            # 治理者彼此
            for i in range(len(gov_vals)):
                for j in range(i + 1, len(gov_vals)):
                    if gov_vals[i][1] != gov_vals[j][1]:
                        warns.append(
                            f"{leaf.section}/concept.yaml: inherited brief.{field} CONFLICT — "
                            f"governors [{gov_vals[i][0]}]={gov_vals[i][1]!r} vs "
                            f"[{gov_vals[j][0]}]={gov_vals[j][1]!r}; adjudicate with the human")
    return warns


def _scan_state_markers(text: str) -> list[str]:
    hits: list[str] = []
    if _CHECKBOX_RE.search(text):
        hits.append("a checkbox (- [ ] / - [x])")
    if _STATUS_LINE_RE.search(text):
        hits.append("a status: field")
    return hits


def check_authored_state(layout, leaves: list[Leaf]) -> list[str]:
    """★#6.2b 後盾：手寫規定檔（brief / writing-guide.md / change notes.md）帶 checkbox/status 欄
    → WARN。完成度永遠導出、規定檔不得帶狀態；此條可機械偵測，不純靠自律。"""
    warns: list[str] = []
    # brief 內字串子欄的 checkbox（brief 是結構化 dict，status 欄由 closed-schema 另擋；這裡抓散文式）
    for leaf in leaves:
        brief = _brief_of(leaf)
        for k, v in brief.items():
            if isinstance(v, str) and _CHECKBOX_RE.search(v):
                warns.append(f"{leaf.section}/concept.yaml: brief.{k} contains a checkbox — "
                             "completeness is always DERIVED; an authored instruction field must "
                             "not carry state (agent-contract #6.2b)")
    # writing-guide.md
    wg = layout.writing_guide
    if wg.is_file():
        for hit in _scan_state_markers(wg.read_text(encoding="utf-8")):
            warns.append(f"writing-guide.md contains {hit} — authored doctrine must not carry "
                         "state; completeness is derived (agent-contract #6.2b)")
    # change notes.md（active changes）
    try:
        from dspx import change as chg
        for cid in chg.active_change_ids(layout):
            notes = chg.notes_path(chg.change_dir(layout, cid, chg.STATE_ACTIVE))
            if notes.is_file():
                for hit in _scan_state_markers(notes.read_text(encoding="utf-8")):
                    warns.append(f"changes/{cid}/notes.md contains {hit} — progress is DERIVED by "
                                 "`docspec change status`; notes.md must not carry state (#6.2b)")
    except Exception:  # noqa: BLE001 — change 子系統缺席時不影響其餘 check
        pass
    return warns
