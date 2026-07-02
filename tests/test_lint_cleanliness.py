"""deliverable-cleanliness：V4（placeholder 類放寬）、V12（GFM alert 殘留）、V10（數字一致 WARN）。

對應 change deliverable-cleanliness-truthful / capability deliverable-cleanliness。
靶＝渲染後的 docs/_latest.md（lint 掃交付物）；每個測試 render 一個最小 leaf 後注入缺陷再 lint。
"""

from __future__ import annotations

from pathlib import Path

from dspx.check import run_check  # noqa: F401  (keep parity with sibling test imports)
from dspx.commands import render as render_cmd
from dspx.layout import Layout
from dspx.lint import ERROR, WARN, run_lint
from dspx.model import load_project
from dspx.schema import load_schema


def _render(home: Path, monkeypatch, article: str = "a") -> Layout:
    monkeypatch.chdir(home.parent)
    render_cmd.run([article])
    return Layout(home)


def _inject(layout: Layout, article: str, extra: str) -> None:
    p = layout.docs_latest(article)
    p.write_text(p.read_text(encoding="utf-8") + extra, encoding="utf-8")


def _lint(layout: Layout):
    return run_lint(layout, load_project(layout), load_schema())


def _leaf(write_leaf, home):
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1, "concept": "x",
                                     "brief": {"audience": "a", "depth": "d",
                                               "breadth": "b", "forbidden": ["f"]}})


# ── V4 placeholder 類（放寬：不只 literal [TBD]）──────────────────────────

def test_v4_annotated_tbd_caught(make_project, write_leaf, monkeypatch):
    home = make_project(); _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject(layout, "a", "\n\n回覆簽名 [TBD: 確認 1.x 簽名]。\n")
    findings = _lint(layout)
    assert any(f.rule == "V4" and f.level == ERROR for f in findings)


def test_v4_todo_fixme_cjk_placeholder_caught(make_project, write_leaf, monkeypatch):
    home = make_project(); _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject(layout, "a", "\n\n這段 [TODO] 要補；那段 [FIXME: x]；還有 [待補]。\n")
    rules = [f for f in _lint(layout) if f.rule == "V4"]
    assert len(rules) >= 3 and all(f.level == ERROR for f in rules)


def test_v4_code_span_placeholder_exempt(make_project, write_leaf, monkeypatch):
    """code 區段內的 <VID>/[TODO] 是內容範例，不該觸發 V4。"""
    home = make_project(); _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject(layout, "a", "\n\n路徑 `fleet/sc/<VID>/status`，範例：\n\n```\n# [TODO] later\nx = <fill>\n```\n")
    assert not any(f.rule == "V4" for f in _lint(layout))


# ── V12 GFM alert 殘留 ──────────────────────────────────────────────

def test_v12_warning_alert_caught(make_project, write_leaf, monkeypatch):
    home = make_project(); _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject(layout, "a", "\n\n> [!WARNING] 待補連線錯誤處理。\n")
    assert any(f.rule == "V12" and f.level == ERROR for f in _lint(layout))


def test_v12_plain_blockquote_not_flagged(make_project, write_leaf, monkeypatch):
    home = make_project(); _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject(layout, "a", "\n\n> 官方定義：Zenoh 是一個 pub/sub/query 協定。\n")
    assert not any(f.rule == "V12" for f in _lint(layout))


def test_v12_code_fenced_alert_exempt(make_project, write_leaf, monkeypatch):
    home = make_project(); _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject(layout, "a", "\n\n```md\n> [!WARNING] this is a doc example\n```\n")
    assert not any(f.rule == "V12" for f in _lint(layout))


# ── V10 跨文件數字一致（WARN、非阻塞）────────────────────────────────

def test_v10_number_drift_warn_not_error(make_project, write_leaf, monkeypatch):
    home = make_project(); _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject(layout, "a", "\n\ne_stop 採 timeout 1000ms。\n\ne_stop 的 timeout 800ms。\n")
    v10 = [f for f in _lint(layout) if f.rule == "V10"]
    assert v10 and all(f.level == WARN for f in v10)        # WARN，不是 ERROR
    assert any("1000ms" in f.detail and "800ms" in f.detail for f in v10)


def test_v10_different_metric_not_flagged(make_project, write_leaf, monkeypatch):
    """同 key 不同度量、或不同 key → 不報衝突。"""
    home = make_project(); _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject(layout, "a", "\n\ntask_assign 的 timeout 5000ms。\n\ne_stop 端到端延遲低於 100ms。\n")
    assert not any(f.rule == "V10" for f in _lint(layout))


def test_v10_consistent_numbers_clean(make_project, write_leaf, monkeypatch):
    home = make_project(); _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject(layout, "a", "\n\ntask_assign 的 timeout 5000ms。\n\ntask_assign 表格列 5000ms。\n")
    assert not any(f.rule == "V10" for f in _lint(layout))


# ── V13 保留範例/佔位 token 外洩（WARN）──────────────────────────────

def test_v13_reserved_example_tokens_caught(make_project, write_leaf, monkeypatch):
    home = make_project(); _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject(layout, "a", "\n\nContact admin@example.com; see lorem ipsum dolor; call 555-0142.\n")
    v13 = [f for f in _lint(layout) if f.rule == "V13"]
    assert v13 and all(f.level == WARN for f in v13)
    detail = " ".join(f.detail for f in v13)
    assert "example.com" in detail


def test_v13_clean_doc_no_finding(make_project, write_leaf, monkeypatch):
    home = make_project(); _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject(layout, "a", "\n\n真實聯絡資料、無範例 token。\n")
    assert not any(f.rule == "V13" for f in _lint(layout))


# ── V14 孤兒圖檔（WARN）──────────────────────────────────────────────

def _leaf_with_asset(write_leaf, home, name="fig.png"):
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1, "concept": "x",
                                     "brief": {"audience": "a", "depth": "d",
                                               "breadth": "b", "forbidden": ["f"]}})
    adir = Layout(home).docs_assets_dir("a")   # Model A：圖住交付側 docs/a/assets/，非 corpus
    adir.mkdir(parents=True, exist_ok=True)
    (adir / name).write_bytes(b"\x89PNG\r\n\x1a\n")


def test_v14_orphan_asset_caught(make_project, write_leaf, monkeypatch):
    home = make_project(); _leaf_with_asset(write_leaf, home)
    layout = _render(home, monkeypatch)            # 不引用 fig.png
    v14 = [f for f in _lint(layout) if f.rule == "V14"]
    assert v14 and v14[0].level == WARN and "fig.png" in v14[0].where


def test_v14_referenced_asset_not_flagged(make_project, write_leaf, monkeypatch):
    home = make_project(); _leaf_with_asset(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject(layout, "a", "\n\n![圖](assets/fig.png)\n")   # 有引用 → 非孤兒
    assert not any(f.rule == "V14" for f in _lint(layout))


# ── V15 撰寫工具/治理詞彙洩漏（ERROR）────────────────────────────────

def test_v15_governance_topology_vocab_caught(make_project, write_leaf, monkeypatch):
    home = make_project(); _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject(layout, "a", "\n\n本文件在三層森林中的定位明確，承接兩個治理父，governed-by 此概念。\n")
    v15 = [f for f in _lint(layout) if f.rule == "V15"]
    assert v15 and all(f.level == ERROR for f in v15)
    hits = {f.detail.split('"')[1] for f in v15}
    assert "治理父" in hits and "governed-by" in hits
    assert any("森林" in h for h in hits)


def test_v15_engine_command_leak_caught(make_project, write_leaf, monkeypatch):
    home = make_project(); _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject(layout, "a", "\n\n不一致時應由 factcheck 提出，並 raise 一筆 finding。\n")
    v15 = [f for f in _lint(layout) if f.rule == "V15"]
    hits = {f.detail.split('"')[1] for f in v15}
    assert "factcheck" in hits
    assert any("finding" in h for h in hits)


def test_v15_layer_labels_and_fanin_caught(make_project, write_leaf, monkeypatch):
    home = make_project(); _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject(layout, "a", "\n\n本節是 L2a 至 L3 鑽石雙父 fan-in 的安全底線，屬 Tier-2 規格。\n")
    hits = {f.detail.split('"')[1] for f in _lint(layout) if f.rule == "V15"}
    assert "L2a" in hits and "雙父" in hits
    assert any(h.lower() == "fan-in" for h in hits) and any("Tier" in h for h in hits)


def test_v15_section_anchor_crossref_caught(make_project, write_leaf, monkeypatch):
    home = make_project(); _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject(layout, "a", "\n\n詳見 §跨文件待修與介面清單。\n")
    assert any(f.rule == "V15" and f.level == ERROR for f in _lint(layout))


def test_v15_dual_use_domain_terms_not_flagged(make_project, write_leaf, monkeypatch):
    """領域中合法的 上游/下游、§+標準條號 不該誤報。"""
    home = make_project(); _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject(layout, "a", "\n\n演算法級實作移交下游車端安全規格與上游詳設，依 ISO 17757 §4.2。\n")
    assert not any(f.rule == "V15" for f in _lint(layout))


def test_v15_code_span_tool_token_exempt(make_project, write_leaf, monkeypatch):
    """code 區段內的 governed-by:/factcheck 是欄位/指令範例，不該觸發 V15。"""
    home = make_project(); _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject(layout, "a", "\n\n設定範例 `governed-by: c1`，指令 `docspec factcheck`。\n")
    assert not any(f.rule == "V15" for f in _lint(layout))


# ── V16 規範逃避詞（WARN、同句 應/不得）──────────────────────────────

def test_v16_hedge_word_with_normative_keyword_caught(make_project, write_leaf, monkeypatch):
    home = make_project(); _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject(layout, "a", "\n\n系統應視情況重新啟動。本模組不得儘量避免記錄失敗事件。\n")
    v16 = [f for f in _lint(layout) if f.rule == "V16"]
    assert v16 and all(f.level == WARN for f in v16)
    hits = {f.detail.split('"')[1] for f in v16}
    assert "視情況" in hits and "儘量" in hits


def test_v16_hedge_word_without_normative_keyword_not_flagged(make_project, write_leaf, monkeypatch):
    home = make_project(); _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject(layout, "a", "\n\n維運人員最好熟悉現場環境，酌情安排巡檢排班。\n")
    assert not any(f.rule == "V16" for f in _lint(layout))


def test_v16_biyaoshi_never_flagged_even_next_to_budebu(make_project, write_leaf, monkeypatch):
    """必要時故意排除：即使同句緊鄰 不得，也不該觸發 V16。"""
    home = make_project(); _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject(layout, "a", "\n\n非經雙邊確認握手不得自行解除，必要時另行處理。\n")
    assert not any(f.rule == "V16" for f in _lint(layout))


def test_v16_different_pseudo_sentences_not_flagged(make_project, write_leaf, monkeypatch):
    home = make_project(); _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject(layout, "a", "\n\n系統應於逾時後停止服務。維護排程視情況調整。\n")
    assert not any(f.rule == "V16" for f in _lint(layout))


def test_v16_code_span_tokens_exempt(make_project, write_leaf, monkeypatch):
    """code 區段內的 應/視情況 是內容範例，不該觸發 V16。"""
    home = make_project(); _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject(layout, "a", "\n\n範例片段：`系統應視情況重新啟動`，僅供說明格式。\n")
    assert not any(f.rule == "V16" for f in _lint(layout))


# ── V17 英文 AI-ism 詞彙（WARN）──────────────────────────────────────

def test_v17_ai_ism_tokens_caught(make_project, write_leaf, monkeypatch):
    home = make_project(); _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject(layout, "a", "\n\nWe delve into the design, a testament to the team, and it "
                         "showcases seamless integration.\n")
    v17 = [f for f in _lint(layout) if f.rule == "V17"]
    assert v17 and all(f.level == WARN for f in v17)        # WARN，永不 ERROR
    hits = {f.detail.split('"')[1].lower() for f in v17}
    assert {"delve", "testament to", "showcases", "seamless"} <= hits


def test_v17_sentence_initial_in_todays_caught(make_project, write_leaf, monkeypatch):
    """行首與句末標點後的 In today's 都要抓；彎引號 apostrophe 也收。"""
    home = make_project(); _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject(layout, "a", "\n\nIn today's fast-paced API ecosystems, limits matter. "
                         "In today’s teams the answer differs.\n")
    v17 = [f for f in _lint(layout) if f.rule == "V17"]
    assert v17 and all(f.level == WARN for f in v17)
    assert sum("In today" in f.detail for f in v17) >= 2


def test_v17_narrowed_and_excluded_forms_not_flagged(make_project, write_leaf, monkeypatch):
    """ground-truthing 收窄的形態不誤報：robust／utilization／名詞 leverage／名詞 underscores／
    非片語 navigate／中句 in today's。"""
    home = make_project(); _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject(layout, "a", "\n\nThe method shows robustness to noisy context and keeps CPU "
                         "utilization low. The leverage sits in predictable places. "
                         "Names use underscores. Navigate to the settings page, then "
                         "review the notes from in today's meeting.\n")
    assert not any(f.rule == "V17" for f in _lint(layout))


def test_v17_code_span_tokens_exempt(make_project, write_leaf, monkeypatch):
    """code 區段內的觸發詞是內容（API 名/範例），不該觸發 V17。"""
    home = make_project(); _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject(layout, "a", "\n\nRun `delve debug` on the target, for example:\n\n"
                         "```\nutilize(tapestry)  # seamless\n```\n")
    assert not any(f.rule == "V17" for f in _lint(layout))


def test_v17_clean_doc_no_finding(make_project, write_leaf, monkeypatch):
    home = make_project(); _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject(layout, "a", "\n\nThe gateway rejects requests over the limit and returns 429 "
                         "with a Retry-After header.\n")
    assert not any(f.rule == "V17" for f in _lint(layout))


# ── 章節定位（F-v15-no-section-locator：交付物本文規則的 where 帶 § <section>）──────


def _two_leaves(write_leaf, home):
    for i, name in enumerate(("x", "y"), start=1):
        write_leaf(home, f"a/{name}",
                   concept={"id": f"c{i}", "title": name.upper(), "order": i, "concept": name,
                            "brief": {"audience": "a", "depth": "d",
                                      "breadth": "b", "forbidden": ["f"]}})


def _inject_into_section(layout: Layout, article: str, section: str, extra: str) -> None:
    """把文字插進指定章節的標記之後（成為該章節段的內容）。"""
    p = layout.docs_latest(article)
    text = p.read_text(encoding="utf-8")
    marker = f"<!-- dspx:section {section} -->"
    assert marker in text
    p.write_text(text.replace(marker, marker + "\n" + extra, 1), encoding="utf-8")


def test_finding_where_names_the_containing_section(make_project, write_leaf, monkeypatch):
    """V15 token 只在章節 a/y → finding 的 where 指名 § a/y（不再只有檔案級）。"""
    home = make_project(); _two_leaves(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject_into_section(layout, "a", "a/y", "\n本文件同時承接兩個治理父。\n")
    v15 = [f for f in _lint(layout) if f.rule == "V15"]
    assert v15 and all(f.where == "docs/a/_latest.md § a/y" for f in v15)
    # detail 同時導向同文件核准寫法（引章節人讀標題，非 §+編號/後台 id）
    assert all("詳見「〈章節標題〉」一節" in f.detail for f in v15)


def test_same_token_in_two_sections_yields_two_located_findings(make_project, write_leaf, monkeypatch):
    """去重單位＝每章節：同 token 洩漏兩章節＝兩筆 finding、各自可定位。"""
    home = make_project(); _two_leaves(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject_into_section(layout, "a", "a/x", "\n上表由治理父決定。\n")
    _inject_into_section(layout, "a", "a/y", "\n本節亦由治理父決定。\n")
    v15 = [f for f in _lint(layout) if f.rule == "V15"]
    assert len(v15) == 2
    assert {f.where for f in v15} == {"docs/a/_latest.md § a/x", "docs/a/_latest.md § a/y"}


def test_preamble_before_first_marker_falls_back_to_file_level(make_project, write_leaf, monkeypatch):
    """首個標記之前的文字（preamble）回退檔案級 where；整份無標記（他測已覆蓋）同理。"""
    home = make_project(); _two_leaves(write_leaf, home)
    layout = _render(home, monkeypatch)
    p = layout.docs_latest("a")
    text = p.read_text(encoding="utf-8")
    idx = text.index("<!-- dspx:")          # 任何標記（section 或 group）之前
    p.write_text(text[:idx] + "序言就提到治理父。\n\n" + text[idx:], encoding="utf-8")
    v15 = [f for f in _lint(layout) if f.rule == "V15"]
    assert v15 and all(f.where == "docs/a/_latest.md" for f in v15)


def test_v4_and_v16_findings_are_section_located_too(make_project, write_leaf, monkeypatch):
    """章節定位涵蓋整個交付物本文規則家族（不只 V15）——抽 V4/V16 各驗一筆。"""
    home = make_project(); _two_leaves(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject_into_section(layout, "a", "a/x", "\n回覆簽名 [TBD: 確認]。\n")
    _inject_into_section(layout, "a", "a/y", "\n系統應視情況重新啟動。\n")
    findings = _lint(layout)
    assert any(f.rule == "V4" and f.where == "docs/a/_latest.md § a/x" for f in findings)
    assert any(f.rule == "V16" and f.where == "docs/a/_latest.md § a/y" for f in findings)
