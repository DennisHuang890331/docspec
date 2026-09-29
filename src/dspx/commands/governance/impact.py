"""docspec impact — 影響分析：未處理的可疑標記 ＋ 依賴已取代／撤回治理決策的文件章節。

- `docspec impact`：列出待處理項目（治理紀錄的可疑標記、需改指向接替決策的文件章節）。
- `docspec impact clear <S-id> --reason "..."`：看過之後附理由清除標記（理由必填）。
- `docspec trace <id>` 另見 trace 指令。
"""

from __future__ import annotations

import argparse

from dspx.commands._shared import BootstrapError, load_model
from dspx.commands.governance._gov_common import emit_json, fail, label, open_layout, public
from dspx.engine import governance as gv
from dspx.engine.impact import doc_sections_needing_review

NAME = "impact"
HELP = ("governance: impact review — open suspect flags and document sections that realize a "
        "superseded/withdrawn project decision; `impact clear <id> --reason` resolves a flag")


def open_items(layout, leaves, gov: gv.Governance) -> dict:
    by_id = gov.by_id()
    suspects = []
    for s in gov.suspects:
        if s.get("status") != "open":
            continue
        tgt = by_id.get(str(s.get("target")), {})
        trig = by_id.get(str(s.get("trigger")), {})
        suspects.append({**public(s), "target-label": label(tgt) if tgt else s.get("target"),
                         "trigger-label": label(trig) if trig else s.get("trigger")})
    return {"suspects": suspects, "sections": doc_sections_needing_review(layout, leaves, gov)}


def run(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="docspec impact", description=HELP)
    sub = p.add_subparsers(dest="op")
    c = sub.add_parser("clear", help="clear a suspect flag after review (reason required)")
    c.add_argument("id")
    c.add_argument("--reason", required=True)
    c.add_argument("--by", default=None)
    p.add_argument("--json", dest="as_json", action="store_true")
    args = p.parse_args(argv)
    layout = open_layout()
    if layout is None:
        return 1
    try:
        if args.op == "clear":
            sid = gv.strip_ns(args.id)
            path = gv.record_path(layout, "suspect", sid)
            if not path.is_file():
                return fail(f"no such suspect flag \"{sid}\"")
            if not args.reason.strip():
                return fail("--reason must say what was reviewed and why no (further) change is needed")
            rec = gv.load_record(path, "suspect")
            if rec.get("status") != "open":
                return fail(f"suspect flag {sid} is already {rec.get('status')}")
            rec.update({"status": "cleared", "cleared-reason": args.reason.strip(),
                        "cleared-by": gv.detect_tool(args.by), "cleared-at": gv.today()})
            gv.write_record(layout, "suspect", rec)
            print(f"suspect {sid} cleared")
            return 0
        try:
            leaves = load_model(layout)
        except BootstrapError as exc:
            return exc.exit_code
        gov = gv.load_governance(layout)
        items = open_items(layout, leaves, gov)
        if args.as_json:
            emit_json(items)
            return 0
        if not items["suspects"] and not items["sections"]:
            print("（沒有待處理的影響項目）")
            return 0
        if items["suspects"]:
            print("可疑標記（看過後以 `docspec impact clear <編號> --reason ...` 清除）：")
            for s in items["suspects"]:
                print(f"- {s['target-label']}：因為「{s['trigger-label']}」變更（{s['id']}）")
        if items["sections"]:
            print("需要重看的文件章節（審閱內容後，把 realizes 改指向接替的決策）：")
            for r in items["sections"]:
                succ = f"，接替者 gov:{r['successor']}" if r.get("successor") else ""
                print(f"- {r['title']}（{r['section']}）：依據的決策 gov:{r['decision']} "
                      f"已{'被取代' if r['status'] == 'superseded' else '撤回'}{succ}")
        return 0
    except gv.GovernanceError as exc:
        return fail(str(exc))
