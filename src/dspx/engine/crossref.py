"""跨文件反向索引：把既有正向 staleness 邊反轉成「影響圖」（同源不漂）。

引擎已有一張完整的跨文件真相圖，但只被**正向**走（staleness：「我為什麼髒＝誰變了害到我」）。
本模組補**反向**遍歷（impact：「我改了會害到誰」）——不是新資料模型，是既有邊的反向鄰接表：

| 正向邊（`model.py`）                              | 反向＝影響                              |
|---|---|
| deps：leaf → 它 realize 的決策（`realized_statements`／`decision_index`） | 決策 → 誰 realize 它（stale-upstream） |
| anc/norm：leaf → 祖先（`ancestor_leaves`）        | 節 → 子孫（stale-inherited / stale-norm） |
| 散文錨：節散文 → target-id（`iter_prose_anchor_ids`） | target → 誰指向它（跨參考）            |

三張反向表**全部複用正向的解析函式**（`decision_index` 的同一套 id、`ancestor_leaves` 的同一
祖先集、check 掃錨的同一趟 `iter_article_prose_anchors`）＝反向視圖不可能與引擎真正據以行動的
正向 staleness 漂移。純加法、零儲存改動、跑現有散檔。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dspx.engine.model import Leaf, ancestor_leaves


@dataclass
class ReverseIndices:
    """三張反向鄰接表 ＋ 交付物 render 覆蓋面（供 reverse_anchor 誠實回報）。"""

    # decision/history id → 反向 realize 它的 leaf 們（純 corpus）
    reverse_realizes: dict[str, list[Leaf]] = field(default_factory=dict)
    # section 路徑 → 以它為祖先（路徑父鏈 ∪ governed-by 遞移）的子孫 leaf 們（純 corpus）
    descendants: dict[str, list[Leaf]] = field(default_factory=dict)
    # target id（concept.id / decision id）→ 散文錨指向它的 [(article, section)]（需 render）
    reverse_anchor: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    # 已 render（掃得到錨）與未 render（跨參考算不出、非空集＝無引用）的文章
    rendered_articles: list[str] = field(default_factory=list)
    unrendered_articles: list[str] = field(default_factory=list)


def build_reverse_indices(leaves: list[Leaf], layout=None) -> ReverseIndices:
    """回三張反向表。全部複用正向解析函式＝與正向 staleness 同源、不漂。

    - `reverse_realizes`：對每個 leaf、每個 `leaf.concept["realizes"]` 反登記（決策身份用與
      `decision_index`／check 同一套 str(id)）。純 corpus。
    - `descendants`：對每個 leaf 呼叫**既有** `ancestor_leaves`（路徑父鏈 ∪ governed-by 遞移閉包，
      與 aperture／staleness 共用同一函式）再反轉——不另寫遍歷邏輯，確保 `X∈descendants` ⟺
      `X∈ancestor_leaves(leaf)` 精確互為反向。純 corpus。
    - `reverse_anchor`：搭 check 掃錨的**同一趟** `iter_article_prose_anchors`（單一遍歷實作，
      check 死引用與此反登記共用），零第二套掃描邏輯。錨住在已 render 的散文裡，故連帶回報
      哪些文章尚未 render（跨參考算不出＝明確回報，不以空集假裝無引用）。需 `layout`。
    """
    reverse_realizes: dict[str, list[Leaf]] = {}
    for leaf in leaves:
        if leaf.concept is None:
            continue
        for rid in (leaf.concept.get("realizes") or []):
            reverse_realizes.setdefault(str(rid), []).append(leaf)

    by_section = {lf.section: lf for lf in leaves}
    concept_by_id = {lf.concept["id"]: lf for lf in leaves
                     if lf.concept and lf.concept.get("id")}
    descendants: dict[str, list[Leaf]] = {}
    for leaf in leaves:
        for anc, _is_governed in ancestor_leaves(leaf.section, by_section, concept_by_id):
            descendants.setdefault(anc.section, []).append(leaf)

    reverse_anchor: dict[str, list[tuple[str, str]]] = {}
    rendered: list[str] = []
    unrendered: list[str] = []
    if layout is not None:
        from dspx.check._prose_anchors import iter_article_prose_anchors
        hits, rendered, unrendered = iter_article_prose_anchors(layout, leaves)
        for article, section, anchor_id in hits:
            reverse_anchor.setdefault(anchor_id, []).append((article, section))

    return ReverseIndices(
        reverse_realizes=reverse_realizes,
        descendants=descendants,
        reverse_anchor=reverse_anchor,
        rendered_articles=rendered,
        unrendered_articles=unrendered,
    )
