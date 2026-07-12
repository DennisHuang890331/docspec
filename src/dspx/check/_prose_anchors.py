"""check：散文交叉引用錨的死引用（engine-completeness-gate，P1b）。

散文回引改綁穩定錨（`<!--@<id>-->`，號碼 render 注入）後，跨文件引用第一次可驗——手寫的
字面 `§9.2` 引擎從來驗不了（正是 SC-renumber 94–107 處失錨要多輪 audit 才發現的根因）。這裡
把散文錨的目標 id 收進與 realizes/governed-by 同一類的死引用守門：指向不存在或已退役的 id
＝ERROR，附散文位置（`docs/<article>/_latest.md § <section>`）與失效 id。

只在散文 span 內認錨（`iter_prose_anchor_ids`；code fence/inline code/URL 內的錨樣式不算引用）。
"""

from __future__ import annotations

from dspx.engine.model import Leaf

from ._types import IdRecord

# 退場（不可被引用）狀態：decision/concept 的死狀態集（與 model._DEAD_DECISION_STATUSES 同源精神）。
_RETIRED_STATUSES = ("superseded", "deprecated", "retired")


def _is_retired(rec: IdRecord) -> bool:
    """該 id 是否已退役＝不可被散文引用（已搬進 history，或狀態屬退場集）。"""
    return rec.kind == "history" or (rec.status in _RETIRED_STATUSES)


def iter_article_prose_anchors(
    layout, leaves: list[Leaf],
) -> tuple[list[tuple[str, str, str]], list[str], list[str]]:
    """掃全交付物散文的每個錨綁定＝**單一遍歷實作**（check 死引用與 crossref 反向索引共用）。

    讀 `docs/<article>/_latest.md`，沿隱形章節標記切段取每節散文，只在散文 span 內認錨綁定
    （`iter_prose_anchor_ids`；code fence／inline code／URL／圖路徑內的錨樣式不算引用）。回：
    - `hits`：`[(article, section, anchor_id)]`，依出現序、每（節,id）去重一次；
    - `rendered`：有 `_latest.md`（掃得到錨）的文章；
    - `unrendered`：尚未 render 的文章（錨住散文裡＝無交付物就無資料，跨參考算不出，
      呼叫端據此**明確回報**、不以空集假裝無引用）。

    抽成單一 helper 讓「怎麼掃錨」只有一份實作——check 的死引用守門與 crossref 的
    reverse_anchor 反登記共用它，不會兩處各寫一套而漂移（同源）。"""
    from dspx.engine.render import iter_prose_anchor_ids, parse_section_bodies

    hits: list[tuple[str, str, str]] = []
    rendered: list[str] = []
    unrendered: list[str] = []
    for article in sorted({lf.article for lf in leaves}):
        latest = layout.docs_latest(article)
        if not latest.is_file():
            unrendered.append(article)
            continue
        rendered.append(article)
        bodies = parse_section_bodies(latest.read_text(encoding="utf-8"))
        for section, body in bodies.items():
            seen_here: set[str] = set()
            for anchor_id, _offset in iter_prose_anchor_ids(body):
                if anchor_id in seen_here:
                    continue            # 同節同 id 只算一次
                seen_here.add(anchor_id)
                hits.append((article, section, anchor_id))
    return hits, rendered, unrendered


def check_prose_anchor_refs(layout, leaves: list[Leaf],
                            seen: dict[str, IdRecord]) -> list[str]:
    """收每篇交付物散文的錨 id，指向不存在/退役 id＝ERROR（同 realizes/governed-by 死引用類）。

    掃錨走共用的 `iter_article_prose_anchors`（未 render＝無交付物＝無錨可驗，跳過）；報錯指名
    散文位置與失效 id。"""
    errors: list[str] = []
    hits, _rendered, _unrendered = iter_article_prose_anchors(layout, leaves)
    for article, section, anchor_id in hits:
        where = f"docs/{article}/_latest.md § {section}"
        rec = seen.get(anchor_id)
        if rec is None:
            errors.append(
                f"{where}: prose cross-reference anchor points to nonexistent id "
                f"\"{anchor_id}\" (dead reference — repoint to a live section/decision id "
                f"or drop the anchor)")
        elif _is_retired(rec):
            errors.append(
                f"{where}: prose cross-reference anchor points to a retired id "
                f"\"{anchor_id}\" (it now lives in {rec.section} as {rec.kind}, status "
                f"{rec.status} — repoint to its live successor or drop the anchor)")
    return errors
