"""docspec list — 列出 corpus（文章與末節）。"""

from __future__ import annotations

import argparse
import json

from dspx.check import run_check
from dspx.commands._shared import BootstrapError, bootstrap, load_engine_schema, load_model
from dspx.commands.status import section_state

NAME = "list"
HELP = "List the corpus's articles and leaf sections"


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec list", description=HELP)
    parser.add_argument("--json", action="store_true", dest="as_json", help="output as JSON")
    args = parser.parse_args(argv)

    try:
        layout, config = bootstrap()
        leaves = load_model(layout)
        schema = load_engine_schema(config)
    except BootstrapError as exc:
        return exc.exit_code

    if args.as_json:
        check_ok = run_check(leaves, schema, layout).ok
        print(json.dumps([
            {"section": lf.section, "article": lf.article, "title": lf.title,
             "id": lf.concept_id, "order": lf.order,
             "concept": (lf.concept or {}).get("concept"),     # 一句話索引（廉價，免開檔）
             "status": section_state(lf, schema, check_ok)}    # ready / developing / waiting…
            for lf in leaves
        ], ensure_ascii=False, indent=2))
        return 0

    if not leaves:
        print("Corpus is empty. Use docspec new <section> to create the first section.")
        return 0

    current_article = None
    for lf in leaves:
        if lf.article != current_article:
            current_article = lf.article
            print(f"\n{current_article}/")
        depth = lf.section.count("/")
        print(f"{'  ' * depth}  {lf.section} — {lf.title}")
    return 0
