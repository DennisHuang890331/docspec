"""docspec roadmap [--json] — backlog 視圖（計劃了、還沒做）。

derive 層（Seam 2）：讀 roadmap.all_entries → 掉 done/dropped（backlog＝未做的工作）→
算 blocked/unblocked → 按文件（target 的 article ／ forest）分組。

- blocked＝任一 depends-on 的 entry 還沒 done（dep id 在「全部 entry」內解析，含 done）。
- unblocked＝kind=task 且 status=open 且 !blocked（＝現在就能開工的）。
- 語義／「該不該做」不判（那是 audit）；這裡只忠實算可開工性與分組。
"""

from __future__ import annotations

import argparse
import json

from dspx import roadmap
from dspx.commands._shared import BootstrapError, bootstrap, load_model

NAME = "roadmap"
HELP = "Backlog view: planned-but-not-done work (grouped by document, tagged unblocked/blocked/doing)"

FOREST_GROUP = "forest"


def _target_to_article(leaves: list) -> dict:
    """section id（concept id ∪ section 路徑）→ 文件名。供 target 分組解析。"""
    index: dict[str, str] = {}
    for leaf in leaves:
        index[leaf.section] = leaf.article
        if leaf.concept_id:
            index[str(leaf.concept_id)] = leaf.article
    return index


def build_backlog_view(layout, leaves: list) -> dict:
    """算 backlog view：掉 done/dropped、算 blocked/unblocked、按文件分組。

    回傳 {"groups": {article-or-"forest": [entry,...]}}，
    每個 entry＝原 entry ＋ 衍生欄 {blocked: bool, blocking-deps: [open dep id], unblocked: bool}。
    分組依 stable 出現序；group 內保留載入序。
    """
    entries = roadmap.all_entries(layout, leaves)

    # dep 狀態在「全部 entry」內解析（含 done）——dep 指向 done 才算解除。
    status_by_id = {str(e["id"]): e.get("status") for e in entries if e.get("id")}
    target_article = _target_to_article(leaves)

    groups: dict[str, list[dict]] = {}
    for e in entries:
        if e.get("status") in ("done", "dropped"):
            continue  # backlog＝未做的工作；done/dropped 掉出

        deps = e.get("depends-on") or []
        if not isinstance(deps, list):
            deps = [deps]
        blocking = [str(d) for d in deps if status_by_id.get(str(d)) != "done"]
        blocked = bool(blocking)
        unblocked = (e.get("kind") == "task" and e.get("status") == "open"
                     and not blocked)

        target = e.get("target")
        if target == roadmap.FOREST_TARGET:
            group = FOREST_GROUP
        else:
            group = target_article.get(str(target)) if target is not None else None
            if group is None:
                # target 死引用會在 check 硬擋；derive 仍容錯歸到 forest 桶以免漏顯。
                group = FOREST_GROUP

        view_entry = dict(e)
        view_entry["blocked"] = blocked
        view_entry["blocking-deps"] = blocking
        view_entry["unblocked"] = unblocked
        groups.setdefault(group, []).append(view_entry)

    return {"groups": groups}


def _print_group(title: str, items: list[dict]) -> None:
    unblocked = [e for e in items if e.get("unblocked")]
    doing = [e for e in items if e.get("status") == "doing"]
    blocked = [e for e in items if e.get("blocked") and e.get("status") != "doing"]
    # 既非 unblocked、非 doing、非 blocked（如 status=open 的 gap）＝其他待辦。
    accounted = {id(e) for e in unblocked} | {id(e) for e in doing} | {id(e) for e in blocked}
    other = [e for e in items if id(e) not in accounted]

    print(f"\n{title}/")

    def _line(e: dict, suffix: str = "") -> None:
        print(f"  [{e.get('kind')}] {e.get('id')}  {e.get('title') or ''}{suffix}")

    if unblocked:
        print("  Ready to start (unblocked):")
        for e in unblocked:
            _line(e)
    if blocked:
        print("  Blocked (blocked-by):")
        for e in blocked:
            deps = ", ".join(e.get("blocking-deps") or [])
            _line(e, f"  ← waiting on: {deps}")
    if doing:
        print("  In progress (doing):")
        for e in doing:
            _line(e)
    if other:
        print("  Other to-do:")
        for e in other:
            _line(e, f"  ({e.get('status')})")


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec roadmap", description=HELP)
    parser.add_argument("--json", action="store_true", dest="as_json", help="output as JSON")
    args = parser.parse_args(argv)

    try:
        layout, _config = bootstrap()
        leaves = load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code

    view = build_backlog_view(layout, leaves)
    groups = view["groups"]

    if args.as_json:
        print(json.dumps(view, ensure_ascii=False, indent=2))
        return 0

    if not groups:
        print("(nothing to do)")
        return 0

    # forest 桶置頂（跨文件工作先看），其餘按文件名排序。
    ordered = ([FOREST_GROUP] if FOREST_GROUP in groups else []) + \
        sorted(g for g in groups if g != FOREST_GROUP)
    for g in ordered:
        _print_group(g, groups[g])
    return 0
