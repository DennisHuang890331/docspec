"""check：F1 跨節決策引用未接結構邊（機械切片，非阻塞導向 realizes/governed-by）。"""

from __future__ import annotations

import re

from dspx.model import Leaf


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


def _cross_section_decision_refs(leaves: list[Leaf]) -> tuple[list[str], list[str]]:
    """F1：機械切片——某節**明引**別節某決策的 id，卻無對應 `realizes`/`governed-by` 結構邊。

    唯有結構邊進 deps/anc 指紋、使過期鏈生效；只寫進散文的依賴對 staleness 隱形（supersede→
    下游 false-green）。回傳 `(errors, warnings)`，依「id 出現在哪」分級：

    - **id 出現在 `concept.sources`** → **ERROR**。`sources` 契約上只放**外部出處**（標準/論文/
      資料集／"Author's design"），出現專案內部 decision id ＝鐵定填錯欄位；逆迫作者改用
      `realizes:`/`governed-by:`（內部依賴的家）。大型文件最致命的無聲陷阱就在這格，故 fail-loud。
    - **id 出現在 concept 散文 / 本節決策 statement** → **WARN**（非阻塞導向）。散文可合法順帶提及，
      故只提醒、不擋。

    兩者皆限縮在確定性可判的訊號：精確 token 比對專案真實存在的 decision id 集（非語義推斷）。純人話
    描述（無真實 id）不在此攔——那是 factcheck/audit 的語義範疇。
    """
    # id → 擁有它的節；concept id → 節（供 governed-by 解析到「被治理的節」）
    id_owner: dict[str, str] = {}
    concept_section: dict[str, str] = {}
    for leaf in leaves:
        for e in (*leaf.decisions, *leaf.history):
            if e.get("id"):
                id_owner[str(e["id"])] = leaf.section
        if leaf.concept and leaf.concept.get("id"):
            concept_section[str(leaf.concept["id"])] = leaf.section

    errors: list[str] = []
    warnings: list[str] = []
    for leaf in leaves:
        if not leaf.concept:
            continue
        realized = {str(x) for x in (leaf.concept.get("realizes") or [])}
        # governed-by 指 concept id → 解析成「被治理的節」集；引用其決策即視為已結構化
        governed_sections = {
            concept_section[str(g)] for g in (leaf.concept.get("governed-by") or [])
            if str(g) in concept_section
        }
        sources_text = "\n".join(str(s) for s in (leaf.concept.get("sources") or []))
        prose_parts: list[str] = []
        if isinstance(leaf.concept.get("concept"), str):
            prose_parts.append(leaf.concept["concept"])
        for e in leaf.decisions:   # 本節決策 statement（不掃 material：草稿料、噪音高）
            if isinstance(e.get("statement"), str):
                prose_parts.append(e["statement"])
        prose_text = "\n".join(prose_parts)
        for did, owner in id_owner.items():
            if owner == leaf.section:
                continue                      # 自己的決策、非跨節
            if did in realized or owner in governed_sections:
                continue                      # 已用結構邊覆蓋＝依賴可見、非無聲（即使 id 也出現在文字裡）
            # token 比對：id 是獨立 token（前後非 word/hyphen），不誤判為更長 id 的子串
            token = r"(?<![\w-])" + re.escape(did) + r"(?![\w-])"
            if sources_text and re.search(token, sources_text):
                errors.append(
                    f"{leaf.section}: concept.sources names internal decision id \"{did}\" "
                    f"(owned by {owner}) — sources is for external provenance only; express this "
                    f"dependency with concept.realizes/governed-by so staleness tracks it"
                )
            elif prose_text and re.search(token, prose_text):
                warnings.append(
                    f"{leaf.section}: references decision \"{did}\" (owned by {owner}) "
                    f"only in prose — add concept.realizes/governed-by so staleness tracks it"
                )
    return errors, warnings
