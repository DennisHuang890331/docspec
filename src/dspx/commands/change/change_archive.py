"""change archive 交易（D3）：驗全綠＋fork 漂移守門 → corpus/森林級/外部檔落地 →
move 此刻才跑正式 mv（★G3）→ 交付每篇各自判路落地（slot 補丁／整份換，★G5）→ 正式帳本重算 →
搬 _archive/ → roadmap prune → audit WARN。交易順序定死、冪等、中途失敗報告已完成步驟。
"""

from __future__ import annotations

import sys

from dspx.engine import change as chg


def run_archive(layout, schema, change: "chg.Change", *, override_drift: bool = False) -> int:
    # ① 驗全綠（每個 target 導出 done）
    statuses = chg.derive_change_status(layout, change, schema)
    if not chg.is_archivable(statuses):
        sys.stderr.write(f"docspec: change \"{change.id}\" is not archivable — these targets are "
                         "not done:\n")
        for s in statuses:
            if not s.done:
                sys.stderr.write(f"  ✗ [{s.action}] {s.ref}: {s.detail}\n")
        sys.stderr.write("  (fix them, or `docspec change archive <id> --abandon --reason <r>`)\n")
        return 1

    # ② fork 漂移守門（★#9 / D5）
    drift = chg.fork_drift(layout, change)
    if drift and not override_drift:
        sys.stderr.write(f"docspec: change \"{change.id}\" archive aborted — a forked official file "
                         "drifted since staging (a zero-change direct edit or another change "
                         "archived first):\n")
        for d in drift:
            sys.stderr.write(f"  ✗ {d['path']}  (forked {d['forked']} → now {d['current']})\n")
        sys.stderr.write("  reintegrate into staging, or `--override-drift` to land your version "
                         "anyway (no automatic merge exists).\n")
        return 1

    # ── 收集受影響 article + 各 article 的 action 集合（G5 每篇各自判路）──
    from dspx.engine.model import load_project
    union_leaves = chg.load_union(layout, change)
    article_actions: dict[str, set[str]] = {}
    corpus_sections: list[str] = []
    move_targets: list[chg.Target] = []
    file_targets: list[chg.Target] = []
    for t in change.targets:
        if t.kind == "file":
            file_targets.append(t)
            continue
        if t.action == "move":
            move_targets.append(t)
        section = chg.section_of_ref(t.ref, union_leaves)
        if section is None and t.kind == "create":
            section = t.ref
        if section is None:
            continue
        art = section.split("/", 1)[0]
        article_actions.setdefault(art, set()).add(t.action)
        if t.action != "move":
            corpus_sections.append(section)

    # 本單顯式 target 的節集合（★2.2：非此集、卻被 rebaseline 靜默轉 synced 的下游要列名）
    target_sections: set[str] = set(corpus_sections)
    for t in move_targets:
        msec = chg.section_of_ref(t.ref, union_leaves)
        if msec:
            target_sections.add(msec)
        if t.dest:
            target_sections.add(t.dest)

    done_steps: list[str] = []
    absorbed: list[tuple[str, str]] = []
    try:
        # ③ corpus 章節落地正式 corpus（backend 路由：散檔整檔搬回／store 結構化 merge-by-id）
        for section in corpus_sections:
            chg.land_corpus_section(layout, change, section, schema)
        if corpus_sections:
            done_steps.append(f"landed {len(corpus_sections)} corpus section(s)")

        # ④ 森林級檔（glossary/writing-guide/config）整檔搬回
        forest_landed = _land_forest_files(layout, change)
        if forest_landed:
            done_steps.append(f"landed forest-level file(s): {', '.join(forest_landed)}")

        # ⑤ 外部 file target 整檔搬回 + 跑 validator
        for t in file_targets:
            official = layout.project_root / t.ref
            if chg.land_file(layout, change, official):
                done_steps.append(f"landed file target {t.ref}")
                if t.validator:
                    _run_validator(t.validator, official)

        # ⑥ move：此刻才對正式面跑真正的 mv（★G3）
        for t in move_targets:
            rc = _run_move(layout, schema, t, union_leaves)
            if rc != 0:
                raise _ArchiveAbort(f"move of \"{t.ref}\" failed")
            done_steps.append(f"moved {t.ref} -> {t.dest}")

        # ⑦ 交付每篇文件各自判路落地（★G5）
        for art, actions in sorted(article_actions.items()):
            structural = actions & {"create", "retire", "move", "redraft"}
            if structural:
                chg.whole_file_replace_deliverable(layout, change, art)
                done_steps.append(f"{art}: whole-file replace ({', '.join(sorted(structural))})")
            else:
                sections = {s for s in corpus_sections if s.split("/", 1)[0] == art}
                # 補丁前 drift 偵測（既有 drifted 語義）：正式 _latest 某 patch 目標格被手改 → 中止交人
                drifted = _drifted_patch_targets(layout, art, sections)
                if drifted and not override_drift:
                    raise _ArchiveAbort(
                        f"{art}: official _latest.md was hand-edited (drifted) at slot(s) "
                        + ", ".join(sorted(drifted)) + " — reconcile the hand-edit, or --override-drift")
                patched = chg.slot_patch_deliverable(layout, change, art, sections)
                done_steps.append(f"{art}: slot patch ({len(patched)} section(s))")

        # ★2.2：rebaseline 前偵測「被本次改動波及、但非本單 target」的下游節——它們現在 stale，
        #   下一步 rebaseline 會把它們**靜默**重戳 synced（未經本次顯式復驗）。先列名、archive 不阻塞。
        absorbed = _silently_absorbed_downstream(layout, schema,
                                                 set(article_actions.keys()), target_sections)

        # ⑧ 正式帳本重算（等效 rebaseline、散文即剛收案內容）
        from dspx.engine.render import render_article
        official_leaves = load_project(layout)
        for art in sorted(article_actions.keys()):
            if any(lf.article == art for lf in official_leaves):
                render_article(layout, official_leaves, art, rebaseline=True)
        done_steps.append("recomputed official ledgers")

    except _ArchiveAbort as exc:
        sys.stderr.write(f"docspec: change \"{change.id}\" archive aborted mid-transaction: {exc}\n")
        if done_steps:
            sys.stderr.write("  steps already completed (fix-forward, corpus already landed):\n")
            for s in done_steps:
                sys.stderr.write(f"    - {s}\n")
        return 1

    # ⑨ 案卷搬 _archive/（凍結）
    chg.move_to_state(layout, change, chg.STATE_ARCHIVED)

    # ⑩ roadmap prune（晉升 entry 掉出——案卷即完工紀錄）
    pruned = _prune_promoted_roadmap(layout, change)

    # ⑪ audit WARN：晉升來源 finding 未 close（非阻塞）
    _warn_unclosed_audit(layout, change)

    print(f"archived change \"{change.id}\": {change.dir}")
    for s in done_steps:
        print(f"  · {s}")
    if pruned:
        print(f"  · pruned roadmap entry {pruned}")

    # ★2.2：列名被 rebaseline 靜默轉 synced 的非 target 下游（未經本次顯式復驗）——非阻塞 WARN。
    if absorbed:
        sys.stderr.write(
            f"docspec: ⚠ change \"{change.id}\" recomputed {len(absorbed)} downstream section(s) to "
            "synced that were NOT explicit targets of this change (not re-verified this change — "
            "the rebaseline absorbed their inherited staleness):\n")
        for sec, sync in absorbed:
            sys.stderr.write(f"    · {sec}  (was {sync})\n")
        sys.stderr.write("  if any needs real re-verification, open a follow-up change targeting it "
                         "(or docspec stale <section> it).\n")
    return 0


def _silently_absorbed_downstream(layout, schema, articles: set, target_sections: set) -> list:
    """★2.2：收案落地上游後、rebaseline 前，哪些**非本單 target** 的下游節現在 stale？
    這些節接著會被 rebaseline 靜默重戳 synced（未經本次顯式復驗）。回 [(section, sync)]。"""
    from dspx.commands.query.status import _docs_hashes, _leaf_row
    from dspx.engine.model import decision_index, load_project
    leaves = load_project(layout)
    by = {lf.section: lf for lf in leaves}
    dindex = decision_index(leaves)
    out: list = []
    for art in sorted(articles):
        dh = _docs_hashes(layout, art)
        for lf in leaves:
            if lf.article != art or lf.section in target_sections:
                continue
            sync = _leaf_row(layout, lf, schema, True, dh, by, dindex)["sync"]
            if isinstance(sync, str) and sync.startswith("stale"):
                out.append((lf.section, sync))
    return out


class _ArchiveAbort(Exception):
    pass


def _land_forest_files(layout, change) -> list[str]:
    """森林級檔（glossary.yaml/writing-guide.md/config.yaml）若在 staging 則整檔搬回。"""
    landed: list[str] = []
    for name, official in (
            ("glossary.yaml", layout.planning_home / "glossary.yaml"),
            ("writing-guide.md", layout.writing_guide),
            ("config.yaml", layout.planning_home / "config.yaml")):
        if chg.land_file(layout, change, official):
            landed.append(name)
    return landed


def _run_move(layout, schema, t: "chg.Target", leaves) -> int:
    """收案時對正式面跑真正的 docspec mv（含全部路徑引用重寫）。"""
    if not t.dest:
        sys.stderr.write(f"docspec: move target \"{t.ref}\" has no --dest; cannot mv.\n")
        return 1
    section = chg.section_of_ref(t.ref, leaves) or t.ref
    from dspx.commands.corpus.mv import _run_section_mode
    return _run_section_mode(layout, schema, section, t.dest)


def _drifted_patch_targets(layout, article: str, sections: set[str]) -> set[str]:
    from dspx.engine.render import detect_drift
    drifted = {d["section"] for d in detect_drift(layout, article)}
    return drifted & sections


def _run_validator(cmd: str, path) -> None:
    import subprocess
    try:
        subprocess.run(cmd.split() + [str(path)], check=False)
    except Exception as exc:   # noqa: BLE001 — validator 失敗非阻塞、只提示
        sys.stderr.write(f"docspec: ⚠ file target validator \"{cmd}\" failed to run: {exc}\n")


def _prune_promoted_roadmap(layout, change) -> str | None:
    """收案時 prune 指向本 change 的 roadmap promoted-to entry（案卷即完工紀錄）。"""
    import yaml
    from dspx.reports import roadmap as rm
    candidates = [rm.forest_roadmap_path(layout)]
    if layout.corpus_dir.is_dir():
        for art in layout.articles():
            candidates.append(rm.doc_roadmap_path(layout, art))
    for path in candidates:
        if not path.is_file():
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        entries = data.get("entries") if isinstance(data, dict) else None
        if not isinstance(entries, list):
            continue
        keep = [e for e in entries
                if not (isinstance(e, dict) and str(e.get("promoted-to")) == change.id)]
        if len(keep) != len(entries):
            pruned_id = next((str(e.get("id")) for e in entries
                              if isinstance(e, dict) and str(e.get("promoted-to")) == change.id), None)
            data["entries"] = keep
            path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                            encoding="utf-8", newline="\n")
            return pruned_id
    return None


def _warn_unclosed_audit(layout, change) -> None:
    """晉升自 audit finding 的 change 收案時，若該 finding 仍 open → 非阻塞 WARN（audit 永不 gate、
    archive 永不代結案）。"""
    if not change.promoted_from:
        return
    from dspx.reports.audit import all_findings
    from dspx.engine.model import load_project
    fid = change.promoted_from
    for f in all_findings(layout, load_project(layout)):
        if str(f.get("id")) == fid and f.get("status") == "open":
            sys.stderr.write(
                f"docspec: ⚠ change \"{change.id}\" traces to audit finding \"{fid}\" which is still "
                "open — archive proceeds, but closing the finding stays an audit/factcheck act "
                "(audit never gates, archive never closes findings).\n")
            return
