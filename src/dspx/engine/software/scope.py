"""Versioned, local verification contracts; presentation fields are deliberately excluded."""

from __future__ import annotations

from dspx.engine import governance as gv
from dspx.engine.software import changes as chg
from dspx.engine.software import io, specs as sp, tasks as tk

VERSION = 1


def requirement_ref(ref: str) -> str:
    cap, rid, _ = sp.split_ref(ref)
    return f"{cap}/{rid}"


def _basis(layout, refs):
    refs = sorted(set(refs))
    if not refs:
        return []
    gov = gv.load_governance(layout) if gv.has_governance(layout) else gv.Governance([], [], [], [])
    decisions = {str(d.get("id")): d for d in gov.decisions}
    return [{"ref": ref, "decision": {
        k: v for k, v in (decisions.get(gv.strip_ns(ref)) or {}).items()
        if k not in ("created-at", "activated-at", "created-by", "title")
    }} for ref in refs]


def requirement(layout, ch, ref, *, scenario_ids=None):
    req = tk._requirement_after(layout, ch, ref)
    if req is None:
        return {"ref": ref, "missing": True}
    scenarios = [{k: s.get(k) for k in ("id", "when", "then")}
                 for s in req.get("scenarios") or []
                 if scenario_ids is None or str(s.get("id")) in scenario_ids]
    return {"ref": ref, "statement": req.get("statement"),
            "verification": sorted(io.as_list(req.get("verification"))),
            "based-on": _basis(layout, io.as_list(req.get("based-on"))),
            "scenarios": sorted(scenarios, key=lambda s: str(s["id"]))}


def seal(data):
    return {"version": VERSION, "fingerprint": io.fingerprint(data), "contract": data}


def test_scope(layout, ch, test):
    refs = {}
    for ref in io.as_list(test.get("covers")):
        _cap, _rid, sid = sp.split_ref(ref)
        refs.setdefault(requirement_ref(ref), set()).add(sid)
    return seal({"location": test.get("location"), "covers": sorted(io.as_list(test.get("covers"))),
                 "requirements": [requirement(layout, ch, r, scenario_ids=refs[r]) for r in sorted(refs)]})


def task_scope(layout, ch, task):
    wanted = set(io.as_list((task.get("verify") or {}).get("tests")))
    plans = [t for t in ch["tests"].get("tests") or [] if str(t.get("id")) in wanted]
    refs = {requirement_ref(r) for r in io.as_list(task.get("implements"))}
    refs |= {requirement_ref(r) for t in plans for r in io.as_list(t.get("covers"))}
    settings = chg.repo_settings(layout)
    runners = {}
    for t in plans:
        repo, _ = tk.split_location(t.get("location") or "")
        cfg = settings.get(repo) or {}
        runners[repo] = {"test-command": cfg.get("test-command", "python -m pytest"),
                         "rootdir-arg": cfg.get("rootdir-arg", "--rootdir={root}"),
                         "junit-arg": cfg.get("junit-arg", "--junitxml={junit}")}
    return seal({"requirements": [requirement(layout, ch, r) for r in sorted(refs)],
                 "decisions": _basis(layout, io.as_list(ch["design"].get("decisions"))),
                 "implements": sorted(io.as_list(task.get("implements"))),
                 "methods": sorted(io.as_list((task.get("verify") or {}).get("methods"))),
                 "test-ids": sorted(wanted),
                 "tests": sorted([{"id": t.get("id"), "location": t.get("location"),
                                   "covers": sorted(io.as_list(t.get("covers")))} for t in plans],
                                  key=lambda t: str(t["id"])),
                 "allow-skips": bool((task.get("verify") or {}).get("allow-skips")),
                 "files": sorted(io.as_list(task.get("files"))), "runners": runners})


def acceptance_scope(layout, ch, task):
    """Owner confirmation includes every implementing task of the accepted requirements."""
    refs = {requirement_ref(r) for r in io.as_list(task.get("implements"))}
    related = [t for t in ch["tasks"].get("tasks") or []
               if t is task or refs & {requirement_ref(r) for r in io.as_list(t.get("implements"))}]
    return seal({str(t["id"]): task_scope(layout, ch, t) for t in related}), related


def differences(previous, current) -> list[str]:
    """Explain comparable contracts without becoming another validity predicate.

    Only field names and identifiers are printed, not arbitrary requirement text
    or runner command values. Old/unsupported contracts keep the generic reason.
    """
    if (not isinstance(previous, dict) or not isinstance(current, dict)
            or previous.get("version") != VERSION or current.get("version") != VERSION
            or not isinstance(previous.get("contract"), dict)
            or not isinstance(current.get("contract"), dict)):
        return []
    before, after = previous["contract"], current["contract"]
    required = {"requirements", "decisions", "implements", "methods", "test-ids", "tests",
                "allow-skips", "files", "runners"}
    for contract in (before, after):
        if not required <= contract.keys():
            return []
        requirements = contract["requirements"]
        if not isinstance(requirements, list):
            return []
        for req in requirements:
            if not isinstance(req, dict) or "ref" not in req:
                return []
            if req.get("missing") is True:
                continue
            if not {"statement", "verification", "based-on", "scenarios"} <= req.keys():
                return []
            if (not isinstance(req["scenarios"], list)
                    or any(not isinstance(s, dict) or not {"id", "when", "then"} <= s.keys()
                           for s in req["scenarios"])):
                return []
    changes = []

    def indexed(rows, key):
        if not isinstance(rows, list) or any(not isinstance(r, dict) or key not in r for r in rows):
            return None
        result = {str(r[key]): r for r in rows}
        return result if len(result) == len(rows) else None

    def record_fields(old, new, label):
        if old == new:
            return
        if not isinstance(old, dict) or not isinstance(new, dict):
            changes.append(f"{label} changed")
            return
        for field in sorted(old.keys() | new.keys()):
            if old.get(field) != new.get(field):
                changes.append(f"{label} {field} changed")

    def records(old, new, key, label):
        left, right = indexed(old, key), indexed(new, key)
        if left is None or right is None:
            if old != new:
                changes.append(f"{label} changed")
            return
        for ident in sorted(left.keys() | right.keys()):
            record_fields(left.get(ident), right.get(ident), f"{label} {ident}")

    left = indexed(before.get("requirements", []), "ref")
    right = indexed(after.get("requirements", []), "ref")
    if left is None or right is None:
        if before.get("requirements") != after.get("requirements"):
            changes.append("requirements changed")
    else:
        for ref in sorted(left.keys() | right.keys()):
            old, new = left.get(ref), right.get(ref)
            if old is None or new is None:
                changes.append(f"requirement {ref} {'added' if old is None else 'removed'}")
                continue
            for field in sorted(old.keys() | new.keys()):
                if old.get(field) == new.get(field):
                    continue
                if field == "scenarios":
                    old_s = indexed(old.get(field), "id")
                    new_s = indexed(new.get(field), "id")
                    if old_s is None or new_s is None:
                        changes.append(f"requirement {ref} scenarios changed")
                    else:
                        for sid in sorted(old_s.keys() | new_s.keys()):
                            record_fields(old_s.get(sid), new_s.get(sid), f"scenario {ref}/{sid}")
                elif field == "based-on":
                    records(old.get(field), new.get(field), "ref", f"requirement {ref} based-on")
                else:
                    changes.append(f"requirement {ref} {field} changed")

    for field in sorted((before.keys() | after.keys()) - {"requirements"}):
        old, new = before.get(field), after.get(field)
        if old == new:
            continue
        if field in ("tests", "decisions"):
            records(old, new, "id" if field == "tests" else "ref", field)
        elif field == "runners" and isinstance(old, dict) and isinstance(new, dict):
            for repo in sorted(old.keys() | new.keys()):
                record_fields(old.get(repo), new.get(repo), f"runners {repo}")
        elif field in ("methods", "files", "implements", "test-ids") and isinstance(old, list) and isinstance(new, list):
            removed, added = set(map(str, old)) - set(map(str, new)), set(map(str, new)) - set(map(str, old))
            if removed:
                changes.append(f"{field} removed: {', '.join(sorted(removed))}")
            if added:
                changes.append(f"{field} added: {', '.join(sorted(added))}")
            if not removed and not added:
                changes.append(f"{field} changed")
        else:
            changes.append(f"{field} changed")
    return changes
