"""交付物 span 分類服務（引擎級、零第三方依賴）。

把交付物全文切成 `Span{start, end, kind, section}` 序列——全覆蓋、不重疊、原文序；
`mask_non_prose` 做**等長遮蔽**（offset 不變），供讀取端在遮蔽文字上跑 regex、match
offset 直接回指原文；`propose_conversions` 是 normalize 與 lint V18 的**單一判定權威**
（封閉映射表＋兩側 CJK 條件）。

掃描優先序（衝突裁決序）＝frontmatter → 逐行 fence 狀態機（**fence 優先於 marker 判定**：
fence 內的字面 `dspx:section` 行歸 fence、不推進章節）→ fence 外才認 marker → 行級
heading／table_row → 段內 html_comment／inline_code／image／url，殘餘為 prose。
薄引擎：行級狀態機＋段內 regex，不建 markdown parser。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# 單一真相源：marker／image 的權威定義住 render，直接取用、勿另寫分岔。
from dspx.render import (
    CLOSING_MARKER_RE,
    GROUP_MARKER_RE,
    MARKER_RE,
)

# 封閉 kind 集（spec：prose-spans）。
PROSE = "prose"
FENCE = "fence"
INLINE_CODE = "inline_code"
IMAGE = "image"
HTML_COMMENT = "html_comment"
MARKER = "marker"
HEADING = "heading"
TABLE_ROW = "table_row"
URL = "url"

# 散文面 kind（normalize 只在這些 span 內轉換標點）。
PROSE_KINDS = frozenset({PROSE, HEADING, TABLE_ROW})
# byte-exact kind（mask_non_prose 預設遮蔽面；normalize 一個 byte 不碰）。
BYTE_EXACT_KINDS = frozenset({FENCE, INLINE_CODE, IMAGE, HTML_COMMENT, MARKER, URL})

# 段內 regex：image 與 _fidelity._IMAGE_MD_RE 同課（遷移 byte-exact 對齊）；inline code
# 與 lint._INLINE_CODE_RE 同課；html_comment 與 lint._HTML_COMMENT_RE 同課（DOTALL）。
_IMAGE_RE = re.compile(r"!\[.*?\]\(\s*[^)]*\)")
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_URL_RE = re.compile(r"https?://[^\s)]+")
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_HEADING_RE = re.compile(r"#{1,6}(?:\s|$)")
_TABLE_ROW_RE = re.compile(r"\s*\|")


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    kind: str
    section: str | None


def _is_cjk(ch: str) -> bool:
    """CJK 語境判定：漢字（含擴充 A）＋ CJK 符號標點 ＋ 全形形式（`，。！？（）：；` 等）。

    含全形標點類使 normalize 冪等：轉出的全形標點作為鄰居仍算 CJK，連續半形標點逐一轉盡。"""
    o = ord(ch)
    return (
        0x4E00 <= o <= 0x9FFF        # CJK 統一漢字
        or 0x3400 <= o <= 0x4DBF     # 擴充 A
        or 0x3000 <= o <= 0x303F     # CJK 符號與標點（、。「」〈〉…）
        or 0xFF00 <= o <= 0xFFEF      # 全形形式（，。！？（）：；０-９Ａ-Ｚ…）
    )


def _line_spans(text: str) -> list[tuple[int, int]]:
    """把全文切成逐行 `(start, end)`（end 含該行尾隨 `\\n`）；最後一行可無換行。"""
    out: list[tuple[int, int]] = []
    i = 0
    n = len(text)
    while i < n:
        j = text.find("\n", i)
        if j == -1:
            out.append((i, n))
            break
        out.append((i, j + 1))
        i = j + 1
    return out


def _frontmatter_end(text: str) -> int:
    """檔首 YAML frontmatter 區塊的結束 offset（含關閉 `---` 行的換行）；無 → 0。"""
    if not text.startswith("---"):
        return 0
    lines = _line_spans(text)
    if not lines or text[lines[0][0]:lines[0][1]].strip() != "---":
        return 0
    for start, end in lines[1:]:
        if text[start:end].strip() == "---":
            return end
    return 0   # 未關閉 → 不當 frontmatter（保守，整份走一般分類）


def classify_deliverable(text: str) -> list[Span]:
    """把交付物全文切成 `Span` 序列（全覆蓋、不重疊、原文序）。

    以逐字元 kind 陣列填色（保證全覆蓋不重疊），最後把相鄰同 (kind, section) 併成 span。
    """
    n = len(text)
    if n == 0:
        return []
    kinds: list[str | None] = [None] * n
    sections: list[str | None] = [None] * n

    def fill(a: int, b: int, kind: str, *, only_none: bool = False) -> None:
        for p in range(a, b):
            if only_none and kinds[p] is not None:
                continue
            kinds[p] = kind

    # ── ① frontmatter（整塊 byte-exact，歸 fence、section=None）──
    fm_end = _frontmatter_end(text)
    if fm_end:
        fill(0, fm_end, FENCE)

    # ── ② 逐行：fence 狀態機優先 → fence 外認 marker → 行級 heading/table_row ──
    #    content 行先不填 kind（留 None，段內處理），但 section 歸屬即時記錄。
    current_section: str | None = None
    in_fence = False
    for start, end in _line_spans(text):
        if start < fm_end:
            continue                       # frontmatter 行已處理
        line = text[start:end]
        content = line.rstrip("\n")
        is_fence_marker = content.lstrip().startswith("```")
        if in_fence:
            fill(start, end, FENCE)
            for p in range(start, end):
                sections[p] = current_section
            if is_fence_marker:
                in_fence = False
            continue
        if is_fence_marker:
            fill(start, end, FENCE)
            for p in range(start, end):
                sections[p] = current_section
            in_fence = True
            continue
        m = MARKER_RE.match(content) or GROUP_MARKER_RE.match(content)
        if m:
            current_section = m.group(1)   # section/group marker 推進歸屬
            fill(start, end, MARKER)
            for p in range(start, end):
                sections[p] = current_section
            continue
        if CLOSING_MARKER_RE.match(content):
            fill(start, end, MARKER)
            for p in range(start, end):
                sections[p] = current_section
            continue
        # content 行：kind 留 None（段內處理）、section 即時歸屬
        for p in range(start, end):
            sections[p] = current_section

    # ── ③ 段內：html_comment（DOTALL、可跨行）先於行級 inline 分類；只覆蓋 content（None）位置 ──
    for mm in _HTML_COMMENT_RE.finditer(text):
        fill(mm.start(), mm.end(), HTML_COMMENT, only_none=True)

    # ── ④ 行級 heading/table_row 基底 kind + 段內 inline_code/image/url ──
    for start, end in _line_spans(text):
        # 該行是否仍有未分類（content）位置
        if all(kinds[p] is not None for p in range(start, end)):
            continue
        content = text[start:end]
        stripped = content.lstrip()
        if _HEADING_RE.match(stripped) and content[:len(content) - len(stripped)].strip() == "":
            base = HEADING
        elif _TABLE_ROW_RE.match(content):
            base = TABLE_ROW
        else:
            base = PROSE
        # 段內 byte-exact：inline_code → image → url（優先序即非重疊裁決）
        for rx, kind in ((_INLINE_CODE_RE, INLINE_CODE), (_IMAGE_RE, IMAGE), (_URL_RE, URL)):
            for mm in rx.finditer(content):
                fill(start + mm.start(), start + mm.end(), kind, only_none=True)
        # 殘餘 content 位置 → 基底 kind
        for p in range(start, end):
            if kinds[p] is None:
                kinds[p] = base

    # ── ⑤ 併相鄰同 (kind, section) 成 span ──
    spans: list[Span] = []
    i = 0
    while i < n:
        k = kinds[i]
        s = sections[i]
        j = i + 1
        while j < n and kinds[j] == k and sections[j] == s:
            j += 1
        spans.append(Span(i, j, k or PROSE, s))
        i = j
    return spans


def mask_non_prose(text: str, kinds: set[str] | frozenset[str] | None = None) -> str:
    """把指定 kind 的 span 內容逐字元換成等長半形空白（offset 不變）；未遮區逐 byte 不變。

    `kinds` 預設＝全部 byte-exact kind；讀取端傳子集以對齊自己既有的剝除面。"""
    if kinds is None:
        kinds = BYTE_EXACT_KINDS
    buf = list(text)
    for sp in classify_deliverable(text):
        if sp.kind in kinds:
            for p in range(sp.start, sp.end):
                buf[p] = " "
    return "".join(buf)


# ── normalize / V18 共用判定（D3/D5 單一權威）─────────────────────────────
# 封閉映射表（**已定案**）：ground-truth 閘（台中港語料 260 檔唯讀）後只准刪不准擴。
# 定案＝保留 6 個句內/句末標點；**刪除 `(`/`)`**——括號是成對定界符，逐字元 CJK-語境轉換
# 無法保證成對一致：語料中大量括號內夾 ASCII/識別碼/數字（`（如 ISO 3691-4)`、`（如 ADM, VA)`）
# 或右括號後接 markdown 強調（`（法規對齊)**`）、backtick——開括號轉、閉括號（左鄰為 ASCII/
# 數字/`` ` ``）不轉 ＝ 產生 mismatched bracket（誤轉）。留下的 6 個為單字元標點，無成對問題，
# 且左鄰嚴格 CJK 條件已擋盡識別碼/小數/版本號。完整 ground-truth 結論見 change design.md D3。
PUNCT_MAP = {
    ",": "，",
    ".": "。",
    ";": "；",
    ":": "：",
    "?": "？",
    "!": "！",
}


@dataclass(frozen=True)
class Conversion:
    offset: int          # 原文 offset（單字元）
    src: str             # 原半形字元
    dst: str             # 目標全形字元
    section: str | None  # 所屬章節路徑
    before: str          # 前文窗（供 --dry-run 對位）
    after: str           # 後文窗


def _left_is_cjk(text: str, i: int) -> bool:
    """左鄰：略過半形空白/tab 後第一個非空白字元是否 CJK；行首/段界/字串端＝非 CJK。

    左鄰嚴格 CJK 是保護軸——散文中夾裸 ASCII 識別碼/inline code 的尾隨標點（`e_stop,`、
    `` `retry_max=3`, ``）左側為非 CJK ⇒ 不轉（design D3 的關鍵免疫來自這一側）。"""
    j = i - 1
    while j >= 0 and text[j] in " \t":
        j -= 1
    if j < 0 or text[j] == "\n":
        return False
    return _is_cjk(text[j])


def _right_ok(text: str, i: int) -> bool:
    """右鄰：CJK **或**行尾/段界（換行/字串端）皆放行；右側為 ASCII/數字/拉丁 ⇒ 擋。

    右側放行 boundary 是為了轉換句末標點（`擇一。`、`如下：`＋換行）——這是 normalize 的
    主用例；右側非空白且非 CJK（`3.14`、`Node.js`、`a:b`）則擋（ground-truth 定案，見 D3）。"""
    j = i + 1
    n = len(text)
    while j < n and text[j] in " \t":
        j += 1
    if j >= n or text[j] == "\n":
        return True      # 行尾/段界＝句末標點的典型情境，放行
    return _is_cjk(text[j])


def propose_conversions(text: str) -> list[Conversion]:
    """枚舉散文面 span（prose/heading/table_row）內每筆可轉換的半形標點。

    條件＝封閉映射表成員 ∧ 左鄰嚴格 CJK ∧ 右鄰 CJK-或-行尾。byte-exact span 一個 byte 不碰。
    normalize 拿它產寫入、V18 拿它產 finding——報必可修的單一權威。"""
    out: list[Conversion] = []
    for sp in classify_deliverable(text):
        if sp.kind not in PROSE_KINDS:
            continue
        for i in range(sp.start, sp.end):
            ch = text[i]
            dst = PUNCT_MAP.get(ch)
            if dst is None:
                continue
            if not _left_is_cjk(text, i):
                continue
            if not _right_ok(text, i):
                continue
            out.append(Conversion(
                offset=i, src=ch, dst=dst, section=sp.section,
                before=text[max(0, i - 12):i],
                after=text[i + 1:i + 13],
            ))
    return out


def apply_conversions(text: str, conversions: list[Conversion]) -> str:
    """把 conversions（單字元、1:1）splice 回原文；offset 穩定。"""
    if not conversions:
        return text
    buf = list(text)
    for c in conversions:
        buf[c.offset] = c.dst
    return "".join(buf)
