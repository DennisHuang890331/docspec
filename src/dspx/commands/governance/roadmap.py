"""docspec roadmap [--json] | roadmap done <id> --note "..." — backlog 視圖 ＋ 完成分流。

derive 層（Seam 2）：讀 roadmap.all_entries（統無狀態模型：在檔＝待辦、掉出＝完成）→
算 blocked/unblocked → 按文件（target 的 article ／ forest）分組。

- blocked＝任一 depends-on 的 id **仍在**目前的 entries 集合裡（尚未掉出＝尚未完成）。
- unblocked＝kind=task 且 !blocked（＝現在就能開工的；沒有 status 了，能開工只看依賴）。
- 語義／「該不該做」不判（那是 audit）；這裡只忠實算可開工性與分組。

`done` 子指令＝小工作直接結案（無需開單）：把該 entry 移出 roadmap.yaml、append 一行進
roadmap-archive.yaml（見 dspx.roadmap.mark_done）。晉升為 change 的完成路線不走這裡——
`change archive` 交易會自己 prune 掉 promoted-to entry。
"""

from __future__ import annotations

import argparse
import json
import sys

from dspx import roadmap
from dspx.commands._shared import BootstrapError, bootstrap, load_model

NAME = "roadmap"
HELP = ("Backlog view: planned-but-not-done work (grouped by document, tagged unblocked/blocked); "
        "`roadmap done <id> --note ...` routes small completed work to roadmap-archive.yaml")

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
    """算 backlog view：全部 entry 皆待辦、算 blocked/unblocked、按文件分組。

    回傳 {"groups": {article-or-"forest": [entry,...]}}，
    每個 entry＝原 entry ＋ 衍生欄 {blocked: bool, blocking-deps: [id], unblocked: bool}。
    分組依 stable 出現序；group 內保留載入序。
    """
    entries = roadmap.all_entries(layout, leaves)

    # dep 是否「解除」＝dep id 是否還在目前的 entries 裡；掉出＝完成。
    current_ids = {str(e["id"]) for e in entries if e.get("id")}
    target_article = _target_to_article(leaves)

    groups: dict[str, list[dict]] = {}
    for e in entries:
        deps = e.get("depends-on") or []
        if not isinstance(deps, list):
            deps = [deps]
        blocking = [str(d) for d in deps if str(d) in current_ids]
        blocked = bool(blocking)
        unblocked = (e.get("kind") == "task" and not blocked)

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
    blocked = [e for e in items if e.get("blocked")]
    # 既非 unblocked、非 blocked（如 gap，kind≠task）＝其他待辦。
    accounted = {id(e) for e in unblocked} | {id(e) for e in blocked}
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
    if other:
        print("  Other to-do:")
        for e in other:
            _line(e)


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec roadmap", description=HELP)
    sub = parser.add_subparsers(dest="op")

    p_done = sub.add_parser(
        "done", help="🟢 small direct work, no change needed: move the entry into roadmap-archive.yaml")
    p_done.add_argument("id")
    p_done.add_argument("--note", required=True, help="one-line completion note")

    parser.add_argument("--json", action="store_true", dest="as_json", help="output as JSON (view only)")
    args = parser.parse_args(argv)

    try:
        layout, _config = bootstrap()
        leaves = load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code

    if args.op == "done":
        try:
            record = roadmap.mark_done(layout, leaves, args.id, args.note.strip())
        except roadmap.RoadmapError as exc:
            sys.stderr.write(f"docspec: {exc}\n")
            return 1
        print(f"{record['id']} -> roadmap-archive.yaml ({record['date']}): {record['note']}")
        return 0

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
