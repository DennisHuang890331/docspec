"""docspec normalize <article> — 對交付物散文面做確定性半形→全形標點正規化。

確定性機械變換（封閉映射表＋左鄰嚴格 CJK／右鄰 CJK-或-行尾條件；code／圖 path／URL／
裸識別碼 byte-exact 跳過）。**帳本自持**（D4）：寫回後直接更新各觸及節 prose 指紋、
其餘軸原樣保留——不產假 ✎drift、也不自動跑 render（render F2 會吸收 stale 信號）。
"""

from __future__ import annotations

import argparse
import sys

from dspx.commands._shared import BootstrapError, bootstrap, load_engine_schema, load_model
from dspx.engine.render import (
    LEDGER_FINGERPRINT_VERSION,
    parse_section_bodies,
    prose_hash,
    read_ledger,
    read_ledger_groups,
    read_ledger_version,
    write_ledger,
)
from dspx.engine.spans import apply_conversions, propose_conversions

NAME = "normalize"
HELP = "convert half-width punctuation to full-width in a deliverable's prose (deterministic; code/URLs untouched)"


def _update_ledger_prose(layout, article: str, touched: set[str], new_text: str) -> None:
    """帳本自持（D4）：把觸及節的 prose 指紋更新為新值，own/anc/deps/norm/style 原樣保留。

    僅在帳本為現行版本時更新——v1／壞帳本不動（避免靜默遷移／吸收 stale 信號），改由警告
    導向 `docspec render --rebaseline`。帳本無該節記錄（未撰寫）→ 不寫。"""
    version = read_ledger_version(layout, article)
    if version is None:
        return                                  # 無帳本（未 render）→ 無指紋可維護
    if version != LEDGER_FINGERPRINT_VERSION:
        sys.stderr.write(
            f"docspec: ⚠ ledger of \"{article}\" is fingerprint v{version} (not current) — "
            "prose fingerprints were NOT updated; `docspec diff` may show ✎drift until you run "
            f"`docspec render {article} --rebaseline`.\n")
        return
    ledger = read_ledger(layout, article)
    if not ledger:
        return
    bodies = parse_section_bodies(new_text)
    changed = False
    for section in touched:
        rec = ledger.get(section)
        if not isinstance(rec, dict) or rec.get("prose") is None:
            continue                            # 無基準（未撰寫節）→ 不寫（detect_drift 本就跳過）
        if section in bodies:
            rec["prose"] = prose_hash(bodies[section])
            changed = True
    if changed:
        write_ledger(layout, article, ledger, groups_fp=read_ledger_groups(layout, article))


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec normalize", description=HELP)
    parser.add_argument("article", help="name of the article to normalize")
    parser.add_argument(
        "--dry-run", action="store_true", dest="dry_run",
        help="list every conversion (section, surrounding context, before -> after) without "
             "writing the file or touching the ledger")
    args = parser.parse_args(argv)

    try:
        layout, config = bootstrap()
        load_engine_schema(config)
        leaves = load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code

    if not any(lf.article == args.article for lf in leaves):
        sys.stderr.write(f"docspec: no leaf sections found for article \"{args.article}\"\n")
        return 1

    latest = layout.docs_latest(args.article)
    if not latest.is_file():
        sys.stderr.write(
            f"docspec: deliverable {latest} does not exist — run `docspec render {args.article}` first.\n")
        return 1

    text = latest.read_text(encoding="utf-8")
    convs = propose_conversions(text)

    if not convs:
        print(f"normalize: \"{args.article}\" prose already uses full-width punctuation (0 conversions).")
        return 0

    if args.dry_run:
        print(f"normalize --dry-run: \"{args.article}\" — {len(convs)} conversion(s) proposed "
              "(nothing written):")
        for c in convs:
            loc = c.section or "(preamble)"
            print(f"  § {loc}: …{c.before}[{c.src} -> {c.dst}]{c.after}…")
        return 0

    new_text = apply_conversions(text, convs)
    latest.write_text(new_text, encoding="utf-8", newline="\n")

    touched = {c.section for c in convs}
    _update_ledger_prose(layout, args.article, touched, new_text)

    named = sorted(s for s in touched if s)
    print(f"normalize: \"{args.article}\" — {len(convs)} conversion(s) across "
          f"{len(touched)} section(s) -> {latest}")
    if named:
        print(f"  sections touched: {', '.join(named)}")
    return 0
