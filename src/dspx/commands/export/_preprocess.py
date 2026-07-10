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


# ── 手寫編號標題去除模板自動編號（issue #09 殘餘；numbered profile 雙重編號的病灶）──
#
# numbered profile（academic/paper/manual）對「手寫已含編號」的標題會再疊加模板自動編號＝雙重編號。
# 引擎端 doc.typ 後處理：命中手寫編號 regex 的單行 `= <text>` heading 改寫成 `#heading(numbering: none)`，
# 手寫編號**原文一字不改**（byte-lock）、只關掉模板自動編號。一律套用（unnumbered profile 下
# `numbering: none` ＝語義等價 no-op，省掉 profile 分支）。
#
# ★issue #09 附的兩個 template show-rule 方案已被實測否決、不得回頭採用：原版無限遞迴
# （maximum show rule depth exceeded）、修正版書籤重複（4 標題產 7 書籤）。引擎端文本後處理是唯一
# 實測乾淨的路。
#
# 手寫編號 pattern（標題文字開頭命中任一 → 去編號）。純數字（無點分隔）如「2026 年度計畫」刻意**不**
# 命中（要求層級點分隔或尾點，避免誤傷「以數字開頭但非編號」的標題）。
_MANUAL_NUMBER_RES = (
    re.compile(r"^\d+(?:\.\d+)+\.?\s"),      # 1.2 / 1.2.3 / 3.2.（層級十進位，至少一個點）
    re.compile(r"^\d+\.\s"),                 # 3.（單層＋尾點＋空白）
    re.compile(r"^§\s?\d"),                  # § 3
    re.compile(r"^Annex\s+[A-Z]\b"),         # Annex A
    re.compile(r"^附錄\s?[A-Z]"),             # 附錄 A / 附錄A
    re.compile(r"^[A-Z]\.\d+(?:\.\d+)*\s"),  # A.1 / B.2.3
)

# pandoc typst-writer 的單行 heading：`= <text>`（label 若有在下一行、改寫後仍附著於 #heading）。
_TYPST_HEADING_RE = re.compile(r"^(=+)\s+(.+?)\s*$")
# fenced/raw code 區（typst raw block：≥3 個 ` 或 ~）——區內的 `= …` 行不得改寫。
_TYPST_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")


def _denumber_manual_headings(typst_src: str) -> str:
    """把「手寫已含編號」的單行 heading 改寫成 `#heading(level: N, numbering: none)[<text>]`。

    逐行掃描、跳過 fenced/raw code 區；heading 文字命中任一手寫編號 pattern 才改寫（手寫編號原文
    保留、一字不改）。不分 profile 一律套用。
    """
    out: list[str] = []
    in_fence = False
    fence_char = ""
    for line in typst_src.split("\n"):
        fm = _TYPST_FENCE_RE.match(line)
        if fm:
            marker = fm.group(1)
            if not in_fence:
                in_fence = True
                fence_char = marker[0]
            elif line.strip().startswith(fence_char * 3):
                in_fence = False
            out.append(line)
            continue
        if in_fence:
            out.append(line)
            continue
        m = _TYPST_HEADING_RE.match(line)
        if m:
            eqs, text = m.group(1), m.group(2)
            if any(r.match(text) for r in _MANUAL_NUMBER_RES):
                out.append(f"#heading(level: {len(eqs)}, numbering: none)[{text}]")
                continue
        out.append(line)
    return "\n".join(out)
