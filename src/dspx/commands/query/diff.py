"""docspec diff <article> — 偵測交付物被手改（散文偷跑離開源料）。

確定性偵測：哪幾節的散文跟上次 render 記的 prose 指紋不符＝被手改過。
引擎只報「被改了」，不判斷改得對不對——收回源料是 agent 的判斷（見 develop skill）。
"""

from __future__ import annotations

import argparse
import json

from dspx.commands._shared import BootstrapError, bootstrap, load_engine_schema, load_model
from dspx.engine.render import detect_drift

NAME = "diff"
HELP = "detect hand-edits to the deliverable (_latest prose != last render fingerprint)"


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec diff", description=HELP)
    parser.add_argument("article", nargs="?", default=None, help="article name (omit = all)")
    parser.add_argument("--json", action="store_true", dest="as_json", help="output as JSON")
    args = parser.parse_args(argv)

    try:
        layout, config = bootstrap()
        load_engine_schema(config)
        leaves = load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code

    articles = [args.article] if args.article else sorted({lf.article for lf in leaves})
    drift = []
    for art in articles:
        for d in detect_drift(layout, art):
            drift.append({"article": art, **d})

    if args.as_json:
        print(json.dumps({"drift": drift}, ensure_ascii=False, indent=2))
        return 0

    if not drift:
        print("diff: deliverable matches source (no hand-edit drift detected).")
        return 0

    print(f"diff: {len(drift)} section(s) drifted — deliverable prose departed from source:")
    for d in drift:
        print(f"  ✎ {d['section']}")
    print("\n→ factcheck classifies each drift and routes the fix (it does not rewrite prose):")
    print("  · cosmetic (wording only) → accept; re-run `docspec render` to set the new baseline.")
    print("  · content/style (touches the idea or convention) → fix concept/decisions upstream,")
    print("    then re-render. factcheck flags; develop/edit fix.")
    return 0
