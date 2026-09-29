"""`docspec roadmap` 在啟用治理層的專案（有 docspec/governance/）：唯一一份專案 roadmap。

子指令：
  （無）            檢視：各里程碑進度與工作項目的推導狀態（--json、--milestone）
  add               新增工作項目（相容前一代：--kind gap|task、--target <節|forest>）
  milestone         新增里程碑（--type checkpoint|deliverable、--due）
  link <id> --ref   加一個指向（change:<id>／doc:<節或文章>／gov:<id>／swc:<軟體 change>）
  done <id> --note  手動結案（沒有 refs 可推導的小工作）
  waive <id> --ruling RL-… --note … [--reopen-when …]  豁免（依據使用者裁定）
  migrate           前一代 roadmap 一次轉換進來（已啟用治理層時冪等）
"""

from __future__ import annotations

import argparse

from dspx.commands._shared import BootstrapError, load_model
from dspx.commands.governance._gov_common import emit_json, fail, split_csv
from dspx.engine import governance as gv
from dspx.engine import roadmap_v2 as rv

_LEGACY_FOREST = "forest"


def _refs_from_target(target: str | None, leaves: list) -> list[str]:
    if not target or target == _LEGACY_FOREST:
        return []
    path = rv._section_path(target, leaves)
    return [f"doc:{path or target}"]


def _load(layout, rid: str, kind: str = "work") -> dict | None:
    path = gv.record_path(layout, kind, rid)
    return gv.load_record(path, kind) if path.is_file() else None


def _print_view(v: dict) -> None:
    def line(r: dict, indent: str = "  ") -> None:
        print(f"{indent}- [{rv.status_label(r['status'], r)}] {r['title']}（{r['id']}）")
        for c in v["children"].get(str(r["id"]), []):
            line(c, indent + "  ")

    if not v["milestones"] and not v["unassigned"]:
        print("(roadmap is empty)")
        return
    for m in v["milestones"]:
        due = f"，{m['due']}" if m.get("due") else ""
        print(f"{m['title']}（{m['type']}{due}，{m['id']}）— {m['done']}/{m['total']}")
        for r in m["items"]:
            line(r)
    if v["unassigned"]:
        print("未歸入里程碑：")
        for r in v["unassigned"]:
            line(r)


def run(argv: list[str], layout) -> int:
    p = argparse.ArgumentParser(prog="docspec roadmap",
                                description="the single project roadmap (governance layer)")
    p.add_argument("--json", dest="as_json", action="store_true")
    p.add_argument("--milestone", default=None, help="only this milestone")
    sub = p.add_subparsers(dest="op")
    a = sub.add_parser("add", help="add a work item")
    a.add_argument("--title", required=True)
    a.add_argument("--what", default="")
    a.add_argument("--milestone", dest="m", default=None)
    a.add_argument("--parent", default=None)
    a.add_argument("--depends-on", default="")
    a.add_argument("--ref", default="", help="comma-separated change:<id> / doc:<section> / gov:<id> / swc:<software change>")
    a.add_argument("--target", default=None, help="(compat) section path/id or 'forest'")
    a.add_argument("--kind", default=None, choices=("gap", "task"), help="(compat) gap or task")
    a.add_argument("--priority", default="")
    a.add_argument("--from-audit", default="")
    a.add_argument("--by", default=None)
    m = sub.add_parser("milestone", help="add a milestone")
    m.add_argument("--title", required=True)
    m.add_argument("--type", required=True, choices=gv.MILESTONE_TYPES,
                   help="checkpoint = plan checkpoint; deliverable = something handed over")
    m.add_argument("--due", default=None)
    m.add_argument("--by", default=None)
    lk = sub.add_parser("link", help="add refs to a work item")
    lk.add_argument("id")
    lk.add_argument("--ref", required=True)
    d = sub.add_parser("done", help="close a work item by hand (no refs to derive from)")
    d.add_argument("id")
    d.add_argument("--note", required=True)
    w = sub.add_parser("waive", help="waive part of a work item, citing the owner's ruling")
    w.add_argument("id")
    w.add_argument("--ruling", required=True)
    w.add_argument("--note", required=True)
    w.add_argument("--reopen-when", default="")
    sub.add_parser("migrate", help="convert the previous per-document/forest roadmap")
    args = p.parse_args(argv)
    try:
        leaves = load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code
    try:
        if args.op == "migrate":
            res = rv.migrate_legacy(layout, leaves, gv.detect_tool(None))
            if not res["created"]:
                print("nothing to migrate (no previous roadmap files)")
                return 0
            print(f"migrated {res['created']} roadmap entries into docspec/governance/roadmap/")
            for old, new in res["mapping"].items():
                print(f"  {old} -> {new}")
            for path in res["removed"]:
                print(f"  removed {path}")
            return 0
        if args.op == "add":
            tool = gv.detect_tool(args.by)
            rid = gv.next_id(layout, "work", tool)
            rec: dict = {"id": rid, "title": args.title.strip(), "created-by": tool,
                         "created-at": gv.today()}
            refs = split_csv(args.ref) and [r.strip() for r in args.ref.split(",") if r.strip()]
            refs = (refs or []) + _refs_from_target(args.target, leaves)
            for key, val in (("what", args.what.strip()), ("kind", args.kind),
                             ("priority", args.priority.strip()),
                             ("from-audit", args.from_audit.strip()),
                             ("milestone", gv.strip_ns(args.m) if args.m else None),
                             ("parent", gv.strip_ns(args.parent) if args.parent else None)):
                if val:
                    rec[key] = val
            if refs:
                rec["refs"] = refs
            if split_csv(args.depends_on):
                rec["depends-on"] = split_csv(args.depends_on)
            gv.write_record(layout, "work", rec)
            print(f"roadmap add: {rec['title']}（{rid}）")
            return 0
        if args.op == "milestone":
            tool = gv.detect_tool(args.by)
            rid = gv.next_id(layout, "milestone", tool)
            rec = {"id": rid, "title": args.title.strip(), "type": args.type,
                   "created-by": tool, "created-at": gv.today()}
            if args.due:
                rec["due"] = args.due
            gv.write_record(layout, "milestone", rec)
            print(f"milestone add: {rec['title']}（{rid}）")
            return 0
        if args.op in ("link", "done", "waive"):
            rid = gv.strip_ns(args.id)
            rec = _load(layout, rid)
            if rec is None:
                return fail(f"no such work item \"{rid}\"")
            if args.op == "link":
                refs = gv._as_list(rec.get("refs"))
                for r in (x.strip() for x in args.ref.split(",")):
                    if r and r not in refs:
                        refs.append(r)
                rec["refs"] = refs
            elif args.op == "done":
                rec["closed"] = {"date": gv.today(), "note": args.note.strip()}
            else:
                ruling = gv.strip_ns(args.ruling)
                if _load(layout, ruling, "ruling") is None:
                    return fail(f"no such ruling \"{ruling}\"")
                wv = {"ruling": ruling, "note": args.note.strip()}
                if args.reopen_when.strip():
                    wv["reopen-when"] = args.reopen_when.strip()
                rec["waivers"] = list(rec.get("waivers") or []) + [wv]
            gv.write_record(layout, "work", rec)
            print(f"roadmap {args.op}: {rec['title']}（{rid}）")
            return 0
        v = rv.view(layout, leaves)
        if args.milestone:
            mid = gv.strip_ns(args.milestone)
            v["milestones"] = [m for m in v["milestones"] if str(m["id"]) == mid]
            v["unassigned"] = []
        if args.as_json:
            emit_json(v)
        else:
            _print_view(v)
        return 0
    except gv.GovernanceError as exc:
        return fail(str(exc))
