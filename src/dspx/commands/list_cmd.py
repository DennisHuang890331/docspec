"""docspec list — 列出 corpus（文章、末節、分組節點）。"""

from __future__ import annotations

import argparse
import json
import sys

from dspx.check import run_check
from dspx.commands._shared import BootstrapError, bootstrap, load_engine_schema, load_model
from dspx.commands.status import develop_only_sections, section_state

NAME = "list"
HELP = "List the corpus's articles, leaf sections, and group nodes"


def _article_of(section: str) -> str:
    return section.split("/", 1)[0]


def _group_nodes(leaves: list) -> list[str]:
    """分組節點集合＝render 產 group marker 的同一套推導（path prefixes parts[:i]，
    i in range(2, len(parts))、本身非 leaf 節）；跨 leaf 去重、保排序。"""
    leaf_sections = {lf.section for lf in leaves}
    out: list[str] = []
    seen: set[str] = set()
    for lf in leaves:
        parts = [p for p in lf.section.split("/") if p]
        for i in range(2, len(parts)):
            gs = "/".join(parts[:i])
            if gs in seen or gs in leaf_sections:
                continue
            seen.add(gs)
            out.append(gs)
    return out


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec list", description=HELP)
    parser.add_argument("article", nargs="?", default=None, help="scope output to this article")
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
    all_leaves = leaves          # check/section_state 跑全專案（scoping 只濾輸出列）

    if args.article:
        known = {lf.article for lf in leaves} | {_article_of(s) for s in dev_only}
        if args.article not in known:
            sys.stderr.write(f"docspec: no leaf sections found for article \"{args.article}\"\n")
            return 1
        leaves = [lf for lf in leaves if lf.article == args.article]
        dev_only = [s for s in dev_only if _article_of(s) == args.article]

    from dspx.render import _group_order, _group_title
    groups = _group_nodes(leaves)

    if args.as_json:
        check_ok = run_check(all_leaves, schema, layout).ok
        rows = [
            {"section": lf.section, "article": lf.article, "title": lf.title,
             "id": lf.concept_id, "order": lf.order,
             "concept": (lf.concept or {}).get("concept"),     # 一句話索引（廉價，免開檔）
             "status": section_state(lf, schema, check_ok),    # ready / developing / waiting…
             "kind": "leaf"}
            for lf in leaves
        ] + [
            {"section": sec, "article": _article_of(sec), "title": sec.rsplit("/", 1)[-1],
             "id": None, "order": None, "concept": None, "status": "developing",
             "kind": "develop-only"}
            for sec in dev_only
        ] + [
            {"section": gs, "article": _article_of(gs),
             "title": _group_title(layout, gs, gs.rsplit("/", 1)[-1]),
             "id": None, "order": _group_order(layout, gs),
             "concept": None, "status": None, "kind": "group"}
            for gs in groups
        ]
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    if not leaves and not dev_only:
        print("Corpus is empty. Use docspec new <section> to create the first section.")
        return 0

    # 合併排序：依 article、再依 section 路徑；develop-only 標 (developing)；group 標 [group]。
    items = [(lf.article, lf.section, lf.title, "leaf") for lf in leaves]
    items += [(_article_of(sec), sec, sec.rsplit("/", 1)[-1], "develop-only") for sec in dev_only]
    items += [(_article_of(gs), gs, _group_title(layout, gs, gs.rsplit("/", 1)[-1]), "group")
              for gs in groups]
    items.sort(key=lambda t: (t[0], t[1]))

    current_article = None
    for article, section, title, kind in items:
        if article != current_article:
            current_article = article
            print(f"\n{article}/")
        depth = section.count("/")
        if kind == "group":
            print(f"{'  ' * depth}  [group] {section}/ — {title}")
            continue
        tag = "  (developing — not yet crystallized)" if kind == "develop-only" else ""
        print(f"{'  ' * depth}  {section} — {title}{tag}")
    return 0
