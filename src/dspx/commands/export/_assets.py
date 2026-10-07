"""圖片資產：收集正文引用的資產、非阻塞健檢、copy 進 build dir。"""

from __future__ import annotations

import shutil
import stat
from pathlib import Path

from dspx.engine.layout import Layout, parse_semver
from dspx.engine.document_versions import _safe


class HistoricalAssetError(ValueError):
    """A frozen document's image source cannot be established."""


def _collect_referenced_assets(layout: Layout, article: str, body_md: str, *,
                               snapshot: Path | None = None) -> dict[str, Path]:
    """Resolve referenced images from the selected snapshot, or live preview assets.

    交付物以扁平 `assets/<file>` 引用圖片（backend-neutral）；實體圖檔住**交付側 `docs/assets/`**
    （Model A：圖是交付物、住 docs/）。export 把被引用的圖檔 copy 進 build dir 的 `assets/`，
    typst/xelatex 才找得到。引用了但 docs/assets/ 找不到的，交給 `artispec check` ⑨ 閘擋
    （預覽只 copy 找得到的、不重複報錯）。Frozen export 只讀 snapshot/assets，
    缺圖或舊快照未保存歷史圖時拒絕重建，不能借用目前交付側圖片冒充歷史。
    """
    from dspx.engine.render import find_image_refs
    refs = [r for r in find_image_refs(body_md) if r.startswith("assets/")]
    if not refs:
        return {}
    if snapshot is not None:
        _safe(layout, snapshot)
        # New snapshots keep their immutable images beside document.md. Legacy
        # Markdown contains no evidence that today's images are its old images.
        version = snapshot.parent.parent.name
        if (parse_semver(version) is None
                or snapshot.resolve() != layout.version_snapshot(article, version).resolve()):
            raise HistoricalAssetError(
                f"historical image assets were not preserved for legacy snapshot {snapshot}; "
                "cannot rebuild its referenced images with guaranteed historical provenance. "
                "Current document assets will not be substituted.")
        asset_dir = _safe(layout, snapshot.parent / "assets")
        found: dict[str, Path] = {}
        for ref in dict.fromkeys(refs):
            candidate = _safe(layout, snapshot.parent / ref)
            if not candidate.resolve().is_relative_to(asset_dir.resolve()) or not candidate.is_file():
                raise HistoricalAssetError(
                    f"frozen snapshot image asset is missing: {ref} ({candidate}); "
                    "restore the historical snapshot asset; current document assets will not be substituted.")
            found[ref] = candidate
        return found
    asset_dir = _safe(layout, layout.docs_assets_dir(article))
    found = {}
    for ref in dict.fromkeys(refs):
        candidate = _safe(layout, asset_dir / ref[len("assets/"):])
        if not candidate.resolve().is_relative_to(asset_dir.resolve()):
            raise ValueError(f"invalid image asset reference: {ref}")
        if candidate.is_file():
            found[ref] = candidate
    return found


def _figure_health_warnings(body_md: str, assets: dict[str, Path]) -> list[str]:
    """非阻塞圖片健檢（export 時，補 render-fidelity 只比文字的盲區）：
      ① 正文引用 `assets/<file>` 卻沒收集到實體檔 → PDF 會缺圖（snapshot 已剝 marker 無法逐節
         歸屬，但扁平 ref↔收集表比對 snapshot-safe）。
      ② 收集到的光柵圖近全黑/近全白 → drawio SVG 在 Typst 壓成黑塊正是這樣（PNG-primary 已治源，
         此為事後健檢）。需 Pillow；缺則只做 ①。
    回 WARN 字串清單，呼叫端印 stderr、不阻擋 export。"""
    from dspx.engine.render import find_image_refs
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
                gray = im.convert("L")
                stat = ImageStat.Stat(gray)
                mean = stat.mean[0]
                hist = gray.histogram()
        except Exception:  # noqa: BLE001 — 壞圖/解碼失敗不阻擋
            continue
        # 近全白判準＝**非白像素占比**（histogram 數灰階 <245 的像素），非 mean luma：
        # 稀疏線圖（白底細線的狀態圖）mean 天然 >247 但訊息完整，mean 判準系統性誤報；
        # 非白占比 <0.1% 才是真空白/近空白渲染。近全黑分支不動——黑塊是實心面積，mean 對它成立。
        total = sum(hist) or 1
        nonwhite = sum(hist[:245]) / total
        if mean < 8:
            warns.append(f"figure \"{ref}\" renders almost entirely black (mean luma {mean:.0f}/255)"
                         f" — a drawio SVG under the Typst track collapses to a black box; re-render"
                         f" it as PNG (dspx-diagram is PNG-primary)")
        elif nonwhite < 0.001:
            warns.append(f"figure \"{ref}\" is almost entirely blank (non-white pixels "
                         f"{nonwhite:.2%} < 0.10%) — verify the render is not empty")
    return warns


def _copy_assets_into(build: Path, assets: dict[str, Path], *, layout: Layout | None = None) -> None:
    """把收集到的圖片資產 copy 進 build/assets/（保留扁平檔名，對應正文的 `assets/<file>`）。"""
    if not assets:
        return
    adir = build / "assets"
    if layout is not None:
        _safe(layout, adir)
        for ref, src in assets.items():
            _safe(layout, src)
            _safe(layout, build / ref)
    adir.mkdir(parents=True, exist_ok=True)
    for ref, src in assets.items():
        if src.is_file():
            target = build / ref
            if not target.resolve().is_relative_to(adir.resolve()):
                raise ValueError(f"invalid image asset reference: {ref}")
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                target.chmod(target.stat().st_mode | stat.S_IWUSR)
            # Derived assets stay writable even when the snapshot is read-only.
            shutil.copyfile(src, target)
