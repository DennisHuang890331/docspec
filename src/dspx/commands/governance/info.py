"""docspec info — 使用者提供的現況資訊（不是決定）。

2026/09/30 實測後裁定：原本文件樹每節分「決定（decisions）」與「資訊（material）」，治理層只做了
決定那一半。負責人說的現況（例如「學校電腦大多是 Windows 10」「名單欄位是班級、座號、學號、姓名」）
記在這裡：保存原話、主題、誰提供的；講得不清楚時才覆述確認。文件可以引用它（`gov:I-…`），
事實查核把它當第一手來源。資訊過時了，用較新的資訊 `--supersedes` 取代，或 `withdraw`。
"""

from __future__ import annotations

import argparse

from dspx.commands.governance._gov_common import emit_json, fail, open_layout, public, split_csv
from dspx.engine import governance as gv

NAME = "info"
HELP = ("governance: information the owner gives about the current situation (not a decision), "
        "kept in their own words (add / withdraw / list / show)")


def _label(r: dict) -> str:
    return f"{r.get('about')}：{r.get('quote')}（{r.get('id')}）"


def run(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="docspec info", description=HELP)
    sub = p.add_subparsers(dest="op")
    a = sub.add_parser("add", help="record information the owner gave")
    a.add_argument("--quote", required=True, help="the owner's exact words")
    a.add_argument("--about", required=True, help="short topic, e.g. 學校電腦環境")
    a.add_argument("--source", default="", help="who it comes from if not the owner themself "
                   "(e.g. 資訊組, relayed by the owner)")
    a.add_argument("--read-back", default="", help="only when the owner was unclear: your restatement")
    a.add_argument("--confirmed", default="", help="with --read-back: the owner's confirming reply")
    a.add_argument("--supersedes", default="", help="comma-separated earlier info ids it replaces")
    a.add_argument("--date", default=None, help="date the owner said it (default today)")
    a.add_argument("--by", default=None, help="tool prefix: claude|gpt|gemini (auto-detected)")
    w = sub.add_parser("withdraw", help="the information turned out wrong or no longer applies")
    w.add_argument("id")
    w.add_argument("--reason", required=True)
    ls = sub.add_parser("list", help="list information (current by default)")
    ls.add_argument("--all", action="store_true", help="include superseded and withdrawn")
    ls.add_argument("--about", default=None, help="filter by topic (substring)")
    ls.add_argument("--json", dest="as_json", action="store_true")
    sh = sub.add_parser("show", help="show one piece of information")
    sh.add_argument("id")
    sh.add_argument("--json", dest="as_json", action="store_true")
    args = p.parse_args(argv)
    if not args.op:
        p.print_help()
        return 0
    layout = open_layout()
    if layout is None:
        return 1
    try:
        if args.op == "add":
            if bool(args.read_back.strip()) != bool(args.confirmed.strip()):
                return fail("--read-back and --confirmed go together")
            tool = gv.detect_tool(args.by)
            rid = gv.next_id(layout, "info", tool)
            rec = {"id": rid, "quote": args.quote.strip(), "about": args.about.strip(),
                   "date": args.date or gv.today(), "recorded-by": tool, "status": "current"}
            if args.source.strip():
                rec["source"] = args.source.strip()
            if args.read_back.strip():
                rec["read-back"] = args.read_back.strip()
                rec["confirmed-reply"] = args.confirmed.strip()
            if split_csv(args.supersedes):
                rec["supersedes"] = split_csv(args.supersedes)
            gv.write_record(layout, "info", rec)
            print(f"info add: {_label(rec)}")
            return 0
        if args.op == "withdraw":
            rid = gv.strip_ns(args.id)
            path = gv.record_path(layout, "info", rid)
            if not path.is_file():
                return fail(f"no such info \"{rid}\"")
            rec = gv.load_record(path, "info")
            rec.update({"status": "withdrawn", "withdrawn-reason": args.reason.strip(),
                        "withdrawn-at": gv.today()})
            gv.write_record(layout, "info", rec)
            print(f"info {rid} -> withdrawn")
            return 0
        gov = gv.load_governance(layout)
        rows = [{**public(r), "effective-status": gv.info_effective_status(r, gov)} for r in gov.infos]
        if args.op == "show":
            rid = gv.strip_ns(args.id)
            rec = next((r for r in rows if str(r.get("id")) == rid), None)
            if rec is None:
                return fail(f"no such info \"{rid}\"")
            if args.as_json:
                emit_json(rec)
            else:
                for k, v in rec.items():
                    print(f"{k}: {v}")
            return 0
        if not args.all:
            rows = [r for r in rows if r["effective-status"] == "current"]
        if args.about:
            rows = [r for r in rows if args.about in str(r.get("about"))]
        if args.as_json:
            emit_json({"info": rows})
            return 0
        if not rows:
            print("(no information recorded)")
        for r in rows:
            note = "" if r["effective-status"] == "current" else f" [{r['effective-status']}]"
            src = f"（據{r['source']}）" if r.get("source") else ""
            print(f"- {_label(r)}{src}{note}")
        return 0
    except gv.GovernanceError as exc:
        return fail(str(exc))
