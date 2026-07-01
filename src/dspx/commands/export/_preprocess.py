"""backend-neutral 快照預處理：剝 raw-LaTeX、typst 表格欄寬平衡、typst 數學符號修正。"""

from __future__ import annotations

import re

# pandoc 的 raw-LaTeX fenced 區塊（```{=latex} … ```），typst 軌不渲染（pandoc 丟棄）→
# fidelity 比對時要從源端剔除，否則 TikZ 標籤裡的 CJK 被誤判成「PDF 缺字」。
_RAW_LATEX_BLOCK_RE = re.compile(r"`{3,}\s*\{=(?:latex|tex)\}.*?`{3,}", re.DOTALL)


def _strip_raw_latex(md: str) -> str:
    """剔除 raw-LaTeX fenced 區塊（typst 不渲染它們）；供 typst 軌的 fidelity 源端使用。"""
    return _RAW_LATEX_BLOCK_RE.sub("", md)


# pandoc 的 typst writer 對沒指定欄寬的表格給「等分百分比」欄寬（columns: (33.33%, 33.33%, …)），
# 與內容無關 → 文字重的欄被擠成窄條、字被硬斷成「parti-tion」「exe-cution」。把『等分百分比』
# 改成 typst auto（依內容定寬、且 typst auto 會把表收進容器寬、不水平溢出，只在需要時換行）。
# 非等分（作者用 grid table 指定的相對欄寬）＝作者意圖，保留不動。
_TYPST_COLS_RE = re.compile(r"columns:\s*\(([^)]*)\)")


def _balance_table_columns(typst_src: str) -> str:
    """把 pandoc typst 表格的等分百分比欄寬改成 auto（依內容定寬）；非等分保留。"""
    def repl(m: "re.Match[str]") -> str:
        parts = [p.strip() for p in m.group(1).split(",") if p.strip()]
        if len(parts) < 2 or not all(p.endswith("%") for p in parts):
            return m.group(0)
        try:
            vals = [float(p[:-1]) for p in parts]
        except ValueError:
            return m.group(0)
        if max(vals) - min(vals) > 0.5:   # 非等分＝作者指定的相對寬 → 尊重
            return m.group(0)
        return "columns: (" + ", ".join(["auto"] * len(parts)) + ")"
    return _TYPST_COLS_RE.sub(repl, typst_src)


# pandoc 的 typst writer 對少數數學符號發出 typst 不認的識別字（pandoc/typst 版本錯位）→ 編譯炸。
# 已知：集合交集 ∩ → pandoc 發 `sect`，但 typst 用 `inter`。只在 `$…$` 數學區段內、整字替換（避免動到散文）。
_TYPST_MATH_RE = re.compile(r"\$.*?\$", re.DOTALL)
_TYPST_MATH_SYMBOL_FIXES = {"sect": "inter"}   # pandoc 名 → typst 名


def _fix_typst_math(typst_src: str) -> str:
    """修 pandoc→typst 數學符號錯位（如 ∩：sect→inter）；只在數學區段內整字替換。"""
    def fix_span(m: "re.Match[str]") -> str:
        span = m.group(0)
        for bad, good in _TYPST_MATH_SYMBOL_FIXES.items():
            span = re.sub(rf"\b{bad}\b", good, span)
        return span
    return _TYPST_MATH_RE.sub(fix_span, typst_src)
