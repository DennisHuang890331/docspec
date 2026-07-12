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
    from dspx.commands.deliverable import render as render_cmd
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1})
    _set_glossary(home, [{"id": "rmm", "canonical": "風險估測與異常監測系統",
                          "bucket": "module", "code": "RMM", "aliases_forbidden": ["安全監控系統"]}])
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    latest = home.parent / "docs" / "g" / "_latest.md"
    latest.write_text(latest.read_text("utf-8").replace("## 1. X\n",
                      "## 1. X\n\n本節由安全監控系統負責，縮寫 RMM。\n"), encoding="utf-8")
    layout = Layout(home)
    findings = run_lint(layout, load_project(layout), load_schema())
    rules = {f.rule for f in findings}
    assert "Vg1" in rules     # 同物異名「安全監控系統」
    assert "Vg2" in rules     # 縮寫 RMM 裸用、且 canonical 從未出現 → 報


# ── Vg1 遮蔽法（lint-false-positive-batch D3）────────────────────────────


def _render_with_insert(make_project, write_leaf, monkeypatch, terms, insert):
    """建專案＋glossary＋render，把 insert 塞進交付物，回傳 findings。"""
    from dspx.commands.deliverable import render as render_cmd
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1})
    _set_glossary(home, terms)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    latest = home.parent / "docs" / "g" / "_latest.md"
    latest.write_text(latest.read_text("utf-8").replace("## 1. X\n", "## 1. X\n\n" + insert + "\n"),
                      encoding="utf-8")
    layout = Layout(home)
    return run_lint(layout, load_project(layout), load_schema())


_OCC_TERM = [{"id": "occ", "canonical": "行控中心", "bucket": "module",
              "aliases_forbidden": ["行控"]}]


def test_lint_vg1_substring_alias_masked_no_false_positive(make_project, write_leaf, monkeypatch):
    """alias「行控」⊂ canonical「行控中心」：正文寫對正名 → 遮蔽後無裸用、零 Vg1。"""
    findings = _render_with_insert(make_project, write_leaf, monkeypatch, _OCC_TERM,
                                   "本節由行控中心統一調度，行控中心亦負責回報。")
    assert not any(f.rule == "Vg1" for f in findings)


def test_lint_vg1_bare_alias_still_caught(make_project, write_leaf, monkeypatch):
    """裸用「行控」（未被任何 canonical 出現處覆蓋）仍報 Vg1。"""
    findings = _render_with_insert(make_project, write_leaf, monkeypatch, _OCC_TERM,
                                   "本節由行控中心統一調度；異常時由行控通知現場。")
    vg1 = [f for f in findings if f.rule == "Vg1"]
    assert vg1 and any("行控" in f.detail for f in vg1)


def test_lint_vg1_code_span_alias_exempt(make_project, write_leaf, monkeypatch):
    """fenced/inline code 內的別名 token 是內容（欄位名/範例），不報 Vg1。"""
    findings = _render_with_insert(
        make_project, write_leaf, monkeypatch,
        [{"id": "t", "canonical": "風險估測系統", "bucket": "module",
          "aliases_forbidden": ["監控系統"]}],
        "欄位 `監控系統` 為列名。\n\n```\nkey: 監控系統\n```")
    assert not any(f.rule == "Vg1" for f in findings)


def test_validate_alias_substring_of_own_canonical_rejected():
    """alias 為自己 canonical 的子字串＝死配置 → 結構錯誤、指名 term 與別名。"""
    errs = validate_glossary([{"id": "occ", "canonical": "行控中心", "bucket": "module",
                               "aliases_forbidden": ["行控"]}])
    assert any("occ" in e and "行控" in e for e in errs)


def test_validate_alias_overlapping_other_term_canonical_ok():
    """跨 term 重疊（A 的別名 ⊂ B 的 canonical）不受此不變量限制。"""
    errs = validate_glossary([
        {"id": "occ", "canonical": "行控中心", "bucket": "module"},
        {"id": "dsp", "canonical": "調度系統", "bucket": "module",
         "aliases_forbidden": ["行控"]},
    ])
    assert errs == []


def test_lint_vg2_suppressed_when_canonical_localized(make_project, write_leaf, monkeypatch):
    """canonical 已在文中出現（首用已在地化）→ 後續裸用縮寫不再每次誤報 Vg2。"""
    from dspx.commands.deliverable import render as render_cmd
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1})
    _set_glossary(home, [{"id": "rmm", "canonical": "風險估測與異常監測系統",
                          "bucket": "module", "code": "RMM"}])
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    latest = home.parent / "docs" / "g" / "_latest.md"
    # canonical 首次展開後、再裸用 RMM 當 shorthand
    latest.write_text(latest.read_text("utf-8").replace("## X\n",
                      "## X\n\n本節由風險估測與異常監測系統（RMM）負責；後續 RMM 偵測異常。\n"),
                      encoding="utf-8")
    layout = Layout(home)
    findings = run_lint(layout, load_project(layout), load_schema())
    assert "Vg2" not in {f.rule for f in findings}   # 已在地化 → 不誤報
