"""Document release storage and explicit, preflighted legacy relocation."""
from __future__ import annotations

import shutil
import stat
import tempfile
import os
from pathlib import Path

import yaml

from dspx.engine.layout import Layout, LayoutError, parse_semver
from dspx.engine.render import find_image_refs
from dspx.engine.store import atomic_write_store
from dspx.reports import freeze


def _is_link(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        tag = getattr(os.lstat(path), "st_reparse_tag", None)
    except FileNotFoundError:
        return False
    return tag is not None and tag in (getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", -1),
                                       getattr(stat, "IO_REPARSE_TAG_SYMLINK", -2))


def _safe(layout: Layout, path: Path) -> Path:
    root = layout.project_root.resolve()
    if not path.resolve().is_relative_to(root):
        raise LayoutError(f"version path escapes managed project root: {path}")
    for candidate in (path, *path.parents):
        if candidate == layout.project_root:
            break
        if _is_link(candidate):
            raise LayoutError(f"version path uses a symlink or junction: {candidate}")
        if candidate != path and candidate.exists() and not candidate.is_dir():
            raise LayoutError(f"version path parent is not a directory: {candidate}")
    return path


def verify_selected(layout: Layout, article: str, version: str) -> None:
    """Read-only integrity gate for the selected immutable source bundle."""
    if version == "latest":
        _safe(layout, layout.docs_latest(article))
        return
    snapshot = _safe(layout, layout.docs_snapshot(article, version))
    if not snapshot.is_file():
        raise LayoutError(f"document snapshot not found: {snapshot}")
    _safe(layout, freeze._manifest_path(layout.planning_home))
    raw = freeze._load_raw(layout.planning_home)
    key = snapshot.relative_to(layout.project_root).as_posix()
    if key not in raw.get("frozen", {}) and key not in raw.get("legacy", {}):
        raise LayoutError(f"selected document snapshot is not registered: {key}")
    canonical = snapshot == layout.version_snapshot(article, version)
    if canonical:
        for entry in snapshot.parent.rglob("*"):
            _safe(layout, entry)
    prefix = snapshot.parent.relative_to(layout.project_root).as_posix() + "/"
    problems = freeze.verify(layout.planning_home, layout.project_root, layout.docs_dir, read_only=True)
    selected = [(path, why) for path, why in problems
                if path == key or (canonical and path.startswith(prefix))]
    if selected:
        raise LayoutError("selected snapshot integrity failed: " + "; ".join(f"{p}: {why}" for p, why in selected))


def identical_to_snapshot(layout: Layout, article: str, version: str, body: str) -> bool:
    """Compare released prose AND its referenced image bytes with current content."""
    snapshot = _safe(layout, layout.docs_snapshot(article, version))
    if not snapshot.is_file() or snapshot.read_text(encoding="utf-8").strip() + "\n" != body:
        return False
    refs = list(dict.fromkeys(r for r in find_image_refs(body) if r.startswith("assets/")))
    if refs and snapshot != layout.version_snapshot(article, version):
        return False  # Historical image bytes were never established.
    for ref in refs:
        if len(Path(ref).parts) != 2 or "\\" in ref:
            return False
        released = _safe(layout, snapshot.parent / ref)
        working = _safe(layout, layout.docs_assets_dir(article) / Path(ref).name)
        if not released.is_file() or not working.is_file() or released.read_bytes() != working.read_bytes():
            return False
    return True


def capture(layout: Layout, article: str, version: str, body: str) -> Path:
    """Commit one immutable snapshot bundle; image bytes are captured at freeze."""
    target = _safe(layout, layout.version_snapshot(article, version))
    if target.parent.exists():
        raise LayoutError(f"document snapshot destination already exists: {target.parent}")
    for old in layout.legacy_snapshots(article, version):
        if old.exists():
            raise LayoutError(f"document version already exists: {old}")
    refs = list(dict.fromkeys(r for r in find_image_refs(body) if r.startswith("assets/")))
    assets = {}
    for ref in refs:
        relative = Path(ref)
        if len(relative.parts) != 2 or relative.parts[1] in (".", "..") or "\\" in ref:
            raise LayoutError(f"unsafe or unsupported snapshot image reference: {ref}")
        src = _safe(layout, layout.docs_assets_dir(article) / relative.name)
        if not src.is_file():
            raise LayoutError(f"cannot freeze missing document image: {ref}")
        assets[ref] = src.read_bytes()
    raw = freeze._load_raw(layout.planning_home)
    old_frozen = dict(raw.get("frozen", {}))
    relative_target = target.relative_to(layout.project_root).as_posix()
    if relative_target in old_frozen or relative_target in raw.get("legacy", {}):
        raise LayoutError(f"snapshot is already registered: {relative_target}")
    target.parent.parent.mkdir(parents=True, exist_ok=True)
    pending = Path(tempfile.mkdtemp(prefix="_pending-", dir=target.parent.parent))
    installed = False
    try:
        (pending / "document.md").write_text(body, encoding="utf-8", newline="\n")
        for ref, payload in assets.items():
            dest = pending / ref
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(payload)
        pending.rename(target.parent)
        installed = True
        files = sorted(p for p in target.parent.rglob("*") if p.is_file())
        frozen = dict(old_frozen)
        algorithms = dict(raw.get("hash-algorithms", {}))
        for p in files:
            key = p.relative_to(layout.project_root).as_posix()
            if key in frozen or key in raw.get("legacy", {}):
                raise LayoutError(f"snapshot file is already registered: {key}")
            frozen[key] = freeze._hash(p) if p.name == "document.md" else freeze._hash_legacy_algo(p)
            if p.name != "document.md":
                algorithms[key] = "sha256-bytes"
        raw["frozen"] = frozen
        if algorithms:
            raw["hash-algorithms"] = algorithms
        atomic_write_store(freeze._manifest_path(layout.planning_home),
                           yaml.safe_dump(raw, allow_unicode=True, sort_keys=True))
    except BaseException:
        # Only directories created by this invocation, verified inside the project.
        doomed = target.parent if installed else pending
        _safe(layout, doomed)
        shutil.rmtree(doomed)
        raise
    for p in files:
        try:
            p.chmod(stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
        except OSError:
            pass  # Integrity manifest remains the cross-platform guarantee.
    return target


def articles(layout: Layout) -> list[str]:
    found = set(layout.articles())
    versions = layout.planning_home / "changes" / "_versions"
    _safe(layout, versions)
    if versions.is_dir():
        found.update(p.name for p in versions.iterdir() if p.is_dir() and not p.name.startswith("_"))
    flat = layout.docs_dir / "archive"
    _safe(layout, flat)
    if flat.is_dir():
        for p in flat.iterdir():
            article, separator, version = p.stem.rpartition("_v")
            if p.is_file() and p.suffix == ".md" and separator and parse_semver(version):
                found.add(article)
    history = layout.docs_dir / "revision_history"
    _safe(layout, history)
    if history.is_dir():
        found.update(p.stem for p in history.iterdir() if p.is_file() and p.suffix == ".md")
    if layout.docs_dir.is_dir():
        found.update(p.name for p in layout.docs_dir.iterdir() if p.is_dir()
                     and ((p / "archive").is_dir() or (p / "changelog.md").is_file())
                     and p.name not in ("exports", "assets", "archive", "revision_history"))
    return sorted(found)


def rows(layout: Layout, article: str | None = None) -> list[dict]:
    _safe(layout, freeze._manifest_path(layout.planning_home))
    names = articles(layout)
    if article is not None and article not in names:
        raise LayoutError(f"unknown document: {article}")
    out = []
    problems = freeze.verify(layout.planning_home, layout.project_root, layout.docs_dir, read_only=True)
    if problems:
        raise LayoutError("document history integrity failed: " + "; ".join(f"{p}: {why}" for p, why in problems))
    for name in ([article] if article else names):
        for parsed in layout.existing_versions(name):
            version = ".".join(map(str, parsed))
            snapshot = _safe(layout, layout.docs_snapshot(name, version))
            refs = [r for r in find_image_refs(snapshot.read_text(encoding="utf-8")) if r.startswith("assets/")]
            missing = [r for r in refs if not (snapshot.parent / r).is_file()]
            current = snapshot == layout.version_snapshot(name, version)
            out.append({"document": name, "version": version,
                        "snapshot": snapshot.relative_to(layout.project_root).as_posix(),
                        "storage": "versions" if current else "legacy",
                        "asset-provenance": "unknown" if missing else "captured" if refs else "not-required",
                        "diagnostics": ["historical image provenance is unknown: " + ", ".join(missing)] if missing else []})
    return out


def migrate(layout: Layout, article: str | None = None, *, dry_run: bool = False) -> dict:
    """Preflight the whole batch, then move bytes and rekey original hashes once."""
    _safe(layout, freeze._manifest_path(layout.planning_home))
    names = articles(layout)
    if article is not None and article not in names:
        raise LayoutError(f"unknown document: {article}")
    for name in ([article] if article else names):
        layout.existing_versions(name)  # Diagnose colliding identities before hash errors.
    raw = freeze._load_raw(layout.planning_home)
    problems = freeze.verify(layout.planning_home, layout.project_root, layout.docs_dir, read_only=True)
    if problems:
        raise LayoutError("migration refused: history integrity failed: " + "; ".join(f"{p}: {why}" for p, why in problems))
    moves: list[tuple[Path, Path]] = []
    warnings = []
    rekeys = {}
    def add(source: Path, target: Path, *, registered: bool = False):
        _safe(layout, source)
        _safe(layout, target)
        if target.exists() or any(t == target for _, t in moves):
            raise LayoutError(f"migration destination already exists: {target}")
        old = source.relative_to(layout.project_root).as_posix()
        new = target.relative_to(layout.project_root).as_posix()
        if new in raw.get("frozen", {}) or new in raw.get("legacy", {}):
            raise LayoutError(f"migration destination is already registered: {new}")
        if registered:
            tables = [key for key in ("frozen", "legacy") if old in raw.get(key, {})]
            if len(tables) != 1:
                raise LayoutError(f"migration source is not uniquely registered: {old}")
            rekeys[old] = (tables[0], new)
        moves.append((source, target))
    for name in ([article] if article else names):
        versions = layout.existing_versions(name)
        for parsed in versions:
            version = ".".join(map(str, parsed))
            snapshot = layout.docs_snapshot(name, version)
            if snapshot != layout.version_snapshot(name, version):
                add(snapshot, layout.version_snapshot(name, version), registered=True)
                if any(r.startswith("assets/") for r in find_image_refs(snapshot.read_text(encoding="utf-8"))):
                    warnings.append(f"{name}@{version}: historical image provenance is unknown; current images were not copied")
            if parsed != max(versions):
                for fmt in ("pdf", "docx", "tex"):
                    source = layout.docs_export(name, version, fmt)
                    if source.is_file():
                        add(source, layout.version_export(name, version, fmt))
        for source in layout.legacy_changelogs(name):
            if source.is_file():
                add(source, layout.docs_changelog(name))
        proof = layout.docs_exports_dir / "_proof" / name
        if proof.is_dir():
            for source in sorted(proof.iterdir()):
                if source.is_file() and source.name.startswith("page_") and source.suffix == ".png":
                    add(source, layout.document_versions_dir(name) / "_legacy-proof" / source.name)
            if any(s.parent == proof for s, _ in moves):
                warnings.append(f"{name}: unversioned proof preserved as _legacy-proof; version provenance is unknown")
    if article is None:
        legacy = layout.docs_dir / "archive" / "legacy"
        if legacy.is_dir():
            for source in sorted(legacy.rglob("*")):
                if source.is_file() and not freeze.is_sync_junk(source.name):
                    relative = source.relative_to(legacy)
                    if len(relative.parts) < 2:
                        raise LayoutError(f"legacy collection has no name: {source}")
                    target = layout.planning_home / "changes" / "_versions" / "_legacy" / relative.parts[0] / "snapshot"
                    add(source, target.joinpath(*relative.parts[1:]), registered=True)
    # Registered older/non-semver history also belongs outside docs. Preserve
    # its original classification and hashes without inventing version numbers.
    for old in sorted(set(raw.get("frozen", {})) | set(raw.get("legacy", {}))):
        if old in rekeys:
            continue
        source = layout.project_root / old
        if not source.is_relative_to(layout.docs_dir) or not freeze.is_frozen_path(source):
            continue
        rel = source.relative_to(layout.docs_dir)
        if rel.parts[0] == "archive":
            if article is not None:
                continue
            collection, tail = "_unversioned", rel.parts[1:]
        elif len(rel.parts) > 2 and rel.parts[1] == "archive":
            collection, tail = rel.parts[0], rel.parts[2:]
            if article is not None and collection != article:
                continue
        else:
            continue
        target = layout.planning_home / "changes" / "_versions" / "_legacy" / collection / "snapshot"
        add(source, target.joinpath(*tail), registered=True)
        warnings.append(f"{old}: preserved as a legacy collection without an inferred version number")
    result = {"schema-version": 1, "dry-run": dry_run,
              "moves": [{"from": s.relative_to(layout.project_root).as_posix(),
                         "to": t.relative_to(layout.project_root).as_posix()} for s, t in moves],
              "diagnostics": warnings}
    if dry_run or not moves:
        return result
    updated = {**raw, "frozen": dict(raw.get("frozen", {})), "legacy": dict(raw.get("legacy", {}))}
    if "hash-algorithms" in raw:
        updated["hash-algorithms"] = dict(raw["hash-algorithms"])
    for old, (table, new) in rekeys.items():
        updated[table][new] = updated[table].pop(old)
        if old in updated.get("hash-algorithms", {}):
            updated["hash-algorithms"][new] = updated["hash-algorithms"].pop(old)
    if not updated["legacy"] and "legacy" not in raw:
        del updated["legacy"]
    moved = []
    created = []
    try:
        for source, target in moves:
            parents = []
            for parent in (target.parent, *target.parent.parents):
                if parent.exists():
                    break
                parents.append(parent)
            for parent in reversed(parents):
                parent.mkdir()
                created.append(parent)
            source.rename(target)
            moved.append((source, target))
        atomic_write_store(freeze._manifest_path(layout.planning_home),
                           yaml.safe_dump(updated, allow_unicode=True, sort_keys=True))
    except BaseException:
        for source, target in reversed(moved):
            target.rename(source)
        for parent in reversed(created):
            if parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
        raise
    # Remove only emptied managed history directories, never users' unrelated files.
    for source, _ in moves:
        parent = source.parent
        while parent != layout.docs_dir and parent.is_relative_to(layout.docs_dir):
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
    return result
