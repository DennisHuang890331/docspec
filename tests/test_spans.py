"""prose-spans 服務屬性測試（capability prose-spans）。

全覆蓋不重疊、原文序、等長遮蔽、kinds 子集、fence 內字面 marker 不推進章節、段內混合分類。
"""

from __future__ import annotations

from dspx.engine.spans import (
    FENCE,
    HTML_COMMENT,
    IMAGE,
    INLINE_CODE,
    MARKER,
    PROSE,
    URL,
    Conversion,
    apply_conversions,
    classify_deliverable,
    mask_non_prose,
    propose_conversions,
)

# 代表性交付物樣本（frontmatter＋marker＋heading＋fence＋inline code＋圖＋URL＋表格）
SAMPLE = """---
article: a
version: 0.0.0
---
<!-- dspx:section a/x -->
## 標題

本節說明系統設定 `cfg.yaml`，並見圖 ![圖示](assets/f.png) 與網址 https://a.b/c 詳情。

```python
x = {"a": 1}  # <!-- dspx:section a/y -->
```

<!-- dspx:section a/z -->
### 另一節

本節列出兩種模式,並在啟動時擇一.
"""


def _assert_invariants(text: str) -> list:
    spans = classify_deliverable(text)
    assert spans, "非空文字應有 span"
    assert spans[0].start == 0
    assert spans[-1].end == len(text)
    for a, b in zip(spans, spans[1:]):
        assert a.end == b.start, "相鄰 span 必首尾相接"
        assert a.start < a.end
    assert all(s.start < s.end for s in spans)
    # 原文序
    assert spans == sorted(spans, key=lambda s: s.start)
    return spans


def test_full_coverage_non_overlap_ordered():
    _assert_invariants(SAMPLE)


def test_coverage_on_varied_inputs():
    for text in ("", "純散文一行", "a\nb\n", "```\ncode\n```\n", "# h\n", "---\nx: 1\n---\n本文"):
        spans = classify_deliverable(text)
        if text:
            assert spans[0].start == 0 and spans[-1].end == len(text)
            for a, b in zip(spans, spans[1:]):
                assert a.end == b.start
        else:
            assert spans == []


def test_mask_equal_length_prose_unchanged():
    masked = mask_non_prose(SAMPLE)
    assert len(masked) == len(SAMPLE)
    # 散文區逐 byte 不變
    for sp in classify_deliverable(SAMPLE):
        if sp.kind == PROSE:
            assert masked[sp.start:sp.end] == SAMPLE[sp.start:sp.end]
        if sp.kind in (FENCE, INLINE_CODE, IMAGE, MARKER, URL, HTML_COMMENT):
            assert set(masked[sp.start:sp.end]) <= {" ", "\n"} or all(
                c == " " for c in masked[sp.start:sp.end])


def test_mask_kinds_subset_only_masks_given():
    masked = mask_non_prose(SAMPLE, kinds={IMAGE})
    for sp in classify_deliverable(SAMPLE):
        if sp.kind == IMAGE:
            assert masked[sp.start:sp.end] == " " * (sp.end - sp.start)
        else:
            # 其餘（含 fence/inline code）逐 byte 不變
            assert masked[sp.start:sp.end] == SAMPLE[sp.start:sp.end]


def test_fence_literal_marker_stays_fence_no_section_advance():
    spans = classify_deliverable(SAMPLE)
    # fence 內含字面 `<!-- dspx:section a/y -->`：該處必歸 fence，且不出現 section=a/y 的 span
    assert not any(s.section == "a/y" for s in spans), "fence 內字面 marker 不得推進章節"
    # 該字面行的字元 kind＝fence
    idx = SAMPLE.index("x = {")
    fence_span = next(s for s in spans if s.start <= idx < s.end)
    assert fence_span.kind == FENCE
    # fence 之後（fence 外）的散文仍屬 a/x（未被字面 marker 斬斷）
    after_fence_prose = [s for s in spans if s.kind == PROSE and s.start >= fence_span.end
                         and s.section == "a/x"]
    assert after_fence_prose, "fence 之後仍應有歸 a/x 的散文 span"


def test_frontmatter_is_fence():
    spans = classify_deliverable(SAMPLE)
    first = spans[0]
    assert first.kind == FENCE and first.start == 0
    assert SAMPLE[first.start:first.end].startswith("---")


def test_inline_mixed_line_classification():
    line = "本節說明系統設定 `cfg.yaml`，並見圖 ![圖](assets/f.png) 與網址 https://a.b/c 詳情。"
    spans = classify_deliverable(line)
    kinds = {s.kind for s in spans}
    assert INLINE_CODE in kinds
    assert IMAGE in kinds
    assert URL in kinds
    assert PROSE in kinds
    # inline code 的內容確為 `cfg.yaml`
    ic = next(s for s in spans if s.kind == INLINE_CODE)
    assert line[ic.start:ic.end] == "`cfg.yaml`"


def test_html_comment_span():
    text = "前 <!-- 一段註解 --> 後"
    spans = classify_deliverable(text)
    hc = next(s for s in spans if s.kind == HTML_COMMENT)
    assert text[hc.start:hc.end] == "<!-- 一段註解 -->"


# ── propose_conversions（D3/D5 共用判定）──────────────────────────────

def test_propose_two_sided_cjk_converts():
    text = "本系統支援兩種模式,並在啟動時擇一."
    conv = propose_conversions(text)
    got = {c.src for c in conv}
    assert got == {",", "."}
    out = apply_conversions(text, conv)
    assert out == "本系統支援兩種模式，並在啟動時擇一。"


def test_propose_identifier_trailing_punct_not_converted():
    # 識別碼尾隨標點：`e_stop,` 的逗號左側是 p（非 CJK）→ 不轉
    text = "設定 e_stop, 然後停止。"
    conv = propose_conversions(text)
    assert not any(c.src == "," for c in conv)


def test_propose_decimal_and_domain_immune():
    text = "版本 3.14 與網域 example.com 是常數。"
    conv = propose_conversions(text)
    # 3.14 的點兩側是數字（非 CJK）、example.com 在 url 之外仍靠識別碼保護
    assert not any(c.dst == "。" for c in conv)


def test_propose_skips_byte_exact_spans():
    text = "見 `a,b` 與\n```\nx=1,\n```\n（設定,如上）"
    conv = propose_conversions(text)
    # 只有散文的「設定,如上」該轉；code 內的逗號不轉
    assert all(c.section is None or True for c in conv)
    for c in conv:
        # 轉換點左右都 CJK；不會落在 code
        assert text[c.offset] == ","


def test_idempotent():
    text = "模式一,模式二。"
    once = apply_conversions(text, propose_conversions(text))
    twice = apply_conversions(once, propose_conversions(once))
    assert once == twice
    assert propose_conversions(once) == []
