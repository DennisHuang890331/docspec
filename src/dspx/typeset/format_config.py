r"""format-config「格式旋鈕」子系統——約束 agent、杜絕排版幻覺。

★問題：agent 若能直接調排版，可能填壞值或幻覺出不存在的字型/設定，壞值會一路漏進
render → 整份炸或靜默渲錯。

★解法（本模組）：定義一組**驗證過的結構化旋鈕**（值用 enum/範圍約束）。agent 只填值，
docspec **確定性**把旋鈕轉成 Typst 模板參數／pandoc 變數。任何不在 enum / 超範圍的值
→ 在轉換前 `validate_format_config` 就拋 FormatConfigError、export 非零。壞值/幻覺
永遠到不了 render。

入口：
  - `validate_format_config(raw) -> dict`：把（可能部分指定、可能含壞值的）旋鈕表
    驗證＋補預設成完整旋鈕表；任何壞值拋 FormatConfigError（清楚指名哪顆旋鈕、為何）。
  - `compile_typst_vars(knobs) -> list[str]`：把**已驗證**旋鈕編成 pandoc `-V` 變數，
    餵給 docspec-typst 模板（Typst 為現行預設 PDF 軌）；base_size/leading 進 Typst，
    code.highlight 走 pandoc 的語法高亮。

旋鈕表的存放（見 config.py / commands/export.py）：
  - 專案預設＝config 的 `export.format` 區塊（沿用「未知鍵 warn、缺鍵給預設」）。
  - per-article 覆寫＝`docspec export <art> --format-config <file.yaml>`（覆蓋同名旋鈕）。
"""

from __future__ import annotations

from typing import Any


class FormatConfigError(Exception):
    """格式旋鈕含不合法值（不在 enum / 超出範圍 / 型別錯）。

    刻意在「轉成 render 參數之前」就擋下：壞值/幻覺永遠到不了 render。
    """


# ── 旋鈕 schema（單一事實來源；validate 與 compile 都讀它）─────────────────
#
# 具名版心 preset → geometry 參數（a4-wide 寬版心＝預設/現狀）。
_PAGE_PRESETS: dict[str, str] = {
    # 現狀寬版心＝預設；不設旋鈕＝行為不變。
    "a4-wide":   "paperwidth=210mm,paperheight=297mm,hmargin=12mm,vmargin=20mm,headsep=12pt,footskip=14pt",
    # A4 一般留白（學術/正式投稿常見）。
    "a4-normal": "paperwidth=210mm,paperheight=297mm,hmargin=25mm,vmargin=25mm,headsep=12pt,footskip=14pt",
    # 期刊雙欄窄頁（投稿原貌）。
    "cas-native": "paperwidth=192mm,paperheight=262mm,hmargin=13.7mm,vmargin=18mm,headsep=12pt,footskip=14pt",
}

# pandoc 支援的語法高亮 style（pandoc --list-highlight-styles 的子集；只收常用穩定者）。
_HIGHLIGHT_STYLES = ("tango", "pygments", "kate", "espresso", "zenburn", "haddock", "breezedark")

# 表格樣式 enum。
_TABLE_STYLES = ("github", "booktabs")

# 數值範圍旋鈕：鍵 → (min, max, 單位字串供錯誤訊息)。
_PAGE_MARGIN_RANGE = (10.0, 40.0, "mm")
# 首行縮排（em）：0＝明確關縮排；中文慣例 2em（≈2 字）。未設＝完全交 profile。
_PAR_INDENT_RANGE = (0.0, 4.0, "em")
_TABLE_SIZE_RANGE = (8.0, 14.0, "pt")     # 窄表內文字級（寬表＝此值-1；EM 欄寬同步縮放）
# base_size 上限拉到 18：定版內文＝14.5pt（見 _BODY_SIZE_ANCHOR），
# 過去上限 14 連預設都裝不下＝bug 之一。10–18 涵蓋常見投稿字級。
_BASE_SIZE_RANGE = (10.0, 18.0, "pt")
_LEADING_RANGE = (1.1, 1.6, "")

# 內文字級錨點：compile_typst_vars 用它判斷 base_size 是否仍是繼承自舊雙欄期刊版心的預設值
# ——若是，不發 fontsize、讓 Typst 模板用自己的單欄 A4 house 預設（該 14.5pt 錨點在 Typst
# 單欄 A4 上過大）；使用者一旦把 base_size 調成別的值就照常發。
_BODY_SIZE_ANCHOR = 14.5

# 預設旋鈕表（＝現狀；不設任何旋鈕時 compile 出的覆寫與 bundled preamble 等效）。
# 注意：page 預設用 preset「a4-wide」＝bundled preamble 現行版心，故預設不改版面。
DEFAULT_FORMAT: dict[str, Any] = {
    "page": {"preset": "a4-wide"},   # 或 {"margin": <10–40 mm>}（margin 與 preset 互斥）
    "font": {
        "base_size": 14.5,        # 內文字級錨點（與 _BODY_SIZE_ANCHOR 一致＝交 Typst 模板 house 預設）
        "leading": 1.45,
    },
    # par.first_line_indent：預設**不設**（＝完全交 profile 的 _indent，行為不變）。設 0–4 em
    # 覆寫所有 profile 的首行縮排 amount（中文慣例 2em；0＝明確關縮排）；all:false 與段距 _parspace 不受影響。
    "par": {},
    "table": {"style": "github", "zebra": True, "size": 12.0, "column_rules": True},
    "code": {"highlight": "tango"},
}

# 旋鈕 schema 的頂層已知區塊＋各區塊已知鍵（未知鍵 warn 忽略，與 config 一致）。
_KNOWN_SECTIONS = frozenset(DEFAULT_FORMAT)
_KNOWN_KEYS: dict[str, frozenset[str]] = {
    "page": frozenset({"preset", "margin"}),
    "font": frozenset({"base_size", "leading"}),
    "par": frozenset({"first_line_indent"}),
    "table": frozenset({"style", "zebra", "size", "column_rules"}),
    "code": frozenset({"highlight"}),
}


# ── 驗證（壞值在這裡就被擋；永不進 compile/LaTeX）────────────────────────

def _warn_default(msg: str) -> None:
    import sys
    sys.stderr.write(msg + "\n")


def _check_number(section: str, key: str, value: Any, lo: float, hi: float, unit: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FormatConfigError(
            f"format.{section}.{key}={value!r} has wrong type (must be a number)."
        )
    v = float(value)
    if not (lo <= v <= hi):
        raise FormatConfigError(
            f"format.{section}.{key}={value}{unit} is out of the valid range "
            f"{lo:g}–{hi:g}{unit}."
        )
    return v


def _check_enum(section: str, key: str, value: Any, allowed) -> str:
    if value not in allowed:
        raise FormatConfigError(
            f"format.{section}.{key}={value!r} is not a valid value; "
            f"choices: {', '.join(map(str, allowed))}."
        )
    return value


def validate_format_config(raw: Any, *, warn=None) -> dict:
    """把（可能部分指定、可能含壞值的）旋鈕表驗證＋補預設成完整旋鈕表。

    - 缺的旋鈕 → 給 DEFAULT_FORMAT 的預設（沿用 config 規則）。
    - 未知區塊／未知鍵 → warn 忽略（沿用 config 規則）。
    - 不合法值（不在 enum / 超範圍 / 型別錯）→ 拋 FormatConfigError（清楚指名）。
      ★這是防幻覺閘門：壞值在此處就死，永不被編成輸出。

    回傳：完整、已驗證、可直接餵 compile_typst_vars / pandoc_* 的旋鈕表。
    """
    warn = warn or _warn_default
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise FormatConfigError("the format knob table must be a key-value mapping (dict).")

    import copy
    out = copy.deepcopy(DEFAULT_FORMAT)

    for section, body in raw.items():
        if section not in _KNOWN_SECTIONS:
            warn(f"docspec: format has unknown section \"{section}\" (ignored)")
            continue
        if not isinstance(body, dict):
            raise FormatConfigError(f"format.{section} must be a key-value mapping (dict).")
        for key, value in body.items():
            if key not in _KNOWN_KEYS[section]:
                warn(f"docspec: format.{section} has unknown knob \"{key}\" (ignored)")
                continue
            out[section][key] = value

    # ── page：preset 或 margin（margin 給了就以 margin 為準、清掉 preset）──
    page = out["page"]
    if "margin" in (raw.get("page") or {}):
        margin = _check_number("page", "margin", page["margin"], *_PAGE_MARGIN_RANGE)
        out["page"] = {"margin": margin}
    else:
        preset = _check_enum("page", "preset", page.get("preset", "a4-wide"), _PAGE_PRESETS)
        out["page"] = {"preset": preset}

    # ── font（Typst 軌：標題字級由 template.typ 以 em-相對設定、層級恆正確，故只剩
    #    內文字級與行距兩顆旋鈕；cas-sc 時代的字型 enum/heading_scale/字級階梯不變量已隨
    #    LaTeX 軌退場移除）──
    f = out["font"]
    f["base_size"] = _check_number("font", "base_size", f["base_size"], *_BASE_SIZE_RANGE)
    f["leading"] = _check_number("font", "leading", f["leading"], *_LEADING_RANGE)

    # ── par：first_line_indent（未設＝交 profile；設了驗 0–4 em）──
    par = out.get("par") or {}
    if "first_line_indent" in par:
        par["first_line_indent"] = _check_number(
            "par", "first_line_indent", par["first_line_indent"], *_PAR_INDENT_RANGE)
    out["par"] = par

    # ── table ──
    t = out["table"]
    t["style"] = _check_enum("table", "style", t["style"], _TABLE_STYLES)
    if not isinstance(t["zebra"], bool):
        raise FormatConfigError(f"format.table.zebra={t['zebra']!r} has wrong type (must be true/false).")
    t["size"] = _check_number("table", "size", t["size"], *_TABLE_SIZE_RANGE)
    if not isinstance(t["column_rules"], bool):
        raise FormatConfigError(
            f"format.table.column_rules={t['column_rules']!r} has wrong type (must be true/false).")

    # ── code ──
    out["code"]["highlight"] = _check_enum(
        "code", "highlight", out["code"]["highlight"], _HIGHLIGHT_STYLES)

    return out


# ── 語法高亮：旋鈕值 → pandoc CLI --syntax-highlighting 參數 ─────────────

def pandoc_highlight_style(knobs: dict) -> str:
    """回 pandoc `--syntax-highlighting=<style>` 要用的 style（已驗證、必在 enum 內）。"""
    return knobs["code"]["highlight"]


# ── Typst 軌：已驗證旋鈕 → pandoc -V 模板變數（docspec-typst template 讀）─────────

# Typst 軌仍未映射的旋鈕（其餘＝模板統一預設）。house 字型已統一成思源宋體＋Source Serif 4
# （見模板）；table 樣式/字級/斑馬紋 → Typst 參數化是**唯一**剩下的 follow-up（page margin/preset
# 與 par.first_line_indent 已於本 change 接線、脫離此清單）。
_TYPST_KNOB_FOLLOWUPS = ("table.style/zebra/size",)


def compile_typst_vars(knobs: dict) -> list[str]:
    r"""把**已驗證**旋鈕編成 pandoc `-V` 變數，餵給 docspec-typst 模板。

    映射 Typst 軌支援的子集：
      - font.base_size → `fontsize`（內文字級 pt；模板 `#set text(size:)`）。
      - font.leading   → `leading`（LaTeX linespread 1.1–1.6 近似成 typst `par(leading:)` em）。
      - page.margin / page.preset → `margin`（四邊等值覆寫模板 house 版心）：margin 直接發；
        preset a4-normal→25mm、a4-wide→不發（house 幾何）、cas-native→不發＋一行警告（期刊雙欄
        版心、Typst 單欄不適用）。
      - par.first_line_indent（設了）→ `first-line-indent`（覆寫所有 profile 的首行縮排 amount）。
    code.highlight 走 pandoc CLI `--syntax-highlighting`（不在此）。
    其餘旋鈕（見 _TYPST_KNOB_FOLLOWUPS）仍用模板統一預設。

    ★Typst 軌 house body＝模板的 `$if(fontsize)$…$else$<TYPST 預設>$endif$` fallback（單欄 A4
    適中字級）：base_size 的**專案預設**＝LaTeX cas-sc 的 14.5pt 錨點（_BODY_SIZE_ANCHOR），那是
    為雙欄期刊 LaTeX 版心挑的、在 Typst 單欄 A4 上過大。故當 base_size 維持該 LaTeX 錨點預設時，
    這裡**不**發 fontsize、讓 Typst 模板用自己的 house 預設；使用者一旦把 base_size 調成別的值
    （真的想控 Typst 內文字級），就照常發。標題階梯是 em 相對、隨內文縮放，層級恆正確。
    """
    f = knobs["font"]
    # linespread（baseline 倍率）→ typst leading（行間 gap）的工程近似：1.45→0.95em、1.1→0.6em、1.6→1.1em。
    leading_em = max(0.5, f["leading"] - 0.5)
    out: list[str] = ["-V", f"leading={leading_em:g}em"]
    # base_size 仍是 LaTeX 錨點預設 → 交給 Typst 模板 house 預設（單欄 A4 不過大）；否則照旋鈕值發。
    if f["base_size"] != _BODY_SIZE_ANCHOR:
        out += ["-V", f"fontsize={f['base_size']:g}pt"]

    # page.margin / page.preset → 四邊等值 margin（模板 $if(margin)$ 覆寫 house 版心）。
    page = knobs.get("page") or {}
    if "margin" in page:
        out += ["-V", f"margin={page['margin']:g}mm"]
    else:
        preset = page.get("preset", "a4-wide")
        if preset == "a4-normal":
            out += ["-V", "margin=25mm"]
        elif preset == "cas-native":
            _warn_default(
                "docspec: ⚠ page.preset 'cas-native' is a journal two-column trim and is not "
                "mapped on the single-column Typst track — using the house page geometry.")
        # a4-wide（預設）＝不發 → 模板 house 版心、行為不變。

    # par.first_line_indent（設了）→ 覆寫所有 profile 的首行縮排 amount。
    par = knobs.get("par") or {}
    if "first_line_indent" in par:
        out += ["-V", f"first-line-indent={par['first_line_indent']:g}em"]
    return out


def pandoc_table_metavars(knobs: dict) -> list[str]:
    r"""表格旋鈕（size / column_rules）→ pandoc `-M key=val` 參數串，餵給 docspec-tables.lua。

    lua 在 \begingroup 內用顯式 \fontsize 設表格字級、用 !{\vrule} 畫直欄線——這兩者都**在
    lua 端**（pandoc 階段 TeX macro 還不存在），故走 pandoc metadata（-M）傳值、lua 按名字讀。
    ★table.size 變動時 lua 會同步重算 EM 欄寬常數（否則欄寬以錯字級估算而爆版）。
    預設值（size 12 / column_rules on）＝lua 現行硬寫值＝byte-identical。
    """
    t = knobs["table"]
    return [
        "-M", f"docspec-table-size={t['size']:g}",
        "-M", f"docspec-table-colrules={'on' if t['column_rules'] else 'off'}",
    ]
