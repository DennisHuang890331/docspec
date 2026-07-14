"""docspec change — 修改事件容器的生命週期指令（new / add-target / status / archive）。

狀態＝位置＋導出（無 status 欄、引擎獨占寫 change.yaml）。archive 是唯一人閘（執行＝接受）；
退回＝繼續改讓導出自動變不綠（無獨立 accept/return 機制）。詳見 change-container /
change-staging spec 與 design D1–D8。
"""

from __future__ import annotations

import argparse
import sys

from dspx.engine import change as chg
from dspx.commands._shared import (BootstrapError, bootstrap, load_engine_schema,
                                    load_model)

NAME = "change"
HELP = ("modification event container: change new / add-target / status / archive "
        "(staging draft-branch, derived acceptance, two-route landing)")


# ── change new ────────────────────────────────────────────────────────

def _cmd_new(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="docspec change new")
    p.add_argument("id", help="change id (lowercase alphanumeric with '-'; becomes changes/<id>/)")
    p.add_argument("--seed", action="append", default=[], metavar="REF",
                   help="a decision id, concept id, or term:<glossary-term> the change stems from "
                        "(repeatable); auto targets are snapshotted from reverse-realizes")
    p.add_argument("--publish", choices=list(chg.PUBLISH_POLICIES), default=None,
                   help="publish policy (REQUIRED, no default): advisory (WARN) | release-bound (block)")
    p.add_argument("--title", default=None, help="one-line title (defaults to the id)")
    p.add_argument("--why", default="", help="why this change exists (one line; fill notes.md for detail)")
    p.add_argument("--from-roadmap", default=None, metavar="ENTRY-ID",
                   help="promote a roadmap entry: move its content into the change, collapse the "
                        "entry to a promoted-to pointer (move, don't copy)")
    p.add_argument("--from-audit", default=None, metavar="FINDING-ID",
                   help="lineage back to an audit finding (archive prints a WARN if still open)")
    args = p.parse_args(argv)

    reason = chg.validate_id(args.id)
    if reason:
        sys.stderr.write(f"docspec: refusing to create change \"{args.id}\": {reason}\n")
        return 2
    if args.publish is None:
        sys.stderr.write(
            "docspec: change new requires --publish advisory|release-bound (fail-loud, no default "
            "— the publish policy is a mandatory declaration, not an afterthought).\n")
        return 2

    try:
        layout, config = bootstrap()
        load_engine_schema(config)
        leaves = load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code

    if chg.change_state(layout, args.id) is not None:
        sys.stderr.write(f"docspec: change \"{args.id}\" already exists "
                         f"({chg.change_state(layout, args.id)}); not overwritten.\n")
        return 2

    cdir = chg.change_dir(layout, args.id, chg.STATE_ACTIVE)
    change = chg.Change(
        id=args.id,
        title=args.title or args.id,
        why=args.why,
        created=chg.now_date(),
        publish=args.publish,
        seeds=list(args.seed),
        dir=cdir,
    )

    # ── 晉升搬家（--from-roadmap）：搬內容進 change、原 entry 收攏為 promoted-to（不複製）──
    promoted_note = ""
    if args.from_roadmap:
        moved = _promote_roadmap(layout, args.from_roadmap, change)
        if moved is None:
            sys.stderr.write(f"docspec: roadmap entry \"{args.from_roadmap}\" not found "
                             "(cannot promote).\n")
            return 1
        change.promoted_from = args.from_roadmap
        promoted_note = moved
    if args.from_audit:
        change.promoted_from = change.promoted_from or args.from_audit

    # ── auto targets 快照（D6，一跳）──
    autos: list[chg.Target] = []
    blind_terms: list[str] = []
    for seed in args.seed:
        if seed.startswith("term:"):
            blind_terms.append(seed[len("term:"):])
            continue
        for t in chg.auto_targets_for_seed(layout, leaves, seed):
            if change.target_by_ref(t.ref) is None:
                change.targets.append(t)
                autos.append(t)

    cdir.mkdir(parents=True, exist_ok=True)
    chg.notes_path(cdir).write_text(
        f"# {change.title}\n\n{change.why}\n\n" + (promoted_note or ""),
        encoding="utf-8", newline="\n")
    # 入單標髒每個 auto target（★2.3）：staging 化＋preview 帳本標 stale。
    for t in autos:
        section = chg.section_of_ref(t.ref, leaves)
        if section is not None:
            chg.stage_section(change, layout, section)
            chg.enlist_stale(layout, change, section)
    chg.save_change(change)

    print(f"created change \"{args.id}\" ({args.publish}): {chg.change_yaml_path(cdir)}")
    print(f"  notes: {chg.notes_path(cdir)}")
    if autos:
        print(f"  auto targets ({len(autos)}, reverse-realizes; staged + enlist-staled):")
        for t in autos:
            print(f"    [{t.action}] {t.ref}")
    else:
        print("  no auto targets from seeds — add them with `docspec change add-target`.")
    # ★2.1 通用引用型下游提示：以散文錨引用 seed（不硬寫值）的 auto target，改動未必需重寫，
    #   可 remove-target 免除誤卡導出完成度（避免 byte-identical 被反作弊拒收）。
    generic = _generic_reference_autos(layout, leaves, autos, args.seed)
    if generic:
        print(f"  ↳ generic-reference downstream ({len(generic)}): "
              + ", ".join(generic) + " — their prose cites the seed by anchor (no hardwired value), "
              "so a value change may not require rewriting them. If a target does not actually "
              f"change, drop it: `docspec change remove-target {args.id} <ref>`.")
    # 盲區提醒（投影、不落檔）
    print("  ↳ blind-spot reminder: auto targets cover only reverse-realizes. Add MANUAL targets "
          "for prose cross-references, figures, schemas, and file targets the engine cannot see "
          "(docspec change add-target).")
    if blind_terms:
        print(f"  ↳ term seed(s) {', '.join(blind_terms)}: run "
              f"`docspec edit --term <old> <new> --dry-run` to find prose hits, then add-target them.")
    return 0


def _generic_reference_autos(layout, leaves, autos: list, seeds: list[str]) -> list[str]:
    """★2.1：哪些 auto target 是「通用引用型下游」＝其散文以穩定錨引用某 seed（不硬寫值）。

    signal＝reverse_anchor[seed] 含該 auto target 的 (article, section)＝它的散文錨指向 seed。
    未 render 的文章算不出錨（reverse_anchor 空）＝不誤報（誠實不提示）。回傳 ref 清單。"""
    from dspx.engine.crossref import build_reverse_indices
    seed_ids = [s for s in seeds if not s.startswith("term:")]
    if not seed_ids or not autos:
        return []
    ri = build_reverse_indices(leaves, layout)
    flagged: list[str] = []
    for t in autos:
        section = chg.section_of_ref(t.ref, leaves)
        if section is None:
            continue
        article = section.split("/", 1)[0]
        if any((article, section) in ri.reverse_anchor.get(sid, []) for sid in seed_ids):
            flagged.append(t.ref)
    return flagged


def _promote_roadmap(layout, entry_id: str, change: "chg.Change") -> str | None:
    """晉升搬家：把 roadmap entry 的 what 搬進 change.notes、原 entry 收攏成 promoted-to。
    回傳搬進 notes 的一段文字（None＝找不到 entry）。"""
    from dspx.reports import roadmap as rm
    from dspx.engine.sealed import load_sealed
    # 找 entry 所在檔（forest + per-doc）；★store-native：讀寫皆走密封 API，不裸寫。
    candidates = [rm.forest_roadmap_path(layout)]
    if layout.corpus_dir.is_dir():
        for art in layout.articles():
            candidates.append(rm.doc_roadmap_path(layout, art))
    for path in candidates:
        if not path.is_file():
            continue
        _rev, entries = load_sealed(path, list_key="entries", error_cls=rm.RoadmapError)
        for i, e in enumerate(entries):
            if isinstance(e, dict) and str(e.get("id")) == entry_id:
                what = str(e.get("what") or e.get("title") or "")
                # 收攏：只留 id/title/promoted-to（搬家不複製）
                entries[i] = {"id": e.get("id"), "title": e.get("title"),
                              "promoted-to": change.id}
                rm._write_entries(path, entries)
                return f"## promoted from roadmap {entry_id}\n\n{what}\n"
    return None


# ── change add-target ─────────────────────────────────────────────────

def _cmd_add_target(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="docspec change add-target")
    p.add_argument("id", help="change id")
    p.add_argument("ref", help="concept.id / section path (existing) | corpus path (create) | "
                               "file path (file) | glossary term (term)")
    p.add_argument("--action", choices=list(chg.ACTIONS), required=True,
                   help="acceptance criterion + apply mode selector")
    p.add_argument("--origin", choices=list(chg.ORIGINS), default="manual")
    p.add_argument("--kind", choices=list(chg.TARGET_KINDS), default="section")
    p.add_argument("--dest", default=None, help="move action: destination section path")
    p.add_argument("--validator", default=None, help="file target: validator command run on landing")
    args = p.parse_args(argv)

    try:
        layout, config = bootstrap()
        load_engine_schema(config)
        leaves = load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code

    if chg.change_state(layout, args.id) != chg.STATE_ACTIVE:
        sys.stderr.write(f"docspec: no active change \"{args.id}\" to add a target to.\n")
        return 1
    change = chg.load_change_at(chg.change_dir(layout, args.id, chg.STATE_ACTIVE),
                                chg.STATE_ACTIVE)
    if change.target_by_ref(args.ref) is not None:
        sys.stderr.write(f"docspec: target \"{args.ref}\" already in change \"{args.id}\".\n")
        return 2

    t = chg.Target(ref=args.ref, action=args.action, origin=args.origin, kind=args.kind,
                   dest=args.dest)

    # ── file target：記 baseline hash（收案時 hash≠baseline＝做過事）──
    if args.kind == "file":
        official = layout.project_root / args.ref
        t.baseline = None
        from dspx.engine.model import content_hash
        if official.is_file():
            t.baseline = content_hash(official)
        t.validator = args.validator
        chg.stage_file(change, layout, official)
    elif args.action == "create":
        t.kind = "create"
        chg.stage_section(change, layout, args.ref)   # 建空節資料夾
    else:
        section = chg.section_of_ref(args.ref, leaves)
        if section is None:
            sys.stderr.write(
                f"docspec: ref \"{args.ref}\" does not resolve to an existing section "
                "(concept.id or section path). For a new section use --action create; for a file "
                "use --kind file.\n")
            return 1
        chg.stage_section(change, layout, section)
        # 入單標髒（★2.3）：revise/align/redraft/review 對 staging 副本標 stale。
        if args.action in ("revise", "align", "redraft", "review"):
            chg.enlist_stale(layout, change, section)

    change.targets.append(t)
    chg.save_change(change)
    print(f"added target to \"{args.id}\": [{t.action}] {t.ref}"
          + (f" -> {t.dest}" if t.dest else ""))
    if t.kind == "file":
        print(f"  staged a copy of {t.ref} (baseline hash recorded; official file untouched).")
    elif args.action == "create":
        print(f"  staged an empty section for {t.ref} (crystallize it in staging).")
    else:
        print("  staged the section's own files into staging + enlist-staled "
              "(status derives it not-done until the prose is rewritten in the preview).")
    return 0


# ── change remove-target ──────────────────────────────────────────────

def _cmd_remove_target(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="docspec change remove-target")
    p.add_argument("id", help="change id")
    p.add_argument("ref", help="the target ref to drop (concept.id / section path / file path)")
    args = p.parse_args(argv)

    try:
        layout, config = bootstrap()
        load_engine_schema(config)
        leaves = load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code

    if chg.change_state(layout, args.id) != chg.STATE_ACTIVE:
        sys.stderr.write(f"docspec: no active change \"{args.id}\".\n")
        return 1
    change = chg.load_change_at(chg.change_dir(layout, args.id, chg.STATE_ACTIVE),
                                chg.STATE_ACTIVE)
    t = change.target_by_ref(args.ref)
    if t is None:
        sys.stderr.write(f"docspec: change \"{args.id}\" has no target \"{args.ref}\".\n")
        return 1

    # 丟棄該 target 的 staging（檔案粒度、不誤刪子節暫存），再自 change 移除。
    if t.kind == "file":
        official = layout.project_root / t.ref
        staged = chg.staging_target(change.dir, layout, official)
        if staged.is_file():
            staged.unlink()
        change.fork_hashes.pop(chg.workspace_rel(layout, official), None)
    else:
        section = chg.section_of_ref(t.ref, leaves)
        if section is None and t.kind == "create":
            section = t.ref
        if section is not None:
            chg.unstage_section(change, layout, section)
    change.targets = [x for x in change.targets if x.ref != t.ref]
    chg.save_change(change)
    print(f"removed target \"{t.ref}\" from change \"{args.id}\" (staging dropped; it no longer "
          "blocks the derived completeness).")
    return 0


# ── change status ─────────────────────────────────────────────────────

def _cmd_status(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="docspec change status")
    p.add_argument("id", nargs="?", default=None, help="change id (omit to list all active changes)")
    p.add_argument("--json", action="store_true", dest="as_json")
    args = p.parse_args(argv)

    try:
        layout, config = bootstrap()
        schema = load_engine_schema(config)
        load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code

    if args.id is None:
        return _list_active(layout, schema, args.as_json)

    state = chg.change_state(layout, args.id)
    if state is None:
        sys.stderr.write(f"docspec: no change \"{args.id}\".\n")
        return 1
    change = chg.load_change(layout, args.id)
    # ★8.5：已收案/已棄案的 change 顯示終態，而非對已消失的 staging 導出 0/N not archivable。
    if state != chg.STATE_ACTIVE:
        label = "ACCEPTED (archived)" if state == chg.STATE_ARCHIVED else "ABANDONED"
        if args.as_json:
            import json
            print(json.dumps({"id": change.id, "state": state, "terminal": label,
                              "targets": len(change.targets)}, ensure_ascii=False, indent=2))
            return 0
        print(f"change \"{change.id}\" [{state}] — {label}; {len(change.targets)} target(s). "
              "The dossier is frozen (acceptance/abandon already happened); no live derivation.")
        if change.abandoned:
            print(f"  reason: {change.abandoned.get('reason')}")
        return 0
    statuses = chg.derive_change_status(layout, change, schema)
    archivable = chg.is_archivable(statuses)
    done_n = sum(1 for s in statuses if s.done)

    if args.as_json:
        import json
        print(json.dumps({
            "id": change.id, "state": change.state, "publish": change.publish,
            "archivable": archivable, "done": done_n, "total": len(statuses),
            "targets": [{"ref": s.ref, "action": s.action, "section": s.section,
                         "done": s.done, "detail": s.detail} for s in statuses],
        }, ensure_ascii=False, indent=2))
        return 0

    print(f"change \"{change.id}\" [{change.state}]  publish={change.publish}  "
          f"{done_n}/{len(statuses)}" + ("  (archivable)" if archivable else ""))
    if change.why:
        print(f"  why: {change.why}")
    for s in statuses:
        mark = "✓" if s.done else "·"
        print(f"  {mark} [{s.action}] {s.ref}  — {s.detail}")
    if not archivable:
        print("  not archivable yet — finish the · targets (or drop them).")
    return 0


def _list_active(layout, schema, as_json: bool) -> int:
    changes = chg.iter_active_changes(layout)
    rows = []
    for change in changes:
        statuses = chg.derive_change_status(layout, change, schema)
        rows.append((change, sum(1 for s in statuses if s.done), len(statuses),
                     chg.is_archivable(statuses)))
    if as_json:
        import json
        print(json.dumps([{"id": c.id, "title": c.title, "publish": c.publish,
                           "done": d, "total": tot, "archivable": arch}
                          for c, d, tot, arch in rows], ensure_ascii=False, indent=2))
        return 0
    if not rows:
        print("no active changes.")
        return 0
    print(f"active changes ({len(rows)}):")
    for c, d, tot, arch in rows:
        tag = " (archivable)" if arch else ""
        print(f"  {c.id}  {d}/{tot}{tag}  {c.title}")
    return 0


# ── change archive (accept) / --abandon ───────────────────────────────

def _cmd_archive(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="docspec change archive")
    p.add_argument("id", help="change id")
    p.add_argument("--abandon", action="store_true", help="drop the change (zero rollback needed)")
    p.add_argument("--reason", default=None, help="required with --abandon")
    p.add_argument("--override-drift", action="store_true",
                   help="land the staged files even though a fork-drifted official file was "
                        "detected (\"land mine anyway\"); by default drift aborts to the human")
    args = p.parse_args(argv)

    try:
        layout, config = bootstrap()
        schema = load_engine_schema(config)
        load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code

    if chg.change_state(layout, args.id) != chg.STATE_ACTIVE:
        st = chg.change_state(layout, args.id)
        sys.stderr.write(
            f"docspec: no active change \"{args.id}\""
            + (f" (it is {st})" if st else "") + ".\n")
        return 1
    change = chg.load_change(layout, args.id)

    if args.abandon:
        return _abandon(layout, change, args.reason)

    from dspx.commands.change.change_archive import run_archive
    return run_archive(layout, schema, change, override_drift=args.override_drift)


def _abandon(layout, change, reason) -> int:
    if not reason:
        sys.stderr.write("docspec: --abandon requires --reason <text>.\n")
        return 2
    # 丟 staging/preview、reason 入 change.yaml、搬 _abandoned/、roadmap 復活提示；正式面零變化。
    import shutil
    for sub in (chg.staging_dir(change.dir), chg.preview_dir(change.dir)):
        if sub.exists():
            shutil.rmtree(sub)
    change.abandoned = {"date": chg.now_date(), "reason": reason}
    chg.save_change(change)
    chg.move_to_state(layout, change, chg.STATE_ABANDONED)
    print(f"abandoned change \"{change.id}\": moved to {change.dir}")
    print("  official corpus and docs are untouched by construction (content never left staging).")
    if change.promoted_from:
        print(f"  ↳ reminder: the promoted source \"{change.promoted_from}\" is now a bare pointer "
              "into an _abandoned dossier — resurrect or re-point that roadmap/audit entry "
              "(the engine will NOT auto-resurrect; docspec check flags the orphan).")
    return 0


# ── dispatch ──────────────────────────────────────────────────────────

_SUB = {
    "new": _cmd_new,
    "add-target": _cmd_add_target,
    "remove-target": _cmd_remove_target,
    "status": _cmd_status,
    "archive": _cmd_archive,
}


def run(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print("docspec change — modification event container\n")
        print("Subcommands (each takes --help for its flags):")
        print("  new <id> --publish <p> [--seed REF ...]   open a change container")
        print("  add-target <id> <ref> --action <a>        enlist a target (stages it + enlist-stales)")
        print("  remove-target <id> <ref>                  drop a target (discards its staging)")
        print("  status [<id>]                             derived per-target acceptance")
        print("  archive <id> [--abandon --reason R]       accept (land) or abandon")
        return 0
    sub, rest = argv[0], argv[1:]
    fn = _SUB.get(sub)
    if fn is None:
        sys.stderr.write(f"docspec change: unknown subcommand \"{sub}\". "
                         f"Valid: {', '.join(_SUB)}\n")
        return 2
    return fn(rest)
