"""Evaluator launcher acceptance using real, bounded Python subprocess stubs.

These stubs are explicitly synthetic. They test subprocess/session recording and
must never be counted as fresh-agent workflow validation.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest


RUNNER = Path(__file__).resolve().parents[1] / "scripts/validation/run_workflow_participant.py"
THREAD = "00000000-0000-0000-0000-000000000123"
OTHER_THREAD = "00000000-0000-0000-0000-000000000456"
PROMPT = "請接手這份合成操作文件，先查現況。\n"

# It receives Codex-shaped arguments and emits Codex-shaped JSONL; it is a Python
# test double, not a tool-provider identity or a working agent.
STUB = r'''
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
settings = json.loads(Path(os.environ["PARTICIPANT_TEST_SETTINGS"]).read_text(encoding="utf-8"))
prompt = sys.stdin.read()
output = Path(sys.argv[sys.argv.index("-o") + 1])
facts = {"argv": sys.argv[1:], "cwd": os.getcwd(), "prompt": prompt,
         "actor_markers": {name: os.environ.get(name) for name in
            ("CODEX_THREAD_ID", "CODEX_SESSION_ID", "DOCSPEC_ACTOR_ID", "DOCSPEC_AGENT", "PYTHONPATH")}}
(output.parent / "stub-invocation.json").write_text(json.dumps(facts, ensure_ascii=False), encoding="utf-8")
for event in settings["events"]:
    print(json.dumps(event, ensure_ascii=False), flush=True)
print("合成執行器診斷。", file=sys.stderr, flush=True)
if settings.get("writer"):
    child = subprocess.Popen([sys.executable, settings["writer"], settings["late_marker"]],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    (output.parent / "stub-descendant.json").write_text(json.dumps({"pid": child.pid}), encoding="utf-8")
if settings.get("sleep"):
    time.sleep(settings["sleep"])
output.write_text("這是合成測試回覆，並非真實 agent 驗收。\n", encoding="utf-8")
sys.exit(settings.get("exit", 0))
'''


@pytest.fixture
def case(tmp_path):
    run = tmp_path / "驗證 artifacts"
    project = run / "project 空白"
    project.mkdir(parents=True)
    (project / "managed.txt").write_text("Synthetic managed content.\n", encoding="utf-8")
    manifest = {"project": str(project), "platform": "windows" if os.name == "nt" else "linux",
                "participant_launches": [], "agent_workflow_executed": False, "preparation_only": True}
    (run / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    prompt = run / "合成任務.txt"
    prompt.write_text(PROMPT, encoding="utf-8")
    stub = tmp_path / "synthetic codex stub.py"
    stub.write_text(STUB, encoding="utf-8")
    return {"run": run, "project": project, "prompt": prompt, "stub": stub, "tmp": tmp_path}


def _started(thread=THREAD):
    return {"type": "thread.started", "thread_id": thread}


def _launch(case, events, *, phase="preflight", thread=None, timeout=10, child_exit=0,
            child_sleep=0, node=None, writer=None):
    settings = case["tmp"] / (phase + "-stub-settings.json")
    body = {"events": events, "exit": child_exit, "sleep": child_sleep}
    if writer is not None:
        body.update(writer=str(writer), late_marker=str(case["project"] / "late-write.txt"))
    settings.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    env = dict(os.environ, PARTICIPANT_TEST_SETTINGS=str(settings), PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    # Parent markers must not be passed to a fresh child as the child's identity.
    env.update(CODEX_THREAD_ID="synthetic-parent", CODEX_SESSION_ID="synthetic-parent", DOCSPEC_ACTOR_ID="synthetic-parent",
               DOCSPEC_AGENT="synthetic-parent", PYTHONPATH="synthetic-parent-path")
    argv = [sys.executable, str(RUNNER), "--run", str(case["run"]), "--phase", phase,
            "--prompt", str(case["prompt"]), "--node", str(node or sys.executable),
            "--codex", str(case["stub"]), "--timeout", str(timeout)]
    if thread is not None:
        argv.extend(["--thread", thread])
    result = subprocess.run(argv, env=env, capture_output=True, encoding="utf-8", errors="strict", timeout=20)
    folder = case["run"] / "participants" / phase
    recorded = json.loads((folder / "result.json").read_text(encoding="utf-8")) if (folder / "result.json").is_file() else None
    return result, folder, recorded


def _manifest(case):
    return json.loads((case["run"] / "manifest.json").read_text(encoding="utf-8"))


def test_plain_preflight_requires_a_real_session_and_accepts_no_shell_commands(case):
    result, folder, recorded = _launch(case, [_started(), {"type": "turn.completed", "usage": {}}])
    assert result.returncode == 0, result.stderr
    assert recorded["exit"] == 0 and recorded["actual_session"] == THREAD
    assert recorded["shell_events"] == 0
    assert _manifest(case)["agent_workflow_executed"] is True
    assert _manifest(case)["preparation_only"] is False
    invocation = json.loads((folder / "stub-invocation.json").read_text(encoding="utf-8"))
    assert invocation["prompt"] == PROMPT
    assert all(value is None for value in invocation["actor_markers"].values())
    assert Path(invocation["cwd"]).resolve() == case["project"].resolve()
    launch = json.loads((folder / "launch.json").read_text(encoding="utf-8"))
    assert launch["prompt_sha256"] == hashlib.sha256(PROMPT.encode("utf-8")).hexdigest()
    assert launch["fresh"] is True and launch["resume_thread"] is None
    assert (folder / "answer.txt").read_text(encoding="utf-8").startswith("這是合成測試回覆")
    assert (case["project"] / "managed.txt").read_text(encoding="utf-8") == "Synthetic managed content.\n"


def test_completed_command_logs_are_raw_utf8_and_counted_once(case):
    command = {"id": "item_0", "type": "command_execution", "command": "artispec handover",
               "aggregated_output": "交接單尚未建立。", "exit_code": 0}
    events = [_started(), {"type": "item.started", "item": dict(command, exit_code=None)},
              {"type": "item.completed", "item": command}, {"type": "turn.completed", "usage": {}}]
    result, folder, recorded = _launch(case, events)
    assert result.returncode == 0 and recorded["shell_events"] == 1
    actual_lines = (folder / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert actual_lines == [json.dumps(row, ensure_ascii=False) for row in events]
    assert "合成執行器診斷。" in (folder / "stderr.txt").read_text(encoding="utf-8")
    assert recorded["shell_acquisition"] == "complete"


def test_resumed_preflight_checks_the_actual_returned_session(case):
    events = [_started(), {"type": "turn.completed", "usage": {}}]
    result, folder, recorded = _launch(case, events, thread=THREAD)
    assert result.returncode == 0 and recorded["actual_session"] == THREAD
    invocation = json.loads((folder / "stub-invocation.json").read_text(encoding="utf-8"))
    assert invocation["argv"][invocation["argv"].index("resume") + 1] == THREAD
    assert json.loads((folder / "launch.json").read_text(encoding="utf-8"))["fresh"] is False


def test_wrong_resume_session_is_not_counted_as_success(case):
    result, folder, recorded = _launch(case, [_started(OTHER_THREAD), {"type": "turn.completed"}], thread=THREAD)
    assert result.returncode != 0 and recorded["exit"] != 0
    assert recorded["actual_session"] == OTHER_THREAD
    explanation = json.dumps(recorded, ensure_ascii=False)
    assert THREAD in explanation and OTHER_THREAD in explanation
    assert json.loads((folder / "events.jsonl").read_text(encoding="utf-8").splitlines()[0])["thread_id"] == OTHER_THREAD


@pytest.mark.parametrize("events", [[], [{"type": "turn.completed"}],
                                     [_started(), _started(OTHER_THREAD), {"type": "turn.completed"}]])
def test_zero_child_exit_without_unique_actual_identity_is_not_success(case, events):
    result, folder, recorded = _launch(case, events)
    assert result.returncode != 0 and recorded["exit"] != 0
    assert recorded["actual_session"] is None
    assert _manifest(case)["agent_workflow_executed"] is False
    assert _manifest(case)["preparation_only"] is True
    assert (folder / "events.jsonl").is_file()


@pytest.mark.parametrize("events", [[_started()], [_started(), {"type": "turn.failed", "error": {"message": "synthetic failure"}}]])
def test_zero_child_exit_without_successful_turn_does_not_establish_completion(case, events):
    result, folder, recorded = _launch(case, events)
    assert result.returncode != 0 and recorded["exit"] != 0
    assert recorded["actual_session"] == THREAD
    assert _manifest(case)["agent_workflow_executed"] is True
    assert (folder / "events.jsonl").read_text(encoding="utf-8").splitlines()


def test_launcher_failure_retains_attempt_records_without_claiming_agent_execution(case):
    result, folder, recorded = _launch(case, [], node=case["tmp"] / "missing-executable")
    assert result.returncode == recorded["exit"] == 127
    assert recorded["launch_error"] and recorded["actual_session"] is None
    assert (folder / "launch.json").is_file() and (folder / "events.jsonl").read_bytes() == b""
    assert _manifest(case)["agent_workflow_executed"] is False
    assert _manifest(case)["preparation_only"] is True


def test_child_nonzero_exit_is_preserved_even_if_jsonl_has_a_completed_turn(case):
    result, folder, recorded = _launch(case, [_started(), {"type": "turn.completed"}], child_exit=7)
    assert result.returncode == recorded["exit"] == 7
    assert recorded["actual_session"] == THREAD
    assert (folder / "events.jsonl").read_text(encoding="utf-8").splitlines()


def test_timeout_keeps_raw_events_and_the_original_timeout_reason(case):
    result, folder, recorded = _launch(case, [_started(OTHER_THREAD)], thread=THREAD, timeout=1, child_sleep=3)
    assert result.returncode == recorded["exit"] == 124
    assert recorded["actual_session"] == OTHER_THREAD
    assert "timeout" in json.dumps(recorded, ensure_ascii=False).lower()
    assert json.loads((folder / "events.jsonl").read_text(encoding="utf-8").splitlines()[0])["thread_id"] == OTHER_THREAD


def test_timeout_stops_descendant_writers_before_the_runner_returns(case):
    writer = case["tmp"] / "bounded-synthetic-writer.py"
    writer.write_text("from pathlib import Path\nimport sys,time\ntime.sleep(4)\nPath(sys.argv[1]).write_text('late synthetic write', encoding='utf-8')\n", encoding="utf-8")
    result, folder, recorded = _launch(case, [_started()], timeout=2, child_sleep=6, writer=writer)
    assert result.returncode == recorded["exit"] == 124
    assert (folder / "stub-descendant.json").is_file(), "The test must actually launch a bounded descendant"
    marker = case["project"] / "late-write.txt"
    deadline = time.monotonic() + 4.5
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not marker.exists(), "A child writer survived timeout and changed the checkpoint source"


def test_existing_phase_is_not_overwritten_or_added_to_the_manifest_again(case):
    result, folder, recorded = _launch(case, [_started(), {"type": "turn.completed"}])
    assert result.returncode == 0
    before = {path.name: path.read_bytes() for path in folder.iterdir() if path.is_file()}
    manifest_before = (case["run"] / "manifest.json").read_bytes()
    repeated, same_folder, recorded = _launch(case, [_started(OTHER_THREAD), {"type": "turn.completed"}])
    assert repeated.returncode != 0 and same_folder == folder
    assert {path.name: path.read_bytes() for path in folder.iterdir() if path.is_file()} == before
    assert (case["run"] / "manifest.json").read_bytes() == manifest_before
