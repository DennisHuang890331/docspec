"""check：圖片引用完整性（⑨，交付 _latest.md 的 ![](assets/…) 必須解析到實體圖檔）。"""

from __future__ import annotations

from dspx.model import Leaf


def _validate_image_refs(layout, leaves: list[Leaf]) -> list[str]:
    """圖片引用完整性（fail-loud；backend-neutral）：交付 `_latest.md` 內每個
    `![](assets/…)` 都必須對應到**交付側 `docs/assets/`**（Model A：圖住交付側、非 corpus）下
    實際存在的圖檔。斷掉＝check error，不靜默推遲到 export 或讀者。只驗 `assets/` 引用；
    http(s)/相對上層/絕對路徑不在範圍。未 render（無 _latest.md）→ 無引用可驗、跳過。

    撞名守門已不需要：圖集中在單一 `docs/assets/`，一個 `assets/<basename>` 就是一個實體檔、
    無「扁平命名空間指向多節各自的檔」歧義（per-section 模型才有的問題，Model A 消除之）。"""
    from dspx.render import find_image_refs, parse_section_bodies
    from dspx.model import docs_asset_files

    by_section = {lf.section: lf for lf in leaves}
    errs: list[str] = []
    for art in sorted({lf.article for lf in leaves}):
        latest = layout.docs_latest(art)
        if not latest.is_file():
            continue
        available = {f"assets/{p.name}" for p in docs_asset_files(layout, art)}
        bodies = parse_section_bodies(latest.read_text(encoding="utf-8"))
        for section, body in bodies.items():
            leaf = by_section.get(section)
            if leaf is None:
                continue
            asset_refs = 0
            for ref in find_image_refs(body):
                if not ref.startswith("assets/"):
                    continue
                asset_refs += 1
                if ref not in available:
                    errs.append(
                        f"{section}: image reference \"{ref}\" does not resolve to an asset in "
                        f"docs/assets/ (render the diagram into docs/assets/, fix the path, "
                        f"or remove the reference)"
                    )
            # diagram-intent：節自己宣告 brief.layout=diagram 卻零張圖 ref＝宣告版面 vs 交付物的機械
            # 落差（吃封閉 enum；不解析 decision 文字＝那是語義，留 audit/skill，鐵律1）。
            brief = leaf.concept.get("brief")
            if isinstance(brief, dict) and brief.get("layout") == "diagram" and asset_refs == 0:
                errs.append(
                    f"{section}: declared brief.layout=diagram but the deliverable embeds no image "
                    f"— embed the diagram with ![](assets/<file>) or change the layout"
                )
    return errs
