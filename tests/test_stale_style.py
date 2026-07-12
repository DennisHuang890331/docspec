"""stale-style 軸：寫作 doctrine（writing-guide.md ＋ glossary.yaml）變更 → 吃它的節轉
`stale-style`、路由到 edit（就地重套風格／對齊術語，不像 stale-own 回 draft 重生散文）。

對應 change `staleness-style-doctrine-axis`。歷史盲點＝改寫作風格/術語對 staleness 完全隱形
（writing-guide/glossary 不在任何節 source_hash）；本軸補上，使「風格換了、哪些節要重套」有信號。
"""

from __future__ import annotations

import yaml

from dspx.commands.deliverable import render as render_cmd
from dspx.engine.layout import Layout
from dspx.engine.model import style_fingerprint
from dspx.engine.render import read_ledger

GUIDE_A = "# Writing guide\n\n## Project conventions\n整體文體：論文／期刊標準語言，嚴謹精確。\n"
GUIDE_B = "# Writing guide\n\n## Project conventions\n整體文體：口語化、平易近人。\n"


def _sync_of(home, article, section):
    """重算某節 sync 狀態（同 status._leaf_row）。"""
    from dspx.commands.query.status import _docs_hashes, _leaf_row
    from dspx.engine.model import decision_index, load_project
    from dspx.engine.schema import load_schema
    layout = Layout(home)
    leaves = load_project(layout)
    by = {lf.section: lf for lf in leaves}
    return _leaf_row(layout, by[section], load_schema(), True,
                     _docs_hashes(layout, article), by, decision_index(leaves))["sync"]


def _latest(home, article="g"):
    return home.parent / "docs" / article / "_latest.md"


def _baseline_with_prose(make_project, write_leaf, monkeypatch, guide=GUIDE_A):
    """建專案＋寫作守則＋一個有散文、已 render 定基準（synced）的節。回傳 home。"""
    home = make_project()
    (home / "writing-guide.md").write_text(guide, encoding="utf-8")
    write_leaf(home, "g/intro", concept={"id": "c1", "title": "概覽", "order": 1})
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    latest = _latest(home)
    latest.write_text(latest.read_text("utf-8").replace("## 1. 概覽\n", "## 1. 概覽\n\n限流保護後端。\n"), "utf-8")
    render_cmd.run(["g"])
    assert _sync_of(home, "g", "g/intro") == "synced"
    # 基準帳本已記 style 欄
    assert read_ledger(Layout(home), "g")["g/intro"].get("style") == style_fingerprint(Layout(home))
    return home


def test_writing_guide_change_restales_as_stale_style(make_project, write_leaf, monkeypatch):
    """改 writing-guide（散文未動）→ render → 該節 stale-style（不是 synced，也不是 stale-own）。"""
    home = _baseline_with_prose(make_project, write_leaf, monkeypatch)
    (home / "writing-guide.md").write_text(GUIDE_B, encoding="utf-8")
    # render（散文未重寫）→ F2 沿用舊 style → 信號存活
    render_cmd.run(["g"])
    assert _sync_of(home, "g", "g/intro") == "stale-style"


def test_glossary_change_restales_as_stale_style(make_project, write_leaf, monkeypatch):
    """改 glossary.yaml（術語權威）→ 同屬 doctrine → stale-style。"""
    home = _baseline_with_prose(make_project, write_leaf, monkeypatch)
    (home / "glossary.yaml").write_text(
        yaml.safe_dump({"terms": [{"id": "t1", "canonical": "節流", "bucket": "module"}]},
                       allow_unicode=True), encoding="utf-8")
    render_cmd.run(["g"])
    assert _sync_of(home, "g", "g/intro") == "stale-style"


def test_restyle_prose_clears_stale_style(make_project, write_leaf, monkeypatch):
    """重套風格（散文真的改）→ render → style 指紋前進 → synced。"""
    home = _baseline_with_prose(make_project, write_leaf, monkeypatch)
    (home / "writing-guide.md").write_text(GUIDE_B, encoding="utf-8")
    render_cmd.run(["g"])
    assert _sync_of(home, "g", "g/intro") == "stale-style"
    latest = _latest(home)
    latest.write_text(latest.read_text("utf-8").replace("限流保護後端。", "限流會保護後端啦。"), "utf-8")
    render_cmd.run(["g"])
    assert _sync_of(home, "g", "g/intro") == "synced"


def test_ack_clears_stale_style(make_project, write_leaf, monkeypatch):
    """散文已符新 doctrine、不需改 → render --ack → 清 stale-style（不必捏造散文）。"""
    home = _baseline_with_prose(make_project, write_leaf, monkeypatch)
    (home / "writing-guide.md").write_text(GUIDE_B, encoding="utf-8")
    render_cmd.run(["g"])
    assert _sync_of(home, "g", "g/intro") == "stale-style"
    assert render_cmd.run(["g", "--ack", "g/intro"]) == 0
    assert _sync_of(home, "g", "g/intro") == "synced"


def test_ack_refused_on_stale_own_even_if_style_also_changed(
        make_project, write_leaf, monkeypatch, capsys):
    """守門：節其實 stale-own（自己源變了）→ 即使 doctrine 也變了，--ack 仍拒絕、保住信號。"""
    home = _baseline_with_prose(make_project, write_leaf, monkeypatch)
    write_leaf.edit_replace(home, "g/intro", "title: 概覽", "title: 概覽（改）")
    (home / "writing-guide.md").write_text(GUIDE_B, encoding="utf-8")
    assert _sync_of(home, "g", "g/intro") == "stale-own"     # own 優先於 style
    capsys.readouterr()
    render_cmd.run(["g", "--ack", "g/intro"])
    assert _sync_of(home, "g", "g/intro") == "stale-own"     # 沒被吞
    assert "refused" in capsys.readouterr().err


def test_stale_own_takes_precedence_over_style(make_project, write_leaf, monkeypatch):
    """own 與 style 同時變 → 報 stale-own（較嚴重、回 draft），不被 style 遮蔽。"""
    home = _baseline_with_prose(make_project, write_leaf, monkeypatch)
    write_leaf.edit_replace(home, "g/intro", "title: 概覽", "title: 概覽（修訂）")
    (home / "writing-guide.md").write_text(GUIDE_B, encoding="utf-8")
    render_cmd.run(["g"])
    assert _sync_of(home, "g", "g/intro") == "stale-own"


def test_old_ledger_without_style_baselines_then_detects(make_project, write_leaf, monkeypatch):
    """向後相容：本軸上線前寫的帳本沒有 style 欄 → 一次 render 補基準（不誤報 stale-style）；
    之後改 doctrine 才偵測得到。"""
    from dspx.engine.render import write_ledger
    home = _baseline_with_prose(make_project, write_leaf, monkeypatch)
    # 模擬舊帳本：移除 style 欄
    ledger = read_ledger(Layout(home), "g")
    ledger["g/intro"].pop("style", None)
    write_ledger(Layout(home), "g", ledger)
    assert "style" not in read_ledger(Layout(home), "g")["g/intro"]
    # 舊帳本（無 style）不應誤報 stale-style
    assert _sync_of(home, "g", "g/intro") == "synced"
    # render（散文未動）→ 以現值補基準
    render_cmd.run(["g"])
    assert read_ledger(Layout(home), "g")["g/intro"].get("style") == style_fingerprint(Layout(home))
    assert _sync_of(home, "g", "g/intro") == "synced"
    # 之後改 doctrine → 偵測得到
    (home / "writing-guide.md").write_text(GUIDE_B, encoding="utf-8")
    render_cmd.run(["g"])
    assert _sync_of(home, "g", "g/intro") == "stale-style"
