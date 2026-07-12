"""check ⑩：group 記錄輕量驗證（corpus-fail-loud-batch；★store-only）。

group＝分組節點的可選在地化標題/排序（render 讀 title/order），住 `corpus/<article>.yaml`
store 記錄的 `kind: group` 條目。這裡把「title 是字串、order 是數值、order 不與同層兄弟
撞號」入 check 硬閘（皆機械可判、非語義）——store 記錄由 put/tidy/write 產出，型別仍可能
被建構端寫壞（如 title 給 list），故保留型別驗證。
"""

from __future__ import annotations

GROUP_FILE = "group.yaml"   # get/put/報訊息的檔名慣例（store 記錄非實體檔）


def _validate_groups(layout, leaves: list) -> list[str]:
    """驗證全 store 篇的 group 記錄（title/order 型別＋同層 order 撞號）；回傳錯誤字串清單。"""
    from dspx.engine import store as _store
    errors: list[str] = []

    # 同層兄弟的已宣告 order（撞號比對面）：leaf 的 concept.order。
    leaf_order: dict[str, float] = {
        lf.section: lf.order for lf in leaves
        if lf.concept is not None and isinstance(lf.concept.get("order"), (int, float))
        and not isinstance(lf.concept.get("order"), bool)
    }

    group_order: dict[str, float] = {}   # group section -> 宣告的 order
    for art in _store.store_articles(layout):
        art_obj = _store.cached_article(layout, art)
        for rec in (art_obj.group_records() if art_obj is not None else []):
            sec = rec.path
            where = f"corpus/{sec}/{GROUP_FILE}"
            meta = rec.group or {}
            title = meta.get("title")
            if title is not None and (not isinstance(title, str) or not title.strip()):
                errors.append(f"{where}: title must be a non-empty string, got {title!r}")
            order = meta.get("order")
            if order is not None:
                if isinstance(order, bool) or not isinstance(order, (int, float)):
                    errors.append(f"{where}: order must be a number, got {order!r}")
                else:
                    group_order[sec] = float(order)

    # order 撞號：group 宣告的 order vs 同層兄弟（leaf concept.order 或另一 group.yaml order）。
    def _parent(sec: str) -> str:
        return sec.rsplit("/", 1)[0] if "/" in sec else ""

    declared = [(sec, o, "group") for sec, o in group_order.items()] + \
               [(sec, o, "leaf") for sec, o in leaf_order.items()]
    for sec, order, _kind in sorted((s, o, k) for s, o, k in declared if k == "group"):
        for sib, sib_order, sib_kind in declared:
            if sib == sec or _parent(sib) != _parent(sec):
                continue
            if sib_order == order:
                errors.append(
                    f"corpus/{sec}/{GROUP_FILE}: order {order:g} collides with sibling "
                    f"\"{sib}\" ({'group.yaml' if sib_kind == 'group' else 'concept.yaml'} "
                    f"order) — sibling order must be unique or the sort is ambiguous")
    return errors
