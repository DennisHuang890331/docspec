"""docspec status — 章節架構概觀：每節 有沒檔＋可開寫(ready)＋同步/過期。"""

from __future__ import annotations

import argparse
import json

from dspx.check import run_check, run_file_check
from dspx.commands._shared import BootstrapError, bootstrap, load_engine_schema, load_model
from dspx.frontmatter import FrontmatterError, read_frontmatter
from dspx.layout import Layout
from dspx.model import Leaf, ancestor_brief_fingerprint, decision_index, deps_fingerprint
from dspx.schema import Schema

NAME = "status"
HELP = "section structure overview: per section files present / writable / synced or stale"


def section_state(leaf: Leaf, schema: Schema, check_ok: bool) -> str:
    """每節狀態（status 與 list 共用）。
    ready 需「concept+decisions 齊、欄位完整（per-section run_file_check）、全專案 check 綠」；
    develop.md 還在 or 必填未齊 → developing（不擋寫、draft 不選）。"""
    has_concept = (leaf.dir / "concept.yaml").is_file()
    has_decisions = (leaf.dir / "decisions.yaml").is_file()
    if leaf.has_develop:
        return "developing"
    if not has_concept or not has_decisions:
        missing = [n for n, ok in (("concept", has_concept), ("decisions", has_decisions)) if not ok]
        return "waiting(missing:" + ",".join(missing) + ")"
    if run_file_check(leaf, schema):
        return "developing"          # 必填未齊（空/佔位/型別）→ 仍 developing（1.3）
    if not check_ok:
        return "waiting(check red)"
    return "ready"


def _docs_hashes(layout: Layout, article: str) -> dict[str, str]:
    """讀 docs/<article>/_latest.md frontmatter 記錄的各節投影源 hash。"""
    path = layout.docs_latest(article)
    if not path.is_file():
        return {}
    try:
        data, _ = read_frontmatter(path)
    except FrontmatterError:
        return {}
    sections = data.get("sections") or {}
    return dict(sections) if isinstance(sections, dict) else {}


def _leaf_row(layout: Layout, leaf: Leaf, schema: Schema, check_ok: bool,
              docs_hashes: dict, by_section: dict, dindex: dict) -> dict:
    has_concept = (leaf.dir / "concept.yaml").is_file()
    has_decisions = (leaf.dir / "decisions.yaml").is_file()
    recorded = docs_hashes.get(leaf.section)
    if recorded is None:
        sync = "unwritten"
    else:
        # 相容舊格式（str=只有 own）與新格式（{own, anc, deps}）
        rec_own = recorded.get("own") if isinstance(recorded, dict) else recorded
        rec_anc = recorded.get("anc") if isinstance(recorded, dict) else None
        rec_deps = recorded.get("deps") if isinstance(recorded, dict) else None
        own_now = leaf.source_hash()
        anc_now = ancestor_brief_fingerprint(leaf.section, by_section)
        deps_now = deps_fingerprint(leaf, dindex)
        if rec_own != own_now:
            sync = "stale-own"          # 自己的源改了 → draft 重渲染
        elif rec_deps is not None and rec_deps != deps_now:
            sync = "stale-upstream"     # realizes 的共享真相改了 → draft 重渲染
        elif rec_anc is not None and rec_anc != anc_now:
            sync = "stale-inherited"    # 只有祖先 brief 改了 → edit 敘事性對齊
        else:
            sync = "synced"

    state = section_state(leaf, schema, check_ok)

    return {
        "section": leaf.section,
        "state": state,
        "sync": sync,
        "files": {
            "concept": has_concept,
            "decisions": has_decisions,
            "material": leaf.has_material,
            "develop": leaf.has_develop,
            "history": leaf.has_history,
            "draft": recorded is not None,
        },
    }


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec status", description=HELP)
    parser.add_argument("--section", default=None, help="report only this leaf section")
    parser.add_argument("--json", action="store_true", dest="as_json", help="output as JSON")
    args = parser.parse_args(argv)

    try:
        layout, config = bootstrap()
        schema = load_engine_schema(config)
        leaves = load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code

    check_ok = run_check(leaves, schema, layout).ok
    by_section = {lf.section: lf for lf in leaves}   # 全專案，供祖先 brief 查找
    dindex = decision_index(leaves)                  # 全專案決策索引，供 deps 指紋
    shown = [lf for lf in leaves if lf.section == args.section] if args.section else leaves

    from dspx.render import detect_drift
    hashes_by_article: dict[str, dict] = {}
    drift_by_article: dict[str, set] = {}
    rows = []
    for leaf in shown:
        if leaf.article not in hashes_by_article:
            hashes_by_article[leaf.article] = _docs_hashes(layout, leaf.article)
            drift_by_article[leaf.article] = {
                d["section"] for d in detect_drift(layout, leaf.article)}
        row = _leaf_row(layout, leaf, schema, check_ok,
                        hashes_by_article[leaf.article], by_section, dindex)
        row["drifted"] = leaf.section in drift_by_article[leaf.article]
        rows.append(row)

    # develop-only 章節（已建 develop.md、尚未結晶成 concept/decisions）——讓它們可見且不誤報 ready
    leaf_sections = {lf.section for lf in leaves}
    if layout.corpus_dir.is_dir():
        for dev in sorted(layout.corpus_dir.rglob("develop.md")):
            if layout.is_archived_path(dev.parent):
                continue                       # 封存區（_archive/）對引擎隱形
            sec = layout.section_id(dev.parent)
            if sec in leaf_sections:
                continue                       # 已結晶＝leaf，上面已列
            if args.section and sec != args.section:
                continue
            rows.append({
                "section": sec, "state": "developing", "sync": "uncrystallized",
                "files": {"concept": False, "decisions": False,
                          "material": (dev.parent / "material.md").is_file(),
                          "develop": True, "history": False, "draft": False},
                "drifted": False,
            })

    if args.as_json:
        print(json.dumps({"checkOk": check_ok, "sections": rows},
                         ensure_ascii=False, indent=2))
        return 0

    if not rows:
        print("corpus is empty (no leaf sections yet). Use docspec new <section> to create the first one.")
        return 0

    print(f"check: {'green' if check_ok else 'red (run docspec check first)'}  "
          f"{len(rows)} leaf section(s)\n")
    for r in rows:
        f = r["files"]
        flags = "".join([
            "c" if f["concept"] else "-",
            "d" if f["decisions"] else "-",
            "m" if f["material"] else "-",
            "v" if f["develop"] else "-",
            "h" if f["history"] else "-",
        ])
        drift = " ✎hand-edited(docspec diff)" if r.get("drifted") else ""
        print(f"  {r['section']:<28} {r['state']:<16} {r['sync']:<16} [{flags}]{drift}")
    print("\n  flags: c=concept d=decisions m=material v=develop h=history")
    return 0
