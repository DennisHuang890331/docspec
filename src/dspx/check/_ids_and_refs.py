"""check：id 收集/唯一性（①）＋死引用/realizes/governed-by liveness（②）。"""

from __future__ import annotations

from dspx.engine.model import Leaf

from ._types import IdRecord


def collect_ids(leaves: list[Leaf]) -> tuple[dict[str, IdRecord], list[str]]:
    """① 收集 id + 唯一性（concept.id ∪ decisions.id ∪ history.id）。"""
    errors: list[str] = []
    seen: dict[str, IdRecord] = {}

    def claim(the_id: str, section: str, kind: str, status: str | None) -> None:
        if not the_id:
            return
        if the_id in seen:
            prev = seen[the_id]
            errors.append(
                f"{section}:{the_id} duplicate id (already claimed by {prev.kind} in {prev.section})"
            )
            return
        seen[the_id] = IdRecord(id=the_id, section=section, kind=kind, status=status)

    for leaf in leaves:
        if leaf.concept is None:
            errors.append(f"{leaf.section}: concept.yaml missing or empty")
            continue
        cid = leaf.concept.get("id")
        if not cid:
            errors.append(f"{leaf.section}: concept.yaml missing id")
        else:
            claim(str(cid), leaf.section, "concept", leaf.concept.get("status"))

        for e in leaf.decisions:
            eid = e.get("id")
            if not eid:
                errors.append(f"{leaf.section}: decisions entry missing id: {e!r}")
                continue
            claim(str(eid), leaf.section, "decision", e.get("status"))
        for e in leaf.history:
            eid = e.get("id")
            if not eid:
                errors.append(f"{leaf.section}: history entry missing id: {e!r}")
                continue
            claim(str(eid), leaf.section, "history", e.get("status"))

    return seen, errors


def check_dead_references(leaves: list[Leaf], seen: dict[str, IdRecord]) -> list[str]:
    """② 死引用（realizes/governed-by 的 liveness 守門 ＋ 泛用 check_ref）。"""
    errors: list[str] = []
    id_set = set(seen)
    # governed-by 嚴格守門：目標必須是「活的 concept id」（不能放行 decision/history id）。
    concept_ids = {the_id for the_id, rec in seen.items() if rec.kind == "concept"}
    # 退場 concept（status=deprecated）不可被繼承——被治理子會默默錨在已宣告退場的真相上（M3）。
    deprecated_concept_ids = {the_id for the_id, rec in seen.items()
                              if rec.kind == "concept" and rec.status == "deprecated"}

    def check_ref(section: str, where: str, target: object) -> None:
        if target is None:
            return
        targets = target if isinstance(target, list) else [target]
        for t in targets:
            t = str(t)
            if t not in id_set:
                errors.append(f"{section}: {where} points to nonexistent id \"{t}\"")

    for leaf in leaves:
        if leaf.concept is None:
            continue
        sec = leaf.section
        # realizes 不能 reuse check_ref：目標必須是「存在的決策（kind=decision）」。指向 history
        # （已 retire）的死決策＝下游默默錨在搬進 history 的死真相上（FG-1）；指向 concept＝錯邊
        # 類型（治理用 governed-by）。superseded-but-present 刻意放行＝過渡遷移窗，由 staleness
        # （deps_fingerprint 納 status）＋ aperture 前景化負責，不卡死下游整份 check。
        rz = leaf.concept.get("realizes")
        if rz is not None:
            for t in (rz if isinstance(rz, list) else [rz]):
                t = str(t)
                rec = seen.get(t)
                if rec is None:
                    errors.append(f"{sec}: concept.realizes points to nonexistent id \"{t}\"")
                elif rec.kind == "history":
                    errors.append(
                        f"{sec}: concept.realizes points to a retired decision \"{t}\" "
                        f"(it now lives in history — repoint to its live successor or drop the edge)"
                    )
                elif rec.kind == "concept":
                    errors.append(
                        f"{sec}: concept.realizes points to a concept id \"{t}\" "
                        f"(realizes is for a shared decision; use governed-by for inherited governance)"
                    )
        # governed-by 不能 reuse check_ref：必須是活 concept id，非任意 id（decision/history 不行）。
        gb = leaf.concept.get("governed-by")
        if gb is not None:
            for t in (gb if isinstance(gb, list) else [gb]):
                if str(t) not in concept_ids:
                    errors.append(
                        f"{sec}: concept.governed-by points to a non-concept or nonexistent id \"{t}\""
                    )
                elif str(t) in deprecated_concept_ids:
                    errors.append(
                        f"{sec}: concept.governed-by points to a deprecated concept \"{t}\" "
                        f"(a retired concept cannot be inherited — repoint to a live concept or drop the governance)"
                    )
        for e in leaf.decisions:
            eid = e.get("id", "?")
            check_ref(sec, f"decisions[{eid}].supersedes", e.get("supersedes"))
            check_ref(sec, f"decisions[{eid}].superseded-by", e.get("superseded-by"))
            trace = e.get("trace") or {}
            if isinstance(trace, dict):
                check_ref(sec, f"decisions[{eid}].trace.governs", trace.get("governs"))
                check_ref(sec, f"decisions[{eid}].trace.refs", trace.get("refs"))
        for e in leaf.history:
            eid = e.get("id", "?")
            check_ref(sec, f"history[{eid}].superseded-by", e.get("superseded-by"))

    return errors
