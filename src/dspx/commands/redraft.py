"""docspec redraft <article> — 整篇文章批次標髒：全部已撰寫節的散文重投（whole re-projection）。

大重構／全文重投後的批次版 `docspec stale`：對該文章**每個有帳本記錄（已撰寫）的節**設
`redraft: true` 旗標（指紋一律不動）；status 全數投影成 `stale-own`（draft 零改動接手）。
標髒前自動把現行 `docs/<article>/_latest.md`（存在時）備份到
`docspec/.ledger/redraft-backup/<article>.<timestamp>.md`——draft 隨後會批次重寫全文散文，
備份是唯一悔棋點；放 `.ledger/` 不放 `docs/`（交付潔癖：docs/ 只放人讀交付物）。
強制 `--reason`、每節一筆入 append-only verdicts journal。agent-facing（不進 HUMAN_COMMANDS）。
"""

from __future__ import annotations

import argparse
import datetime
import shutil
import sys

from dspx.commands._shared import BootstrapError, bootstrap, load_model
from dspx.layout import LEDGER_DIR_NAME
from dspx.render import (
    append_verdicts,
    ledger_needs_migration,
    read_ledger,
    read_ledger_groups,
    verdict_entry,
    write_ledger,
)

NAME = "redraft"
HELP = ("mark every written section of an article for rewrite (sets redraft flags; fingerprints "
        "untouched; backs up _latest.md into docspec/.ledger/redraft-backup/ first; requires "
        "--reason, journaled per section)")


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec redraft", description=HELP)
    parser.add_argument("article", help="article whose written sections should all be re-drafted")
    parser.add_argument(
        "--reason", default=None, metavar="TEXT",
        help="why the whole article must be re-projected although no fingerprint moved — "
             "mandatory; recorded per section in the append-only verdicts journal.")
    args = parser.parse_args(argv)

    if not args.reason:
        sys.stderr.write(
            "docspec: redraft requires --reason <text> — the verdict is journaled; say why the "
            "article's prose must be rewritten.\n")
        return 2

    try:
        layout, _config = bootstrap()
        leaves = load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code

    if not any(lf.article == args.article for lf in leaves):
        sys.stderr.write(f"docspec: no leaf sections found for article \"{args.article}\"\n")
        return 1

    # v1 帳本閘：write_ledger 會蓋上現行版本鍵——對 v1 帳本標髒＝把未遷移的舊值謊稱 v2。
    if ledger_needs_migration(layout, args.article):
        sys.stderr.write(
            f"docspec: the ledger of \"{args.article}\" is fingerprint v1 — migrate first with "
            f"`docspec render {args.article} --rebaseline`, then mark sections.\n")
        return 1

    ledger = read_ledger(layout, args.article)
    written = [(s, rec) for s, rec in ledger.items() if isinstance(rec, dict)]
    if not written:
        sys.stderr.write(
            f"docspec: article \"{args.article}\" has no written sections in its ledger — "
            "unwritten sections are already draft's work; nothing to mark.\n")
        return 1

    # 標髒前備份現行交付物（唯一悔棋點）：draft 之後會批次重寫全文散文。
    # lazy 建目錄；備份住 .ledger/（機器簿記），絕不碰 docs/（會撞交付潔癖 lint）。
    latest = layout.docs_latest(args.article)
    backup = None
    if latest.is_file():
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_dir = layout.planning_home / LEDGER_DIR_NAME / "redraft-backup"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / f"{args.article}.{stamp}.md"
        shutil.copy2(str(latest), str(backup))

    for _section, rec in written:
        rec["redraft"] = True
    write_ledger(layout, args.article, ledger,
                 groups_fp=read_ledger_groups(layout, args.article))
    # 每節一筆（schema 均一、可按節 grep）；redraft 不動指紋＝own_before == own_after。
    append_verdicts(layout, args.article, [
        verdict_entry("redraft", section, args.reason,
                      rec.get("own"), rec.get("own"), rec.get("prose"))
        for section, rec in written])

    print(f"marked {len(written)} written section(s) of \"{args.article}\" for rewrite "
          "(redraft flags set; fingerprints untouched).")
    if backup is not None:
        print(f"  backed up the current deliverable to {backup} — the pre-redraft prose survives "
              "the coming rewrite.")
    print("  docspec status now reports them stale-own — draft re-renders each; a real prose "
          "rewrite (or render --ack-own) clears the flag.")
    return 0
