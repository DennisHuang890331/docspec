"""check：audit.yaml 結構驗證（⑤，per-doc-root ＋ forest；結構查，語義不查）。"""

from __future__ import annotations

from dspx.model import Leaf


def _audit_faces(layout) -> tuple[str, ...]:
    """從 project config 取 audit faces（core+packs）；不可用→DEFAULT_FACES。"""
    from dspx.audit import DEFAULT_FACES
    try:
        from dspx.config import load_config
        config = load_config(layout.planning_home)
        audit = config.get("audit") or {}
        core = tuple(audit.get("core") or ())
        packs = tuple((audit.get("packs") or {}).keys())
        faces = core + packs
        return faces or DEFAULT_FACES
    except Exception:
        return DEFAULT_FACES


def _validate_audit(layout, leaves: list[Leaf], id_set: set[str],
                    concept_ids: set[str]) -> list[str]:
    """audit.yaml 結構閘（per-doc-root ＋ forest；結構查、語義/「攻防對不對」不查）：
    - id 全域唯一（跨所有 store）/ status / severity / **face**（補漏：舊 check 漏驗 face）；
    - 每個 target 死引用（section path 或 concept id 要存在）；
    - 放對檔——target 的 distinct 文件數對應 store：1→該文件 doc-root、≥2→forest。
    放錯/死引會讓「audit→roadmap from-audit」與彙總算錯 → 違「引擎＝可信索引」，故 check 硬擋。"""
    from dspx.audit import all_findings, distinct_articles, validate_finding

    faces = _audit_faces(layout)
    findings = all_findings(layout, leaves)
    if not findings:
        return []

    # section 識別：concept id ∪ section 路徑（target 可是任一；§anchor 取 '#' 前段）。
    section_paths = {leaf.section for leaf in leaves}

    errs: list[str] = []
    seen_ids: set[str] = set()
    for f in findings:
        fid = str(f.get("id", "?"))
        store = f.get("_store", "")
        where = f"audit[{fid}] ({store})"
        # 欄位級（id/face/severity/status/finding/targets）——含 face 補漏
        for e in validate_finding(f, faces):
            errs.append(f"{where}: {e}")
        # 全域 id 唯一
        if f.get("id"):
            if fid in seen_ids:
                errs.append(f"{where}: duplicate audit id (global)")
            else:
                seen_ids.add(fid)

        targets = f.get("targets")
        if not isinstance(targets, list) or not targets:
            continue  # 形式錯誤已由 validate_finding 報
        # target 死引用：每個都要解析到真實 section
        for t in targets:
            sec = str(t).split("#", 1)[0]
            if sec not in id_set and sec not in section_paths and sec not in concept_ids:
                errs.append(f"{where}: target points to nonexistent section id \"{t}\"")
        # 放對檔：distinct 文件數對應 store
        arts = distinct_articles(targets, leaves)
        if not arts:
            continue  # 全死引用，上面已報
        if len(arts) >= 2:
            if store != "forest":
                errs.append(f"{where}: a finding spanning {len(arts)} documents must go in the forest "
                            f"audit (currently in {store})")
        else:  # 單文件
            expected = f"doc:{arts[0]}"
            if store != expected:
                errs.append(f"{where}: a single-document finding should go in the {expected} audit"
                            f" (currently in {store})")
    return errs
