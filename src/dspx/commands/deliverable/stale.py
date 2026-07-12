"""docspec stale <section|article> — 標髒散文（散文必須重寫，即使指紋一根沒動）。

台中港〔#18〕實證：大重構後的橫掃可能讓某些源料位元不變、散文卻已不合時宜——沒有標髒動詞時，
作者被迫假改 concept 觸發 stale（竄改真相源去搬簿記旗標）。本指令在帳本記錄上設
`redraft: true` 顯式旗標（**指紋一律不動**＝保留「散文上次基於什麼寫」的歷史資訊）；status
在 own 比對前把旗標投影成 `stale-own`（apply 的 pickup 集合零改動接手）；散文真重寫後由
render 的重算路徑自然清除、或 render --ack-own 顯式清除。強制 `--reason`、裁決入 append-only
verdicts journal。agent-facing（不進 HUMAN_COMMANDS）。

位置引數兩態（由是節路徑還是文章名自動判定）：
  - **一節** `docspec stale <section>`：標髒單一已撰寫節（journal verb=stale）。
  - **整篇** `docspec stale <article>`：對該文章**每個有帳本記錄（已撰寫）的節**批次標髒＝
    大重構／全文重投後的批次版（journal verb=redraft）。標髒前自動把現行
    `docs/<article>/_latest.md` 備份到 `docspec/.ledger/redraft-backup/<article>.<ts>.md`
    ——draft 隨後會批次重寫全文散文，備份是唯一悔棋點；放 `.ledger/` 不放 `docs/`（交付潔癖）。
"""

from __future__ import annotations

import argparse
import datetime
import shutil
import sys

from dspx.commands._shared import BootstrapError, bootstrap, load_model
from dspx.engine.layout import LEDGER_DIR_NAME
from dspx.engine.render import (
    append_verdicts,
    ledger_needs_migration,
    read_ledger,
    read_ledger_groups,
    verdict_entry,
    write_ledger,
)

NAME = "stale"
HELP = ("mark prose for rewrite (sets redraft flags on ledger entries; fingerprints untouched; "
        "requires --reason, journaled). <section> marks one section; <article> marks every "
        "written section of the article (whole re-projection, backs up _latest.md first)")


def _stale_one(layout, section: str, reason: str) -> int:
    """一節標髒（journal verb=stale）。"""
    article = section.split("/", 1)[0]
    if ledger_needs_migration(layout, article):
        sys.stderr.write(
            f"docspec: the ledger of \"{article}\" is an older fingerprint version — migrate first "
            f"with `docspec render {article} --rebaseline`, then mark sections.\n")
        return 1
    ledger = read_ledger(layout, article)
    rec = ledger.get(section)
    if not isinstance(rec, dict):
        sys.stderr.write(
            f"docspec: \"{section}\" has no ledger entry (its prose was never written) — an "
            "unwritten section is already draft's work; nothing to mark.\n")
        return 1

    rec["redraft"] = True
    write_ledger(layout, article, ledger, groups_fp=read_ledger_groups(layout, article))
    append_verdicts(layout, article, [
        verdict_entry("stale", section, reason, rec.get("own"), rec.get("own"), rec.get("prose"))])

    print(f"marked \"{section}\" for rewrite (redraft flag set; fingerprints untouched).")
    print("  docspec status now reports it stale-own — apply picks it up; a real prose rewrite "
          "(or render --ack-own) clears the flag.")
    return 0


def _stale_article(layout, article: str, reason: str) -> int:
    """整篇批次標髒＝全文重投（journal verb=redraft）；標髒前備份現行交付物（唯一悔棋點）。"""
    if ledger_needs_migration(layout, article):
        sys.stderr.write(
            f"docspec: the ledger of \"{article}\" is an older fingerprint version — migrate "
            f"first with `docspec render {article} --rebaseline`, then mark sections.\n")
        return 1

    ledger = read_ledger(layout, article)
    written = [(s, rec) for s, rec in ledger.items() if isinstance(rec, dict)]
    if not written:
        sys.stderr.write(
            f"docspec: article \"{article}\" has no written sections in its ledger — "
            "unwritten sections are already draft's work; nothing to mark.\n")
        return 1

    # 標髒前備份現行交付物（唯一悔棋點）：draft 之後會批次重寫全文散文。住 .ledger/、不碰 docs/。
    latest = layout.docs_latest(article)
    backup = None
    if latest.is_file():
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_dir = layout.planning_home / LEDGER_DIR_NAME / "redraft-backup"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / f"{article}.{stamp}.md"
        shutil.copy2(str(latest), str(backup))

    for _section, rec in written:
        rec["redraft"] = True
    write_ledger(layout, article, ledger, groups_fp=read_ledger_groups(layout, article))
    # 每節一筆（schema 均一、可按節 grep）；whole-article 標髒 journal verb=redraft、不動指紋。
    append_verdicts(layout, article, [
        verdict_entry("redraft", section, reason, rec.get("own"), rec.get("own"), rec.get("prose"))
        for section, rec in written])

    print(f"marked {len(written)} written section(s) of \"{article}\" for rewrite "
          "(redraft flags set; fingerprints untouched).")
    if backup is not None:
        print(f"  backed up the current deliverable to {backup} — the pre-redraft prose survives "
              "the coming rewrite.")
    print("  docspec status now reports them stale-own — apply re-renders each; a real prose "
          "rewrite (or render --ack-own) clears the flag.")
    return 0


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec stale", description=HELP)
    parser.add_argument("target",
                        help="a leaf section (mark one) OR an article name (mark every written "
                             "section of it = whole re-projection)")
    parser.add_argument(
        "--reason", default=None, metavar="TEXT",
        help="why this prose must be rewritten although no fingerprint moved — mandatory; "
             "recorded in the article's append-only verdicts journal.")
    args = parser.parse_args(argv)

    if not args.reason:
        sys.stderr.write(
            "docspec: stale requires --reason <text> — the verdict is journaled; say why this "
            "prose must be rewritten.\n")
        return 2

    try:
        layout, _config = bootstrap()
        leaves = load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code

    target = args.target.strip("/")
    # 位置引數兩態：先認完整節路徑（一節），再認文章名（整篇）。
    if any(lf.section == target for lf in leaves):
        return _stale_one(layout, target, args.reason)
    if any(lf.article == target for lf in leaves):
        return _stale_article(layout, target, args.reason)
    sys.stderr.write(
        f"docspec: no leaf section or article found for \"{target}\" "
        "(give a leaf section path to mark one, or an article name to mark the whole article).\n")
    return 1
