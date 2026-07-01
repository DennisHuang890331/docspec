"""圖片資產：收集正文引用的資產、非阻塞健檢、copy 進 build dir。"""

from __future__ import annotations

import shutil
from pathlib import Path

from dspx.layout import Layout


def _collect_referenced_assets(layout: Layout, article: str, body_md: str) -> dict[str, Path]:
    """收集正文引用、且實際存在的圖片資產：{`assets/<file>` → 交付側 docs/assets/ 源檔路徑}。

    交付物以扁平 `assets/<file>` 引用圖片（backend-neutral）；實體圖檔住**交付側 `docs/assets/`**
    （Model A：圖是交付物、住 docs/）。export 把被引用的圖檔 copy 進 build dir 的 `assets/`，
    typst/xelatex 才找得到。引用了但 docs/assets/ 找不到的，交給 `docspec check` ⑨ 閘擋
    （這裡只 copy 找得到的、不重複報錯）。
    """
    from dspx.render import find_image_refs
    from dspx.model import docs_asset_files
    refs = [r for r in find_image_refs(body_md) if r.startswith("assets/")]
    if not refs:
        return {}
    name_to_path: dict[str, Path] = {
        f"assets/{p.name}": p for p in docs_asset_files(layout, article)
    }
    return {r: name_to_path[r] for r in dict.fromkeys(refs) if r in name_to_path}


def _figure_health_warnings(body_md: str, assets: dict[str, Path]) -> list[str]:
    """非阻塞圖片健檢（export 時，補 render-fidelity 只比文字的盲區）：
      ① 正文引用 `assets/<file>` 卻沒收集到實體檔 → PDF 會缺圖（snapshot 已剝 marker 無法逐節
         歸屬，但扁平 ref↔收集表比對 snapshot-safe）。
      ② 收集到的光柵圖近全黑/近全白 → drawio SVG 在 Typst 壓成黑塊正是這樣（PNG-primary 已治源，
         此為事後健檢）。需 Pillow；缺則只做 ①。
    回 WARN 字串清單，呼叫端印 stderr、不阻擋 export。"""
    from dspx.render import find_image_refs
    warns: list[str] = []
    refs = [r for r in dict.fromkeys(find_image_refs(body_md)) if r.startswith("assets/")]
    for r in refs:
        if r not in assets:
            warns.append(f"image \"{r}\" is referenced but no matching asset was collected "
                         f"— the PDF will be missing this figure")
    try:
        from PIL import Image, ImageStat
    except ImportError:
        return warns
    for ref, src in assets.items():
        if src.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            continue
        try:
            with Image.open(src) as im:
                mean = ImageStat.Stat(im.convert("L")).mean[0]
        except Exception:  # noqa: BLE001 — 壞圖/解碼失敗不阻擋
            continue
        if mean < 8:
            warns.append(f"figure \"{ref}\" renders almost entirely black (mean luma {mean:.0f}/255)"
                         f" — a drawio SVG under the Typst track collapses to a black box; re-render"
                         f" it as PNG (dspx-diagram is PNG-primary)")
        elif mean > 247:
            warns.append(f"figure \"{ref}\" is almost entirely blank (mean luma {mean:.0f}/255)"
                         f" — verify the render is not empty")
    return warns


def _copy_assets_into(build: Path, assets: dict[str, Path]) -> None:
    """把收集到的圖片資產 copy 進 build/assets/（保留扁平檔名，對應正文的 `assets/<file>`）。"""
    if not assets:
        return
    adir = build / "assets"
    adir.mkdir(exist_ok=True)
    for ref, src in assets.items():
        if src.is_file():
            shutil.copy2(src, adir / Path(ref).name)
