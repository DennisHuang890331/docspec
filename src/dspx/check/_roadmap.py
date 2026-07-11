"""check：roadmap.yaml 結構驗證（⑧，per-doc + forest；需 layout/leaves 脈絡）。"""

from __future__ import annotations

from dspx.model import Leaf

from ._cycles import _find_cycle


def _promoted_to_errors(where: str, promoted_to, change_states: dict[str, str],
                        roadmap_ids: set[str] | None = None) -> list[str]:
    """promoted-to 反查（★G6，roadmap 與 audit 共用）：
    - 指向 ACTIVE/ARCHIVED change → 健康（空清單）；
    - 指向 ABANDONED change → 孤兒 ERROR（內容凍在 `_abandoned/`，引擎不自動復活）；
    - roadmap_ids 給定且 promoted_to 命中其一 → 健康（finding 晉升為 roadmap entry 的路徑）；
    - 其餘（不存在的 change id、也不是任何現行 roadmap id）→ 死指標 ERROR。"""
    pid = str(promoted_to)
    if roadmap_ids is not None and pid in roadmap_ids:
        return []
    state = change_states.get(pid)
    if state in ("active", "archived"):
        return []
    if state == "abandoned":
        return [f"{where}: promoted-to points at an abandoned change \"{pid}\" -- its content is "
                f"frozen in changes/_abandoned/{pid}/; resurrect the change or re-point promoted-to "
                "(the engine never auto-resurrects)"]
    return [f"{where}: promoted-to points to a nonexistent change/roadmap id \"{pid}\""]


def _validate_roadmap(layout, leaves: list[Leaf], id_set: set[str],
                      concept_ids: set[str]) -> list[str]:
    """roadmap.yaml 結構閘（跟 concept/decisions 同級：結構查、語義/「做不做」不查）：
    - 欄位/enum/id 唯一/已退休欄（roadmap.validate_roadmap）；
    - depends-on 死引用（指 roadmap id）＋環（DAG，比照 governs）；
    - target 死引用（section id 要存在）＋放對檔（per-doc 檔的 target 必須落該文件樹內或其
      root；`forest` target 只能在 forest 檔）；
    - from-audit 死引用（指現行 audit finding id）；
    - promoted-to 反查（★G6：active/archived 健康、abandoned 孤兒 ERROR、死指標 ERROR）。
    死引用會讓 derive 的 unblocked 算錯 → 違「引擎＝可信索引」，故 check 硬擋。"""
    from dspx import roadmap as _roadmap

    entries = _roadmap.all_entries(layout, leaves)
    if not entries:
        return []
    errs: list[str] = _roadmap.validate_roadmap(entries)

    # section 識別：concept id ∪ section 路徑（target 可是任一）。
    section_paths = {leaf.section for leaf in leaves}
    # 每篇文章的 section id 集合（concept id ＋ section 路徑），供 per-doc 放置判定。
    article_targets: dict[str, set[str]] = {}
    for leaf in leaves:
        art = leaf.article
        bucket = article_targets.setdefault(art, set())
        bucket.add(leaf.section)
        if leaf.concept_id:
            bucket.add(str(leaf.concept_id))

    roadmap_ids = {str(e["id"]) for e in entries if e.get("id")}

    # ── depends-on 死引用 + 環 ──
    graph: dict[str, list[str]] = {}
    for e in entries:
        eid = e.get("id")
        if not eid:
            continue
        deps = e.get("depends-on") or []
        if not isinstance(deps, list):
            deps = [deps]
        graph.setdefault(str(eid), [])
        for d in deps:
            if str(d) not in roadmap_ids:
                errs.append(f"roadmap[{eid}]: depends-on points to nonexistent roadmap id \"{d}\"")
            else:
                graph[str(eid)].append(str(d))
    errs.extend(_find_cycle(graph, "roadmap depends-on"))

    # ── target 死引用 + 放對檔 ──
    for e in entries:
        eid = e.get("id", "?")
        store = e.get("_store", "")
        target = e.get("target")
        if not isinstance(target, str) or not target.strip():
            continue  # 形式錯誤已由 validate_roadmap 報
        if target == _roadmap.FOREST_TARGET:
            if store != "forest":
                errs.append(f"roadmap[{eid}]: target=forest can only go in the forest file"
                            f" (currently in {store})")
            continue
        # target 是 section id（concept id 或 section 路徑）→ 必須存在
        if target not in id_set and target not in section_paths and \
                target not in concept_ids:
            errs.append(f"roadmap[{eid}]: target points to nonexistent section id \"{target}\"")
            continue
        # 放對檔：section/root target 必須落在該文件的 doc 檔
        if store == "forest":
            errs.append(f"roadmap[{eid}]: section target \"{target}\" should not go in the forest file"
                        f" (per-doc work goes in corpus/<article>/roadmap.yaml)")
        elif store.startswith("doc:"):
            art = store[len("doc:"):]
            if target not in article_targets.get(art, set()):
                errs.append(f"roadmap[{eid}]: target \"{target}\" is not within document \"{art}\"'s tree"
                            f" (a per-doc file may only hold targets within that document's tree or its root)")

    # ── from-audit 死引用（指現行 audit finding id；per-doc + forest）──
    from dspx.audit import all_findings as _all_findings
    audit_ids: set[str] = {str(f["id"]) for f in _all_findings(layout, leaves)
                           if f.get("id")}
    for e in entries:
        fa = e.get("from-audit")
        if fa and str(fa) not in audit_ids:
            errs.append(f"roadmap[{e.get('id', '?')}]: from-audit points to nonexistent "
                        f"audit finding id \"{fa}\"")

    # ── promoted-to 反查（★G6：roadmap entry 永遠指向一個 change id）──
    from dspx import change as _chg
    change_states = _chg.all_change_states(layout)
    for e in entries:
        pt = e.get("promoted-to")
        if pt:
            errs.extend(_promoted_to_errors(f"roadmap[{e.get('id', '?')}]", pt, change_states))

    return errs
