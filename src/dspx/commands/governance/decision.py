"""docspec decision — 專案層（跨領域的方向性）決策。

- `add` 建草稿。取代舊決策時用 `--supersedes`，而且 `--statement` 必須是**合併後的完整新版**
  （2026/09/29 裁定：不再允許「以後者為準」式的局部取代）。
- `activate` 轉為有效：前提是 `--based-on` 的裁定全部是 major 且已經使用者確認。新決策生效後，
  它 supersedes 的舊決策推導為 superseded（舊檔不改），並觸發影響分析。
- `withdraw` 撤回；`list` 預設只列有效；`show` 含完整取代歷史。
文件章節以 `gov:<id>` realizes 這裡的決策。
"""

from __future__ import annotations

import argparse

from dspx.commands.governance._gov_common import (emit_json, fail, label, open_layout, public,
                                                  split_csv)
from dspx.engine import governance as gv

NAME = "decision"
HELP = ("governance: project-level decisions (add draft / activate / withdraw / list / show); "
        "superseding requires the full merged text")


def history_chain(did: str, gov: gv.Governance) -> list[dict]:
    """沿 supersedes 往回走的完整歷史（新到舊，含依據裁定）。"""
    by_id = {str(d.get("id")): d for d in gov.decisions}
    out, seen, queue = [], set(), [did]
    while queue:
        cur = queue.pop(0)
        if cur in seen or cur not in by_id:
            continue
        seen.add(cur)
        d = by_id[cur]
        out.append({**public(d), "effective-status": gv.decision_effective_status(d, gov)})
        queue.extend(gv._as_list(d.get("supersedes")))
    return out


def run(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="docspec decision", description=HELP)
    sub = p.add_subparsers(dest="op")
    a = sub.add_parser("add", help="create a draft decision")
    a.add_argument("--title", required=True)
    a.add_argument("--statement", required=True,
                   help="the complete current text (when superseding: the full merged text)")
    a.add_argument("--rationale", default="")
    a.add_argument("--based-on", default="", help="comma-separated ruling ids")
    a.add_argument("--supersedes", default="", help="comma-separated decision ids this replaces")
    a.add_argument("--by", default=None, help="tool prefix: claude|gpt|gemini (auto-detected)")
    act = sub.add_parser("activate", help="make a draft decision active")
    act.add_argument("id")
    wd = sub.add_parser("withdraw", help="withdraw a decision")
    wd.add_argument("id")
    ls = sub.add_parser("list", help="list decisions (default: active only)")
    ls.add_argument("--all", action="store_true")
    ls.add_argument("--json", dest="as_json", action="store_true")
    sh = sub.add_parser("show", help="show a decision with its full supersede history")
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
        gov = gv.load_governance(layout)
        known = {str(d.get("id")) for d in gov.decisions}
        if args.op == "add":
            supersedes = split_csv(args.supersedes)
            based_on = split_csv(args.based_on)
            missing = [x for x in supersedes if x not in known]
            if missing:
                return fail(f"--supersedes points to unknown decision(s): {', '.join(missing)}")
            rulings = {str(r.get("id")) for r in gov.rulings}
            missing = [x for x in based_on if x not in rulings]
            if missing:
                return fail(f"--based-on points to unknown ruling(s): {', '.join(missing)}")
            tool = gv.detect_tool(args.by)
            rid = gv.next_id(layout, "decision", tool)
            rec = {"id": rid, "title": args.title.strip(), "statement": args.statement.strip(),
                   "status": "draft", "created-by": tool, "created-at": gv.today()}
            if args.rationale.strip():
                rec["rationale"] = args.rationale.strip()
            if based_on:
                rec["based-on"] = based_on
            if supersedes:
                rec["supersedes"] = supersedes
            gv.write_record(layout, "decision", rec)
            print(f"decision add (draft): {label(rec)}")
            return 0
        if args.op in ("activate", "withdraw"):
            did = gv.strip_ns(args.id)
            path = gv.record_path(layout, "decision", did)
            if not path.is_file():
                return fail(f"no such decision \"{did}\"")
            rec = gv.load_record(path, "decision")
            if args.op == "activate":
                if rec.get("status") != "draft":
                    return fail(f"decision {did} is {rec.get('status')}, not a draft")
                bad = gv.unconfirmed_basis(rec, gov)
                if bad:
                    return fail(f"cannot activate {did}: based on rulings not confirmed by the owner "
                                f"({', '.join(bad)}). Ask the owner to run `docspec approve`.")
                if not gv._as_list(rec.get("based-on")):
                    return fail(f"cannot activate {did}: it cites no owner-confirmed ruling "
                                f"(--based-on). Record the owner's ruling first.")
                rec["status"] = "active"
            else:
                rec["status"] = "withdrawn"
            gv.write_record(layout, "decision", rec)
            print(f"decision {did} -> {rec['status']}")
            if gv._as_list(rec.get("supersedes")) or args.op == "withdraw":
                from dspx.engine.impact import flag_after_change
                flagged = flag_after_change(layout, did)
                if flagged:
                    print(f"impact: {len(flagged)} downstream item(s) marked suspect — "
                          f"run `docspec impact` to review")
            return 0
        if args.op == "show":
            did = gv.strip_ns(args.id)
            chain = history_chain(did, gov)
            if not chain:
                return fail(f"no such decision \"{did}\"")
            if args.as_json:
                emit_json({"decision": did, "history": chain})
                return 0
            for i, d in enumerate(chain):
                tag = "current" if i == 0 else "earlier"
                print(f"[{tag}] {label(d)} — {d['effective-status']}")
                print(f"    {d.get('statement')}")
                if d.get("based-on"):
                    print(f"    based on: {', '.join(d['based-on'])}")
            return 0
        rows = [{**public(d), "effective-status": gv.decision_effective_status(d, gov)}
                for d in gov.decisions]
        if not args.all:
            rows = [r for r in rows if r["effective-status"] == "active"]
        if args.as_json:
            emit_json({"decisions": rows})
            return 0
        if not rows:
            print("(no decisions)")
        for r in rows:
            print(f"- [{r['effective-status']}] {label(r)}")
        return 0
    except gv.GovernanceError as exc:
        return fail(str(exc))
