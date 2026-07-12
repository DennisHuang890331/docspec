"""lint V6（material 散文滲入）、V8（骨肉漂移）、Vr1-3（roadmap 軟提醒，統無狀態模型改版）。"""

from __future__ import annotations

from pathlib import Path

import yaml

from dspx.check import run_check
from dspx.commands.deliverable import render as render_cmd
from dspx.layout import Layout
from dspx.lint import run_lint
from dspx.model import load_project
from dspx.schema import load_schema


def _write_roadmap(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"entries": entries}, allow_unicode=True,
                                   sort_keys=False), encoding="utf-8")


def test_v6_prose_in_material(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1},
               material="## fact: 標題 {#m-a}\n這是一段散文。\n第二行散文。\n第三行散文。\n第四行散文。\n")
    layout = Layout(home)
    findings = run_lint(layout, load_project(layout), load_schema())
    assert any(f.rule == "V6" for f in findings)


def test_v6_ignores_fenced_code_block(make_project, write_leaf):
    """material 的圍欄式程式碼區塊（draft 要逐字渲染）不該被 V6 當散文誤報。"""
    home = make_project()
    code = "```python\nimport zenoh\ns = zenoh.open()\nx = 1\ny = 2\nz = 3\n```"
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1},
               material=f"## src: 範例 {{#m-a}}\n{code}\n")
    layout = Layout(home)
    findings = run_lint(layout, load_project(layout), load_schema())
    assert not any(f.rule == "V6" for f in findings)


def test_v8_drift_missing_section(make_project, write_leaf, monkeypatch):
    home = make_project()
    write_leaf(home, "g/a", concept={"id": "c1", "title": "A", "order": 1})
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])                       # _latest 有 g/a
    write_leaf(home, "g/b", concept={"id": "c2", "title": "B", "order": 2})  # 新增、未 render
    layout = Layout(home)
    findings = run_lint(layout, load_project(layout), load_schema())
    assert any(f.rule == "V8" and "g/b" in f.detail for f in findings)


# ── Vr1-3 roadmap 軟提醒（皆 WARN、非阻塞；統無狀態模型：present=backlog）────

def _root(home, write_leaf):
    write_leaf(home, "art", concept={"id": "c-art", "title": "Art", "order": 1,
                                     "concept": "x",
                                     "brief": {"audience": "a", "depth": "d",
                                               "breadth": "b", "forbidden": ["f"]}})


def test_vr1_too_many_entries_warns(make_project, write_leaf):
    home = make_project()
    _root(home, write_leaf)
    _write_roadmap(home / "corpus" / "art" / "roadmap.yaml", [
        {"id": f"r{i}", "kind": "task", "title": "t",
         "what": "w", "target": "art"} for i in range(8)   # 8 > 7
    ])
    layout = Layout(home)
    findings = run_lint(layout, load_project(layout), load_schema())
    vr1 = [f for f in findings if f.rule == "Vr1"]
    assert vr1 and all(f.level == "WARN" for f in vr1)
    # 非阻塞：check 仍綠
    assert run_check(load_project(layout), load_schema(), layout=layout).ok


def test_vr2_promoted_entry_still_substantial_warns(make_project, write_leaf):
    """含 promoted-to 卻仍帶實質內容（如 what/target）→ 搬家沒搬乾淨。"""
    home = make_project()
    _root(home, write_leaf)
    _write_roadmap(home / "corpus" / "art" / "roadmap.yaml", [
        {"id": "r1", "kind": "task", "title": "t", "what": "w", "target": "art",
         "promoted-to": "chg-x"}])
    layout = Layout(home)
    findings = run_lint(layout, load_project(layout), load_schema())
    assert any(f.rule == "Vr2" and f.level == "WARN" for f in findings)


def test_vr2_clean_collapsed_promoted_entry_no_warn(make_project, write_leaf):
    """乾淨收攏（只剩 id/title/promoted-to）→ 不誤報。"""
    home = make_project()
    _root(home, write_leaf)
    _write_roadmap(home / "corpus" / "art" / "roadmap.yaml", [
        {"id": "r1", "title": "t", "promoted-to": "chg-x"}])
    layout = Layout(home)
    findings = run_lint(layout, load_project(layout), load_schema())
    assert not any(f.rule == "Vr2" for f in findings)


def test_vr3_roadmap_audit_mirror_warns(make_project, write_leaf, monkeypatch):
    """entry.what 散文引用一條仍全文開放的 finding id → 雙帳鏡像 WARN。"""
    from dspx.commands.governance import audit as audit_cmd
    home = make_project()
    _root(home, write_leaf)
    monkeypatch.chdir(home.parent)
    assert audit_cmd.run(["raise", "--target", "art", "--face", "logic",
                          "--sev", "med", "--finding", "散文問題"]) == 0
    _write_roadmap(home / "corpus" / "art" / "roadmap.yaml", [
        {"id": "r1", "kind": "task", "title": "t", "what": "修 (audit F1)", "target": "art"}])
    layout = Layout(home)
    findings = run_lint(layout, load_project(layout), load_schema())
    assert any(f.rule == "Vr3" and f.level == "WARN" for f in findings)


def test_vr3_no_mirror_when_finding_closed(make_project, write_leaf, monkeypatch):
    from dspx.commands.governance import audit as audit_cmd
    home = make_project()
    _root(home, write_leaf)
    monkeypatch.chdir(home.parent)
    assert audit_cmd.run(["raise", "--target", "art", "--face", "logic",
                          "--sev", "med", "--finding", "散文問題"]) == 0
    assert audit_cmd.run(["resolve", "F1", "--status", "fixed"]) == 0
    _write_roadmap(home / "corpus" / "art" / "roadmap.yaml", [
        {"id": "r1", "kind": "task", "title": "t", "what": "修 (audit F1)", "target": "art"}])
    layout = Layout(home)
    findings = run_lint(layout, load_project(layout), load_schema())
    assert not any(f.rule == "Vr3" for f in findings)
