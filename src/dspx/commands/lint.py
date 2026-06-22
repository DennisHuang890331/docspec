"""docspec lint — 交付物潔淨度報告（單跑不擋；publish 時 ERROR 級當閘）。"""

from __future__ import annotations

import argparse
import json

from dspx.commands._shared import BootstrapError, bootstrap, load_engine_schema, load_model
from dspx.lint import ERROR, run_lint

NAME = "lint"
HELP = "deliverable cleanliness (leaked ids/anchors/scaffolding/[TBD], material chunking)"


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec lint", description=HELP)
    parser.add_argument("--json", action="store_true", dest="as_json", help="output as JSON")
    args = parser.parse_args(argv)

    try:
        layout, config = bootstrap()
        schema = load_engine_schema(config)
        leaves = load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code

    findings = run_lint(layout, leaves, schema)
    errors = [f for f in findings if f.level == ERROR]

    if args.as_json:
        print(json.dumps({
            "errorCount": len(errors),
            "findings": [{"rule": f.rule, "level": f.level, "where": f.where,
                          "detail": f.detail} for f in findings],
        }, ensure_ascii=False, indent=2))
        return 0

    if not findings:
        print("lint: clean (no issues).")
        return 0
    print(f"lint: {len(findings)} issue(s) (ERROR {len(errors)})")
    for f in findings:
        mark = "✗" if f.level == ERROR else "⚠"
        print(f"  {mark} [{f.rule} {f.level}] {f.where}: {f.detail}")
    return 0
