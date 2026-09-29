"""check：引擎的硬閘與索引脊椎（結構，非語義）。

三檢查（照 engine-spec §5）：①id 唯一 ②死引用 ③循環。
全綠 → 吐 id 索引（status / instructions / publish 重用）。
語義對不對一律不在此驗（→ audit，永不當引擎閘門）。
"""

from __future__ import annotations

from dspx.engine.model import Leaf
from dspx.engine.schema import Schema

from . import (
    _audit,
    _authored,
    _changes,
    _cross_section,
    _cycles,
    _fieldmap,
    _groups,
    _hierarchy,
    _hygiene,
    _ids_and_refs,
    _images,
    _prose_anchors,
    _roadmap,
)
from ._fieldmap import run_file_check
from ._types import CheckResult, IdRecord, Index

__all__ = ["run_check", "run_file_check", "CheckResult", "IdRecord", "Index"]


def run_check(leaves: list[Leaf], schema: Schema, layout=None) -> CheckResult:
    errors: list[str] = []
    index = Index(sections=[leaf.section for leaf in leaves])

    seen, id_errors = _ids_and_refs.collect_ids(leaves)          # ①
    errors.extend(id_errors)
    index.ids = seen                                              # Index construction is
                                                                   # orchestration-level, not
                                                                   # inside collect_ids

    id_set = set(seen)                                                        # for _validate_audit's
    concept_ids = {t for t, rec in seen.items() if rec.kind == "concept"}     # call only — mirrors
                                                                               # check_dead_references'
                                                                               # own internal derivation;
                                                                               # this is a SEPARATE copy
                                                                               # in the orchestrator's
                                                                               # own scope because
                                                                               # _validate_audit (⑤) is
                                                                               # a sibling call, not
                                                                               # something
                                                                               # check_dead_references
                                                                               # can hand back
    gov_decisions = None
    if layout is not None:
        from dspx.engine.governance import (GovernanceError, decision_index_entries,
                                             validate as _validate_gov)
        try:
            gov_decisions = decision_index_entries(layout)
        except GovernanceError:         # 壞封條等：由 ⑬ 回報，這裡不重複炸
            gov_decisions = {}
        from dspx.engine.software.links import requirement_index_entries
        gov_decisions = {**requirement_index_entries(layout), **gov_decisions}   # req:（軟體需求）
    errors.extend(_ids_and_refs.check_dead_references(leaves, seen, gov_decisions))  # ②

    errors.extend(_cycles._detect_supersede_cycle(leaves))                    # ③
    errors.extend(_cycles._detect_governs_cycle(leaves))
    errors.extend(_fieldmap._validate_fields(leaves, schema))                 # ④
    if layout is not None:
        errors.extend(_audit._validate_audit(layout, leaves, id_set, concept_ids))  # ⑤ — own `if layout`
    errors.extend(_hierarchy._check_hierarchy(leaves))                       # ⑦ — unconditional
    if layout is not None:
        from dspx.engine.glossary import load_glossary, validate_glossary          # ⑥ — unchanged inline
        errors.extend(validate_glossary(load_glossary(layout)))
        errors.extend(_roadmap._validate_roadmap(layout, leaves, id_set, concept_ids))  # ⑧ — same `if layout`
        errors.extend(_images._validate_image_refs(layout, leaves))         # ⑨ — same `if layout`
        errors.extend(_groups._validate_groups(layout, leaves))             # ⑩ — group.yaml 輕量驗證
        errors.extend(_prose_anchors.check_prose_anchor_refs(layout, leaves, seen))  # ⑪ — 散文錨死引用（P1b）
        errors.extend(_changes._validate_changes(layout, leaves, id_set, concept_ids))  # ⑫ — changes/ 容器（change-event-layer 1.4）
        errors.extend(_validate_gov(layout))                                 # ⑬ — 治理層紀錄（governance/）
        from dspx.engine import governance as _gv
        if _gv.has_governance(layout):
            from dspx.engine.roadmap_v2 import validate_refs
            try:
                errors.extend(validate_refs(layout, leaves, _gv.load_governance(layout)))
            except _gv.GovernanceError:
                pass                                                         # 壞封條已由 ⑬ 回報
        from dspx.engine.software import validate_all as _validate_sw
        sw_errors, sw_warnings = _validate_sw(layout)                        # ⑭ — 軟體領域（software/）
        errors.extend(sw_errors)

    ref_errors, warnings = _cross_section._cross_section_decision_refs(leaves)  # trailing F1 check
    errors.extend(ref_errors)
    if layout is not None:
        warnings.extend(_hygiene._scan_hygiene(layout))   # 衛生 WARN（衝突副本/死資料夾，非阻塞）
        warnings.extend(_authored.check_inherited_conflicts(leaves))   # ★#27 繼承信封矛盾（非阻塞）
        warnings.extend(_authored.check_authored_state(layout, leaves))  # ★#6.2b 手寫規定檔帶狀態
        warnings.extend(_roadmap._roadmap_id_collisions(layout, leaves))  # B5 活躍/封存撞號（非阻塞）
        warnings.extend(sw_warnings)                                          # ⑭ 軟體領域提醒（大小、未結異議）

    return CheckResult(ok=not errors, errors=errors, index=index, warnings=warnings)
