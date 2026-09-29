"""docspec code — 軟體領域（取代 OpenSpec）：能力規格、change 資料夾、任務、測試規劃。

    docspec code spec list | show <能力> [--req R1] [--json|--md]
    docspec code change new|set|design|delta|show|status|list …
    docspec code task add|list <change> …
    docspec code testplan add|list|object|respond <change> …
    docspec code evidence run|add|accept|waive|list <change> <task> …

任務的完成欄位沒有「打勾」指令：`evidence` 產生證據後，引擎依證據推導並寫回 tasks.yaml。

所有檔案都是引擎擁有、封條的 YAML，只能透過這些指令寫入；查詢支援 `--json` 讓 agent 只取需要的部分。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from dspx.commands.governance._gov_common import emit_json, fail, open_layout
from dspx.engine import governance as gv
from dspx.engine.software import changes as chg
from dspx.engine.software import evidence as ev
from dspx.engine.software import io
from dspx.engine.software import specs as sp
from dspx.engine.software import tasks as tk

NAME = "code"
HELP = ("software domain (replaces OpenSpec): capability specs, change folders, spec deltas, "
        "tasks and test plans")


def _csv(raw: str | None) -> list[str]:
    return [x.strip() for x in (raw or "").split(",") if x.strip()]


def _gov_csv(raw: str | None) -> list[str]:
    return [x if x.startswith("gov:") else f"gov:{x}" for x in _csv(raw)]


# ── parser ───────────────────────────────────────────────────────────────

def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="docspec code", description=HELP)
    top = p.add_subparsers(dest="area")

    spec = top.add_parser("spec", help="current capability specs (read-only)")
    ss = spec.add_subparsers(dest="op")
    x = ss.add_parser("list", help="list capabilities")
    x.add_argument("--json", dest="as_json", action="store_true")
    x = ss.add_parser("show", help="show one capability (optionally one requirement)")
    x.add_argument("capability")
    x.add_argument("--req", default=None, help="only this requirement, e.g. R1")
    x.add_argument("--json", dest="as_json", action="store_true")
    x.add_argument("--md", action="store_true", help="Markdown for people / PR review")

    change = top.add_parser("change", help="change folders: proposal, design, spec deltas")
    cs = change.add_subparsers(dest="op")
    x = cs.add_parser("new", help="create a change folder")
    x.add_argument("id", help="kebab-case change id")
    x.add_argument("--why", required=True)
    x.add_argument("--what", action="append", default=[], help="one bullet (repeatable)")
    x.add_argument("--new", dest="new_caps", default="", help="new capabilities (comma-separated)")
    x.add_argument("--modified", default="", help="existing capabilities this changes")
    x.add_argument("--code-areas", default="", help="repo:path areas touched (comma-separated)")
    x.add_argument("--depends-on", default="", help="change ids that must archive first")
    x.add_argument("--by", default=None, help="tool prefix: claude|gpt|gemini (auto-detected)")
    x = cs.add_parser("set", help="edit the proposal")
    x.add_argument("id")
    x.add_argument("--why", default=None)
    x.add_argument("--what", action="append", default=[], help="append a bullet")
    x.add_argument("--new", dest="new_caps", default="", help="add new capabilities")
    x.add_argument("--modified", default="", help="add modified capabilities")
    x.add_argument("--code-areas", default="", help="add code areas")
    x.add_argument("--depends-on", default="", help="add prerequisite changes")
    x = cs.add_parser("design", help="edit design.yaml (list fields append)")
    x.add_argument("id")
    x.add_argument("--context", default=None)
    x.add_argument("--migration", default=None)
    for flag in ("goal", "non-goal", "risk", "open-question"):
        x.add_argument(f"--{flag}", action="append", default=[])
    x.add_argument("--decision", default="", help="governance decision ids (gov:D-…)")
    x = cs.add_parser("delta", help="add one spec delta (the engine fills base fingerprints and ids)")
    x.add_argument("id")
    x.add_argument("--capability", default=None)
    x.add_argument("--op", dest="delta_op", default=None, help="add-requirement | modify-requirement | "
                   "rename-requirement | remove-requirement | add-scenario | modify-scenario | "
                   "remove-scenario")
    x.add_argument("--ref", default=None, help="R1 or R1/S2 (relative to the capability)")
    x.add_argument("--title", default=None)
    x.add_argument("--statement", default=None)
    x.add_argument("--verification", default=None, help="test,inspection,…")
    x.add_argument("--based-on", default=None, help="governance decision ids")
    x.add_argument("--when", default=None)
    x.add_argument("--then", default=None)
    x.add_argument("--reason", default=None)
    x.add_argument("--scenario", action="append", default=[],
                   help="for add-requirement: 'title | when | then' (repeatable)")
    x.add_argument("--purpose", default=None, help="purpose of a new capability")
    x.add_argument("--from", dest="from_file", default=None,
                   help="YAML file: {capability, purpose?, deltas: [...]} or a list of those")
    for name, hlp in (("show", "show a change"), ("status", "validation, tasks, conflicts")):
        x = cs.add_parser(name, help=hlp)
        x.add_argument("id")
        x.add_argument("--json", dest="as_json", action="store_true")
        if name == "show":
            x.add_argument("--md", action="store_true")
    x = cs.add_parser("list", help="list changes")
    x.add_argument("--archived", action="store_true")
    x.add_argument("--json", dest="as_json", action="store_true")

    task = top.add_parser("task", help="tasks (completion is written by the engine, not by hand)")
    ts = task.add_subparsers(dest="op")
    x = ts.add_parser("add", help="add a task")
    x.add_argument("change")
    x.add_argument("--title", required=True)
    x.add_argument("--implements", default="", help="cap/R1,… requirements this implements")
    x.add_argument("--files", default="", help="repo:path files this task changes")
    x.add_argument("--verify", default="", help="test,inspection,demonstration,analysis")
    x.add_argument("--tests", default="", help="planned test ids that verify it (T1,T2)")
    x.add_argument("--allow-skips", action="store_true",
                   help="skipped tests are expected (e.g. no GPU) and do not block completion")
    x.add_argument("--depends-on", default="", help="task ids in this change")
    x = ts.add_parser("list", help="list tasks with engine status")
    x.add_argument("change")
    x.add_argument("--json", dest="as_json", action="store_true")

    tp = top.add_parser("testplan", help="test plan (written by the test role, not the implementer)")
    tps = tp.add_subparsers(dest="op")
    x = tps.add_parser("add", help="plan a test for scenarios")
    x.add_argument("change")
    x.add_argument("--location", required=True, help="repo:path::test_name")
    x.add_argument("--covers", required=True, help="cap/R1/S1,… scenarios it verifies")
    x.add_argument("--level", default="unit", help=", ".join(tk.TEST_LEVELS))
    x.add_argument("--note", default=None)
    x.add_argument("--by", default=None)
    x = tps.add_parser("list", help="list planned tests and objections")
    x.add_argument("change")
    x.add_argument("--json", dest="as_json", action="store_true")
    x = tps.add_parser("object", help="implementer: the test looks wrong")
    x.add_argument("change")
    x.add_argument("test")
    x.add_argument("--reason", required=True)
    x.add_argument("--by", default=None)
    x = tps.add_parser("respond", help="test role: answer an objection")
    x.add_argument("change")
    x.add_argument("objection")
    x.add_argument("--resolution", required=True, help="test-fixed | rejected")
    x.add_argument("--reason", required=True)
    x.add_argument("--by", default=None)
    evd = top.add_parser("evidence", help="evidence; the engine derives task completion from it")
    es = evd.add_subparsers(dest="op")
    x = es.add_parser("run", help="engine runs the task's planned tests (or the command after --)")
    x.add_argument("change")
    x.add_argument("task")
    x.add_argument("--timeout", type=int, default=1800)
    x.add_argument("--by", default=None)
    x = es.add_parser("add", help="record an inspection / demonstration / analysis")
    x.add_argument("change")
    x.add_argument("task")
    x.add_argument("--type", required=True, help="inspection | demonstration | analysis")
    x.add_argument("--subject", required=True, help="what was looked at (screenshot path, size, …)")
    x.add_argument("--conclusion", required=True)
    x.add_argument("--result", default="pass", help="pass | fail")
    x.add_argument("--by", default=None)
    x = es.add_parser("accept", help="the owner's acceptance, read back in the conversation")
    x.add_argument("change")
    x.add_argument("task")
    x.add_argument("--read-back", required=True, help="what you showed and your plain-language summary")
    x.add_argument("--confirmed", required=True, help="the owner's confirming reply (verbatim)")
    x.add_argument("--by", default=None)
    x = es.add_parser("waive", help="waive a task on the basis of an effective ruling")
    x.add_argument("change")
    x.add_argument("task")
    x.add_argument("--ruling", required=True)
    x.add_argument("--reopen-when", required=True)
    x.add_argument("--by", default=None)
    x = es.add_parser("list", help="evidence for a change")
    x.add_argument("change")
    x.add_argument("--task", default=None)
    x.add_argument("--json", dest="as_json", action="store_true")
    return p


# ── spec ─────────────────────────────────────────────────────────────────

def _spec(layout, args) -> int:
    if args.op == "list":
        rows = []
        for cap, spec in sp.load_all(layout).items():
            rows.append({"capability": cap, "purpose": spec.get("purpose"),
                         "requirements": len(spec.get("requirements") or [])})
        if args.as_json:
            emit_json(rows)
            return 0
        if not rows:
            print("(no capability specs yet)")
        for r in rows:
            print(f"{r['capability']} — {r['requirements']} requirement(s): {r['purpose']}")
        return 0
    spec = sp.load_spec(layout, args.capability)
    if spec is None:
        return fail(f"no capability \"{args.capability}\" (see `docspec code spec list`)")
    if args.req and sp.find_requirement(spec, args.req) is None:
        return fail(f"{args.capability} has no requirement \"{args.req}\"")
    if args.as_json:
        out = dict(spec)
        if args.req:
            out["requirements"] = [sp.find_requirement(spec, args.req)]
        emit_json(out)
        return 0
    print(sp.render_md(spec, args.req), end="")
    return 0


# ── change ───────────────────────────────────────────────────────────────

def _merge(existing: list, extra: list) -> list:
    return list(existing) + [x for x in extra if x not in existing]


def _deltas_from_args(args) -> list[tuple[str, dict, str | None]]:
    if args.from_file:
        data = yaml.safe_load(Path(args.from_file).read_text(encoding="utf-8"))
        groups = data if isinstance(data, list) else [data]
        out = []
        for g in groups:
            if not isinstance(g, dict) or not g.get("capability"):
                raise io.SoftwareError("--from: each entry needs `capability` and `deltas`")
            for d in g.get("deltas") or []:
                out.append((g["capability"], dict(d), g.get("purpose")))
        return out
    if not args.capability or not args.delta_op:
        raise io.SoftwareError("delta needs --capability and --op (or --from FILE)")
    raw = {"op": args.delta_op, "ref": args.ref, "title": args.title, "statement": args.statement,
           "when": args.when, "then": args.then, "reason": args.reason}
    if args.verification:
        raw["verification"] = _csv(args.verification)
    if args.based_on:
        raw["based-on"] = _gov_csv(args.based_on)
    if args.scenario:
        scns = []
        for s in args.scenario:
            parts = [x.strip() for x in s.split("|")]
            if len(parts) != 3:
                raise io.SoftwareError(f"--scenario must be 'title | when | then', got: {s}")
            scns.append(dict(zip(("title", "when", "then"), parts)))
        raw["scenarios"] = scns
    raw = {k: v for k, v in raw.items() if v not in (None, "", [])}
    return [(args.capability, raw, args.purpose)]


def _print_findings(errs: list[str], warns: list[str]) -> None:
    for e in errs:
        print(f"  ✗ {e}")
    for w in warns:
        print(f"  ! {w}")


def _change(layout, args) -> int:
    if args.op == "list":
        rows = chg.list_archived(layout) if args.archived else chg.list_active(layout)
        if args.as_json:
            emit_json(rows)
        else:
            print("\n".join(rows) if rows else "(none)")
        return 0
    if args.op == "new":
        tool = gv.detect_tool(args.by)
        chg.new_change(layout, args.id, why=args.why, what=args.what, new_caps=_csv(args.new_caps),
                       modified_caps=_csv(args.modified), code_areas=_csv(args.code_areas),
                       depends_on=_csv(args.depends_on), tool=tool)
        print(f"code change new: {args.id} ({io.change_dir(layout, args.id).relative_to(layout.project_root)})")
        return 0

    ch = chg.load_change(layout, args.id)
    if args.op == "set":
        p = ch["proposal"]
        if args.why:
            p["why"] = args.why.strip()
        if args.what:
            p["what"] = _merge(p.get("what") or [], args.what)
        caps = p.setdefault("capabilities", {"new": [], "modified": []})
        existing = set(sp.list_capabilities(layout))
        for c in _csv(args.new_caps):
            if c in existing:
                return fail(f"capability \"{c}\" already exists; use --modified")
        for c in _csv(args.modified):
            if c not in existing:
                return fail(f"capability \"{c}\" does not exist; use --new")
        caps["new"] = _merge(caps.get("new") or [], _csv(args.new_caps))
        caps["modified"] = _merge(caps.get("modified") or [], _csv(args.modified))
        for key, raw in (("code-areas", args.code_areas), ("depends-on", args.depends_on)):
            if _csv(raw):
                p[key] = _merge(p.get(key) or [], _csv(raw))
        chg.write_part(layout, args.id, "proposal", p)
        print(f"code change set: {args.id} proposal updated")
        return 0
    if args.op == "design":
        d = ch["design"]
        for key, val in (("context", args.context), ("migration", args.migration)):
            if val:
                d[key] = val.strip()
        for key, vals in (("goals", args.goal), ("non-goals", args.non_goal), ("risks", args.risk),
                          ("open-questions", args.open_question)):
            if vals:
                d[key] = _merge(d.get(key) or [], vals)
        if args.decision:
            d["decisions"] = _merge(d.get("decisions") or [], _gov_csv(args.decision))
        chg.write_part(layout, args.id, "design", d)
        errs, _w = chg.validate_change(layout, chg.load_change(layout, args.id))
        bad = [e for e in errs if "design." in e]
        _print_findings(bad, [])
        print(f"code change design: {args.id} design updated")
        return 0
    if args.op == "delta":
        added = []
        for cap, raw, purpose in _deltas_from_args(args):
            d = chg.add_delta(layout, args.id, cap, raw, purpose)
            added.append(f"{cap} {d['op']} {d.get('ref') or d.get('id')}")
        for a in added:
            print(f"code change delta: {args.id}: {a}")
        return 0
    if args.op == "show":
        if args.as_json:
            emit_json({k: v for k, v in ch.items() if k != "folder"})
        else:
            print(chg.render_md(layout, ch), end="")
        return 0
    # status（先依證據刷新任務狀態）
    _report_refresh(ev.refresh(layout, args.id), args.id, quiet=args.as_json)
    ch = chg.load_change(layout, args.id)
    errs, warns = chg.validate_change(layout, ch)
    tasks = ch["tasks"].get("tasks") or []
    counts: dict[str, int] = {}
    for t in tasks:
        counts[t.get("status", "not-started")] = counts.get(t.get("status", "not-started"), 0) + 1
    if args.as_json:
        emit_json({"change": args.id, "errors": errs, "warnings": warns, "tasks": counts,
                   "touched": tk.touched_summary(ch)})
        return 1 if errs else 0
    print(f"change {args.id}: {len(tasks)} task(s)"
          + (" — " + ", ".join(f"{tk.STATUS_LABEL.get(k, k)} {v}" for k, v in counts.items())
             if counts else ""))
    print(f"touches: {', '.join(tk.touched_summary(ch)) or '—'}")
    for row in ev.explain(layout, args.id):
        if row["status"] not in ("done", "done-waived"):
            print(f"  task {row['task']} {tk.STATUS_LABEL.get(row['status'], row['status'])}: {row['why']}")
    if not errs and not warns:
        print("  ✓ references and deltas are consistent")
    _print_findings(errs, warns)
    return 1 if errs else 0


# ── task / testplan ──────────────────────────────────────────────────────

def _task(layout, args) -> int:
    ch = chg.load_change(layout, args.change)
    if args.op == "add":
        rec = tk.add_task(ch["tasks"], title=args.title, implements=_csv(args.implements),
                          files=_csv(args.files), methods=_csv(args.verify), tests=_csv(args.tests),
                          allow_skips=args.allow_skips, depends_on=_csv(args.depends_on))
        chg.write_part(layout, args.change, "tasks", ch["tasks"])
        print(f"code task add: {args.change} task {rec['id']} — {rec['title']}")
        return 0
    _report_refresh(ev.refresh(layout, args.change), args.change, quiet=args.as_json)
    ch = chg.load_change(layout, args.change)
    tasks = ch["tasks"].get("tasks") or []
    if args.as_json:
        emit_json(tasks)
        return 0
    print(tk.render_md(layout, ch).split("## Tasks", 1)[1].strip())
    return 0


def _testplan(layout, args) -> int:
    ch = chg.load_change(layout, args.change)
    tests = ch["tests"]
    if args.op == "list":
        if args.as_json:
            emit_json(tests)
        else:
            print(tk.render_md(layout, ch).split("## Tasks", 1)[0].strip())
        return 0
    tool = gv.detect_tool(args.by)
    if args.op == "add":
        rec = tk.add_test(tests, location=args.location, covers=_csv(args.covers), level=args.level,
                          tool=tool, note=args.note, today=gv.today())
        msg = f"code testplan add: {args.change} {rec['id']} {rec['location']}"
    elif args.op == "object":
        rec = tk.add_objection(tests, test_id=args.test, reason=args.reason, tool=tool, today=gv.today())
        msg = f"code testplan object: {args.change} {rec['id']} on {rec['test']} (open)"
    else:
        rec = tk.respond_objection(tests, oid=args.objection, resolution=args.resolution,
                                   response=args.reason, tool=tool, today=gv.today())
        msg = f"code testplan respond: {args.change} {rec['id']} -> {rec['resolution']}"
    chg.write_part(layout, args.change, "tests", tests)
    print(msg)
    return 0


def _report_refresh(changed, cid: str, quiet: bool = False) -> None:
    if quiet:
        return
    for task_id, old, new in changed:
        print(f"task {cid}#{task_id}: {tk.STATUS_LABEL.get(old, old)} → {tk.STATUS_LABEL.get(new, new)}")


def _evidence(layout, args, command: list[str] | None) -> int:
    if args.op == "list":
        rows = [e for e in ev.load_all(layout) if e.get("change") == args.change
                and (args.task is None or str(e.get("task")) == args.task)]
        if args.as_json:
            emit_json(rows)
            return 0
        for e in rows:
            extra = ""
            if e.get("type") == "test-run":
                c = e.get("counts") or {}
                extra = f" passed {c.get('passed')} failed {c.get('failed')} skipped {c.get('skipped')}"
            print(f"{e['id']} task {e['task']} {e['type']} {e.get('result')}{extra} ({e.get('at')})"
                  + (f" — {e['reason']}" if e.get("reason") else ""))
        if not rows:
            print("(no evidence)")
        return 0
    tool = gv.detect_tool(args.by)
    if args.op == "run":
        rec = ev.run_tests(layout, args.change, args.task, command, tool=tool, timeout=args.timeout)
        c = rec["counts"]
        print(f"evidence {rec['id']}: {rec['command']}")
        print(f"  passed {c['passed']}, failed {c['failed']}, skipped {c['skipped']}, "
              f"exit {rec['exit-code']} → {rec['result']}")
        for pt in rec.get("per-test") or []:
            print(f"  {pt['test']} {pt['location']}: {pt['outcome']}")
        if rec.get("reason"):
            print(f"  reason: {rec['reason']}")
        for chk in (rec.get("environment") or {}).get("checks") or []:
            if not chk["ok"]:
                print(f"  ! environment check failed: {chk['name']}")
    elif args.op == "add":
        rec = ev.record(layout, args.change, args.task, args.type, tool=tool, subject=args.subject,
                        conclusion=args.conclusion, result=args.result)
        print(f"evidence {rec['id']}: {rec['type']} {rec['result']}")
    elif args.op == "accept":
        rec = ev.accept(layout, args.change, args.task, tool=tool, read_back=args.read_back,
                        confirmed=args.confirmed)
        print(f"evidence {rec['id']}: acceptance recorded")
    else:
        rec = ev.waive(layout, args.change, args.task, tool=tool, ruling=args.ruling,
                       reopen_when=args.reopen_when)
        print(f"evidence {rec['id']}: waived by {rec['ruling']}")
    changed = ev.refresh(layout, args.change)
    _report_refresh(changed, args.change)
    if not changed:
        row = next(r for r in ev.explain(layout, args.change) if str(r["task"]) == str(args.task))
        print(f"task {args.change}#{args.task}: {tk.STATUS_LABEL.get(row['status'], row['status'])}"
              f" — {row['why']}")
    return 0 if rec.get("result") == "pass" else 1


def run(argv: list[str]) -> int:
    command = None
    if "--" in argv:                      # `code evidence run <change> <task> -- <指令…>`
        i = argv.index("--")
        argv, command = argv[:i], argv[i + 1:] or None
    p = _parser()
    args = p.parse_args(argv)
    if not args.area or not getattr(args, "op", None):
        p.print_help()
        return 0
    layout = open_layout()
    if layout is None:
        return 1
    try:
        if args.area == "evidence":
            return _evidence(layout, args, command)
        return {"spec": _spec, "change": _change, "task": _task, "testplan": _testplan}[args.area](
            layout, args)
    except io.SoftwareError as exc:
        return fail(str(exc))
    except (OSError, yaml.YAMLError, json.JSONDecodeError) as exc:
        return fail(str(exc))
