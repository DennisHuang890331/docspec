"""Mechanical post-handover checks against external, pre-recorded fixture facts.

This checks state and writes its result outside the participant projects. It does
not replace the independent review of whether an agent understood the facts.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from dspx.engine import handover, change_catalog
from dspx.engine.layout import Layout
from dspx.engine.config import load_config
from dspx.engine.schema import load_schema
from dspx.engine.software import evidence

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--run-dir", type=Path, required=True)
args = parser.parse_args()
root = args.run_dir.resolve()
facts = json.loads((root / "facts.json").read_text(encoding="utf-8"))
before = json.loads((root / "managed-before.json").read_text(encoding="utf-8"))
rows = {}
for name in ("current", "stale"):
    home = root / name / "docspec"
    layout = Layout(home, docs_layout=load_config(home).get("docs_layout", "per-article"))
    after = {}
    for folder in (layout.planning_home, layout.project_root / "docs"):
        for path in sorted(folder.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                after[path.relative_to(layout.project_root).as_posix()] = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    original = before[name]["files"]
    changes = [path for path in sorted(original.keys() | after.keys())
               if original.get(path) != after.get(path)]
    assert changes == ["docspec/governance/handover.yaml"], changes
    note = handover.load(layout)
    fresh = handover.freshness(layout, note)
    assert fresh["status"] == "current" and fresh["changes"] == [], fresh
    current = [change_catalog.show(layout, entry, load_schema()) for entry in change_catalog.entries(layout)]
    assert current == facts[name]["changes"], "A domain judgment or source changed during handover"
    evs = evidence.load_all(layout)
    assert len(evs) == (0 if name == "current" else 2), evs
    expected_runtime = "ready\n" if name == "current" else "not-ready\n"
    assert (layout.project_root / "app/runtime-input.txt").read_text(encoding="utf-8") == expected_runtime
    assert (layout.project_root / "app/src/entry.py").read_text(encoding="utf-8") == "TITLE = '工作清單'\n"
    expected_test = ("from pathlib import Path\n\ndef test_first_row():\n"
                     "    assert (Path(__file__).parents[1] / 'runtime-input.txt').read_text(encoding='utf-8').strip() == 'ready'\n")
    assert (layout.project_root / "app/tests/test_entry.py").read_text(encoding="utf-8") == expected_test
    rows[name] = {"managed-changes": changes, "freshness": fresh,
                  "evidence": [{"id": e["id"], "result": e["result"]} for e in evs],
                  "note": note, "changes": current, "passed": True}
report = {"synthetic": True, "kind": "mechanical-state-check", "cases": rows}
(root / "post-handover-check.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({name: {"passed": row["passed"], "managed-changes": row["managed-changes"]}
                  for name, row in rows.items()}, ensure_ascii=False))
