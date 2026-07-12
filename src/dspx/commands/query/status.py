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
    ancestor_normative_fingerprint,
    decision_index,
    deps_fingerprint,
    style_fingerprint,
)
from dspx.schema import Schema

NAME = "status"
HELP = "section structure overview: per section files present / writable / synced or stale"


def section_state(leaf: Leaf, schema: Schema, check_ok: bool) -> str:
    """每節狀態（status 與 list 共用）。
    ready 需「concept 齊、欄位完整（per-section run_file_check）、全專案 check 綠」；
    develop.md 還在 or 必填未齊 → developing（不擋寫、draft 不選）。
    decisions.yaml 缺席＝合法空（該節無自有裁決）＝不降級（contract-slimming D2）。"""
    # backend-neutral：concept 存在＝模型有 concept（store leaf 無實體 concept.yaml，散檔 leaf
    # 由 leaf_dirs 保證有）；develop 存在＝leaf.has_develop（散檔在 leaf.dir、store 在 work/）。
    has_concept = leaf.concept is not None
    if leaf.has_develop:
        return "developing"
    if not has_concept:
        return "waiting(missing:concept)"
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


# style 子軸 → 對人輸出的載體名（診斷指名哪個 doctrine 載體動了；標籤仍統一 stale-style）
_STYLE_CARRIER_NAMES = {"guide": "writing-guide", "gloss": "glossary", "purpose": "purpose"}


def _style_carriers_moved(rec_style, style_now: dict) -> list[str]:
    """比對帳本 style mapping 與現值，回「動了的載體」名單（診斷用）。非 mapping（防禦）→ 空。"""
    if not isinstance(rec_style, dict):
        return []
    return [_STYLE_CARRIER_NAMES[k] for k in ("guide", "gloss", "purpose")
            if rec_style.get(k) != style_now.get(k)]


def compute_sync(layout: Layout, leaf: Leaf, recorded, by_section: dict, dindex: dict,
                 deliverable_missing: bool = False,
                 needs_migration: bool = False) -> tuple[str, list[str]]:
    """一節的同步狀態（sync）＋（若 stale-style）動了的 doctrine 載體名單。
    抽成獨立函式讓 status 與 instructions（apply 模式投影）共用同一判準——避免 sync
    優先序在兩處重寫而漂移（鐵律2）。回 (sync, style_moved)。"""
    style_moved: list[str] = []
    if recorded is None:
        return "unwritten", style_moved
    if deliverable_missing:
        # 存在性互驗（corpus-fail-loud-batch D2）：帳本有記錄但交付檔不見了——
        # 「曾經有交付物、現在缺席」＝必然異常，不得以帳本指紋照算 synced/stale。
        return "deliverable-missing", style_moved
    if needs_migration:
        # 帳本版本閘（fingerprint v2 D7）：v1 舊值與 v2 算法現值不可比——逐軸比對必然全紅
        # ＝假 stale 風暴，也不得報 synced。顯 needs-migration、文章級指示 --rebaseline。
        return "needs-migration", style_moved
    # 相容舊格式（str=只有 own）與新格式（{own, anc, deps, norm, style}）
    rec_own = recorded.get("own") if isinstance(recorded, dict) else recorded
    rec_anc = recorded.get("anc") if isinstance(recorded, dict) else None
    rec_deps = recorded.get("deps") if isinstance(recorded, dict) else None
    rec_norm = recorded.get("norm") if isinstance(recorded, dict) else None
    rec_style = recorded.get("style") if isinstance(recorded, dict) else None
    own_now = leaf.source_hash()
    anc_now = ancestor_brief_fingerprint(leaf.section, by_section)
    deps_now = deps_fingerprint(leaf, dindex)
    norm_now = ancestor_normative_fingerprint(leaf.section, by_section)
    style_now = style_fingerprint(layout)
    # 優先序 own > upstream > norm > inherited > style：規矩失守比敘事框架移動嚴重、
    # 但仍在「散文必須重寫」（own/upstream）之下——norm 變更常見結局是「散文合法、ack 即清」。
    if isinstance(recorded, dict) and recorded.get("redraft"):
        # 標髒旗標（docspec stale / redraft）：在 own 比對**前**投影成 stale-own——
        # apply（rewrite）的 pickup 集合（stale-own）零改動接手；散文真重寫（render 重算）或
        # render --ack-own 才清旗標。舊帳本無此鍵＝行為不變（零遷移）。
        return "stale-own", style_moved
    if rec_own != own_now:
        return "stale-own", style_moved          # 自己的源改了 → apply rewrite 重渲染
    if rec_deps is not None and rec_deps != deps_now:
        return "stale-upstream", style_moved     # realizes 的共享真相改了 → apply rewrite 重渲染
    if rec_norm is not None and rec_norm != norm_now:
        return "stale-norm", style_moved         # 祖先 active normative（規矩）改了 → apply align 逐句核對
    if rec_anc is not None and rec_anc != anc_now:
        return "stale-inherited", style_moved    # 只有祖先 brief 改了 → apply align 敘事性對齊
    if rec_style is not None and rec_style != style_now:
        # 寫作 doctrine（writing-guide/glossary/purpose）改了 → apply align 就地重套風格/對齊術語
        return "stale-style", _style_carriers_moved(rec_style, style_now)
    return "synced", style_moved


def _leaf_row(layout: Layout, leaf: Leaf, schema: Schema, check_ok: bool,
              docs_hashes: dict, by_section: dict, dindex: dict,
              deliverable_missing: bool = False,
              needs_migration: bool = False) -> dict:
    # backend-neutral 檔旗標：由模型判在（store leaf 無實體檔），不再靠 leaf.dir 存在性。
    has_concept = leaf.concept is not None
    has_decisions = bool(leaf.decisions)
    recorded = docs_hashes.get(leaf.section)
    sync, style_moved = compute_sync(layout, leaf, recorded, by_section, dindex,
                                     deliverable_missing=deliverable_missing,
                                     needs_migration=needs_migration)

    state = section_state(leaf, schema, check_ok)

    row = {
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
    if style_moved:
        row["styleMoved"] = style_moved
    return row


def _print_active_changes_overview(layout: Layout, schema: Schema) -> None:
    """status 頂部顯示 active changes 概觀（task 5.2）：id｜完成數/總數｜archivable。
    無 active change 時零輸出差異。"""
    from dspx import change as chg
    changes = chg.iter_active_changes(layout)
    if not changes:
        return
    print("── active changes (in flight) ──")
    for change in changes:
        statuses = chg.derive_change_status(layout, change, schema)
        done_n = sum(1 for s in statuses if s.done)
        tag = " (archivable)" if chg.is_archivable(statuses) else ""
        print(f"  {change.id}  {done_n}/{len(statuses)}{tag}  {change.title}")
    print()


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

    from dspx.render import (detect_drift, groups_fingerprint, ledger_needs_migration,
                             read_ledger_groups)
    hashes_by_article: dict[str, dict] = {}
    drift_by_article: dict[str, set] = {}
    missing_by_article: dict[str, bool] = {}
    migration_by_article: dict[str, bool] = {}
    skeleton_stale: list[str] = []
    rows = []
    for leaf in shown:
        if leaf.article not in hashes_by_article:
            hashes_by_article[leaf.article] = _docs_hashes(layout, leaf.article)
            drift_by_article[leaf.article] = {
                d["section"] for d in detect_drift(layout, leaf.article)}
            # 存在性互驗（D2）：帳本非空 ∧ 交付檔缺席 → 全文章各節顯 deliverable-missing
            missing_by_article[leaf.article] = bool(
                hashes_by_article[leaf.article]) and not layout.docs_latest(leaf.article).is_file()
            # 帳本版本閘（fingerprint v2 D7）：v1 帳本＝各節 needs-migration、不逐軸比對。
            migration_by_article[leaf.article] = ledger_needs_migration(layout, leaf.article)
            # group.yaml 骨架面（D4）：帳本記的 groups 指紋 vs 現值不符＝改了 title/order
            # 但交付物還是舊骨架 → 需 render（舊帳本無 groups 欄＝無信號，下次 render 補記）。
            recorded_groups = read_ledger_groups(layout, leaf.article)
            if (recorded_groups is not None
                    and recorded_groups != groups_fingerprint(layout, leaf.article)):
                skeleton_stale.append(leaf.article)
        row = _leaf_row(layout, leaf, schema, check_ok,
                        hashes_by_article[leaf.article], by_section, dindex,
                        deliverable_missing=missing_by_article[leaf.article],
                        needs_migration=migration_by_article[leaf.article])
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

    needs_migration_articles = sorted(a for a, m in migration_by_article.items() if m)

    # 分組節點列（吸收原 `docspec list` 唯一多出的能力）：concept-less 的 group 目錄，
    # 帶 group.yaml 在地化標題/order。--section 指到單一 leaf 時不列 group。
    from dspx.render import _group_order, _group_title, outline_group_nodes
    group_rows: list[dict] = []
    if not args.section:
        for gs in outline_group_nodes(leaves):
            if args.article and gs.split("/", 1)[0] != args.article:
                continue
            group_rows.append({
                "section": gs, "article": gs.split("/", 1)[0],
                "title": _group_title(layout, gs, gs.rsplit("/", 1)[-1]),
                "order": _group_order(layout, gs)})

    if args.as_json:
        print(json.dumps({"checkOk": check_ok, "sections": rows,
                          "groups": group_rows,
                          "skeletonStale": skeleton_stale,
                          "needsMigration": needs_migration_articles},
                         ensure_ascii=False, indent=2))
        return 0

    if not rows:
        print("corpus is empty (no leaf sections yet). Use docspec new <section> to create the first one.")
        return 0

    _print_active_changes_overview(layout, schema)

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
        moved = ("" if not r.get("styleMoved")
                 else " (" + "+".join(r["styleMoved"]) + " moved)")
        print(f"  {r['section']:<28} {r['state']:<16} {r['sync']:<16} [{flags}]{moved}{drift}")
    for art in skeleton_stale:
        print(f"\n  ⚠ deliverable skeleton of \"{art}\" is stale: a group.yaml title/order "
              f"changed since the last render — run docspec render {art}")
    if any(r["sync"] == "deliverable-missing" for r in rows):
        print("\n  ⚠ deliverable-missing: the rendered file was deleted but the ledger still has "
              "records — restore it from git/Drive history, or run "
              "`docspec render <article> --rebaseline` to rebuild explicitly")
    for art in needs_migration_articles:
        print(f"\n  ⚠ needs-migration: the fingerprint ledger of \"{art}\" is an older fingerprint "
              "version (its values are not comparable with the current algorithms, so no per-axis "
              f"staleness is shown) — migrate once with `docspec render {art} --rebaseline` (prose "
              "is preserved; pending stale signals are absorbed into the new baseline)")
    if group_rows:
        print("\n  group nodes (concept-less grouping folders; title from group.yaml):")
        for g in group_rows:
            order = "" if g["order"] is None else f"  order={g['order']}"
            print(f"    [group] {g['section']}/ — {g['title']}{order}")
    print("\n  flags: c=concept d=decisions m=material v=develop h=history")
    print("  (sync is state; the single apply skill routes its own mode from it — "
          "docspec instructions apply <section> projects the mode + verb)")
    return 0
