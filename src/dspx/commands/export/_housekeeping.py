"""輸出清理（預設只留 latest）＋選輸入快照。"""

from __future__ import annotations

import sys
import re
import shutil
import hashlib
from pathlib import Path

from dspx.engine.layout import Layout, parse_semver
from dspx.engine.document_versions import _safe


def _preflight_version_paths(layout: Layout, article: str) -> None:
    """Guard paths that version discovery may enumerate before resolving input."""
    versions = _safe(layout, layout.document_versions_dir(article))
    if versions.is_dir():
        for folder in versions.iterdir():
            if parse_semver(folder.name) is not None:
                _safe(layout, folder)
                _safe(layout, folder / "snapshot" / "document.md")
    for root, prefix in ((layout.docs_dir / "archive", f"{article}_v"),
                         (layout.docs_dir / article / "archive", "v")):
        _safe(layout, root)
        if root.is_dir():
            for candidate in root.iterdir():
                if candidate.name.startswith(prefix) and candidate.suffix == ".md":
                    _safe(layout, candidate)


def _prune_old_pdfs(layout: Layout, article: str, keep: Path) -> list[Path]:
    """預設只留 latest：刪同篇其他已產 PDF（舊版號 + `_vlatest` 預覽），只留剛產出的 `keep`。

    scope 嚴格：只掃 docs/exports/ **頂層**、檔名前綴 `<article>_v`（`_v` 分隔符保證不誤傷
    `<article>-x` 等他篇）；非遞迴（不碰 journals/ 子夾）、不碰 archive/。回刪除清單。"""
    pruned: list[Path] = []
    exports = _safe(layout, layout.docs_exports_dir)
    if not exports.is_dir():
        return pruned
    keep = keep.resolve()
    for p in exports.iterdir():
        if not p.name.startswith(f"{article}_v") or p.suffix != ".pdf":
            continue
        _safe(layout, p)
        if not p.is_file():
            continue
        if p.resolve() == keep:
            continue
        label = p.stem[len(f"{article}_v"):]
        if label != "latest" and parse_semver(label) is None:
            continue
        try:
            p.unlink()
            pruned.append(p)
        except OSError:
            pass   # 刪不掉不致命（鎖定/權限）；export 本身已成功
    return pruned


def _is_latest_frozen(layout: Layout, article: str, label: str) -> bool:
    """Only the highest existing frozen version can update the public projection."""
    selected = parse_semver(label)
    _preflight_version_paths(layout, article)
    versions = layout.existing_versions(article)
    return selected is not None and bool(versions) and selected == max(versions)


def _prune_proof_pages(directory: Path, *, layout: Layout | None = None) -> None:
    """Remove only generated page images, preserving unrelated user files."""
    if layout is not None:
        _safe(layout, directory)
    if directory.is_dir():
        for path in directory.iterdir():
            if layout is not None:
                _safe(layout, path)
            if path.is_file() and re.fullmatch(r"page_\d+\.png", path.name):
                path.unlink()


def _preserve_legacy_proof(layout: Layout, article: str) -> None:
    """Keep unversioned public proof bytes without inventing a version claim."""
    directory = _safe(layout, layout.docs_exports_dir / "_proof" / article)
    if not directory.is_dir():
        return
    pages = sorted(_safe(layout, p) for p in directory.iterdir()
                   if re.fullmatch(r"page_\d+\.png", p.name) and _safe(layout, p).is_file())
    if not pages:
        return
    fingerprints = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in pages}
    versions = _safe(layout, layout.document_versions_dir(article))
    if versions.is_dir():
        for folder in versions.iterdir():
            if folder.name != "_preview" and parse_semver(folder.name) is None:
                continue
            proof = _safe(layout, folder / "proof")
            if proof.is_dir():
                saved = {p.name: hashlib.sha256(_safe(layout, p).read_bytes()).hexdigest()
                         for p in proof.iterdir()
                         if re.fullmatch(r"page_\d+\.png", p.name) and _safe(layout, p).is_file()}
                if saved == fingerprints:
                    return  # These exact bytes are already retained.
    digest = hashlib.sha256(repr(sorted(fingerprints.items())).encode("utf-8")).hexdigest()
    target = _safe(layout, versions / "_legacy-proof" / digest)
    for page in pages:
        saved_page = _safe(layout, target / page.name)
        if saved_page.exists() and (not saved_page.is_file() or saved_page.read_bytes() != page.read_bytes()):
            raise ValueError(f"unversioned proof preservation conflict: {saved_page}")
    target.mkdir(parents=True, exist_ok=True)
    for page in pages:
        if not (target / page.name).exists():
            shutil.copy2(page, target / page.name)
    sys.stderr.write(
        f"artispec: unversioned proof preserved at {target}; version provenance is unknown.\n")


def _preserve_public_outputs(layout: Layout, article: str, selected: str) -> list[Path]:
    """Preflight and preserve legacy artifacts before clearing old projections.

    All conflicts are checked before copying or deleting anything. Snapshot
    contents and assets are never moved or invented by this compatibility path.
    """
    transfers: list[tuple[Path, Path]] = []
    exports = _safe(layout, layout.docs_exports_dir)
    prefix = f"{article}_v"
    candidates = [p for p in exports.iterdir() if p.name.startswith(prefix)] if exports.is_dir() else []
    journals = _safe(layout, layout.docs_journal_dir)
    if journals.is_dir():
        for adapter in journals.iterdir():
            _safe(layout, adapter)
            if adapter.is_dir():
                candidates.extend(p for p in adapter.iterdir()
                                  if p.name.startswith(prefix) and p.suffix == ".tex")
    for source in candidates:
        _safe(layout, source)
        if not source.is_file() or source.suffix not in (".pdf", ".tex"):
            continue
        label = source.stem[len(f"{article}_v"):]
        if label == selected or (label != "latest" and parse_semver(label) is None):
            continue
        if label != "latest" and not _safe(layout, layout.docs_snapshot(article, label)).is_file():
            raise ValueError(
                f"legacy export has no source snapshot: {source}; preserve it and review "
                "document versions before updating the latest deliverable")
        target = layout.version_export(article, label, source.suffix[1:])
        if source.parent != exports:
            target = target.parent / "journals" / source.parent.name / source.name
        _safe(layout, target)
        if target.exists() and (not target.is_file() or target.read_bytes() != source.read_bytes()):
            raise ValueError(
                f"legacy export conflicts with the saved version artifact: {source} versus {target}; "
                "no public artifacts were removed; review/migrate document versions first")
        transfers.append((source, target))
    for source, target in transfers:
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    return [source for source, _target in transfers]


# ── 選輸入快照 ────────────────────────────────────────────────────

def _resolve_input(layout: Layout, article: str, version: str | None,
                   latest: bool) -> tuple[Path, str] | None:
    """回 (快照路徑, 版本標籤)；找不到→印錯誤回 None。"""
    _preflight_version_paths(layout, article)
    if latest:
        path = _safe(layout, layout.docs_latest(article))
        if not path.is_file():
            sys.stderr.write(f"artispec: _latest not found ({path}) — render/publish first.\n")
            return None
        sys.stderr.write("artispec: ⚠ --latest exports the working copy (not a final draft, no version number, may contain drift).\n")
        return path, "latest"
    if version is not None:
        if parse_semver(version) is None:
            sys.stderr.write(f"artispec: --version \"{version}\" is not valid semver (X.Y.Z).\n")
            return None
        path = _safe(layout, layout.docs_snapshot(article, version))
        if not path.is_file():
            sys.stderr.write(f"artispec: snapshot for version v{version} not found ({path}).\n")
            return None
        return path, version
    versions = layout.existing_versions(article)
    if not versions:
        sys.stderr.write(
            f"artispec: article \"{article}\" has no published snapshot yet — first `artispec freeze {article}`"
            f" (or --latest to export a preview of the working copy).\n")
        return None
    top = max(versions)
    label = f"{top[0]}.{top[1]}.{top[2]}"
    return _safe(layout, layout.docs_snapshot(article, label)), label
