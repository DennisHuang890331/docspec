"""docspec baseline — 專案基線：交付時把整個專案一次釘住，並查某個文件版本對應的軟體狀態。

    docspec baseline <名稱> [--note "…"]      建立（例：docspec baseline 期中交付）
    docspec baseline list
    docspec baseline show <名稱> [--json]
    docspec baseline doc <文件> <版本> [--json]   文件定版時自動記下的軟體狀態
"""

from __future__ import annotations

import argparse

from dspx.commands.governance._gov_common import emit_json, fail, open_layout
from dspx.engine import governance as gv
from dspx.engine import project_baseline as pb

NAME = "baseline"
HELP = ("project baseline: pin every document version, the software specs, repo commits and active "
        "decisions under a name (e.g. a delivery); show what state a frozen document version described")
_SUBS = ("list", "show", "doc", "create")


def _print_state(b: dict) -> None:
    sw = b.get("software") or {}
    for repo, commit in (sw.get("repos") or {}).items():
        print(f"  commit {repo}: {commit}")
    specs = sw.get("specs")
    if isinstance(specs, dict):
        print(f"  software specs: {len(specs)} capability spec(s) pinned")
    if sw.get("active-changes"):
        print(f"  open software changes: {', '.join(sw['active-changes'])}")
    dec = (b.get("governance") or {}).get("decisions")
    if isinstance(dec, list):
        print(f"  active decisions: {', '.join(dec) or '—'}")


def run(argv: list[str]) -> int:
    if argv and argv[0] not in _SUBS and not argv[0].startswith("-"):
        argv = ["create", *argv]                        # `docspec baseline 期中交付`
    p = argparse.ArgumentParser(prog="docspec baseline", description=HELP)
    sub = p.add_subparsers(dest="op")
    c = sub.add_parser("create", help="pin the whole project under a name")
    c.add_argument("name")
    c.add_argument("--note", default="")
    c.add_argument("--by", default=None)
    sub.add_parser("list", help="list project baselines")
    s = sub.add_parser("show", help="show one project baseline")
    s.add_argument("name")
    s.add_argument("--json", dest="as_json", action="store_true")
    d = sub.add_parser("doc", help="software state recorded when a document version was frozen")
    d.add_argument("article")
    d.add_argument("version")
    d.add_argument("--json", dest="as_json", action="store_true")
    args = p.parse_args(argv)
    if not args.op:
        p.print_help()
        return 0
    layout = open_layout()
    if layout is None:
        return 1
    try:
        if args.op == "create":
            from dspx.commands._shared import BootstrapError, load_model
            try:
                leaves = load_model(layout)
            except BootstrapError as exc:
                return exc.exit_code
            b = pb.create(layout, leaves, args.name, note=args.note, tool=gv.detect_tool(args.by))
            print(f"baseline \"{b['name']}\" recorded ({pb.project_path(layout, b['name']).relative_to(layout.project_root)})")
            for art, row in b["documents"].items():
                print(f"  {art}: v{row['version']}" if row["version"] else f"  {art}: (never frozen)")
            _print_state(b)
            for w in b.get("warnings") or []:
                print(f"  ! {w}")
            return 0
        if args.op == "list":
            rows = pb.list_all(layout)
            if not rows:
                print("(no project baselines yet — `docspec baseline <name>`)")
            for r in rows:
                print(f"{r['name']} — {r['created-at']}" + (f" — {r['note']}" if r.get("note") else "")
                      + (f" ({r['warnings']} warning(s))" if r["warnings"] else ""))
            return 0
        if args.op == "show":
            b = pb.load(layout, args.name)
            if args.as_json:
                emit_json(b)
                return 0
            print(f"baseline \"{b['name']}\" — {b.get('created-at')}" + (f" — {b['note']}" if b.get("note") else ""))
            for art, row in b["documents"].items():
                extra = " (plus unfrozen edits)" if row.get("unfrozen-edits") else ""
                print(f"  {art}: v{row['version']}{extra}" if row["version"] else f"  {art}: (never frozen)")
            _print_state(b)
            for w in b.get("warnings") or []:
                print(f"  ! {w}")
            return 0
        rec = pb.doc_version_record(layout, args.article, args.version)
        if args.as_json:
            emit_json(rec)
            return 0
        print(f"\"{rec['document']}\" v{rec['version']} was frozen at {rec['frozen-at']}; at that moment:")
        _print_state(rec)
        return 0
    except pb.BaselineError as exc:
        return fail(str(exc))
