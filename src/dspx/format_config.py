r"""format-config「格式旋鈕」子系統——約束 agent、杜絕 LaTeX 幻覺。

★問題：release skill 讓 agent 直接手編 docspec-cas 的 preamble/lua。agent 可能寫壞 LaTeX、
或幻覺出不存在的字型/指令，壞值會一路漏進 xelatex → 整份炸或靜默渲錯。

★解法（本模組）：定義一組**驗證過的結構化旋鈕**（值用 enum/範圍約束）。agent 只填值，
docspec **確定性**把旋鈕編譯成 LaTeX 覆寫片段、注入 build（在 bundled preamble.tex
*之後*，覆寫生效）。任何不在 enum / 超範圍的值 → 在編譯前 `validate_format_config`
就拋 FormatConfigError、export 非零、**根本不產生 LaTeX**。壞值/幻覺永遠到不了 xelatex。

兩個入口：
  - `validate_format_config(raw) -> dict`：把（可能部分指定、可能含壞值的）旋鈕表
    驗證＋補預設成完整旋鈕表；任何壞值拋 FormatConfigError（清楚指名哪顆旋鈕、為何）。
  - `compile_format_config(knobs) -> str`：把**已驗證**的旋鈕表確定性編成 LaTeX 覆寫片段。

旋鈕表的存放（見 config.py / commands/export.py）：
  - 專案預設＝config 的 `export.format` 區塊（沿用「未知鍵 warn、缺鍵給預設」）。
  - per-article 覆寫＝`docspec export <art> --format-config <file.yaml>`（覆蓋同名旋鈕）。
"""

from __future__ import annotations

from typing import Any


class FormatConfigError(Exception):
    """格式旋鈕含不合法值（不在 enum / 超出範圍 / 型別錯）。

    刻意在「編譯成 LaTeX 之前」就擋下：壞值/幻覺永遠到不了 xelatex。
    """


# ── 旋鈕 schema（單一事實來源；validate 與 compile 都讀它）─────────────────
#
# CJK 字型 enum → (data_dir/fonts 內的字型檔基名（不含副檔名）, 副檔名)。
# 全是 bundled OFL 字型（見 commands/setup.py 的 _FONT_MANIFEST / paths.REQUIRED_FONT_FILES）。
# agent 只能從這份 enum 挑——挑不存在的字型＝幻覺，validate 直接擋。
_CJK_FONTS: dict[str, tuple[str, str]] = {
    "TW-Kai":           ("TW-Kai-98_1", "ttf"),            # 全字庫正楷體（內文預設）
    "SourceHanSerifTC": ("SourceHanSerifTC-Regular", "otf"),  # 思源宋
    "SourceHanSansTC":  ("SourceHanSansTC-Regular", "otf"),   # 思源黑（標題預設）
    # C5：以下兩顆已由 setup _FONT_MANIFEST 納入真檔（不再是別名）。
    "LXGWWenKaiTC":     ("LXGWWenKaiTC-Regular", "ttf"),   # 霞鶩文楷 TC（手寫楷風、OFL）
    "TW-Sung":          ("TW-Sung-98_1", "ttf"),          # 全字庫正宋體（宋體、政府開放資料）
}

# 內文（CJKmain）粗體 fallback：單字重的宋/楷無原生粗體 → 內文 **emphasis** 借思源宋 SemiBold
# （同宋體族、比 Bold 輕、優雅而仍可辨 emphasis；用 Bold 過黑、SemiBold 是定版）。標題另走
# AutoFakeBold＝合成同面粗體、不借此檔。
_CJK_BOLD_FALLBACK = "SourceHanSerifTC-SemiBold.otf"
# 標題（CJKsans）合成粗體強度：標楷/宋等單字重者 \bfseries 時就地加粗（保持同字面，不換成黑體）。
_HEADING_FAKE_BOLD = 2.0

# 具名版心 preset → geometry 參數（沿用 bundled preamble 的寬版心當 a4-wide＝預設/現狀）。
_PAGE_PRESETS: dict[str, str] = {
    # 現狀（bundled preamble.tex 的版心）＝預設；不設旋鈕＝行為不變。
    "a4-wide":   "paperwidth=210mm,paperheight=297mm,hmargin=12mm,vmargin=20mm,headsep=12pt,footskip=14pt",
    # A4 一般留白（學術/正式投稿常見）。
    "a4-normal": "paperwidth=210mm,paperheight=297mm,hmargin=25mm,vmargin=25mm,headsep=12pt,footskip=14pt",
    # upstream cas-sc 原生窄頁（期刊投稿原貌）。
    "cas-native": "paperwidth=192mm,paperheight=262mm,hmargin=13.7mm,vmargin=18mm,headsep=12pt,footskip=14pt",
}

# pandoc 支援的語法高亮 style（pandoc --list-highlight-styles 的子集；只收常用穩定者）。
_HIGHLIGHT_STYLES = ("tango", "pygments", "kate", "espresso", "zenburn", "haddock", "breezedark")

# 表格樣式 enum。
_TABLE_STYLES = ("github", "booktabs")

# 數值範圍旋鈕：鍵 → (min, max, 單位字串供錯誤訊息)。
_PAGE_MARGIN_RANGE = (10.0, 40.0, "mm")
_HEADING_SCALE_RANGE = (0.8, 1.6, "")     # 標題字級倍率（×preamble 基準 17/15/14pt）
_TABLE_SIZE_RANGE = (8.0, 14.0, "pt")     # 窄表內文字級（寬表＝此值-1；EM 欄寬同步縮放）
# base_size 上限拉到 18：定版內文＝14.5pt（upstream cas-sc \maketitle 後重定義；見 _BODY_SIZE_ANCHOR），
# 過去上限 14 連預設都裝不下＝bug 之一。10–18 涵蓋常見投稿字級。
_BASE_SIZE_RANGE = (10.0, 18.0, "pt")
_LEADING_RANGE = (1.1, 1.6, "")

# 標題字級階梯：由 base_size 確定性衍生的倍率（section / subsection / subsubsection），
# 取代過去寫死的 17/15/14pt（那是內文 12pt 時代的值；內文升 14.5 後最深階 14 < 內文＝倒置）。
# 倍率單調遞減保證 section > subsection > subsubsection；最深階 > base_size 的不變量由 validate
# 把關（heading_scale 過低會破壞：base × 1.10 × hs > base 需 hs > 1/1.10 ≈ 0.909）。
_HEADING_MULTIPLIERS = (1.45, 1.25, 1.10)
_HEADING_LEADING = 1.2   # 標題 baselineskip = size × 此比


def _heading_sizes(base_size: float, heading_scale: float) -> list[tuple[float, float]]:
    r"""衍生標題字級階梯 [(size, baselineskip), …]＝base_size × 各倍率 × heading_scale。"""
    return [
        (base_size * m * heading_scale, base_size * m * heading_scale * _HEADING_LEADING)
        for m in _HEADING_MULTIPLIERS
    ]

# 內文字級錨點：base_size 預設＝此值時，post-\maketitle 字級階梯與舊 before.tex 硬寫值
# byte-identical（normalsize 14.5/18.3、small 13/16、footnotesize 12/14.5）。其餘 base_size
# 等比例縮放整個階梯。★這是 C4 修正的核心：字級階梯必須在 \maketitle **之後**重定義
# （upstream cas-sc 在 maketitle 重設 NFSS 字級巨集，preamble 的 normalsize 重定義全失效），故由
# compile_postmaketitle_fonts 編、export 注入 before.tex 的 __DOCSPEC_FONTSIZES__（見 memory
# cas-sc-font-size-reset）。base_size 旋鈕因此**真的**控制內文字級（過去 before.tex 硬寫 14.5
# →旋鈕對內文無效）。
_BODY_SIZE_ANCHOR = 14.5

# 預設旋鈕表（＝現狀；不設任何旋鈕時 compile 出的覆寫與 bundled preamble 等效）。
# 注意：page 預設用 preset「a4-wide」＝bundled preamble 現行版心，故預設不改版面。
DEFAULT_FORMAT: dict[str, Any] = {
    "page": {"preset": "a4-wide"},   # 或 {"margin": <10–40 mm>}（margin 與 preset 互斥）
    "font": {
        "cjk_body": "TW-Sung",        # 內文＝全字庫正宋體（宋體、易讀；C5 人挑定版）
        "cjk_heading": "TW-Kai",      # 標題/章節標題＝標楷（楷書、優雅、靠字級醒目）
        "base_size": 14.5,        # 定版內文字級（與 _BODY_SIZE_ANCHOR 一致＝預設 byte-identical）
        "leading": 1.45,
        "heading_scale": 1.0,     # 標題字級倍率（1.0＝preamble 基準、不發覆寫＝byte-identical）
    },
    "table": {"style": "github", "zebra": True, "size": 12.0, "column_rules": True},
    "code": {"highlight": "tango"},
}

# 旋鈕 schema 的頂層已知區塊＋各區塊已知鍵（未知鍵 warn 忽略，與 config 一致）。
_KNOWN_SECTIONS = frozenset(DEFAULT_FORMAT)
_KNOWN_KEYS: dict[str, frozenset[str]] = {
    "page": frozenset({"preset", "margin"}),
    "font": frozenset({"cjk_body", "cjk_heading", "base_size", "leading", "heading_scale"}),
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
      ★這是防幻覺閘門：壞值在此處就死，永不被 compile 成 LaTeX。

    回傳：完整、已驗證、可直接餵 compile_format_config 的旋鈕表。
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

    # ── font ──
    f = out["font"]
    f["cjk_body"] = _check_enum("font", "cjk_body", f["cjk_body"], _CJK_FONTS)
    f["cjk_heading"] = _check_enum("font", "cjk_heading", f["cjk_heading"], _CJK_FONTS)
    f["base_size"] = _check_number("font", "base_size", f["base_size"], *_BASE_SIZE_RANGE)
    f["leading"] = _check_number("font", "leading", f["leading"], *_LEADING_RANGE)
    f["heading_scale"] = _check_number(
        "font", "heading_scale", f["heading_scale"], *_HEADING_SCALE_RANGE)

    # ── 標題字級階梯不變量（防幻覺閘門的呈現層版本）：最深階仍須嚴格 > 內文。
    #    單調遞減由固定倍率保證；只有 heading_scale 過低會使最深階 ≤ base_size。
    deepest = _heading_sizes(f["base_size"], f["heading_scale"])[-1][0]
    if deepest <= f["base_size"]:
        need = 1.0 / _HEADING_MULTIPLIERS[-1]
        raise FormatConfigError(
            f"heading ladder inverts: deepest heading {deepest:.2f}pt <= body "
            f"{f['base_size']:g}pt. font.heading_scale={f['heading_scale']:g} is too low "
            f"for font.base_size={f['base_size']:g} (need heading_scale > {need:.3f})."
        )

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


# ── 編譯（已驗證旋鈕 → 確定性 LaTeX 覆寫片段）────────────────────────────

def _cjk_font_decl(cmd: str, enum_name: str, *, bold: str) -> str:
    r"""產一行 \setCJK*font，從 enum 解到 bundled 字型檔（Path=./fonts/、絕對載入）。

    bold 模式（單字重的宋/楷無原生粗體，故粗體要嘛借檔、要嘛合成）：
      - "fallback"：BoldFont=思源宋 SemiBold＝內文 **emphasis** 用宋粗（會 pop、比 Bold 輕）。
      - "fake"：AutoFakeBold＝就地合成同面粗體＝標題 \bfseries 仍是標楷（不換黑體）。
    """
    base, ext = _CJK_FONTS[enum_name]
    opts = [f"Path=./fonts/", f"Extension=.{ext}"]
    if bold == "fallback":
        opts.append(f"BoldFont={_CJK_BOLD_FALLBACK}")
    elif bold == "fake":
        opts.append(f"AutoFakeBold={_HEADING_FAKE_BOLD:g}")
    return f"\\{cmd}{{{base}}}[{', '.join(opts)}]"


def compile_format_config(knobs: dict) -> str:
    r"""把**已驗證**的旋鈕表確定性編成 LaTeX 覆寫片段（注入在 bundled preamble *之後*）。

    覆寫的東西（只動呈現、不碰內容）：
      - geometry（版心：preset 或對稱 margin）
      - \setCJKmainfont / \setCJKsansfont（CJK 內文/標題字型，從 bundled enum 選）
      - \normalsize 重定義（字級 base_size pt、行高＝base_size × 1.25）＋ \linespread（leading）
      - 表格樣式（booktabs 風＝無格線色、隱去斑馬；github 風＝細灰格線＋斑馬底）
      - （語法高亮 style 不在這裡：它是 pandoc CLI 旗標 --syntax-highlighting，由 export 帶。）

    ★呼叫前務必已過 validate_format_config——這裡假設值皆合法、不再防禦（壞值在 validate 已死）。
    """
    lines: list[str] = [
        "% ==== docspec format-config 覆寫（旋鈕→LaTeX；注入於 bundled preamble 之後）====",
        "% 由 docspec 從驗證過的格式旋鈕確定性編譯而成；agent 不裸寫此檔。",
    ]

    # ── 版心 ──
    page = knobs["page"]
    if "preset" in page:
        geo = _PAGE_PRESETS[page["preset"]]
        lines.append(f"% page preset = {page['preset']}")
    else:
        m = page["margin"]
        geo = (f"paperwidth=210mm,paperheight=297mm,"
               f"hmargin={m:g}mm,vmargin={m:g}mm,headsep=12pt,footskip=14pt")
        lines.append(f"% page margin = {m:g}mm（對稱）")
    lines.append(f"\\geometry{{{geo}}}")

    # ── CJK 字型 ──
    f = knobs["font"]
    lines.append(f"% cjk_body = {f['cjk_body']}, cjk_heading = {f['cjk_heading']}")
    # 內文＝CJKmain（預設 TW-Sung 宋）；標題＝CJKsans（預設 TW-Kai 楷）。
    # 內文（CJKmain）：粗體借思源宋 SemiBold（emphasis 宋粗）；標題（CJKsans）：AutoFakeBold（合成同面粗體）。
    lines.append(_cjk_font_decl("setCJKmainfont", f["cjk_body"], bold="fallback"))
    lines.append(_cjk_font_decl("setCJKsansfont", f["cjk_heading"], bold="fake"))

    # ── 標題字級階梯（由 base_size 衍生 × heading_scale；無條件發射）──
    # cas 的 \sectionfont 等是 plain \def（heading 時才讀、跨 \maketitle 存活），preamble 已 \def；
    # 此處在 preamble *之後* 再 \def 即生效。一律發射＝format_config 成為標題字級唯一真相來源、
    # 且不變量（最深階 > 內文，已於 validate 把關）在預設路徑也保證生效。
    hs = f["heading_scale"]
    sec, ssec, sssec = _heading_sizes(f["base_size"], hs)
    lines.append(
        f"% heading ladder = base_size {f['base_size']:g}pt × {_HEADING_MULTIPLIERS} × heading_scale {hs:g}")
    lines.append(
        f"\\def\\sectionfont{{\\sffamily\\fontsize{{{sec[0]:.2f}pt}}{{{sec[1]:.2f}pt}}\\bfseries}}")
    lines.append(
        f"\\def\\ssectionfont{{\\sffamily\\fontsize{{{ssec[0]:.2f}pt}}{{{ssec[1]:.2f}pt}}"
        "\\bfseries\\selectfont}")
    lines.append(
        f"\\def\\sssectionfont{{\\sffamily\\fontsize{{{sssec[0]:.2f}pt}}{{{sssec[1]:.2f}pt}}"
        "\\fontseries{b}\\fontshape{it}\\selectfont}")

    # ── 行高 leading（base_size 字級階梯不在這裡：見下方說明）──
    # ★字級階梯（normalsize/small/footnotesize）**不**在 preamble 發——upstream cas-sc 在 \maketitle
    #   重設 NFSS 字級巨集，preamble 的 normalsize 重定義會被覆蓋掉（內文卡 class 預設）。
    #   字級階梯改由 compile_postmaketitle_fonts 編、export 注入 before.tex 的 \maketitle **之後**
    #   （base_size 旋鈕才真的控制內文）。leading 走 \linespread＝全域 \baselinestretch，跨 maketitle
    #   仍生效，故留在 preamble。
    lines.append(f"% leading = {f['leading']:g}（字級階梯見 post-\\maketitle 注入）")
    lines.append(f"\\linespread{{{f['leading']:g}}}")

    # ── 表格樣式 ──
    # ★lua filter（docspec-tables.lua）在 \begingroup 內把格線色寫死成「\arrayrulecolor{
    #   docspecRule}」、斑馬/表頭底色寫死成「\rowcolor{docspecZebra}」。故旋鈕**不靠全域
    #   \arrayrulecolor**（出不了 begingroup），而是**重定義這兩個被引用的顏色名**——
    #   確定性、且 lua 一字不改即生效：
    #     - github  ：docspecRule＝淺灰 #D0D7DE、docspecZebra＝淡底 #F6F8FA（現狀）。
    #     - booktabs：docspecRule＝近黑 #222222（三線粗黑感）、zebra 關＝底色設白。
    #     - zebra=false：docspecZebra＝白（表頭/偶數列 \rowcolor 白＝視覺無斑馬）。
    t = knobs["table"]
    lines.append(f"% table style = {t['style']}, zebra = {t['zebra']}")
    if t["style"] == "booktabs":
        rule_hex = "222222"
        lines.append("\\setlength{\\heavyrulewidth}{1.5pt}")
        lines.append("\\setlength{\\lightrulewidth}{0.75pt}")
    else:  # github
        rule_hex = "D0D7DE"
        lines.append("\\setlength{\\heavyrulewidth}{1.1pt}")
        lines.append("\\setlength{\\lightrulewidth}{0.5pt}")
    lines.append(f"\\definecolor{{docspecRule}}{{HTML}}{{{rule_hex}}}")
    # zebra 旋鈕獨立於 style：true＝隔列淡底、false＝白（視覺無斑馬）。
    if t["zebra"]:
        lines.append("\\definecolor{docspecZebra}{HTML}{F6F8FA}")
    else:
        lines.append("\\definecolor{docspecZebra}{HTML}{FFFFFF}")

    return "\n".join(lines) + "\n"


# ── post-\maketitle 字級階梯（C4：upstream cas-sc 在 maketitle 後才能定字級）──────────

def compile_postmaketitle_fonts(knobs: dict) -> str:
    r"""把 base_size 旋鈕編成 NFSS 字級階梯，注入 before.tex 的 \maketitle **之後**。

    upstream cas-sc 在 \maketitle 期間把字級巨集（\normalsize/\small/\footnotesize）重設回 class
    預設，故唯一能讓「內文真的吃到 base_size」的位置＝maketitle 之後。export 用此字串替換
    before.tex 的 __DOCSPEC_FONTSIZES__ placeholder。

    階梯以 _BODY_SIZE_ANCHOR（14.5）為錨等比例縮放：base_size＝14.5（預設）時，輸出與舊
    before.tex 硬寫的 normalsize 14.5/18.3、small 13/16、footnotesize 12/14.5 **byte-identical**
    （故預設匯出不變）；改 base_size 才整條階梯一起放大/縮小。
    """
    size = knobs["font"]["base_size"]
    f = size / _BODY_SIZE_ANCHOR

    def pair(sz: float, base: float) -> tuple[str, str]:
        return f"{sz * f:g}", f"{base * f:g}"

    ns, nsb = pair(14.5, 18.3)
    sm, smb = pair(13.0, 16.0)
    fn, fnb = pair(12.0, 14.5)
    return (
        "\\makeatletter\n"
        f"\\renewcommand\\normalsize{{\\@setfontsize\\normalsize{{{ns}}}{{{nsb}}}}}\n"
        f"\\renewcommand\\small{{\\@setfontsize\\small{{{sm}}}{{{smb}}}}}\n"
        f"\\renewcommand\\footnotesize{{\\@setfontsize\\footnotesize{{{fn}}}{{{fnb}}}}}\n"
        "\\makeatother\n"
        "\\normalsize"
    )


# ── 語法高亮：旋鈕值 → pandoc CLI --syntax-highlighting 參數 ─────────────

def pandoc_highlight_style(knobs: dict) -> str:
    """回 pandoc `--syntax-highlighting=<style>` 要用的 style（已驗證、必在 enum 內）。"""
    return knobs["code"]["highlight"]


# ── Typst 軌：已驗證旋鈕 → pandoc -V 模板變數（docspec-typst template 讀）─────────

# Typst 軌目前由旋鈕控的子集（其餘＝模板統一預設）。font 字型旋鈕在 Typst 軌**不適用**
# （house 已統一成思源宋體＋Source Serif 4、見模板）；table 樣式/版心/heading_scale → Typst
# 參數化是後續 follow-up。
_TYPST_KNOB_FOLLOWUPS = ("table.style/zebra/size", "page margin/preset", "font.heading_scale",
                         "font.cjk_body/cjk_heading (moot: Typst house font is unified)")


def compile_typst_vars(knobs: dict) -> list[str]:
    r"""把**已驗證**旋鈕編成 pandoc `-V` 變數，餵給 docspec-typst 模板。

    目前映射 Typst 軌支援的子集：
      - font.base_size → `fontsize`（內文字級 pt；模板 `#set text(size:)`）。
      - font.leading   → `leading`（LaTeX linespread 1.1–1.6 近似成 typst `par(leading:)` em）。
    code.highlight 走 pandoc CLI `--syntax-highlighting`（與 LaTeX 軌同，不在此）。
    其餘旋鈕（見 _TYPST_KNOB_FOLLOWUPS）目前用模板統一預設、不由旋鈕控。

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
