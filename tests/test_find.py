"""docspec find（agent 快速查找：節+面+行號+片段）＋ find --numbers（值層呈現器）＋
status --pending-facts（[TBD] 事實佇列）。"""

from __future__ import annotations

from dspx.commands.query import find as find_cmd
from dspx.commands.query import status as status_cmd
from dspx.commands.deliverable import render as render_cmd
from dspx.engine.layout import Layout

_BRIEF = {"audience": "a", "depth": "d", "breadth": "b", "forbidden": ["f"]}


def _leaf(write_leaf, home, sec="sc/x", **kw):
    return write_leaf(home, sec, concept={"id": "c1", "title": "X", "order": 1,
                                          "concept": "x", "brief": _BRIEF}, **kw)


def _inject(layout, article, section, body):
    p = layout.docs_latest(article)
    lines = p.read_text(encoding="utf-8").split("\n")
    marker = f"<!-- dspx:section {section} -->"
    out, i = [], 0
    while i < len(lines):
        out.append(lines[i])
        if lines[i].strip() == marker:
            if i + 1 < len(lines):
                out.append(lines[i + 1]); i += 1
            out.append(""); out.append(body)
        i += 1
    p.write_text("\n".join(out), encoding="utf-8", newline="\n")


def test_find_prose_reports_section_and_line(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    _leaf(write_leaf, home)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["sc"])
    layout = Layout(home)
    _inject(layout, "sc", "sc/x", "散文提到接駁車速限這個關鍵字。")
    render_cmd.run(["sc"])
    capsys.readouterr()
    monkeypatch.chdir(home.parent)
    assert find_cmd.run(["速限", "--in", "prose"]) == 0
    out = capsys.readouterr().out
    assert "sc/x" in out and "prose" in out and "_latest.md L" in out


def test_find_masks_code_fence(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    _leaf(write_leaf, home)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["sc"])
    layout = Layout(home)
    _inject(layout, "sc", "sc/x", "散文沒有那個詞。\n\n`code target here`")
    render_cmd.run(["sc"])
    capsys.readouterr()
    monkeypatch.chdir(home.parent)
    assert find_cmd.run(["target", "--in", "prose"]) == 0
    assert "no hits" in capsys.readouterr().out            # code fence 內不算命中


def test_find_decisions_face(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    _leaf(write_leaf, home, decisions=[{"id": "d1", "kind": "normative", "status": "accepted",
                                        "statement": "速限不得超過 25 km/h"}])
    monkeypatch.chdir(home.parent)
    capsys.readouterr()
    assert find_cmd.run(["速限", "--in", "decisions"]) == 0
    out = capsys.readouterr().out
    assert "decisions[0].statement" in out and "[d1]" in out


def test_find_numbers_groups_and_flags_multiple(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    _leaf(write_leaf, home)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["sc"])
    layout = Layout(home)
    _inject(layout, "sc", "sc/x", "延遲目標 100ms，另一處 timeout 是 1000ms。")
    render_cmd.run(["sc"])
    capsys.readouterr()
    monkeypatch.chdir(home.parent)
    assert find_cmd.run(["--numbers"]) == 0
    out = capsys.readouterr().out
    assert "100" in out and "1000" in out
    assert "multiple values" in out                        # 同指涉·ms 兩值 → 攤出、標記供 agent 判
    assert "drift" not in out.lower() and "reconcile" not in out.lower()  # 只攤不判


def test_status_pending_facts_lists_tbd(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    _leaf(write_leaf, home, material="## fact {#m}\n速限 [TBD] km/h（等實測）。\n")
    monkeypatch.chdir(home.parent)
    capsys.readouterr()
    assert status_cmd.run(["--pending-facts"]) == 0
    out = capsys.readouterr().out
    assert "sc/x" in out and "material" in out and "[TBD]" in out


def test_status_pending_facts_empty(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    _leaf(write_leaf, home, material="## fact {#m}\n速限 25 km/h。\n")
    monkeypatch.chdir(home.parent)
    capsys.readouterr()
    assert status_cmd.run(["--pending-facts"]) == 0
    assert "no pending facts" in capsys.readouterr().out


def test_find_in_unknown_face_fails(make_project, write_leaf, monkeypatch, capsys):
    """#6：未知 --in 面名 fail-loud（別靜默給假『不存在』）。"""
    home = make_project()
    _leaf(write_leaf, home)
    monkeypatch.chdir(home.parent)
    assert find_cmd.run(["x", "--in", "audits"]) == 2       # 打錯字（audit 才對）→ 非零、報錯


def test_status_pending_facts_finds_prose_tbd(make_project, write_leaf, monkeypatch, capsys):
    """#5：[TBD] 主要寫在散文（zero-inference），--pending-facts 要掃得到。"""
    home = make_project()
    _leaf(write_leaf, home)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["sc"])
    layout = Layout(home)
    _inject(layout, "sc", "sc/x", "回覆簽名 [TBD: 確認格式]。")
    render_cmd.run(["sc"])
    capsys.readouterr()
    monkeypatch.chdir(home.parent)
    assert status_cmd.run(["--pending-facts"]) == 0
    out = capsys.readouterr().out
    assert "prose (docs)" in out and "[TBD" in out
