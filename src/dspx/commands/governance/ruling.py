"""docspec ruling — 使用者裁定（agent 轉記；major 需使用者以 `docspec approve` 確認）。

- `--tier major`：會改變決策的裁定。存為 pending，只有使用者在終端機 `docspec approve` 才轉
  confirmed；未確認前不能作為決策生效的依據。
- `--tier minor`：一般性的小裁定。只記原話（status＝recorded），清單上標「未經本人確認」，
  也不能作為決策生效的依據。
- 「被取代」不手寫：由之後確認的裁定 `--supersedes` 推導。
"""

from __future__ import annotations

import argparse

from dspx.commands.governance._gov_common import (emit_json, fail, label, open_layout, public,
                                                  split_csv)
from dspx.engine import governance as gv

NAME = "ruling"
HELP = ("governance: the owner's rulings, transcribed by an agent (add / list / show); "
        "major rulings take effect only after the owner runs `docspec approve`")

_TIER_NOTE = {"pending": "awaiting owner confirmation", "confirmed": "confirmed by owner",
              "rejected": "rejected by owner", "recorded": "recorded, not confirmed by owner",
              "superseded": "superseded"}


def run(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="docspec ruling", description=HELP)
    sub = p.add_subparsers(dest="op")
    a = sub.add_parser("add", help="transcribe a ruling (verbatim quote)")
    a.add_argument("--quote", required=True, help="the owner's exact words")
    a.add_argument("--interpretation", default="", help="how the agent understands it")
    a.add_argument("--tier", required=True, choices=gv.RULING_TIERS,
                   help="major = changes a decision (owner must confirm); minor = record only")
    a.add_argument("--answers", default="", help="comma-separated question ids it answers")
    a.add_argument("--supersedes", default="", help="comma-separated earlier ruling ids it replaces")
    a.add_argument("--provisional", action="store_true", help="the owner said this is tentative")
    a.add_argument("--date", default=None, help="date the owner said it (default today)")
    a.add_argument("--by", default=None, help="tool prefix: claude|gpt|gemini (auto-detected)")
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
            tool = gv.detect_tool(args.by)
            if tool == "user":
                return fail("rulings are transcribed by an agent; the owner confirms them with "
                            "`docspec approve`")
            rid = gv.next_id(layout, "ruling", tool)
            rec = {"id": rid, "quote": args.quote.strip(), "date": args.date or gv.today(),
                   "recorded-by": tool, "tier": args.tier,
                   "status": "pending" if args.tier == "major" else "recorded"}
            for key, raw in (("answers", args.answers), ("supersedes", args.supersedes)):
                if split_csv(raw):
                    rec[key] = split_csv(raw)
            if args.interpretation.strip():
                rec["interpretation"] = args.interpretation.strip()
            if args.provisional:
                rec["provisional"] = True
            gv.write_record(layout, "ruling", rec)
            note = (" — the owner must confirm it with `docspec approve` before it can support a decision"
                    if args.tier == "major" else " — recorded only (not confirmed by the owner)")
            print(f"ruling add: {label(rec)}{note}")
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
            prov = "，暫定" if r.get("provisional") else ""
            print(f"- [{_TIER_NOTE.get(r['effective-status'], r['effective-status'])}{prov}] "
                  f"{label(r)}")
        return 0
    except gv.GovernanceError as exc:
        return fail(str(exc))
