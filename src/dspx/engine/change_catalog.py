"""One change namespace; domain formats and acceptance rules remain independent."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from dspx.engine import change as documents
from dspx.engine.software import changes as software, io


@dataclass(frozen=True)
class Entry:
    id: str
    domain: str
    state: str
    folder: Path


def entries(layout) -> list[Entry]:
    result = []
    ids = {}
    for root in io.change_roots(layout):
        for state, base in (("active", root), ("archived", root / "_archive"),
                            ("abandoned", root / "_abandoned")):
            if not base.is_dir():
                continue
            for folder in sorted(base.iterdir()):
                if not folder.is_dir() or folder.name.startswith("_"):
                    continue
                io.managed_path(layout, folder)
                doc = (folder / "change.yaml").is_file()
                sw = (folder / "proposal.yaml").is_file()
                if doc == sw:
                    raise io.SoftwareError(f"missing or ambiguous change record: {folder}")
                if doc:
                    if root == io.legacy_changes_dir(layout):
                        raise io.SoftwareError(f"document change in software-only legacy location: {folder}")
                    ch = documents.load_change_at(folder, state)
                    problems = documents.validate_change(ch)
                    cid = ch.id
                    expected = folder.name
                    domain = "document"
                else:
                    body = io.load(folder / "proposal.yaml", "proposal")
                    if not isinstance(body, dict):
                        raise io.SoftwareError(f"malformed proposal: {folder}")
                    cid = str(body.get("id") or "")
                    expected = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", folder.name) if state == "archived" else folder.name
                    problems = [reason] if (reason := software.validate_id(cid)) else []
                    domain = "software"
                    if state == "abandoned":
                        problems.append("software changes do not have an abandoned state")
                if problems or cid != expected:
                    raise io.SoftwareError(f"invalid change record {folder}: {problems or 'id differs from folder'}")
                if cid in ids:
                    raise io.SoftwareError(f'duplicate change id "{cid}": {ids[cid]} and {folder}')
                ids[cid] = folder
                result.append(Entry(cid, domain, state, folder))
    return sorted(result, key=lambda e: e.id)


def ensure_available(layout, cid: str) -> None:
    entry = next((e for e in entries(layout) if e.id == cid), None)
    if entry:
        raise io.SoftwareError(f'a {entry.domain} change named "{cid}" already exists ({entry.state}); '
                               'names are reserved across domains and history')
    if (io.changes_dir(layout) / cid).exists() or (io.legacy_changes_dir(layout) / cid).exists():
        raise io.SoftwareError(f'change destination "{cid}" already exists')


def ensure_unique(layout, cid: str) -> None:
    """Reject copies of this identity without evaluating unrelated domain records."""
    io.check_change_id(cid)
    folders = []
    for root in io.change_roots(layout):
        for base in (root, root / "_archive", root / "_abandoned"):
            if not base.is_dir():
                continue
            for folder in base.iterdir():
                if not folder.is_dir():
                    continue
                name = (re.sub(r"^\d{4}-\d{2}-\d{2}-", "", folder.name)
                        if base.name == "_archive" and (folder / "proposal.yaml").exists()
                        else folder.name)
                if name == cid:
                    folders.append(folder)
    if len(folders) > 1:
        raise io.SoftwareError(f'duplicate change id "{cid}": {folders}')


def show(layout, entry: Entry, schema) -> dict:
    """Read existing judgments without invoking a refreshing CLI command."""
    from dspx.engine.software import evidence, archive
    sources = [p.relative_to(layout.project_root).as_posix()
               for p in sorted(entry.folder.rglob("*")) if p.is_file()]
    row = {"schema-version": 1, "id": entry.id, "domain": entry.domain,
           "state": entry.state, "sources": sources, "diagnostics": []}
    if entry.domain == "document":
        ch = documents.load_change_at(entry.folder, entry.state)
        row["summary"] = ch.title
        details = {"record": ch.to_dict()}
        if entry.state == "active":
            targets = documents.derive_change_status(layout, ch, schema)
            details.update({"targets": [{"ref": t.ref, "action": t.action,
                                         "section": t.section, "done": t.done, "detail": t.detail}
                                        for t in targets],
                            "archivable": documents.is_archivable(targets)})
        row["details"] = details
    else:
        ch = software.load_change(layout, entry.id, entry.folder)
        row["summary"] = ch["proposal"].get("why") or entry.id
        details = {k: ch[k] for k in ("proposal", "design", "deltas", "tests", "tasks")}
        if entry.state == "active":
            evs = evidence.load_all(layout)
            details["task-status"] = evidence.explain(layout, entry.id)
            details["signoff"] = evidence.signoff_view(layout, ch)
            details["evidence"] = [e for e in evs if e.get("change") == entry.id]
            errors, warnings = software.validate_change(layout, ch, strict=True)
            errors += archive.blockers(layout, ch, evs)
            details["archivable"] = not errors
            row["diagnostics"] = errors + warnings
        row["details"] = details
    return row


def migrate(layout, *, dry_run: bool = False) -> list[dict]:
    """Explicit byte-preserving moves, fully preflighted, with rollback."""
    catalog = entries(layout)
    legacy = io.legacy_changes_dir(layout)
    home = layout.planning_home.resolve()
    moves = []
    for entry in catalog:
        if entry.domain != "software" or not entry.folder.is_relative_to(legacy):
            continue
        software.load_change(layout, entry.id, entry.folder)  # all seals before any move
        target = io.changes_dir(layout) / entry.folder.relative_to(legacy)
        for path in (entry.folder, target, *entry.folder.rglob("*")):
            if path.is_symlink() or not path.resolve().is_relative_to(home):
                raise io.SoftwareError(f"migration path leaves managed root: {path}")
        if target.exists():
            raise io.SoftwareError(f"migration destination already exists: {target}")
        moves.append((entry.folder, target))
    if not dry_run:
        moved = []
        created = []
        try:
            for source, target in moves:
                if not target.parent.exists():
                    for parent in (target.parent, *target.parent.parents):
                        if parent.exists():
                            break
                        created.append(parent)
                    target.parent.mkdir(parents=True)
                source.rename(target)
                moved.append((source, target))
        except BaseException:
            for source, target in reversed(moved):
                target.rename(source)
            for directory in created:
                if directory.is_dir() and not any(directory.iterdir()):
                    directory.rmdir()
            raise
    return [{"from": s.relative_to(layout.project_root).as_posix(),
             "to": t.relative_to(layout.project_root).as_posix()} for s, t in moves]
