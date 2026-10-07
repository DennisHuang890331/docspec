"""Exercise the installed CLI with synthetic session ids, not fresh participants."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    cli, python = args.cli.absolute(), args.python.absolute()
    for path in (cli, python, args.wheel):
        if not path.is_file():
            parser.error(f"missing input: {path}")
    run = args.output_dir.absolute() / ("run-" + uuid.uuid4().hex)
    project = run / "project"
    project.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ)
    for key in ("PYTHONPATH", "CODEX_THREAD_ID", "DOCSPEC_ACTOR_ID"):
        env.pop(key, None)
    env.update({"PYTHONUTF8": "1", "DOCSPEC_AGENT": "gpt",
                "PATH": str(cli.parent) + os.pathsep + env.get("PATH", "")})
    calls = []
    checks = 0

    def check(condition: bool, reason: str) -> None:
        nonlocal checks
        assert condition, reason
        checks += 1

    def call(*argv: str, actor: str = "synthetic-test-A", expected: int = 0) -> str:
        current_env = dict(env, DOCSPEC_ACTOR_ID=actor)
        result = subprocess.run([str(cli), *argv], cwd=project, env=current_env,
                                capture_output=True, encoding="utf-8", errors="strict", timeout=120)
        calls.append({"time": datetime.now(timezone.utc).isoformat(), "command": [str(cli), *argv],
                      "actor": actor, "exit": result.returncode, "stdout": result.stdout,
                      "stderr": result.stderr, "source_entrypoint": False})
        (run / "commands.json").write_text(json.dumps(calls, indent=2, ensure_ascii=False), encoding="utf-8")
        check(result.returncode == expected, json.dumps(calls[-1], ensure_ascii=False))
        return result.stdout

    def managed_bytes() -> dict:
        return {p.relative_to(project).as_posix(): p.read_bytes()
                for p in (project / "docspec").rglob("*") if p.is_file()}

    try:
        call("init", "--agents-md", "--tool", "codex", "--lang", "en")
        app = project / "app"
        (app / "tests").mkdir(parents=True)
        (app / "value.py").write_text("VALUE = 2\n", encoding="utf-8")
        test_file = app / "tests/test_value.py"
        test_file.write_text("from value import VALUE\n\ndef test_value():\n    assert VALUE == 2\n", encoding="utf-8")
        call("code", "repo", "add", "app", "app", "--test-command", f'"{python}" -m pytest -q')
        call("code", "change", "new", "actor-check", "--why", "Synthetic instance mechanics", "--new", "value")
        call("code", "change", "delta", "actor-check", "--capability", "value", "--op", "add-requirement",
             "--title", "Value", "--statement", "Value SHALL be 2.", "--verification", "test",
             "--scenario", "Value | The value is read | It equals 2", "--purpose", "Synthetic value acceptance")
        call("code", "testplan", "add", "actor-check", "--location", "app:tests/test_value.py::test_value",
             "--covers", "value/R1/S1")
        call("code", "task", "add", "actor-check", "--title", "Provide value", "--implements", "value/R1",
             "--files", "app:value.py", "--verify", "test", "--tests", "T1", actor="synthetic-implementation-B")
        before = managed_bytes()
        for argv in (("sign", "actor-check", "T1"), ("set", "actor-check", "T1", "--note", "wrong author"),
                     ("remove", "actor-check", "T1")):
            call("code", "testplan", *argv, actor="synthetic-implementation-B", expected=1)
            check(managed_bytes() == before, "rejected author operation wrote managed files")
        call("code", "testplan", "sign", "actor-check", "T1")
        plan = json.loads(call("code", "testplan", "list", "actor-check", "--json"))
        check(plan["tests"][0]["written-by-instance"] == "synthetic-test-A", "test author instance missing")
        check(plan["tests"][0]["signed"]["by-instance"] == "synthetic-test-A", "signer instance missing")
        check(plan["signoffs"][0]["status"] == "current", "distinct sessions did not retain current signoff")
        call("code", "testplan", "object", "actor-check", "T1", "--reason", "Synthetic question", actor="synthetic-implementation-B")
        before = managed_bytes()
        for actor in ("synthetic-implementation-B", "synthetic-unrelated-C"):
            call("code", "testplan", "respond", "actor-check", "O1", "--resolution", "rejected",
                 "--reason", "Wrong responder", actor=actor, expected=1)
            check(managed_bytes() == before, "rejected response wrote managed files")
        call("code", "testplan", "respond", "actor-check", "O1", "--resolution", "rejected", "--reason", "Original scenario is correct")
        call("code", "evidence", "run", "actor-check", "1", actor="synthetic-implementation-B")
        tasks = json.loads(call("code", "task", "list", "actor-check", "--json"))
        check(tasks[0]["created-by-instance"] == "synthetic-implementation-B", "task instance missing")
        check(tasks[0]["status"] == "done", "installed engine did not obtain passing evidence")
        test_file.write_text(test_file.read_text(encoding="utf-8").replace("== 2", "== 3"), encoding="utf-8")
        plan = json.loads(call("code", "testplan", "list", "actor-check", "--json"))
        check(plan["signoffs"][0]["status"] == "needs-review", "test edits did not invalidate signoff")
        test_file.write_text(test_file.read_text(encoding="utf-8").replace("== 3", "== 2"), encoding="utf-8")
        # Registering implementation after signing must not bypass separation.
        call("code", "task", "add", "actor-check", "--title", "Same-session implementation", "--implements", "value/R1",
             "--files", "app:value.py", "--verify", "test", "--tests", "T1")
        plan = json.loads(call("code", "testplan", "list", "actor-check", "--json"))
        check(plan["signoffs"][0]["status"] == "needs-review", "sign-first/add-task-later bypass succeeded")
        before = managed_bytes()
        call("code", "testplan", "sign", "actor-check", "T1", expected=1)
        check(managed_bytes() == before, "same-session rejected signoff wrote managed files")
        summary = {"passed": True, "checks": checks, "commands": len(calls), "run": str(run),
                   "runtime": os.name, "synthetic_instance_ids": True, "fresh_agent_workflow": False,
                   "wheel_sha256": hashlib.sha256(args.wheel.read_bytes()).hexdigest()}
    except Exception as exc:
        summary = {"passed": False, "checks": checks, "commands": len(calls), "run": str(run), "error": str(exc)}
        (run / "result.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        raise
    (run / "result.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
