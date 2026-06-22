"""引擎指令 end-to-end（new / retire / lint / publish / status staleness）。"""

from __future__ import annotations

import yaml

from dspx.commands import check as check_cmd
from dspx.commands import lint as lint_cmd
from dspx.commands import new as new_cmd
from dspx.commands import publish as publish_cmd
from dspx.commands import ready as ready_cmd
from dspx.commands import retire as retire_cmd


def _entries(path):
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("entries", [])


def test_new_scaffolds_develop_only(make_project, monkeypatch):
    """develop 階段只建 develop.md；concept/decisions 由結晶時才產（不預建空 stub）。"""
    home = make_project()
    monkeypatch.chdir(home.parent)
    assert new_cmd.run(["guide/intro"]) == 0
    leaf = home / "corpus" / "guide" / "intro"
    assert (leaf / "develop.md").is_file()
    assert not (leaf / "concept.yaml").exists()
    assert not (leaf / "decisions.yaml").exists()
    assert not (leaf / "material.md").exists()
    assert not (leaf / "history.yaml").exists()


def test_new_then_instructions_on_uncrystallized(make_project, monkeypatch, capsys):
    """未結晶節（只有 develop.md）也能投影；concept 模板的 id/order 已填好供結晶。"""
    import json
    from dspx.commands import instructions as instr
    home = make_project()
    monkeypatch.chdir(home.parent)
    new_cmd.run(["g/a"])
    new_cmd.run(["g/b"])
    capsys.readouterr()
    assert instr.run(["develop", "g/b", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    tpl = "".join(w.get("template") or "" for w in data["writes"])
    assert "sec-" in tpl          # concept 模板 id 已填
    assert "order: 2" in tpl      # 同層第二個 → order 接龍 2


def test_new_refuses_overwrite(make_project, monkeypatch):
    home = make_project()
    monkeypatch.chdir(home.parent)
    assert new_cmd.run(["g/a"]) == 0
    assert new_cmd.run(["g/a"]) == 2


def test_ready_graduates_complete_and_drained(make_project, write_leaf, monkeypatch):
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1, "concept": "real"},
               decisions=[{"id": "d1", "kind": "normative", "status": "accepted", "statement": "s"}],
               develop="<!-- thinking workbench, now drained -->")
    monkeypatch.chdir(home.parent)
    assert ready_cmd.run(["g/x"]) == 0
    assert not (home / "corpus" / "g" / "x" / "develop.md").exists()  # 刪除＝畢業的持久動作


def test_ready_refuses_when_develop_has_content(make_project, write_leaf, monkeypatch):
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1, "concept": "real"},
               decisions=[{"id": "d1", "kind": "normative", "status": "accepted", "statement": "s"}],
               develop="## still thinking\nthis paragraph is not yet distributed")
    monkeypatch.chdir(home.parent)
    assert ready_cmd.run(["g/x"]) == 1
    assert (home / "corpus" / "g" / "x" / "develop.md").is_file()  # 帶內容不准畢業、不刪


def test_ready_refuses_incomplete_fields(make_project, write_leaf, monkeypatch):
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1, "concept": ""},
               decisions=[{"id": "d1", "kind": "normative", "status": "accepted", "statement": "s"}],
               develop="")
    monkeypatch.chdir(home.parent)
    assert ready_cmd.run(["g/x"]) == 1


def test_ready_refuses_uncrystallized(make_project, monkeypatch):
    home = make_project()
    monkeypatch.chdir(home.parent)
    new_cmd.run(["g/a"])                       # 只有 develop.md
    assert ready_cmd.run(["g/a"]) == 1         # 缺 concept/decisions


def test_show_decision_and_concept_payload(make_project, write_leaf, monkeypatch, capsys):
    import json
    from dspx.commands import show
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1, "concept": "one-liner",
                                      "brief": {"audience": "a", "depth": "d", "breadth": "b"}},
               decisions=[{"id": "d1", "kind": "normative", "status": "accepted",
                           "statement": "the rule", "rationale": "because"}])
    monkeypatch.chdir(home.parent)
    assert show.run(["d1", "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["kind"] == "decision" and d["statement"] == "the rule" and d["rationale"] == "because"
    assert show.run(["c1", "--json"]) == 0
    c = json.loads(capsys.readouterr().out)
    assert c["kind"] == "concept" and c["concept"] == "one-liner" and c["brief"]["audience"] == "a"


def test_retired_lists_active_decision_retirements(make_project, write_leaf, monkeypatch, capsys):
    import json
    from dspx.commands import retired as retired_cmd
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1},
               history=[{"id": "d-old", "kind": "normative", "status": "superseded",
                         "statement": "old rule", "retired-in": "v2"}])
    monkeypatch.chdir(home.parent)
    assert retired_cmd.run(["--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert any(d["id"] == "d-old" and d["section"] == "g/x" for d in data["retiredDecisions"])


def test_show_retired_decision_reads_history_md(make_project, write_leaf, monkeypatch, capsys):
    import json
    from dspx.commands import retire as retire_cmd
    from dspx.commands import show
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1},
               decisions=[{"id": "d-old", "kind": "normative", "status": "deprecated",
                           "statement": "old", "rationale": "because reasons"}])
    monkeypatch.chdir(home.parent)
    retire_cmd.run(["a/x"])          # d-old → history.yaml；rationale → history.md ## d-old
    capsys.readouterr()
    assert show.run(["d-old", "--json"]) == 0
    p = json.loads(capsys.readouterr().out)
    assert p["kind"] == "history" and "because reasons" in (p.get("rationale") or "")


def test_show_unknown_id(make_project, monkeypatch):
    from dspx.commands import show
    home = make_project()
    monkeypatch.chdir(home.parent)
    assert show.run(["ghost", "--json"]) == 1


def test_show_glossary_term_drilldown(make_project, write_leaf, monkeypatch, capsys):
    """glossary term id → show 回完整 record（含 definition/english）——精瘦索引的下鑽。"""
    import json
    from dspx.commands import show
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1})
    (home / "glossary.yaml").write_text(yaml.safe_dump({"terms": [
        {"id": "rmm", "canonical": "風險估測系統", "bucket": "module", "code": "RMM",
         "english": "Risk Monitoring Module", "definition": "監測異常並發報的子系統。",
         "aliases_forbidden": ["安全監控系統"]},
    ]}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    monkeypatch.chdir(home.parent)
    assert show.run(["rmm", "--json"]) == 0
    p = json.loads(capsys.readouterr().out)
    assert p["kind"] == "glossary"
    assert p["definition"] == "監測異常並發報的子系統。"
    assert p["english"] == "Risk Monitoring Module"
    assert p["canonical"] == "風險估測系統" and p["bucket"] == "module"


def test_instructions_glossary_block_is_lean(make_project, write_leaf, monkeypatch, capsys):
    """instructions draft 的術語段＝精瘦索引：含 canonical/bucket/forbidden，不含 definition/english 文字。"""
    from dspx.commands import instructions as instr_cmd
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1})
    (home / "glossary.yaml").write_text(yaml.safe_dump({"terms": [
        {"id": "rmm", "canonical": "風險估測系統", "bucket": "module", "code": "RMM",
         "english": "Risk Monitoring Module", "definition": "監測異常並發報的子系統。",
         "aliases_forbidden": ["安全監控系統"]},
    ]}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    monkeypatch.chdir(home.parent)
    assert instr_cmd.run(["draft", "g/x"]) == 0
    out = capsys.readouterr().out
    # 精瘦：定義/英文不出現在注入文字
    assert "監測異常並發報的子系統" not in out
    assert "Risk Monitoring Module" not in out
    # 但 canonical + bucket + forbidden + 下鑽提示都在
    assert "風險估測系統" in out
    assert "module" in out
    assert "安全監控系統" in out         # aliases_forbidden
    assert "docspec show" in out         # 下鑽提示


def _write_roadmap_file(path, entries):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"entries": entries}, allow_unicode=True,
                                   sort_keys=False), encoding="utf-8")


def test_instructions_develop_prints_roadmap(make_project, write_leaf, monkeypatch, capsys):
    """develop 投影印「待辦（roadmap）」段（本文件＋forest）；draft 不印。"""
    from dspx.commands import instructions as instr_cmd
    home = make_project()
    write_leaf(home, "art", concept={"id": "c-art", "title": "Art", "order": 1,
                                     "concept": "x", "brief": {"audience": "a"}})
    _write_roadmap_file(home / "roadmap.yaml", [
        {"id": "f1", "kind": "task", "status": "open", "title": "森林工作",
         "what": "w", "target": "forest"}])
    _write_roadmap_file(home / "corpus" / "art" / "roadmap.yaml", [
        {"id": "r1", "kind": "task", "status": "open", "title": "可開工",
         "what": "w", "target": "art"}])
    monkeypatch.chdir(home.parent)

    assert instr_cmd.run(["develop", "art"]) == 0
    out = capsys.readouterr().out
    assert "Backlog (roadmap)" in out
    assert "r1" in out and "f1" in out

    assert instr_cmd.run(["draft", "art"]) == 0
    assert "Backlog (roadmap)" not in capsys.readouterr().out


def test_guide_projects_workflow_and_artifacts(make_project, monkeypatch, capsys):
    import json
    from dspx.commands import guide
    home = make_project()
    monkeypatch.chdir(home.parent)
    assert guide.run(["--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["workflow"].get("loop")                       # 敘事來自 schema、非 hardcode
    assert len(data["workflow"].get("skills", [])) == 6   # develop/draft/edit/factcheck/publish/release
    ids = {a["id"] for a in data["artifacts"]}
    assert {"concept", "decisions", "develop"} <= ids         # 涵蓋每個 schema artifact
    concept = next(a for a in data["artifacts"] if a["id"] == "concept")
    assert "brief.audience" in concept["requiredFields"] and "develop" in concept["reader"]


def test_instructions_emits_required_fields(make_project, monkeypatch, capsys):
    import json
    from dspx.commands import instructions as instr
    home = make_project()
    monkeypatch.chdir(home.parent)
    new_cmd.run(["g/a"])
    capsys.readouterr()
    assert instr.run(["develop", "g/a", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    concept_w = next(w for w in data["writes"] if w["id"] == "concept")
    rf = concept_w["requiredFields"]
    assert "concept" in rf and "brief.audience" in rf and "brief.depth" in rf and "brief.breadth" in rf


def test_factcheck_gets_ancestor_normative(make_project, write_leaf, monkeypatch, capsys):
    # P3-lite：引擎把祖先鏈 normative 決策當非阻塞供料餵給 factcheck
    import json
    from dspx.commands import instructions as instr
    home = make_project()
    write_leaf(home, "art", concept={"id": "root", "title": "Art", "order": 1, "concept": "x",
                                      "brief": {"audience": "a", "depth": "d", "breadth": "b"}},
               decisions=[{"id": "dec-sot", "kind": "normative", "status": "accepted",
                           "statement": "ICD is the only SoT"}])
    write_leaf(home, "art/child", concept={"id": "c2", "title": "Child", "order": 1, "concept": "y"})
    monkeypatch.chdir(home.parent)
    assert instr.run(["factcheck", "art/child", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    an = data["ancestorNormative"]
    assert any(d["id"] == "dec-sot" for a in an for d in a["decisions"])
    # draft 不該拿到（只有 factcheck）
    capsys.readouterr()
    instr.run(["draft", "art/child", "--json"])
    assert json.loads(capsys.readouterr().out)["ancestorNormative"] == []


def test_list_json_includes_concept_and_status(make_project, write_leaf, monkeypatch, capsys):
    import json
    from dspx.commands import list_cmd
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1, "concept": "the one-liner"},
               decisions=[{"id": "d1", "kind": "normative", "status": "accepted", "statement": "s"}])
    monkeypatch.chdir(home.parent)
    assert list_cmd.run(["--json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    row = next(r for r in rows if r["section"] == "g/x")
    assert row["concept"] == "the one-liner"
    assert row["status"] == "ready"


def test_hook_postcheck_flags_incomplete(make_project, write_leaf, monkeypatch):
    from dspx.commands import hook
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1, "concept": ""})
    monkeypatch.chdir(home.parent)
    cpath = home / "corpus" / "g" / "x" / "concept.yaml"
    # exit 2＝把「必填未齊」提醒餵回 agent（非阻擋，檔已寫）
    assert hook._postcheck({"tool_input": {"file_path": str(cpath)}}) == 2


def test_hook_postcheck_passes_complete(make_project, write_leaf, monkeypatch):
    from dspx.commands import hook
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1, "concept": "real"})
    monkeypatch.chdir(home.parent)
    cpath = home / "corpus" / "g" / "x" / "concept.yaml"
    assert hook._postcheck({"tool_input": {"file_path": str(cpath)}}) == 0


def test_hook_postcheck_never_disturbs(tmp_path):
    from dspx.commands import hook
    # 非 corpus 檔 / 不在專案 / 壞輸入 → 一律放行 0，絕不干擾 agent
    assert hook._postcheck({"tool_input": {"file_path": str(tmp_path / "x.txt")}}) == 0
    assert hook._postcheck({"tool_input": {"file_path": str(tmp_path / "concept.yaml")}}) == 0
    assert hook._postcheck(None) == 0
    assert hook._postcheck({}) == 0


def test_retire_moves_superseded(make_project, write_leaf, monkeypatch):
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1},
               decisions=[
                   {"id": "d-old", "kind": "normative", "status": "superseded", "statement": "舊"},
                   {"id": "d-new", "kind": "normative", "status": "accepted", "statement": "新"},
               ])
    monkeypatch.chdir(home.parent)
    assert retire_cmd.run(["g/x", "--in", "t1"]) == 0
    leaf = home / "corpus" / "g" / "x"
    dec_ids = [e["id"] for e in _entries(leaf / "decisions.yaml")]
    his = _entries(leaf / "history.yaml")
    assert dec_ids == ["d-new"]
    assert his[0]["id"] == "d-old" and his[0]["retired-in"] == "t1"
    # 搬後 check 仍綠
    assert check_cmd.run([]) == 0


def test_lint_flags_leaks(make_project, write_leaf, monkeypatch):
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "sec-leak", "title": "X", "order": 1})
    docs = home.parent / "docs" / "g"
    docs.mkdir(parents=True)
    (docs / "_latest.md").write_text("看 sec-leak 與 [TBD] 還有 {#m-a}", encoding="utf-8")
    monkeypatch.chdir(home.parent)
    rules = set()
    import dspx.lint as lint_mod
    from dspx.layout import Layout
    from dspx.model import load_project
    from dspx.schema import load_schema
    findings = lint_mod.run_lint(Layout(home), load_project(Layout(home)), load_schema())
    rules = {f.rule for f in findings}
    assert {"V1", "V2", "V4"} <= rules
    assert lint_cmd.run([]) == 0  # lint 單跑不擋（回 0）


def test_lint_v3_allows_domain_notation_flags_scaffold(make_project, write_leaf, monkeypatch):
    """V3：技術標記（KE 模板 <vehicle_id>、泛型 <T>、code 內 {…}）不誤報；真鷹架 {id} 仍抓。"""
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1})
    docs = home.parent / "docs" / "g"
    docs.mkdir(parents=True)
    monkeypatch.chdir(home.parent)
    import dspx.lint as lint_mod
    from dspx.layout import Layout
    from dspx.model import load_project
    from dspx.schema import load_schema

    # 領域標記在 code 與散文裡都合法 → 不該觸發 V3
    (docs / "_latest.md").write_text(
        "訂閱 `fleet/sc/<vehicle_id>/status`。\n```\nfleet/sc/<vid>/cmd/{session_id}\n```\n泛型 <T> 也合法。",
        encoding="utf-8")
    findings = lint_mod.run_lint(Layout(home), load_project(Layout(home)), load_schema())
    assert not any(f.rule == "V3" for f in findings)

    # 真鷹架字 {id} 殘留（非 code）→ 仍要抓
    (docs / "_latest.md").write_text("殘留 {id} 沒填", encoding="utf-8")
    findings = lint_mod.run_lint(Layout(home), load_project(Layout(home)), load_schema())
    assert any(f.rule == "V3" for f in findings)


def test_publish_gate_and_staleness(make_project, write_leaf, monkeypatch):
    from dspx.commands import render as render_cmd
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1},
               decisions=[{"id": "d1", "kind": "normative", "status": "accepted", "statement": "規"}])
    monkeypatch.chdir(home.parent)
    docs = home.parent / "docs" / "g"

    render_cmd.run(["g"])                      # 建骨架
    latest = docs / "_latest.md"
    latest.write_text(
        latest.read_text(encoding="utf-8").replace("## X\n", "## X\n\n內文。\n"),
        encoding="utf-8")                       # 模擬 draft 寫散文
    assert publish_cmd.run(["g"]) == 0
    assert (docs / "archive" / "v1.0.0.md").is_file()
    meta = yaml.safe_load(latest.read_text("utf-8").split("---")[1])
    assert meta["version"] == "1.0.0"
    assert "g/x" in meta["sections"]


def test_publish_aborts_on_dirty_docs(make_project, write_leaf, monkeypatch):
    from dspx.commands import render as render_cmd
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "sec-leak", "title": "X", "order": 1})
    monkeypatch.chdir(home.parent)
    docs = home.parent / "docs" / "g"
    render_cmd.run(["g"])
    latest = docs / "_latest.md"
    latest.write_text(                          # 散文洩漏內部 id → lint ERROR
        latest.read_text(encoding="utf-8").replace("## X\n", "## X\n\n洩漏 sec-leak。\n"),
        encoding="utf-8")
    assert publish_cmd.run(["g"]) == 1
