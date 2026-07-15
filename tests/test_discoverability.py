"""cli-discoverability-and-authoring-seams（batch 1）：
- show：concept payload 帶 governedBy＋section-path 第二地址形狀＋both-shapes not-found。
- list：group 節點（在地化標題）＋全列 kind＋article scoping。
- status/check/lint：article scoping（check 閘不受 scope 影響；lint 歸屬走 ` § ` 前綴契約）。
"""

from __future__ import annotations

import json

import yaml

from dspx.commands.query import check as check_cmd
from dspx.commands.query import lint as lint_cmd
from dspx.commands.query import show as show_cmd
from dspx.commands.query import status as status_cmd

def _dec(the_id: str) -> list[dict]:
    return [{"id": the_id, "kind": "normative", "status": "accepted", "statement": "規"}]


def test_show_concept_payload_carries_governed_by(make_project, write_leaf,
                                                  monkeypatch, capsys):
    """3.1：concept payload 帶 governedBy（json＋text）；無此欄位不多印。"""
    home = make_project()
    write_leaf(home, "child/x", concept={"id": "cx", "title": "X", "order": 1, "concept": "y",
                                         "governed-by": ["c-parent"]})
    write_leaf(home, "parent/y", concept={"id": "c-parent", "title": "P", "order": 1,
                                          "concept": "p"})
    monkeypatch.chdir(home.parent)
    assert show_cmd.run(["cx", "--json"]) == 0
    p = json.loads(capsys.readouterr().out)
    assert p["governedBy"] == ["c-parent"]
    assert show_cmd.run(["cx"]) == 0
    assert "governedBy" in capsys.readouterr().out
    assert show_cmd.run(["c-parent"]) == 0
    assert "governedBy" not in capsys.readouterr().out   # 空值照舊跳過


def test_show_section_path_returns_ids(make_project, write_leaf, monkeypatch, capsys):
    """3.3a：show <article>/<leaf> 回 concept＋decision id（json＋text）。"""
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "cx", "title": "X", "order": 3, "concept": "y",
                                     "status": "stable"},
               decisions=[{"id": "d1", "kind": "normative", "status": "accepted",
                           "statement": "字" * 120}],
               history=[{"id": "d-old", "kind": "normative", "status": "superseded",
                         "statement": "old", "retired-in": "v1"}])
    monkeypatch.chdir(home.parent)
    assert show_cmd.run(["g/x", "--json"]) == 0
    p = json.loads(capsys.readouterr().out)
    assert p["kind"] == "section" and p["conceptId"] == "cx"
    assert p["status"] == "stable" and p["order"] == 3     # concept.status，非 sync 狀態
    assert p["decisions"][0]["id"] == "d1"
    assert len(p["decisions"][0]["statement"]) == 80       # statement 截 80 字
    assert p["history"][0]["id"] == "d-old"
    assert show_cmd.run(["g/x"]) == 0
    out = capsys.readouterr().out
    assert "cx" in out and "d1" in out


def test_show_id_precedence_over_section_shape(make_project, write_leaf, monkeypatch, capsys):
    """3.3b：既有 id 命中維持原 payload（精確 id 先行）。"""
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "cx", "title": "X", "order": 1, "concept": "one-liner"})
    monkeypatch.chdir(home.parent)
    assert show_cmd.run(["cx", "--json"]) == 0
    p = json.loads(capsys.readouterr().out)
    assert p["kind"] == "concept" and p["concept"] == "one-liner"


def test_show_not_found_mentions_both_shapes(make_project, write_leaf, monkeypatch, capsys):
    """3.3d：garbage 引數 → exit 1，訊息同時提 id 與 section。"""
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "cx", "title": "X", "order": 1})
    monkeypatch.chdir(home.parent)
    assert show_cmd.run(["no/where"]) == 1
    err = capsys.readouterr().err
    assert "id or section" in err and "docspec status" in err


# ── 4. status: group nodes（list 已併入 status；group 列由 status 補上）─────────────

def _titled_group_corpus(home, write_leaf):
    write_leaf(home, "demo/intro", concept={"id": "ci", "title": "導言", "order": 1,
                                            "concept": "x"})
    write_leaf(home, "demo/guide/setup", concept={"id": "cs", "title": "安裝", "order": 1,
                                                  "concept": "y"})
    write_leaf.group(home, "demo/guide", title="操作指南", order=2)


def test_status_group_node_with_localized_title(make_project, write_leaf, monkeypatch, capsys):
    """titled group.yaml → status 的 group 列（text＋json）帶在地化標題。"""
    home = make_project()
    _titled_group_corpus(home, write_leaf)
    monkeypatch.chdir(home.parent)
    assert status_cmd.run([]) == 0
    assert "[group] demo/guide/ — 操作指南" in capsys.readouterr().out
    assert status_cmd.run(["--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    g = next(r for r in data["groups"] if r["section"] == "demo/guide")
    assert g["title"] == "操作指南" and g["order"] == 2.0 and g["article"] == "demo"


def test_status_group_nodes_scoped_to_article(make_project, write_leaf, monkeypatch, capsys):
    """status <article> 的 group 列只含該文章；--section 指單一 leaf 時不列 group。"""
    home = make_project()
    _titled_group_corpus(home, write_leaf)
    write_leaf(home, "other/g/x", concept={"id": "ox", "title": "X", "order": 1, "concept": "z"})
    monkeypatch.chdir(home.parent)
    assert status_cmd.run(["demo", "--json"]) == 0
    groups = json.loads(capsys.readouterr().out)["groups"]
    assert {g["section"] for g in groups} == {"demo/guide"}
    assert status_cmd.run(["--section", "demo/intro", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["groups"] == []


# ── 5. status / check / lint scoping ────────────────────────────────────────

def _two_article_project(home, write_leaf):
    write_leaf(home, "a/x", concept={"id": "ca", "title": "AX", "order": 1, "concept": "x"},
               decisions=_dec("d-a"))
    write_leaf(home, "b/y", concept={"id": "cb", "title": "BY", "order": 1, "concept": "y"},
               decisions=_dec("d-b"))


def test_status_scoped_by_article_and_section_anded(make_project, write_leaf,
                                                    monkeypatch, capsys):
    """5.1：status <a> 只列 a 的列；--section 續用且 AND；no-arg 不變；unknown → 1。"""
    home = make_project()
    _two_article_project(home, write_leaf)
    monkeypatch.chdir(home.parent)
    capsys.readouterr()

    assert status_cmd.run(["a", "--json"]) == 0
    secs = [r["section"] for r in json.loads(capsys.readouterr().out)["sections"]]
    assert secs and all(s.split("/", 1)[0] == "a" for s in secs)

    assert status_cmd.run(["a", "--section", "a/x", "--json"]) == 0
    secs = [r["section"] for r in json.loads(capsys.readouterr().out)["sections"]]
    assert secs == ["a/x"]

    assert status_cmd.run(["--json"]) == 0        # no-arg：全列
    secs = {r["section"] for r in json.loads(capsys.readouterr().out)["sections"]}
    assert {"a/x", "b/y"} <= secs

    assert status_cmd.run(["nope"]) == 1
    assert 'no leaf sections found for article "nope"' in capsys.readouterr().err


def test_check_scope_green_filters_index_only(make_project, write_leaf, monkeypatch, capsys):
    """5.2b：綠路 index 只剩該文章 id＋pinned note；json ok/errors/warnings 與無 scope 相同。"""
    home = make_project()
    _two_article_project(home, write_leaf)
    monkeypatch.chdir(home.parent)

    assert check_cmd.run(["--json"]) == 0
    full = json.loads(capsys.readouterr().out)
    assert check_cmd.run(["a", "--json"]) == 0
    scoped = json.loads(capsys.readouterr().out)
    assert scoped["scope"] == "a"
    assert scoped["ok"] == full["ok"]
    assert scoped["errors"] == full["errors"] and scoped["warnings"] == full["warnings"]
    assert set(scoped["index"]["ids"]) == {"ca", "d-a"}
    assert scoped["index"]["sections"] == ["a/x"]

    assert check_cmd.run(["a"]) == 0
    out = capsys.readouterr().out
    assert "ca" in out and "cb" not in out
    assert '(index scoped to "a"; check itself always validates the whole project)' in out


def test_check_scope_never_hides_errors(make_project, write_leaf, monkeypatch, capsys):
    """5.2a：另一文章的 ERROR 在 check <a> 下照樣紅、照樣印（scope 對錯誤零影響）。"""
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "ca", "title": "AX", "order": 1, "concept": "x"})
    write_leaf(home, "b/y", concept={"id": "cb", "title": "BY", "order": 1, "concept": "y",
                                     "realizes": ["ghost-decision"]})     # 死引用在 b
    monkeypatch.chdir(home.parent)
    assert check_cmd.run(["a"]) == 1
    out = capsys.readouterr().out
    assert "ghost-decision" in out                # 跨文章錯誤照印
    assert check_cmd.run(["a", "--json"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is False and any("ghost-decision" in e for e in data["errors"])


def _plant_locator_leaks(home):
    """兩文章各一個 V1 洩漏，交付物帶 section marker → where＝`docs/<art>/_latest.md § <sec>`。"""
    for art, sec, cid in (("a", "a/x", "ca"), ("b", "b/y", "cb")):
        docs = home.parent / "docs" / art
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "_latest.md").write_text(
            f"<!-- dspx:section {sec} -->\n## T\n\n洩漏 {cid} 在散文。\n", encoding="utf-8")


def test_lint_scope_filters_by_locator_where(make_project, write_leaf, monkeypatch, capsys):
    """5.3a：locator 形 where（` § ` 尾綴）——b 的 finding 在 lint a 下被濾、a 的保留。"""
    home = make_project()
    _two_article_project(home, write_leaf)
    _plant_locator_leaks(home)
    monkeypatch.chdir(home.parent)
    assert lint_cmd.run(["a", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    wheres = [f["where"] for f in data["findings"] if f["rule"] == "V1"]
    assert wheres == ["docs/a/_latest.md § a/x"]          # locator 形、只剩 a
    assert not any(w.startswith("docs/b/") for w in (f["where"] for f in data["findings"]))


def test_lint_scope_keeps_unattributable_findings(make_project, write_leaf,
                                                  monkeypatch, capsys):
    """5.3b：歸不到任何 article 的 finding（forest roadmap Vr）在 scope 下存活。"""
    home = make_project()
    _two_article_project(home, write_leaf)
    (home / "roadmap.yaml").write_text(yaml.safe_dump({"entries": [
        {"id": "r1", "title": "森林項", "what": "w", "target": "forest",
         "promoted-to": "chg-x"}]}, allow_unicode=True), encoding="utf-8")
    monkeypatch.chdir(home.parent)
    assert lint_cmd.run(["a", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert any(f["rule"] == "Vr2" and f["where"] == "forest/roadmap.yaml"
               for f in data["findings"])   # promoted-to 卻仍帶 what/target、專案級不被藏


def test_lint_scope_json_errorcount_reflects_filter(make_project, write_leaf,
                                                    monkeypatch, capsys):
    """5.3c：errorCount 反映過濾後清單；5.3d：no-arg 輸出不變（兩文章都在）。"""
    home = make_project()
    _two_article_project(home, write_leaf)
    _plant_locator_leaks(home)
    monkeypatch.chdir(home.parent)

    assert lint_cmd.run(["--json"]) == 0
    full = json.loads(capsys.readouterr().out)
    v1_all = [f for f in full["findings"] if f["rule"] == "V1"]
    assert {f["where"] for f in v1_all} == {"docs/a/_latest.md § a/x",
                                            "docs/b/_latest.md § b/y"}   # no-arg 不變

    assert lint_cmd.run(["a", "--json"]) == 0
    scoped = json.loads(capsys.readouterr().out)
    v1_scoped = [f for f in scoped["findings"] if f["rule"] == "V1"]
    assert scoped["errorCount"] == full["errorCount"] - len(v1_all) + len(v1_scoped)
    assert lint_cmd.run(["nope"]) == 1
    assert 'no leaf sections found for article "nope"' in capsys.readouterr().err
