"""artispec diff <article> — 偵測交付物被手改（散文偷跑離開源料）。

確定性偵測：哪幾節的散文跟上次 render 記的 prose 指紋不符＝被手改過。
引擎只報「被改了」，不判斷改得對不對——收回源料是 agent 的判斷（見 develop skill）。
"""

from __future__ import annotations

import argparse
import json
import sys

from dspx.commands._shared import BootstrapError, bootstrap, load_engine_schema
from dspx.engine.render import detect_drift
from dspx.engine.document_context import add_context_arguments, load_context
from dspx.engine.model import ModelError

NAME = "diff"
HELP = "detect hand-edits to the deliverable (_latest prose != last render fingerprint)"


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="artispec diff", description=HELP)
    parser.add_argument("article", nargs="?", default=None, help="article name (omit = all)")
    parser.add_argument("--json", action="store_true", dest="as_json", help="output as JSON")
    add_context_arguments(parser)
    args = parser.parse_args(argv)

    try:
        layout, config = bootstrap()
        context = load_context(layout, config, args.change)
        layout, config, leaves = context.layout, context.config, context.leaves
        load_engine_schema(config)
    except BootstrapError as exc:
        return exc.exit_code
    except (ModelError, OSError, ValueError) as exc:
        sys.stderr.write(f"artispec diff: {exc}\n")
        return 1

    articles = [args.article] if args.article else sorted({lf.article for lf in leaves})
    if args.article and args.article not in context.articles:
        sys.stderr.write(f'artispec diff: no article "{args.article}" in the selected sources\n')
        return 1
    try:
        diagnostics = context.preview_diagnostics(articles)
        unavailable = {diagnostic["article"] for diagnostic in diagnostics}
        drift = []
        for art in articles:
            if art in unavailable:
                continue
            for d in detect_drift(layout, art):
                drift.append({"article": art, **d})
    except (ModelError, OSError, ValueError) as exc:
        sys.stderr.write(f"artispec diff: {exc}\n")
        return 1

    if args.as_json:
        print(json.dumps({"drift": drift, **context.metadata(diagnostics)}, ensure_ascii=False, indent=2))
        return 1 if diagnostics else 0

    context.print_context(diagnostics)
    if diagnostics and not drift:
        print("diff: prose review is incomplete; resolve the preview diagnostics above.")
        return 1

    if not drift:
        print("diff: deliverable matches source (no hand-edit drift detected).")
        return 0

    print(f"diff: {len(drift)} section(s) drifted — deliverable prose departed from source:")
    for d in drift:
        print(f"  ✎ {d['section']}")
    print("\n→ factcheck classifies each drift and routes the fix (it does not rewrite prose):")
    selector = f" --change {context.change.id}" if context.change else ""
    print(f"  · cosmetic (wording only) → accept; re-run `artispec render <article>{selector}` to set the new baseline.")
    print("  · content/style (touches the idea or convention) → fix concept/decisions upstream,")
    print("    then re-render. factcheck flags; develop/edit fix.")
    return 1 if diagnostics else 0
