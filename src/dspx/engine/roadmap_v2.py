"""唯一一份專案 roadmap（治理層；2026/09/29 裁定）：里程碑 → 工作項目 → 指向 change／文件。

與前一代 roadmap（`reports/roadmap.py`：每份文件一份＋森林一份、「在檔＝待辦、做完就移出」）
的差別：
- 住在 `docspec/governance/roadmap/`，一筆一檔（M-… 里程碑、W-… 工作項目）。
- **做完的項目保留**；狀態一律由系統推導（SR5、SR15），不手寫：
    done（完成）／done-waived（完成，含豁免）／in-progress（進行中）／
    blocked（卡住：前置未完成，或有未處理的可疑標記）／not-started（未開始）。
- 工作項目用 `refs` 指向實際執行的東西：
    `change:<id>`（文件 change；封存＝滿足）、`doc:<章節路徑>`（該節已同步＝滿足）、
    `doc:<文章>`（目前內容已定版且全部章節已同步＝滿足）、`gov:Q-…`／`gov:RL-…`（問題已裁定／裁定已記錄生效）。
    `swc:<id>`（軟體 change；封存＝完成，封存時有豁免的任務＝完成含豁免；受上游決策影響＝卡住）。
    `gov:D-…`（決策）與 `gov:I-…`（資訊）是**背景依據**不是完成條件：
    保留引用、有效狀態與影響提醒，但依據存在或生效不代表工作做完。
- 沒有成果 refs 的項目（含只有背景依據）：有子項目就看子項目；
  否則只能以 `roadmap done --note` 手動結案。
- 計畫查核點（checkpoint）與交付物（deliverable）是不同的里程碑型別（SR15）。
舊專案用 `artispec roadmap migrate` 一次轉換（見 migrate_legacy）。
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
    n = len(item.get("waivers") or []) + int(item.get("software-waived") or 0)
    if status == DONE_WAIVED and not n:          # 豁免在軟體 change 的任務裡，不在項目上
        return "完成（含豁免）" if lang == "zh" else "done (with waivers)"
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
    sw_changes: dict[str, str] = field(default_factory=dict)    # 軟體 change → active／archived／archived-waived
    sw_waived: dict[str, int] = field(default_factory=dict)     # 封存時豁免的任務數
    frozen_current: set[str] = field(default_factory=set)
    sw_details: dict[str, list[str]] = field(default_factory=dict)
    source_problems: dict[str, list[str]] = field(default_factory=dict)


def build_context(layout: Layout, leaves: list, gov: gv.Governance | None = None,
                  *, include_details: bool = False) -> Context:
    from dspx.commands.query.status import _docs_hashes, compute_sync
    from dspx.engine import change as chg
    from dspx.engine import project_baseline as pb
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
                                             by_section, dindex,
                                             deliverable_missing=not layout.docs_latest(leaf.article).is_file())
    articles = {lf.article for lf in leaves}
    published = {a for a in articles if layout.existing_versions(a)}
    frozen_current = {a for a in published if layout.docs_latest(a).is_file()
                      and not pb._has_unfrozen_edits(layout, a, pb._latest_frozen(layout, a))}
    sw_changes, sw_waived = _software_change_states(layout)
    return Context(gov=gov, change_states=chg.all_change_states(layout), sync=sync,
                   articles=articles, published=published, frozen_current=frozen_current,
                   open_suspect_targets={str(s.get("target")) for s in gov.suspects
                                         if s.get("status") == "open"},
                   sw_changes=sw_changes, sw_waived=sw_waived,
                   sw_details=_software_details(layout, {cid: st for cid, st in sw_changes.items()
                       if any(f"swc:{cid}" in gv._as_list(w.get("refs")) for w in gov.work)})
                       if include_details else {},
                   source_problems=_governance_source_problems(gov))


def _governance_source_problems(gov: gv.Governance) -> dict[str, list[str]]:
    """Validate only governance sources reachable from each explicit work reference.

    Following a successor and its preserved predecessor is normal traversal, not
    a supersession cycle. Reuse the governance validator's directed cycle check
    after collecting the related family, then feed problems to the existing
    roadmap judgment rather than computing another completion status.
    """
    records = gov.by_id()
    successors: dict[str, list[str]] = {}
    answering: dict[str, list[str]] = {}
    effective = {"decision": "active", "ruling": "effective", "info": "current"}
    for rid, rec in records.items():
        kind = gv.kind_of_id(rid)
        if kind in effective and rec.get("status") == effective[kind]:
            for old in gv._as_list(rec.get("supersedes")):
                successors.setdefault(gv.strip_ns(old), []).append(rid)
        if kind == "ruling" and rec.get("status") == "effective":
            for question in gv._as_list(rec.get("answers")):
                answering.setdefault(gv.strip_ns(question), []).append(rid)
    out: dict[str, list[str]] = {}
    refs = dict.fromkeys(ref for work in gov.work for ref in gv._as_list(work.get("refs"))
                         if ref.startswith(gv.GOV_NAMESPACE))
    for ref in refs:
        pending = [(gv.strip_ns(ref), ref)]
        seen: set[str] = set()
        related: dict[str, dict] = {}
        problems = []
        while pending:
            rid, source = pending.pop()
            if rid in seen:
                continue
            seen.add(rid)
            rec = records.get(rid)
            if rec is None:
                problems.append(f"治理來源不存在: gov:{rid}（來源 {source}）")
                continue
            related[rid] = rec
            for key in ("based-on", "answers", "supersedes"):
                pending.extend((gv.strip_ns(target), f"gov:{rid}")
                               for target in gv._as_list(rec.get(key)))
            pending.extend((new, f"gov:{rid}") for new in successors.get(rid, []))
            pending.extend((answer, f"gov:{rid}") for answer in answering.get(rid, []))
        for kind in effective:
            family = [{**rec, "supersedes": [gv.strip_ns(target)
                                            for target in gv._as_list(rec.get("supersedes"))]}
                      for rid, rec in related.items() if gv.kind_of_id(rid) == kind]
            problems.extend(gv._supersede_cycles(family, kind))
        if problems:
            out[ref] = list(dict.fromkeys(problems))
    return out


def _software_details(layout: Layout, states: dict[str, str]) -> dict[str, list[str]]:
    """Reuse evidence derivation without refreshing tasks or running an executor."""
    from dspx.engine.software import archive, changes, evidence, io, tasks
    details = {}
    for cid, state in states.items():
        if state != "active":
            continue
        notes = []
        try:
            ch = changes.load_change(layout, cid)
            if not ch["tasks"].get("tasks"):
                notes.append("尚未建立實作任務")
            for row in evidence.explain(layout, cid):
                if row["status"] not in ("done", "done-waived"):
                    notes.append(f"{row['task']} ({row['status']}): {row['why']}")
            labels = {"requirements-without-task": "需求尚無實作任務",
                      "scenarios-without-test": "情境尚無測試計畫",
                      "tests-without-task": "測試尚未連結任務",
                      "tasks-without-tests": "任務待測試規劃",
                      "tasks-to-complete": "任務資料待補齊"}
            for key, values in tasks.gaps(layout, ch).items():
                if values:
                    names = [str(v.get("id", v)) if isinstance(v, dict) else str(v) for v in values]
                    notes.append(f"{labels.get(key, key)}: {', '.join(names)}")
            # This function only reads existing records; archive.plan would refresh tasks.
            for problem in archive.blockers(layout, ch, evidence.load_all(layout)):
                if not problem.startswith("task "):
                    notes.append(problem)
            if not notes:
                notes.append("任務已有完成證據，尚未封存；仍需查核封存條件")
        except (io.SoftwareError, OSError, ValueError) as exc:
            notes.append(f"無法讀取軟體狀態: {exc}")
        notes.append(f"查看 `artispec code change status {cid}`；封存查核 `artispec archive {cid} --dry-run`")
        details[cid] = notes
    return details


def _software_change_states(layout: Layout) -> tuple[dict[str, str], dict[str, int]]:
    from dspx.engine.software import changes as swc
    from dspx.engine.software import io as swio
    if not swio.has_software(layout):
        return {}, {}
    out = {c: "active" for c in swc.list_active(layout)}
    waived_n: dict[str, int] = {}
    for cid, folder in swc.archived_ids(layout).items():
        base = swio.baselines_dir(layout) / f"{folder}.yaml"
        n = 0
        if base.is_file():
            try:
                n = int((swio.load(base, "baseline").get("tasks") or {}).get("done-waived") or 0)
            except (swio.SoftwareError, ValueError):
                pass
        out[cid] = "archived-waived" if n else "archived"
        if n:
            waived_n[cid] = n
    return out, waived_n


def is_constraint_ref(ref: str) -> bool:
    """治理決策與資訊是背景依據（只供追溯與影響分析，不算成果完成條件）。"""
    return (str(ref).startswith(gv.GOV_NAMESPACE)
            and gv.kind_of_id(gv.strip_ns(ref)) in ("decision", "info"))


def ref_state(ref: str, ctx: Context) -> str:
    """單一 ref 的狀態：done / in-progress / not-started / missing。"""
    ref = str(ref)
    if ref.startswith("change:"):
        st = ctx.change_states.get(ref[len("change:"):])
        return {"archived": DONE, "active": IN_PROGRESS}.get(st, "missing" if st is None else NOT_STARTED)
    if ref.startswith("swc:"):
        st = ctx.sw_changes.get(ref[len("swc:"):])
        if st is None:
            return "missing"
        if st.startswith("archived"):
            return DONE_WAIVED if st == "archived-waived" else DONE
        return BLOCKED if ref in ctx.open_suspect_targets else IN_PROGRESS
    if ref.startswith("doc:"):
        target = ref[len("doc:"):].strip("/")
        if target in ctx.articles:
            secs = [s for sec, s in ctx.sync.items() if sec.split("/", 1)[0] == target]
            if target in ctx.frozen_current and all(s in ("synced", "stale-software") for s in secs):
                return DONE
            return IN_PROGRESS if any(s != "unwritten" for s in secs) else NOT_STARTED
        if target in ctx.sync:
            s = ctx.sync[target]
            return DONE if s in ("synced", "stale-software") else NOT_STARTED if s == "unwritten" else IN_PROGRESS
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
        if kind == "info":
            # A preserved information record exists even when superseded or withdrawn.
            # is_constraint_ref excludes it from delivery completion; keep its real
            # effective status in the explanation rather than reopening finished work.
            return DONE
        if kind == "question":
            return DONE if gv.question_effective_status(rec, gov) in ("answered", "withdrawn") else NOT_STARTED
        if kind == "ruling":
            return DONE if gv.ruling_effective_status(rec, gov) in ("effective", "superseded") else NOT_STARTED
        return NOT_STARTED
    return "missing"


def relationship_problems(item: dict, ctx: Context, _seen: frozenset = frozenset()) -> list[str]:
    """Missing sources and structural cycles cannot support a completed result."""
    iid = str(item.get("id"))
    if iid in _seen:
        return [f"工作相依循環: {iid}"]
    seen = _seen | {iid}
    rows = {str(w["id"]): w for w in ctx.gov.work}
    problems = [f"連結不存在: {ref}" for ref in gv._as_list(item.get("refs"))
                if ref_state(ref, ctx) == "missing"]
    for ref in gv._as_list(item.get("refs")):
        problems.extend(ctx.source_problems.get(ref, []))
    linked = [str(w["id"]) for w in ctx.gov.work if str(w.get("parent")) == iid]
    linked += gv._as_list(item.get("depends-on"))
    for rid in dict.fromkeys(linked):
        if rid not in rows:
            problems.append(f"前置工作不存在: {rid}")
        else:
            problems.extend(relationship_problems(rows[rid], ctx, seen))
    return list(dict.fromkeys(problems))


def item_status(item: dict, ctx: Context, _seen: frozenset = frozenset()) -> str:
    iid = str(item.get("id"))
    if iid in _seen:                     # 環由 check 回報；推導時防無窮遞迴
        return BLOCKED
    if not _seen and relationship_problems(item, ctx):
        return BLOCKED
    seen = _seen | {iid}
    waived = bool(item.get("waivers"))
    fin = DONE_WAIVED if waived else DONE
    by_id = {str(w.get("id")): w for w in ctx.gov.work}
    children = [w for w in ctx.gov.work if str(w.get("parent")) == iid]
    refs = [r for r in gv._as_list(item.get("refs")) if not is_constraint_ref(r)]
    if item.get("closed") and not refs and not children:
        return fin
    states = [ref_state(r, ctx) for r in refs]
    child_states = [item_status(c, ctx, seen) for c in children]
    parts = states + child_states
    if parts and all(s in _FINISHED for s in parts):
        return DONE_WAIVED if waived or DONE_WAIVED in child_states or DONE_WAIVED in states else DONE
    for dep in gv._as_list(item.get("depends-on")):
        d = by_id.get(dep)
        if d is None or item_status(d, ctx, seen) not in _FINISHED:
            return BLOCKED
    if iid in ctx.open_suspect_targets or BLOCKED in states:
        return BLOCKED
    if any(s in (DONE, DONE_WAIVED, IN_PROGRESS, BLOCKED) for s in parts):
        return IN_PROGRESS
    return NOT_STARTED


def block_reason(item: dict, ctx: Context, lang: str = "zh") -> str:
    """卡住的原因（白話）：等哪些前置項目、或受上游變更影響需重看。"""
    by_id = {str(w.get("id")): w for w in ctx.gov.work}
    waiting = [by_id[d] for d in gv._as_list(item.get("depends-on"))
               if d in by_id and item_status(by_id[d], ctx) not in _FINISHED]
    parts = []
    missing = [str(d) for d in gv._as_list(item.get("depends-on")) if d not in by_id]
    if missing:
        parts.append("前置工作不存在: " + ", ".join(missing) if lang == "zh"
                     else "missing prerequisite: " + ", ".join(missing))
    if waiting:
        names = "、".join(f"{w.get('title')}（{w.get('id')}）" for w in waiting)
        parts.append(f"等 {names} 完成" if lang == "zh" else f"waiting for {names}")
    affected = [r for r in gv._as_list(item.get("refs")) if r in ctx.open_suspect_targets]
    if affected:
        names = "、".join(affected)
        parts.append(f"{names} 受上游決策變更影響，需重看（`artispec impact`）" if lang == "zh"
                     else f"{names} affected by an upstream decision change; review with `artispec impact`")
    if str(item.get("id")) in ctx.open_suspect_targets:
        parts.append("受上游變更影響，需重看（`artispec impact`）" if lang == "zh"
                     else "affected by an upstream change; review with `artispec impact`")
    return "；".join(parts) if lang == "zh" else "; ".join(parts)


def _basis_details(ref: str, ctx: Context) -> list[str]:
    """Explain the original background reference without replacing it or closing work."""
    rid = gv.strip_ns(ref)
    rec = ctx.gov.by_id().get(rid)
    if rec is None:
        return [f"連結不存在: {ref}"]
    kind = gv.kind_of_id(rid)
    if kind == "info":
        state = gv.info_effective_status(rec, ctx.gov)
        successors = [r for r in ctx.gov.infos if r.get("status") != "withdrawn"
                      and rid in gv._as_list(r.get("supersedes"))]
    else:
        state = gv.decision_effective_status(rec, ctx.gov)
        successors = [r for r in ctx.gov.decisions if r.get("status") == "active"
                      and rid in gv._as_list(r.get("supersedes"))]
    notes = [f"{ref}: 背景依據（{state}），不作為成果完成條件；"
             f"查看 `artispec {kind} show {rid}`"]
    if state == "superseded":
        replacements = ", ".join(f"gov:{r['id']}" for r in successors) or "無法確認"
        notes.append(f"{ref}: 已被取代，取代來源: {replacements}；"
                     "需重看原引用，不自動改用新版或清除影響標記（`artispec impact`）")
    elif state == "withdrawn":
        notes.append(f"{ref}: 背景依據已撤回（withdrawn），需重看原引用；"
                     f"查看 `artispec {kind} show {rid}`，不自動重新打開已完成工作")
    return notes


def item_details(item: dict, ctx: Context, _seen: frozenset = frozenset()) -> list[str]:
    """Common explanation for the JSON and text views, including unfinished children."""
    iid = str(item.get("id"))
    if iid in _seen:
        return [f"工作相依循環: {iid}"]
    seen = _seen | {iid}
    problems = relationship_problems(item, ctx)
    notes = list(problems)
    reason = block_reason(item, ctx)
    if reason:
        notes.append(reason)
    by_id = {str(w.get("id")): w for w in ctx.gov.work}
    for dep in gv._as_list(item.get("depends-on")):
        prerequisite = by_id.get(str(dep))
        if prerequisite and item_status(prerequisite, ctx) not in _FINISHED:
            notes.extend(f"前置工作 {dep}: {detail}"
                         for detail in item_details(prerequisite, ctx, seen))
    for ref in gv._as_list(item.get("refs")):
        if is_constraint_ref(ref):
            notes.extend(_basis_details(ref, ctx))
            continue
        if ref_state(ref, ctx) == "missing":
            notes.append(f"連結不存在: {ref}")
        elif ref.startswith("swc:"):
            details = ctx.sw_details.get(ref[4:], [])
            notes.extend(f"{ref}: {s}" for s in details)
            if not details and ref_state(ref, ctx) not in _FINISHED:
                notes.append(f"{ref}: 軟體變更尚未封存；"
                             f"查看 `artispec code change status {ref[4:]}`")
        elif ref.startswith("change:") and ref_state(ref, ctx) not in _FINISHED:
            notes.append(f"{ref}: 文件變更尚未封存；查看 `artispec change status {ref[7:]}`")
        elif ref.startswith("doc:"):
            target = ref[4:].strip("/")
            states = {sec: st for sec, st in ctx.sync.items()
                      if sec.split("/", 1)[0] == target} if target in ctx.articles else {
                          target: ctx.sync.get(target, "missing")}
            if target in ctx.articles and states and all(
                    st in ("synced", "stale-software") for st in states.values()):
                if target not in ctx.frozen_current:
                    notes.append(f"{ref}: 已寫好但尚未定版（目前內容）；`artispec freeze {target}`")
            for section, st in states.items():
                if st == "stale-software":
                    notes.append(f"doc:{section}: stale-software，軟體差異提醒，不阻擋文件完成")
                elif st != "synced":
                    notes.append(f"doc:{section}: {st}；查看 `artispec status`")
        elif ref.startswith("gov:") and ref_state(ref, ctx) not in _FINISHED:
            rid = gv.strip_ns(ref)
            rec = ctx.gov.by_id().get(rid, {})
            kind = gv.kind_of_id(rid)
            if kind == "question":
                state = gv.question_effective_status(rec, ctx.gov)
                notes.append(f"{ref}: 問題尚待裁定（{state}）；"
                             "查看 `artispec question list --all --json`")
            elif kind == "ruling":
                state = gv.ruling_effective_status(rec, ctx.gov)
                notes.append(f"{ref}: 裁定尚未生效（{state}）；"
                             f"查看 `artispec ruling show {rid}`")
            else:
                notes.append(f"{ref}: 尚無可判定成果完成的狀態；"
                             f"查看 `artispec roadmap show {iid}`")
    for child in ctx.gov.work:
        if str(child.get("parent")) == iid and item_status(child, ctx) not in _FINISHED:
            details = item_details(child, ctx, seen)
            prefix = f"子工作 {child.get('title')}（{child.get('id')}）"
            notes.extend(f"{prefix}: {s}" for s in details)
            if not details:
                notes.append(f"{prefix}: {status_label(item_status(child, ctx), child)}")
    delivery_refs = [r for r in gv._as_list(item.get("refs")) if not is_constraint_ref(r)]
    has_children = any(str(child.get("parent")) == iid for child in ctx.gov.work)
    if not delivery_refs and not has_children and not item.get("closed") and not problems:
        notes.append(f"{iid}: 尚未連結成果，背景依據不能證明工作完成；"
                     "請連結實際成果，或在小工作完成後用 "
                     f"`artispec roadmap done {iid} --note <完成理由>` 明確結案")
    return list(dict.fromkeys(notes))


def due_note(milestone: dict, status: str, lang: str = "zh") -> str:
    """里程碑到期提醒：未完成且已過期／7 天內到期。日期格式 YYYY/MM/DD 或 YYYY-MM-DD。"""
    import datetime
    raw = str(milestone.get("due") or "").replace("/", "-")
    try:
        due = datetime.date.fromisoformat(raw)
    except ValueError:
        return ""
    if status in _FINISHED:
        return ""
    days = (due - datetime.date.today()).days
    if days < 0:
        return "⚠ 已逾期" if lang == "zh" else "⚠ overdue"
    if days <= 7:
        return f"⚠ {days} 天內到期" if lang == "zh" else f"⚠ due in {days} day(s)"
    return ""


def view(layout: Layout, leaves: list, gov: gv.Governance | None = None) -> dict:
    """roadmap 檢視：{milestones:[{…, progress, items:[…]}], unassigned:[…]}。"""
    ctx = build_context(layout, leaves, gov, include_details=True)
    rows = {}
    for w in ctx.gov.work:
        st = item_status(w, ctx)
        rows[str(w["id"])] = {**{k: v for k, v in w.items() if not k.startswith("_")},
                              "status": st, "details": item_details(w, ctx)}
        sw_n = sum(ctx.sw_waived.get(r[len("swc:"):], 0) for r in gv._as_list(w.get("refs"))
                   if r.startswith("swc:"))
        if sw_n:
            rows[str(w["id"])]["software-waived"] = sw_n
        if st == BLOCKED:
            rows[str(w["id"])]["blocked-because"] = block_reason(w, ctx)
    out = {"milestones": [], "unassigned": []}
    for m in ctx.gov.milestones:
        items = [r for r in rows.values() if str(r.get("milestone")) == str(m["id"])
                 and not r.get("parent")]
        done = sum(1 for r in items if r["status"] in _FINISHED)
        mst = DONE if items and done == len(items) else (IN_PROGRESS if done else NOT_STARTED)
        out["milestones"].append({**{k: v for k, v in m.items() if not k.startswith("_")},
                                  "done": done, "total": len(items), "status": mst,
                                  "due-note": due_note(m, mst), "items": items})
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
        warn = f" {m['due-note']}" if m.get("due-note") else ""
        lines.append(f"- {m['title']}（{kind_name.get(m.get('type'), m.get('type'))}{due}，"
                     f"{m['id']}）：{m['done']}/{m['total']}{warn}")
        for r in sorted(m["items"], key=lambda r: r["status"] != BLOCKED):   # 卡住的先列
            if r["status"] not in _FINISHED:
                lines.append(f"  - {status_label(r['status'], r, lang)}：{r['title']}（{r['id']}）"
                             + ("——" + "；".join(r["details"]) if r.get("details") else ""))
    for r in v["unassigned"]:
        if r["status"] not in _FINISHED:
            lines.append(f"- {status_label(r['status'], r, lang)}：{r['title']}（{r['id']}）"
                         + ("——" + "；".join(r["details"]) if r.get("details") else ""))
    return lines


def validate_refs(layout: Layout, leaves: list, gov: gv.Governance) -> list[str]:
    """refs 死引用（check 層，需 corpus 與 changes 脈絡）。"""
    if not gov.work:
        return []
    ctx = build_context(layout, leaves, gov)
    errs = []
    for w in gov.work:
        for r in gv._as_list(w.get("refs")):
            if not r.startswith(("change:", "doc:", "gov:", "swc:")):
                errs.append(f"governance work item {w.get('id')}: ref \"{r}\" must start with "
                            f"change:, doc:, gov: or swc:")
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
