"""Owner-approved roadmap rules: basis is not a delivery, and queries explain gaps."""

import json
import subprocess

import pytest

from test_software_archive import proj, _change, code
from dspx.commands.governance import decision, info, question, roadmap, ruling
from dspx.engine import governance as gv


def _bytes(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file()}


def _work(layout, refs="", *, parent=None):
    args = ["add", "--title", "Synthetic delivery"]
    if refs:
        args += ["--ref", refs]
    if parent:
        args += ["--parent", parent]
    assert roadmap.run(args) == 0
    return gv.load_governance(layout).work[-1]["id"]


def _basis(kind):
    if kind == "info":
        assert info.run(["add", "--about", "Environment", "--quote", "Synthetic offline Windows terminal"]) == 0
        return "gov:I-claude-1"
    assert ruling.run(["add", "--quote", "Use this synthetic delivery"]) == 0
    assert decision.run(["add", "--title", "Delivery direction", "--statement", "Keep the original delivery contract",
                         "--based-on", "RL-claude-1"]) == 0
    assert decision.run(["activate", "D-claude-1"]) == 0
    return "gov:D-claude-1"


def _row(capsys, wid):
    capsys.readouterr()
    assert roadmap.run(["--json"]) == 0
    view = json.loads(capsys.readouterr().out)
    rows = view["unassigned"] + [r for m in view["milestones"] for r in m["items"]]
    rows += [r for children in view["children"].values() for r in children]
    return next(r for r in rows if r["id"] == wid)


@pytest.mark.parametrize("kind", ["info", "decision"])
def test_background_only_is_not_automatically_a_completed_delivery(proj, capsys, kind):
    ref = _basis(kind)
    wid = _work(proj, ref)
    row = _row(capsys, wid)
    assert row["status"] == "not-started"
    assert row["refs"] == [ref]
    assert row["details"], "A background-only work item must explain how completion can be established"
    assert any("artispec roadmap done" in d for d in row["details"])


@pytest.mark.parametrize("kind", ["info", "decision"])
def test_background_only_can_be_closed_with_an_explicit_reason(proj, capsys, kind):
    ref = _basis(kind)
    wid = _work(proj, ref)
    assert roadmap.run(["done", wid, "--note", "The synthetic planning task was completed"]) == 0
    row = _row(capsys, wid)
    assert row["status"] == "done"
    assert row["refs"] == [ref]


@pytest.mark.parametrize("kind", ["info", "decision"])
def test_archived_delivery_with_background_reference_is_completed(proj, capsys, kind):
    _change("delivered")
    assert code("archive", "delivered") == 0
    ref = _basis(kind)
    wid = _work(proj, f"swc:delivered,{ref}")
    row = _row(capsys, wid)
    assert row["status"] == "done"
    assert row["refs"] == ["swc:delivered", ref]


@pytest.mark.parametrize("kind", ["info", "decision"])
def test_missing_required_evidence_still_prevents_completion_with_background(proj, capsys, kind):
    _change("unfinished", run=False)
    ref = _basis(kind)
    wid = _work(proj, f"swc:unfinished,{ref}")
    row = _row(capsys, wid)
    assert row["status"] not in ("done", "done-waived")
    assert any("swc:unfinished" in d for d in row["details"])
    assert any("1" in d for d in row["details"])


def test_parent_uses_child_delivery_with_information_as_background(proj, capsys):
    ref = _basis("info")
    parent = _work(proj, ref)
    child = _work(proj, parent=parent)
    assert roadmap.run(["done", child, "--note", "The synthetic child task is complete"]) == 0
    assert _row(capsys, parent)["status"] == "done"


@pytest.mark.parametrize("kind", ["info", "decision"])
def test_missing_background_cannot_support_a_manually_closed_item(proj, capsys, kind):
    ref = _basis(kind)
    wid = _work(proj, ref)
    # A valid closed historical record can lose a source afterwards.
    rec = gv.load_record(gv.record_path(proj, "work", wid), "work")
    rec["closed"] = {"date": gv.today(), "note": "Originally completed synthetic work"}
    gv.write_record(proj, "work", rec)
    gv.record_path(proj, kind, gv.strip_ns(ref)).unlink()
    before = _bytes(proj.project_root)
    row = _row(capsys, wid)
    assert row["status"] not in ("done", "done-waived")
    assert any(ref in d for d in row["details"])
    assert _bytes(proj.project_root) == before


@pytest.mark.parametrize("kind", ["info", "decision"])
def test_missing_background_does_not_suggest_bypassing_it_with_manual_completion(proj, capsys, kind):
    ref = _basis(kind)
    wid = _work(proj, ref)
    gv.record_path(proj, kind, gv.strip_ns(ref)).unlink()
    before = _bytes(proj.project_root)
    row = _row(capsys, wid)
    assert row["status"] == "blocked"
    assert any(ref in d for d in row["details"])
    assert not any("artispec roadmap done" in d for d in row["details"])
    assert _bytes(proj.project_root) == before


@pytest.mark.parametrize("kind", ["info", "decision"])
def test_corrupt_background_is_reported_without_repairing_records(proj, capsys, kind):
    ref = _basis(kind)
    wid = _work(proj, ref)
    path = gv.record_path(proj, kind, gv.strip_ns(ref))
    path.write_text(path.read_text(encoding="utf-8").replace("Synthetic", "Altered").replace("original delivery", "altered delivery"),
                    encoding="utf-8")
    before = _bytes(proj.project_root)
    capsys.readouterr()
    assert roadmap.run(["show", wid, "--json"]) != 0
    captured = capsys.readouterr()
    assert captured.out or captured.err
    assert _bytes(proj.project_root) == before


def test_questions_and_rulings_remain_real_completion_conditions(proj, capsys):
    assert question.run(["add", "--title", "Choose the synthetic operating mode"]) == 0
    wid = _work(proj, "gov:Q-claude-1")
    pending = _row(capsys, wid)
    assert pending["status"] == "not-started"
    assert any("Q-claude-1" in d for d in pending["details"])
    assert ruling.run(["add", "--quote", "Choose offline mode", "--answers", "Q-claude-1"]) == 0
    assert _row(capsys, wid)["status"] == "done"
    ruled = _work(proj, "gov:RL-claude-1")
    assert _row(capsys, ruled)["status"] == "done"
    assert ruling.run(["reject", "RL-claude-1", "--reason", "The synthetic mode was recorded incorrectly"]) == 0
    row = _row(capsys, ruled)
    assert row["status"] not in ("done", "done-waived")
    assert any("RL-claude-1" in d for d in row["details"])


@pytest.mark.parametrize("change", ["supersede", "withdraw"])
def test_information_change_keeps_completed_delivery_and_original_reference(proj, capsys, change):
    _change("delivered")
    assert code("archive", "delivered") == 0
    ref = _basis("info")
    wid = _work(proj, f"swc:delivered,{ref}")
    if change == "supersede":
        assert info.run(["add", "--about", "Environment", "--quote", "Synthetic Linux terminal",
                         "--supersedes", "I-claude-1"]) == 0
    else:
        assert info.run(["withdraw", "I-claude-1", "--reason", "The environment description no longer applies"]) == 0
    row = _row(capsys, wid)
    assert row["status"] == "done"
    assert row["refs"] == ["swc:delivered", ref]
    details = "\n".join(row["details"])
    assert "I-claude-1" in details
    if change == "supersede":
        assert "I-claude-2" in details
    else:
        assert "withdraw" in details.lower() or "撤回" in details


def test_finished_work_keeps_done_when_its_decision_is_superseded(proj, capsys):
    ref = _basis("decision")
    wid = _work(proj, ref)
    assert roadmap.run(["done", wid, "--note", "Synthetic planning complete"]) == 0
    assert ruling.run(["add", "--quote", "Revise the synthetic direction"]) == 0
    assert decision.run(["add", "--title", "Replacement", "--statement", "Use the replacement delivery contract",
                         "--supersedes", "D-claude-1", "--based-on", "RL-claude-2"]) == 0
    assert decision.run(["activate", "D-claude-2"]) == 0
    row = _row(capsys, wid)
    assert row["status"] == "done"
    assert row["refs"] == [ref]
    assert any("D-claude-2" in d for d in row["details"])
    assert any("重看" in d or "review" in d.lower() for d in row["details"])


def test_unfinished_reasons_are_shared_by_text_and_json_and_queries_do_not_write(proj, monkeypatch, capsys):
    _basis("info")
    wid = _work(proj, "gov:I-claude-1")
    row = _row(capsys, wid)
    before = _bytes(proj.project_root)
    def forbidden(*args, **kwargs):
        raise AssertionError("A roadmap query must not run an external command")
    monkeypatch.setattr(subprocess, "run", forbidden)
    capsys.readouterr()
    assert roadmap.run([]) == 0
    text = capsys.readouterr().out
    assert row["details"]
    assert all(d in text for d in row["details"])
    assert _bytes(proj.project_root) == before


def _assert_list_and_show_do_not_complete(capsys, wid, expected_ids):
    row = _row(capsys, wid)
    assert row["status"] not in ("done", "done-waived")
    assert all(identifier in "\n".join(row["details"]) for identifier in expected_ids)
    capsys.readouterr()
    assert roadmap.run(["show", wid, "--json"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["work"]["status"] not in ("done", "done-waived")
    diagnostics = json.dumps(summary["diagnostics"], ensure_ascii=False)
    assert all(identifier in diagnostics for identifier in expected_ids)


@pytest.mark.parametrize("kind", ["info", "decision"])
@pytest.mark.parametrize("completion", ["archived", "closed"])
def test_linked_governance_supersession_cycles_cannot_support_completion(proj, capsys, kind, completion):
    ref = _basis(kind)
    if kind == "info":
        assert info.run(["add", "--about", "Environment", "--quote", "Synthetic replacement environment",
                         "--supersedes", "I-claude-1"]) == 0
        replacement = "I-claude-2"
    else:
        assert decision.run(["add", "--title", "Replacement", "--statement", "Synthetic replacement constraint",
                             "--based-on", "RL-claude-1", "--supersedes", "D-claude-1"]) == 0
        assert decision.run(["activate", "D-claude-2"]) == 0
        replacement = "D-claude-2"
    if completion == "archived":
        _change("delivered")
        assert code("archive", "delivered") == 0
        wid = _work(proj, f"swc:delivered,{ref}")
    else:
        wid = _work(proj, ref)
        assert roadmap.run(["done", wid, "--note", "Originally completed synthetic work"]) == 0
    path = gv.record_path(proj, kind, gv.strip_ns(ref))
    original = gv.load_record(path, kind)
    original["supersedes"] = [replacement]
    gv.write_record(proj, kind, original)
    before = _bytes(proj.project_root)
    _assert_list_and_show_do_not_complete(capsys, wid, [gv.strip_ns(ref), replacement])
    assert _bytes(proj.project_root) == before


@pytest.mark.parametrize("kind", ["info", "decision"])
def test_missing_transitive_governance_basis_prevents_false_completed_work(proj, capsys, kind):
    original = _basis(kind)
    if kind == "info":
        assert info.run(["add", "--about", "Environment", "--quote", "Synthetic replacement environment",
                         "--supersedes", "I-claude-1"]) == 0
        ref, missing_kind, missing_id = "gov:I-claude-2", "info", "I-claude-1"
    else:
        ref, missing_kind, missing_id = original, "ruling", "RL-claude-1"
    wid = _work(proj, ref)
    assert roadmap.run(["done", wid, "--note", "Originally completed synthetic planning"]) == 0
    gv.record_path(proj, missing_kind, missing_id).unlink()
    before = _bytes(proj.project_root)
    _assert_list_and_show_do_not_complete(capsys, wid, [missing_id])
    assert _bytes(proj.project_root) == before


@pytest.mark.parametrize("kind", ["info", "decision"])
def test_normal_multistep_governance_supersession_is_not_a_cycle(proj, capsys, kind):
    ref = _basis(kind)
    for n in (2, 3):
        if kind == "info":
            assert info.run(["add", "--about", "Environment", "--quote", f"Synthetic environment version {n}",
                             "--supersedes", f"I-claude-{n - 1}"]) == 0
        else:
            assert decision.run(["add", "--title", f"Direction {n}", "--statement", f"Synthetic constraint version {n}",
                                 "--based-on", "RL-claude-1", "--supersedes", f"D-claude-{n - 1}"]) == 0
            assert decision.run(["activate", f"D-claude-{n}"]) == 0
    wid = _work(proj, ref)
    assert roadmap.run(["done", wid, "--note", "The synthetic planning task is complete"]) == 0
    assert _row(capsys, wid)["status"] == "done"
    assert roadmap.run(["show", wid, "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["work"]["status"] == "done"
    assert not any("cycle" in diagnostic["code"] for diagnostic in result["diagnostics"])


def test_unrelated_missing_governance_basis_does_not_block_selected_work(proj, capsys):
    _basis("decision")
    assert info.run(["add", "--about", "Selected environment", "--quote", "Valid synthetic environment"]) == 0
    wid = _work(proj, "gov:I-claude-1")
    assert roadmap.run(["done", wid, "--note", "The synthetic planning task is complete"]) == 0
    gv.record_path(proj, "ruling", "RL-claude-1").unlink()
    assert _row(capsys, wid)["status"] == "done"
    assert roadmap.run(["show", wid, "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["work"]["status"] == "done"
    assert not any("RL-claude-1" in str(row) for row in result["diagnostics"])
