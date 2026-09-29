"""唯一一份專案 roadmap（治理層；2026/09/29 裁定）：里程碑 → 工作項目 → 指向 change／文件。

與前一代 roadmap（`reports/roadmap.py`：每份文件一份＋森林一份、「在檔＝待辦、做完就移出」）
的差別：
- 住在 `docspec/governance/roadmap/`，一筆一檔（M-… 里程碑、W-… 工作項目）。
- **做完的項目保留**；狀態一律由系統推導（SR5、SR15），不手寫：
    done（完成）／done-waived（完成，含豁免）／in-progress（進行中）／
    blocked（卡住：前置未完成，或有未處理的可疑標記）／not-started（未開始）。
- 工作項目用 `refs` 指向實際執行的東西：
    `change:<id>`（文件 change；封存＝滿足）、`doc:<章節路徑>`（該節已同步＝滿足）、
    `doc:<文章>`（已發布且全部章節已同步＝滿足）、`gov:<id>`（決策生效／問題已裁定／裁定已確認）。
- 沒有 refs 的項目：有子項目就看子項目；否則只能以 `roadmap done --note` 手動結案。
- 計畫查核點（checkpoint）與交付物（deliverable）是不同的里程碑型別（SR15）。
舊專案用 `docspec roadmap migrate` 一次轉換（見 migrate_legacy）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dspx.engine import governance as gv
from dspx.engine.layout import Layout

DONE, DONE_WAIVED, IN_PROGRESS, BLOCKED, NOT_STARTED = (
    "done", "done-waived", "in-progress", "blocked", "not-started")
_FINISHED = (DONE, DONE_WAIVED)

_LABELS = {
    "zh": {DONE: "完成", DONE_WAIVED: "完成（含豁免 {n} 項）", IN_PROGRESS: "進行中",
           BLOCKED: "卡住", NOT_STARTED: "未開始"},
    "en": {DONE: "done", DONE_WAIVED: "done ({n} waived)", IN_PROGRESS: "in progress",
           BLOCKED: "blocked", NOT_STARTED: "not started"},
}


def status_label(status: str, item: dict, lang: str = "zh") -> str:
    n = len(item.get("waivers") or [])
    return _LABELS[lang][status].format(n=n)


@dataclass
class Context:
    """推導需要的專案狀態快照（一次建好，逐項查）。"""

    gov: gv.Governance
    change_states: dict[str, str]
    sync: dict[str, str]                 # section → sync
    articles: set[str]
    published: set[str]                  # 至少發布過一版的文章
    open_suspect_targets: set[str] = field(default_factory=set)


def build_context(layout: Layout, leaves: list, gov: gv.Governance | None = None) -> Context:
    from dspx.commands.query.status import _docs_hashes, compute_sync
    from dspx.engine import change as chg
    from dspx.engine.model import project_decision_index
    gov = gov or gv.load_governance(layout)
    by_section = {lf.section: lf for lf in leaves}
    dindex = project_decision_index(layout, leaves)
    sync: dict[str, str] = {}
    hashes: dict[str, dict] = {}
    for leaf in leaves:
        if leaf.article not in hashes:
            hashes[leaf.article] = _docs_hashes(layout, leaf.article)
        sync[leaf.section], _ = compute_sync(layout, leaf, hashes[leaf.article].get(leaf.section),
                                             by_section, dindex)
    articles = {lf.article for lf in leaves}
    published = {a for a in articles if layout.existing_versions(a)}
    return Context(gov=gov, change_states=chg.all_change_states(layout), sync=sync,
                   articles=articles, published=published,
                   open_suspect_targets={str(s.get("target")) for s in gov.suspects
                                         if s.get("status") == "open"})


def ref_state(ref: str, ctx: Context) -> str:
    """單一 ref 的狀態：done / in-progress / not-started / missing。"""
    ref = str(ref)
    if ref.startswith("change:"):
        st = ctx.change_states.get(ref[len("change:"):])
        return {"archived": DONE, "active": IN_PROGRESS}.get(st, "missing" if st is None else NOT_STARTED)
    if ref.startswith("doc:"):
        target = ref[len("doc:"):].strip("/")
        if target in ctx.sync:
            s = ctx.sync[target]
            return DONE if s == "synced" else NOT_STARTED if s == "unwritten" else IN_PROGRESS
        if target in ctx.articles:
            secs = [s for sec, s in ctx.sync.items() if sec.split("/", 1)[0] == target]
            if target in ctx.published and all(s == "synced" for s in secs):
                return DONE
            return IN_PROGRESS if any(s != "unwritten" for s in secs) else NOT_STARTED
        return "missing"
    if ref.startswith("gov:"):
        rid = gv.strip_ns(ref)
        gov = ctx.gov
        rec = gov.by_id().get(rid)
        if rec is None:
            return "missing"
        kind = gv.kind_of_id(rid)
        if kind == "decision":
            st = gv.decision_effective_status(rec, gov)
            return DONE if st in ("active", "superseded") else IN_PROGRESS if st == "draft" else NOT_STARTED
        if kind == "question":
            return DONE if gv.question_effective_status(rec, gov) in ("answered", "withdrawn") else NOT_STARTED
        if kind == "ruling":
            return DONE if gv.ruling_effective_status(rec, gov) in ("confirmed", "superseded") else IN_PROGRESS
        return NOT_STARTED
    return "missing"


def item_status(item: dict, ctx: Context, _seen: frozenset = frozenset()) -> str:
    iid = str(item.get("id"))
    if iid in _seen:                     # 環由 check 回報；推導時防無窮遞迴
        return BLOCKED
    seen = _seen | {iid}
    waived = bool(item.get("waivers"))
    fin = DONE_WAIVED if waived else DONE
    if item.get("closed"):
        return fin
    by_id = {str(w.get("id")): w for w in ctx.gov.work}
    children = [w for w in ctx.gov.work if str(w.get("parent")) == iid]
    refs = gv._as_list(item.get("refs"))
    states = [ref_state(r, ctx) for r in refs]
    child_states = [item_status(c, ctx, seen) for c in children]
    parts = states + child_states
    if parts and all(s in _FINISHED for s in parts):
        return DONE_WAIVED if waived or DONE_WAIVED in child_states else DONE
    for dep in gv._as_list(item.get("depends-on")):
        d = by_id.get(dep)
        if d is None or item_status(d, ctx, seen) not in _FINISHED:
            return BLOCKED
    if iid in ctx.open_suspect_targets:
        return BLOCKED
    if any(s in (DONE, DONE_WAIVED, IN_PROGRESS, BLOCKED) for s in parts):
        return IN_PROGRESS
    return NOT_STARTED


def view(layout: Layout, leaves: list, gov: gv.Governance | None = None) -> dict:
    """roadmap 檢視：{milestones:[{…, progress, items:[…]}], unassigned:[…]}。"""
    ctx = build_context(layout, leaves, gov)
    rows = {}
    for w in ctx.gov.work:
        rows[str(w["id"])] = {**{k: v for k, v in w.items() if not k.startswith("_")},
                              "status": item_status(w, ctx)}
    out = {"milestones": [], "unassigned": []}
    for m in ctx.gov.milestones:
        items = [r for r in rows.values() if str(r.get("milestone")) == str(m["id"])
                 and not r.get("parent")]
        done = sum(1 for r in items if r["status"] in _FINISHED)
        out["milestones"].append({**{k: v for k, v in m.items() if not k.startswith("_")},
                                  "done": done, "total": len(items),
                                  "status": DONE if items and done == len(items) else
                                  (IN_PROGRESS if done else NOT_STARTED),
                                  "items": items})
    out["unassigned"] = [r for r in rows.values() if not r.get("milestone") and not r.get("parent")]
    out["children"] = {pid: [r for r in rows.values() if str(r.get("parent")) == pid]
                       for pid in rows}
    return out


def progress_lines(layout: Layout, leaves: list, gov: gv.Governance, lang: str = "zh") -> list[str]:
    """一頁現況用：每個里程碑一行進度 ＋ 卡住的項目。"""
    if not gov.work and not gov.milestones:
        return []
    v = view(layout, leaves, gov)
    kind_name = {"zh": {"checkpoint": "查核點", "deliverable": "交付物"},
                 "en": {"checkpoint": "checkpoint", "deliverable": "deliverable"}}[lang]
    lines = []
    for m in v["milestones"]:
        due = f"，{m['due']}" if m.get("due") else ""
        lines.append(f"- {m['title']}（{kind_name.get(m.get('type'), m.get('type'))}{due}，"
                     f"{m['id']}）：{m['done']}/{m['total']}")
    stuck = [r for r in v["milestones"] for r in r["items"] if r["status"] == BLOCKED]
    stuck += [r for r in v["unassigned"] if r["status"] == BLOCKED]
    for r in stuck:
        lines.append(f"- {'卡住' if lang == 'zh' else 'blocked'}：{r['title']}（{r['id']}）")
    return lines


def validate_refs(layout: Layout, leaves: list, gov: gv.Governance) -> list[str]:
    """refs 死引用（check 層，需 corpus 與 changes 脈絡）。"""
    if not gov.work:
        return []
    ctx = build_context(layout, leaves, gov)
    errs = []
    for w in gov.work:
        for r in gv._as_list(w.get("refs")):
            if not r.startswith(("change:", "doc:", "gov:")):
                errs.append(f"governance work item {w.get('id')}: ref \"{r}\" must start with "
                            f"change:, doc: or gov:")
            elif ref_state(r, ctx) == "missing":
                errs.append(f"governance work item {w.get('id')}: ref \"{r}\" points to nothing")
    return errs


# ── 前一代 roadmap 的一次性轉換 ──────────────────────────────────────────────

def _section_path(target: str, leaves: list) -> str | None:
    for lf in leaves:
        if lf.section == target or (lf.concept and str(lf.concept.get("id")) == target):
            return lf.section
    return None


def migrate_legacy(layout: Layout, leaves: list, tool: str) -> dict:
    """把前一代 roadmap（森林＋每份文件＋roadmap-archive）轉進治理層 roadmap，並刪除舊檔。

    - 每筆 entry → 一個工作項目；target 節 → `doc:<章節路徑>`；promoted-to change → `change:<id>`。
    - depends-on 依新舊編號對照改寫；roadmap-archive 的完工紀錄 → 已結案（closed）的項目。
    - audit 的 promoted-to 若指向舊 R 編號，改寫成新編號。
    回傳 {mapping: {舊→新}, created: n, removed: [路徑]}。冪等：沒有舊檔就什麼都不做。"""
    from dspx.reports import roadmap as legacy
    entries = legacy.all_entries(layout, leaves)
    archive_path = legacy.forest_roadmap_archive_path(layout)
    archived = []
    if archive_path.is_file():
        import yaml
        data = yaml.safe_load(archive_path.read_text(encoding="utf-8")) or {}
        archived = [e for e in (data.get("entries") or []) if isinstance(e, dict)]
    if not entries and not archived:
        return {"mapping": {}, "created": 0, "removed": []}
    gov_dir = gv.gov_dir(layout)
    gov_dir.mkdir(parents=True, exist_ok=True)
    mapping: dict[str, str] = {}
    plan: list[tuple[str, dict]] = []
    def _num(e):
        rid = str(e.get("id", ""))
        return (0, int(rid[1:]), rid) if rid[1:].isdigit() else (1, 0, rid)

    for e in sorted(list(entries) + [{**a, "_archived": True} for a in archived], key=_num):
        new_id = gv.next_id(layout, "work", tool)
        n = int(new_id.rsplit("-", 1)[1]) + len(plan)
        new_id = f"W-{tool}-{n}"
        mapping[str(e.get("id"))] = new_id
        plan.append((new_id, e))
    for new_id, e in plan:
        rec: dict = {"id": new_id, "title": str(e.get("title") or e.get("id")),
                     "created-by": tool, "created-at": gv.today(), "legacy-id": str(e.get("id"))}
        for key in ("what", "kind", "priority", "from-audit"):
            if e.get(key):
                rec[key] = e[key]
        refs = []
        target = e.get("target")
        if target and target != legacy.FOREST_TARGET:
            path = _section_path(str(target), leaves)
            refs.append(f"doc:{path or target}")
        if e.get("promoted-to"):
            refs.append(f"change:{e['promoted-to']}")
        if refs:
            rec["refs"] = refs
        deps = [mapping.get(str(d), str(d)) for d in gv._as_list(e.get("depends-on"))]
        if deps:
            rec["depends-on"] = deps
        if e.get("_archived"):
            rec["closed"] = {"date": str(e.get("date") or gv.today()),
                             "note": str(e.get("note") or "")}
        gv.write_record(layout, "work", rec)
    _remap_audit_promotions(layout, leaves, mapping)
    removed = []
    paths = [legacy.forest_roadmap_path(layout), archive_path]
    for art in sorted({lf.article for lf in leaves}):
        paths.append(legacy.doc_roadmap_path(layout, art))
    for pth in paths:
        if pth.is_file():
            pth.unlink()
            removed.append(str(pth.relative_to(layout.project_root)))
    return {"mapping": mapping, "created": len(plan), "removed": removed}


def _remap_audit_promotions(layout: Layout, leaves: list, mapping: dict) -> None:
    from dspx.reports import audit
    stores = [audit.load_forest_audit(layout)]
    stores += [audit.load_doc_audit(layout, a) for a in sorted({lf.article for lf in leaves})]
    for store in stores:
        changed = False
        for f in store.findings:
            old = str(f.get("promoted-to") or "")
            if old in mapping:
                f["promoted-to"] = mapping[old]
                changed = True
        if changed:
            store.save()
