"""docspec stale <section> — 標髒一個已撰寫節：散文必須重寫，即使指紋一根沒動。

台中港〔#18〕實證：大重構後的橫掃可能讓某些源料位元不變、散文卻已不合時宜——沒有標髒動詞時，
作者被迫假改 concept 觸發 stale（竄改真相源去搬簿記旗標）。本指令在該節帳本記錄上設
`redraft: true` 顯式旗標（**指紋一律不動**＝保留「散文上次基於什麼寫」的歷史資訊）；status
在 own 比對前把旗標投影成 `stale-own`（draft 的 pickup 集合零改動接手）；散文真重寫後由
render 的重算路徑自然清除。強制 `--reason`、裁決入 append-only verdicts journal。
agent-facing（不進 HUMAN_COMMANDS）。整篇文章批次標髒用 `docspec redraft`。
"""

from __future__ import annotations

import argparse
import sys

from dspx.commands._shared import BootstrapError, bootstrap, load_model
from dspx.render import (
    append_verdicts,
    read_ledger,
    read_ledger_groups,
    verdict_entry,
    write_ledger,
)

NAME = "stale"
HELP = ("mark one written section's prose for rewrite (sets a redraft flag on its ledger entry; "
        "fingerprints untouched; requires --reason, journaled)")


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec stale", description=HELP)
    parser.add_argument("section", help="leaf section to mark for rewrite (path relative to corpus/)")
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

    section = args.section.strip("/")
    if not any(lf.section == section for lf in leaves):
        # 未知節：沿用 render 的 unknown-article 措辭風格
        sys.stderr.write(f"docspec: no leaf section found for \"{section}\"\n")
        return 1

    article = section.split("/", 1)[0]
    ledger = read_ledger(layout, article)
    rec = ledger.get(section)
    if not isinstance(rec, dict):
        # 未撰寫（無帳本記錄）＝本來就是 draft 的工作，沒有「標髒」可言。
        sys.stderr.write(
            f"docspec: \"{section}\" has no ledger entry (its prose was never written) — an "
            "unwritten section is already draft's work; nothing to mark.\n")
        return 1

    # 設旗標、指紋一律不動；groups 指紋原樣保留（標髒不是 render，不得蓋掉骨架面信號）。
    rec["redraft"] = True
    write_ledger(layout, article, ledger,
                 groups_fp=read_ledger_groups(layout, article))
    append_verdicts(layout, article, [
        verdict_entry("stale", section, args.reason,
                      rec.get("own"), rec.get("own"), rec.get("prose"))])

    print(f"marked \"{section}\" for rewrite (redraft flag set; fingerprints untouched).")
    print("  docspec status now reports it stale-own — draft picks it up; a real prose rewrite "
          "(or render --ack-own) clears the flag.")
    return 0
