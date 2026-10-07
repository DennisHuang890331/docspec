"""Extend isolated handover fixtures with both change domains; answers remain outside cases.

Uses the existing builder's --output-dir argument. This is synthetic preparation,
not an agent result. Each call creates a fresh directory and never deletes data.
"""
import contextlib
import io
import json
from pathlib import Path
import runpy

with contextlib.redirect_stdout(io.StringIO()):
    data = runpy.run_path(str(Path(__file__).with_name("build_handover_cases.py")))

cli = data["cli"]
run_root = data["run_root"]
ho = data["ho"]
managed_snapshot = data["managed_snapshot"]
import os
from dspx.engine import change_catalog
from dspx.engine.schema import load_schema

facts_path = run_root / "facts.json"
facts = json.loads(facts_path.read_text(encoding="utf-8"))
snapshots = {}
for name in ("current", "stale"):
    layout = data[name]
    os.chdir(layout.project_root)
    cli("change", "new", "revise-guide", "--publish", "advisory", "--seed", "c-overview",
        "--why", "整理合成入口說明，保留兩域各自完成條件")
    cli("roadmap", "link", "W-gpt-1", "--ref", "change:revise-guide")
    if name == "current":
        old = ho.load(layout)
        ho.write(layout, {key: old.get(key, []) for key in
                         ("done", "in-progress", "promises", "cautions", "next")}, tool="gpt")
    catalog = change_catalog.entries(layout)
    assert {e.domain for e in catalog} == {"document", "software"}
    assert all(e.folder.parent == layout.planning_home / "changes" for e in catalog)
    facts[name]["changes"] = [change_catalog.show(layout, e, load_schema()) for e in catalog]
    facts[name]["roadmap"] = json.loads(cli("roadmap", "--json"))
    facts[name]["work-summary"] = json.loads(cli("roadmap", "show", "W-gpt-1", "--json"))
    facts[name]["initial-freshness"] = ho.freshness(layout, ho.load(layout))["status"]
    snapshots[name] = managed_snapshot(layout)
assert facts["current"]["initial-freshness"] == "current"
assert facts["stale"]["initial-freshness"] == "stale"
facts["acceptance"].append("Both domains must be discovered by shared change/show; original document targets and unsigned/failed software judgments remain distinct.")
facts_path.write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")
(run_root / "managed-before.json").write_text(json.dumps(snapshots, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"run": str(run_root), "current": str(data["current"].project_root),
                  "stale": str(data["stale"].project_root), "facts": str(facts_path)}, ensure_ascii=False))
