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


def test_new_seeds_develop_header_with_id_title_order(make_project, monkeypatch):
    """#5/#6：new 把 id/title/order 種進 develop.md 註解頭（id 持久化、--title 生效）；
    種子是純註解 → drain_remainder 永不擋畢業。"""
    home = make_project()
    monkeypatch.chdir(home.parent)
    assert new_cmd.run(["demo/intro", "--title", "導言"]) == 0
    body = (home / "corpus" / "demo" / "intro" / "develop.md").read_text(encoding="utf-8")
    assert "sec-" in body                 # 生成的 id 持久化在鷹架裡
    assert "導言" in body                  # --title 不再是 no-op
    assert "order: 1" in body
    assert ready_cmd.drain_remainder(body) == ""   # 種子＝註解，不算實質殘留

    assert new_cmd.run(["demo/guide"]) == 0        # 無 --title → 路徑末段
    body2 = (home / "corpus" / "demo" / "guide" / "develop.md").read_text(encoding="utf-8")
    assert "guide" in body2
    assert ready_cmd.drain_remainder(body2) == ""


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


def test_show_addresses_dead_decision_in_place(make_project, write_leaf, monkeypatch, capsys):
    """contract-slimming D3：死決策留原 decisions.yaml、就地可 show（不搬 history.yaml）。"""
    import json
    from dspx.commands import retire as retire_cmd
    from dspx.commands import show
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1},
               decisions=[{"id": "d-old", "kind": "normative", "status": "deprecated",
                           "statement": "old", "rationale": "because reasons"}])
    monkeypatch.chdir(home.parent)
    assert retire_cmd.run(["a/x"]) == 0        # 純報告、零寫入
    assert not (home / "corpus" / "a" / "x" / "history.yaml").exists()
    capsys.readouterr()
    # 死決策留原檔＝show 就地定址（kind:decision，rationale 直接在條目上）
    assert show.run(["d-old", "--json"]) == 0
    p = json.loads(capsys.readouterr().out)
    assert p["kind"] == "decision" and "because reasons" in (p.get("rationale") or "")


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
    assert instr_cmd.run(["apply", "g/x"]) == 0
    out = capsys.readouterr().out
    # 精瘦：定義/英文不出現在注入文字
    assert "監測異常並發報的子系統" not in out
    assert "Risk Monitoring Module" not in out
    # 但 canonical + bucket + forbidden + 下鑽提示都在
    assert "風險估測系統" in out
    assert "module" in out
    assert "安全監控系統" in out         # aliases_forbidden
    assert "docspec show" in out         # 下鑽提示


def test_instructions_backstage_projections_warn_against_narration(make_project, write_leaf, monkeypatch, capsys):
    """報幕防漏：brief / coverage / coherence / ancestor 投影都帶『別唸進交付物』後台警告。"""
    from dspx.commands import instructions as instr_cmd
    home = make_project()
    write_leaf(home, "art", concept={"id": "root", "title": "Art", "order": 1, "concept": "x",
                                     "brief": {"audience": "a", "depth": "d", "breadth": "b"}},
               decisions=[{"id": "dec-sot", "kind": "normative", "status": "accepted",
                           "statement": "ICD is the only SoT"}])
    write_leaf(home, "art/child",
               concept={"id": "c2", "title": "Child", "order": 1, "concept": "y",
                        "brief": {"audience": "a", "depth": "d", "breadth": "b",
                                  "forbidden": ["不寫封包格式"]},
                        "must_cover": ["黑通道定義"]},
               decisions=[{"id": "d2", "kind": "normative", "status": "accepted", "statement": "規"}])
    monkeypatch.chdir(home.parent)

    # draft：自身 brief/sources（Readable）+ 父鏈 brief + 祖先 normative 都帶後台警告
    assert instr_cmd.run(["apply", "art/child"]) == 0
    out = capsys.readouterr().out
    assert "constraints/provenance you OBEY" in out      # 自身 brief/sources
    assert "本節規範" in out                              # 守護字串點名報幕句式
    assert "obey these inherited constraints" in out      # 父鏈 brief
    assert "backstage governance you OBEY" in out         # 祖先 normative

    # factcheck：coverage + coherence 也帶後台警告
    assert instr_cmd.run(["factcheck", "art/child"]) == 0
    out2 = capsys.readouterr().out
    assert "backstage completeness check" in out2         # coverage contract
    assert "本節約束下游" in out2                          # coverage/coherence 守護點名


def test_instructions_writing_guide_precedes_sections_with_tail_pointer(make_project, write_leaf, monkeypatch, capsys):
    """F-edit-projection-too-large：writing guide（風格權威）印在大宗逐節內容之前（緊接 header），
    輸出最末一行回指它——巨量/被截尾的投影從頭從尾都找得到；只調順序、無截斷機制。"""
    from dspx.commands import instructions as instr_cmd
    home = make_project()
    (home / "writing-guide.md").write_text("# Writing guide\n\n風格權威哨兵句。\n", encoding="utf-8")
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1})
    monkeypatch.chdir(home.parent)
    assert instr_cmd.run(["apply", "g/x"]) == 0
    out = capsys.readouterr().out
    assert out.index("Writing guide") < out.index("── Readable")   # 風格權威在逐節內容之前
    assert out.rstrip().splitlines()[-1].startswith("(style authority:")  # 尾端回指


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
        {"id": "f1", "kind": "task", "title": "森林工作",
         "what": "w", "target": "forest"}])
    _write_roadmap_file(home / "corpus" / "art" / "roadmap.yaml", [
        {"id": "r1", "kind": "task", "title": "可開工",
         "what": "w", "target": "art"}])
    monkeypatch.chdir(home.parent)

    assert instr_cmd.run(["develop", "art"]) == 0
    out = capsys.readouterr().out
    assert "Backlog (roadmap)" in out
    assert "r1" in out and "f1" in out

    assert instr_cmd.run(["apply", "art"]) == 0
    assert "Backlog (roadmap)" not in capsys.readouterr().out


def test_guide_projects_workflow_and_artifacts(make_project, monkeypatch, capsys):
    import json
    from dspx.commands import guide
    home = make_project()
    monkeypatch.chdir(home.parent)
    assert guide.run(["--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["workflow"].get("loop")                       # 敘事來自 schema、非 hardcode
    assert len(data["workflow"].get("skills", [])) == 5   # develop/apply/factcheck/publish/release
    ids = {a["id"] for a in data["artifacts"]}
    assert {"concept", "decisions", "develop"} <= ids         # 涵蓋每個 schema artifact
    concept = next(a for a in data["artifacts"] if a["id"] == "concept")
    # differential-brief contract (contract-slimming): brief and its sub-fields are OPTIONAL
    # (write only the diff from the ancestor chain; root completeness enforced by the hierarchy
    # check, not schema-required). Top-level concept identity fields stay required; brief is still
    # discoverable in the field contract as an optional (closed) object.
    assert "concept" in concept["requiredFields"] and "develop" in concept["reader"]
    assert "brief.audience" not in concept["requiredFields"]
    brief_field = next(f for f in concept["fieldContract"] if f["name"] == "brief")
    assert brief_field.get("required") is False


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
    # differential-brief contract (contract-slimming): brief sub-fields are optional now.
    assert "concept" in rf
    assert "brief.audience" not in rf and "brief.depth" not in rf and "brief.breadth" not in rf


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
    # M4：draft 現在也拿得到祖先 normative（落筆遵守 ruling；供料、非 gate）
    capsys.readouterr()
    instr.run(["apply", "art/child", "--json"])
    draft_an = json.loads(capsys.readouterr().out)["ancestorNormative"]
    assert any(d["id"] == "dec-sot" for a in draft_an for d in a["decisions"])


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


def test_list_shows_develop_only_sections(make_project, monkeypatch, capsys):
    """只有 develop.md（未結晶）的節：status 看得到，list 也要看得到（同 liveness 判準），
    不可誤報 Corpus is empty。"""
    import json
    from dspx.commands import list_cmd, new as new_cmd
    home = make_project()
    monkeypatch.chdir(home.parent)
    new_cmd.run(["g/intro"])                      # 只建 develop.md、未結晶
    # text 模式：不說 empty、列出該節並標 developing
    assert list_cmd.run([]) == 0
    out = capsys.readouterr().out
    assert "Corpus is empty" not in out
    assert "g/intro" in out and "developing" in out
    # json 模式：含該節、status=developing
    assert list_cmd.run(["--json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert any(r["section"] == "g/intro" and r["status"] == "developing" for r in rows)


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


def test_retire_is_non_mutating(make_project, write_leaf, monkeypatch, capsys):
    """contract-slimming D3：retire 純報告、零寫入——死決策留原 decisions.yaml、不生 history.yaml。"""
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1},
               decisions=[
                   {"id": "d-old", "kind": "normative", "status": "superseded", "statement": "舊"},
                   {"id": "d-new", "kind": "normative", "status": "accepted", "statement": "新"},
               ])
    monkeypatch.chdir(home.parent)
    leaf = home / "corpus" / "g" / "x"
    before = (leaf / "decisions.yaml").read_bytes()
    assert retire_cmd.run(["g/x", "--in", "t1"]) == 0
    # 死決策留原檔（一個 byte 不動）、無 history.yaml、報告點名死決策
    assert (leaf / "decisions.yaml").read_bytes() == before
    assert [e["id"] for e in _entries(leaf / "decisions.yaml")] == ["d-old", "d-new"]
    assert not (leaf / "history.yaml").exists()
    assert "d-old" in capsys.readouterr().out
    # 報告後 check 仍綠
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
        latest.read_text(encoding="utf-8").replace("## 1. X\n", "## 1. X\n\n內文。\n"),
        encoding="utf-8")                       # 模擬 draft 寫散文
    assert publish_cmd.run(["g"]) == 0
    assert (docs / "archive" / "v1.0.0.md").is_file()
    meta = yaml.safe_load(latest.read_text("utf-8").split("---")[1])
    assert meta["version"] == "1.0.0"
    # 指紋帳本現存隱藏 sidecar（ISSUE-3），不在 _latest frontmatter
    from dspx.layout import Layout
    from dspx.render import read_ledger
    assert "g/x" in read_ledger(Layout(home), "g")


def test_publish_aborts_on_dirty_docs(make_project, write_leaf, monkeypatch):
    from dspx.commands import render as render_cmd
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "sec-leak", "title": "X", "order": 1})
    monkeypatch.chdir(home.parent)
    docs = home.parent / "docs" / "g"
    render_cmd.run(["g"])
    latest = docs / "_latest.md"
    latest.write_text(                          # 散文洩漏內部 id → lint ERROR
        latest.read_text(encoding="utf-8").replace("## 1. X\n", "## 1. X\n\n洩漏 sec-leak。\n"),
        encoding="utf-8")
    assert publish_cmd.run(["g"]) == 1


# ── C2：publish i18n + 版本正確性 ──────────────────────────────────

def _render_and_draft(home, monkeypatch, write_leaf, prose):
    from dspx.commands import render as render_cmd
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1})
    monkeypatch.chdir(home.parent)
    docs = home.parent / "docs" / "g"
    render_cmd.run(["g"])
    latest = docs / "_latest.md"
    latest.write_text(latest.read_text("utf-8").replace("## 1. X\n", f"## 1. X\n\n{prose}\n"),
                      encoding="utf-8")
    return docs


def test_publish_first_version_not_labeled_patch(make_project, write_leaf, monkeypatch):
    home = make_project()
    _render_and_draft(home, monkeypatch, write_leaf, "內文。")
    assert publish_cmd.run(["g"]) == 0
    from dspx.layout import Layout
    cl = Layout(home).docs_changelog("g").read_text("utf-8")
    assert "1.0.0" in cl
    assert "Patch" not in cl and "首版" in cl   # 首版不標自相矛盾的 Patch


def test_publish_refuses_noop_bump(make_project, write_leaf, monkeypatch):
    home = make_project()
    docs = _render_and_draft(home, monkeypatch, write_leaf, "內文。")
    assert publish_cmd.run(["g"]) == 0           # v1.0.0
    assert publish_cmd.run(["g"]) == 1           # 無改動 → no-op 拒
    assert not (docs / "archive" / "v1.0.1.md").is_file()
    assert publish_cmd.run(["g", "--allow-noop"]) == 0   # 強制放行
    assert (docs / "archive" / "v1.0.1.md").is_file()


def test_publish_english_changelog(make_project, write_leaf, monkeypatch):
    home = make_project("language: en\ndocs_layout: per-article\n")
    _render_and_draft(home, monkeypatch, write_leaf, "Body text.")
    assert publish_cmd.run(["g"]) == 0
    from dspx.layout import Layout
    cl = Layout(home).docs_changelog("g").read_text("utf-8")
    assert "| Version | Date | Level | Summary |" in cl
    assert "Initial" in cl
    assert "版本" not in cl and "（未填摘要）" not in cl


def test_publish_changelog_level_localized_by_content(make_project, write_leaf, monkeypatch):
    """非首版級別欄依**文件語言**在地化：中文交付物 → 中文級別（非英文「Patch」）。"""
    home = make_project()
    docs = _render_and_draft(home, monkeypatch, write_leaf, "中文內文第一版。")
    assert publish_cmd.run(["g"]) == 0                         # v1.0.0 首版
    latest = docs / "_latest.md"
    latest.write_text(latest.read_text("utf-8").replace("第一版", "第二版"), encoding="utf-8")
    assert publish_cmd.run(["g", "--level", "patch", "--note", "修字"]) == 0  # v1.0.1
    from dspx.layout import Layout
    cl = Layout(home).docs_changelog("g").read_text("utf-8")
    assert "修訂" in cl              # 中文級別 map（patch→修訂）
    assert "Patch" not in cl        # 不冒英文


def test_publish_changelog_language_detected_not_config(make_project, write_leaf, monkeypatch):
    """英文交付物即使專案 config.language 為預設 zh-TW，changelog 仍走英文（內容偵測 > config）。"""
    home = make_project()   # 預設 config.language = zh-TW
    _render_and_draft(home, monkeypatch, write_leaf, "This deliverable is written in English prose.")
    assert publish_cmd.run(["g"]) == 0
    from dspx.layout import Layout
    cl = Layout(home).docs_changelog("g").read_text("utf-8")
    assert "| Version | Date | Level | Summary |" in cl   # 英文表頭
    assert "版本" not in cl                                # 無中文殘留（雖 config 是 zh-TW）
    assert "(no summary)" in cl


# ── publish --dry-run（8.1，Decision 8）───────────────────────────────


def _watch_state(paths):
    return {str(p): (p.read_bytes() if p.is_file() else None) for p in paths}


def test_publish_dry_run_green_zero_writes(make_project, write_leaf, monkeypatch, capsys):
    """8.1a：全綠 → exit 0；_latest/帳本/changelog/快照夾全部位元不變。"""
    from dspx.layout import Layout
    home = make_project()
    docs = _render_and_draft(home, monkeypatch, write_leaf, "內文。")
    layout = Layout(home)
    watch = [docs / "_latest.md", layout.docs_ledger("g"), layout.docs_changelog("g")]
    before = _watch_state(watch)
    capsys.readouterr()
    assert publish_cmd.run(["g", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "✓ check" in out and "✓ lint" in out and "✓ coverage" in out
    assert "no-op: skipped (no prior version)" in out
    assert "version preview: v1.0.0" in out
    assert "dry-run verdict: GO" in out
    assert _watch_state(watch) == before               # 零寫入
    assert not (docs / "archive").exists()             # 無快照


def test_publish_dry_run_red_lint_prints_consolidated_report(make_project, write_leaf,
                                                             monkeypatch, capsys):
    """8.1b：lint ERROR → exit 1、零寫入，且**彙總報告照印**（含 lint fail 行＋其餘閘行；
    舊單閘 abort 訊息不出現＝分支點在既有閘區塊之前）。"""
    from dspx.commands import render as render_cmd
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "sec-leak", "title": "X", "order": 1})
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    docs = home.parent / "docs" / "g"
    latest = docs / "_latest.md"
    latest.write_text(                                 # 散文洩漏內部 id → lint ERROR
        latest.read_text(encoding="utf-8").replace("## 1. X\n", "## 1. X\n\n洩漏 sec-leak。\n"),
        encoding="utf-8")
    before = latest.read_bytes()
    capsys.readouterr()
    assert publish_cmd.run(["g", "--dry-run"]) == 1
    captured = capsys.readouterr()
    assert "✗ lint:" in captured.out and "ERROR finding(s)" in captured.out
    assert "✓ check" in captured.out and "coverage" in captured.out   # 彙總、非 early-return
    assert "dry-run verdict: NO-GO" in captured.out
    assert "publish aborted" not in captured.err       # 舊 abort 訊息不得出現
    assert latest.read_bytes() == before
    assert not (docs / "archive").exists()


def test_publish_dry_run_no_prose_is_nogo(make_project, write_leaf, monkeypatch, capsys):
    """8.1c：零散文 → coverage 閘 fail、exit 1。"""
    from dspx.commands import render as render_cmd
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1})
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])                              # 只有骨架
    capsys.readouterr()
    assert publish_cmd.run(["g", "--dry-run"]) == 1
    out = capsys.readouterr().out
    assert "✗ coverage: no written sections yet" in out
    assert "dry-run verdict: NO-GO" in out


def test_publish_dry_run_noop_gate_and_allow_noop(make_project, write_leaf, monkeypatch, capsys):
    """8.1d：內容與前版位元相同 → no-op 行＋exit 1；--allow-noop → 該閘標 skipped。"""
    home = make_project()
    docs = _render_and_draft(home, monkeypatch, write_leaf, "內文。")
    assert publish_cmd.run(["g"]) == 0                 # 真發行 v1.0.0
    capsys.readouterr()
    assert publish_cmd.run(["g", "--dry-run"]) == 1
    out = capsys.readouterr().out
    assert "✗ no-op: content is byte-identical to v1.0.0" in out
    assert publish_cmd.run(["g", "--dry-run", "--allow-noop"]) == 0
    out = capsys.readouterr().out
    assert "no-op: skipped (--allow-noop)" in out
    assert "dry-run verdict: GO" in out
    # dry-run 全程不動檔：仍只有 v1.0.0
    assert (docs / "archive" / "v1.0.0.md").is_file()
    assert not (docs / "archive" / "v1.0.1.md").exists()
