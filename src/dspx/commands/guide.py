"""docspec guide — projects the single agent contract from the schema, live.

Workflow (loop + author skills + boundaries + filing rules) + every artifact's
meaning / required fields / format / read-write aperture. All from schema.yaml
(workflow block + artifacts + filing-rules) — never written to a file, never drifts.
This solves docspec onboarding with docspec's own philosophy: rules live in the
schema and get projected, not duplicated in drifting prose.
"""

from __future__ import annotations

import argparse
import json
import sys

from dspx.commands._shared import BootstrapError, bootstrap, load_engine_schema
from dspx.schema import required_field_names

NAME = "guide"
HELP = ("agent contract: projects the workflow + every artifact's "
        "meaning/required-fields/format/read-write aperture from the schema")


def _artifact_contract(art) -> dict:
    return {
        "id": art.id,
        "generates": art.generates,
        "kind": art.kind,
        "meaning": art.description,
        "requiredFields": required_field_names(art.schema) if art.schema else [],
        "blockGrammar": art.block_grammar,
        "reader": list(art.aperture.read),
        "writer": list(art.aperture.write),
        "projectsInto": art.aperture.projects_into,
    }


def _print_artifact(a: dict) -> None:
    print(f"\n● {a['id']} → {a['generates']} ({a['kind']})")
    print(f"  meaning: {a['meaning'].strip()}")
    if a["requiredFields"]:
        print(f"  required: {', '.join(a['requiredFields'])}")
    if a["blockGrammar"]:
        print(f"  format: {a['blockGrammar']}")
    print(f"  reader: {', '.join(a['reader']) or '—'}　writer: {', '.join(a['writer']) or '—'}"
          f"　projects: {a['projectsInto'] or '—'}")


def _print_project_file(pf: dict) -> None:
    print(f"\n● {pf.get('id')} → {pf.get('file', '—')}")
    if pf.get("meaning"):
        print(f"  meaning: {str(pf['meaning']).strip()}")
    print(f"  reader: {', '.join(pf.get('reader') or []) or '—'}"
          f"　writer: {', '.join(pf.get('writer') or []) or '—'}")
    if pf.get("when"):
        print(f"  when: {str(pf['when']).strip()}")
    if pf.get("fence"):
        print(f"  scope: {str(pf['fence']).strip()}")


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec guide", description=HELP)
    parser.add_argument("artifact", nargs="?", default=None,
                        help="print only this artifact's / project-file's contract")
    parser.add_argument("--json", action="store_true", dest="as_json", help="JSON output")
    args = parser.parse_args(argv)

    try:
        _layout, config = bootstrap()
        schema = load_engine_schema(config)
    except BootstrapError as exc:
        return exc.exit_code

    artifacts = [_artifact_contract(a) for a in schema.artifacts]
    project_files = [dict(pf) for pf in schema.project_files]

    if args.as_json:
        print(json.dumps({"schema": schema.name, "workflow": schema.workflow,
                          "artifacts": artifacts, "projectFiles": project_files,
                          "filingRules": list(schema.filing_rules)},
                         ensure_ascii=False, indent=2))
        return 0

    # single-item drill-down: docspec guide <id>
    if args.artifact:
        a = next((x for x in artifacts if x["id"] == args.artifact), None)
        if a:
            _print_artifact(a)
            return 0
        pf = next((p for p in project_files if p.get("id") == args.artifact), None)
        if pf:
            _print_project_file(pf)
            return 0
        ids = [x["id"] for x in artifacts] + [str(p.get("id")) for p in project_files]
        sys.stderr.write(
            f"docspec guide: unknown artifact '{args.artifact}'. Valid: {', '.join(ids)}\n")
        return 2

    wf = schema.workflow or {}
    print(f"docspec contract (schema: {schema.name})\n")

    # table of contents (so the agent doesn't read only the head and miss scope)
    toc = ["Workflow (loop)", "Author skills", "Boundaries"]
    if schema.filing_rules:
        toc.append("Filing rules")
    toc.append("Artifact contracts: " + ", ".join(a["id"] for a in artifacts))
    if project_files:
        toc.append("Project-level files: " + ", ".join(str(p.get("id")) for p in project_files))
    print("── Contents ──")
    for t in toc:
        print(f"  · {t}")
    print()

    if wf.get("loop"):
        print("── Workflow (loop) ──")
        print("  " + str(wf["loop"]).strip().replace("\n", "\n  ") + "\n")
    if wf.get("skills"):
        print("── Author skills ──")
        for s in wf["skills"]:
            if isinstance(s, dict):
                print(f"  • {s.get('id')} — {s.get('summary', '')}")
                for st in s.get("steps", []):
                    print(f"      - {st}")
                if s.get("transaction"):
                    print(f"      ⮑ commit: docspec {s['transaction']}")
            else:  # back-compat: a plain string skill line
                print(f"  • {s}")
        print()
    if wf.get("boundaries"):
        print("── Boundaries ──")
        for b in wf["boundaries"]:
            print(f"  • {b}")
        print()
    if schema.filing_rules:
        print("── Filing rules (engine-enforced) ──")
        for r in schema.filing_rules:
            print(f"  • [{r.get('enforced-by')}] {r.get('rule')}")
        print()

    print("── Artifact contracts (each file's meaning / required / read-write) ──")
    for a in artifacts:
        _print_artifact(a)

    if project_files:
        print("\n── Project-level files (agent must know; engine does not validate content) ──")
        for pf in project_files:
            _print_project_file(pf)
    return 0
