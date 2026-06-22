"""glossary：載入/驗證、lint Vg1(同物異名)/Vg2(縮寫裸奔)。"""

from __future__ import annotations

import yaml

from dspx.check import run_check
from dspx.glossary import load_glossary, validate_glossary
from dspx.layout import Layout
from dspx.lint import run_lint
from dspx.model import load_project
from dspx.schema import load_schema


def _set_glossary(home, terms):
    (home / "glossary.yaml").write_text(
        yaml.safe_dump({"terms": terms}, allow_unicode=True, sort_keys=False), encoding="utf-8")


def test_load_and_validate(make_project):
    home = make_project()
    _set_glossary(home, [
        {"id": "rmm", "canonical": "風險估測與異常監測系統", "bucket": "module", "code": "RMM",
         "aliases_forbidden": ["安全監控系統"]},
    ])
    layout = Layout(home)
    assert len(load_glossary(layout)) == 1
    assert validate_glossary(load_glossary(layout)) == []


def test_definition_is_optional(make_project):
    """definition 是 optional 下鑽欄——帶或不帶都不報錯（無硬 invariant）。"""
    home = make_project()
    _set_glossary(home, [
        {"id": "rmm", "canonical": "風險估測與異常監測系統", "bucket": "module", "code": "RMM",
         "definition": "持續比對感測讀數與閾值、對異常發報的子系統。"},
        {"id": "bare", "canonical": "純名", "bucket": "module"},   # 無 definition
    ])
    layout = Layout(home)
    terms = load_glossary(layout)
    assert validate_glossary(terms) == []
    by_id = {t["id"]: t for t in terms}
    assert by_id["rmm"]["definition"].startswith("持續比對")
    assert "definition" not in by_id["bare"]


def test_check_catches_bad_glossary(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    _set_glossary(home, [{"id": "t1", "bucket": "bogus"}])   # 缺 canonical、bucket 非法
    layout = Layout(home)
    res = run_check(load_project(layout), load_schema(), layout)
    assert not res.ok
    assert any("canonical" in e for e in res.errors)
    assert any("bucket" in e for e in res.errors)


def test_lint_vg1_forbidden_alias(make_project, write_leaf, monkeypatch):
    from dspx.commands import render as render_cmd
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1})
    _set_glossary(home, [{"id": "rmm", "canonical": "風險估測與異常監測系統",
                          "bucket": "module", "code": "RMM", "aliases_forbidden": ["安全監控系統"]}])
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    latest = home.parent / "docs" / "g" / "_latest.md"
    latest.write_text(latest.read_text("utf-8").replace("## X\n",
                      "## X\n\n本節由安全監控系統負責，縮寫 RMM。\n"), encoding="utf-8")
    layout = Layout(home)
    findings = run_lint(layout, load_project(layout), load_schema())
    rules = {f.rule for f in findings}
    assert "Vg1" in rules     # 同物異名「安全監控系統」
    assert "Vg2" in rules     # 縮寫 RMM 裸用
