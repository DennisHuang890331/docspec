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
                                               "breadth": "b", "forbidden": "f"}})


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
