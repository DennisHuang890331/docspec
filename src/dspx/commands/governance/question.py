"""docspec question — 待裁定問題（需要使用者決定的事）。

add ＝ agent 提出問題；explain ＝ 使用者表示沒聽懂、待解釋；withdraw ＝ 撤回；list ＝ 清單。
「已裁定」不手寫：有裁定 answers 它就推導為 answered。
"""

from __future__ import annotations

import argparse

from dspx.commands.governance._gov_common import (emit_json, fail, label, open_layout, public,
                                                  split_csv)
from dspx.engine import governance as gv

NAME = "question"
HELP = "governance: questions awaiting the owner's ruling (add / list / explain / withdraw)"


def _update_status(layout, qid: str, status: str) -> int:
    path = gv.record_path(layout, "question", qid)
    if not path.is_file():
        return fail(f"no such question \"{qid}\"")
    rec = gv.load_record(path, "question")
    rec["status"] = status
    gv.write_record(layout, "question", rec)
    print(f"question {qid} -> {status}")
    return 0


def run(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="docspec question", description=HELP)
    sub = p.add_subparsers(dest="op")
    a = sub.add_parser("add", help="record a question the owner must decide")
    a.add_argument("--title", required=True, help="one line, plain language")
    a.add_argument("--body", default="", help="plain-language explanation and the options")
    a.add_argument("--affects", default="", help="comma-separated ids this question affects")
    a.add_argument("--by", default=None, help="tool prefix: claude|gpt|gemini (auto-detected)")
    ls = sub.add_parser("list", help="list questions")
    ls.add_argument("--all", action="store_true", help="include answered and withdrawn")
    ls.add_argument("--json", dest="as_json", action="store_true")
    for op in ("explain", "withdraw", "reopen"):
        x = sub.add_parser(op, help={"explain": "the owner did not understand: needs explanation",
                                     "withdraw": "withdraw the question",
                                     "reopen": "back to open"}[op])
        x.add_argument("id")
    args = p.parse_args(argv)
    if not args.op:
        p.print_help()
        return 0
    layout = open_layout()
    if layout is None:
        return 1
    try:
        if args.op == "add":
            tool = gv.detect_tool(args.by)
            rid = gv.next_id(layout, "question", tool)
            rec = {"id": rid, "title": args.title.strip(), "status": "open",
                   "raised-by": tool, "raised-at": gv.today()}
            if args.body.strip():
                rec["body"] = args.body.strip()
            if split_csv(args.affects):
                rec["affects"] = split_csv(args.affects)
            gv.write_record(layout, "question", rec)
            print(f"question add: {label(rec)}")
            return 0
        if args.op in ("explain", "withdraw", "reopen"):
            status = {"explain": "needs-explanation", "withdraw": "withdrawn", "reopen": "open"}[args.op]
            return _update_status(layout, gv.strip_ns(args.id), status)
        gov = gv.load_governance(layout)
        rows = []
        for q in gov.questions:
            st = gv.question_effective_status(q, gov)
            if args.all or st in ("open", "needs-explanation"):
                rows.append({**public(q), "effective-status": st})
        if args.as_json:
            emit_json({"questions": rows})
            return 0
        if not rows:
            print("(no open questions)")
        for r in rows:
            print(f"- [{r['effective-status']}] {label(r)}")
        return 0
    except gv.GovernanceError as exc:
        return fail(str(exc))
