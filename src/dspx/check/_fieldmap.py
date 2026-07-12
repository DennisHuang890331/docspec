"""check：欄位級 schema 驗證（④，每份 yaml 都被欄位檢查）＋單節完整性（run_file_check）。"""

from __future__ import annotations

import re

from dspx.engine.model import Leaf
from dspx.engine.schema import Schema

# 佔位字（必填字串若整值是這些＝視同未填）：TODO/TBD/FIXME 整詞，或 <…>/{…} 整值包起來
_PLACEHOLDER_RE = re.compile(r"^(?:TODO|TBD|FIXME|<.*>|\{.*\})$", re.IGNORECASE)


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


def _check_fieldmap(obj: dict, fieldmap: dict, where: str, closed: bool = False) -> list[str]:
    """依 schema 欄位定義驗：必填空但在/佔位字、型別、enum、巢狀 object 遞迴。
    （結構完整性，非語義；required 的「空但在」是 P0 修正的核心。）
    closed=True（fieldmap 已完全列舉）：對 schema 未宣告的未知 key 報 ERROR
    （捕捉發明/打錯的 key——如 brief.diagram——同 dead-ref 一類的機械 drift，鐵律1）。"""
    errs: list[str] = []
    if closed and isinstance(obj, dict):
        unknown = [k for k in obj if k not in (fieldmap or {})]
        for k in sorted(unknown):
            errs.append(f"{where}: unknown field \"{k}\" not in schema "
                        f"(allowed: {', '.join(sorted(fieldmap or {}))})")
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
            errs.extend(_check_fieldmap(val, spec["fields"], f"{where}.{fname}",
                                        closed=bool(spec.get("closed"))))
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
                                    f"{leaf.section}/concept.yaml", closed=concept_art.closed))
    if decisions_art and decisions_art.schema:
        for e in leaf.decisions:
            errs.extend(_check_fieldmap(e, decisions_art.schema,
                                        f"{leaf.section}/decisions[{e.get('id','?')}]",
                                        closed=decisions_art.closed))
    if history_art and history_art.schema:
        for e in leaf.history:
            errs.extend(_check_fieldmap(e, history_art.schema,
                                        f"{leaf.section}/history[{e.get('id','?')}]",
                                        closed=history_art.closed))
    return errs


def _validate_fields(leaves: list[Leaf], schema: Schema) -> list[str]:
    errs: list[str] = []
    for leaf in leaves:
        errs.extend(run_file_check(leaf, schema))
    return errs
