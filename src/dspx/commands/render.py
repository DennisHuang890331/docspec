"""docspec render <article> — 確定性把末節散文骨架同步進 docs/<article>/_latest.md。"""

from __future__ import annotations

import argparse
import sys

from dspx.commands._shared import BootstrapError, bootstrap, load_engine_schema, load_model
from dspx.render import render_article

NAME = "render"
HELP = "sync leaf section prose skeleton into docs/<article>/_latest.md (deterministic, preserves written prose)"


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec render", description=HELP)
    parser.add_argument("article", help="name of the article to assemble")
    parser.add_argument(
        "--ack", action="append", default=[], metavar="SECTION", dest="ack",
        help="acknowledge a stale-inherited / stale-style SECTION as aligned (prose needs no "
             "change — already matches the moved ancestor brief or the updated writing-guide/"
             "glossary) and re-stamp its ancestor + style fingerprints; refused if the section is "
             "actually stale-own/upstream (rewrite its prose instead). Repeatable.")
    args = parser.parse_args(argv)

    try:
        layout, config = bootstrap()
        load_engine_schema(config)
        leaves = load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code

    if not any(lf.article == args.article for lf in leaves):
        sys.stderr.write(f"docspec: no leaf sections found for article \"{args.article}\"\n")
        return 1

    result = render_article(layout, leaves, args.article, ack_sections=set(args.ack))
    total = len(result["sections"])
    print(f"synced \"{args.article}\" skeleton -> {result['written_path']}")
    print(f"  {total} section(s), of which {result['drafted']} have prose and "
          f"{total - result['drafted']} are unwritten.")
    if result.get("acked"):
        print(f"  acknowledged (re-stamped, stale-inherited/stale-style cleared): {', '.join(result['acked'])}")
        # 非阻塞提醒：ack 清掉的是「祖先動了」的信號，但子節自己的 brief/concept 框架/圖
        # 是否仍與上游一致＝語義、staleness 照不到（revision-coherence-probes）。導向覆檢、非 gate。
        print("  ↳ also re-check these sections' own brief / concept framing / figures are still "
              "consistent with the moved ancestor (the ledger can't see that — factcheck owns it).")
    if result.get("ack_refused"):
        sys.stderr.write(
            "docspec: ⚠ --ack refused for (these are stale-own/upstream — rewrite the prose, "
            f"don't acknowledge): {', '.join(result['ack_refused'])}\n")
    return 0
