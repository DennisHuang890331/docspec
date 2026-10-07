"""Independent behavior contract for evaluator-side recording and checkpoints."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest


ROOT = Path(__file__).resolve().parents[1]


def runtime():
    path = ROOT / "scripts" / "validation" / "workflow_runtime.py"
    assert path.is_file(), "shared validation runtime must exist before workflows can reuse it"
    spec = importlib.util.spec_from_file_location("_tested_workflow_runtime", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _jsonl(path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def _snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_record_real_failed_command_preserves_unicode_arguments_input_and_session(tmp_path):
    helper = runtime()
    cwd = tmp_path / "中文 space"
    cwd.mkdir()
    script = cwd / "真實 command.py"
    script.write_text("import os,sys\nprint(sys.argv[1])\nprint(sys.stdin.read())\n"
                      "print(os.environ['VALIDATION_MESSAGE'])\n"
                      "print('實際錯誤',file=sys.stderr)\nraise SystemExit(7)\n", encoding="utf-8")
    log = tmp_path / "命令.jsonl"
    argv = [sys.executable, str(script), "非 ASCII argument"]
    event = helper.record_command(argv, cwd=cwd, log=log, phase="initial-test",
                                  session="real-session-1", env={"VALIDATION_MESSAGE": "受控環境"},
                                  input="輸入資料")
    assert event["argv"] == argv
    assert Path(event["cwd"]) == cwd
    assert event["exit"] == 7
    assert "非 ASCII argument" in event["stdout"]
    assert "輸入資料" in event["stdout"] and "受控環境" in event["stdout"]
    assert "實際錯誤" in event["stderr"]
    assert event["phase"] == "initial-test" and event["session"] == "real-session-1"
    assert json.loads(log.read_text(encoding="utf-8")) == event


def test_record_launch_failure_and_append_do_not_replace_prior_result(tmp_path):
    helper = runtime()
    log = tmp_path / "launch.jsonl"
    first = helper.record_command([sys.executable, "-c", "print('ok')"], cwd=tmp_path,
                                  log=log, phase="preflight", session="s1")
    second = helper.record_command([str(tmp_path / "missing-executable")], cwd=tmp_path,
                                   log=log, phase="launch", session="s2")
    assert first["exit"] == 0 and second["exit"] == 127
    assert second["stderr"] and not second["stdout"]
    assert [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] == [first, second]


def test_record_concurrent_processes_preserves_each_complete_utf8_command_result(tmp_path):
    helper = runtime()
    cwd = tmp_path / "parallel recording 中文 space"
    cwd.mkdir()
    log = cwd / "shared commands.jsonl"
    release = cwd / "release"
    payload = cwd / "actual unicode command.py"
    payload.write_text(
        "import sys\n"
        "marker=sys.argv[1]\n"
        "sys.stdout.write(marker+'\\n'+'完整輸出'*12500+'\\n')\n"
        "sys.stderr.write(marker+'\\n'+'真實錯誤'*2500+'\\n')\n"
        "raise SystemExit(int(sys.argv[2]))\n", encoding="utf-8")
    worker = cwd / "record worker.py"
    worker.write_text(
        "import importlib.util, pathlib, sys, time\n"
        "helper_path,log,cwd,payload,release,index=sys.argv[1:]\n"
        "spec=importlib.util.spec_from_file_location('shared_runtime',helper_path)\n"
        "helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)\n"
        "index=int(index);root=pathlib.Path(cwd)\n"
        "(root/('ready-'+str(index))).write_bytes(b'ready')\n"
        "deadline=time.monotonic()+20\n"
        "while not pathlib.Path(release).is_file():\n"
        "    if time.monotonic()>deadline:raise SystemExit(99)\n"
        "    time.sleep(.005)\n"
        "marker='工作-'+str(index)\n"
        "helper.record_command([sys.executable,payload,marker,str(index%3)],cwd=cwd,log=log,\n"
        "    phase='concurrent-recording',session='synthetic-session-'+str(index))\n",
        encoding="utf-8")
    size = 16
    def launch(index):
        return subprocess.run([sys.executable, "-B", str(worker), str(Path(helper.__file__)),
                               str(log), str(cwd), str(payload), str(release), str(index)],
                              capture_output=True, encoding="utf-8", timeout=30)
    with ThreadPoolExecutor(max_workers=size) as pool:
        futures = [pool.submit(launch, index) for index in range(size)]
        deadline = time.monotonic() + 15
        while not all((cwd / f"ready-{index}").is_file() for index in range(size)):
            assert time.monotonic() < deadline, "all actual subprocesses must reach the recording barrier"
            time.sleep(.005)
        release.write_bytes(b"release")
        results = [future.result() for future in futures]
    assert all(result.returncode == 0 for result in results), [result.stderr for result in results]
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == size
    assert {row["session"] for row in rows} == {f"synthetic-session-{index}" for index in range(size)}
    for row in rows:
        index = int(row["session"].rsplit("-", 1)[1])
        marker = f"工作-{index}"
        expected = [sys.executable, str(payload), marker, str(index % 3)]
        assert row["command"] == row["argv"] == expected
        assert Path(row["cwd"]) == cwd
        assert row["phase"] == "concurrent-recording"
        assert row["exit"] == index % 3
        assert row["stdout"] == marker + "\n" + "完整輸出" * 12500 + "\n"
        assert row["stderr"] == marker + "\n" + "真實錯誤" * 2500 + "\n"


def test_record_append_preserves_existing_unparseable_history_bytes(tmp_path):
    helper = runtime()
    log = tmp_path / "prior broken history.jsonl"
    original = b'{"phase":"old","partial":"\xe5\x8e\x9f\xe5\xa7\x8b"}\nnot-json-tail\n'
    log.write_bytes(original)
    event = helper.record_command([sys.executable, "-c", "print('新的實際結果')"], cwd=tmp_path,
                                  log=log, phase="new-recording", session="synthetic-current-session")
    actual = log.read_bytes()
    assert actual[:len(original)] == original
    assert json.loads(actual[len(original):].decode("utf-8")) == event
    assert event["exit"] == 0 and event["stdout"] == "新的實際結果\n"
    with pytest.raises(json.JSONDecodeError):
        [json.loads(line) for line in actual.decode("utf-8").splitlines()]


def test_codex_completed_event_is_counted_once_with_actual_result(tmp_path):
    helper = runtime()
    path = tmp_path / "actual-shape.jsonl"
    _jsonl(path, [
        {"type": "thread.started", "thread_id": "real-thread"},
        {"type": "turn.started"},
        {"type": "item.started", "item": {"id": "item_1", "type": "command_execution",
         "command": "artispec check --json", "aggregated_output": "", "exit_code": None, "status": "in_progress"}},
        {"type": "item.updated", "item": {"id": "item_1", "type": "command_execution",
         "command": "artispec check --json", "aggregated_output": "partial", "exit_code": None, "status": "in_progress"}},
        {"type": "item.completed", "item": {"id": "item_1", "type": "command_execution",
         "command": "artispec check --json", "aggregated_output": "真實輸出", "exit_code": 1, "status": "completed"}},
        {"type": "item.completed", "item": {"id": "item_1", "type": "command_execution",
         "command": "artispec check --json", "aggregated_output": "真實輸出", "exit_code": 1, "status": "completed"}},
        {"type": "item.completed", "item": {"id": "item_2", "type": "agent_message", "text": "self-report"}},
        {"type": "turn.completed", "usage": {"input_tokens": 12, "output_tokens": 8}},
    ])
    result = helper.parse_codex_events(path)
    assert result["acquisition"] == "complete"
    assert result["session"] == "real-thread"
    assert result["events"] == [{"id": "item_1", "command": "artispec check --json",
                                  "status": "completed", "exit": 1, "stdout": "真實輸出"}]


@pytest.mark.parametrize("state", ["missing", "unfinished", "malformed", "unknown"])
def test_codex_unavailable_or_unfinished_history_cannot_be_claimed_complete(tmp_path, state):
    helper = runtime()
    path = tmp_path / "history.jsonl"
    if state == "unfinished":
        _jsonl(path, [{"type": "thread.started", "thread_id": "unfinished-thread"},
                     {"type": "item.started", "item": {"id": "i", "type": "command_execution",
                      "command": "echo pending", "status": "in_progress"}}])
    elif state == "malformed":
        path.write_text('{"type":"thread.started","thread_id":"s"}\nnot-json\n', encoding="utf-8")
    elif state == "unknown":
        _jsonl(path, [{"type": "unrecognized.shell-format", "message": "I ran 100 queries"}])
    result = helper.parse_codex_events(path)
    assert result["acquisition"] == ("missing" if state == "missing" else "incomplete")
    assert result["diagnostics"]
    assert result["events"] == []


def test_codex_mixed_unknown_envelope_prevents_complete_without_losing_actual_commands(tmp_path):
    helper = runtime()
    path = tmp_path / "mixed-shape.jsonl"
    _jsonl(path, [
        {"type": "thread.started", "thread_id": "real-thread"},
        {"type": "turn.started"},
        {"type": "item.completed", "item": {"id": "item_1", "type": "command_execution",
         "command": "artispec handover", "aggregated_output": "Actual source", "exit_code": 0, "status": "completed"}},
        {"type": "future.unsupported-shell-envelope", "message": "Unknown shell evidence"},
        {"type": "turn.completed"},
    ])
    result = helper.parse_codex_events(path)
    assert result["acquisition"] == "incomplete"
    assert result["session"] == "real-thread"
    assert len(result["events"]) == 1
    assert result["events"][0]["command"] == "artispec handover"
    assert any("unknown" in reason.lower() or "unsupported" in reason.lower() for reason in result["diagnostics"])


def test_resolve_actual_relative_absolute_and_declared_external_mapping(tmp_path):
    helper = runtime()
    root = tmp_path / "案例"
    path = root / "docs" / "teacher_latest.md"
    path.parent.mkdir(parents=True)
    path.write_text("內容", encoding="utf-8")
    expected = path.resolve()
    assert helper.resolve_source("docs/teacher_latest.md L4", case_root=root) == expected
    assert helper.resolve_source(str(path) + " L4", case_root=root) == expected
    assert helper.resolve_source("teacher_latest.md:4", case_root=root, cwd=path.parent) == expected
    assert helper.resolve_source("/home/synthetic/case/docs/teacher_latest.md L4", case_root=root,
                                  mappings={"/home/synthetic/case": root}) == expected


@pytest.mark.parametrize("location", ["../outside.md", "missing.md", "teacher_latest.md L4"])
def test_resolve_refuses_escape_missing_or_undeclared_basename_search(tmp_path, location):
    helper = runtime()
    root = tmp_path / "case"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "teacher_latest.md").write_text("real", encoding="utf-8")
    (tmp_path / "outside.md").write_text("outside", encoding="utf-8")
    with pytest.raises(helper.ValidationError):
        helper.resolve_source(location, case_root=root)


def test_resolve_ambiguous_declared_root_and_cwd_is_rejected(tmp_path):
    helper = runtime()
    root = tmp_path / "case"
    cwd = root / "docs"
    cwd.mkdir(parents=True)
    (root / "same.md").write_text("root", encoding="utf-8")
    (cwd / "same.md").write_text("cwd", encoding="utf-8")
    with pytest.raises(helper.ValidationError):
        helper.resolve_source("same.md", case_root=root, cwd=cwd)


def test_manifest_hashes_all_files_and_classifies_without_dropping_overlap(tmp_path):
    helper = runtime()
    contents = {
        "docspec/changes/archive/c/tests/test_old.py": b"sealed old test\n",
        "docspec/changes/_archive/d/manifest.yaml": b"sealed change\n",
        "docspec/changes/_versions/manual-1.0.md": b"frozen document\n",
        "docspec/software/changes/_archive/e/baseline.yaml": b"legacy sealed change\n",
        "docspec/corpus/a/history.yaml": b"entries: []\n",
        "docspec/governance/journal-current.yaml": b"entries: []\n",
        "tests/test_feature.py": b"def test_feature(): pass\n",
        "docs/manual_latest.md": "教師說明\n".encode(),
        "test-handover-next.md": b"projected\n",
        "main.py": b"print('app')\n",
    }
    for name, value in contents.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
    manifest = helper.build_manifest(tmp_path)
    assert manifest["version"] == 1
    assert manifest["files"] == {name: hashlib.sha256(value).hexdigest() for name, value in contents.items()}
    assert manifest["categories"] == {
        "immutable_snapshot": ["docspec/changes/_archive/d/manifest.yaml",
                               "docspec/changes/_versions/manual-1.0.md",
                               "docspec/changes/archive/c/tests/test_old.py",
                               "docspec/software/changes/_archive/e/baseline.yaml"],
        "append_history": ["docspec/corpus/a/history.yaml", "docspec/governance/journal-current.yaml"],
        "test_source": ["tests/test_feature.py"],
        "public_projection": ["docs/manual_latest.md", "test-handover-next.md"],
        "other": ["main.py"],
    }


@pytest.mark.parametrize("relative, category", [
    ("docspec/changes/_versions/teacher/history.md", "append_history"),
    ("docspec/changes/_archive/c/docspec/changes/_versions/teacher/history.md", "immutable_snapshot"),
    ("app/tests/test_seats.py", "test_source"),
    ("planning/test-handoff.md", "public_projection"),
])
def test_manifest_classifies_actual_workflow_layout_with_snapshot_precedence(tmp_path, relative, category):
    helper = runtime()
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_bytes(b"real workflow fixture\n")
    manifest = helper.build_manifest(tmp_path)
    assert manifest["files"] == {relative: hashlib.sha256(path.read_bytes()).hexdigest()}
    assert manifest["categories"][category] == [relative]
    assert sum(relative in entries for entries in manifest["categories"].values()) == 1


def test_checkpoint_complete_copy_and_old_destination_is_preserved(tmp_path):
    helper = runtime()
    source = tmp_path / "source"
    source.mkdir()
    (source / "file.md").write_text("ready", encoding="utf-8")
    expected = helper.build_manifest(source)
    before = _snapshot(source)
    dest = tmp_path / "complete"
    manifest_path = tmp_path / "complete-manifest.json"
    helper.checkpoint_artifacts(source, dest, expected_manifest=expected, manifest_path=manifest_path)
    assert helper.build_manifest(dest) == expected
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == expected
    assert _snapshot(source) == before
    old = _snapshot(dest)
    with pytest.raises(helper.ValidationError):
        helper.checkpoint_artifacts(source, dest, expected_manifest=expected)
    assert _snapshot(dest) == old


@pytest.mark.parametrize("mutation", ["modify", "delete", "add"])
def test_checkpoint_rejects_source_changed_since_finalized_manifest(tmp_path, mutation):
    helper = runtime()
    source = tmp_path / "source"
    source.mkdir()
    file = source / "file.md"
    file.write_text("final", encoding="utf-8")
    expected = helper.build_manifest(source)
    if mutation == "modify":
        file.write_text("later", encoding="utf-8")
    elif mutation == "delete":
        file.unlink()
    else:
        (source / "extra.md").write_text("extra", encoding="utf-8")
    dest = tmp_path / "checkpoint"
    with pytest.raises(helper.ValidationError):
        helper.checkpoint_artifacts(source, dest, expected_manifest=expected)
    assert not dest.exists()


@pytest.mark.parametrize("mutation", ["modify", "delete", "add", "destination-extra"])
def test_checkpoint_rejects_actual_change_during_copy_and_removes_only_new_incomplete_package(
        tmp_path, monkeypatch, mutation):
    helper = runtime()
    source = tmp_path / "source"
    source.mkdir()
    file = source / "file.md"
    file.write_text("final", encoding="utf-8")
    expected = helper.build_manifest(source)
    prior = tmp_path / "prior-complete"
    prior.mkdir()
    (prior / "old.md").write_bytes(b"old evidence")
    prior_bytes = _snapshot(prior)
    copytree = shutil.copytree
    def interrupted_copy(src, dst, *args, **kwargs):
        value = copytree(src, dst, *args, **kwargs)
        if mutation == "modify":
            file.write_text("still being edited", encoding="utf-8")
        elif mutation == "delete":
            file.unlink()
        elif mutation == "add":
            (source / "late.md").write_text("new file", encoding="utf-8")
        else:
            (Path(dst) / "extra.md").write_text("unexpected copied file", encoding="utf-8")
        return value
    monkeypatch.setattr(shutil, "copytree", interrupted_copy)
    dest = tmp_path / "new-incomplete"
    with pytest.raises(helper.ValidationError):
        helper.checkpoint_artifacts(source, dest, expected_manifest=expected)
    assert not dest.exists()
    assert source.is_dir()
    assert _snapshot(prior) == prior_bytes


def test_wait_uses_real_condition_and_returns_truthy_value():
    helper = runtime()
    calls = []
    def predicate():
        calls.append(1)
        return {"control": "ready"} if len(calls) == 3 else None
    assert helper.wait_for_condition(predicate, timeout=1, interval=0.001) == {"control": "ready"}
    assert len(calls) == 3


def test_wait_timeout_is_a_failure_instead_of_timing_based_success():
    helper = runtime()
    with pytest.raises(helper.ValidationError):
        helper.wait_for_condition(lambda: False, timeout=0.005, interval=0.001)
