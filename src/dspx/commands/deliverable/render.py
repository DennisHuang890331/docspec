"""docspec render <article> — 確定性把末節散文骨架同步進 docs/<article>/_latest.md。"""

from __future__ import annotations

import argparse
import sys

from dspx.commands._shared import BootstrapError, bootstrap, load_engine_schema, load_model
from dspx.engine.render import ledger_needs_migration, read_ledger, render_article

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


def _render_change(layout, args) -> int:
    """render --change：從 union view（staging 優先、正式補底）渲染到 change 的 preview 區。
    正式 docs/ 零寫入；預覽成品與帳本從正式版 seed（★G2）。"""
    from dspx.engine import change as chg
    if chg.change_state(layout, args.change) != chg.STATE_ACTIVE:
        sys.stderr.write(f"docspec: no active change \"{args.change}\".\n")
        return 1
    change = chg.load_change_at(chg.change_dir(layout, args.change, chg.STATE_ACTIVE),
                                chg.STATE_ACTIVE)
    union_leaves = chg.load_union(layout, change)
    if not any(lf.article == args.article for lf in union_leaves):
        sys.stderr.write(
            f"docspec: no leaf sections found for article \"{args.article}\" in the union view "
            f"of change \"{args.change}\".\n")
        return 1
    # ★G2：seed preview 成品與帳本從正式版（否則首次 preview render 全 unwritten）。
    chg.seed_preview(layout, change, args.article)
    overlay = chg.OverlayLayout(layout, change)
    result = render_article(overlay, union_leaves, args.article,
                            ack_sections=set(args.ack), ack_own_sections=set(args.ack_own),
                            reason=args.reason or "")
    total = len(result["sections"])
    print(f"synced change \"{args.change}\" preview of \"{args.article}\" -> {result['written_path']}")
    print(f"  {total} section(s), of which {result['drafted']} have prose and "
          f"{total - result['drafted']} are unwritten. (official docs/ untouched)")
    if result.get("acked"):
        print(f"  acknowledged: {', '.join(result['acked'])}")
    if result.get("ack_owned"):
        print(f"  ack-own: {', '.join(result['ack_owned'])}")
    return 0


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec render", description=HELP)
    parser.add_argument("article", help="name of the article to assemble")
    parser.add_argument(
        "--ack", action="append", default=[], metavar="SECTION", dest="ack",
        help="acknowledge a stale-inherited / stale-norm / stale-style SECTION as aligned (prose "
             "needs no change — already matches the moved ancestor brief, the changed ancestor "
             "ruling, or the updated writing-guide/glossary/purpose) and re-stamp its ancestor + "
             "norm + style fingerprints; refused if the section is actually stale-own/upstream "
             "(rewrite its prose instead). Repeatable.")
    parser.add_argument(
        "--ack-own", action="append", default=[], metavar="SECTION", dest="ack_own",
        help="acknowledge a stale-own / stale-upstream SECTION whose prose legitimately needs no "
             "change (the source change was structural wiring / metadata only — e.g. a sources: "
             "path move, a realizes/governed-by re-wire, an order or title renumbering) and "
             "re-stamp its own + deps fingerprints to current; anc/style are kept, so a masked "
             "stale-inherited/stale-style surfaces. Requires --reason. Repeatable; composable "
             "with --ack.")
    parser.add_argument(
        "--reason", default=None, metavar="TEXT",
        help="why this verdict is legitimate — recorded in the article's append-only verdicts "
             "journal (docspec/.ledger/<article>.verdicts.yaml). Mandatory with --ack-own; "
             "optional with --ack.")
    parser.add_argument(
        "--rebaseline", action="store_true",
        help="explicit rebuild: I know the deliverable file is gone, the ledger is corrupt, or "
             "the ledger is an older fingerprint version (pre-current algorithms) — regenerate "
             "the skeleton, recompute every fingerprint axis with the current algorithms (prose "
             "is preserved) and reset the baseline. Absorbs any pending stale signals. Without "
             "this flag, render refuses to touch the ledger in those states.")
    parser.add_argument(
        "--change", default=None, metavar="CHANGE-ID",
        help="render the UNION view (staging over official) into changes/<id>/preview/<article>_"
             "latest.md with a staging-side sidecar ledger; official docs/ is never written "
             "(the preview + ledger are seeded from the official version, ★G2)")
    args = parser.parse_args(argv)

    # --ack-own 強制 --reason（裁決入 journal；改變 own/deps 裁決＝事後最需考古的一類）。
    if args.ack_own and not args.reason:
        sys.stderr.write(
            "docspec: --ack-own requires --reason <text> — you are attesting the prose still "
            "implements CHANGED source material; the verdict is journaled, say why.\n")
        return 2

    try:
        layout, config = bootstrap()
        load_engine_schema(config)
        leaves = load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code

    # ── --change：union view 渲染到 preview（正式 docs 零寫入，D2/G2）──
    if args.change is not None:
        return _render_change(layout, args)

    if not any(lf.article == args.article for lf in leaves):
        sys.stderr.write(f"docspec: no leaf sections found for article \"{args.article}\"\n")
        return 1

    # 壞帳本閘（D3）：隔離備份＋拒跑；--rebaseline 才放行重建。
    rc = _guard_ledger_health(layout, args.article, args.rebaseline)
    if rc is not None:
        return rc

    # 帳本版本閘：舊版本值與現行算法不可比——逐軸比對必然全紅＝假 stale 風暴；靜默以新算法
    # 重蓋＝吸收待處理信號。故常規 render 拒跑（非零退出、帳本與交付物零改動）、指示顯式一次遷移。
    if ledger_needs_migration(layout, args.article) and not args.rebaseline:
        sys.stderr.write(
            f"docspec: the fingerprint ledger of \"{args.article}\" is an older fingerprint "
            "version — its values are not comparable with the current algorithms, so per-axis "
            "staleness would be a false-stale storm.\n"
            "  refusing to render (nothing was changed). Migrate once with "
            f"`docspec render {args.article} --rebaseline`: every axis is recomputed with the "
            "current algorithms and the prose is preserved. NOTE: any stale signals pending at "
            "migration time are absorbed into the new baseline — review `docspec status` "
            "concerns first if that matters.\n")
        return 1

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

    if args.rebaseline:
        # 吸收警語（D7 誠實代價）：rebaseline 把遷移/重建當下未處理的 stale 信號吸收成新基準。
        sys.stderr.write(
            "docspec: --rebaseline — recomputing every fingerprint axis with the current "
            "algorithms; prose is preserved, but any pending stale signals (and redraft flags) "
            "are absorbed into the new baseline.\n")

    result = render_article(layout, leaves, args.article, ack_sections=set(args.ack),
                            ack_own_sections=set(args.ack_own), reason=args.reason or "",
                            rebaseline=args.rebaseline)
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
    if result.get("ack_owned"):
        print(f"  ack-own (own/deps re-stamped over a CHANGED source; anc/style kept): "
              f"{', '.join(result['ack_owned'])}")
        # 加重版責任註記：--ack 證言「散文與沒動的內容仍對齊」；--ack-own 證言「散文仍實現
        # **已變更**的源料」——語義風險高一級，導向 factcheck 覆檢（非阻塞、永不 gate）。
        print("  ↳ you are ATTESTING these sections' prose still implements the CHANGED source "
              "material — a stronger claim than --ack, and the ledger cannot verify it. Run a "
              "factcheck review over them (non-blocking, but expected).")
    if result.get("ack_own_skipped"):
        sys.stderr.write(
            "docspec: ⚠ --ack-own skipped for (no ledger entry — an unwritten section is draft's "
            f"work, there is nothing to acknowledge): {', '.join(result['ack_own_skipped'])}\n")
    if result.get("ack_refused"):
        sys.stderr.write(
            "docspec: ⚠ --ack refused for (these are stale-own/upstream — rewrite the prose, "
            f"don't acknowledge): {', '.join(result['ack_refused'])}\n")
    return 0
