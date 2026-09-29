"""治理層檢視（第一期第 6 步）：一頁現況、目前有效設計、待批准清單。

檢視是**產生物**：每次從紀錄重新產生、整份覆寫，不接受手改（SR1）。
給使用者看的內容一律白話、條列，編號只放在括號裡（SR17）；一頁現況有長度上限（SR16，
預設 2000 字），超出的清單只列前幾項並註明「還有幾項，用哪個指令看」。
"""

from __future__ import annotations

import datetime

from dspx.engine import governance as gv
from dspx.engine.config import lang_subtag
from dspx.engine.impact import doc_sections_needing_review
from dspx.engine.layout import Layout

BRIEF_LIMIT = 2000
_LIST_CAP = 5

_T = {
    "zh": {
        "brief_title": "專案現況", "generated": "產生時間",
        "todo": "需要你處理", "approve": "待批准（在終端機執行 `docspec approve`）",
        "questions": "待你裁定的問題", "review": "需要重看", "suspects": "可疑標記",
        "sections": "文件章節", "recent_rulings": "最近的裁定", "decisions": "目前有效的決策",
        "docs": "文件狀態", "roadmap": "工作進度", "next": "下一步", "none": "無",
        "more": "還有 {n} 項，用 `{cmd}` 查看", "unconfirmed": "未經本人確認",
        "pending_conf": "待你確認", "provisional": "暫定",
        "doc_line": "{article}：{total} 節，已同步 {synced}，需更新 {stale}，未寫 {unwritten}",
        "n_approve": "有 {n} 項待你批准：請在終端機執行 `docspec approve`。",
        "n_q": "有 {n} 個問題等你裁定。",
        "n_review": "有 {n} 項受上游變更影響，需要重看（`docspec impact`）。",
        "n_stale": "有 {n} 個文件章節需要更新內容。",
        "all_clear": "目前沒有卡住的事項。",
        "design_title": "目前有效的設計", "based_on": "依據", "history": "取代了",
        "pending_title": "待批准事項", "ruling": "裁定", "request": "申請", "quote": "原話",
        "interp": "agent 的解讀", "nothing": "（沒有）",
    },
    "en": {
        "brief_title": "Project status", "generated": "Generated",
        "todo": "Needs you", "approve": "Awaiting approval (run `docspec approve` in a terminal)",
        "questions": "Questions awaiting your ruling", "review": "Needs review",
        "suspects": "Suspect flags", "sections": "Document sections",
        "recent_rulings": "Recent rulings", "decisions": "Active decisions",
        "docs": "Documents", "roadmap": "Progress", "next": "Next steps", "none": "none",
        "more": "{n} more — see `{cmd}`", "unconfirmed": "not confirmed by the owner",
        "pending_conf": "awaiting your confirmation", "provisional": "provisional",
        "doc_line": "{article}: {total} sections, {synced} synced, {stale} need updating, "
                    "{unwritten} unwritten",
        "n_approve": "{n} item(s) await your approval: run `docspec approve` in a terminal.",
        "n_q": "{n} question(s) await your ruling.",
        "n_review": "{n} item(s) were affected by upstream changes and need review (`docspec impact`).",
        "n_stale": "{n} document section(s) need their prose updated.",
        "all_clear": "Nothing is blocked right now.",
        "design_title": "Current effective design", "based_on": "Based on", "history": "Replaces",
        "pending_title": "Pending approvals", "ruling": "Ruling", "request": "Request",
        "quote": "Words", "interp": "Agent's reading", "nothing": "(none)",
    },
}


def _lang(config: dict | None) -> str:
    return "zh" if lang_subtag((config or {}).get("language")) == "zh" else "en"


def _label(rec: dict, width: int = 50) -> str:
    title = rec.get("title") or rec.get("quote") or rec.get("summary") or ""
    title = " ".join(str(title).split())
    if len(title) > width:
        title = title[:width - 1] + "…"
    return f"{title}（{rec.get('id')}）"


def _capped(lines: list[str], cmd: str, t: dict, cap: int = _LIST_CAP) -> list[str]:
    if len(lines) <= cap:
        return lines
    return lines[:cap] + ["- " + t["more"].format(n=len(lines) - cap, cmd=cmd)]


def doc_summary(layout: Layout, leaves: list) -> list[dict]:
    """每篇文章的同步狀態統計（沿用 status 的 compute_sync＝同一判準，不另算）。"""
    from dspx.commands.query.status import _docs_hashes, compute_sync
    from dspx.engine.model import project_decision_index
    by_section = {lf.section: lf for lf in leaves}
    dindex = project_decision_index(layout, leaves)
    out: dict[str, dict] = {}
    hashes: dict[str, dict] = {}
    for leaf in leaves:
        art = leaf.article
        if art not in hashes:
            hashes[art] = _docs_hashes(layout, art)
        sync, _ = compute_sync(layout, leaf, hashes[art].get(leaf.section), by_section, dindex)
        row = out.setdefault(art, {"article": art, "total": 0, "synced": 0, "stale": 0,
                                   "unwritten": 0})
        row["total"] += 1
        if sync == "synced":
            row["synced"] += 1
        elif sync == "unwritten":
            row["unwritten"] += 1
        else:
            row["stale"] += 1
    return list(out.values())


def brief(layout: Layout, leaves: list, config: dict | None = None,
          limit: int = BRIEF_LIMIT) -> str:
    """一頁現況：整份重新產生；超過 limit 字時逐步縮短清單。"""
    for cap in (_LIST_CAP, 3, 1, 0):
        text = _brief(layout, leaves, config, cap)
        if len(text) <= limit:
            return text
    return text[:limit]


def _brief(layout: Layout, leaves: list, config: dict | None, cap: int) -> str:
    t = _T[_lang(config)]
    gov = gv.load_governance(layout) if gv.has_governance(layout) else gv.Governance([], [], [], [], [])
    lines = [f"# {t['brief_title']}", "",
             f"{t['generated']}：{datetime.date.today().strftime('%Y/%m/%d')}", ""]

    pend = [r for r in gov.rulings if r.get("status") == "pending"] + \
        [q for q in gov.requests if q.get("status") == "pending"]
    qs = [q for q in gov.questions if gv.question_effective_status(q, gov) in ("open", "needs-explanation")]
    suspects = [s for s in gov.suspects if s.get("status") == "open"]
    review_secs = doc_sections_needing_review(layout, leaves, gov)
    docs = doc_summary(layout, leaves)
    stale_total = sum(d["stale"] for d in docs)

    lines.append(f"## {t['next']}")
    nxt = []
    if pend:
        nxt.append("- " + t["n_approve"].format(n=len(pend)))
    if qs:
        nxt.append("- " + t["n_q"].format(n=len(qs)))
    if suspects or review_secs:
        nxt.append("- " + t["n_review"].format(n=len(suspects) + len(review_secs)))
    if stale_total:
        nxt.append("- " + t["n_stale"].format(n=stale_total))
    lines += nxt or ["- " + t["all_clear"]]
    lines.append("")

    if pend or qs:
        lines.append(f"## {t['todo']}")
        if pend:
            lines.append(f"{t['approve']}：")
            lines += _capped([f"- {_label(r)}" for r in pend], "docspec approve --list", t, cap)
        if qs:
            lines.append(f"{t['questions']}：")
            lines += _capped([f"- {_label(q)}" for q in qs], "docspec question list", t, cap)
        lines.append("")

    if suspects or review_secs:
        by_id = gov.by_id()
        lines.append(f"## {t['review']}")
        items = [f"- {_label(by_id.get(str(s.get('target')), {'id': s.get('target')}))}"
                 for s in suspects]
        items += [f"- {r['title']}（{r['section']}）" for r in review_secs]
        lines += _capped(items, "docspec impact", t, cap)
        lines.append("")

    recent = sorted(gov.rulings, key=lambda r: str(r.get("date")), reverse=True)
    if recent:
        lines.append(f"## {t['recent_rulings']}")
        items = []
        for r in recent:
            st = gv.ruling_effective_status(r, gov)
            if st in ("rejected", "superseded"):
                continue
            tag = {"pending": t["pending_conf"], "recorded": t["unconfirmed"]}.get(st)
            if r.get("provisional"):
                tag = f"{tag}，{t['provisional']}" if tag else t["provisional"]
            items.append(f"- {r.get('date')}「{_label(r, 40)}」" + (f"（{tag}）" if tag else ""))
        lines += _capped(items, "docspec ruling list", t, cap)
        lines.append("")

    active = [d for d in gov.decisions if gv.decision_effective_status(d, gov) == "active"]
    if active:
        lines.append(f"## {t['decisions']}（{len(active)}）")
        lines += _capped([f"- {_label(d)}" for d in active], "docspec decision list", t, cap)
        lines.append("")

    try:
        from dspx.engine.roadmap_v2 import progress_lines
        prog = progress_lines(layout, leaves, gov, _lang(config))
    except ImportError:
        prog = []
    if prog:
        lines.append(f"## {t['roadmap']}")
        lines += _capped(prog, "docspec roadmap", t, cap)
        lines.append("")

    if docs:
        lines.append(f"## {t['docs']}")
        lines += [f"- {t['doc_line'].format(**d)}" for d in docs][:max(cap, 1) * 2]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def effective_design(layout: Layout, config: dict | None = None) -> str:
    """目前有效設計：只列有效決策（完整現行內容）與依據、取代了誰。"""
    t = _T[_lang(config)]
    gov = gv.load_governance(layout)
    rulings = {str(r.get("id")): r for r in gov.rulings}
    lines = [f"# {t['design_title']}", ""]
    active = [d for d in gov.decisions if gv.decision_effective_status(d, gov) == "active"]
    if not active:
        lines.append(t["nothing"])
    for d in active:
        lines += [f"## {_label(d, 80)}", "", str(d.get("statement", "")).strip(), ""]
        basis = [f"「{_label(rulings[r], 40)}」" for r in gv._as_list(d.get("based-on")) if r in rulings]
        if basis:
            lines.append(f"- {t['based_on']}：{'、'.join(basis)}")
        if d.get("supersedes"):
            lines.append(f"- {t['history']}：{'、'.join(gv._as_list(d.get('supersedes')))}"
                         f"（`docspec decision show {d['id']}`）")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def pending_list(layout: Layout, config: dict | None = None) -> str:
    t = _T[_lang(config)]
    gov = gv.load_governance(layout)
    lines = [f"# {t['pending_title']}", "", t["approve"], ""]
    items = 0
    for r in gov.rulings:
        if r.get("status") == "pending":
            items += 1
            lines += [f"- {t['ruling']}：{_label(r, 80)}", f"  - {t['quote']}：「{r.get('quote')}」"]
            if r.get("interpretation"):
                lines.append(f"  - {t['interp']}：{r['interpretation']}")
    for q in gov.requests:
        if q.get("status") == "pending":
            items += 1
            lines.append(f"- {t['request']}：{_label(q, 80)}")
    qs = [q for q in gov.questions if gv.question_effective_status(q, gov) in ("open", "needs-explanation")]
    if qs:
        lines += ["", f"## {t['questions']}", ""]
        lines += [f"- {_label(q, 80)}" for q in qs]
    if not items and not qs:
        lines.append(t["nothing"])
    return "\n".join(lines).rstrip() + "\n"
