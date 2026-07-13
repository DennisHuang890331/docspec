"""docspec edit（機械精準修改原語：--punct / --term / --replace）。

--punct/--term 是 normalize/rename-term 的統一入口（委派；核心邏輯各自已有測）；本檔重點測
新的 --replace：節定位 literal 替換、**不越節**、code/URL 遮罩、dry-run 零寫入、0 命中 exit 1。
"""

from __future__ import annotations

from pathlib import Path

from dspx.commands.deliverable import edit as edit_cmd
from dspx.commands.deliverable import render as render_cmd
from dspx.engine.layout import Layout

_BRIEF = {"audience": "a", "depth": "d", "breadth": "b", "forbidden": ["f"]}


def _two_leaves(write_leaf, home):
    write_leaf(home, "sc/a", concept={"id": "c1", "title": "A", "order": 1, "concept": "x", "brief": _BRIEF})
    write_leaf(home, "sc/b", concept={"id": "c2", "title": "B", "order": 2, "concept": "x", "brief": _BRIEF})


def _inject(layout: Layout, article: str, section: str, body: str) -> None:
    p = layout.docs_latest(article)
    lines = p.read_text(encoding="utf-8").split("\n")
    marker = f"<!-- dspx:section {section} -->"
    out: list[str] = []
    i = 0
    while i < len(lines):
        out.append(lines[i])
        if lines[i].strip() == marker:
            if i + 1 < len(lines):
                out.append(lines[i + 1]); i += 1
            out.append(""); out.append(body)
        i += 1
    p.write_text("\n".join(out), encoding="utf-8", newline="\n")


def _setup(make_project, write_leaf, monkeypatch, a_body: str, b_body: str = "乙節也有 target 但不該被動到。"):
    home = make_project()
    _two_leaves(write_leaf, home)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["sc"])
    layout = Layout(home)
    _inject(layout, "sc", "sc/a", a_body)
    _inject(layout, "sc", "sc/b", b_body)
    render_cmd.run(["sc"])
    return home, layout


def test_replace_scoped_to_one_section_only(make_project, write_leaf, monkeypatch, capsys):
    home, layout = _setup(make_project, write_leaf, monkeypatch,
                          "甲節有 target 出現兩次 target 這裡。")
    capsys.readouterr()
    monkeypatch.chdir(home.parent)
    assert edit_cmd.run(["sc/a", "--replace", "target", "目標"]) == 0
    out = layout.docs_latest("sc").read_text(encoding="utf-8")
    assert "甲節有 目標 出現兩次 目標 這裡。" in out          # 甲節換了（兩處）
    assert "乙節也有 target 但不該被動到。" in out            # 乙節逐 byte 不動
    assert "2 hit(s)" in capsys.readouterr().out


def test_replace_dry_run_writes_nothing(make_project, write_leaf, monkeypatch, capsys):
    home, layout = _setup(make_project, write_leaf, monkeypatch, "甲節 target 在此。")
    before = layout.docs_latest("sc").read_text(encoding="utf-8")
    capsys.readouterr()
    monkeypatch.chdir(home.parent)
    assert edit_cmd.run(["sc/a", "--replace", "target", "目標", "--dry-run"]) == 0
    assert "--dry-run" in capsys.readouterr().out
    assert layout.docs_latest("sc").read_text(encoding="utf-8") == before


def test_replace_zero_hit_exits_1(make_project, write_leaf, monkeypatch, capsys):
    home, layout = _setup(make_project, write_leaf, monkeypatch, "甲節 target 在此。")
    monkeypatch.chdir(home.parent)
    assert edit_cmd.run(["sc/a", "--replace", "不存在", "X"]) == 1


def test_replace_unknown_section_exits_1(make_project, write_leaf, monkeypatch):
    home, layout = _setup(make_project, write_leaf, monkeypatch, "甲節 target 在此。")
    monkeypatch.chdir(home.parent)
    assert edit_cmd.run(["sc/nope", "--replace", "target", "X"]) == 1


def test_replace_masks_inline_code(make_project, write_leaf, monkeypatch, capsys):
    home, layout = _setup(make_project, write_leaf, monkeypatch,
                          "散文 target 在此。 `code target here` 收尾。")
    capsys.readouterr()
    monkeypatch.chdir(home.parent)
    assert edit_cmd.run(["sc/a", "--replace", "target", "目標"]) == 0
    out = layout.docs_latest("sc").read_text(encoding="utf-8")
    assert "散文 目標 在此。" in out                         # 散文換
    assert "`code target here`" in out                      # inline code byte-exact


def test_punct_mode_delegates(make_project, write_leaf, monkeypatch, capsys):
    home, layout = _setup(make_project, write_leaf, monkeypatch, "甲節逗號,接續。")
    capsys.readouterr()
    monkeypatch.chdir(home.parent)
    assert edit_cmd.run(["sc", "--punct"]) == 0
    assert "，" in layout.docs_latest("sc").read_text(encoding="utf-8")   # 半形→全形


def test_term_mode_delegates(make_project, write_leaf, monkeypatch, capsys):
    home, layout = _setup(make_project, write_leaf, monkeypatch, "AGV 是搬運車。")
    capsys.readouterr()
    monkeypatch.chdir(home.parent)
    assert edit_cmd.run(["sc", "--term", "AGV", "無人搬運車"]) == 0
    assert "無人搬運車 是搬運車。" in layout.docs_latest("sc").read_text(encoding="utf-8")
