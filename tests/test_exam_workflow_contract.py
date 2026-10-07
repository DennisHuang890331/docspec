"""Evaluator fixture contracts, never evidence of a participant workflow pass.

Only the case builder runs here. Supplied CLI/wheel files are inert synthetic
inputs: no installed product, external provider, or product test is executed.
"""
from __future__ import annotations

from collections import Counter
import csv
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest


REPO = Path(__file__).resolve().parents[1]
BUILDER = REPO / "scripts/validation/build_exam_workflow_cases.py"
RECORDER = REPO / "scripts/validation/record_installed_command.py"
PRIVATE_FILES = {
    "oracle.json", "owner-persona.md", "change-event.md", "handover-task.md",
    "recorder-config.json", "manifest.json", "record_installed_command.py",
}
SYNTHETIC_IDS = re.compile(r"\b(?:RL|D|W|E|T)-(?:gpt|codex|claude|gemini)-\d+\b")


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(data: dict) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file()}


@pytest.fixture
def builder():
    assert BUILDER.is_file(), "exam case builder has not been implemented"
    spec = importlib.util.spec_from_file_location("exam_case_builder_contract", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def contract(builder):
    return builder.case_contract()


@pytest.fixture
def inputs(tmp_path):
    # Deliberately cannot serve as a CLI; preparing a case must not execute it.
    cli = tmp_path / "installed cli" / "artispec.exe"
    cli.parent.mkdir()
    cli.write_bytes(b"synthetic inert console-script fixture\n")
    wheel = tmp_path / "synthetic-artispec-0.1.0-py3-none-any.whl"
    wheel.write_bytes(b"synthetic wheel hash input; not a distributable artifact\n")
    return cli, wheel


def _build(output: Path, inputs, platform: str, runtime_python: Path | None = None):
    assert BUILDER.is_file(), "exam case builder has not been implemented"
    cli, wheel = inputs
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("DOCSPEC_AGENT", None)
    env["PYTHONUTF8"] = "1"
    result = subprocess.run(
        [sys.executable, str(BUILDER), "--output-dir", str(output),
         "--cli", str(cli), "--python", str(runtime_python or sys.executable), "--wheel", str(wheel),
         "--platform", platform], cwd=REPO, env=env, capture_output=True,
        encoding="utf-8", errors="strict", timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    runs = [p for p in output.iterdir() if p.is_dir() and p.name.startswith("run-")]
    assert runs, "builder must create a fresh run-* directory"
    return runs


def _manifest(run: Path) -> dict:
    return json.loads((run / "manifest.json").read_text(encoding="utf-8"))


def test_contract_is_deterministic_json_and_does_not_mutate_environment(builder):
    before = dict(os.environ)
    first = builder.case_contract()
    second = builder.case_contract()
    assert first == second
    assert dict(os.environ) == before
    assert set(first) == {
        "task", "owner_persona", "change_event", "handover_task", "oracle", "students_csv",
    }
    assert isinstance(first["oracle"], dict)
    for name in set(first) - {"oracle"}:
        assert isinstance(first[name], str) and first[name].strip()
    assert json.loads(_canonical(first)) == first


def test_synthetic_students_have_unique_class_and_number_identity(contract):
    reader = csv.DictReader(io.StringIO(contract["students_csv"]))
    assert reader.fieldnames == ["class", "number", "name"]
    students = list(reader)
    assert len(students) == 16
    assert sorted(Counter(row["class"] for row in students).values()) == [8, 8]
    assert len({(row["class"], row["number"]) for row in students}) == 16
    assert all(row["name"].strip() for row in students)
    for class_name in {row["class"] for row in students}:
        assert {int(row["number"]) for row in students if row["class"] == class_name} == set(range(1, 9))
    assert "合成" in contract["owner_persona"] or "synthetic" in contract["owner_persona"].lower()


def test_oracle_has_the_agreed_room_student_and_adjacency_rules(contract):
    oracle = contract["oracle"]
    assert oracle["students"] == {
        "count": 16, "classes": 2, "per_class": 8,
        "csv_columns": ["class", "number", "name"],
    }
    rooms = oracle["rooms"]
    assert len(rooms) == 2 and len({room["id"] for room in rooms}) == 2
    assert all(room["rows"] == room["columns"] == 4 for room in rooms)
    assert oracle["adjacency"] == {"orthogonal": True, "diagonal": False}
    assert oracle["initial_output_fields"] == ["class", "number", "name"]
    assert oracle["change_output_fields"] == ["capacity", "remaining"]


def test_fixed_fixture_has_a_constructive_legal_seating_solution(contract):
    # Checkerboard colors prove feasibility without shipping a solved seating
    # table to the participant, or evaluating an unimplemented product solver.
    rows = list(csv.DictReader(io.StringIO(contract["students_csv"])))
    classes = sorted({row["class"] for row in rows})
    queues = {name: [row for row in rows if row["class"] == name] for name in classes}
    placed = {}
    for room in contract["oracle"]["rooms"]:
        for row in range(room["rows"]):
            for column in range(room["columns"]):
                name = classes[(row + column) % 2]
                if queues[name]:
                    placed[room["id"], row, column] = queues[name].pop()
    assert all(not queue for queue in queues.values())
    assert len(placed) == 16
    assert len({(s["class"], s["number"]) for s in placed.values()}) == 16
    for (room, row, column), student in placed.items():
        for dy, dx in ((0, 1), (1, 0)):
            adjacent = placed.get((room, row + dy, column + dx))
            assert adjacent is None or adjacent["class"] != student["class"]


def test_opening_task_keeps_owner_answers_and_future_change_private(contract):
    task = contract["task"]
    assert "README" in task
    assert "提問" in task or "詢問" in task or "ask" in task.lower()
    assert "考場" in task or "seating" in task.lower()
    assert not SYNTHETIC_IDS.search(task)
    for hidden in ("oracle", "owner-persona", "capacity", "remaining", "剩餘座位", "前後左右", "斜角"):
        assert hidden not in task
    assert not re.search(r"\b16\b|4\s*[xX×＊*]\s*4", task)
    assert contract["owner_persona"] not in task
    assert contract["change_event"] not in task


def test_owner_persona_covers_real_operator_constraints_and_document_authority(contract):
    persona = contract["owner_persona"]
    for term in ("Windows", "CSV", "姓名", "座號", "操作手冊", "PDF", "proof", "合成"):
        assert term.lower() in persona.lower()
    assert "離線" in persona
    assert "雙擊" in persona or "双击" in persona
    assert "安裝" in persona or "安装" in persona
    assert "授權" in persona and "定版" in persona
    assert "示意圖" in persona
    assert "前後左右" in persona and "斜角" in persona
    document = contract["oracle"]["document"]
    assert document == {
        "manual_count": 1, "seating_diagram_count": 1,
        "pdf_proof_required": True, "synthetic_freeze_authorized": True,
    }


def test_once_only_change_and_fresh_handover_are_observable_without_fake_ids(contract):
    event = contract["change_event"]
    handover = contract["handover_task"]
    assert "容量" in event and "剩餘" in event
    assert "初版" in event
    assert "一次" in event
    assert "全新" in handover or "fresh" in handover.lower()
    assert "接手" in handover or "resume" in handover.lower()
    assert "對話" in handover or "conversation" in handover.lower()
    assert not SYNTHETIC_IDS.search(event + handover)


@pytest.mark.parametrize("platform", ["windows", "linux"])
def test_case_project_contains_only_readmes_opening_task_and_synthetic_input(tmp_path, inputs, contract, platform):
    run, = _build(tmp_path / platform, inputs, platform)
    manifest = _manifest(run)
    project = Path(manifest["project"])
    assert project.is_dir() and project.parent == run
    assert {p.name for p in project.iterdir()} == {
        "README.md", "README.zh-TW.md", "TASK.md", "students.csv",
    }
    assert (project / "TASK.md").read_text(encoding="utf-8") == contract["task"]
    assert (project / "students.csv").read_text(encoding="utf-8") == contract["students_csv"]
    assert (project / "TASK.md").read_bytes() == contract["task"].encode("utf-8")
    assert (project / "students.csv").read_bytes() == contract["students_csv"].encode("utf-8")
    for name in ("README.md", "README.zh-TW.md"):
        assert (project / name).read_bytes() == (REPO / name).read_bytes()
    assert not (project / "docspec").exists()
    assert not (project / "AGENTS.md").exists()
    assert not PRIVATE_FILES.intersection(p.name for p in project.rglob("*"))
    assert PRIVATE_FILES <= {p.name for p in run.iterdir()}
    assert json.loads((run / "oracle.json").read_text(encoding="utf-8")) == contract["oracle"]
    for filename, key in (("owner-persona.md", "owner_persona"), ("change-event.md", "change_event"),
                          ("handover-task.md", "handover_task")):
        assert (run / filename).read_text(encoding="utf-8") == contract[key]


def test_platforms_share_semantic_contract_and_artifact_hashes(tmp_path, inputs, contract):
    windows, = _build(tmp_path / "windows", inputs, "windows")
    linux, = _build(tmp_path / "linux", inputs, "linux")
    manifests = [_manifest(windows), _manifest(linux)]
    assert [m["platform"] for m in manifests] == ["windows", "linux"]
    for manifest in manifests:
        assert manifest["contract_version"] == 1
        assert manifest["case_id"]
        assert manifest["wheel_sha256"] == _hash(inputs[1].read_bytes())
        assert manifest["contract_sha256"] == _hash(_canonical(contract))
        assert manifest["participant_launches"] == []
        assert manifest["agent_workflow_executed"] is False
    assert (windows / "oracle.json").read_bytes() == (linux / "oracle.json").read_bytes()


@pytest.mark.parametrize("platform", ["windows", "linux"])
def test_opening_task_points_to_the_public_guide_with_original_bytes_and_hash(tmp_path, inputs, platform):
    run, = _build(tmp_path / platform, inputs, platform)
    manifest = _manifest(run)
    project = Path(manifest["project"])
    task = (project / "TASK.md").read_text(encoding="utf-8")
    relative_guide = "../reference/docs/user-guide.md"
    assert relative_guide in task
    guide = (project / relative_guide).resolve(strict=True)
    assert guide == run / "reference/docs/user-guide.md"
    assert guide.read_bytes() == (REPO / "docs/user-guide.md").read_bytes()
    assert manifest["reference_files"] == {
        "reference/docs/user-guide.md": _hash(guide.read_bytes()),
    }
    assert _snapshot(run / "reference") == {"docs/user-guide.md": guide.read_bytes()}
    assert {p.name for p in project.iterdir()} == {
        "README.md", "README.zh-TW.md", "TASK.md", "students.csv",
    }


def test_repeated_preparation_preserves_every_old_run_byte(tmp_path, inputs):
    output = tmp_path / "runs"
    first, = _build(output, inputs, "windows")
    marker = first / "participant-note.txt"
    marker.write_text("Existing observations must survive.\n", encoding="utf-8")
    before = _snapshot(first)
    runs = _build(output, inputs, "windows")
    assert len(runs) == 2
    assert first in runs
    assert _snapshot(first) == before


def test_linux_manifest_preserves_the_real_venv_python_symlink(tmp_path, inputs):
    python_link = tmp_path / "synthetic-venv" / "bin" / "python"
    python_link.parent.mkdir(parents=True)
    try:
        python_link.symlink_to(Path(sys.executable).resolve())
    except OSError as exc:
        if os.name == "nt" and (isinstance(exc, PermissionError) or getattr(exc, "winerror", None) == 1314):
            pytest.skip(f"Windows cannot create the real venv Python symlink: {exc}")
        raise
    assert python_link.is_symlink()
    assert python_link.absolute() != python_link.resolve()
    run, = _build(tmp_path / "linux-runs", inputs, "linux", runtime_python=python_link)
    manifest = _manifest(run)
    assert manifest["python"] == str(python_link.absolute())
    assert manifest["python"] != str(python_link.resolve())


def test_preparation_does_not_launch_product_or_external_test_processes(builder, tmp_path, inputs, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("case preparation launched a product or external process")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.delenv("PYTHONPATH", raising=False)
    before_env, before_cwd = dict(os.environ), Path.cwd()
    cli, wheel = inputs
    builder.main([
        "--output-dir", str(tmp_path / "runs"), "--cli", str(cli),
        "--python", sys.executable, "--wheel", str(wheel), "--platform", "windows",
    ])
    assert dict(os.environ) == before_env
    assert Path.cwd() == before_cwd
    run, = (tmp_path / "runs").iterdir()
    assert _manifest(run)["agent_workflow_executed"] is False


@pytest.mark.parametrize("platform", ["windows", "linux"])
def test_recorder_uses_the_supplied_installed_cli_without_spoofed_identity(tmp_path, inputs, platform):
    run, = _build(tmp_path / platform, inputs, platform)
    manifest = _manifest(run)
    config = json.loads((run / "recorder-config.json").read_text(encoding="utf-8"))
    assert Path(config["executable"]) == inputs[0].resolve()
    assert Path(config["project"]) == Path(manifest["project"])
    assert Path(config["log"]).parent == run
    assert not Path(config["log"]).exists(), "preparation must not fabricate command evidence"
    assert "DOCSPEC_AGENT" not in config.get("environment", {})
    assert "PYTHONPATH" not in config.get("environment", {})
    assert (run / "record_installed_command.py").read_bytes() == RECORDER.read_bytes()
    assert not list(run.rglob("*commands*.jsonl"))
