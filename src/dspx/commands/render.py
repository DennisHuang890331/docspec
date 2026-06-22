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

    result = render_article(layout, leaves, args.article)
    total = len(result["sections"])
    print(f"synced \"{args.article}\" skeleton -> {result['written_path']}")
    print(f"  {total} section(s), of which {result['drafted']} have prose and "
          f"{total - result['drafted']} are unwritten.")
    return 0
