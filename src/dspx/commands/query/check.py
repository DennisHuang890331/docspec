"""docspec check — 硬閘：id 唯一 / 死引用 / 循環。全綠吐 id 索引。

article 引數只縮**綠路的索引輸出**（74 leaf/224 id 森林的 dump 之痛）；
check 本體永遠驗整個專案——errors/warnings/exit code 不受 scope 影響
（check 錯誤是無結構歸屬的純字串，per-article 藏任何一條＝false-green 向量）。
"""

from __future__ import annotations

import argparse
import json
import sys

from dspx.check import run_check
from dspx.commands._shared import BootstrapError, bootstrap, load_engine_schema, load_model

NAME = "check"
HELP = "structural hard gate: id uniqueness / dead references / cycles (exit 1 on failure)"


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec check", description=HELP)
    parser.add_argument("article", nargs="?", default=None,
                        help="scope the green-path index listing to this article "
                             "(check itself always validates the whole project)")
    parser.add_argument("--json", action="store_true", dest="as_json", help="output as JSON")
    args = parser.parse_args(argv)

    try:
        layout, config = bootstrap()
        schema = load_engine_schema(config)
        leaves = load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code

    if args.article:
        known = {lf.article for lf in leaves}
        if args.article not in known:
            sys.stderr.write(f"docspec: no leaf sections found for article \"{args.article}\"\n")
            return 1

    result = run_check(leaves, schema, layout)

    def _in_scope(section: str) -> bool:
        if not args.article:
            return True
        return section == args.article or section.startswith(f"{args.article}/")

    if args.as_json:
        payload = {
            "ok": result.ok,
            "errors": result.errors,
            "warnings": result.warnings,
            "index": {
                "ids": {k: {"section": v.section, "kind": v.kind, "status": v.status}
                        for k, v in result.index.ids.items() if _in_scope(v.section)},
                "sections": [s for s in result.index.sections if _in_scope(s)],
            },
        }
        if args.article:
            payload["scope"] = args.article
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if result.ok else 1

    def _print_warnings() -> None:
        if result.warnings:
            print(f"warnings ({len(result.warnings)}, non-blocking):")
            for w in result.warnings:
                print(f"  ⚠ {w}")

    if result.ok:
        scoped_sections = [s for s in result.index.sections if _in_scope(s)]
        scoped_ids = {k: v for k, v in result.index.ids.items() if _in_scope(v.section)}
        print(f"check passed: {len(scoped_sections)} leaf sections, {len(scoped_ids)} ids.")
        if args.article:
            print(f"(index scoped to \"{args.article}\"; check itself always validates the whole project)")
        for the_id, rec in sorted(scoped_ids.items()):
            print(f"  {the_id:<24} {rec.kind:<9} {rec.section}")
        _print_warnings()
        return 0

    print(f"check failed ({len(result.errors)} issue(s)):")
    for err in result.errors:
        print(f"  ✗ {err}")
    _print_warnings()
    return 1
