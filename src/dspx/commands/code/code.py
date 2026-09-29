"""docspec code — 軟體領域（取代 OpenSpec）：能力規格、change 資料夾、任務、測試規劃。

    docspec code spec list | show <能力> [--req R1] [--json|--md]
    docspec code change new|set|design|delta|show|status|list …
    docspec code task add|list <change> …
    docspec code testplan add|list|object|respond <change> …
    docspec code evidence run|add|accept|waive|list <change> <task> …
    docspec code archive <change> [--dry-run]      收尾：差異併回正式規格、資料夾收進 _archive/、寫基線
    docspec code test [--capability X] [--list]    依正式規格的 verified-by 跑回歸測試
    docspec code import-openspec [--path openspec] [--dry-run]   從 OpenSpec 搬過來

任務的完成欄位沒有「打勾」指令：`evidence` 產生證據後，引擎依證據推導並寫回 tasks.yaml。

所有檔案都是引擎擁有、封條的 YAML，只能透過這些指令寫入；查詢支援 `--json` 讓 agent 只取需要的部分。
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

import yaml

from dspx.commands.governance._gov_common import emit_json, fail, open_layout
from dspx.engine import governance as gv
from dspx.engine.software import archive as arc
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

    repo = top.add_parser("repo", help="register the code repos whose tests the engine runs "
                          "(docspec/software/config.yaml)")
    rs = repo.add_subparsers(dest="op")
    x = rs.add_parser("add", help="register a repo (or update its settings)")
    x.add_argument("name", help="short name used in test locations, e.g. seating:tests/test_x.py::test_y")
    x.add_argument("path", help="repo folder, relative to the project root")
    x.add_argument("--test-command", default=None,
                   help="runner only, e.g. \"python -m pytest -q\" or \"PYTHONPATH=src python -m pytest\"; "
                        "the engine appends --rootdir, --junitxml and the planned test locations")
    x.add_argument("--junit-arg", default=None, help="non-pytest runners: how to ask for a JUnit report, "
                   "e.g. \"--reporter-out={junit}\"")
    x.add_argument("--rootdir-arg", default=None, help="non-pytest runners: root-dir option, \"\" for none")
    x = rs.add_parser("list", help="list registered repos and the command the engine will run")
    x.add_argument("--json", dest="as_json", action="store_true")

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
    x = cs.add_parser("design", help="edit design.yaml (list fields append; --remove-<field> drops an item)")
    x.add_argument("id")
    x.add_argument("--context", default=None)
    x.add_argument("--migration", default=None)
    for flag in ("goal", "non-goal", "risk", "open-question"):
        x.add_argument(f"--{flag}", action="append", default=[])
        x.add_argument(f"--remove-{flag}", action="append", default=[],
                       help=f"drop a {flag} (exact text, or its 1-based number as shown by change show)")
    x.add_argument("--decision", default="", help="governance decision ids (gov:D-…)")
    x.add_argument("--remove-decision", default="", help="drop cited decisions (e.g. superseded ones)")
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
    x = cs.add_parser("gaps", help="what links are still missing (tasks, planned tests)")
    x.add_argument("id")
    x.add_argument("--template", action="store_true",
                   help="print a YAML draft to fill in and load with task set --from / testplan add --from")
    x = cs.add_parser("undelta", help="take back spec deltas (to rewrite them)")
    x.add_argument("id")
    x.add_argument("--capability", required=True)
    x.add_argument("--ref", required=True, help="R1, R1/S2, or the id of a requirement this change adds")
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
    x = ts.add_parser("set", help="fill in or change a task's links (e.g. after an OpenSpec import)")
    x.add_argument("change")
    x.add_argument("task", nargs="?")
    x.add_argument("--from", dest="from_file", default=None,
                   help="YAML with `tasks: [{task, implements, files, verify, tests, …}]` "
                        "(see `docspec code change gaps --template`)")
    x.add_argument("--title", default=None)
    x.add_argument("--implements", default=None, help="replace: cap/R1,…")
    x.add_argument("--files", default=None, help="replace: repo:path,…")
    x.add_argument("--verify", default=None, help="replace: test,inspection,…")
    x.add_argument("--tests", default=None, help="replace: T1,T2")
    x.add_argument("--allow-skips", default=None, choices=["yes", "no"])
    x.add_argument("--depends-on", default=None, help="replace: task ids")
    x = ts.add_parser("remove", help="remove a task that has no evidence yet")
    x.add_argument("change")
    x.add_argument("task")
    x = ts.add_parser("list", help="list tasks with engine status")
    x.add_argument("change")
    x.add_argument("--json", dest="as_json", action="store_true")

    tp = top.add_parser("testplan", help="test plan (written by the test role, not the implementer)")
    tps = tp.add_subparsers(dest="op")
    x = tps.add_parser("add", help="plan a test for scenarios")
    x.add_argument("change")
    x.add_argument("--location", default=None, help="repo:path::test_name")
    x.add_argument("--covers", default=None, help="cap/R1/S1,… scenarios it verifies")
    x.add_argument("--from", dest="from_file", default=None,
                   help="YAML with `tests: [{location, covers, level, note}]`")
    x.add_argument("--level", default="unit", help=", ".join(tk.TEST_LEVELS))
    x.add_argument("--note", default=None)
    x.add_argument("--by", default=None)
    x = tps.add_parser("sign", help="test role: sign off the written tests (evidence refuses tests "
                       "that are unsigned or changed after sign-off)")
    x.add_argument("change")
    x.add_argument("tests", nargs="*", help="test ids (default: all planned tests)")
    x.add_argument("--by", default=None)
    x = tps.add_parser("remove", help="remove a planned test no task uses")
    x.add_argument("change")
    x.add_argument("test")
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
    x = es.add_parser("run", help="engine runs the task's planned tests with the repo's test runner")
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
    x = top.add_parser("archive", help="finish a change: merge its deltas into the specs, move the "
                       "folder to changes/_archive/, write a baseline")
    x.add_argument("change")
    x.add_argument("--dry-run", action="store_true", help="check and preview only")
    x.add_argument("--json", dest="as_json", action="store_true")
    x.add_argument("--by", default=None)
    x = top.add_parser("import-openspec", help="import an OpenSpec folder (specs, active and archived "
                       "changes) into docspec/software; writes an import report")
    x.add_argument("--path", default="openspec")
    x.add_argument("--dry-run", action="store_true")
    x.add_argument("--by", default=None)
    x = top.add_parser("test", help="regression: run the tests the specs name in verified-by")
    x.add_argument("--capability", default=None)
    x.add_argument("--list", action="store_true", help="only print the list (e.g. for CI)")
    x.add_argument("--json", dest="as_json", action="store_true")
    x = es.add_parser("list", help="evidence for a change")
    x.add_argument("change")
    x.add_argument("--task", default=None)
    x.add_argument("--json", dest="as_json", action="store_true")
    return p


# ── repo ─────────────────────────────────────────────────────────────────

def _repo(layout, args) -> int:
    if args.op == "add":
        p = io.config_path(layout)
        data = chg.load_config(layout)
        repos = data.get("repos") or {}
        entry = repos.get(args.name)
        entry = dict(entry) if isinstance(entry, dict) else {}
        entry["path"] = args.path
        for key, val in (("test-command", args.test_command), ("junit-arg", args.junit_arg),
                         ("rootdir-arg", args.rootdir_arg)):
            if val is not None:
                entry[key] = val
        if not (layout.project_root / args.path).is_dir():
            print(f"warning: {args.path} is not a folder yet (relative to {layout.project_root})",
                  file=sys.stderr)
        repos[args.name] = entry
        data["repos"] = repos
        if "test-command" in entry:
            ev._split_command(args.name, entry)          # 格式不對就在登記時擋下
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        print(f"repo \"{args.name}\" → {args.path} registered in {p.relative_to(layout.project_root)}")
        print("  tests run as: " + shlex.join(
            ev.build_command(layout, args.name, [f"{args.name}:<planned test>"], Path("<junit.xml>"))))
        return 0
    rows = []
    for name, cfg in chg.repo_settings(layout).items():
        try:
            env, _a = ev._split_command(name, cfg)
            cmd = shlex.join(ev.build_command(layout, name, [f"{name}:<planned test>"], Path("<junit.xml>")))
            if env:
                cmd = " ".join(f"{k}={v}" for k, v in env.items()) + " " + cmd
        except io.SoftwareError as exc:
            cmd = f"(invalid: {exc})"
        rows.append({"name": name, "path": cfg.get("path"), "command": cmd})
    if args.as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    elif not rows:
        print("(no repos registered — `docspec code repo add <name> <path>`)")
    else:
        for r in rows:
            print(f"{r['name']}: {r['path']}\n  tests run as: {r['command']}")
    return 0


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


def _gaps_template(cid: str, g: dict) -> str:
    """缺口草稿：agent 填好後分兩次載入（實作者 task set --from；測試角色 testplan add --from）。"""
    lines = [f"# Missing links for software change {cid}.",
             "# Implementer: fill `tasks`, then  docspec code task set " + cid + " --from <file>",
             "# Test role:   fill `tests`, then  docspec code testplan add " + cid + " --from <file>",
             "#", "# Requirements that no task implements yet (put them in some task's `implements`):"]
    lines += [f"#   {r}" for r in g["requirements-without-task"]] or ["#   (none)"]
    lines += ["", "tasks:"]
    for t in g["tasks-to-complete"]:
        v = t.get("verify") or {}
        lines += [f"  - task: \"{t['id']}\"   # {str(t.get('title'))[:70]}",
                  f"    implements: {json.dumps(io.as_list(t.get('implements')))}",
                  f"    files: {json.dumps(io.as_list(t.get('files')))}",
                  f"    verify: {json.dumps(io.as_list(v.get('methods')))}   # test / inspection / "
                  f"demonstration / analysis",
                  f"    tests: {json.dumps(io.as_list(v.get('tests')))}   # planned test ids once they exist"]
    lines += ["", "tests:"]
    for ref in g["scenarios-without-test"]:
        lines += ["  - location: \"\"   # repo:path::test_name — leave empty to skip",
                  f"    covers: [\"{ref}\"]", "    level: unit"]
    return "\n".join(lines) + "\n"


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

    if args.op == "show" and chg.change_state(layout, args.id) == "archived":
        ch = chg.load_archived(layout, args.id)
    else:
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
        for key, drops in (("goals", args.remove_goal), ("non-goals", args.remove_non_goal),
                           ("risks", args.remove_risk), ("open-questions", args.remove_open_question)):
            items = list(d.get(key) or [])
            for drop in drops:
                target = drop.strip()
                if target.isdigit() and 1 <= int(target) <= len(items):
                    target = items[int(target) - 1]
                if target not in items:
                    raise io.SoftwareError(f"design {key} has no item {drop!r}")
                items.remove(target)
            if drops:
                if items:
                    d[key] = items
                else:
                    d.pop(key, None)
        for key, vals in (("goals", args.goal), ("non-goals", args.non_goal), ("risks", args.risk),
                          ("open-questions", args.open_question)):
            if vals:
                d[key] = _merge(d.get(key) or [], vals)
        if args.remove_decision:
            drop = set(_gov_csv(args.remove_decision))
            d["decisions"] = [x for x in d.get("decisions") or [] if x not in drop]
        if args.decision:
            d["decisions"] = _merge(d.get("decisions") or [], _gov_csv(args.decision))
        if not d.get("decisions"):
            d.pop("decisions", None)
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
    if args.op == "gaps":
        g = tk.gaps(layout, ch)
        if args.template:
            print(_gaps_template(args.id, g), end="")
            return 0
        print(f"change {args.id}:")
        print(f"  requirements without a task: {len(g['requirements-without-task'])}")
        for r in g["requirements-without-task"]:
            print(f"    - {r}")
        print(f"  scenarios without a planned test: {len(g['scenarios-without-test'])}")
        for r in g["scenarios-without-test"]:
            print(f"    - {r}")
        print(f"  tasks missing verification or files: {len(g['tasks-to-complete'])}")
        for t in g["tasks-to-complete"]:
            print(f"    - {t['id']}. {t.get('title')}")
        print(f"(fill them in bulk: `docspec code change gaps {args.id} --template > links.yaml`)")
        return 0
    if args.op == "undelta":
        removed = chg.remove_deltas(layout, args.id, args.capability, args.ref)
        print(f"code change undelta: {args.id}: removed {removed} delta(s) on {args.capability} {args.ref}")
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
    touched: dict[str, int] = {}
    for ref in tk.touched_summary(ch):
        cap, rid, sid = sp.split_ref(ref)
        if not sid:
            touched[cap] = touched.get(cap, 0) + 1
    print("touches: " + (", ".join(f"{cap} ({n} requirement(s))" for cap, n in touched.items()) or "—"))
    for row in ev.explain(layout, args.id):
        if row["status"] not in ("done", "done-waived", "imported-done"):
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
                          allow_skips=args.allow_skips, depends_on=_csv(args.depends_on),
                          tool=gv.detect_tool(None))
        chg.write_part(layout, args.change, "tasks", ch["tasks"])
        print(f"code task add: {args.change} task {rec['id']} — {rec['title']}")
        return 0
    if args.op == "set":
        if args.from_file:
            entries = (yaml.safe_load(Path(args.from_file).read_text(encoding="utf-8")) or {}).get("tasks")
            if not isinstance(entries, list):
                return fail("--from: the file needs a `tasks:` list")
            for e in entries:                       # 全部套用成功才寫入
                if not isinstance(e, dict) or not e.get("task"):
                    return fail("--from: every entry needs `task: <id>`")
                tk.set_task(ch, str(e["task"]), {k: e.get(k) for k in (
                    "title", "implements", "files", "verify", "tests", "allow-skips", "depends-on")})
            done = [str(e["task"]) for e in entries]
        else:
            if not args.task:
                return fail("task set needs a task id (or --from FILE)")
            tk.set_task(ch, args.task, {
                "title": args.title, "implements": None if args.implements is None else _csv(args.implements),
                "files": None if args.files is None else _csv(args.files),
                "verify": None if args.verify is None else _csv(args.verify),
                "tests": None if args.tests is None else _csv(args.tests),
                "allow-skips": None if args.allow_skips is None else args.allow_skips == "yes",
                "depends-on": None if args.depends_on is None else _csv(args.depends_on)})
            done = [args.task]
        chg.write_part(layout, args.change, "tasks", ch["tasks"])
        print(f"code task set: {args.change} task(s) {', '.join(done)} updated")
        _report_refresh(ev.refresh(layout, args.change), args.change)
        return 0
    if args.op == "remove":
        if ev.for_task(ev.load_all(layout), args.change, args.task):
            return fail(f"task {args.task} already has evidence; it cannot be removed (waive it instead)")
        tasks = ch["tasks"].get("tasks") or []
        keep = [t for t in tasks if str(t.get("id")) != args.task]
        if len(keep) == len(tasks):
            return fail(f"change {args.change} has no task \"{args.task}\"")
        users = [t["id"] for t in keep if args.task in io.as_list(t.get("depends-on"))]
        if users:
            return fail(f"task(s) {', '.join(users)} depend on task {args.task}")
        ch["tasks"]["tasks"] = keep
        chg.write_part(layout, args.change, "tasks", ch["tasks"])
        print(f"code task remove: {args.change} task {args.task}")
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
    if args.op == "remove":
        users = [t["id"] for t in ch["tasks"].get("tasks") or []
                 if args.test in io.as_list((t.get("verify") or {}).get("tests"))]
        if users:
            return fail(f"planned test {args.test} is used by task(s) {', '.join(users)}")
        before = len(tests.get("tests") or [])
        tests["tests"] = [t for t in tests.get("tests") or [] if str(t.get("id")) != args.test]
        if len(tests["tests"]) == before:
            return fail(f"change {args.change} has no planned test \"{args.test}\"")
        chg.write_part(layout, args.change, "tests", tests)
        print(f"code testplan remove: {args.change} {args.test}")
        return 0
    tool = gv.detect_tool(args.by)
    if args.op == "sign":
        signed = tk.sign_tests(layout, ch, args.tests, tool=tool, now=ev._now(),
                               fingerprint=lambda loc: ev.file_hash(layout, ev.test_file_key(loc)))
        chg.write_part(layout, args.change, "tests", tests)
        for t in signed:
            print(f"code testplan sign: {args.change} {t['id']} {t['location']} signed by {tool}")
        _report_refresh(ev.refresh(layout, args.change), args.change)
        return 0
    if args.op == "add":
        if args.from_file:
            entries = (yaml.safe_load(Path(args.from_file).read_text(encoding="utf-8")) or {}).get("tests")
            if not isinstance(entries, list):
                return fail("--from: the file needs a `tests:` list")
            added, skipped = [], 0
            for e in entries:
                if not isinstance(e, dict) or not str(e.get("location") or "").strip():
                    skipped += 1                          # 範本裡還沒填位置的列
                    continue
                added.append(tk.add_test(tests, location=str(e["location"]).strip(),
                                         covers=io.as_list(e.get("covers")),
                                         level=str(e.get("level") or "unit"), tool=tool,
                                         note=e.get("note"), today=gv.today()))
            msg = (f"code testplan add: {args.change} {len(added)} test(s) planned"
                   + (f"; {skipped} entr(ies) without a location skipped" if skipped else ""))
        else:
            if not args.location or not args.covers:
                return fail("testplan add needs --location and --covers (or --from FILE)")
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


def _evidence(layout, args) -> int:
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
        rec = ev.run_tests(layout, args.change, args.task, tool=tool, timeout=args.timeout)
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
        print(f"evidence {rec['id']}: task {args.task} waived by 「{rec['ruling-quote']}」"
              f"({rec['ruling']}) — check that this ruling is really about this task")
    changed = ev.refresh(layout, args.change)
    _report_refresh(changed, args.change)
    if not changed:
        row = next(r for r in ev.explain(layout, args.change) if str(r["task"]) == str(args.task))
        print(f"task {args.change}#{args.task}: {tk.STATUS_LABEL.get(row['status'], row['status'])}"
              f" — {row['why']}")
    return 0 if rec.get("result") == "pass" else 1


def _archive(layout, args) -> int:
    p = arc.plan(layout, args.change)
    if args.as_json:
        emit_json({k: v for k, v in p.items() if k not in ("ch", "specs")}
                  | {"capabilities": sorted(p["specs"])})
        if not p["ok"] or args.dry_run:
            return 0 if p["ok"] else 1
    if not p["ok"]:
        print(f"cannot archive {args.change} yet:")
        for e in p["errors"]:
            print(f"  ✗ {e}")
        return 1
    if not args.as_json:
        print(f"{'would archive' if args.dry_run else 'archiving'} {args.change}:")
        for cap in sorted(p["specs"]):
            print(f"  spec {cap} updated")
        for old, new in p["renames"].items():
            print(f"  ! {old} was taken by another change; renumbered to {new}")
        for w in p["warnings"]:
            print(f"  ! {w}")
    if args.dry_run:
        return 0
    res = arc.archive(layout, args.change, tool=gv.detect_tool(args.by))
    if not args.as_json:
        for row in res.get("waived", []):
            print(f"  waived: task {row['task']} ({row['title']}) — {row['why']}")
        print(f"  moved to {res['dest'].relative_to(layout.project_root)}")
        print(f"  baseline written ({len(res['baseline']['evidence'])} evidence record(s))")
        for d in res["dropped-verified-by"]:
            print(f"  ! {d['scenario']} changed; these tests no longer verify it (test role: update or "
                  f"delete them): {', '.join(d['tests'])}")
        for sid in res["cleared-suspects"]:
            print(f"  suspect flag {sid} cleared (requirement rewritten by this change)")
        for other in res["affected"]:
            print(f"  ! active change {other} edits the same capability — run "
                  f"`docspec code change status {other}` to check its deltas still apply")
    return 0


def _import(layout, args) -> int:
    from dspx.engine.software import openspec_import as osi
    source = Path(args.path)
    if not source.is_absolute():
        source = (Path.cwd() / source).resolve()
    report = osi.run_import(layout, source, tool=gv.detect_tool(args.by), dry_run=args.dry_run)
    text = osi.render_report(report, args.path)
    if args.dry_run:
        print(text, end="")
        return 0
    out = io.root(layout) / "import-openspec-report.md"
    out.write_text(text, encoding="utf-8")
    print(f"imported {len(report['specs'])} spec(s), {len(report['active'])} active and "
          f"{len(report['archived'])} archived change(s); {len(report['notes'])} note(s)")
    print(f"report: {out.relative_to(layout.project_root)}")
    return 0


def _test(layout, args) -> int:
    if args.list:
        rows = arc.regression_list(layout, args.capability)
        if args.as_json:
            emit_json(rows)
            return 0
        for repo, items in rows.items():
            print(f"[{repo}]")
            for i in items:
                print(f"  {i['location']}  ← {', '.join(i['scenarios'])}")
        if not rows:
            print("(no verified-by tests in the specs yet)")
        return 0
    results = arc.run_regression(layout, args.capability)
    if args.as_json:
        emit_json(results)
    bad = False
    for r in results:
        if r.get("error"):
            bad = True
            if not args.as_json:
                print(f"[{r['repo']}] error: {r['error']}")
            continue
        c = r["counts"]
        bad = bad or bool(r["failing"]) or r["exit"] != 0
        if not args.as_json:
            print(f"[{r['repo']}] passed {c['passed']}, failed {c['failed']}, skipped {c['skipped']}")
            for f in r["failing"]:
                print(f"  ✗ {f['location']} {f['outcome']} → affects {', '.join(f['scenarios'])}")
    if not results and not args.as_json:
        print("(no verified-by tests in the specs yet)")
    return 1 if bad else 0


def run(argv: list[str]) -> int:
    if "--" in argv:
        return fail("custom test commands are not accepted: the engine builds the command from the "
                    "planned tests. Change the runner with `test-command` for the repo in "
                    "docspec/software/config.yaml.")
    p = _parser()
    args = p.parse_args(argv)
    if not args.area or (args.area not in ("archive", "test", "import-openspec")
                         and not getattr(args, "op", None)):
        p.print_help()
        return 0
    layout = open_layout()
    if layout is None:
        return 1
    try:
        if args.area == "evidence":
            return _evidence(layout, args)
        if args.area == "archive":
            return _archive(layout, args)
        if args.area == "test":
            return _test(layout, args)
        if args.area == "import-openspec":
            return _import(layout, args)
        return {"repo": _repo, "spec": _spec, "change": _change, "task": _task, "testplan": _testplan}[args.area](
            layout, args)
    except io.SoftwareError as exc:
        return fail(str(exc))
    except (OSError, yaml.YAMLError, json.JSONDecodeError) as exc:
        return fail(str(exc))
