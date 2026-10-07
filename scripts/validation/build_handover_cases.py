"""Build synthetic Windows/Linux handover cases; this is not an agent eval run.

Run with a persistent Python environment containing pytest, pyyaml, questionary,
and platformdirs, for example:
    python scripts/validation/build_handover_cases.py --output-dir C:/Temp/e11

Do not use an ephemeral uv run interpreter: evidence runners retain its path.
Each case has a neutral run-docspec.py entrypoint, plus Windows .cmd/.ps1
or Linux .sh launchers. No PowerShell execution-policy changes are needed.

Each invocation creates a new run directory without deleting or reusing older
projects. Evaluator facts and command logs remain outside participant projects.
All owner quotes and role signoffs are SYNTHETIC fixture data, not real approvals.
The builder asserts fixture state; it does not claim a fresh agent can resume it.
"""
import argparse
import contextlib
import datetime
import hashlib
import io as buffer
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output-dir", required=True, type=Path,
                    help="parent for a new run-* directory; never overwritten")
parser.add_argument("--installed-cli", type=Path,
                    help="use this installed console script, without importing the repository source")
args = parser.parse_args()
if not __debug__:
    parser.error("run without -O so fixture assertions remain enabled")
ROOT = args.output_dir.resolve()
if "builds-v0" in Path(sys.executable).parts:
    parser.error("use a persistent Python environment, not an ephemeral uv run interpreter")
ROOT.mkdir(parents=True, exist_ok=True)
if args.installed_cli is None:
    sys.path.insert(0, str(REPO / "src"))
else:
    args.installed_cli = args.installed_cli.resolve(strict=True)
    if os.environ.get("PYTHONPATH"):
        parser.error("installed validation requires PYTHONPATH to be unset")
os.environ["PYTHONUTF8"] = "1"
os.environ["DOCSPEC_AGENT"] = "gpt"
from dspx.cli import main
from dspx.engine.layout import Layout
from dspx.engine import store, handover as ho, governance as gv
from dspx.engine.schema import load_schema
from dspx.engine.config import load_config
from dspx.engine.software import specs, evidence

stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
run_root = ROOT / ("run-" + stamp)
run_root.mkdir()  # exist_ok=False: even a timestamp collision cannot overwrite a run.
runner_path = run_root / "runner.py"
runner_path.write_text(
    "import os, sys\n"
    + f"sys.path.insert(0, {str(REPO / 'src')!r})\n"
    + "os.environ.setdefault('PYTHONUTF8', '1')\n"
    + "os.environ.setdefault('DOCSPEC_AGENT', 'gpt')\n"
    + "from dspx.cli import main\n"
    + "raise SystemExit(main(sys.argv[1:]))\n", encoding="utf-8")
if args.installed_cli is not None:
    runner_path.write_text(
        "import datetime, json, os, subprocess, sys\nfrom pathlib import Path\n"
        + f"executable = {str(args.installed_cli)!r}\n"
        + "env = dict(os.environ)\nenv.pop('PYTHONPATH', None)\nenv['PYTHONUTF8']='1'\n"
        + "env['PATH'] = str(Path(executable).parent) + os.pathsep + env.get('PATH', '')\n"
        + "cmd = [executable, *sys.argv[1:]]\n"
        + "result = subprocess.run(cmd, env=env, capture_output=True, encoding='utf-8', errors='replace')\n"
        + "row = {'time': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'cwd': str(Path.cwd()), 'command': cmd, 'exit': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}\n"
        + "with (Path(__file__).parent/'participant-commands.jsonl').open('a', encoding='utf-8') as log: log.write(json.dumps(row, ensure_ascii=False)+'\\n')\n"
        + "sys.stdout.write(result.stdout)\nsys.stderr.write(result.stderr)\nraise SystemExit(result.returncode)\n",
        encoding="utf-8")
(run_root / "setup.json").write_text(
    json.dumps({"source": str(REPO), "python": sys.executable,
                "dependencies": ["pytest", "pyyaml", "questionary", "platformdirs"],
                "platform": sys.platform, "synthetic": True}, indent=2), encoding="utf-8")
log = []

def cli(*args, expected=0):
    if globals()["args"].installed_cli is not None:
        executable = globals()["args"].installed_cli
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env["PATH"] = str(executable.parent) + os.pathsep + env.get("PATH", "")
        result = subprocess.run([str(executable), *args], env=env, capture_output=True,
                                encoding="utf-8", errors="strict")
        code = result.returncode
        out, err = buffer.StringIO(result.stdout), buffer.StringIO(result.stderr)
    else:
        out, err = buffer.StringIO(), buffer.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(args))
    row = {"project": Path.cwd().name, "args": list(args), "exit": code,
           "stdout": out.getvalue(), "stderr": err.getvalue()}
    log.append(row)
    (run_root / "build-log.json").write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    if code != expected:
        raise AssertionError(row)
    return out.getvalue()

def managed_snapshot(layout):
    """Full managed byte hashes, including handover/archives, for evaluator use.

    Covers every file under docspec/ and docs/, excluding transient Python caches.
    Generated agent rules and software fixture source files are not managed records.
    This baseline lives outside the cases and does not become product state.
    """
    files = {}
    for folder in (layout.planning_home, layout.project_root / "docs"):
        if not folder.exists():
            continue
        for path in sorted(folder.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                files[path.relative_to(layout.project_root).as_posix()] = (
                    "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest())
    encoded = json.dumps(files, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return {"version": 1, "algorithm": "sha256", "scope": ["docspec/**", "docs/**"],
            "fingerprint": "sha256:" + hashlib.sha256(encoded).hexdigest(), "files": files}


def one_work_summary(layout):
    """Exactly one CLI read must expose the related facts without mutating state."""
    before = managed_snapshot(layout)
    result = json.loads(cli("roadmap", "show", "W-gpt-1", "--json"))
    after = managed_snapshot(layout)
    assert before == after, "roadmap show changed managed content"
    assert result["work"]["id"] == "W-gpt-1", result
    return result, {"command": "artispec roadmap show W-gpt-1 --json",
                    "before": before["fingerprint"], "after": after["fingerprint"],
                    "unchanged": True}


def seed(project):
    project.mkdir()
    os.chdir(project)
    cli("init", "--tool", "codex", "--agents-md", "--no-tex-hint", "--no-update-check")
    # Neutral Python entrypoint preserves argv and keeps evaluator facts outside.
    runner_name = "run-artispec" if args.installed_cli is not None else "run-docspec"
    local_runner = project / (runner_name + ".py")
    local_runner.write_text(
        "import runpy\nfrom pathlib import Path\n"
        "runpy.run_path(str(Path(__file__).resolve().parents[1] / 'runner.py'), run_name='__main__')\n",
        encoding="utf-8")
    # Reuse the persistent interpreter; no dependency installation per CLI call.
    if os.name == "nt":
        exe = sys.executable.replace("'", "''")
        (project / (runner_name + ".ps1")).write_text(
            "$env:PYTHONUTF8 = '1'\n"
            + f"& '{exe}' \"$PSScriptRoot/{runner_name}.py\" @args\nexit $LASTEXITCODE\n",
            encoding="utf-8")
        cmd_exe = sys.executable.replace("%", "%%")
        (project / (runner_name + ".cmd")).write_text(
            "@echo off\nchcp 65001 >nul\nsetlocal DisableDelayedExpansion\nset PYTHONUTF8=1\n"
            + f'"{cmd_exe}" "%~dp0{runner_name}.py" %*\n'
            + "exit /b %ERRORLEVEL%\n", encoding="utf-8", newline="\r\n")
    else:
        shell_runner = project / (runner_name + ".sh")
        shell_runner.write_text(
            "#!/bin/sh\nexport PYTHONUTF8=1\n"
            + f'exec {shlex.quote(sys.executable)} {shlex.quote(str(local_runner))} "$@"\n',
            encoding="utf-8", newline="\n")
        shell_runner.chmod(0o755)
    home = project / "docspec"
    layout = Layout(home, docs_layout=load_config(home).get("docs_layout", "per-article"))
    app = project / "app"
    (app / "src").mkdir(parents=True)
    (app / "tests").mkdir()
    (app / "src" / "entry.py").write_text("TITLE = '工作清單'\n", encoding="utf-8")
    (app / "runtime-input.txt").write_text("ready\n", encoding="utf-8")
    (app / "tests" / "test_entry.py").write_text(
        "from pathlib import Path\n\ndef test_first_row():\n"
        "    assert (Path(__file__).parents[1] / 'runtime-input.txt').read_text(encoding='utf-8').strip() == 'ready'\n",
        encoding="utf-8")
    test_argv = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
    runner = subprocess.list2cmdline(test_argv) if os.name == "nt" else shlex.join(test_argv)
    cli("code", "repo", "add", "app", "app", "--test-command", runner)
    specs.write_spec(layout, {"capability": "entry", "purpose": "工作清單入口",
        "requirements": [{"id": "R1", "title": "列出任務", "statement": "It SHALL list tasks.",
            "verification": ["test"], "scenarios": [{"id": "S1", "title": "第一列",
                "when": "開啟工作清單", "then": "看到第一列"}]}]})
    rec = store.SectionRecord(path="guide/overview", kind="leaf", concept={
        "id": "c-overview", "title": "入口說明", "order": 1, "status": "draft",
        "concept": "工作清單入口的操作說明", "brief": {"audience": "操作人員", "depth": "簡短操作步驟", "breadth": "入口導覽"}},
        decisions=[], history=[])
    article = store.Article(name="guide", revision=1, records=[rec])
    store.save_article(layout, article, load_schema())
    cli("ruling", "add", "--quote", "合成情境：入口仍稱工作清單，先改善第一列可讀性。")
    cli("decision", "add", "--title", "入口呈現", "--statement", "入口稱工作清單；第一列必須完整可見。", "--based-on", "RL-gpt-1")
    cli("decision", "activate", "D-gpt-1")
    cli("code", "change", "new", "improve-entry", "--why", "第一列需完整可見", "--modified", "entry")
    cli("code", "change", "delta", "improve-entry", "--capability", "entry", "--op", "modify-scenario", "--ref", "R1/S1", "--then", "第一列完整可見")
    cli("code", "testplan", "add", "improve-entry", "--location", "app:tests/test_entry.py::test_first_row", "--covers", "entry/R1/S1", "--by", "gemini")
    cli("code", "task", "add", "improve-entry", "--title", "確認入口第一列", "--implements", "entry/R1", "--files", "app:src/entry.py", "--verify", "test", "--tests", "T1")
    cli("roadmap", "add", "--title", "改善軟體入口", "--ref", "swc:improve-entry,gov:D-gpt-1")
    return layout

current = seed(run_root / "current")
cli("handover", "write", "--done", "已整理改善第一列的範圍。", "--promise", "完成入口改善後回報可讀性。", "--next", "接續測試角色審查與簽收，再按證據推進。")
assert ho.freshness(current, ho.load(current))["status"] == "current"
current_plan = json.loads(cli("code", "testplan", "list", "improve-entry", "--json"))
current_roadmap = json.loads(cli("roadmap", "--json"))
assert len(current_plan["tests"]) == 1 and not current_plan["tests"][0].get("signed")
assert evidence.load_all(current) == []
current_summary, current_read = one_work_summary(current)
current_software = next(s for s in current_summary["software"] if s["id"] == "improve-entry")
assert any(s["test"] == "T1" and s["status"] == "unsigned" for s in current_software["signoffs"])
assert current_software["evidence"] == []
assert any(g["id"] == "D-gpt-1" and g["status"] == "active" for g in current_summary["governance"])

stale = seed(run_root / "stale")
# Link before the old handover; a summary must not infer unrelated W-gpt-2.
cli("roadmap", "link", "W-gpt-1", "--ref", "doc:guide")
cli("code", "testplan", "sign", "improve-entry", "T1", "--by", "gemini")
cli("code", "evidence", "run", "improve-entry", "1")
cli("handover", "write", "--done", "第一列測試已通過。", "--promise", "回報入口改善結果。", "--next", "依工作清單入口的方向整理說明，準備收尾。")
assert ho.freshness(stale, ho.load(stale))["status"] == "current"
cli("ruling", "add", "--quote", "合成情境：入口改稱工作總覽，仍須完整顯示第一列。")
cli("decision", "add", "--title", "入口呈現", "--statement", "入口改稱工作總覽；第一列必須完整可見。", "--based-on", "RL-gpt-2", "--supersedes", "D-gpt-1")
cli("decision", "activate", "D-gpt-2")
# Runtime input intentionally outside the declared evidence file set and scope.
(stale.project_root / "app" / "runtime-input.txt").write_text("not-ready\n", encoding="utf-8")
cli("code", "evidence", "run", "improve-entry", "1", expected=1)
cli("render", "guide")
latest = stale.docs_latest("guide")
text = latest.read_text(encoding="utf-8")
needle = "## 1. 入口說明\n"
assert needle in text, text
latest.write_text(text.replace(needle, needle + "\n入口採工作總覽，開啟後檢視完整第一列。\n"), encoding="utf-8")
cli("render", "guide")
cli("roadmap", "add", "--title", "入口操作說明", "--ref", "doc:guide,gov:D-gpt-2")
rows = evidence.load_all(stale)
assert len(rows) == 2, rows
assert rows[0]["result"] == "pass" and rows[1]["result"] == "fail", rows
assert rows[0]["scope"] == rows[1]["scope"], rows
assert rows[0]["files"] and rows[0]["files"] == rows[1]["files"], rows
assert ho.freshness(stale, ho.load(stale))["status"] == "stale"
gov = gv.load_governance(stale)
assert gv.decision_index_entries(stale)["gov:D-gpt-1"]["status"] == "superseded"
new_decision = next(d for d in gov.decisions if d["id"] == "D-gpt-2")
assert gv.decision_effective_status(new_decision, gov) == "active"
assert not stale.existing_versions("guide")
stale_roadmap = json.loads(cli("roadmap", "--json"))
document_work = next(w for w in stale_roadmap["unassigned"] if w["id"] == "W-gpt-2")
assert document_work["status"] == "in-progress", document_work
stale_handover = json.loads(cli("handover", "--json"))
stale_summary, stale_read = one_work_summary(stale)
assert any(g["id"] == "D-gpt-1" and g["status"] == "superseded"
           and "D-gpt-2" in g["current-ids"] for g in stale_summary["governance"])
assert any(g["id"] == "D-gpt-2" and g["status"] == "active" for g in stale_summary["governance"])
stale_software = next(s for s in stale_summary["software"] if s["id"] == "improve-entry")
assert any(e["id"] == "E-gpt-2" and e["result"] == "fail" for e in stale_software["evidence"])
assert all(e["id"] != "E-gpt-1" for e in stale_software["evidence"])
assert any(d["id"] == "doc:guide" and d["written"] and not d["frozen"] for d in stale_summary["documents"])
assert all(d["id"] != "W-gpt-2" for d in stale_summary["dependencies"])
assert {"failed-verification", "superseded-basis", "unfrozen-document"} <= {
    a["code"] for a in stale_summary["actions"]}
facts = {"synthetic": True, "run": str(run_root), "source": str(REPO),
    "runner": "Each project has run-docspec.py; Windows also has .cmd/.ps1 and Linux has .sh.",
    "current": {"project": str(current.project_root), "handover": "current", "test": "T1 planned but unsigned", "evidence": [], "roadmap": current_roadmap, "testplan": current_plan, "work-summary": current_summary},
    "stale": {"project": str(stale.project_root), "handover": stale_handover,
        "document_link": "W-gpt-1 explicitly links doc:guide before the old handover; W-gpt-2 stays independent.",
        "effective_decision": "D-gpt-2", "superseded_decision": "D-gpt-1",
        "earlier_evidence": "E-gpt-1 pass", "latest_evidence": "E-gpt-2 fail",
        "scope_equal": rows[0]["scope"] == rows[1]["scope"],
        "runtime_input": "app/runtime-input.txt is deliberately undeclared; changed ready -> not-ready",
        "document": {"section": "guide/overview", "path": str(latest), "state": "written; no frozen version"},
        "roadmap": stale_roadmap, "work-summary": stale_summary},
    "acceptance": ["Current: find W-gpt-1, unsigned T1, zero evidence, fresh handover.",
        "Stale: reject obsolete handover next-step and D-gpt-1; identify active D-gpt-2 from authority records.",
        "Stale: latest failed E-gpt-2 defeats earlier pass E-gpt-1 with the same scope.",
        "Stale: distinguish written-unfrozen guide from software task; one does not block the other.",
        "Before mutation: explain facts and cite records; then authorized local next step; rewrite handover only after checking current state."]}
(run_root / "facts.json").write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")
(run_root / "factcheck.json").write_text(json.dumps({
    "synthetic": True, "fixture_assertions_passed": True,
    "current_handover": ho.freshness(current, ho.load(current))["status"],
    "current_unsigned_tests": [t["id"] for t in current_plan["tests"] if not t.get("signed")],
    "current_evidence_count": len(evidence.load_all(current)),
    "stale_handover": stale_handover["freshness"]["status"],
    "stale_evidence_results": [{"id": row["id"], "result": row["result"]} for row in rows],
    "same_scope": rows[0]["scope"] == rows[1]["scope"],
    "same_watched_files": rows[0]["files"] == rows[1]["files"],
    "active_decision": new_decision["id"],
    "superseded_decision": "D-gpt-1",
    "document_work_state": document_work["status"],
    "document_versions": stale.existing_versions("guide"),
    "fresh_agent_evaluation_performed": False,
    "one_summary_read": {"current": current_read, "stale": stale_read},
}, ensure_ascii=False, indent=2), encoding="utf-8")
(run_root / "managed-before.json").write_text(json.dumps({
    "current": managed_snapshot(current), "stale": managed_snapshot(stale),
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"run": str(run_root), "current": str(current.project_root), "stale": str(stale.project_root), "facts": str(run_root / "facts.json"), "log": str(run_root / "build-log.json")}, ensure_ascii=False, indent=2))
