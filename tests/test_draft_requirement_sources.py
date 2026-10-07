"""F2 acceptance: real sealed draft sources, landing proof, and domain independence.

The test role owns this file. Fixtures use the existing software engines to create
and archive synthetic records; no source resolver or archive outcome is mocked.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess

import pytest

from dspx.check import run_check
from dspx.commands.deliverable import freeze as freeze_cmd
from dspx.commands.deliverable import render as render_cmd
from dspx.commands.governance import decision as decision_cmd
from dspx.commands.governance import roadmap as roadmap_cmd
from dspx.commands.governance import ruling as ruling_cmd
from dspx.commands.governance import trace as trace_cmd
from dspx.commands.projection import instructions as instructions_cmd
from dspx.commands.query.status import _docs_hashes, _leaf_row
from dspx.engine import project_baseline
from dspx.engine.layout import Layout
from dspx.engine.model import (
    deps_doc_fingerprint,
    deps_fingerprint,
    load_project,
    project_decision_index,
    realized_statements,
)
from dspx.engine.schema import load_schema
from dspx.engine.software import archive, changes, evidence, io, links, specs, tasks


def _requirement(rid, statement="It SHALL export seats."):
    return {
        "id": rid, "title": "Seat export", "statement": statement,
        "verification": ["inspection"],
        "scenarios": [{"id": "S1", "title": "Export", "when": "seats exist",
                       "then": "an output is created"}],
    }


@pytest.fixture
def project(make_project, monkeypatch):
    home = make_project()
    monkeypatch.chdir(home.parent)
    monkeypatch.setenv("DOCSPEC_AGENT", "gpt")
    monkeypatch.setenv("DOCSPEC_ACTOR_ID", "f2-independent-test-fixture")
    layout = Layout(home)
    specs.write_spec(layout, {"capability": "seat", "purpose": "Synthetic seating",
                              "requirements": [_requirement("R1"), _requirement("R2")]})
    return layout


def _new(layout, cid="update", cap="seat", new=False):
    changes.new_change(layout, cid, why="Synthetic scope change", what=[],
                       new_caps=[cap] if new else [],
                       modified_caps=[] if new else [cap], code_areas=[],
                       depends_on=[], tool="gpt")
    return cid


def _modify(layout, cid="update", cap="seat", ref="R1", **fields):
    _new(layout, cid, cap)
    changes.add_delta(layout, cid, cap,
                      {"op": "modify-requirement", "ref": ref,
                       **(fields or {"statement": "It SHALL also report remaining seats."})})
    return f"draft-req:{cid}/{cap}/{ref}"


def _add(layout, cid="addition", cap="seat", new=False):
    _new(layout, cid, cap, new)
    requirement = _requirement("ignored", "It SHALL include empty rooms.")
    delta = changes.add_delta(layout, cid, cap,
                              {"op": "add-requirement",
                               **{key: value for key, value in requirement.items() if key != "id"}},
                              purpose="Synthetic capability" if new else None)
    return f"draft-req:{cid}/{cap}/{delta['id']}"


def _source(layout, ref):
    resolver = getattr(links, "resolve_requirement_source", None)
    assert callable(resolver), "F2 must expose the shared requirement source resolver"
    result = resolver(layout, ref)
    assert isinstance(result, dict)
    assert result["original-ref"] == ref
    assert {"source-kind", "state", "source-ref", "change", "baseline", "statement",
            "fingerprint", "based-on", "diagnostics"} <= result.keys()
    return result


def _complete_and_archive(layout, cid, refs):
    change = changes.load_change(layout, cid)
    task = tasks.add_task(change["tasks"], title="Inspect synthetic requirement", implements=refs,
                          files=[], methods=["inspection"], tests=[], allow_skips=False,
                          depends_on=[], tool="gpt", instance="f2-independent-test-fixture")
    changes.write_part(layout, cid, "tasks", change["tasks"])
    evidence.record(layout, cid, task["id"], "inspection", tool="gpt",
                    subject="Synthetic requirement behavior", conclusion="Verified by inspection", result="pass")
    evidence.accept(layout, cid, task["id"], tool="gpt",
                    read_back="The synthetic requirement matches the requested scope.", confirmed="Approved")
    return archive.archive(layout, cid, tool="gpt")


def _document(layout, write_leaf, refs):
    home = layout.planning_home
    write_leaf(home, "manual", concept={"id": "c-manual", "title": "Operation manual", "order": 0,
                                         "concept": "Synthetic seating manual",
                                         "brief": {"audience": "teacher", "depth": "steps", "breadth": "seating"}})
    write_leaf(home, "manual/export", concept={"id": "c-export", "title": "Export seats", "order": 1,
                                                "concept": "Export the current room layout", "realizes": refs})
    return "manual/export"


def _leaf_and_index(layout, section="manual/export"):
    leaves = load_project(layout)
    return next(leaf for leaf in leaves if leaf.section == section), project_decision_index(layout, leaves)


def _sync(layout, section="manual/export"):
    leaves = load_project(layout)
    by_section = {leaf.section: leaf for leaf in leaves}
    return _leaf_row(layout, by_section[section], load_schema(), True, _docs_hashes(layout, "manual"),
                     by_section, project_decision_index(layout, leaves))["sync"]


def _write_document(layout):
    assert render_cmd.run(["manual"]) == 0
    path = layout.project_root / "docs" / "manual" / "_latest.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace("# Operation manual\n", "# Operation manual\n\nExport the prepared room layout.\n")
    text = text.replace("## 1. Export seats\n", "## 1. Export seats\n\nChoose Export to save the seat layout.\n")
    path.write_text(text, encoding="utf-8")
    assert render_cmd.run(["manual"]) == 0
    assert _sync(layout) == "synced"


def _manifest(layout):
    return {path.relative_to(layout.project_root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in layout.project_root.rglob("*") if path.is_file()}


def _baseline(layout, cid):
    [path] = list(io.baselines_dir(layout).glob(f"*-{cid}.yaml"))
    return path


def test_active_added_requirement_has_the_selected_draft_source(project):
    ref = _add(project)
    source = _source(project, ref)
    assert source["state"] == "draft"
    assert source["change"] == "addition"
    assert "include empty rooms" in source["statement"]
    assert source["fingerprint"] and not source["diagnostics"]


def test_active_modified_requirement_and_its_scenarios_share_one_source(project):
    ref = _modify(project)
    changes.add_delta(project, "update", "seat", {"op": "modify-scenario", "ref": "R1/S1",
                                                   "then": "remaining seats are also shown"})
    source = _source(project, ref)
    assert source["state"] == "draft"
    assert "also report remaining seats" in source["statement"]
    assert "remaining seats are also shown" in source["statement"]


def test_scenario_only_delta_makes_its_requirement_a_valid_draft_source(project):
    _new(project)
    changes.add_delta(project, "update", "seat", {"op": "modify-scenario", "ref": "R1/S1",
                                                   "then": "empty rooms are also shown"})
    source = _source(project, "draft-req:update/seat/R1")
    assert source["state"] == "draft" and "empty rooms are also shown" in source["statement"]


def test_same_requirement_number_in_two_changes_is_not_mixed(project):
    first = _modify(project, "first", statement="It SHALL show first-change content.")
    second = _modify(project, "second", statement="It SHALL show second-change content.")
    a, b = _source(project, first), _source(project, second)
    assert a["state"] == b["state"] == "draft"
    assert "first-change content" in a["statement"] and "second-change content" not in a["statement"]
    assert "second-change content" in b["statement"] and "first-change content" not in b["statement"]
    assert a["fingerprint"] != b["fingerprint"]


def test_unmodified_requirement_is_not_borrowed_from_formal_specs(project):
    _modify(project)
    source = _source(project, "draft-req:update/seat/R2")
    assert source["state"] == "unresolved" and source["diagnostics"]
    assert not source["statement"]


def test_capability_containing_slashes_resolves_before_and_after_archive(project):
    ref = _add(project, "nested", "school/room/seats", new=True)
    assert _source(project, ref)["state"] == "draft"
    _complete_and_archive(project, "nested", ["school/room/seats/R1"])
    source = _source(project, ref)
    assert source["state"] == "formal"
    assert source["source-ref"] == "req:school/room/seats/R1" and source["baseline"]


def test_base_conflict_does_not_project_valid_looking_draft_content(project):
    ref = _modify(project)
    spec = specs.load_spec(project, "seat")
    spec["requirements"][0]["statement"] = "It SHALL follow a later formal edit."
    specs.write_spec(project, spec)
    source = _source(project, ref)
    assert source["state"] == "base-conflict" and source["diagnostics"]
    assert not source["statement"]


@pytest.mark.parametrize("ref", ["draft-req:update/seat/R1/S1", "draft-req:update/seat/not-a-requirement",
                                  "draft-req:../seat/R1", "draft-req:update/../seat/R1",
                                  "draft-req:update/school\\room/R1"])
def test_unsupported_or_unsafe_draft_reference_is_diagnosed(project, ref):
    _modify(project)
    source = _source(project, ref)
    assert source["state"] in {"unresolved", "unknown"}
    assert source["diagnostics"] and not source["statement"]


def test_archive_proof_preserves_the_original_reference_and_history(project, write_leaf):
    ref = _modify(project)
    _document(project, write_leaf, [ref])
    _complete_and_archive(project, "update", ["seat/R1"])
    before = _manifest(project)
    source = _source(project, ref)
    leaf, index = _leaf_and_index(project)
    projected = realized_statements(leaf, index)
    assert source["state"] == "formal" and source["source-ref"] == "req:seat/R1" and source["baseline"]
    assert projected[0]["id"] == ref and projected[0]["source"] == source
    assert leaf.concept["realizes"] == [ref]
    assert _manifest(project) == before


def test_archived_requirement_renaming_uses_saved_mapping_not_same_number(project):
    ref = _add(project)
    assert ref.endswith("/R3")
    # A valid later formal addition occupies the old draft number. The existing
    # delta engine reallocates it when this change lands and seals that mapping.
    formal = specs.load_spec(project, "seat")
    formal["requirements"].append(_requirement("R3", "It SHALL preserve unrelated formal content."))
    specs.write_spec(project, formal)
    result = _complete_and_archive(project, "addition", ["seat/R3"])
    assert result["renames"]["seat/R3"] == "seat/R4"
    source = _source(project, ref)
    assert source["state"] == "formal" and source["source-ref"] == "req:seat/R4"
    assert "include empty rooms" in source["statement"]
    assert "unrelated formal content" not in source["statement"]


def test_archived_scenario_renaming_keeps_requirement_source_resolvable(project):
    _new(project)
    changes.add_delta(project, "update", "seat", {"op": "add-scenario", "ref": "R1", "title": "Empty room",
                                                   "when": "a room is empty", "then": "its capacity is shown"})
    formal = specs.load_spec(project, "seat")
    formal["requirements"][0]["scenarios"].append({"id": "S2", "title": "Other",
                                                    "when": "other output", "then": "unrelated scenario"})
    specs.write_spec(project, formal)
    result = _complete_and_archive(project, "update", ["seat/R1"])
    assert result["renames"]["seat/R1/S2"] == "seat/R1/S3"
    source = _source(project, "draft-req:update/seat/R1")
    assert source["state"] == "formal" and "its capacity is shown" in source["statement"]


def test_legacy_archive_move_does_not_require_the_old_full_folder_path(project):
    ref = _modify(project)
    result = _complete_and_archive(project, "update", ["seat/R1"])
    legacy = io.legacy_changes_dir(project) / io.ARCHIVE_DIR / result["dest"].name
    legacy.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(result["dest"]), str(legacy))
    source = _source(project, ref)
    assert source["state"] == "formal" and source["source-ref"] == "req:seat/R1"


@pytest.mark.parametrize("damage", ["missing", "corrupt", "wrong-change", "missing-capability", "duplicate"])
def test_insufficient_baseline_cannot_borrow_same_number_formal_requirement(project, damage):
    ref = _modify(project)
    _complete_and_archive(project, "update", ["seat/R1"])
    path = _baseline(project, "update")
    if damage == "missing":
        path.unlink()
    elif damage == "corrupt":
        path.write_text(path.read_text(encoding="utf-8").replace("archived-by: gpt", "archived-by: altered"),
                        encoding="utf-8")
    elif damage == "duplicate":
        shutil.copyfile(path, path.parent / "duplicate-update.yaml")
    else:
        body = io.load(path, "baseline")
        if damage == "wrong-change":
            body["change"] = "other-change"
        else:
            body["specs"] = {}
        io.write(path, "baseline", body)
    before = _manifest(project)
    source = _source(project, ref)
    assert source["state"] in {"unresolved", "unknown"} and source["diagnostics"]
    assert not source["statement"]
    assert _manifest(project) == before


def test_corrupt_delta_seal_and_duplicate_change_containers_are_not_guessed(project):
    ref = _modify(project)
    delta = io.change_dir(project, "update") / "specs" / "seat.yaml"
    original = delta.read_bytes()
    delta.write_text(delta.read_text(encoding="utf-8").replace("remaining seats", "occupied seats"), encoding="utf-8")
    source = _source(project, ref)
    assert source["state"] == "unknown" and source["diagnostics"]
    assert not source["statement"]
    delta.write_bytes(original)
    shutil.copytree(io.change_dir(project, "update"), io.legacy_changes_dir(project) / "update")
    source = _source(project, ref)
    assert source["state"] == "unknown" and source["diagnostics"]
    assert not source["statement"]


def test_retracted_delta_is_unresolved_even_when_formal_requirement_exists(project):
    ref = _modify(project)
    assert changes.remove_deltas(project, "update", "seat", "R1") == 1
    source = _source(project, ref)
    assert source["state"] == "unresolved" and source["diagnostics"]
    assert not source["statement"]


def test_retired_landing_requirement_reports_retirement_instead_of_another_source(project):
    ref = _modify(project)
    _complete_and_archive(project, "update", ["seat/R1"])
    formal = specs.load_spec(project, "seat")
    formal["requirements"] = [r for r in formal["requirements"] if r["id"] != "R1"]
    formal["retired"] = {"requirements": ["R1"]}
    specs.write_spec(project, formal)
    source = _source(project, ref)
    assert source["state"] == "retired" and source["diagnostics"]
    assert not source["statement"]


@pytest.mark.parametrize("field", ["statement", "scenario", "verification", "based-on"])
def test_landed_requirement_semantic_changes_stale_only_the_software_axis(project, write_leaf, field):
    ref = _modify(project)
    _complete_and_archive(project, "update", ["seat/R1"])
    _document(project, write_leaf, [ref])
    _write_document(project)
    leaf, index = _leaf_and_index(project)
    original = deps_fingerprint(leaf, index)
    document_only = deps_doc_fingerprint(leaf, index)
    formal = specs.load_spec(project, "seat")
    requirement = formal["requirements"][0]
    if field == "statement":
        requirement["statement"] = "It SHALL include room capacity."
    elif field == "scenario":
        requirement["scenarios"][0]["then"] = "room capacity is also shown"
    elif field == "verification":
        requirement["verification"] = ["demonstration"]
    else:
        requirement["based-on"] = ["gov:D-gpt-99"]
    specs.write_spec(project, formal)
    leaf, index = _leaf_and_index(project)
    assert deps_fingerprint(leaf, index) != original
    assert deps_doc_fingerprint(leaf, index) == document_only
    assert _sync(project) == "stale-software"


def test_mtime_title_and_unrelated_requirement_changes_do_not_stale_draft_source(project, write_leaf):
    ref = _modify(project)
    _complete_and_archive(project, "update", ["seat/R1"])
    _document(project, write_leaf, [ref])
    _write_document(project)
    leaf, index = _leaf_and_index(project)
    original = deps_fingerprint(leaf, index)
    formal = specs.load_spec(project, "seat")
    formal["requirements"][0]["title"] = "Purely descriptive title change"
    formal["requirements"][1]["statement"] = "It SHALL modify unrelated behavior."
    specs.write_spec(project, formal)
    path = io.spec_path(project, "seat")
    os.utime(path, (path.stat().st_atime, path.stat().st_mtime + 3600))
    leaf, index = _leaf_and_index(project)
    assert deps_fingerprint(leaf, index) == original
    assert _sync(project) == "synced"


def test_formal_req_meaning_and_existing_fingerprint_bytes_are_unchanged(project, write_leaf):
    ref = _modify(project)
    _document(project, write_leaf, ["req:seat/R1"])
    leaf, index = _leaf_and_index(project)
    formal_before = deps_fingerprint(leaf, index)
    legacy_entry = {"req:seat/R1": {"section": None, "statement": specs.requirement_text(_requirement("R1")),
                                    "kind": "decision", "status": "accepted", "superseded_by": None}}
    assert formal_before == deps_fingerprint(leaf, legacy_entry)
    source = _source(project, "req:seat/R1")
    assert source["state"] == "formal" and "also report" not in source["statement"]
    assert _source(project, ref)["state"] == "draft"
    assert deps_fingerprint(*_leaf_and_index(project)) == formal_before


def test_missing_draft_source_is_a_software_diagnostic_not_a_corpus_dead_reference(project, write_leaf):
    ref = "draft-req:missing/seat/R1"
    _document(project, write_leaf, [ref])
    result = run_check(load_project(project), load_schema(), project)
    assert result.ok, result.errors
    assert any(ref in error for error in result.software_errors)
    assert not any("nonexistent id" in error for error in result.errors)
    _write_document(project)
    assert freeze_cmd.run(["manual"]) == 0


def test_incomplete_software_cannot_archive_but_ready_document_can_freeze(project, write_leaf):
    ref = _modify(project)
    _document(project, write_leaf, [ref])
    _write_document(project)
    result = run_check(load_project(project), load_schema(), project)
    assert result.ok and result.software_errors
    with pytest.raises(io.SoftwareError, match="cannot archive"):
        archive.archive(project, "update", tool="gpt")
    assert freeze_cmd.run(["manual"]) == 0
    frozen = project_baseline.doc_version_record(project, "manual", "1.0.0")
    assert frozen
    assert changes.change_state(project, "update") == "active"


@pytest.mark.parametrize("missing", [False, True])
def test_projection_and_summary_share_source_facts_and_queries_are_read_only(
        project, write_leaf, monkeypatch, capsys, missing):
    ref = "draft-req:missing/seat/R1" if missing else _modify(project)
    _document(project, write_leaf, [ref])
    assert ruling_cmd.run(["add", "--quote", "Inspect the synthetic manual through its existing work."]) == 0
    assert roadmap_cmd.run(["add", "--title", "Synthetic manual", "--ref", "doc:manual"]) == 0
    capsys.readouterr()
    before = _manifest(project)

    def forbidden(*args, **kwargs):
        pytest.fail("A source query must not execute an external command")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    assert instructions_cmd.run(["apply", "manual/export", "--json"]) == 0
    projection = json.loads(capsys.readouterr().out)
    [realized] = projection["realized"]
    source = _source(project, ref)
    assert realized["id"] == ref and realized["source"] == source
    assert instructions_cmd.run(["apply", "manual/export"]) == 0
    text = capsys.readouterr().out
    assert ref in text and source["state"] in text
    for diagnosis in source["diagnostics"]:
        reason = diagnosis.get("reason", diagnosis.get("message", "")) if isinstance(diagnosis, dict) else str(diagnosis)
        if reason:
            assert reason in text
    assert roadmap_cmd.run(["show", "W-gpt-1", "--json"]) == 0
    summary = json.loads(capsys.readouterr().out)
    summary_text = json.dumps(summary, ensure_ascii=False)
    assert ref in summary_text and source["state"] in summary_text
    if not missing:
        assert "also report remaining seats" in summary_text
    assert roadmap_cmd.run(["show", "W-gpt-1"]) == 0
    summary_text = capsys.readouterr().out
    assert ref in summary_text
    assert _manifest(project) == before


def test_draft_trace_uses_original_node_and_the_actual_governance_basis(project, write_leaf, capsys):
    assert ruling_cmd.run(["add", "--quote", "Include remaining capacity in the synthetic output."]) == 0
    assert decision_cmd.run(["add", "--title", "Capacity", "--statement", "Show capacity",
                             "--based-on", "RL-gpt-1"]) == 0
    assert decision_cmd.run(["activate", "D-gpt-1"]) == 0
    ref = _modify(project, **{"based-on": ["gov:D-gpt-1"]})
    _document(project, write_leaf, [ref])
    capsys.readouterr()
    before = _manifest(project)
    assert trace_cmd.run(["D-gpt-1", "--json"]) == 0
    traced = json.loads(capsys.readouterr().out)
    assert {"ref": ref, "type": "based-on"} in traced["downstream"]
    assert ref in json.dumps(traced, ensure_ascii=False)
    assert _manifest(project) == before
