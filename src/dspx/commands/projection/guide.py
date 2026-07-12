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
from dspx.engine.schema import field_contract, required_field_names

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
        "fieldContract": field_contract(art.schema) if art.schema else [],
        "entriesContainer": bool(art.entries),
        "closed": bool(art.closed),
        "blockGrammar": art.block_grammar,
        "reader": list(art.aperture.read),
        "writer": list(art.aperture.write),
        "projectsInto": art.aperture.projects_into,
    }


def _format_field_line(f: dict, indent: str = "    ") -> list[str]:
    """一欄一行：name  type  required/optional  [= enum 值]  [→ relation]  [(closed)]；
    巢狀 object 子欄縮排遞迴。讓 agent 一眼看到合法形狀（型別＋enum 合法值）。"""
    req = "required" if f.get("required") else "optional"
    bits = [f"{indent}{f['name']:<14} {f['type']:<9} {req}"]
    if f.get("values"):
        bits.append(f"= {' | '.join(map(str, f['values']))}")
    if f.get("relation"):
        bits.append(f"→ {f['relation']}")
    if f.get("type") == "object":
        bits.append("(closed)" if f.get("closed") else "(open)")
    lines = ["  ".join(bits)]
    for sub in f.get("fields", []):
        lines.extend(_format_field_line(sub, indent + "  "))
    return lines


def _print_artifact(a: dict) -> None:
    print(f"\n● {a['id']} → {a['generates']} ({a['kind']})")
    print(f"  meaning: {a['meaning'].strip()}")
    if a.get("entriesContainer"):
        print("  container: file top level is { entries: [ <entry-below> ] }  (NOT a bare list / other key)")
    if a.get("fieldContract"):
        closed = " (closed: unknown keys are a check error)" if a.get("closed") else ""
        print(f"  fields{closed}:")
        for f in a["fieldContract"]:
            for line in _format_field_line(f):
                print(line)
    elif a["requiredFields"]:
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

    wf = schema.workflow or {}
    wf_skills = [s for s in (wf.get("skills") or []) if isinstance(s, dict)]

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
        # workflow-skill drill-down: docspec guide apply (etc.) — projects that skill's contract
        wsk = next((s for s in wf_skills if s.get("id") == args.artifact), None)
        if wsk:
            print(f"● {wsk.get('id')} — {str(wsk.get('summary', '')).strip()}")
            for st in wsk.get("steps", []):
                print(f"  - {st}")
            if wsk.get("transaction"):
                print(f"  ⮑ commit: docspec {wsk['transaction']}")
            return 0
        ids = ([x["id"] for x in artifacts] + [str(p.get("id")) for p in project_files]
               + [str(s.get("id")) for s in wf_skills])
        sys.stderr.write(
            f"docspec guide: unknown artifact '{args.artifact}'. Valid: {', '.join(ids)}\n")
        return 2

    wf = schema.workflow or {}
    print(f"docspec contract (schema: {schema.name})\n")

    # table of contents (so the agent doesn't read only the head and miss scope)
    toc = ["Workflow (loop)", "Author skills", "Boundaries"]
    if wf.get("migration"):
        toc.append("Migration onboarding")
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
    if wf.get("migration"):
        # 遷移三步配方（schema 缺鍵＝不印，向後相容其他 schema；與上方 wf.get 逐鍵防禦一致）
        mig = wf["migration"]
        print("── Migration onboarding (existing projects) ──")
        if isinstance(mig, dict):
            if mig.get("summary"):
                print("  " + str(mig["summary"]).strip().replace("\n", "\n  "))
            for i, step in enumerate(mig.get("steps") or [], 1):
                print(f"  {i}. " + str(step).strip().replace("\n", "\n     "))
        else:
            print(f"  {mig}")
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
