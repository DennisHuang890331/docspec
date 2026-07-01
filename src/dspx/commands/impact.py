"""docspec impact <id> — 反向視圖：這個 id 在哪定義、被誰 realizes/governed-by。

改共享真相前先看炸到誰；也是 agent 找「誰定義了某概念、能不能引用」的查詢。
"""

from __future__ import annotations

import argparse
import json
import sys

from dspx.commands._shared import BootstrapError, bootstrap, load_model
from dspx.model import ancestor_leaves

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

    # 反向的「過期傳播」閉包：改一個 concept 的 brief/框架不只炸到直接 governed-by 它的節，
    # 還順著治理鏈＋路徑父鏈遞移炸到所有「祖先集含本節」的下游（staleness 用同一 ancestor_leaves
    # 算 stale-inherited）。只報直接邊＝深森林根節點的 blast radius 被低估（Round 9 LOW-2）。
    # 對 decision id 不適用（realizes 是直接、非遞移的指標），故只在 concept 時算。
    governed_transitive: list = []
    if defined_at is not None and kind == "concept":
        by_section = {lf.section: lf for lf in leaves}
        concept_by_id = {lf.concept["id"]: lf for lf in leaves
                         if lf.concept and lf.concept.get("id")}
        direct = set(governed_by)
        for lf in leaves:
            if lf.section == defined_at or lf.section in direct:
                continue
            ancs = ancestor_leaves(lf.section, by_section, concept_by_id)
            if any(a.section == defined_at for a, _is_gov in ancs):
                governed_transitive.append(lf.section)

    return {
        "id": the_id, "definedAt": defined_at, "kind": kind,
        "realizedBy": sorted(realized_by),
        "governedBy": sorted(governed_by),
        "governedTransitive": sorted(governed_transitive),
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
    n = len(info["realizedBy"]) + len(info["governedBy"]) + len(info["governedTransitive"])
    print(f"\nBlast radius: {n} section(s) depend on it" + (" (changing it means redoing these)" if n else " (nothing depends on it)"))
    for s in info["realizedBy"]:
        print(f"  realizes ← {s}")
    for s in info["governedBy"]:
        print(f"  governed-by ← {s}")
    for s in info["governedTransitive"]:
        print(f"  inherited (transitive) ← {s}")
    return 0
