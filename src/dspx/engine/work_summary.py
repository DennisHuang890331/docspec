"""One read-only work view, assembled from existing judgments and explicit links."""
from __future__ import annotations

from copy import deepcopy

from dspx.engine import governance as gv, roadmap_v2 as rv
from dspx.engine.software import archive, changes, evidence, io, links, specs, tasks


def build(layout, leaves: list, work_id: str, *, schema_version: int = 2) -> dict:
    if schema_version not in (1, 2):
        raise ValueError(f"unsupported work summary schema version: {schema_version}")
    gov = gv.load_governance(layout)
    records = gov.by_id()
    work_id = gv.strip_ns(work_id)
    work = next((w for w in gov.work if str(w["id"]) == work_id), None)
    if work is None:
        raise gv.GovernanceError(f'no such work item "{work_id}"')
    ctx = rv.build_context(layout, leaves, gov)
    out = {"schema-version": schema_version, "work": {}, "dependencies": [], "governance": [],
           "software": [], "documents": [], "actions": [], "diagnostics": []}
    scopes: dict[tuple[int, str], dict] = {}
    if schema_version == 2:
        out["verification-scopes"] = []
    pending: list[tuple[str, str]] = []
    sources: dict[str, list[str]] = {}
    visited: set[str] = set()
    work_seen: set[str] = set()
    software_dependencies: dict[str, list[str]] = {}

    def diagnostic(code, ids, reason):
        row = {"code": code, "ids": list(ids), "reason": reason}
        if row not in out["diagnostics"]:
            out["diagnostics"].append(row)

    def action(code, ids, reason, command=""):
        row = {"code": code, "ids": list(ids), "reason": reason, "command": command}
        if row not in out["actions"]:
            out["actions"].append(row)

    def enqueue(ref, source):
        ref = str(ref)
        if ref.startswith("gov:"):
            ref = gv.strip_ns(ref)
        if source not in sources.setdefault(ref, []):
            sources[ref].append(source)
        pending.append((ref, source))

    def include(node):
        """Review flags belong to every included node, not only work-level refs."""
        for suspect in gov.suspects:
            if suspect.get("status") == "open" and gv.strip_ns(str(suspect.get("target"))) == gv.strip_ns(node):
                enqueue(suspect["id"], node)

    def work_row(w):
        return {**{k: v for k, v in w.items() if not k.startswith("_")},
                "refs": gv._as_list(w.get("refs")), "what": w.get("what", ""),
                "status": rv.item_status(w, ctx), "details": rv.item_details(w, ctx),
                "command": f"artispec roadmap show {w['id']}"}

    def visit_work(w, trail=()):
        wid = str(w["id"])
        if wid in trail:
            diagnostic("dependency-cycle", [*trail, wid], f"工作相依循環: {' -> '.join((*trail, wid))}")
            return
        if wid in work_seen:
            return
        work_seen.add(wid)
        include(wid)
        refs = gv._as_list(w.get("refs"))
        if not refs:
            diagnostic("coverage", [wid], f"{wid}: 未建立來源連結；摘要無法推論沒有其他限制。")
        for ref in refs:
            enqueue(ref, wid)
            if rv.ref_state(ref, ctx) == "missing":
                diagnostic("missing-source", [wid, ref], f"{wid}: 連結不存在: {ref}")
        for waiver in w.get("waivers") or []:
            if waiver.get("ruling"):
                enqueue(waiver["ruling"], wid)
        linked = [(str(c["id"]), "child") for c in gov.work if str(c.get("parent")) == wid]
        linked += [(d, "prerequisite") for d in gv._as_list(w.get("depends-on"))]
        for rid, relation in linked:
            rec = next((x for x in gov.work if str(x["id"]) == rid), None)
            row = work_row(rec) if rec else {"id": rid, "status": "missing", "details": [f"前置工作不存在: {rid}"]}
            # Keep each explicit edge; shared source contents are assembled only once.
            out["dependencies"].append({**row, "relation": relation, "from": wid})
            if rec:
                visit_work(rec, (*trail, wid))
            else:
                diagnostic("missing-prerequisite", [wid, rid], f"{wid}: 前置工作不存在: {rid}")
    visit_work(work)

    status_functions = {"decision": gv.decision_effective_status, "ruling": gv.ruling_effective_status,
                        "question": gv.question_effective_status, "info": gv.info_effective_status}

    def effective(rec):
        kind = gv.kind_of_id(str(rec["id"]))
        return status_functions[kind](rec, gov) if kind in status_functions else str(rec.get("status", "unknown"))

    def successors(rec):
        kind = gv.kind_of_id(str(rec["id"]))
        allowed = {"decision": "active", "ruling": "effective", "info": "current"}.get(kind)
        if allowed is None:
            return []
        return [r for r in records.values() if gv.kind_of_id(str(r["id"])) == kind
                and str(rec["id"]) in gv._as_list(r.get("supersedes"))
                and (r.get("status") == allowed if kind != "info" else r.get("status") != "withdrawn")]

    def current_ids(rec, trail=()):
        rid = str(rec["id"])
        if rid in trail:
            diagnostic("supersession-cycle", [*trail, rid], f"取代關係循環: {' -> '.join((*trail, rid))}")
            return []
        next_records = successors(rec)
        if not next_records:
            return [rid] if effective(rec) in ("active", "effective", "current") else []
        return list(dict.fromkeys(i for r in next_records for i in current_ids(r, (*trail, rid))))

    def requirement(ref, source, ch=None):
        ref = ref.removeprefix("req:")
        cap, rid, sid = specs.split_ref(ref)
        req = tasks._requirement_after(layout, ch, ref) if ch else specs.find_requirement(specs.load_spec(layout, cap), rid)
        node = f"req:{cap}/{rid}"
        if source not in sources.setdefault(node, []):
            sources[node].append(source)
        visited.add(node)
        include(node)
        if sid:
            include(f"{node}/{sid}")
        if not req:
            diagnostic("missing-source", [source, node], f"{source}: 需求來源不存在: {node}")
            return
        basis = io.as_list(req.get("based-on"))
        if not basis:
            diagnostic("coverage", [node], f"{node}: 未記錄 based-on 連結；不能推論沒有其他限制。")
        for basis_ref in basis:
            enqueue(basis_ref, node)

    while pending:
        ref, source = pending.pop(0)
        if ref in visited:
            continue
        visited.add(ref)
        include(ref)
        if ref in records:
            rec = records[ref]
            kind = gv.kind_of_id(ref)
            row = {"id": ref, "kind": kind, "status": effective(rec),
                   "original-references": sources[ref], "current-ids": current_ids(rec),
                   "sources": [gv.record_path(layout, kind, ref).relative_to(layout.project_root).as_posix()],
                   "command": {
                       "question": "artispec question list --all --json",
                       "work": f"artispec roadmap show {ref}",
                       "milestone": f"artispec roadmap --milestone {ref} --json",
                   }.get(kind, f"artispec {kind} show {ref}")}
            for key in ("title", "statement", "quote", "about", "based-on", "supersedes", "target", "trigger", "path"):
                if key in rec:
                    row[key] = rec[key]
            out["governance"].append(row)
            if kind == "suspect":
                if rec.get("trigger"):
                    enqueue(rec["trigger"], ref)
                action("review-impact", [ref, str(rec.get("target")), str(rec.get("trigger"))],
                       f"{ref}: {rec.get('target')} 受 {rec.get('trigger')} 影響，需審閱；不自動清除標記。", "artispec impact")
                row["command"] = "artispec impact"
            if kind == "question":
                for ruling in gov.rulings:
                    if ref in gv._as_list(ruling.get("answers")):
                        enqueue(ruling["id"], ref)
            for key in ("based-on", "answers", "supersedes"):
                for target in gv._as_list(rec.get(key)):
                    enqueue(target, ref)
            for successor in successors(rec):
                enqueue(successor["id"], ref)
            if row["status"] == "superseded":
                action("superseded-basis", [ref, *row["current-ids"]],
                       f"{ref} 已被取代，目前有效版本: {', '.join(row['current-ids']) or '無法確認'}；檢查影響標記並審閱原引用，不自動改用新版或清除標記。", "artispec impact")
            if kind == "decision" and gv.invalid_basis(rec, gov):
                diagnostic("invalid-basis", [ref], f"{ref}: 決策依據無效: {gv.invalid_basis(rec, gov)}")
        elif ref.startswith("swc:"):
            cid = ref[4:]
            state = ctx.sw_changes.get(cid)
            if state is None:
                diagnostic("missing-source", [source, ref], f"{source}: 來源不存在: {ref}")
                continue  # Missing refs were diagnosed above.
            ch = changes.load_archived(layout, cid) if state.startswith("archived") else changes.load_change(layout, cid)
            historical = state.startswith("archived")
            evs = evidence.load_all(layout)
            task_rows, selected_evidence = [], {}
            for task in ch["tasks"].get("tasks") or []:
                sources.setdefault(f"task:{cid}#{task['id']}", []).append(ref)
                include(f"task:{cid}#{task['id']}")
                mine = evidence.for_task(evs, cid, task["id"])
                if historical:
                    st, support, why = (task.get("status", "unknown"), task.get("evidence") or [],
                                        "封存時的任務與證據紀錄；不以目前程式重新驗證或重開。")
                else:
                    st, support, why = evidence.derive(layout, ch, task, mine)
                task_rows.append({"task": task["id"], "title": task.get("title"), "status": st,
                                  "recorded": task.get("status"), "evidence": support, "why": why})
                # Last attempt of every evidence type plus all currently supporting records.
                latest = {e["type"]: e for e in mine}
                for e in mine:
                    if e["id"] in support or latest[e["type"]]["id"] == e["id"]:
                        sources.setdefault(e["id"], []).append(ref)
                        selected_evidence[e["id"]] = {k: e.get(k) for k in ("id", "task", "type", "result", "reason", "at")}
                        if e.get("ruling"):
                            enqueue(e["ruling"], e["id"])
                        if historical:
                            # Follow the evidence's saved basis, not today's spec.
                            contract = (e.get("scope") or {}).get("contract") or {}
                            for basis in contract.get("decisions") or []:
                                enqueue(basis["ref"], e["id"])
                            for requirement_snapshot in contract.get("requirements") or []:
                                node = "req:" + str(requirement_snapshot["ref"])
                                include(node)
                                for basis in requirement_snapshot.get("based-on") or []:
                                    enqueue(basis["ref"], e["id"])
                            if not contract:
                                diagnostic("historical-coverage", [ref, e["id"]],
                                           f"{e['id']}: 舊封存證據沒有驗證範圍，無法列出當時的需求依據；不以現行規格補猜。")
                if not historical and st not in rv._FINISHED:
                    failed = [e["id"] for e in latest.values() if e.get("result") != "pass"]
                    action("failed-verification" if failed else "verification-needed",
                           [f"task:{cid}#{task['id']}", *failed],
                           f"{cid} 任務 {task['id']}: {why}；" + ("先處理失敗，再重新驗證。" if failed else "依缺少或過時的驗證方法補齊證據。"),
                           f"artispec code evidence list {cid}")
                if not historical:
                    for req in io.as_list(task.get("implements")):
                        requirement(req, f"task:{cid}#{task['id']}", ch)
            signoffs = ([{"test": t["id"], "status": "historical", "problems": [],
                          "signed": t.get("signed"), "note": "封存時簽收紀錄，不代表目前測試內容已簽收。"}
                         for t in ch["tests"].get("tests") or []]
                        if historical else evidence.signoff_view(layout, ch))
            for row in signoffs:
                if row["status"] == "unknown":
                    diagnostic("unreadable-signoff", [ref, f"test:{cid}/{row['test']}"], f"{cid}/{row['test']}: {'; '.join(row['problems'])}")
                if row["status"] not in ("current", "historical"):
                    action("review-signoff", [f"test:{cid}/{row['test']}"],
                           f"{row['test']}: {row['status']}: {'; '.join(row['problems'])}；測試角色檢查測試內容、對應情境及簽收指紋後再簽收。",
                           f"artispec code testplan list {cid}")
            if schema_version == 2:
                # Project the saved signature, never replace it with today's scope.
                signoffs = deepcopy(signoffs)
                tests_by_id = {t["id"]: t for t in ch["tests"].get("tests") or []}
                for row in signoffs:
                    signed = tests_by_id[row["test"]].get("signed")
                    if not isinstance(signed, dict):
                        continue
                    row["signed"] = deepcopy(signed)
                    scope = signed.get("scenario-fingerprint")
                    if not isinstance(scope, dict):
                        continue
                    row["signed"]["scenario-fingerprint"] = {
                        k: scope[k] for k in ("version", "fingerprint") if k in scope
                    }
                    # Malformed saved fields remain visible with the engine's
                    # sign-off problems, but cannot become an indexed scope id.
                    version, fingerprint = scope.get("version"), scope.get("fingerprint")
                    if type(version) is not int or version < 1 or not isinstance(fingerprint, str) or not fingerprint:
                        continue
                    source = {
                        "ref": f"test:{cid}/{row['test']}",
                        "path": (ch["folder"] / "tests.yaml").relative_to(layout.project_root).as_posix(),
                        "command": f"artispec change show {cid} --json",
                        "fingerprint": scope["fingerprint"],
                    }
                    row["scope-source"] = source
                    key = (scope["version"], scope["fingerprint"])
                    if key not in scopes:
                        scopes[key] = {"version": scope["version"], "fingerprint": scope["fingerprint"], "sources": []}
                        out["verification-scopes"].append(scopes[key])
                    if source not in scopes[key]["sources"]:
                        scopes[key]["sources"].append(source)
            for test in ch["tests"].get("tests") or []:
                sources.setdefault(f"test:{cid}/{test['id']}", []).append(ref)
                include(f"test:{cid}/{test['id']}")
                if not historical:
                    for req in io.as_list(test.get("covers")):
                        requirement(req, f"test:{cid}/{test['id']}", ch)
            for basis in io.as_list(ch["design"].get("decisions")):
                enqueue(basis, ref)
            for cap, delta in ch["deltas"].items():
                for entry in delta.get("deltas") or []:
                    for basis in io.as_list(entry.get("based-on")):
                        enqueue(basis, ref)
                    if not historical and entry.get("op") not in ("remove-requirement", "remove-scenario"):
                        requirement(f"{cap}/{entry.get('ref') or entry.get('id')}", ref, ch)
            software_dependencies[ref] = [f"swc:{dep}" for dep in io.as_list(ch["proposal"].get("depends-on"))]
            for dep in io.as_list(ch["proposal"].get("depends-on")):
                enqueue(f"swc:{dep}", ref)
                if dep not in ctx.sw_changes:
                    diagnostic("missing-source", [ref, f"swc:{dep}"], f"{ref}: 前置軟體變更不存在: swc:{dep}")
            errors, warnings = changes.validate_change(layout, ch, strict=True) if not historical else ([], [])
            details = list(dict.fromkeys([*errors, *archive.blockers(layout, ch, evs)])) if not historical else []
            out["software"].append({"id": cid, "status": state, "historical": historical, "tasks": task_rows, "signoffs": signoffs,
                                    "evidence": list(selected_evidence.values()), "details": details,
                                    "gaps": tasks.gaps(layout, ch) if state == "active" else {}, "warnings": warnings,
                                    "source": ch["folder"].relative_to(layout.project_root).as_posix(),
                                    "command": f"artispec code evidence list {cid}"})
        elif ref.startswith("doc:"):
            target = ref[4:].strip("/")
            matched = [lf for lf in leaves if lf.article == target or lf.section == target]
            if not matched:
                diagnostic("missing-source", [source, ref], f"{source}: 文件來源不存在: {ref}")
                continue
            sync = {lf.section: ctx.sync[lf.section] for lf in matched}
            frozen = all(lf.article in ctx.frozen_current for lf in matched)
            details = rv.item_details({"id": "summary-document", "refs": [ref]}, ctx)
            out["documents"].append({"id": ref, "written": all(s != "unwritten" for s in sync.values()),
                                     "sync": sync, "frozen": frozen, "details": details,
                                     "requirement-sources": list({source_ref: links.resolve_requirement_source(layout, source_ref)
                                         for leaf in matched for source_ref in gv._as_list((leaf.concept or {}).get("realizes"))
                                         if links.is_requirement_source(source_ref)}.values()),
                                     "command": f"artispec show {target}" + (" --concepts" if target in ctx.articles else "")})
            if not frozen:
                action("unfrozen-document", [ref], f"{ref}: 目前內容尚未定版；只有負責人明確要求後才能定版。",
                       f"artispec freeze {matched[0].article}")
            for lf in matched:
                include(f"doc:{lf.section}")
                refs = gv._as_list((lf.concept or {}).get("realizes"))
                if not refs:
                    diagnostic("coverage", [f"doc:{lf.section}"], f"doc:{lf.section}: 未記錄 realizes 連結；不能推論沒有其他限制。")
                for target_ref in refs:
                    enqueue(target_ref, f"doc:{lf.section}")
        elif ref.startswith("draft-req:"):
            requirement_source = links.resolve_requirement_source(layout, ref)
            for reason in requirement_source["diagnostics"]:
                diagnostic("software-requirement-source", [source, ref], reason)
            if not requirement_source["based-on"] and requirement_source["state"] in ("draft", "formal"):
                diagnostic("coverage", [ref], f"{ref}: 未記錄 based-on 連結；不能推論沒有其他限制。")
            for basis in requirement_source["based-on"]:
                enqueue(basis, ref)
            if requirement_source["state"] == "formal":
                include(requirement_source["source-ref"])
        elif ref.startswith("req:"):
            requirement(ref, source)
        elif ref.startswith("change:"):
            from dspx.engine import change
            if ref[7:] in ctx.change_states:
                ch = change.load_change(layout, ref[7:])
                for target in ch.targets:
                    if target.kind == "section":
                        path = rv._section_path(target.ref, leaves)
                        enqueue(f"doc:{path or target.ref}", ref)
            else:
                diagnostic("missing-source", [source, ref], f"{source}: 文件變更不存在: {ref}")
        else:
            from dspx.engine.model import decision_index
            rec = decision_index(leaves).get(ref)
            if rec:
                out["governance"].append({"id": ref, "kind": rec["kind"], "status": rec["status"],
                                          "statement": rec["statement"], "original-references": sources[ref],
                                          "current-ids": [rec["superseded_by"]] if rec["superseded_by"] else [ref],
                                          "sources": [f"doc:{rec['section']}"], "command": f"artispec show {ref}"})
                if rec["superseded_by"]:
                    enqueue(rec["superseded_by"], ref)
            else:
                diagnostic("missing-source", [source, ref], f"{source}: 來源不存在: {ref}")

    def check_software_dependencies(ref, trail=(), completed=None):
        if ref in trail:
            diagnostic("dependency-cycle", [*trail, ref], f"軟體相依循環: {' -> '.join((*trail, ref))}")
            return
        if completed is None:
            completed = set()
        if ref in completed:
            return
        for dep in software_dependencies.get(ref, []):
            check_software_dependencies(dep, (*trail, ref), completed)
        completed.add(ref)

    completed = set()
    for ref in software_dependencies:
        check_software_dependencies(ref, completed=completed)

    # Feed discovered source-integrity problems into the shared roadmap judgment.
    # This is validation input, never a second success/completion algorithm.
    for problem in out["diagnostics"]:
        if problem["code"] not in ("missing-source", "supersession-cycle", "dependency-cycle", "missing-prerequisite", "unreadable-signoff"):
            continue
        related = {gv.strip_ns(str(i)) for i in problem["ids"]}
        frontier = list(related)
        while frontier:
            for parent in sources.get(frontier.pop(), []):
                parent = gv.strip_ns(parent)
                if parent not in related:
                    related.add(parent)
                    frontier.append(parent)
        for wid in work_seen:
            for ref in gv._as_list(records[wid].get("refs")):
                if gv.strip_ns(ref) in related or wid in related:
                    ctx.source_problems.setdefault(ref, []).append(problem["reason"])
    out["work"] = work_row(work)
    for row in out["dependencies"]:
        if row["id"] in records:
            row.update(work_row(records[row["id"]]))
    return out


def render(result: dict) -> str:
    """Format the same complete result consumed by JSON clients; never re-query."""
    w = result["work"]
    lines = [f"{w['id']} — {w['title']} [{w['status']}]", f"目標: {w['what'] or w['title']}"]
    lines.extend(f"  {d}" for d in w["details"])
    # Surface the restrictions first; subsequent sections keep the source context.
    problems = list(dict.fromkeys(d for sw in result["software"] for d in sw["details"]))
    lines.extend(f"待處理: {d}" for d in problems)
    for row in result["diagnostics"]:
        lines.append(f"診斷 [{', '.join(row['ids'])}]: {row['reason']}")
    healthy_deps = [r for r in result["dependencies"] if r["status"] in rv._FINISHED]
    if healthy_deps:
        lines.append(f"已完成子工作／前置工作 {len(healthy_deps)} 項: " + ", ".join(f"{r['id']} ({r['relation']}, {r['status']})" for r in healthy_deps))
    for row in result["dependencies"]:
        if row["status"] in rv._FINISHED:
            continue
        lines.append(f"{row['relation']} {row['id']}: {row['status']}")
        lines.extend(f"  {d}" for d in row["details"])
    for row in result["governance"]:
        lines.append(f"{row['kind']} {row['id']}: {row['status']}; 目前版本: {', '.join(row['current-ids']) or '—'}")
        for key in ("statement", "quote"):
            if row.get(key):
                lines.append(f"  {row[key]}")
        lines.append(f"  引用: {', '.join(row['original-references'])}; 來源: {', '.join(row['sources'])}")
        lines.append(f"  {row['command']}")
    for row in result["software"]:
        lines.append(f"軟體 {row['id']}: {row['status']}；任務 {len(row['tasks'])}，測試 {len(row['signoffs'])}")
        lines.extend(f"  提醒: {d}" for d in row["warnings"])
        completed = [t for t in row["tasks"] if t["status"] in rv._FINISHED]
        if completed:
            lines.append(f"  已完成任務 {len(completed)}（含豁免 {sum(t['status'] == 'done-waived' for t in completed)}）")
        for task in row["tasks"]:
            if task["status"] not in rv._FINISHED:
                lines.append(f"  任務 {task['task']}: {task['status']} — {task['why']}; 證據: {', '.join(task['evidence']) or '—'}")
        normal_signoffs = sum(t["status"] in ("current", "historical") for t in row["signoffs"])
        lines.append(f"  {'歷史簽收' if row['historical'] else '有效簽收'} {normal_signoffs}/{len(row['signoffs'])}")
        if row["historical"]:
            lines.append("  封存時的任務、簽收與證據紀錄；不代表目前程式已重新驗證，不重開舊工作。")
        for test in row["signoffs"]:
            if test["status"] in ("current", "historical"):
                continue
            lines.append(f"  {test['test']} sign-off: {test['status']}")
            lines.extend(f"    {p}" for p in test["problems"])
        passed = [e for e in row["evidence"] if e["result"] == "pass"]
        if passed:
            lines.append(f"  通過紀錄 {len(passed)}: " + ", ".join(e["id"] for e in passed))
            supporting = sorted({eid for task in row["tasks"] for eid in task["evidence"]})
            lines.append("  " + ("封存支援證據: " if row["historical"] else "目前有效支援證據: ") + (", ".join(supporting) or "無"))
        for e in row["evidence"]:
            if e["result"] == "pass":
                continue
            lines.append(f"  {e['id']} 任務 {e['task']} {e['type']}: {e['result']} {e['reason'] or ''}")
        lines.append(f"  {row['command']}；來源: {row['source']}")
    for row in result["documents"]:
        lines.append(f"文件 {row['id']}: written={row['written']}; frozen={row['frozen']}")
        lines.append(f"  已同步章節 {sum(st == 'synced' for st in row['sync'].values())}/{len(row['sync'])}")
        lines.extend(f"  {s}: {st}" for s, st in row["sync"].items() if st != "synced")
        lines.extend(f"  {d}" for d in row["details"])
        for source in row.get("requirement-sources", []):
            lines.append(f"  需求來源 {source['original-ref']}: {source['state']}; 目前入口: {source['source-ref'] or '—'}")
            if source["statement"]:
                lines.append(f"    {source['statement']}")
            if source["baseline"]:
                lines.append(f"    封存基線: {source['baseline']}")
            lines.extend(f"    {reason}" for reason in source["diagnostics"])
            if source["change"]:
                lines.append(f"    artispec change show {source['change']}")
        lines.append(f"  {row['command']}")
    for row in result["actions"]:
        lines.append(f"可採取的處理 [{', '.join(row['ids'])}]: {row['reason']}")
        if row["command"]:
            lines.append(f"  {row['command']}")
    return "\n".join(lines)
