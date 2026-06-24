"""docspec list — 列出 corpus（文章與末節）。"""

from __future__ import annotations

import argparse
import json

from dspx.check import run_check
from dspx.commands._shared import BootstrapError, bootstrap, load_engine_schema, load_model
from dspx.commands.status import develop_only_sections, section_state

NAME = "list"
HELP = "List the corpus's articles and leaf sections"


def _article_of(section: str) -> str:
    return section.split("/", 1)[0]


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

    # develop-only 節（已建 develop.md、尚未結晶）也要列——與 status 同 model-liveness 判準，
    # 否則它們在 status 可見、在 list 卻消失（甚至誤報「Corpus is empty」）。
    dev_only = develop_only_sections(layout, {lf.section for lf in leaves})

    if args.as_json:
        check_ok = run_check(leaves, schema, layout).ok
        rows = [
            {"section": lf.section, "article": lf.article, "title": lf.title,
             "id": lf.concept_id, "order": lf.order,
             "concept": (lf.concept or {}).get("concept"),     # 一句話索引（廉價，免開檔）
             "status": section_state(lf, schema, check_ok)}    # ready / developing / waiting…
            for lf in leaves
        ] + [
            {"section": sec, "article": _article_of(sec), "title": sec.rsplit("/", 1)[-1],
             "id": None, "order": None, "concept": None, "status": "developing"}
            for sec in dev_only
        ]
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    if not leaves and not dev_only:
        print("Corpus is empty. Use docspec new <section> to create the first section.")
        return 0

    # 合併排序：依 article、再依 section 路徑；develop-only 標 (developing)。
    items = [(lf.article, lf.section, lf.title, False) for lf in leaves]
    items += [(_article_of(sec), sec, sec.rsplit("/", 1)[-1], True) for sec in dev_only]
    items.sort(key=lambda t: (t[0], t[1]))

    current_article = None
    for article, section, title, dev in items:
        if article != current_article:
            current_article = article
            print(f"\n{article}/")
        depth = section.count("/")
        tag = "  (developing — not yet crystallized)" if dev else ""
        print(f"{'  ' * depth}  {section} — {title}{tag}")
    return 0
