"""Prepare synthetic README validation cases; evaluator material stays outside them.

Run with the newly installed wheel's Python, with PYTHONPATH unset. Both fresh
and baseline interpreters must have pytest available for fixture evidence.
Pass new-agent-task.txt verbatim to the fresh participant (also OWNER-TASK.md
inside its case); it shares a contract and hash with the evaluator facts. Save
the actual launch/delegation inputs before launching, rather than reconstructing
them afterwards. Historical run facts must never be updated to fit outcomes.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def snapshot(project: Path) -> dict:
    return {p.relative_to(project).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for name in ("docspec", "docs") for p in sorted((project / name).rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}


def new_case_contract() -> tuple[dict, str]:
    """Produce evaluator facts and participant requirements from one contract."""
    software = ("Python greet(name): strip surrounding whitespace, return Hello <name> "
                "(Ada returns Hello Ada), raise ValueError for blank names; "
                "implementation path is declared by the change, not fixed by the oracle")
    document = ("short operating instructions for the agreed greeting API; "
                "owner explicitly authorizes synthetic document freeze/PDF/proof; "
                "document identifier is chosen by the participant")
    acceptance = ["independent test authorship/signoff before implementation",
                  "engine evidence pass", "software change archived",
                  "document frozen with PDF and rendered proof", "handover reflects actual state"]
    task = ("# Synthetic owner task\n\n" + software + ".\n\n" + document + ".\n\n"
            + "Acceptance requirements:\n" + "".join(f"- {item}\n" for item in acceptance)
            + "\nUse the supplied README and installed artispec. Preserve actual identifiers. "
              "Use truthful agent identities and a separate test role; do not edit its tests. "
              "When software is blocked, eligible document work remains independent.\n")
    facts = {"synthetic": True, "document": document, "software": software,
             "acceptance": acceptance,
             "owner-task-sha256": hashlib.sha256(task.encode("utf-8")).hexdigest()}
    return facts, task


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cli", type=Path, required=True)
    parser.add_argument("--baseline-python", type=Path, required=True)
    parser.add_argument("--baseline-cli", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("PYTHONPATH"):
        parser.error("unset PYTHONPATH for installed-wheel validation")
    repo = Path(__file__).resolve().parents[2]
    run = args.output_dir.resolve() / datetime.datetime.now().strftime("run-%Y%m%d-%H%M%S-%f")
    run.mkdir(parents=True)
    facts = {}
    paths = {}
    build_logs = []
    for name, python, cli in (("stale", Path(sys.executable), args.cli),
                              ("upgrade", args.baseline_python, args.baseline_cli)):
        env = dict(os.environ)
        env["PATH"] = str(cli.parent) + os.pathsep + env.get("PATH", "")
        env["PYTHONUTF8"] = "1"
        result = subprocess.run([str(python), str(repo / "scripts/validation/build_change_navigation_cases.py"),
                                 "--output-dir", str(run / (name + "-fixtures")),
                                 "--installed-cli", str(cli)], env=env, capture_output=True,
                                encoding="utf-8", errors="strict")
        build_logs.append({"case": name, "exit": result.returncode,
                           "stdout": result.stdout, "stderr": result.stderr})
        (run / "build-commands.json").write_text(json.dumps(build_logs, ensure_ascii=False, indent=2), encoding="utf-8")
        if result.returncode:
            raise RuntimeError(result.stderr + result.stdout)
        built = json.loads(result.stdout)
        parent = Path(built["run"])
        project = Path(built["stale"] if name == "stale" else built["current"])
        paths[name] = project
        facts[name] = json.loads((parent / "facts.json").read_text(encoding="utf-8"))[name if name == "stale" else "current"]
        if name == "upgrade":
            agents = project / "AGENTS.md"
            custom = "# Owner rules\nUse synthetic data only. Preserve this text and the historical `docspec show guide` example.\n\n"
            agents.write_text(custom + agents.read_text(encoding="utf-8"), encoding="utf-8")
            settings = project / ".codex/hooks.json"
            data = json.loads(settings.read_text(encoding="utf-8"))
            data["theme"] = "synthetic-custom"
            data["permissions"] = {"allow": ["read-only-project"]}
            data["hooks"]["PreToolUse"].insert(0, {
                "matcher": "custom", "hooks": [{"type": "command", "command": "other-tool hook guard"}]})
            settings.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            custom_skill = project / ".agents/skills/owner-notes/SKILL.md"
            custom_skill.parent.mkdir(parents=True)
            custom_skill.write_text("# Owner notes\nDo not overwrite user-created skills.\n", encoding="utf-8")
            facts[name]["custom-rules"] = custom
            facts[name]["custom-settings"] = data
            facts[name]["custom-skill-sha256"] = hashlib.sha256(custom_skill.read_bytes()).hexdigest()
    project = run / "new project 文件"
    project.mkdir()
    paths["new"] = project
    facts["new"], owner_task = new_case_contract()
    (project / "OWNER-TASK.md").write_text(owner_task, encoding="utf-8")
    (run / "new-agent-task.txt").write_text(owner_task, encoding="utf-8")
    facts["before"] = {}
    configurations = {}
    for name, project in paths.items():
        shutil.copyfile(repo / "README.md", project / "README.md")
        facts["before"][name] = snapshot(project)
        if name == "new":
            binary = project / ".venv" / ("Scripts/artispec.exe" if os.name == "nt" else "bin/artispec")
        else:
            binary = args.baseline_cli if name == "upgrade" else args.cli
        config = run / (name + "-recorder.json")
        config.write_text(json.dumps({"executable": str(binary.resolve()), "project": str(project),
                                     "log": str(run / (name + "-commands.jsonl")),
                                     "environment": {"DOCSPEC_AGENT": "gpt"}}, ensure_ascii=False, indent=2), encoding="utf-8")
        configurations[name] = str(config)
    recorder = run / "record.py"
    shutil.copyfile(Path(__file__).with_name("record_installed_command.py"), recorder)
    shutil.copyfile(Path(__file__).with_name("workflow_runtime.py"), run / "workflow_runtime.py")
    facts["artifact"] = {"wheel": str(args.wheel.resolve()),
                         "sha256": hashlib.sha256(args.wheel.read_bytes()).hexdigest(),
                         "runtime": sys.platform, "python": sys.executable}
    (run / "facts.json").write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"run": str(run), "cases": {k: str(v) for k, v in paths.items()},
                      "recorder": str(recorder), "config": configurations,
                      "wheel": str(args.wheel.resolve())}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
