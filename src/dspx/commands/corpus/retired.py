"""docspec retired [<prefix>] — 列出/查詢已退場的章節。

掃封存區 corpus/_archive/*/history.yaml 的 `retired:` 區塊（只有退場根節有），
回報一句話＋原本路徑＋封存位置。給 prefix 只列原本路徑以此開頭的（如 `docspec retired zenoh`）。
"""

from __future__ import annotations

import argparse
import json

import yaml

from dspx.commands._shared import BootstrapError, bootstrap

NAME = "retired"
HELP = "list retired sections (one-liner + original path + archive location)"


def _scan_sections(layout) -> list[dict]:
    """封存區整節退場（_archive/*/history.yaml 的 kind:section entry）＋驗 archive link。"""
    root = layout.corpus_archive_dir
    out: list[dict] = []
    if not root.is_dir():
        return out
    for hist in sorted(root.rglob("history.yaml")):
        try:
            data = yaml.safe_load(hist.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        entries = (data.get("entries") or []) if isinstance(data, dict) else []
        for e in entries:
            if not isinstance(e, dict) or e.get("kind") != "section":
                continue
            archive_rel = (e.get("archive")
                           or hist.parent.relative_to(layout.planning_home).as_posix())
            out.append({
                "id": e.get("id"),
                "section": hist.parent.name.replace("__", "/"),   # 原路徑（從封存資料夾名還原）
                "note": e.get("statement", ""),
                "in": e.get("retired-in"),
                "archive": archive_rel,
                "archiveExists": (layout.planning_home / archive_rel).is_dir(),  # 驗 link
            })
    return out


def _scan_decisions(layout) -> list[dict]:
    """活節 history.yaml 的 entries＝per-decision 退場（不在 _archive，引擎可見）。"""
    from dspx.engine.model import load_project
    out: list[dict] = []
    try:
        leaves = load_project(layout)
    except Exception:
        return out
    for leaf in leaves:
        for e in leaf.history:
            if not e.get("id") or e.get("kind") == "section":   # section 退場走 _scan_sections
                continue
            out.append({
                "id": str(e.get("id")), "section": leaf.section,
                "status": e.get("status"), "statement": e.get("statement"),
                "retiredIn": e.get("retired-in"),
            })
    return out


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec retired", description=HELP)
    parser.add_argument("prefix", nargs="?", default=None,
                        help="only list retired items whose original path/section starts with this")
    parser.add_argument("--json", action="store_true", dest="as_json", help="output as JSON")
    args = parser.parse_args(argv)

    try:
        layout, _config = bootstrap()
    except BootstrapError as exc:
        return exc.exit_code

    sections = _scan_sections(layout)
    decisions = _scan_decisions(layout)
    if args.prefix:
        p = args.prefix.strip("/")
        sections = [it for it in sections if str(it["section"]).startswith(p)]
        decisions = [it for it in decisions if str(it["section"]).startswith(p)]

    if args.as_json:
        print(json.dumps({"retired": sections, "retiredDecisions": decisions},
                         ensure_ascii=False, indent=2))
        return 0

    if not sections and not decisions:
        print("(no retired sections or decisions)")
        return 0
    if sections:
        print(f"retired sections ({len(sections)}):\n")
        for it in sections:
            tag = f" (retired in {it['in']})" if it.get("in") else ""
            warn = "" if it["archiveExists"] else "  ⚠️ archive folder does not exist!"
            print(f"  {it['section']}{tag}")
            print(f"    {it['note']}")
            print(f"    archive (link): {it['archive']}{warn}")
    if decisions:
        print(f"\nretired decisions ({len(decisions)}):\n")
        for it in decisions:
            tag = f" (retired in {it['retiredIn']})" if it.get("retiredIn") else ""
            print(f"  {it['id']} @ {it['section']}{tag}　{it.get('statement') or ''}")
    return 0
