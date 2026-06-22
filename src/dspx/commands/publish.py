"""docspec publish <article> — 唯一不可逆指令：閘→render→蓋版→凍結唯讀「乾淨」快照。

★薄引擎鐵律：引擎不寫一個字。散文由 draft/edit（agent）寫進 docs/<article>/_latest.md；
publish 只做確定性的事：
  1. 閘：check + lint（無 ERROR）
  2. render：同步骨架、記各節源 hash（staleness）
  3. 凍結：把 _latest 複製成唯讀快照 vN，並**完全剝除隱形章節標記**（快照零機械痕跡）
"""

from __future__ import annotations

import argparse
import stat
import sys
from datetime import date

from dspx.check import run_check
from dspx.commands._shared import BootstrapError, bootstrap, load_engine_schema, load_model
from dspx.frontmatter import parse_frontmatter, render_frontmatter
from dspx.layout import Layout, next_version
from dspx.lint import ERROR, run_lint
from dspx.render import render_article, strip_markers

NAME = "publish"
HELP = "the only irreversible command: check+lint green -> render -> freeze a read-only, marker-stripped snapshot"

# changelog markdown 表頭（publish 機械寫；列只摘要、不抄細節）。
_CHANGELOG_HEADER = "| 版本 | 日期 | 級別 | 說明 |\n|---|---|---|---|\n"


def _next_version(layout: Layout, article: str, level: str) -> str:
    versions = layout.existing_versions(article)
    prev = max(versions) if versions else None
    return next_version(prev, level)


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec publish", description=HELP)
    parser.add_argument("article", help="name of the article to publish")
    parser.add_argument(
        "--level", choices=["major", "minor", "patch"], default="patch",
        help="semver bump level (+1 from previous version; no previous -> 1.0.0). Defaults to patch.",
    )
    parser.add_argument("--note", default="", help="one-line changelog summary (lean, no details)")
    args = parser.parse_args(argv)

    try:
        layout, config = bootstrap()
        schema = load_engine_schema(config)
        leaves = load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code

    if not any(lf.article == args.article for lf in leaves):
        sys.stderr.write(f"docspec: no leaf sections found for article \"{args.article}\"\n")
        return 1

    # ── 閘 ──
    check = run_check(leaves, schema, layout)
    if not check.ok:
        sys.stderr.write("docspec: publish aborted -- check did not pass:\n")
        for e in check.errors:
            sys.stderr.write(f"  ✗ {e}\n")
        return 1
    lint_errors = [f for f in run_lint(layout, leaves, schema) if f.level == ERROR]
    if lint_errors:
        sys.stderr.write("docspec: publish aborted -- lint has ERROR(s):\n")
        for f in lint_errors:
            sys.stderr.write(f"  ✗ [{f.rule}] {f.where}: {f.detail}\n")
        return 1

    # ── 開啟中 audit findings：非阻塞提醒（audit 永不擋 publish）──
    open_findings = _count_open_findings(layout, leaves, args.article)
    if open_findings:
        sys.stderr.write(
            f"docspec: ⚠ article \"{args.article}\" still has {open_findings} unresolved audit finding(s)"
            f" (audit is non-blocking, publish proceeds; to view: docspec audit --open --article {args.article})\n"
        )

    # ── render：同步骨架 + 記源 hash ──
    result = render_article(layout, leaves, args.article)
    if result["drafted"] == 0:
        sys.stderr.write(
            f"docspec: article \"{args.article}\" has no written sections yet (draft has not produced prose) -- not publishing.\n"
        )
        return 1

    latest = layout.docs_latest(args.article)
    version = _next_version(layout, args.article, args.level)

    # ── 蓋版號到 _latest（保留標記，它是工作副本）──
    meta, body = parse_frontmatter(latest.read_text(encoding="utf-8"))
    meta["version"] = version
    latest.write_text(render_frontmatter(meta, body), encoding="utf-8")

    # ── 凍結快照：完全剝除隱形標記 ──
    # 快照＝純內容：剝隱形標記 ＋ **不寫 frontmatter**（機器簿記不進凍結交付物；
    # 版號在檔名、紀錄在 changelog）。讀者開檔只看到散文。
    clean_body = strip_markers(body).strip() + "\n"
    snapshot = layout.docs_snapshot(args.article, version)
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text(clean_body, encoding="utf-8")
    # 凍結區 hash 抓包（主保證，跨工具、Drive 有效）＋ OS 唯讀（加分，Drive 可能失效）
    from dspx import freeze
    freeze.record(layout.planning_home, layout.project_root, snapshot)
    frozen = True
    try:
        snapshot.chmod(stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    except OSError:
        frozen = False

    # ── changelog：機械寫一列精瘦 markdown 表（版本/日期/級別/說明）──
    # 列只摘要：細節＝快照間 diff（可 derive）＋ decisions/history，不抄進 changelog
    # （避台中港式說明列爆炸）。
    changelog = layout.docs_changelog(args.article)
    changelog.parent.mkdir(parents=True, exist_ok=True)
    if not changelog.is_file():
        changelog.write_text(
            f"# {args.article} — revision history\n\n{_CHANGELOG_HEADER}", encoding="utf-8")
    elif _CHANGELOG_HEADER not in changelog.read_text(encoding="utf-8"):
        # 既有檔但無表頭（如舊格式）→ 補表頭，新列接在後面。
        with changelog.open("a", encoding="utf-8") as fh:
            fh.write(f"\n{_CHANGELOG_HEADER}")
    summary = " ".join(args.note.split()).strip() or "（未填摘要）"
    when = date.today().isoformat()
    level_label = args.level.capitalize()
    with changelog.open("a", encoding="utf-8") as fh:
        fh.write(f"| {version} | {when} | {level_label} | {summary} |\n")

    print(f"published \"{args.article}\" v{version}")
    print(f"  _latest: {latest} (working copy, section markers preserved)")
    print(f"  snapshot: {snapshot}" + (" (read-only, markers stripped)" if frozen else " (markers stripped; read-only attribute failed, freeze is by convention)"))
    print(f"  changelog: {changelog}")
    print(f"  {result['drafted']} section(s) published.")
    return 0


def _count_open_findings(layout, leaves, article: str) -> int:
    """該文件的未解 finding：自己 doc-root store ＋ 觸及它的 forest finding。"""
    from dspx.audit import all_findings, distinct_articles
    n = 0
    for f in all_findings(layout, leaves):
        if f.get("status") != "open":
            continue
        store = f.get("_store", "")
        if store == f"doc:{article}":
            n += 1
        elif store == "forest" and article in distinct_articles(f.get("targets") or [], leaves):
            n += 1
    return n
