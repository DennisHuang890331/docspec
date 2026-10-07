"""Validate installed entry points and hook upgrades in disposable environments.

Run with a native Windows/Linux Python, never import the repository's dspx.
All fixtures are synthetic and every subprocess result is saved outside them.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback


class Validation:
    def __init__(self, root: Path):
        self.root = root
        self.report = {
            "schema-version": 1,
            "platform": sys.platform,
            "python": sys.version,
            "started-at": datetime.now(timezone.utc).isoformat(),
            "commands": [],
            "checks": [],
            "mechanical-status": "running",
        }
        root.mkdir(parents=True, exist_ok=False)
        self.save()

    def save(self):
        (self.root / "package-retirement.json").write_text(
            json.dumps(self.report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def check(self, name, condition, details=None):
        self.report["checks"].append({"name": name, "passed": bool(condition), "details": details})
        self.save()
        if not condition:
            raise AssertionError(name)

    def run(self, argv, *, cwd=None, env=None, stdin=None, expected=0, shell=False):
        started = datetime.now(timezone.utc)
        record = {
            "argv": argv if isinstance(argv, str) else [str(a) for a in argv],
            "shell": shell,
            "cwd": str(cwd) if cwd else None,
            "stdin": stdin,
            "started-at": started.isoformat(),
        }
        try:
            result = subprocess.run(
                argv, cwd=cwd, env=env, input=stdin, capture_output=True, text=True,
                encoding="utf-8", errors="replace", shell=shell, timeout=240)
        except (OSError, subprocess.TimeoutExpired) as exc:
            record.update({"exit-code": None, "stdout": "", "stderr": str(exc), "execution-error": type(exc).__name__})
            self.report["commands"].append(record)
            self.save()
            raise
        record.update({"exit-code": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
        self.report["commands"].append(record)
        self.save()
        if expected is not None and result.returncode != expected:
            raise RuntimeError(f"Expected exit {expected}, got {result.returncode}: {argv}")
        return result


def clean_env(binary_dir: Path | None = None):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    if binary_dir is not None:
        env["PATH"] = str(binary_dir) + os.pathsep + env.get("PATH", "")
    return env


def files_for_environment(root: Path):
    scripts = root / ("Scripts" if os.name == "nt" else "bin")
    python = scripts / ("python.exe" if os.name == "nt" else "python")
    command = scripts / ("artispec.exe" if os.name == "nt" else "artispec")
    return scripts, python, command


def install(v: Validation, environment: Path, wheel: Path):
    scripts, python, _ = files_for_environment(environment)
    env = clean_env(scripts)
    uv = shutil.which("uv")
    if uv:
        argv = [uv, "pip", "install", "--python", str(python), "--force-reinstall", str(wheel)]
    else:
        # The Linux controller already has recent pip; the target needs no pip
        # or distribution ensurepip package (and no system packages are changed).
        argv = [sys.executable, "-m", "pip", "--python", str(python), "install", "--force-reinstall", str(wheel)]
    v.run(argv, env=env, cwd=v.root)


def metadata(v: Validation, environment: Path):
    scripts, python, _ = files_for_environment(environment)
    code = (
        "import importlib.metadata,json;d=importlib.metadata.distribution('docspec');"
        "print(json.dumps({'name':d.metadata['Name'],'version':d.version,"
        "'entry-points':{e.name:e.value for e in d.entry_points if e.group=='console_scripts'}}))"
    )
    return json.loads(v.run([str(python), "-c", code], env=clean_env(scripts), cwd=v.root).stdout)


def seed_project(root: Path):
    root.mkdir(parents=True)
    owner = "# Owner policy\nKeep synthetic data and other tools' hooks unchanged.\n"
    (root / "AGENTS.md").write_text(owner, encoding="utf-8")
    for relative, event in (
        (".claude/settings.json", "PreToolUse"),
        (".codex/hooks.json", "PreToolUse"),
        (".gemini/settings.json", "BeforeTool"),
    ):
        path = root / relative
        path.parent.mkdir(parents=True)
        settings = {"custom-owner-setting": "preserve", "hooks": {event: [{
            "matcher": "Read", "hooks": [{"type": "command", "command": "other-tool hook guard"}],
        }]}}
        path.write_text(json.dumps(settings), encoding="utf-8")
    return owner


def managed_snapshot(project: Path):
    targets = [project / "docspec", project / "docs"]
    return {
        str(path.relative_to(project)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
        for root in targets for path in sorted(root.rglob("*")) if path.is_file()
    }


def add_synthetic_records(project: Path):
    files = {
        "docspec/corpus/upgrade-sentinel.yaml": b"synthetic: true\nowner: keep\n",
        "docspec/governance/decisions/D-synthetic-1.yaml": b"synthetic: preserved sealed bytes\n",
        "docs/archive/synthetic_v1.md": b"Historical command: `docspec show synthetic`.\n",
        "docs/guide/_latest.md": b"Synthetic document staging.\n",
    }
    for relative, body in files.items():
        path = project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    config = project / "docspec/config.yaml"
    with config.open("ab") as stream:
        stream.write(b"\n# Synthetic owner configuration, retained during re-init.\n")


def add_post_init_foreign_hooks(project: Path):
    """Simulate another tool installed after the baseline project's initial init.

    The old generator incorrectly claims generic 'hook guard' strings, so a
    foreign hook must be added after that generation to test the new upgrader.
    """
    for relative, event in (
        (".claude/settings.json", "PreToolUse"),
        (".codex/hooks.json", "PreToolUse"),
        (".gemini/settings.json", "BeforeTool"),
    ):
        path = project / relative
        settings = json.loads(path.read_text(encoding="utf-8"))
        commands = [h.get("command") for e in settings["hooks"][event] for h in e["hooks"]]
        if "other-tool hook guard" not in commands:
            settings["hooks"][event].append({
                "matcher": "Read", "hooks": [{"type": "command", "command": "other-tool hook guard"}],
            })
        path.write_text(json.dumps(settings), encoding="utf-8")


def validate_project(v: Validation, project: Path, environment: Path, owner: str, expected_data):
    scripts, _, command = files_for_environment(environment)
    env = clean_env(scripts)
    for _ in range(2):
        v.run([str(command), "init", "--tool", "all", "--agents-md", "--no-update-check", "--no-tex-hint"],
              cwd=project, env=env)
    actual_data = managed_snapshot(project)
    v.check(f"{project.name}: managed bytes unchanged", actual_data == expected_data,
            {"before": expected_data, "after": actual_data})
    agents = (project / "AGENTS.md").read_text(encoding="utf-8")
    v.check(f"{project.name}: owner rules retained", agents.startswith(owner))
    v.check(f"{project.name}: single managed block", agents.count("<!-- docspec:begin -->") == 1)
    for relative, event, post_event in (
        (".claude/settings.json", "PreToolUse", "PostToolUse"),
        (".codex/hooks.json", "PreToolUse", "PostToolUse"),
        (".gemini/settings.json", "BeforeTool", None),
    ):
        settings = json.loads((project / relative).read_text(encoding="utf-8"))
        v.check(f"{project.name}: {relative} custom setting retained", settings["custom-owner-setting"] == "preserve")
        commands = [h.get("command") for e in settings["hooks"][event] for h in e["hooks"]]
        v.check(f"{project.name}: {relative} foreign guard retained", commands.count("other-tool hook guard") == 1)
        owned = [c for c in commands if c and c.endswith(" hook guard") and c != "other-tool hook guard"]
        expected_hook = f'"{command}" hook guard'
        v.check(f"{project.name}: {relative} only new absolute guard",
                [os.path.normcase(c) for c in owned] == [os.path.normcase(expected_hook)], commands)
        if post_event:
            post = [h["command"] for e in settings["hooks"][post_event] for h in e["hooks"]]
            v.check(f"{project.name}: {relative} one new check",
                    [os.path.normcase(c) for c in post] == [os.path.normcase(f'"{command}" hook check')], post)
        write_tool = "write_file" if relative.startswith(".gemini") else "Write"
        read_tool = "run_shell_command" if relative.startswith(".gemini") else "Bash"
        direct_read_tool = "read_file" if relative.startswith(".gemini") else "Read"
        payloads = (
            ("sealed-write", {"tool_name": write_tool, "tool_input": {"file_path": str(project / "docs/archive/synthetic_v1.md")}}, 2),
            ("sealed-read", {"tool_name": read_tool, "tool_input": {"command": 'cat "docs/archive/synthetic_v1.md"'}}, 0),
            ("sealed-direct-read", {"tool_name": direct_read_tool, "tool_input": {"file_path": str(project / "docs/archive/synthetic_v1.md")}}, 0),
            ("staging-write", {"tool_name": write_tool, "tool_input": {"file_path": str(project / "docs/guide/_latest.md")}}, 0),
        )
        for name, payload, expected in payloads:
            result = v.run(owned[0], cwd=project, env=env, stdin=json.dumps(payload), shell=True, expected=expected)
            v.check(f"{project.name}: {relative} actual guard {name}", result.returncode == expected)
    v.check(f"{project.name}: guard queries did not modify data", managed_snapshot(project) == expected_data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--baseline-wheel", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="new directory outside the repository")
    args = parser.parse_args(argv)
    wheel, baseline = args.wheel.resolve(), args.baseline_wheel.resolve()
    output = args.output_dir.resolve()
    repo = Path(__file__).resolve().parents[2]
    if output == repo or repo in output.parents:
        parser.error("--output-dir must be outside the repository")
    v = Validation(output)
    try:
        for name, artifact in (("wheel", wheel), ("baseline-wheel", baseline)):
            v.check(f"{name} exists", artifact.is_file(), str(artifact))
            v.report[name] = {"path": str(artifact), "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest()}
        for case in ("fresh", "upgrade"):
            environment = output / f"{case} tools \u4e2d\u6587"
            v.run([sys.executable, "-m", "venv", "--without-pip", str(environment)], cwd=output, env=clean_env())
            scripts, _, command = files_for_environment(environment)
            project = output / f"{case} project \u4e2d\u6587"
            owner = seed_project(project)
            install(v, environment, baseline if case == "upgrade" else wheel)
            if case == "upgrade":
                old = metadata(v, environment)
                v.check("baseline exposes both scripts", set(old["entry-points"]) == {"artispec", "docspec"}, old)
                v.check("baseline own bin has docspec", any(scripts.glob("docspec*")))
            v.run([str(command), "init", "--tool", "all", "--agents-md", "--no-update-check", "--no-tex-hint"],
                  cwd=project, env=clean_env(scripts))
            if case == "upgrade":
                add_post_init_foreign_hooks(project)
                v.report["upgrade-fixture-preparation"] = (
                    "Foreign hooks were added after the baseline's initial generation, "
                    "before package upgrade, to model a subsequently installed tool.")
            add_synthetic_records(project)
            before = managed_snapshot(project)
            if case == "upgrade":
                install(v, environment, wheel)
            current = metadata(v, environment)
            v.check(f"{case}: installed package remains docspec", current["name"] == "docspec", current)
            v.check(f"{case}: installed metadata only artispec", current["entry-points"] == {"artispec": "dspx.cli:main"}, current)
            v.check(f"{case}: own bin has no docspec", not any(scripts.glob("docspec*")))
            v.run([str(command), "--help"], cwd=project, env=clean_env(scripts))
            validate_project(v, project, environment, owner, before)
            setup = v.run([str(command), "setup", "--no-download"], cwd=project, env=clean_env(scripts), expected=None)
            v.report.setdefault("controlled-tool-checks", {})[case] = {
                "status": "passed" if setup.returncode == 0 else "environment-failure",
                "exit-code": setup.returncode,
                "note": (
                    "Ran setup --no-download against existing controlled assets. "
                    "It may maintain tex.lock and an existing TinyTeX installation; "
                    "this is not an offline/read-only guarantee. PDF/proof validation is separate."),
            }
        v.report["mechanical-status"] = "passed"
    except Exception as exc:
        v.report["mechanical-status"] = "failed"
        v.report["failure"] = {"message": str(exc), "traceback": traceback.format_exc()}
    finally:
        v.report["finished-at"] = datetime.now(timezone.utc).isoformat()
        v.save()
    print(json.dumps({"status": v.report["mechanical-status"], "report": str(output / "package-retirement.json")}, ensure_ascii=False))
    return 0 if v.report["mechanical-status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
