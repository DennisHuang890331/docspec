"""docspec normalize（capability prose-spans D2＋D4）。

散文半形→全形轉換、byte-exact 跳過、冪等、dry-run 不寫、帳本自持（無假 drift、stale 信號保留）。
"""

from __future__ import annotations

from pathlib import Path

from dspx.commands.deliverable import _normalize as normalize_cmd
from dspx.commands.deliverable import render as render_cmd
from dspx.engine.layout import Layout
from dspx.engine.render import detect_drift, read_ledger


def _leaf(write_leaf, home, section="a/x"):
    write_leaf(home, section, concept={"id": "c1", "title": "X", "order": 1, "concept": "x",
                                       "brief": {"audience": "a", "depth": "d",
                                                 "breadth": "b", "forbidden": ["f"]}})


def _render(home: Path, monkeypatch, article="a") -> Layout:
    monkeypatch.chdir(home.parent)
    render_cmd.run([article])
    return Layout(home)


def _set_prose(layout: Layout, article: str, body: str) -> None:
    """把交付物某節散文換成 body（保留 render 骨架），再 render 記指紋。"""
    p = layout.docs_latest(article)
    text = p.read_text(encoding="utf-8")
    # 在標題行後注入散文（最小 fixture 只有一節）
    text = text.rstrip() + "\n\n" + body + "\n"
    p.write_text(text, encoding="utf-8")


def test_pure_prose_converted(make_project, write_leaf, monkeypatch):
    home = make_project(); _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _set_prose(layout, "a", "本系統支援兩種模式,並在啟動時擇一.")
    render_cmd.run(["a"])   # 記 prose 指紋
    monkeypatch.chdir(home.parent)
    rc = normalize_cmd.run(["a"])
    assert rc == 0
    out = layout.docs_latest("a").read_text(encoding="utf-8")
    assert "模式，並在啟動時擇一。" in out
    assert "模式,並" not in out


def test_identifier_and_code_byte_exact(make_project, write_leaf, monkeypatch):
    home = make_project(); _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _set_prose(layout, "a", "設定 `retry_max=3`, 逾時後停止。\n\n見 e_stop, 然後停止。\n\n"
                            "```\n{\"a\": 1, \"b\": 2}\n```")
    render_cmd.run(["a"])
    monkeypatch.chdir(home.parent)
    before = layout.docs_latest("a").read_text(encoding="utf-8")
    normalize_cmd.run(["a"])
    after = layout.docs_latest("a").read_text(encoding="utf-8")
    # inline code、fenced code、識別碼尾隨標點皆 byte-exact
    assert "`retry_max=3`," in after      # 逗號左鄰為 backtick（非 CJK）不轉
    assert "e_stop, 然後" in after         # 識別碼尾隨逗號不轉
    assert '{"a": 1, "b": 2}' in after    # fenced code 逐 byte 不變


def test_dry_run_writes_nothing(make_project, write_leaf, monkeypatch):
    home = make_project(); _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _set_prose(layout, "a", "模式一,模式二。")
    render_cmd.run(["a"])
    monkeypatch.chdir(home.parent)
    before = layout.docs_latest("a").read_text(encoding="utf-8")
    ledger_before = read_ledger(layout, "a")
    rc = normalize_cmd.run(["a", "--dry-run"])
    assert rc == 0
    assert layout.docs_latest("a").read_text(encoding="utf-8") == before   # 檔案不變
    assert read_ledger(layout, "a") == ledger_before                        # 帳本不變


def test_idempotent(make_project, write_leaf, monkeypatch):
    home = make_project(); _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _set_prose(layout, "a", "模式一,模式二,模式三。")
    render_cmd.run(["a"])
    monkeypatch.chdir(home.parent)
    normalize_cmd.run(["a"])
    once = layout.docs_latest("a").read_text(encoding="utf-8")
    monkeypatch.chdir(home.parent)
    normalize_cmd.run(["a"])
    twice = layout.docs_latest("a").read_text(encoding="utf-8")
    assert once == twice


def test_no_false_drift_after_normalize(make_project, write_leaf, monkeypatch):
    """帳本自持：normalize 後 detect_drift 不報該節（prose 指紋已更新）。"""
    home = make_project(); _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _set_prose(layout, "a", "第一段,第二段。")
    render_cmd.run(["a"])
    monkeypatch.chdir(home.parent)
    assert detect_drift(layout, "a") == []      # render 後乾淨
    normalize_cmd.run(["a"])
    assert detect_drift(layout, "a") == []       # normalize 後仍乾淨（無假 drift）


def test_stale_own_signal_preserved(make_project, write_leaf, monkeypatch):
    """既有 stale-own（own 指紋為舊值）在 normalize 後不被吸收（own 未被重蓋）。"""
    home = make_project(); _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _set_prose(layout, "a", "設定,啟動。")
    render_cmd.run(["a"])
    monkeypatch.chdir(home.parent)
    ledger_before = read_ledger(layout, "a")
    own_before = ledger_before["a/x"]["own"]
    normalize_cmd.run(["a"])
    ledger_after = read_ledger(layout, "a")
    assert ledger_after["a/x"]["own"] == own_before                 # own 未動（stale 信號保留）
    assert ledger_after["a/x"]["prose"] != ledger_before["a/x"]["prose"]  # prose 已更新
