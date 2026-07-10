"""docspec render <article> — 確定性把末節散文骨架同步進 docs/<article>/_latest.md。"""

from __future__ import annotations

import argparse
import sys

from dspx.commands._shared import BootstrapError, bootstrap, load_engine_schema, load_model
from dspx.render import read_ledger, render_article

NAME = "render"
HELP = "sync leaf section prose skeleton into docs/<article>/_latest.md (deterministic, preserves written prose)"


def _guard_ledger_health(layout, article: str, rebaseline: bool) -> int | None:
    """壞帳本閘（D3）：ledger 解析失敗 → 改名隔離備份＋拒跑（絕不以空帳本繼續 render——
    那會把待重寫的 stale 信號永久蓋成新基準）。帶 --rebaseline 才在隔離後放行重建。
    回傳非 None＝要求呼叫端以該碼離開。"""
    import datetime

    import yaml
    for ledger in (layout.docs_ledger(article), layout.docs_ledger_legacy(article)):
        if not ledger.is_file():
            continue
        try:
            yaml.safe_load(ledger.read_text(encoding="utf-8"))
            return None            # 帳本可解析 → 放行（read_ledger 走原路）
        except yaml.YAMLError as exc:
            stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = ledger.with_name(ledger.name + f".corrupt-{stamp}")
            ledger.rename(backup)
            sys.stderr.write(
                f"docspec: ledger {ledger} is corrupt ({exc}).\n"
                f"  quarantined the corrupt file to: {backup}\n")
            if rebaseline:
                sys.stderr.write(
                    "  --rebaseline given: rebuilding the fingerprint baseline from the current "
                    "deliverable (pending stale signals are absorbed).\n")
                return None
            sys.stderr.write(
                "  refusing to render: continuing with an empty ledger would permanently absorb "
                "any pending stale/rewrite signals as the new baseline.\n"
                "  either restore the ledger from git/Drive history, or re-run "
                f"`docspec render {article} --rebaseline` to rebuild the baseline.\n")
            return 1
    return None


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec render", description=HELP)
    parser.add_argument("article", help="name of the article to assemble")
    parser.add_argument(
        "--ack", action="append", default=[], metavar="SECTION", dest="ack",
        help="acknowledge a stale-inherited / stale-style SECTION as aligned (prose needs no "
             "change — already matches the moved ancestor brief or the updated writing-guide/"
             "glossary) and re-stamp its ancestor + style fingerprints; refused if the section is "
             "actually stale-own/upstream (rewrite its prose instead). Repeatable.")
    parser.add_argument(
        "--rebaseline", action="store_true",
        help="explicit rebuild: I know the deliverable file is gone (or the ledger is corrupt) — "
             "regenerate the skeleton and reset the fingerprint baseline. Without this flag, "
             "render refuses to overwrite the ledger in those states.")
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

    # 壞帳本閘（D3）：隔離備份＋拒跑；--rebaseline 才放行重建。
    rc = _guard_ledger_health(layout, args.article, args.rebaseline)
    if rc is not None:
        return rc

    # 存在性互驗（D2）：帳本非空 ∧ 交付檔缺 ＝「曾經有交付物、現在不見了」——拒生空骨架
    # 蓋帳本（帳本零改動）；--rebaseline 才重生骨架並重置基準。
    latest = layout.docs_latest(args.article)
    prior = read_ledger(layout, args.article)
    if prior and not latest.is_file() and not args.rebaseline:
        sys.stderr.write(
            f"docspec: deliverable {latest} is missing but its ledger has "
            f"{len(prior)} section record(s) — refusing to render an empty skeleton over the "
            "ledger (the written prose would be silently lost as the new baseline).\n"
            f"  either restore {latest.name} from git/Drive history, or re-run "
            f"`docspec render {args.article} --rebaseline` to rebuild the skeleton and reset "
            "the baseline.\n")
        return 1

    result = render_article(layout, leaves, args.article, ack_sections=set(args.ack))
    total = len(result["sections"])
    print(f"synced \"{args.article}\" skeleton -> {result['written_path']}")
    print(f"  {total} section(s), of which {result['drafted']} have prose and "
          f"{total - result['drafted']} are unwritten.")
    if result.get("acked"):
        print(f"  acknowledged (re-stamped, stale-inherited/stale-style cleared): {', '.join(result['acked'])}")
        # 非阻塞提醒：ack 清掉的是「祖先動了」的信號，但子節自己的 brief/concept 框架/圖
        # 是否仍與上游一致＝語義、staleness 照不到（revision-coherence-probes）。導向覆檢、非 gate。
        print("  ↳ also re-check these sections' own brief / concept framing / figures are still "
              "consistent with the moved ancestor (the ledger can't see that — factcheck owns it).")
    if result.get("ack_refused"):
        sys.stderr.write(
            "docspec: ⚠ --ack refused for (these are stale-own/upstream — rewrite the prose, "
            f"don't acknowledge): {', '.join(result['ack_refused'])}\n")
    return 0
