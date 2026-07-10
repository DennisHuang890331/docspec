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
from dspx.layout import Layout, next_version, parse_semver
from dspx.lint import ERROR, run_lint
from dspx.render import render_article, strip_markers

NAME = "publish"
HELP = "the only irreversible command: check+lint green -> render -> freeze a read-only, marker-stripped snapshot"

# changelog markdown 表頭（publish 機械寫；列只摘要、不抄細節）。依專案 language 在地化
# （oss-release-prep 英文化漏了 changelog 產生器 → 英文文件洩中文表頭/摘要；同 i18n 根）。
_CHANGELOG_HEADERS = {
    "zh": "| 版本 | 日期 | 級別 | 說明 |\n|---|---|---|---|\n",
    "en": "| Version | Date | Level | Summary |\n|---|---|---|---|\n",
}
_NO_SUMMARY = {"zh": "（未填摘要）", "en": "(no summary)"}
_FIRST_LABEL = {"zh": "首版", "en": "Initial"}
# 級別欄在地化 map（非首版）：原本一律 args.level.capitalize()＝中文文件冒英文「Patch」。
_LEVEL_LABELS = {
    "zh": {"patch": "修訂", "minor": "次版", "major": "主版"},
    "en": {"patch": "Patch", "minor": "Minor", "major": "Major"},
}
# 所有已知表頭變體（偵測既有檔是否已有任一 → 不重複補表頭，避免雙表頭）。
_ALL_HEADERS = tuple(_CHANGELOG_HEADERS.values())


def _changelog_lang(clean_body: str, config: dict) -> str:
    """changelog 在地化＝偵測**文件語言**（從定稿內容 CJK 比例），非綁專案 config.language
    （單一專案級設定常忘了改、英文交付物洩中文表頭）。config.language 為內容無可判時的 fallback。"""
    from dspx.config import detect_language
    return detect_language(clean_body, config.get("language"))


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
    parser.add_argument("--set-version", dest="set_version", default=None, metavar="X.Y.Z",
                        help="seed the version chain on the FIRST publish only (a migrated project "
                             "continues its pre-docspec numbering instead of restarting at 1.0.0); "
                             "refused once any version exists")
    parser.add_argument("--allow-noop", action="store_true",
                        help="allow freezing a snapshot byte-identical to the previous version "
                             "(by default publish refuses a no-op version bump)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print a consolidated go/no-go pre-publish report and exit without "
                             "writing anything (no render, no version stamp, no snapshot, no changelog)")
    args = parser.parse_args(argv)

    # ── --set-version 值：嚴格 semver（唯一真雷點：壞值鑄出的快照檔名日後被版本掃描
    #    靜默跳過＝版本鏈斷裂且無人察覺）→ 不合格即拒、不凍結。──
    if args.set_version is not None and parse_semver(args.set_version) is None:
        sys.stderr.write(
            f"docspec: publish aborted -- --set-version \"{args.set_version}\" is not strict "
            "semver X.Y.Z (a malformed version would be silently skipped by the version scan "
            "and break the chain).\n")
        return 1

    try:
        layout, config = bootstrap()
        schema = load_engine_schema(config)
        leaves = load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code

    if not any(lf.article == args.article for lf in leaves):
        sys.stderr.write(f"docspec: no leaf sections found for article \"{args.article}\"\n")
        return 1

    # ── --dry-run：分支在既有閘區塊**之前**（閘紅時舊 abort 訊息會 early-return、
    #    彙總報告永遠印不出來）；dry-run 自己跑全部閘、印彙總、零寫入。──
    if args.dry_run:
        return _dry_run(layout, schema, leaves, args)

    # ── --set-version 閘：限首次發行。版本鏈已存在＝改史，結構性拒絕；擺在任何寫入
    #    （render 的骨架/帳本）之前＝abort 即零寫入。偽造 is_first 需先刪既有快照 →
    #    被 .freeze.yaml hash net 抓、lint 閘在版本推導前就 abort（design D8）。──
    if args.set_version is not None and layout.existing_versions(args.article):
        sys.stderr.write(
            "docspec: publish aborted -- version chain already exists; "
            "--set-version cannot rewrite history.\n")
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
    prev_versions = layout.existing_versions(args.article)
    is_first = not prev_versions
    # --set-version 走到這裡必為首次（非首次已在前面 abort）＝直接以指定版號鑄造
    version = args.set_version or _next_version(layout, args.article, args.level)

    meta, body = parse_frontmatter(latest.read_text(encoding="utf-8"))
    # 快照＝純內容：剝隱形標記 ＋ **不寫 frontmatter**（機器簿記不進凍結交付物；
    # 版號在檔名、紀錄在 changelog）。讀者開檔只看到散文。
    clean_body = strip_markers(body).strip() + "\n"

    # ── no-op 偵測：與上一凍結快照位元相同 → 拒（不鑄幻影新版；--allow-noop 才放行）──
    if prev_versions and not args.allow_noop:
        prev_v = ".".join(str(p) for p in max(prev_versions))
        prev_snap = layout.docs_snapshot(args.article, prev_v)
        if prev_snap.is_file() and prev_snap.read_text(encoding="utf-8").strip() + "\n" == clean_body:
            sys.stderr.write(
                f"docspec: publish aborted — content is byte-identical to v{prev_v}; nothing new to "
                f"release (use --allow-noop to force a no-op version bump).\n")
            return 1

    # ── 蓋版號到 _latest（保留標記，它是工作副本）──
    meta["version"] = version
    latest.write_text(render_frontmatter(meta, body), encoding="utf-8")

    # ── 凍結快照：完全剝除隱形標記 ──
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
    clang = _changelog_lang(clean_body, config)
    header = _CHANGELOG_HEADERS[clang]
    changelog = layout.docs_changelog(args.article)
    changelog.parent.mkdir(parents=True, exist_ok=True)
    if not changelog.is_file():
        changelog.write_text(
            f"# {args.article} — revision history\n\n{header}", encoding="utf-8")
    elif not any(h in changelog.read_text(encoding="utf-8") for h in _ALL_HEADERS):
        # 既有檔但無任何已知表頭（舊格式）→ 補表頭，新列接在後面（比對全變體，免雙表頭）。
        with changelog.open("a", encoding="utf-8") as fh:
            fh.write(f"\n{header}")
    summary = " ".join(args.note.split()).strip() or _NO_SUMMARY[clang]
    when = date.today().isoformat()
    # 首版＝無前版時 next_version 直接回 1.0.0、忽略 --level → 標 level 會自相矛盾（1.0.0｜Patch）；
    # 改標在地化「首版/Initial」。使用者在首版給了非預設 --level＝對首版無效，提示一聲。
    level_label = _FIRST_LABEL[clang] if is_first else _LEVEL_LABELS[clang][args.level]
    if is_first and args.level != "patch":
        sys.stderr.write(
            f"docspec: note — --level {args.level} has no effect on the first version (it is {version}).\n")
    with changelog.open("a", encoding="utf-8") as fh:
        fh.write(f"| {version} | {when} | {level_label} | {summary} |\n")

    print(f"published \"{args.article}\" v{version}")
    print(f"  _latest: {latest} (working copy, section markers preserved)")
    print(f"  snapshot: {snapshot}" + (" (read-only, markers stripped)" if frozen else " (markers stripped; read-only attribute failed, freeze is by convention)"))
    print(f"  changelog: {changelog}")
    print(f"  {result['drafted']} section(s) published.")
    return 0


def _dry_run(layout: Layout, schema, leaves, args) -> int:
    """`--dry-run`：跑真 publish 的四個阻塞閘（呼叫同一批函式、零第二實作）＋資訊行，零寫入。

    預覽非鎖定（spec：preview, not a reservation）：真 publish 會先 render 再算 coverage，
    dry-run 對現有 `_latest.md` 算——render 不寫散文，閘相關量（哪些節有散文）相同，
    但 dry-run 綠不保證之後真 publish 綠（中間檔案可能變）。"""
    from dspx.render import detect_drift, parse_section_bodies

    article = args.article
    print(f"pre-publish preview for \"{article}\" (--dry-run; nothing is written)")
    ok = True

    # ① check（真 publish：紅 → abort）
    check = run_check(leaves, schema, layout)
    if check.ok:
        print("  ✓ check: passed")
    else:
        ok = False
        print(f"  ✗ check: {len(check.errors)} error(s) — publish would abort (run docspec check)")

    # ② lint ERROR（真 publish：有 → abort）
    lint_errors = [f for f in run_lint(layout, leaves, schema) if f.level == ERROR]
    if lint_errors:
        ok = False
        print(f"  ✗ lint: {len(lint_errors)} ERROR finding(s) — publish would abort (run docspec lint)")
    else:
        print("  ✓ lint: no ERROR findings")

    # ③ coverage（真 publish：render 後 drafted==0 → abort；dry-run 對現有 _latest 算；
    #    無 _latest ＝ 0 written）
    art_leaves = [lf for lf in leaves if lf.article == article]
    latest = layout.docs_latest(article)
    bodies = parse_section_bodies(latest.read_text(encoding="utf-8")) if latest.is_file() else {}
    written = [lf.section for lf in art_leaves if bodies.get(lf.section, "").strip()]
    if written:
        print(f"  ✓ coverage: {len(written)}/{len(art_leaves)} section(s) have prose")
    else:
        ok = False
        print("  ✗ coverage: no written sections yet (draft has not produced prose) "
              "— publish would abort")

    # ④ no-op 預測（真 publish：位元同前版 → abort；--allow-noop／無前版 → 跳過）
    prev_versions = layout.existing_versions(article)
    if args.allow_noop:
        print("  – no-op: skipped (--allow-noop)")
    elif not prev_versions:
        print("  – no-op: skipped (no prior version)")
    else:
        if latest.is_file():
            _, body = parse_frontmatter(latest.read_text(encoding="utf-8"))
            clean_body = strip_markers(body).strip() + "\n"
        else:
            clean_body = "\n"
        prev_v = ".".join(str(p) for p in max(prev_versions))
        prev_snap = layout.docs_snapshot(article, prev_v)
        if prev_snap.is_file() and prev_snap.read_text(encoding="utf-8").strip() + "\n" == clean_body:
            ok = False
            print(f"  ✗ no-op: content is byte-identical to v{prev_v} — publish would abort "
                  f"(use --allow-noop to force)")
        else:
            print(f"  ✓ no-op: content differs from v{prev_v}")

    # ℹ 資訊行（永不阻塞——與真 publish 的非阻塞語義一致）
    from dspx.commands.status import _docs_hashes, _leaf_row
    from dspx.model import decision_index
    by_section = {lf.section: lf for lf in leaves}
    dindex = decision_index(leaves)
    hashes = _docs_hashes(layout, article)
    stale_counts: dict[str, int] = {}
    for lf in art_leaves:
        sync = _leaf_row(layout, lf, schema, check.ok, hashes, by_section, dindex)["sync"]
        if sync != "synced":
            stale_counts[sync] = stale_counts.get(sync, 0) + 1
    stale_note = "  ".join(f"{k}:{v}" for k, v in sorted(stale_counts.items())) or "all synced"
    print(f"  ℹ staleness: {stale_note}")
    print(f"  ℹ drift: {len(detect_drift(layout, article))} hand-edited section(s)")
    print(f"  ℹ audit: {_count_open_findings(layout, leaves, article)} open finding(s) (non-blocking)")
    # 版本預覽：--set-version 反映 seed 版（首次）／預告非首次會被拒（同真 publish 規則、NO-GO 化）
    if args.set_version is not None:
        if prev_versions:
            ok = False
            print("  ✗ --set-version: version chain already exists — publish would abort "
                  "(--set-version cannot rewrite history)")
        else:
            print(f"  ℹ version preview: v{args.set_version} (--set-version, first publish)")
    else:
        print(f"  ℹ version preview: v{_next_version(layout, article, args.level)} (--level {args.level})")

    if ok:
        print("dry-run verdict: GO — all blocking gates pass "
              "(preview only; a real publish re-runs its own gates)")
        return 0
    print("dry-run verdict: NO-GO — fix the ✗ gate(s) above before publishing")
    return 1


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
