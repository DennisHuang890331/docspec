"""Compact work summaries keep judgments and historical scope identities intact."""

import json
import shlex
import subprocess

import pytest

from test_software_archive import proj, _change, code
from dspx.commands.change import change
from dspx.commands.governance import decision, info, roadmap, ruling
from dspx.engine import governance as gv, handover
from dspx.engine import work_summary as ws
from dspx.engine.model import load_project
from dspx.engine.software import changes as chg, evidence, specs


def _bytes(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file()}


def _work(layout, refs):
    assert ruling.run(["add", "--quote", "Track this synthetic work"]) == 0
    assert roadmap.run(["add", "--title", "Synthetic work summary", "--ref", refs]) == 0
    return gv.load_governance(layout).work[-1]["id"]


def _basis(layout, statement="Preserve every necessary delivery constraint"):
    assert ruling.run(["add", "--quote", "Use this synthetic constraint"]) == 0
    assert decision.run(["add", "--title", "Constraint", "--statement", statement, "--based-on", "RL-claude-1"]) == 0
    assert decision.run(["activate", "D-claude-1"]) == 0
    spec = specs.load_spec(layout, "entry")
    spec["requirements"][0]["based-on"] = ["D-claude-1"]
    specs.write_spec(layout, spec)


def _cli(capsys, wid, *, version=None):
    args = ["show", wid, "--json"]
    if version is not None:
        args += ["--schema-version", str(version)]
    capsys.readouterr()
    assert roadmap.run(args) == 0
    return json.loads(capsys.readouterr().out)


def _signoffs(result):
    return [(software, row) for software in result["software"] for row in software["signoffs"]]


def test_default_v2_and_explicit_v1_share_the_same_judgments_and_remain_read_only(proj, monkeypatch, capsys):
    _basis(proj)
    _change("update", run=False)
    wid = _work(proj, "swc:update,gov:D-claude-1")
    before = _bytes(proj.project_root)
    def forbidden(*args, **kwargs):
        raise AssertionError("A work summary must not execute, refresh, sign or write a handover")
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(evidence, "run_tests", forbidden)
    monkeypatch.setattr(evidence, "refresh", forbidden)
    monkeypatch.setattr(handover, "write", forbidden)
    v2 = _cli(capsys, wid)
    assert v2["schema-version"] == 2
    assert ws.build(proj, load_project(proj), wid) == v2
    v1 = _cli(capsys, wid, version=1)
    assert v1["schema-version"] == 1
    assert ws.build(proj, load_project(proj), wid, schema_version=1) == v1
    for field in ("work", "dependencies", "governance", "documents", "actions", "diagnostics"):
        assert v2[field] == v1[field]
    for field in ("id", "status", "historical", "tasks", "evidence", "details", "gaps", "warnings", "source", "command"):
        assert v2["software"][0][field] == v1["software"][0][field]
    assert _bytes(proj.project_root) == before


def test_v2_compacts_signed_scope_but_keeps_all_signer_metadata_and_original_source(proj, capsys):
    _basis(proj)
    _change("update", run=False)
    wid = _work(proj, "swc:update")
    original = chg.load_change(proj, "update")["tests"]["tests"][0]["signed"]
    assert original["scenario-fingerprint"]["contract"]
    result = _cli(capsys, wid)
    software, row = _signoffs(result)[0]
    scope = original["scenario-fingerprint"]
    assert row["signed"] == {**original, "scenario-fingerprint": {"version": scope["version"], "fingerprint": scope["fingerprint"]}}
    source = row["scope-source"]
    assert source["ref"] == "test:update/T1"
    assert source["fingerprint"] == scope["fingerprint"]
    assert source["path"] == f"{software['source']}/tests.yaml"
    assert (proj.project_root / source["path"]).is_file()
    assert source["command"] == "artispec change show update --json"
    capsys.readouterr()
    command = shlex.split(source["command"])
    assert change.run(command[2:]) == 0
    original_readback = json.loads(capsys.readouterr().out)
    assert scope["fingerprint"] in json.dumps(original_readback)
    assert "contract" in json.dumps(original_readback)
    assert chg.load_change(proj, "update")["tests"]["tests"][0]["signed"] == original


def test_identical_signed_scope_is_deduplicated_with_every_source_retained(proj, capsys):
    _basis(proj)
    _change("first", run=False)
    _change("second", run=False)
    wid = _work(proj, "swc:first,swc:second")
    result = _cli(capsys, wid)
    rows = _signoffs(result)
    scopes = [row["signed"]["scenario-fingerprint"] for _, row in rows]
    assert scopes[0] == scopes[1]
    assert len(result["verification-scopes"]) == 1
    scope = result["verification-scopes"][0]
    assert (scope["version"], scope["fingerprint"]) == (scopes[0]["version"], scopes[0]["fingerprint"])
    assert {source["ref"] for source in scope["sources"]} == {"test:first/T1", "test:second/T1"}
    assert all("contract" not in row["signed"]["scenario-fingerprint"] for _, row in rows)


def test_same_requirement_id_at_different_versions_keeps_both_scope_fingerprints(proj, capsys):
    _basis(proj)
    _change("first", then="First synthetic behavior", run=False)
    _change("second", then="Second synthetic behavior", run=False)
    wid = _work(proj, "swc:first,swc:second")
    result = _cli(capsys, wid)
    original_scopes = {chg.load_change(proj, cid)["tests"]["tests"][0]["signed"]["scenario-fingerprint"]["fingerprint"]
                       for cid in ("first", "second")}
    assert len(original_scopes) == 2
    assert {scope["fingerprint"] for scope in result["verification-scopes"]} == original_scopes
    assert {source["ref"] for scope in result["verification-scopes"] for source in scope["sources"]} == {"test:first/T1", "test:second/T1"}


def test_compaction_keeps_effective_decision_in_full_once_and_v1_still_contains_contracts(proj, capsys):
    statement = ("EFFECTIVE_CONSTRAINT " + "Preserve this necessary constraint without truncation. " * 40).strip()
    _basis(proj, statement)
    for cid in ("first", "second", "third"):
        _change(cid)
        assert code("archive", cid) == 0
    wid = _work(proj, "swc:first,swc:second,swc:third")
    before = _bytes(proj.project_root)
    v1 = _cli(capsys, wid, version=1)
    v2 = _cli(capsys, wid)
    assert all("contract" in row["signed"]["scenario-fingerprint"] for _, row in _signoffs(v1))
    assert all("contract" not in row["signed"]["scenario-fingerprint"] for _, row in _signoffs(v2))
    records = [record for record in v2["governance"] if record["id"] == "D-claude-1"]
    assert len(records) == 1 and records[0]["statement"] == statement
    assert json.dumps(v2, ensure_ascii=False).count(statement) == 1
    assert len(json.dumps(v2, ensure_ascii=False).encode("utf-8")) < len(json.dumps(v1, ensure_ascii=False).encode("utf-8"))
    assert _bytes(proj.project_root) == before


def test_archived_signoff_source_and_scope_remain_historical_without_reading_deleted_tests(proj, capsys):
    _basis(proj)
    _change("delivered")
    assert code("archive", "delivered") == 0
    (proj.project_root / "app/tests/test_entry.py").unlink()
    wid = _work(proj, "swc:delivered")
    result = _cli(capsys, wid)
    assert result["work"]["status"] == "done"
    software, row = _signoffs(result)[0]
    assert software["historical"] is True and row["status"] == "historical"
    assert "_archive" in row["scope-source"]["path"]
    assert (proj.project_root / row["scope-source"]["path"]).is_file()
    assert row["signed"]["scenario-fingerprint"]["fingerprint"]
    assert not any(action["code"] == "review-signoff" for action in result["actions"])


@pytest.mark.parametrize("condition", ["unsigned", "legacy", "needs-review"])
def test_problem_signoffs_keep_their_actual_reasons_after_compaction(proj, capsys, condition):
    _change("update", run=False)
    if condition == "needs-review":
        test = proj.project_root / "app/tests/test_entry.py"
        test.write_text(test.read_text(encoding="utf-8").replace("assert True", "assert False", 1), encoding="utf-8")
    else:
        data = chg.load_change(proj, "update")["tests"]
        if condition == "unsigned":
            data["tests"][0].pop("signed")
        else:
            data["tests"][0]["signed"].pop("scenario-fingerprint")
        chg.write_part(proj, "update", "tests", data)
    wid = _work(proj, "swc:update")
    v1 = _cli(capsys, wid, version=1)
    v2 = _cli(capsys, wid)
    before_row = v1["software"][0]["signoffs"][0]
    row = v2["software"][0]["signoffs"][0]
    assert row["status"] == before_row["status"] == ("unsigned" if condition == "unsigned" else "needs-review")
    assert row["problems"] == before_row["problems"] and row["problems"]
    assert v2["actions"] == v1["actions"]
    assert v2["work"]["status"] not in ("done", "done-waived")
    if condition in ("unsigned", "legacy"):
        assert not row.get("scope-source")
        assert v2["verification-scopes"] == []


def test_latest_failed_verification_and_task_recovery_reason_are_not_suppressed(proj, capsys):
    _change("update")
    test = proj.project_root / "app/tests/test_entry.py"
    test.write_text(test.read_text(encoding="utf-8").replace("assert True", "assert False", 1), encoding="utf-8")
    assert code("testplan", "sign", "update", "--by", "gemini") == 0
    assert code("evidence", "run", "update", "1") == 1
    latest = evidence.load_all(proj)[-1]
    wid = _work(proj, "swc:update")
    v1 = _cli(capsys, wid, version=1)
    v2 = _cli(capsys, wid)
    assert v2["software"][0]["tasks"] == v1["software"][0]["tasks"]
    assert v2["actions"] == v1["actions"]
    assert any(record["id"] == latest["id"] and record["result"] == "fail" for record in v2["software"][0]["evidence"])
    assert any(latest["id"] in action["ids"] for action in v2["actions"] if action["code"] == "failed-verification")
    assert v2["work"]["status"] not in ("done", "done-waived")


def test_text_and_default_json_are_the_same_v2_result_with_all_problem_reasons(proj, capsys):
    _change("update", run=False)
    assert info.run(["add", "--about", "Synthetic environment", "--quote", "The terminal is offline"]) == 0
    wid = _work(proj, "swc:update,gov:I-claude-1")
    before = _bytes(proj.project_root)
    result = _cli(capsys, wid)
    assert result["schema-version"] == 2
    assert roadmap.run(["show", wid]) == 0
    text = capsys.readouterr().out
    assert text.strip() == ws.render(result).strip()
    for row in result["actions"] + result["diagnostics"]:
        assert row["reason"] in text
    assert "The terminal is offline" in text
    assert _bytes(proj.project_root) == before


@pytest.mark.parametrize("version", [0, 3])
def test_unknown_summary_version_is_rejected_without_writing(proj, capsys, version):
    wid = _work(proj, "")
    capsys.readouterr()
    before = _bytes(proj.project_root)
    try:
        result = roadmap.run(["show", wid, "--json", "--schema-version", str(version)])
    except SystemExit as exc:
        result = exc.code
    assert result != 0
    assert capsys.readouterr().err
    assert _bytes(proj.project_root) == before


@pytest.mark.parametrize("field,value", [("version", {"invalid": 1}),
                                        ("fingerprint", {"invalid": "digest"}),
                                        ("fingerprint", ["invalid-digest"])])
def test_malformed_saved_scope_identity_is_diagnosed_without_crashing_or_fabricating_a_scope_source(proj, monkeypatch, capsys, field, value):
    _change("update", run=False)
    data = chg.load_change(proj, "update")["tests"]
    data["tests"][0]["signed"]["scenario-fingerprint"][field] = value
    chg.write_part(proj, "update", "tests", data)
    # The existing loader verifies the seal and accepts these nested values.
    # This proves the compact projection can actually encounter the malformed
    # identity, rather than testing an unreachable object injected into a helper.
    assert chg.load_change(proj, "update")["tests"]["tests"][0]["signed"]["scenario-fingerprint"][field] == value
    wid = _work(proj, "swc:update")
    before = _bytes(proj.project_root)
    def forbidden(*args, **kwargs):
        raise AssertionError("Reading an invalid signoff must not execute, refresh or repair records")
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(evidence, "refresh", forbidden)
    monkeypatch.setattr(handover, "write", forbidden)
    capsys.readouterr()
    assert code("testplan", "list", "update", "--json") == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed["signoffs"][0]["status"] == "needs-review"
    assert listed["signoffs"][0]["problems"]
    v1 = _cli(capsys, wid, version=1)
    assert v1["software"][0]["signoffs"] == listed["signoffs"]
    assert v1["work"]["status"] not in ("done", "done-waived")
    capsys.readouterr()
    result = roadmap.run(["show", wid, "--json", "--schema-version", "2"])
    captured = capsys.readouterr()
    if result == 0:
        v2 = json.loads(captured.out)
        row = v2["software"][0]["signoffs"][0]
        assert row["status"] == "needs-review"
        assert row["problems"] == listed["signoffs"][0]["problems"]
        assert not row.get("scope-source")
        assert v2["verification-scopes"] == []
        assert v2["actions"] == v1["actions"]
        assert v2["work"]["status"] not in ("done", "done-waived")
    else:
        assert result in (1, 2)
        error = (captured.out + captured.err).lower()
        assert "t1" in error
        assert any(word in error for word in ("scope", "fingerprint", "sign-off", "簽收", "指紋"))
    assert _bytes(proj.project_root) == before
