"""Typst 軌：標題/正文拆分＋docspec-typst + typst binary 的 PDF build（預設 render 軌，輕量、原生 CJK）。"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from ._assets import _copy_assets_into
from ._config import _PANDOC_FROM
from ._preprocess import _balance_table_columns, _fix_typst_math

_H1_RE = re.compile(r"^#\s+(.+?)\s*$")


def _split_title_body(text: str, fallback_title: str) -> tuple[str, str]:
    """剝 YAML frontmatter、抽首個 H1 當標題；回 (title, body)。

    凍結快照本就無 frontmatter（publish 已剝），但 --latest 工作副本有；一律防禦性剝除。
    首個 H1 移出正文（標題改由 before.tex `\\title` 注入、避免重複），其餘為正文。
    無 H1 → 用 fallback（文章名），正文原樣。
    """
    from dspx.frontmatter import parse_frontmatter
    _, body = parse_frontmatter(text)
    lines = body.split("\n")
    title = fallback_title
    out: list[str] = []
    taken = False
    for line in lines:
        if not taken:
            m = _H1_RE.match(line)
            if m:
                title = m.group(1).strip()
                taken = True
                continue  # 吃掉這一行，不進正文
        out.append(line)
    return title, "\n".join(out).lstrip("\n")


def _build_pdf_typst(pandoc: str, typst: str, typst_template: Path, fonts_src: Path,
                     title: str, body_md: str, out: Path,
                     highlight_style: str = "tango", format_vars: list[str] | None = None,
                     assets: dict[str, Path] | None = None, lang: str = "zh",
                     region: str | None = None, profile: str = "default") -> None:
    """Typst 軌：pandoc -t typst（套 docspec-typst 模板）→ typst compile（受控字型）→ PDF。

    比 xelatex 軌輕：單一 typst binary、原生 CJK（--font-path 受控字型夾、--ignore-system-fonts
    確定性）、無 TinyTeX。docspec 不碰 PDF 二進位，只編排 subprocess。
    format_vars＝已驗證旋鈕編出的 pandoc -V 變數（fontsize/leading；compile_typst_vars）。
    """
    with tempfile.TemporaryDirectory(prefix="dspx_typst_") as td:
        build = Path(td)
        shutil.copy2(typst_template, build / "template.typ")
        (build / "doc.md").write_text(body_md, encoding="utf-8")
        # 圖片資產：被引用的 `assets/<file>` copy 進 build/assets/（typst image("assets/…") 解析；SVG 原生）
        _copy_assets_into(build, assets or {})

        # pandoc markdown → doc.typ（套自帶 typst 模板；標題經 -V 注入、節標題降一級＝root H1 已抽走；
        # 語法高亮＋格式旋鈕變數一併帶入）
        subprocess.run(
            [pandoc, "doc.md", "-f", _PANDOC_FROM, "-t", "typst",
             "--template=template.typ",
             "--shift-heading-level-by=-1",
             f"--syntax-highlighting={highlight_style}",
             "-V", f"title={title}",
             "-V", f"lang={lang}",
             "-V", f"profile={profile}",
             *(["-V", f"region={region}"] if region else []),
             *(format_vars or []),
             "-o", "doc.typ"],
            cwd=str(build), check=True,
        )

        # pandoc 後處理：① 等分百分比欄寬 → auto（治表格擠爆＋硬斷字）；② 修數學符號錯位（sect→inter）。
        doc_typ = build / "doc.typ"
        _src = doc_typ.read_text(encoding="utf-8")
        doc_typ.write_text(_fix_typst_math(_balance_table_columns(_src)), encoding="utf-8")

        # typst compile（受控字型夾、忽略系統字型＝確定性）。
        proc = subprocess.run(
            [typst, "compile", "--font-path", str(fonts_src),
             "--ignore-system-fonts", "doc.typ", "doc.pdf"],
            cwd=str(build), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
        )
        if proc.returncode != 0:
            tail = "\n".join((proc.stdout or "").strip().splitlines()[-12:])
            raise RuntimeError(f"typst compilation failed:\n{tail}" if tail
                               else "typst compilation failed (no output)")
        produced = build / "doc.pdf"
        if not produced.is_file():
            raise RuntimeError("typst did not produce doc.pdf")
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(produced, out)
