"""docspec status — 章節架構概觀：每節 有沒檔＋可開寫(ready)＋同步/過期。"""

from __future__ import annotations

import argparse
import json

from dspx.check import run_check, run_file_check
from dspx.commands._shared import BootstrapError, bootstrap, load_engine_schema, load_model
from dspx.layout import Layout
from dspx.model import (
    Leaf,
    ancestor_brief_fingerprint,
    decision_index,
    deps_fingerprint,
    style_fingerprint,
)
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
    """讀 render 記的各節投影源 hash（指紋帳本）。現行存隱藏 sidecar
    `docs/<article>/.sections.yaml`；舊交付物 fallback 讀 `_latest.md` frontmatter（ISSUE-3）。"""
    from dspx.render import read_ledger
    return read_ledger(layout, article)


def develop_only_sections(layout: Layout, leaf_sections: set[str]) -> list[str]:
    """已建 `develop.md` 但尚未結晶成 concept（＝非 leaf）的章節 id；排序、排除封存區。
    `status` 與 `list` 共用此 model-liveness 判準——否則 develop-only 節在 status 可見、
    在 list 卻消失（甚至 list 誤報「Corpus is empty」）。"""
    out: list[str] = []
    if layout.corpus_dir.is_dir():
        for dev in sorted(layout.corpus_dir.rglob("develop.md")):
            if layout.is_archived_path(dev.parent):
                continue                       # 封存區（_archive/）對引擎隱形
            sec = layout.section_id(dev.parent)
            if sec not in leaf_sections:
                out.append(sec)
    return out


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
        rec_style = recorded.get("style") if isinstance(recorded, dict) else None
        own_now = leaf.source_hash()
        anc_now = ancestor_brief_fingerprint(leaf.section, by_section)
        deps_now = deps_fingerprint(leaf, dindex)
        style_now = style_fingerprint(layout)
        if rec_own != own_now:
            sync = "stale-own"          # 自己的源改了 → draft 重渲染
        elif rec_deps is not None and rec_deps != deps_now:
            sync = "stale-upstream"     # realizes 的共享真相改了 → draft 重渲染
        elif rec_anc is not None and rec_anc != anc_now:
            sync = "stale-inherited"    # 只有祖先 brief 改了 → edit 敘事性對齊
        elif rec_style is not None and rec_style != style_now:
            sync = "stale-style"        # 寫作 doctrine（writing-guide/glossary）改了 → edit 就地重套風格/對齊術語
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
    import sys

    parser = argparse.ArgumentParser(prog="docspec status", description=HELP)
    parser.add_argument("article", nargs="?", default=None, help="scope output to this article")
    parser.add_argument("--section", default=None, help="report only this leaf section")
    parser.add_argument("--json", action="store_true", dest="as_json", help="output as JSON")
    args = parser.parse_args(argv)

    try:
        layout, config = bootstrap()
        schema = load_engine_schema(config)
        leaves = load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code

    if args.article:
        known = {lf.article for lf in leaves} | {
            s.split("/", 1)[0]
            for s in develop_only_sections(layout, {lf.section for lf in leaves})}
        if args.article not in known:
            sys.stderr.write(f"docspec: no leaf sections found for article \"{args.article}\"\n")
            return 1

    check_ok = run_check(leaves, schema, layout).ok
    by_section = {lf.section: lf for lf in leaves}   # 全專案，供祖先 brief 查找
    dindex = decision_index(leaves)                  # 全專案決策索引，供 deps 指紋
    shown = [lf for lf in leaves if lf.article == args.article] if args.article else leaves
    if args.section:
        shown = [lf for lf in shown if lf.section == args.section]

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
    for sec in develop_only_sections(layout, leaf_sections):
        if args.article and sec.split("/", 1)[0] != args.article:
            continue
        if args.section and sec != args.section:
            continue
        devdir = layout.section_dir(sec)
        rows.append({
            "section": sec, "state": "developing", "sync": "uncrystallized",
            "files": {"concept": False, "decisions": False,
                      "material": (devdir / "material.md").is_file(),
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
    print("  sync → who picks it up: stale-own / stale-upstream → draft (re-render the section) · "
          "stale-inherited → edit (narrative-align, or render --ack if no change needed) · "
          "stale-style → edit (restyle / terminology-align to the updated writing-guide/glossary, "
          "or render --ack if the prose already conforms) · "
          "unwritten → draft · ✎ drifted → edit (reconcile the hand-edit)")
    return 0
