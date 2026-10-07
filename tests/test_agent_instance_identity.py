"""Synthetic mechanical actor checks, not proof of independent product testing."""
from __future__ import annotations

import copy
import importlib

import pytest

from test_software_archive import proj, code
from dspx.engine import governance as gv
from dspx.engine.software import changes as chg, evidence as ev, io, tasks as tk


A = "synthetic-test-session-A"
B = "synthetic-implementation-session-B"
C = "synthetic-unrelated-session-C"
ERRORS = (gv.GovernanceError, io.SoftwareError, ValueError)


@pytest.fixture
def actors():
    return importlib.import_module("dspx.engine.actors")


@pytest.fixture(autouse=True)
def isolated_actor_environment(monkeypatch):
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.delenv("DOCSPEC_ACTOR_ID", raising=False)


def _actor(monkeypatch, instance):
    monkeypatch.setenv("DOCSPEC_AGENT", "gpt")
    monkeypatch.delenv("DOCSPEC_ACTOR_ID", raising=False)
    if instance is None:
        monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    else:
        monkeypatch.setenv("CODEX_THREAD_ID", instance)


def _new_test(plan, instance=None):
    return tk.add_test(plan, location="app:tests/test_entry.py::test_first_row",
                       covers=["entry/R1/S1"], level="unit", tool="gpt", note=None,
                       today="2026-10-01", instance=instance)


def _new_task(tasks, instance=None):
    return tk.add_task(tasks, title="Synthetic implementation", implements=["entry/R1"],
                       files=["app:src/entry.py"], methods=["test"], tests=["T1"],
                       allow_skips=False, depends_on=[], tool="gpt", instance=instance)


def _change():
    assert code("change", "new", "identity", "--why", "synthetic actor contract", "--modified", "entry") == 0
    assert code("change", "delta", "identity", "--capability", "entry", "--op", "modify-scenario",
                "--ref", "R1/S1", "--then", "A synthetic actor check is valid") == 0


def _sign(layout, change, instance):
    return tk.sign_tests(layout, change, ["T1"], tool="gpt", now="2026-10-01T00:00:00Z",
                         fingerprint=lambda location: ev.file_hash(layout, ev.test_file_key(location)),
                         instance=instance)


def _bytes(layout):
    return {p.relative_to(layout.planning_home).as_posix(): p.read_bytes()
            for p in layout.planning_home.rglob("*") if p.is_file()}


def _cli_test(monkeypatch, instance=A):
    _actor(monkeypatch, instance)
    assert code("testplan", "add", "identity", "--location", "app:tests/test_entry.py::test_first_row",
                "--covers", "entry/R1/S1") == 0


def _cli_task(monkeypatch, instance=B):
    _actor(monkeypatch, instance)
    assert code("task", "add", "identity", "--title", "Synthetic implementation",
                "--implements", "entry/R1", "--files", "app:src/entry.py", "--verify", "test", "--tests", "T1") == 0


def test_codex_thread_is_authoritative_and_matching_explicit_actor_is_allowed(actors, monkeypatch):
    monkeypatch.setenv("CODEX_THREAD_ID", A)
    assert actors.detect_instance("gpt") == A
    monkeypatch.setenv("DOCSPEC_ACTOR_ID", A)
    assert actors.detect_instance("gpt") == A
    monkeypatch.setenv("DOCSPEC_ACTOR_ID", B)
    with pytest.raises(ERRORS):
        actors.detect_instance("gpt")


def test_explicit_actor_is_only_a_fallback_and_owner_has_no_instance(actors, monkeypatch):
    assert actors.detect_instance("gpt") is None
    monkeypatch.setenv("DOCSPEC_ACTOR_ID", A)
    assert actors.detect_instance("gpt") == A
    monkeypatch.setenv("CODEX_THREAD_ID", B)
    assert actors.detect_instance("user") is None


def test_instance_validation_accepts_absent_and_safe_codes_but_rejects_unsafe_data(actors):
    assert actors.validate_instance(None) is None
    assert actors.validate_instance(A) == A
    for unsafe in ("two words", "../other", "line\nbreak", "tab\tactor", "會話碼"):
        with pytest.raises(ERRORS):
            actors.validate_instance(unsafe)


@pytest.mark.parametrize("unsafe", ["two words", "../other", "line\nbreak", "tab\tactor", "會話碼"])
def test_nonempty_actor_codes_reject_unsafe_formats(actors, monkeypatch, unsafe):
    monkeypatch.setenv("DOCSPEC_ACTOR_ID", unsafe)
    with pytest.raises(ERRORS):
        actors.detect_instance("gpt")
    monkeypatch.delenv("DOCSPEC_ACTOR_ID")
    monkeypatch.setenv("CODEX_THREAD_ID", unsafe)
    with pytest.raises(ERRORS):
        actors.detect_instance("gpt")


@pytest.mark.parametrize("first,second,expected", [(A, A, True), (A, B, False), (A, None, True),
                                                  (None, B, True), (None, None, True)])
def test_same_provider_distinguishes_known_sessions_and_preserves_legacy_guards(actors, first, second, expected):
    assert actors.same_actor("gpt", first, "gpt", second) is expected
    assert actors.same_actor("gpt", first, "claude", second) is False


def test_author_guard_is_exact_for_new_records_and_compatible_for_old_records(actors):
    record = {"written-by": "gpt", "written-by-instance": A}
    actors.require_author(record, "gpt", A)
    actors.require_author(record, "user", None)
    for tool, instance in (("gpt", B), ("gpt", None), ("claude", A)):
        with pytest.raises(ERRORS):
            actors.require_author(record, tool, instance)
    actors.require_author({"written-by": "gpt"}, "gpt", B)
    with pytest.raises(ERRORS):
        actors.require_author({"written-by": "gpt"}, "claude", None)
    actors.require_author({"by": "gpt", "by-instance": A}, "gpt", A,
                          field="by", instance_field="by-instance")


def test_engine_persists_supplied_instances_without_detecting_ambient_session(monkeypatch):
    _actor(monkeypatch, C)
    plan, tasks = {}, {}
    assert _new_test(plan, A)["written-by-instance"] == A
    assert _new_task(tasks, B)["created-by-instance"] == B
    assert "written-by-instance" not in _new_test(plan)
    assert "created-by-instance" not in _new_task(tasks)


@pytest.mark.parametrize("implementer,allowed", [(B, True), (A, False), (None, False)])
def test_signoff_separates_same_provider_sessions_and_keeps_unknown_implementer_blocked(proj, implementer, allowed):
    _change()
    change = chg.load_change(proj, "identity")
    test = _new_test(change["tests"], A)
    _new_task(change["tasks"], implementer)
    if allowed:
        assert _sign(proj, change, A) == [test]
        assert test["signed"]["by"] == "gpt"
        assert test["signed"]["by-instance"] == A
    else:
        before = copy.deepcopy(change)
        with pytest.raises(ERRORS):
            _sign(proj, change, A)
        assert change == before


@pytest.mark.parametrize("candidate", [B, None])
def test_new_test_cannot_be_signed_by_another_or_unidentified_session(proj, candidate):
    _change()
    change = chg.load_change(proj, "identity")
    _new_test(change["tests"], A)
    with pytest.raises(ERRORS):
        _sign(proj, change, candidate)
    assert "signed" not in change["tests"]["tests"][0]


def test_same_provider_objection_round_trip_uses_instances_and_rejects_self_response():
    plan = {}
    _new_test(plan, A)
    objection = tk.add_objection(plan, test_id="T1", reason="Synthetic objection", tool="gpt",
                                today="2026-10-01", instance=B)
    assert objection["by-instance"] == B
    before = copy.deepcopy(plan)
    with pytest.raises(ERRORS):
        tk.respond_objection(plan, oid="O1", resolution="rejected", response="Synthetic answer",
                             tool="gpt", today="2026-10-01", instance=B)
    assert plan == before
    result = tk.respond_objection(plan, oid="O1", resolution="rejected", response="Synthetic answer",
                                  tool="gpt", today="2026-10-01", instance=A)
    assert result["responded-by-instance"] == A


@pytest.mark.parametrize("candidate", [C, None])
def test_only_new_test_author_can_respond_even_when_not_the_objector(candidate):
    plan = {}
    _new_test(plan, A)
    tk.add_objection(plan, test_id="T1", reason="Synthetic objection", tool="gpt",
                     today="2026-10-01", instance=B)
    before = copy.deepcopy(plan)
    with pytest.raises(ERRORS):
        tk.respond_objection(plan, oid="O1", resolution="rejected", response="Synthetic nonauthor answer",
                             tool="gpt", today="2026-10-01", instance=candidate)
    assert plan == before


@pytest.mark.parametrize("test_instance,responder,responder_instance", [(A, "user", None), (None, "gpt", A)])
def test_objection_response_preserves_owner_override_and_legacy_provider_authorship(test_instance, responder, responder_instance):
    plan = {}
    _new_test(plan, test_instance)
    tk.add_objection(plan, test_id="T1", reason="Synthetic objection", tool="gpt",
                     today="2026-10-01", instance=B)
    result = tk.respond_objection(plan, oid="O1", resolution="rejected", response="Synthetic accepted answer",
                                  tool=responder, today="2026-10-01", instance=responder_instance)
    assert result["responded-by"] == responder
    if responder_instance:
        assert result["responded-by-instance"] == responder_instance
    else:
        assert "responded-by-instance" not in result


@pytest.mark.parametrize("signed_instance", [B, None])
def test_new_signoff_with_wrong_or_missing_instance_needs_review(proj, signed_instance):
    _change()
    change = chg.load_change(proj, "identity")
    test = _new_test(change["tests"], A)
    _new_task(change["tasks"], B)
    _sign(proj, change, A)
    assert ev.signoff_problems(proj, [test], change) == []
    if signed_instance is None:
        test["signed"].pop("by-instance")
    else:
        test["signed"]["by-instance"] = signed_instance
    assert ev.signoff_problems(proj, [test], change)


def test_test_content_change_still_invalidates_instance_aware_signoff(proj):
    _change()
    change = chg.load_change(proj, "identity")
    test = _new_test(change["tests"], A)
    _new_task(change["tasks"], B)
    _sign(proj, change, A)
    assert ev.signoff_problems(proj, [test], change) == []
    path = proj.project_root / "app/tests/test_entry.py"
    path.write_text(path.read_text(encoding="utf-8").replace("assert True", "assert False", 1), encoding="utf-8")
    assert ev.signoff_problems(proj, [test], change)


@pytest.mark.parametrize("operation", ["set", "remove", "sign"])
@pytest.mark.parametrize("candidate", [B, None])
def test_cli_wrong_or_missing_new_author_cannot_modify_remove_or_sign(proj, monkeypatch, operation, candidate):
    _change()
    _cli_test(monkeypatch)
    _actor(monkeypatch, candidate)
    before = _bytes(proj)
    args = ["testplan", operation, "identity", "T1"]
    if operation == "set":
        args += ["--note", "Unauthorized synthetic edit"]
    assert code(*args) == 1
    assert _bytes(proj) == before


def test_cli_original_author_can_edit_remove_and_owner_can_override(proj, monkeypatch):
    _change()
    _cli_test(monkeypatch)
    assert code("testplan", "set", "identity", "T1", "--note", "Author's synthetic edit") == 0
    assert code("testplan", "remove", "identity", "T1") == 0
    _cli_test(monkeypatch)
    _actor(monkeypatch, B)
    monkeypatch.setenv("DOCSPEC_AGENT", "user")
    assert code("testplan", "remove", "identity", "T1") == 0


def test_cli_persists_instances_and_allows_independent_same_provider_signoff(proj, monkeypatch):
    _change()
    _cli_test(monkeypatch)
    _cli_task(monkeypatch)
    change = chg.load_change(proj, "identity")
    assert change["tests"]["tests"][0]["written-by-instance"] == A
    assert change["tasks"]["tasks"][0]["created-by-instance"] == B
    _actor(monkeypatch, A)
    assert code("testplan", "sign", "identity", "T1") == 0
    change = chg.load_change(proj, "identity")
    assert change["tests"]["tests"][0]["signed"]["by-instance"] == A
    errors, _warnings = tk.validate_tasks_and_tests(proj, change)
    assert not errors
    _errors, warnings = ev.validate(proj)
    assert not any("same agent" in warning for warning in warnings)
    # Adding a task from the test author must restore the separation guard.
    _cli_task(monkeypatch, A)
    before = _bytes(proj)
    assert code("testplan", "sign", "identity", "T1") == 1
    assert _bytes(proj) == before
    _errors, warnings = ev.validate(proj)
    assert any("same agent" in warning for warning in warnings)


def test_cli_persists_objection_and_response_instances(proj, monkeypatch):
    _change()
    _cli_test(monkeypatch)
    _actor(monkeypatch, B)
    assert code("testplan", "object", "identity", "T1", "--reason", "Synthetic objection") == 0
    before = _bytes(proj)
    assert code("testplan", "respond", "identity", "O1", "--resolution", "rejected",
                "--reason", "Synthetic self response") == 1
    assert _bytes(proj) == before
    for candidate in (C, None):
        _actor(monkeypatch, candidate)
        assert code("testplan", "respond", "identity", "O1", "--resolution", "rejected",
                    "--reason", "Synthetic nonauthor response") == 1
        assert _bytes(proj) == before
    _actor(monkeypatch, A)
    assert code("testplan", "respond", "identity", "O1", "--resolution", "rejected",
                "--reason", "Synthetic author response") == 0
    objection = chg.load_change(proj, "identity")["tests"]["objections"][0]
    assert objection["by-instance"] == B
    assert objection["responded-by-instance"] == A


def test_cli_explicit_override_cannot_replace_a_detected_codex_session(proj, monkeypatch):
    _change()
    _actor(monkeypatch, A)
    monkeypatch.setenv("DOCSPEC_ACTOR_ID", B)
    before = _bytes(proj)
    assert code("testplan", "add", "identity", "--location", "app:tests/test_entry.py::test_first_row",
                "--covers", "entry/R1/S1") == 1
    assert _bytes(proj) == before


@pytest.mark.parametrize("later_implementer,expected_current", [(A, False), (None, False), (B, True)])
def test_signoff_is_rechecked_when_an_implementation_task_is_created_later(proj, later_implementer, expected_current):
    _change()
    change = chg.load_change(proj, "identity")
    test = _new_test(change["tests"], A)
    _sign(proj, change, A)  # No implementation tasks existed at signing time.
    assert ev.signoff_problems(proj, [test], change) == []
    task = _new_task(change["tasks"], later_implementer)
    chg.write_part(proj, "identity", "tests", change["tests"])
    chg.write_part(proj, "identity", "tasks", change["tasks"])
    problems = ev.signoff_problems(proj, [test], change)
    assert bool(problems) is not expected_current
    assert ev.signoff_view(proj, change)[0]["status"] == ("current" if expected_current else "needs-review")
    # This runs the synthetic fixture test through the real engine and its JUnit
    # parser. It verifies the identity gate, not a participant/product workflow.
    record = ev.run_tests(proj, "identity", "1", tool="gpt")
    assert record["exit-code"] == 0 and record["counts"]["passed"] == 1
    assert record["result"] == ("pass" if expected_current else "fail")
    status, _support, _reason = ev.derive(proj, change, task, [record])
    if expected_current:
        assert status == "done"
        # Even a genuinely passing earlier run must lose completion after the
        # signer later creates implementation work in this same change.
        _new_task(change["tasks"], A)
        assert ev.scope_problem(proj, change, task, record) is None
        assert ev.derive(proj, change, task, [record])[0] == "needs-rerun"
    else:
        assert status not in ("done", "done-waived")


def test_legacy_signoff_without_instance_is_not_retroactively_rejected(proj):
    _change()
    change = chg.load_change(proj, "identity")
    test = _new_test(change["tests"])
    _sign(proj, change, None)
    task = _new_task(change["tasks"])
    assert test["written-by"] == test["signed"]["by"] == task["created-by"] == "gpt"
    assert "written-by-instance" not in test and "by-instance" not in test["signed"]
    assert "created-by-instance" not in task
    assert ev.signoff_problems(proj, [test], change) == []
    assert ev.signoff_view(proj, change)[0]["status"] == "current"


@pytest.mark.parametrize("author,signer", [(None, None), ("unknown", "unknown"), ("gpt", None),
                                          (None, "gpt"), ("gpt", "unknown"), ("unknown", "gpt")])
def test_instance_aware_signoff_requires_valid_author_and_signer_providers(proj, author, signer):
    _change()
    change = chg.load_change(proj, "identity")
    test = _new_test(change["tests"], A)
    _sign(proj, change, A)
    if author is None:
        test.pop("written-by")
    else:
        test["written-by"] = author
    if signer is None:
        test["signed"].pop("by")
    else:
        test["signed"]["by"] = signer
    assert ev.signoff_problems(proj, [test], change)
    assert ev.signoff_view(proj, change)[0]["status"] == "needs-review"


@pytest.mark.parametrize("corrupt_signed", [[], ["unexpected"], 0, 1, "", "unexpected", False])
def test_nonmapping_signoff_is_reported_as_needing_review_without_crashing(proj, corrupt_signed):
    _change()
    change = chg.load_change(proj, "identity")
    test = _new_test(change["tests"], A)
    test["signed"] = corrupt_signed
    assert ev.signoff_problems(proj, [test], change)
    assert ev.signoff_view(proj, change)[0]["status"] == "needs-review"


@pytest.mark.parametrize("corrupt_provider", [None, "unknown"])
def test_task_with_known_instance_and_missing_or_invalid_provider_cannot_establish_independence(proj, corrupt_provider):
    _change()
    change = chg.load_change(proj, "identity")
    test = _new_test(change["tests"], A)
    _sign(proj, change, A)
    task = _new_task(change["tasks"], B)
    if corrupt_provider is None:
        task.pop("created-by")
    else:
        task["created-by"] = corrupt_provider
    assert ev.signoff_problems(proj, [test], change)
    assert ev.signoff_view(proj, change)[0]["status"] == "needs-review"
