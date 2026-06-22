"""docspec check — 硬閘：id 唯一 / 死引用 / 循環。全綠吐 id 索引。"""

from __future__ import annotations

import argparse
import json

from dspx.check import run_check
from dspx.commands._shared import BootstrapError, bootstrap, load_engine_schema, load_model

NAME = "check"
HELP = "structural hard gate: id uniqueness / dead references / cycles (exit 1 on failure)"


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec check", description=HELP)
    parser.add_argument("--json", action="store_true", dest="as_json", help="output as JSON")
    args = parser.parse_args(argv)

    try:
        layout, config = bootstrap()
        schema = load_engine_schema(config)
        leaves = load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code

    result = run_check(leaves, schema, layout)

    if args.as_json:
        print(json.dumps({
            "ok": result.ok,
            "errors": result.errors,
            "index": {
                "ids": {k: {"section": v.section, "kind": v.kind, "status": v.status}
                        for k, v in result.index.ids.items()},
                "sections": result.index.sections,
            },
        }, ensure_ascii=False, indent=2))
        return 0 if result.ok else 1

    if result.ok:
        print(f"check passed: {len(result.index.sections)} leaf sections, {len(result.index.ids)} ids.")
        for the_id, rec in sorted(result.index.ids.items()):
            print(f"  {the_id:<24} {rec.kind:<9} {rec.section}")
        return 0

    print(f"check failed ({len(result.errors)} issue(s)):")
    for err in result.errors:
        print(f"  ✗ {err}")
    return 1
