"""check ⑩：group.yaml 輕量驗證（corpus-fail-loud-batch）。

group.yaml＝分組節點的可選在地化標題/排序（render 讀 title/order）。壞檔曾實測讓中文
標題**靜默**降級成英文 slug——這裡把「可解析、title 是字串、order 是數值、order 不與
同層兄弟撞號」入 check 硬閘（皆機械可判、非語義）。
"""

from __future__ import annotations

import yaml

GROUP_FILE = "group.yaml"


def _validate_groups(layout, leaves: list) -> list[str]:
    """驗證 corpus 內全部（非封存）group.yaml；回傳錯誤字串清單。"""
    errors: list[str] = []
    if not layout.corpus_dir.is_dir():
        return errors

    # 同層兄弟的已宣告 order（撞號比對面）：leaf 的 concept.order。
    leaf_order: dict[str, float] = {
        lf.section: lf.order for lf in leaves
        if lf.concept is not None and isinstance(lf.concept.get("order"), (int, float))
        and not isinstance(lf.concept.get("order"), bool)
    }

    group_order: dict[str, float] = {}   # group section -> 宣告的 order
    for gy in sorted(layout.corpus_dir.rglob(GROUP_FILE)):
        if layout.is_archived_path(gy.parent):
            continue
        sec = layout.section_id(gy.parent)
        where = f"corpus/{sec}/{GROUP_FILE}"
        try:
            data = yaml.safe_load(gy.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None)
            position = f" (line {mark.line + 1})" if mark is not None else ""
            errors.append(f"{where}: YAML parse failed{position}")
            continue
        if data is None:
            continue
        if not isinstance(data, dict):
            errors.append(f"{where}: top level must be a mapping (title:/order:)")
            continue
        title = data.get("title")
        if title is not None and (not isinstance(title, str) or not title.strip()):
            errors.append(f"{where}: title must be a non-empty string, got {title!r}")
        order = data.get("order")
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
