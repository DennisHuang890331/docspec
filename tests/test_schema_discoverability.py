"""develop-schema-discoverability-and-ready-gate：
- HIGH#2 _entries 誤名頂層 key fail-loud（修 ready false-green）；真空仍合法。
- HIGH#1 closed fieldmap 拒未知 key（brief.diagram 等發明）。
- HIGH#1 完整封閉契約投影（type/enum values/entries 容器/optional 封閉欄）+ YAML skeleton。
"""

from __future__ import annotations

import pytest
import yaml

from dspx.check import run_check
from dspx.layout import Layout
from dspx.model import ModelError, load_leaf, load_project
from dspx.schema import field_contract, load_schema, yaml_skeleton


# ── HIGH#2：誤名頂層 key fail-loud ───────────────────────────────────────────

def _write_concept(leaf):
    (leaf / "concept.yaml").write_text(
        yaml.safe_dump({"id": "c1", "title": "X", "order": 1, "status": "draft",
                        "concept": "x", "brief": {}}, allow_unicode=True, sort_keys=False),
        encoding="utf-8")


def test_misnamed_decisions_key_fails_loud(make_project, tmp_path):
    home = make_project()
    leaf = home / "corpus" / "a" / "x"
    leaf.mkdir(parents=True)
    _write_concept(leaf)
    # 誤把 decisions.yaml 頂層寫成 `decisions:` 而非 `entries:`（含實質條目）
    (leaf / "decisions.yaml").write_text(
        yaml.safe_dump({"decisions": [{"id": "d1", "kind": "normative",
                                       "status": "accepted", "statement": "x"}]},
                       allow_unicode=True, sort_keys=False),
        encoding="utf-8")
    with pytest.raises(ModelError) as exc:
        load_leaf(Layout(home), leaf)
    assert "entries" in str(exc.value)  # hint 指向正確 key


def test_empty_entries_file_is_legal(make_project):
    home = make_project()
    leaf = home / "corpus" / "a" / "x"
    leaf.mkdir(parents=True)
    _write_concept(leaf)
    # 真正空：空檔 + 明確 entries: []，皆合法（視為 0 條，不報結構錯）
    (leaf / "decisions.yaml").write_text("entries: []\n", encoding="utf-8")
    (leaf / "history.yaml").write_text("", encoding="utf-8")
    lf = load_leaf(Layout(home), leaf)
    assert lf.decisions == [] and lf.history == []


# ── HIGH#1：closed fieldmap 拒未知 key ───────────────────────────────────────

def test_invented_brief_diagram_key_fails(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1,
                                     "concept": "x",
                                     "brief": {"audience": "a", "depth": "d", "breadth": "b",
                                               "diagram": "some spec"}})  # 發明的 key
    res = run_check(load_project(Layout(home)), load_schema())
    assert not res.ok
    assert any("unknown field" in e and "diagram" in e for e in res.errors)


def test_unknown_concept_toplevel_key_fails(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1, "concept": "x",
                                     "made_up": "value"})
    res = run_check(load_project(Layout(home)), load_schema())
    assert not res.ok
    assert any("unknown field" in e and "made_up" in e for e in res.errors)


def test_known_brief_keys_pass(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1, "concept": "x",
                                     "brief": {"audience": "a", "depth": "d", "breadth": "b",
                                               "forbidden": ["q"], "layout": "diagram",
                                               "kind": "reference"}})
    res = run_check(load_project(Layout(home)), load_schema())
    assert res.ok


# ── HIGH#1：完整封閉契約投影 ─────────────────────────────────────────────────

def test_field_contract_carries_type_and_enum_values():
    s = load_schema()
    concept = {f["name"]: f for f in field_contract(s.by_id("concept").schema)}
    assert concept["status"]["type"] == "enum"
    assert concept["status"]["values"] == ["draft", "stable", "deprecated"]
    assert concept["governed-by"]["type"] == "list[ref]"
    brief = {f["name"]: f for f in concept["brief"]["fields"]}
    assert brief["layout"]["values"] == ["prose", "table", "list", "diagram"]
    assert concept["brief"]["closed"] is True


def test_filing_rules_carry_sibling_dependency_via_realizes(make_project, monkeypatch, capsys):
    """#13c：sibling/跨文件決策依賴走 concept.realizes 的規則落 schema.yaml filing-rules、
    由 guide 投影（鐵律2：規則住 schema、被投影，不散落散文）。"""
    import json as _json

    from dspx.commands.projection import guide

    s = load_schema()
    ids = {r.get("id") for r in s.filing_rules}
    assert "sibling-dependency-via-realizes" in ids

    home = make_project()
    monkeypatch.chdir(home.parent)
    assert guide.run(["--json"]) == 0
    data = _json.loads(capsys.readouterr().out)
    rules = {r["id"]: r["rule"] for r in data["filingRules"]}
    assert "sibling-dependency-via-realizes" in rules
    assert "concept.realizes" in rules["sibling-dependency-via-realizes"]
    assert "stale-upstream" in rules["sibling-dependency-via-realizes"]


def test_yaml_skeleton_entries_container_and_enum_comments():
    s = load_schema()
    dec = yaml_skeleton(s.by_id("decisions"))
    assert dec.startswith("entries:")        # 容器形狀
    assert "kind: normative" in dec and "normative | rationale" in dec  # enum 註解
    con = yaml_skeleton(s.by_id("concept"))
    assert "status: draft" in con and "draft | stable | deprecated" in con
    # differential-brief contract (contract-slimming): brief is now a fully-optional object, so the
    # required-only skeleton no longer emits it (an agent writes brief only for the diff-from-ancestor;
    # brief's shape is still discoverable via the field contract / `docspec guide`).
    assert "brief:" not in con
    assert "status: develop" not in con       # develop/status 撞詞：skeleton 絕不出現非法值
