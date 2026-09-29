"""docspec trace <id> — 追溯查詢：一筆治理紀錄（或 `doc:<章節>`）的上游與下游。

上游＝它依據／回答／取代了誰；下游＝誰依據／回答／取代／實現了它。追溯圖每次執行時重建。
"""

from __future__ import annotations

import argparse

from dspx.commands._shared import BootstrapError, load_model
from dspx.commands.governance._gov_common import emit_json, fail, label, open_layout
from dspx.engine import governance as gv
from dspx.engine.impact import DOC_NS, build_graph

NAME = "trace"
HELP = "governance: upstream and downstream links of a record (ruling, decision, question, doc:<section>)"

_UP = {"answers": "回答", "based-on": "依據", "supersedes": "取代", "realizes": "實現",
       "refs": "指向", "depends-on": "前置"}


def run(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="docspec trace", description=HELP)
    p.add_argument("id", help="a governance id (e.g. D-claude-13) or doc:<section path>")
    p.add_argument("--json", dest="as_json", action="store_true")
    args = p.parse_args(argv)
    layout = open_layout()
    if layout is None:
        return 1
    try:
        leaves = load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code
    try:
        gov = gv.load_governance(layout)
        graph = build_graph(layout, leaves, gov)
        ref = args.id if args.id.startswith(DOC_NS) else gv.strip_ns(args.id)
        by_id = gov.by_id()
        titles = {DOC_NS + lf.section: lf.title for lf in leaves}
        if ref not in by_id and ref not in titles:
            return fail(f"unknown record \"{args.id}\"")

        def name(r: str) -> str:
            if r in by_id:
                return label(by_id[r])
            return f"{titles.get(r, r)}（{r}）"

        up = [{"ref": d, "type": t} for d, t in graph.upstream(ref)]
        down = [{"ref": s, "type": t} for s, t in graph.dependents(ref)]
        if args.as_json:
            emit_json({"id": ref, "upstream": up, "downstream": down})
            return 0
        print(name(ref))
        print("上游：" if up else "上游：（無）")
        for e in up:
            print(f"  {_UP[e['type']]} → {name(e['ref'])}")
        print("下游：" if down else "下游：（無）")
        for e in down:
            print(f"  {name(e['ref'])} {_UP[e['type']]}它")
        return 0
    except gv.GovernanceError as exc:
        return fail(str(exc))
