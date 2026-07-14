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


def test_find_numbers_flags_conflict_only_via_glossary(make_project, write_leaf, monkeypatch, capsys):
    """★壓測抓到：只有 glossary 真量名的組能誠實標「多值」——這樣跨文件同量才聚得起來、
    旗標才有意義（不是同節同單位的假分組）。"""
    home = make_project()
    _leaf(write_leaf, home)
    (home / "glossary.yaml").write_text(
        "terms:\n  - id: t1\n    canonical: 回應延遲\n    bucket: standard\n", encoding="utf-8")
    monkeypatch.chdir(home.parent)
    render_cmd.run(["sc"])
    layout = Layout(home)
    _inject(layout, "sc", "sc/x", "回應延遲不超過 100ms；另一處回應延遲卻是 1000ms。")
    render_cmd.run(["sc"])
    capsys.readouterr()
    monkeypatch.chdir(home.parent)
    assert find_cmd.run(["--numbers"]) == 0
    out = capsys.readouterr().out
    assert "回應延遲 · ms" in out                          # 用 glossary 量名當鍵
    assert "multiple values for the same quantity" in out  # 同一量兩值 → 誠實標
    assert "drift" not in out.lower() and "reconcile" not in out.lower()  # 只攤不判


def test_find_numbers_empty_glossary_no_false_flag(make_project, write_leaf, monkeypatch, capsys):
    """★壓測抓到：glossary 空時退回 section 分組——**不得**在假分組上亂標「多值」（違反只呈現不判），
    且要提示補 glossary。"""
    home = make_project()
    _leaf(write_leaf, home)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["sc"])
    layout = Layout(home)
    _inject(layout, "sc", "sc/x", "人行穿越距離 20 公尺；感測範圍 30 公尺。")   # 不同量、同單位
    render_cmd.run(["sc"])
    capsys.readouterr()
    monkeypatch.chdir(home.parent)
    assert find_cmd.run(["--numbers"]) == 0
    out = capsys.readouterr().out
    assert "20" in out and "30" in out
    assert "multiple values for the same quantity" not in out   # 不同量、不亂標
    assert "grouped by section" in out and "glossary is empty" in out  # 誠實 + 指路補 glossary


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
