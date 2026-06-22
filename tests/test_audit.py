"""audit 子系統（redesign：per-doc-root + forest）：raise/resolve/show/list、寫時與 check 驗證。"""

from __future__ import annotations

import yaml

from dspx.audit import load_doc_audit, load_forest_audit
from dspx.check import run_check
from dspx.commands import audit as audit_cmd
from dspx.layout import Layout
from dspx.model import load_project
from dspx.schema import load_schema


def _doc_audit(home, article):
    """per-doc audit 路徑＝corpus/<article>/audit.yaml。"""
    return home / "corpus" / article / "audit.yaml"


def _forest_audit(home):
    return home / "audit.yaml"


def _check(home):
    layout = Layout(home)
    return run_check(load_project(layout), load_schema(), layout=layout)


def _root(cid, title, order=1):
    """root concept 含完整 brief（過 _check_hierarchy root-brief 不變式）。"""
    return {"id": cid, "title": title, "order": order,
            "brief": {"audience": "a", "depth": "d", "breadth": "b"}}


# ── raise：路由到 doc-root vs forest ─────────────────────────────────

def test_raise_rejects_nonexistent_target(make_project, write_leaf, monkeypatch):
    """raise 打到不存在的 target（如漏 zenoh/ 前綴）→ 報錯、不建孤兒 audit.yaml。"""
    home = make_project()
    write_leaf(home, "zenoh/query", concept={"id": "c1", "title": "Q", "order": 1})
    monkeypatch.chdir(home.parent)
    # 漏前綴：'query' 不是真 section → 報錯
    assert audit_cmd.run(["raise", "--target", "query", "--face", "logic",
                          "--sev", "low", "--finding", "x"]) == 1
    assert not _doc_audit(home, "query").exists()
    assert not _doc_audit(home, "zenoh").exists()
    # 完整路徑（單文件）→ 進該 doc-root（root section 名＝article＝zenoh）
    assert audit_cmd.run(["raise", "--target", "zenoh/query", "--face", "logic",
                          "--sev", "low", "--finding", "x"]) == 0
    assert _doc_audit(home, "zenoh").is_file()


def test_single_doc_finding_lands_in_doc_root(make_project, write_leaf, monkeypatch):
    home = make_project()
    write_leaf(home, "a", concept={"id": "ca", "title": "A", "order": 1})
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    monkeypatch.chdir(home.parent)
    assert audit_cmd.run(["raise", "--target", "a/x", "--face", "logic",
                          "--sev", "high", "--finding", "推理跳步",
                          "--suggest", "補步驟"]) == 0
    doc = load_doc_audit(home / "corpus" / "a", "a")
    assert len(doc.findings) == 1
    f = doc.findings[0]
    assert f["id"] == "F1" and f["status"] == "open" and f["targets"] == ["a/x"]
    assert f["log"][0]["action"] == "raised"
    # forest 檔不存在
    assert load_forest_audit(Layout(home)).findings == []


def test_cross_doc_finding_lands_in_forest(make_project, write_leaf, monkeypatch):
    """targets 觸及 2 文件 → forest docspec/audit.yaml；可帶 sot-owner。"""
    home = make_project()
    write_leaf(home, "a", concept={"id": "ca", "title": "A", "order": 1})
    write_leaf(home, "b", concept={"id": "cb", "title": "B", "order": 2})
    monkeypatch.chdir(home.parent)
    assert audit_cmd.run(["raise", "--target", "a", "--target", "b",
                          "--face", "consistency", "--sev", "high",
                          "--finding", "兩文件對狀態機說法不一致",
                          "--sot-owner", "a"]) == 0
    forest = load_forest_audit(Layout(home))
    assert len(forest.findings) == 1
    f = forest.findings[0]
    assert f["targets"] == ["a", "b"] and f["sot-owner"] == "a"
    assert _forest_audit(home).is_file()
    # doc-root 檔不存在
    assert not _doc_audit(home, "a").exists()


def test_target_comma_list(make_project, write_leaf, monkeypatch):
    """--target 支援逗號分隔。"""
    home = make_project()
    write_leaf(home, "a", concept={"id": "ca", "title": "A", "order": 1})
    write_leaf(home, "b", concept={"id": "cb", "title": "B", "order": 2})
    monkeypatch.chdir(home.parent)
    assert audit_cmd.run(["raise", "--target", "a,b", "--face", "consistency",
                          "--sev", "med", "--finding", "x"]) == 0
    assert len(load_forest_audit(Layout(home)).findings) == 1


# ── D3：可選 NLI verdict（contradicted / unsupported）─────────────────

def test_raise_with_verdict_stores_and_shows(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    monkeypatch.chdir(home.parent)
    assert audit_cmd.run(["raise", "--target", "a/x", "--face", "consistency",
                          "--sev", "high", "--finding", "來源反對此說",
                          "--verdict", "contradicted"]) == 0
    f = load_doc_audit(home / "corpus" / "a", "a").findings[0]
    assert f["verdict"] == "contradicted"
    capsys.readouterr()  # 清掉 raise 的輸出
    assert audit_cmd.run(["show", "F1"]) == 0
    assert "verdict: contradicted" in capsys.readouterr().out


def test_raise_bad_verdict_rejected_by_argparse(make_project, write_leaf, monkeypatch):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    monkeypatch.chdir(home.parent)
    import pytest
    with pytest.raises(SystemExit):   # argparse choices 擋下非法 verdict
        audit_cmd.run(["raise", "--target", "a/x", "--face", "logic", "--sev", "low",
                       "--finding", "x", "--verdict", "bogus"])


def test_library_validate_rejects_unknown_verdict():
    from dspx.audit import DEFAULT_FACES, validate_finding
    f = {"id": "F1", "face": "logic", "severity": "low", "status": "open",
         "finding": "x", "targets": ["a"], "verdict": "bogus"}
    errs = validate_finding(f, DEFAULT_FACES)
    assert any("verdict" in e for e in errs)


def test_finding_without_verdict_is_valid(make_project, write_leaf, monkeypatch):
    """舊 finding（無 verdict）仍合法、check 綠。"""
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    monkeypatch.chdir(home.parent)
    assert audit_cmd.run(["raise", "--target", "a/x", "--face", "logic",
                          "--sev", "low", "--finding", "x"]) == 0
    f = load_doc_audit(home / "corpus" / "a", "a").findings[0]
    assert "verdict" not in f
    assert _check(home).ok


# ── resolve / show across stores ───────────────────────────────────

def test_raise_then_resolve_appends_log(make_project, write_leaf, monkeypatch):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    monkeypatch.chdir(home.parent)
    assert audit_cmd.run(["raise", "--target", "a/x", "--face", "logic",
                          "--sev", "high", "--finding", "推理跳步"]) == 0
    # resolve 不需指定 store；引擎用 id 反查
    assert audit_cmd.run(["resolve", "F1", "--status", "fixed",
                          "--actor", "author", "--note", "已補步驟"]) == 0
    doc = load_doc_audit(home / "corpus" / "a", "a")
    f = doc.findings[0]
    assert f["status"] == "fixed"
    assert len(f["log"]) == 2 and f["log"][1]["status"] == "fixed"
    assert f["log"][1]["note"] == "已補步驟"


def test_resolve_cross_doc_finding_in_forest(make_project, write_leaf, monkeypatch):
    home = make_project()
    write_leaf(home, "a", concept={"id": "ca", "title": "A", "order": 1})
    write_leaf(home, "b", concept={"id": "cb", "title": "B", "order": 2})
    monkeypatch.chdir(home.parent)
    audit_cmd.run(["raise", "--target", "a,b", "--face", "consistency",
                   "--sev", "high", "--finding", "x"])
    assert audit_cmd.run(["resolve", "F1", "--status", "rejected"]) == 0
    assert load_forest_audit(Layout(home)).findings[0]["status"] == "rejected"
    assert audit_cmd.run(["show", "F1"]) == 0


def test_raise_rejects_bad_face(make_project, write_leaf, monkeypatch):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    monkeypatch.chdir(home.parent)
    assert audit_cmd.run(["raise", "--target", "a/x", "--face", "bogus",
                          "--sev", "high", "--finding", "x"]) == 1
    assert not _doc_audit(home, "a").exists()


def test_resolve_unknown_id_fails(make_project, write_leaf, monkeypatch):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    monkeypatch.chdir(home.parent)
    assert audit_cmd.run(["resolve", "F9", "--status", "fixed"]) == 1


def test_global_unique_id_across_stores(make_project, write_leaf, monkeypatch):
    """doc-root 與 forest 共用全域 id 序列。"""
    home = make_project()
    write_leaf(home, "a", concept={"id": "ca", "title": "A", "order": 1})
    write_leaf(home, "b", concept={"id": "cb", "title": "B", "order": 2})
    monkeypatch.chdir(home.parent)
    audit_cmd.run(["raise", "--target", "a", "--face", "logic", "--sev", "low",
                   "--finding", "p1"])                       # F1 → doc:a
    audit_cmd.run(["raise", "--target", "a,b", "--face", "consistency",
                   "--sev", "low", "--finding", "p2"])       # F2 → forest
    audit_cmd.run(["raise", "--target", "b", "--face", "clarity", "--sev", "low",
                   "--finding", "p3"])                       # F3 → doc:b
    assert load_doc_audit(home / "corpus" / "a", "a").findings[0]["id"] == "F1"
    assert load_forest_audit(Layout(home)).findings[0]["id"] == "F2"
    assert load_doc_audit(home / "corpus" / "b", "b").findings[0]["id"] == "F3"


def test_aggregate_list(make_project, write_leaf, monkeypatch):
    home = make_project()
    write_leaf(home, "a", concept={"id": "ca", "title": "A", "order": 1})
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    write_leaf(home, "b", concept={"id": "cb", "title": "B", "order": 2})
    monkeypatch.chdir(home.parent)
    audit_cmd.run(["raise", "--target", "a/x", "--face", "logic", "--sev", "high",
                   "--finding", "p1"])
    audit_cmd.run(["raise", "--target", "a,b", "--face", "consistency", "--sev",
                   "low", "--finding", "p2"])
    assert audit_cmd.run([]) == 0
    assert audit_cmd.run(["--open"]) == 0
    assert audit_cmd.run(["--article", "a"]) == 0


# ── check：放置 / face / target 死引用 ──────────────────────────────

def test_check_catches_corrupt_audit_status(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "a", concept={"id": "ca", "title": "A", "order": 1})
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    _doc_audit(home, "a").write_text(
        yaml.safe_dump({"findings": [{"id": "F1", "face": "logic", "severity": "high",
                                      "status": "bogus", "finding": "x",
                                      "targets": ["a/x"]}]}, allow_unicode=True),
        encoding="utf-8")
    res = _check(home)
    assert not res.ok
    assert any("status" in e and "bogus" in e for e in res.errors)


def test_check_catches_bad_face(make_project, write_leaf):
    """補漏：手改 face 非法 → check 抓（舊 check 漏驗 face）。"""
    home = make_project()
    write_leaf(home, "a", concept={"id": "ca", "title": "A", "order": 1})
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    _doc_audit(home, "a").write_text(
        yaml.safe_dump({"findings": [{"id": "F1", "face": "bogus", "severity": "high",
                                      "status": "open", "finding": "x",
                                      "targets": ["a/x"]}]}, allow_unicode=True),
        encoding="utf-8")
    res = _check(home)
    assert not res.ok
    assert any("face" in e and "bogus" in e for e in res.errors)


def test_check_catches_target_dead_ref(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "a", concept={"id": "ca", "title": "A", "order": 1})
    _doc_audit(home, "a").write_text(
        yaml.safe_dump({"findings": [{"id": "F1", "face": "logic", "severity": "high",
                                      "status": "open", "finding": "x",
                                      "targets": ["no-such-section"]}]},
                       allow_unicode=True), encoding="utf-8")
    res = _check(home)
    assert not res.ok
    assert any("target" in e and "no-such-section" in e for e in res.errors)


def test_check_catches_cross_doc_in_doc_file(make_project, write_leaf):
    """跨文件 finding 被手放進 doc-root 檔 → 放置錯。"""
    home = make_project()
    write_leaf(home, "a", concept={"id": "ca", "title": "A", "order": 1})
    write_leaf(home, "b", concept={"id": "cb", "title": "B", "order": 2})
    _doc_audit(home, "a").write_text(
        yaml.safe_dump({"findings": [{"id": "F1", "face": "consistency",
                                      "severity": "high", "status": "open",
                                      "finding": "x", "targets": ["a", "b"]}]},
                       allow_unicode=True), encoding="utf-8")
    res = _check(home)
    assert not res.ok
    assert any("forest" in e and "F1" in e for e in res.errors)


def test_check_catches_single_doc_in_forest(make_project, write_leaf):
    """單文件 finding 被手放進 forest 檔 → 放置錯。"""
    home = make_project()
    write_leaf(home, "a", concept={"id": "ca", "title": "A", "order": 1})
    _forest_audit(home).write_text(
        yaml.safe_dump({"findings": [{"id": "F1", "face": "logic", "severity": "high",
                                      "status": "open", "finding": "x",
                                      "targets": ["a"]}]}, allow_unicode=True),
        encoding="utf-8")
    res = _check(home)
    assert not res.ok
    assert any("doc:a" in e and "F1" in e for e in res.errors)


def test_check_valid_audit_passes(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "a", concept=_root("ca", "A", 1))
    write_leaf(home, "b", concept=_root("cb", "B", 2))
    _doc_audit(home, "a").write_text(
        yaml.safe_dump({"findings": [{"id": "F1", "face": "logic", "severity": "high",
                                      "status": "open", "finding": "x",
                                      "targets": ["a"]}]}, allow_unicode=True),
        encoding="utf-8")
    _forest_audit(home).write_text(
        yaml.safe_dump({"findings": [{"id": "F2", "face": "consistency",
                                      "severity": "med", "status": "open",
                                      "finding": "y", "targets": ["a", "b"]}]},
                       allow_unicode=True), encoding="utf-8")
    res = _check(home)
    assert res.ok, res.errors


def test_check_catches_missing_required_concept_field(make_project):
    """欄位級驗證：concept 缺必填（如 concept 一句話）→ check 抓。"""
    home = make_project()
    leaf = home / "corpus" / "a" / "x"
    leaf.mkdir(parents=True)
    leaf.joinpath("concept.yaml").write_text(
        yaml.safe_dump({"id": "c1", "title": "X", "order": 1}, allow_unicode=True),
        encoding="utf-8")
    layout = Layout(home)
    res = run_check(load_project(layout), load_schema(), layout=layout)
    assert not res.ok
    assert any("required" in e for e in res.errors)
