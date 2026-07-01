"""runtime byte-lock 驗證（產出 PDF 後抽文字、與源做 content-token 比對）。"""

from __future__ import annotations

import sys
from pathlib import Path

from dspx import paths


def _sample(counter, n: int = 12) -> str:
    """把多重集差（Counter）格式成可讀樣本字串：`字×3, A×1 …`。"""
    items = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    shown = ", ".join(f"{tok!r}×{cnt}" for tok, cnt in items[:n])
    more = " …" if len(items) > n else ""
    return shown + more


def _is_cjk(ch: str) -> bool:
    return "一" <= ch <= "鿿"


def _source_anchored_stream(body_md: str) -> tuple[list[str], list[str]]:
    """源端有序內容字元流＋每字「最近 markdown 標題」錨（供差異定位、源端為準）。"""
    import re as _re
    chars: list[str] = []
    anchors: list[str] = []
    heading = "(preamble)"
    for line in _nfc(body_md).splitlines():
        s = line.strip()
        if s.startswith("#"):
            heading = s.lstrip("#").strip() or heading
            continue
        clean = paths._LATEX_CMD_RE.sub(" ", line)
        for ch in paths._CONTENT_CHAR_RE.findall(clean):
            chars.append(ch)
            anchors.append(heading)
    return chars, anchors


def _pdf_paged_stream(pdf) -> tuple[list[str], list[int]]:
    """PDF 端有序內容字元流＋每字所在頁碼（1-indexed；用 page.chars 帶座標的逐字）。"""
    chars: list[str] = []
    pages: list[int] = []
    for i, page in enumerate(pdf.pages, start=1):
        raw = "".join(c.get("text", "") for c in page.chars)
        clean = paths._LATEX_CMD_RE.sub(" ", _nfc(raw))
        for ch in paths._CONTENT_CHAR_RE.findall(clean):
            chars.append(ch)
            pages.append(i)
    return chars, pages


def _nfc(text: str) -> str:
    """NFC 正規化（與 paths.content_* 同一套，供 byte-lock 有序流前處理）。"""
    import unicodedata
    return unicodedata.normalize("NFC", text)


def _window(seq: list[str], lo: int, hi: int, pad: int = 12) -> str:
    """源端字元窗（差異前後文，給人/agent 對位）。"""
    a = max(0, lo - pad)
    b = min(len(seq), hi + pad)
    return ("…" if a > 0 else "") + "".join(seq[a:b]) + ("…" if b < len(seq) else "")


def _verify_byte_lock(out: Path, body_md: str, article: str = "", *, ack: bool = False) -> int:
    """產出 PDF 後 runtime 驗**渲染忠實度**：源正文 vs PDF 抽回文字的位置化精確 diff。

    正名「渲染忠實度檢查」（防竄改改由結構 gate 擋）：這裡只問「凍結內容有沒有在轉檔中
    被吃掉/變形」。比對分兩層，刻意分離「決策」與「定位」（教訓＝機械 drift 才擋、版面
    重排不誤報；CLAUDE.md 操作鐵律 1）：

      ① **決策（pass/fail）走 multiset 淨損**：CJK 字元的淨缺失（src - got）＝豆腐/缺字型/
         丟段，是真內容事故 → 紅燈。multiset 不受 PDF 閱讀順序重排影響（表格/多欄頁不誤報）。
      ② **定位＋雙向報走有序 diff**：difflib.SequenceMatcher 比源端有序流 vs PDF 端有序流，
         報「源有 PDF 缺」（delete）含 page N＋源端最近標題＋前後文窗，並雙向附「PDF 多」
         （insert，多為連字/重複，informational）。

    拉丁/數字差異一律 **informational**（等寬字/語法高亮的字元級抽取本就有損）——印出但
    不致 fail（取代舊的 5% 硬容差）。

    回傳：0＝忠實/僅拉丁雜訊/`--ack`（已 proof 複判）；
         1＝CJK 淨缺失（疑似豆腐/丟段），**或驗證無法執行**（pdfplumber 缺/開不了 PDF）。
    ★渲染忠實度是 hard-gate：驗證器缺席不等於通過（fail-closed）。要明確跳過用 `--no-verify`。
    """
    from collections import Counter

    try:
        import pdfplumber  # type: ignore
    except Exception:
        sys.stderr.write(
            "docspec: ✗ pdfplumber not installed — cannot verify export render fidelity, so export FAILS "
            "(the PDF was produced but is UNVERIFIED). Install the verifier: "
            "uv tool install --from <docspec path> docspec --with pdfplumber  (or `pip install 'docspec[export]'`). "
            "To skip verification deliberately, re-run with --no-verify.\n")
        return 1

    try:
        pdf_cm = pdfplumber.open(str(out))
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(
            f"docspec: ✗ pdfplumber failed to open the produced PDF ({exc}) — render fidelity could not be "
            "verified, so export FAILS (fail-closed). Re-run with --no-verify to skip verification.\n")
        return 1

    with pdf_cm as pdf:
        pdf_chars, pdf_pages = _pdf_paged_stream(pdf)
    src_chars, src_anchors = _source_anchored_stream(body_md)

    # ① 決策：CJK 淨缺失（multiset，順序無關、表格不誤報）。
    src_ms = Counter(src_chars)
    got_ms = Counter(pdf_chars)
    missing = src_ms - got_ms
    extra = got_ms - src_ms
    miss_cjk = Counter({k: v for k, v in missing.items() if _is_cjk(k)})
    miss_latin = Counter({k: v for k, v in missing.items() if not _is_cjk(k)})
    cjk_lost = bool(miss_cjk)

    # ② 定位＋雙向：有序 diff（只在有 CJK 缺失或要報拉丁雜訊時走，省成本）。
    import difflib
    sm = difflib.SequenceMatcher(None, src_chars, pdf_chars, autojunk=False)
    del_runs = []   # (src_lo, src_hi, page, anchor, window, n_cjk)
    ins_runs = []   # (pdf_lo, pdf_hi, page, text)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("delete", "replace") and i2 > i1:
            run = src_chars[i1:i2]
            n_cjk = sum(1 for c in run if _is_cjk(c))
            page = pdf_pages[min(j1, len(pdf_pages) - 1)] if pdf_pages else 0
            anchor = src_anchors[i1] if i1 < len(src_anchors) else ""
            del_runs.append((i1, i2, page, anchor, _window(src_chars, i1, i2), n_cjk))
        if tag in ("insert", "replace") and j2 > j1:
            page = pdf_pages[min(j1, len(pdf_pages) - 1)] if pdf_pages else 0
            ins_runs.append((j1, j2, page, "".join(pdf_chars[j1:j2])))

    if not cjk_lost:
        # 通過（或只有拉丁雜訊/PDF 連字）；有差異就 informational 印一行、不 fail。
        latin_lost = sum(miss_latin.values())
        if latin_lost or extra:
            sys.stderr.write(
                f"docspec: ✓ render fidelity passed (no CJK loss). informational: Latin/digit extraction differs by "
                f"{latin_lost} char(s), PDF side has {sum(extra.values())} extra char(s) (monospace/ligature extraction noise, not lost content).\n")
        return 0

    # CJK 缺失 → 高度可疑。--ack（已 proof 複判）仍印報告但回 0。
    tag = "⚠ (--ack: re-checked, allowed)" if ack else "✗"
    sys.stderr.write(
        f"docspec: {tag} render fidelity: detected a net CJK character loss of {sum(miss_cjk.values())} char(s) "
        f"(suspected missing-glyph boxes / missing font / dropped segment). In source but missing from PDF: {_sample(miss_cjk)}\n")
    cjk_del = [r for r in del_runs if r[5] > 0][:6]
    for _i1, _i2, page, anchor, win, n_cjk in cjk_del:
        proof_hint = f"page_{page:0{max(2, len(str(len(pdf_pages))))}d}.png" if page else "?"
        sys.stderr.write(
            f"    page {page} · source §{anchor or '(preamble)'} · {n_cjk} CJK missing · context \"{win}\""
            f"  → run docspec proof{f' {article}' if article else ''} and look at _proof/.../{proof_hint}\n")
    if ack:
        return 0
    sys.stderr.write(
        "  CJK here cannot be extracted back from the PDF = the render may be eating characters. Run `docspec proof` to that page to re-check:\n"
        "    · real missing-glyph boxes / dropped segment → fix the font/layout and re-export.\n"
        "    · proof shows the text and it's just an extraction misfire (e.g. text inside an image) → add --ack to allow it (or --no-verify to skip entirely).\n")
    return 1
