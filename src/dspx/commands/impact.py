"""docspec impact <id> — 反向視圖：這個 id 在哪定義、被誰 realizes/governed-by。

改共享真相前先看炸到誰；也是 agent 找「誰定義了某概念、能不能引用」的查詢。
"""

from __future__ import annotations

import argparse
import json
import sys

from dspx.commands._shared import BootstrapError, bootstrap, load_model

NAME = "impact"
HELP = "Reverse view: where an id is defined and which sections realize/govern-by it (check the blast radius before changing it)"


def _analyze(leaves: list, the_id: str) -> dict:
    defined_at = None
    kind = None
    for leaf in leaves:
        c = leaf.concept or {}
        if c.get("id") == the_id:
            defined_at, kind = leaf.section, "concept"
        for e in leaf.decisions:
            if e.get("id") == the_id:
                defined_at, kind = leaf.section, f"decision({e.get('status')})"
        for e in leaf.history:
            if e.get("id") == the_id:
                defined_at, kind = leaf.section, "history(retired)"

    realized_by, governed_by = [], []
    for leaf in leaves:
        c = leaf.concept or {}
        if the_id in (c.get("realizes") or []):
            realized_by.append(leaf.section)
        if str(the_id) in [str(x) for x in (c.get("governed-by") or [])]:
            governed_by.append(leaf.section)
    return {
        "id": the_id, "definedAt": defined_at, "kind": kind,
        "realizedBy": sorted(realized_by),
        "governedBy": sorted(governed_by),
    }


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec impact", description=HELP)
    parser.add_argument("id", help="id of the decision/concept")
    parser.add_argument("--json", action="store_true", dest="as_json", help="output as JSON")
    args = parser.parse_args(argv)

    try:
        layout, _config = bootstrap()
        leaves = load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code

    info = _analyze(leaves, args.id)
    if args.as_json:
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return 0

    if info["definedAt"] is None:
        print(f"impact: id \"{args.id}\" not found (undefined).")
        return 1

    print(f"id: {args.id}")
    if info["definedAt"]:
        print(f"  defined at: {info['definedAt']} ({info['kind']})")
    n = len(info["realizedBy"]) + len(info["governedBy"])
    print(f"\nBlast radius: {n} section(s) depend on it" + (" (changing it means redoing these)" if n else " (nothing depends on it)"))
    for s in info["realizedBy"]:
        print(f"  realizes ← {s}")
    for s in info["governedBy"]:
        print(f"  governed-by ← {s}")
    return 0
