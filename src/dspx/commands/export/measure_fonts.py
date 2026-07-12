"""docspec measure-fonts <pdf> — report the actual rendered font sizes in a PDF.

A diagnostic for the release loop: after a font-size change (a `--format-config`
knob, or a hand-edit of the template pack) you measure the *rendered* PDF rather
than guessing by eye. Dominant size = body text; mono/code is scaled 0.90 in the
bundled preamble, so a measured 13.1 pt code char = 14.5 pt logical.

Read-only, offline, no project required (operates on a PDF path) — mirrors
`version`: a module with NAME/HELP/run(argv), no bootstrap.

soft-dep: pdfplumber missing → print an install hint, return 1, never crash.
"""

from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

NAME = "measure-fonts"
HELP = "Print a PDF's actual rendered font sizes (dominant size = body text; settles release typesetting without eyeballing)"

_INSTALL_HINT = (
    "Install the measure-fonts dependency: pdfplumber (uv pip install pdfplumber, "
    "or it's in the export extra: uv run --no-editable docspec measure-fonts)"
)


# ── 相依 probe（soft dependency；鏡像 proof.py）─────────────────────

def _have_pdfplumber() -> bool:
    try:
        import pdfplumber  # type: ignore  # noqa: F401
        return True
    except Exception:
        return False


# ── 單頁量測 ──────────────────────────────────────────────────────

def _measure_page(page):
    """回 (size_counts, font_counts, n_chars)；該頁無字元 → None。"""
    chars = page.chars
    if not chars:
        return None
    size_counts = collections.Counter(round(c["size"], 1) for c in chars)
    font_counts = collections.Counter(c.get("fontname", "?") for c in chars)
    return size_counts, font_counts, len(chars)


def _print_page(idx: int, total: int, result) -> None:
    size_counts, font_counts, n_chars = result
    print(f"\n=== Page {idx + 1} / {total}  ({n_chars} chars) ===")

    print("  Font sizes (pt) — sorted by frequency:")
    for size, count in sorted(size_counts.items(), key=lambda x: -x[1]):
        bar = "█" * min(30, count * 30 // n_chars)
        pct = count / n_chars * 100
        print(f"    {size:5.1f} pt  {count:4d} chars ({pct:4.0f}%)  {bar}")

    print("  Fonts (top 5):")
    for font, count in font_counts.most_common(5):
        pct = count / n_chars * 100
        print(f"    {font[:44]:<44}  {count:4d} ({pct:.0f}%)")

    body_size = size_counts.most_common(1)[0][0]
    print(f"\n  ★ Dominant size: {body_size} pt")
    print(f"    If this is mono/code (Scale=0.90), logical size = {body_size / 0.9:.1f} pt")


# ── 主流程 ────────────────────────────────────────────────────────

def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec measure-fonts", description=HELP)
    parser.add_argument("pdf", help="path to the PDF to measure")
    parser.add_argument("--pages", default="1",
                        help="comma-separated 1-based page numbers (default 1)")
    args = parser.parse_args(argv)

    pdf_path = Path(args.pdf)
    if not pdf_path.is_file():
        sys.stderr.write(f"docspec: PDF not found ({pdf_path}).\n")
        return 1

    if not _have_pdfplumber():
        sys.stderr.write(f"docspec: pdfplumber not found — measure-fonts needs it. {_INSTALL_HINT}\n")
        return 1

    import pdfplumber  # type: ignore

    try:
        page_nums = [int(p.strip()) - 1 for p in args.pages.split(",") if p.strip()]
    except ValueError:
        sys.stderr.write(f"docspec: --pages \"{args.pages}\" is not a valid page-number list (comma-separated, 1-based).\n")
        return 1

    with pdfplumber.open(str(pdf_path)) as pdf:
        total = len(pdf.pages)
        print(f"PDF: {pdf_path}  ({total} pages)")
        for idx in page_nums:
            if idx < 0 or idx >= total:
                print(f"\nPage {idx + 1}: out of range")
                continue
            result = _measure_page(pdf.pages[idx])
            if result is None:
                print(f"\nPage {idx + 1}: no text characters found")
                continue
            _print_page(idx, total, result)
    return 0
