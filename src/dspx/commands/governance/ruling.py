"""docspec ruling — 使用者的決定（保存原話；寫入即生效）。

2026/09/30 實測後修訂：
1. 一律保存使用者原話（`--quote`）。
2. 使用者講得清楚就直接記；講得不清楚時，先在對話中覆述（`--read-back`），使用者回覆確認後
   把回覆原文放進 `--confirmed`（兩者一起給）。
3. 寫入後即生效，可作為決策的依據。使用者提供的現況資訊（不是決定）用 `docspec info`。
使用者事後說「記錯了」→ `ruling reject <id> --reason "<使用者原話>"`，觸發影響分析。
「被取代」不手寫：由之後的裁定 `--supersedes` 推導。
"""

from __future__ import annotations

import argparse

from dspx.commands.governance._gov_common import (emit_json, fail, label, open_layout, public,
                                                  split_csv)
from dspx.engine import governance as gv

NAME = "ruling"
HELP = ("governance: the owner's decisions, kept in their own words (read back only when unclear) "
        "(add / reject / list / show); information the owner gives is `docspec info`")

_STATUS_NOTE = {"effective": "effective", "rejected": "rejected by the owner",
                "superseded": "superseded"}


def run(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="docspec ruling", description=HELP)
    sub = p.add_subparsers(dest="op")
    a = sub.add_parser("add", help="record a decision the owner made")
    a.add_argument("--quote", required=True, help="the owner's exact words")
    a.add_argument("--read-back", default="",
                   help="only when the owner was unclear: how you restated it, in plain words")
    a.add_argument("--confirmed", default="",
                   help="with --read-back: the owner's reply confirming it (verbatim)")
    a.add_argument("--answers", default="", help="comma-separated question ids it answers")
    a.add_argument("--supersedes", default="", help="comma-separated earlier ruling ids it replaces")
    a.add_argument("--provisional", action="store_true", help="the owner said this is tentative")
    a.add_argument("--date", default=None, help="date the owner said it (default today)")
    a.add_argument("--by", default=None, help="tool prefix: claude|gpt|gemini (auto-detected)")
    rj = sub.add_parser("reject", help="the owner says a recorded ruling is wrong")
    rj.add_argument("id")
    rj.add_argument("--reason", required=True, help="the owner's words")
    ls = sub.add_parser("list", help="list rulings")
    ls.add_argument("--status", default=None, help="filter by effective status")
    ls.add_argument("--json", dest="as_json", action="store_true")
    sh = sub.add_parser("show", help="show one ruling")
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
                return fail("--read-back and --confirmed go together: when the owner was unclear, "
                            "record both your restatement and their confirming reply")
            tool = gv.detect_tool(args.by)
            rid = gv.next_id(layout, "ruling", tool)
            rec = {"id": rid, "quote": args.quote.strip(), "date": args.date or gv.today(),
                   "recorded-by": tool, "status": "effective"}
            if args.read_back.strip():
                rec["read-back"] = args.read_back.strip()
                rec["confirmed-reply"] = args.confirmed.strip()
            for key, raw in (("answers", args.answers), ("supersedes", args.supersedes)):
                if split_csv(raw):
                    rec[key] = split_csv(raw)
            if args.provisional:
                rec["provisional"] = True
            gv.write_record(layout, "ruling", rec)
            print(f"ruling add: {label(rec)}")
            # 連結提醒（不擋）：新裁定可能改變現行決策；不取代＝兩者並存、影響分析永遠看不到。
            gov = gv.load_governance(layout)
            active = [d for d in gov.decisions if gv.decision_effective_status(d, gov) == "active"]
            if active:
                print(f"  active project decisions — if this ruling changes one of them, write the full "
                      f"new version with `docspec decision add --supersedes <id> --based-on {rid} …` "
                      f"and activate it:")
                for d in active[:8]:
                    print(f"    - {d.get('title')}（{d.get('id')}）")
                if len(active) > 8:
                    print(f"    … {len(active) - 8} more (`docspec decision list`)")
            if rec.get("supersedes"):
                from dspx.engine.impact import flag_after_change
                flagged = flag_after_change(layout, rid)
                if flagged:
                    print(f"impact: {len(flagged)} downstream item(s) marked suspect — "
                          f"run `docspec impact` to review")
            return 0
        if args.op == "reject":
            rid = gv.strip_ns(args.id)
            path = gv.record_path(layout, "ruling", rid)
            if not path.is_file():
                return fail(f"no such ruling \"{rid}\"")
            rec = gv.load_record(path, "ruling")
            rec.update({"status": "rejected", "rejected-reason": args.reason.strip(),
                        "rejected-at": gv.today()})
            gv.write_record(layout, "ruling", rec)
            from dspx.engine.impact import flag_after_change
            flagged = flag_after_change(layout, rid)
            print(f"ruling {rid} -> rejected"
                  + (f"; {len(flagged)} downstream item(s) marked suspect" if flagged else ""))
            return 0
        gov = gv.load_governance(layout)
        if args.op == "show":
            rid = gv.strip_ns(args.id)
            rec = next((r for r in gov.rulings if str(r.get("id")) == rid), None)
            if rec is None:
                return fail(f"no such ruling \"{rid}\"")
            out = {**public(rec), "effective-status": gv.ruling_effective_status(rec, gov)}
            if args.as_json:
                emit_json(out)
            else:
                for k, v in out.items():
                    print(f"{k}: {v}")
            return 0
        rows = [{**public(r), "effective-status": gv.ruling_effective_status(r, gov)}
                for r in gov.rulings]
        if args.status:
            rows = [r for r in rows if r["effective-status"] == args.status]
        if args.as_json:
            emit_json({"rulings": rows})
            return 0
        if not rows:
            print("(no rulings)")
        for r in rows:
            prov = ", provisional" if r.get("provisional") else ""
            print(f"- [{_STATUS_NOTE.get(r['effective-status'], r['effective-status'])}{prov}] "
                  f"{label(r)}")
        return 0
    except gv.GovernanceError as exc:
        return fail(str(exc))
