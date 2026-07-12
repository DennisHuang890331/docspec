"""docspec proof <article> — 把 export 產物 PDF 逐頁渲成 PNG 供 agent 看圖。

★薄引擎鐵律：proof 只做確定性渲染（pypdfium2 PDF → 點陣圖），不改任何內容、
不碰快照、不碰 corpus。它是 release 互動排版迴圈的「眼睛」：
  export（凍結快照 → PDF）→ proof（PDF → PNG）→ agent + 人看圖討論 → 調格式層 → 重 export → 再 proof。

管線：
  1. 解析 export 產物 PDF（docs/exports/<article>_v<N>.pdf；--latest 則 _vlatest）。
     參數對齊 export：--version（semver）／--latest／預設最新發行版本。
  2. pypdfium2 逐頁 render → PNG 寫進 scratch 夾 docs/exports/_proof/<article>/page_NN.png。
     scratch 夾每次重渲前清空（產物是衍生物、可重生；確定性＝同 PDF 同圖）。
  3. 印出產出的 PNG 路徑清單，供 agent 逐頁讀圖。

soft-dep：pypdfium2 缺了 → 印清楚安裝指引、回 1、不 crash。
找不到 PDF → 提示先 `docspec export`。
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from dspx.commands._shared import BootstrapError, bootstrap
from dspx.engine.layout import Layout, parse_semver

NAME = "proof"
HELP = "Render the export's PDF deliverable to PNGs, page by page (for agents to review layout) → docs/exports/_proof/"

_INSTALL_HINT = (
    "Install the proof dependency: pypdfium2 (uv pip install pypdfium2, "
    "or it's in the dev group: uv run --no-editable docspec proof)"
)

# 渲染解析度：以 PDF 既有 72dpi 為基準的縮放。2.0 ≈ 144dpi，看版面/字級/表格夠清楚，
# 又不至於產出過大檔。確定性＝同 PDF + 同 scale → 同點陣。
_RENDER_SCALE = 2.0


# ── 相依 probe（soft dependency）────────────────────────────────────

def _have_pypdfium2() -> bool:
    try:
        import pypdfium2  # type: ignore  # noqa: F401
        return True
    except Exception:
        return False


# ── 解析 export 產物 PDF（對齊 export 的版本選擇）────────────────────

def _resolve_pdf(layout: Layout, article: str, version: str | None,
                 latest: bool) -> tuple[Path, str] | None:
    """回 (PDF 路徑, 版本標籤)；找不到 → 印錯誤回 None。

    版本選擇邏輯與 export 對齊：--latest → _vlatest；--version → 指定版；
    預設 → 最新發行版本。差別在 proof 找的是已產出的 *.pdf（export 的產物），
    而非快照——故提示先 `docspec export`。
    """
    if latest:
        label = "latest"
    elif version is not None:
        if parse_semver(version) is None:
            sys.stderr.write(f"docspec: --version \"{version}\" is not valid semver (X.Y.Z).\n")
            return None
        label = version
    else:
        versions = layout.existing_versions(article)
        if not versions:
            sys.stderr.write(
                f"docspec: article \"{article}\" has no published snapshot yet — first `docspec publish {article}`"
                f" then `docspec export {article}`.\n")
            return None
        top = max(versions)
        label = f"{top[0]}.{top[1]}.{top[2]}"

    pdf = layout.docs_export(article, label, "pdf")
    if not pdf.is_file():
        sys.stderr.write(
            f"docspec: PDF deliverable not found ({pdf}) — first `docspec export {article}"
            f"{' --latest' if latest else (f' --version {label}' if version else '')}`.\n")
        return None
    return pdf, label


# ── scratch 夾（衍生物、可重生）─────────────────────────────────────

def _proof_dir(layout: Layout, article: str) -> Path:
    """proof 的 PNG scratch 夾＝docs/exports/_proof/<article>/（衍生物、絕不在 archive/）。"""
    return layout.docs_exports_dir / "_proof" / article


# ── 渲染 ──────────────────────────────────────────────────────────

def _render_pages(pdf: Path, out_dir: Path) -> list[Path]:
    """pypdfium2 逐頁 render PNG，回產出的路徑清單（page_01.png …）。

    渲染前清空 out_dir（確定性：同 PDF 重渲不留上一輪殘頁）。
    """
    import pypdfium2 as pdfium  # type: ignore

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    doc = pdfium.PdfDocument(str(pdf))
    try:
        n = len(doc)
        width = max(2, len(str(n)))  # page_01 對齊；頁數多時自動加寬
        produced: list[Path] = []
        for i in range(n):
            page = doc[i]
            bitmap = page.render(scale=_RENDER_SCALE)
            image = bitmap.to_pil()
            target = out_dir / f"page_{i + 1:0{width}d}.png"
            image.save(str(target))
            produced.append(target)
        return produced
    finally:
        doc.close()


# ── 主流程 ────────────────────────────────────────────────────────

def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec proof", description=HELP)
    parser.add_argument("article", help="name of the article to proof")
    parser.add_argument("--version", default=None,
                        help="specific published version (semver X.Y.Z; default latest)")
    parser.add_argument("--latest", action="store_true",
                        help="proof the --latest preview export PDF (_vlatest) instead of a frozen version")
    args = parser.parse_args(argv)

    try:
        layout, _config = bootstrap()
    except BootstrapError as exc:
        return exc.exit_code

    if not _have_pypdfium2():
        sys.stderr.write(
            f"docspec: pypdfium2 not found — proof needs it to render images. {_INSTALL_HINT}\n")
        return 1

    resolved = _resolve_pdf(layout, args.article, args.version, args.latest)
    if resolved is None:
        return 1
    pdf, label = resolved

    out_dir = _proof_dir(layout, args.article)
    try:
        pages = _render_pages(pdf, out_dir)
    except Exception as exc:  # noqa: BLE001 — 任何渲染例外都降級、不 crash
        sys.stderr.write(f"docspec: rendering failed ({exc}) — skipped. {_INSTALL_HINT}\n")
        return 1

    if not pages:
        sys.stderr.write(f"docspec: PDF has no pages to render ({pdf}).\n")
        return 1

    print(f"Proofed {args.article} v{label} ({len(pages)} pages) → {out_dir}")
    for p in pages:
        print(f"  {p}")
    return 0
