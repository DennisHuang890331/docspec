"""check：引擎的硬閘與索引脊椎（結構，非語義）。

三檢查（照 engine-spec §5）：①id 唯一 ②死引用 ③循環。
全綠 → 吐 id 索引（status / instructions / publish 重用）。
語義對不對一律不在此驗（→ audit，永不當引擎閘門）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from dspx.model import Leaf
from dspx.schema import Schema

# 佔位字（必填字串若整值是這些＝視同未填）：TODO/TBD/FIXME 整詞，或 <…>/{…} 整值包起來
_PLACEHOLDER_RE = re.compile(r"^(?:TODO|TBD|FIXME|<.*>|\{.*\})$", re.IGNORECASE)


@dataclass(frozen=True)
class IdRecord:
    """一個 id 的歸屬。"""

    id: str
    section: str
    kind: str        # concept | decision | history
    status: str | None = None


@dataclass
class Index:
    """check 全綠時產出的索引脊椎。"""

    ids: dict[str, IdRecord] = field(default_factory=dict)        # id -> 歸屬
    sections: list[str] = field(default_factory=list)


@dataclass
class CheckResult:
    ok: bool
    errors: list[str]
    index: Index


def _decision_ids(leaves: list[Leaf]) -> set[str]:
    out: set[str] = set()
    for leaf in leaves:
        for e in leaf.decisions:
            if e.get("id"):
                out.add(str(e["id"]))
        for e in leaf.history:
            if e.get("id"):
                out.add(str(e["id"]))
    return out


def run_check(leaves: list[Leaf], schema: Schema, layout=None) -> CheckResult:
    errors: list[str] = []
    index = Index(sections=[leaf.section for leaf in leaves])

    # ── ① 收集 id + 唯一性（concept.id ∪ decisions.id ∪ history.id）──
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

    index.ids = seen
    id_set = set(seen)
    # governed-by 嚴格守門：目標必須是「活的 concept id」（不能放行 decision/history id）。
    concept_ids = {the_id for the_id, rec in seen.items() if rec.kind == "concept"}

    # ── ② 死引用 ──
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
        check_ref(sec, "concept.realizes", leaf.concept.get("realizes"))
        # governed-by 不能 reuse check_ref：必須是活 concept id，非任意 id（decision/history 不行）。
        gb = leaf.concept.get("governed-by")
        if gb is not None:
            for t in (gb if isinstance(gb, list) else [gb]):
                if str(t) not in concept_ids:
                    errors.append(
                        f"{sec}: concept.governed-by points to a non-concept or nonexistent id \"{t}\""
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

    # ── ③ 循環（supersedes / governs 鏈各自 DFS）──
    errors.extend(_detect_supersede_cycle(leaves))
    errors.extend(_detect_governs_cycle(leaves))

    # ── ④ 欄位級 schema 驗證（每份 yaml 都被欄位檢查）──
    errors.extend(_validate_fields(leaves, schema))
    # ── ⑤ audit.yaml 結構驗證（per-doc + forest；id/status/severity/face/target/放置）──
    if layout is not None:
        errors.extend(_validate_audit(layout, leaves, id_set, concept_ids))
    # ── ⑦ 結構性層級不變量（root-brief 完整 / 兄弟 order 唯一 / supersede 一致性）──
    #    （history.md 改為「可選散文細節、乾淨 ## <id> 對應、非硬綁」——舊的破折號雙向
    #     binding check 已移除；孤兒散文段交 lint 提醒，不當 check 硬閘。）
    errors.extend(_check_hierarchy(leaves))
    # ── ⑥ glossary.yaml 驗證（若有 layout）──
    if layout is not None:
        from dspx.glossary import load_glossary, validate_glossary
        errors.extend(validate_glossary(load_glossary(layout)))
        # ── ⑧ roadmap.yaml 驗證（per-doc + forest；需 layout/leaves 脈絡）──
        errors.extend(_validate_roadmap(layout, leaves, id_set, concept_ids))

    return CheckResult(ok=not errors, errors=errors, index=index)


def _is_empty(val: object) -> bool:
    """空但在：空字串/純空白、空 list、空 dict 都算未填。"""
    if val is None:
        return True
    if isinstance(val, str):
        return val.strip() == ""
    if isinstance(val, (list, dict)):
        return len(val) == 0
    return False


def _type_ok(val: object, typ: str | None) -> bool:
    if typ == "string":
        return isinstance(val, str)
    if typ == "number":
        return isinstance(val, (int, float)) and not isinstance(val, bool)
    if typ in ("list", "list[ref]"):
        return isinstance(val, list)
    if typ == "object":
        return isinstance(val, dict)
    if typ in ("enum", "ref"):
        return isinstance(val, str)
    return True  # 未知 type：不判


def _check_fieldmap(obj: dict, fieldmap: dict, where: str) -> list[str]:
    """依 schema 欄位定義驗：必填空但在/佔位字、型別、enum、巢狀 object 遞迴。
    （結構完整性，非語義；required 的「空但在」是 P0 修正的核心。）"""
    errs: list[str] = []
    for fname, spec in (fieldmap or {}).items():
        if not isinstance(spec, dict):
            continue
        required = bool(spec.get("required"))
        typ = spec.get("type")
        present = fname in obj and obj[fname] is not None
        # ① 必填：缺失 or 空但在 → 擋
        if required and (not present or _is_empty(obj[fname])):
            errs.append(f"{where}: required field \"{fname}\" missing or empty")
            continue
        if not present:
            continue
        val = obj[fname]
        # ② 型別
        if typ and not _type_ok(val, typ):
            errs.append(f"{where}: \"{fname}\" should be type {typ}, got {type(val).__name__}")
            continue
        # ③ 佔位字（必填字串整值＝佔位 → 視同未填）
        if required and isinstance(val, str) and _PLACEHOLDER_RE.match(val.strip()):
            errs.append(f"{where}: required field \"{fname}\" is a placeholder \"{val}\" (not filled in)")
        # ④ enum
        if typ == "enum" and spec.get("values") and val not in spec["values"]:
            errs.append(f"{where}: \"{fname}\" value \"{val}\" not in {spec['values']}")
        # ⑤ 巢狀 object sub-schema → 遞迴（如 brief）。**只在非空時遞迴**：
        #    brief:{} ＝整塊省略（＝繼承），不觸發子欄必填；寫了非空 brief 才要求填滿信封。
        if typ == "object" and isinstance(spec.get("fields"), dict) and isinstance(val, dict) and val:
            errs.extend(_check_fieldmap(val, spec["fields"], f"{where}.{fname}"))
    return errs


def run_file_check(leaf: Leaf, schema: Schema) -> list[str]:
    """單節欄位級完整性（required 空/佔位、型別、enum、巢狀 sub-schema）。
    **只看這一節自己**——無 id 唯一/死引用/循環（那些是跨節，屬全專案 check）。
    給 status（ready vs developing）與 PostToolUse hook 重用。"""
    errs: list[str] = []
    concept_art = schema.by_id("concept")
    decisions_art = schema.by_id("decisions")
    history_art = schema.by_id("history")
    if leaf.concept is not None and concept_art and concept_art.schema:
        errs.extend(_check_fieldmap(leaf.concept, concept_art.schema,
                                    f"{leaf.section}/concept.yaml"))
    if decisions_art and decisions_art.schema:
        for e in leaf.decisions:
            errs.extend(_check_fieldmap(e, decisions_art.schema,
                                        f"{leaf.section}/decisions[{e.get('id','?')}]"))
    if history_art and history_art.schema:
        for e in leaf.history:
            errs.extend(_check_fieldmap(e, history_art.schema,
                                        f"{leaf.section}/history[{e.get('id','?')}]"))
    return errs


def _validate_fields(leaves: list[Leaf], schema: Schema) -> list[str]:
    errs: list[str] = []
    for leaf in leaves:
        errs.extend(run_file_check(leaf, schema))
    return errs


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


def _validate_roadmap(layout, leaves: list[Leaf], id_set: set[str],
                      concept_ids: set[str]) -> list[str]:
    """roadmap.yaml 結構閘（跟 concept/decisions 同級：結構查、語義/「做不做」不查）：
    - 欄位/enum/id 唯一（roadmap.validate_roadmap）；
    - depends-on 死引用（指 roadmap id）＋環（DAG，比照 governs）；
    - target 死引用（section id 要存在）＋放對檔（per-doc 檔的 target 必須落該文件樹內或其
      root；`forest` target 只能在 forest 檔）；
    - from-audit 死引用（指現行 audit finding id）。
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

    return errs


def _check_hierarchy(leaves: list[Leaf]) -> list[str]:
    """結構性層級不變量（確定性，複用 section 路徑＋全專案 id index）：
    (a) root-brief 完整——只有 article root（section 無 '/'）必填 audience/depth/breadth；
    (b) 兄弟 order 唯一——同父群組 order 不可撞號（否則 TOC 排序不確定）；
    (c) supersede 一致性——A.supersedes B ⟹ B.status∈{superseded,deprecated} 且 B.superseded-by==A。
    語義（子是否真的窄於父等）不在此——那是 audit。"""
    errs: list[str] = []
    required_brief = ("audience", "depth", "breadth")
    by_parent: dict[str, dict] = {}
    entry_by_id: dict[str, dict] = {}
    for leaf in leaves:
        for e in (*leaf.decisions, *leaf.history):
            if e.get("id"):
                entry_by_id[str(e["id"])] = e

    for leaf in leaves:
        if leaf.concept is None:
            continue
        sec = leaf.section
        # (a) root-brief 完整（root＝section 無 '/'；子節省略＝繼承，不查）
        if "/" not in sec:
            brief = leaf.concept.get("brief")
            if not isinstance(brief, dict):
                errs.append(f"{sec}: root section missing brief (root must fill in the writing envelope; child sections inherit)")
            else:
                for f in required_brief:
                    v = brief.get(f)
                    if v is None or (isinstance(v, str) and not v.strip()):
                        errs.append(f"{sec}: root section brief.{f} missing or empty (root must be fully filled in; child sections inherit)")
        # (b) 兄弟 order 唯一
        order = leaf.concept.get("order")
        if order is not None:
            parent = sec.rsplit("/", 1)[0] if "/" in sec else ""
            grp = by_parent.setdefault(parent, {})
            if order in grp:
                errs.append(f"{sec}: order {order!r} collides with sibling \"{grp[order]}\" -> TOC ordering is nondeterministic")
            else:
                grp[order] = sec

    # (c) supersede 一致性（全專案 id index，非祖先走鏈）
    for leaf in leaves:
        for e in (*leaf.decisions, *leaf.history):
            sup = e.get("supersedes")
            if not sup:
                continue
            a_id = str(e.get("id", "?"))
            b = entry_by_id.get(str(sup))
            if b is None:
                continue                      # 死引用已另報
            if str(b.get("status")) not in ("superseded", "deprecated"):
                errs.append(f"{leaf.section}: \"{a_id}\" supersedes \"{sup}\", but \"{sup}\""
                            f" status should be superseded/deprecated (currently {b.get('status')})")
            if str(b.get("superseded-by") or "") != a_id:
                errs.append(f"{leaf.section}: \"{sup}\"'s superseded-by should point back to \"{a_id}\""
                            f" (currently {b.get('superseded-by')!r})")
    return errs


def _detect_supersede_cycle(leaves: list[Leaf]) -> list[str]:
    # 圖：decision id -> 它 supersedes 的 id
    graph: dict[str, list[str]] = {}
    for leaf in leaves:
        for e in (*leaf.decisions, *leaf.history):
            eid = e.get("id")
            if not eid:
                continue
            sup = e.get("supersedes")
            graph.setdefault(str(eid), [])
            if sup:
                graph[str(eid)].append(str(sup))
    return _find_cycle(graph, "supersedes")


def _detect_governs_cycle(leaves: list[Leaf]) -> list[str]:
    # 圖：concept id -> 它 governed-by 解析到的 concept id（跨樹環 A 治 B、B 治 A 要擋）
    graph: dict[str, list[str]] = {}
    for leaf in leaves:
        if leaf.concept is None:
            continue
        cid = leaf.concept.get("id")
        if not cid:
            continue
        targets = leaf.concept.get("governed-by") or []
        if not isinstance(targets, list):
            targets = [targets]
        graph[str(cid)] = [str(t) for t in targets]
    return _find_cycle(graph, "governs")


def _find_cycle(graph: dict[str, list[str]], label: str) -> list[str]:
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {n: WHITE for n in graph}
    errors: list[str] = []

    def visit(node: str, stack: list[str]) -> None:
        color[node] = GRAY
        for nxt in graph.get(node, []):
            if nxt not in color:  # 指到圖外（死引用已另報）
                continue
            if color[nxt] == GRAY:
                cycle = " → ".join(stack + [node, nxt])
                errors.append(f"{label} cycle: {cycle}")
            elif color[nxt] == WHITE:
                visit(nxt, stack + [node])
        color[node] = BLACK

    for n in graph:
        if color[n] == WHITE:
            visit(n, [])
    return errors
