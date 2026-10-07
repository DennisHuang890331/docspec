"""Independent acceptance tests for version storage and explicit legacy migration."""

from __future__ import annotations

import errno
import hashlib
import io
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from dspx import cli
from dspx.commands.deliverable import freeze as freeze_cmd
from dspx.commands.deliverable import render as render_cmd
from dspx.engine.layout import Layout, LayoutError
from dspx.reports import freeze


def _version_root(home: Path, article: str, version: str) -> Path:
    return home / "changes" / "_versions" / article / version


def _canonical(home: Path, article: str, version: str) -> Path:
    return _version_root(home, article, version) / "snapshot" / "document.md"


def _legacy(layout: Layout, article: str, version: str) -> Path:
    if layout.docs_layout == "flat":
        return layout.docs_dir / "archive" / f"{article}_v{version}.md"
    return layout.docs_dir / article / "archive" / f"v{version}.md"


def _legacy_history(layout: Layout, article: str) -> Path:
    if layout.docs_layout == "flat":
        return layout.docs_dir / "revision_history" / f"{article}.md"
    return layout.docs_dir / article / "changelog.md"


def _write(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _files(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file()}


def _seed_legacy(layout: Layout, article: str, version: str,
                 body: bytes = b"# Historical guide\r\n\r\nApproved historical text.\r\n") -> Path:
    path = _write(_legacy(layout, article, version), body)
    freeze.record(layout.planning_home, layout.project_root, path)
    return path


def _written_doc(make_project, write_leaf, monkeypatch, *, docs_layout="per-article",
                 body="Approved operating instructions.\n") -> Layout:
    home = make_project(f"language: en\ndocs_layout: {docs_layout}\n")
    layout = Layout(home, docs_layout)
    write_leaf(home, "guide/Operation", concept={
        "id": "c-guide-operation", "title": "Operation", "order": 1,
    })
    monkeypatch.chdir(layout.project_root)
    assert render_cmd.run(["guide"]) == 0
    latest = layout.docs_latest("guide")
    latest.write_text(latest.read_text(encoding="utf-8") + body, encoding="utf-8")
    assert render_cmd.run(["guide"]) == 0
    return layout


@pytest.mark.parametrize("docs_layout", ["flat", "per-article"])
def test_new_snapshot_writer_and_reader_are_under_managed_changes(make_project, docs_layout):
    home = make_project()
    layout = Layout(home, docs_layout)
    expected = _canonical(home, "guide", "1.2.3")
    assert layout.version_snapshot("guide", "1.2.3") == expected
    assert layout.docs_snapshot("guide", "1.2.3") == expected
    assert not expected.exists(), "path discovery must not create a snapshot"


@pytest.mark.parametrize("docs_layout", ["flat", "per-article"])
def test_legacy_snapshot_is_read_without_moving_or_rewriting(make_project, docs_layout):
    layout = Layout(make_project(), docs_layout)
    old = _seed_legacy(layout, "guide", "1.2.3")
    before = _files(layout.project_root)
    assert layout.docs_snapshot("guide", "1.2.3") == old
    assert layout.existing_versions("guide") == [(1, 2, 3)]
    assert _files(layout.project_root) == before


@pytest.mark.parametrize("same_bytes", [True, False])
def test_duplicate_new_and_legacy_version_refuses_ambiguous_read(make_project, same_bytes):
    layout = Layout(make_project())
    old = _seed_legacy(layout, "guide", "1.0.0")
    _write(_canonical(layout.planning_home, "guide", "1.0.0"),
           old.read_bytes() if same_bytes else b"A different history.\n")
    before = _files(layout.project_root)
    with pytest.raises(LayoutError):
        layout.docs_snapshot("guide", "1.0.0")
    assert _files(layout.project_root) == before


@pytest.mark.parametrize("docs_layout", ["flat", "per-article"])
def test_existing_versions_merges_valid_new_and_legacy_snapshots(make_project, docs_layout):
    layout = Layout(make_project(), docs_layout)
    _write(_legacy(layout, "guide", "1.0.0"), b"old\n")
    _write(_canonical(layout.planning_home, "guide", "1.0.1"), b"new\n")
    _write(_canonical(layout.planning_home, "guide", "2.0.0"), b"newest\n")
    _write(_canonical(layout.planning_home, "guide", "_preview"), b"preview\n")
    _write(_canonical(layout.planning_home, "guide", "not-a-version"), b"invalid\n")
    _version_root(layout.planning_home, "guide", "9.0.0").mkdir(parents=True)
    _write(_legacy(layout, "other", "8.0.0"), b"unrelated\n")
    before = _files(layout.project_root)
    assert sorted(layout.existing_versions("guide")) == [(1, 0, 0), (1, 0, 1), (2, 0, 0)]
    assert _files(layout.project_root) == before


def test_export_proof_and_history_have_separate_version_paths(make_project):
    home = make_project()
    layout = Layout(home)
    root = _version_root(home, "guide", "1.2.3")
    assert layout.version_export("guide", "1.2.3", "pdf") == root / "exports" / "guide_v1.2.3.pdf"
    assert layout.version_proof("guide", "1.2.3") == root / "proof"
    assert layout.docs_changelog("guide") == home / "changes" / "_versions" / "guide" / "history.md"
    assert layout.version_export("guide", "1.2.3", "pdf") != layout.docs_export("guide", "1.2.3", "pdf")
    assert layout.version_export("guide", "latest", "pdf").parent.parent.name == "_preview"
    assert not root.exists(), "path queries must remain read-only"


@pytest.mark.parametrize("docs_layout", ["flat", "per-article"])
def test_legacy_history_reader_never_redirects_new_history_writer(make_project, docs_layout):
    home = make_project()
    layout = Layout(home, docs_layout)
    old = _write(_legacy_history(layout, "guide"), b"# Prior approved history\r\n")
    before = _files(layout.project_root)
    assert old in layout.legacy_changelogs("guide")
    assert layout.docs_changelog("guide") == home / "changes" / "_versions" / "guide" / "history.md"
    assert _files(layout.project_root) == before


@pytest.mark.parametrize("path", [
    "docspec/changes/_versions/guide/1.0.0/snapshot/document.md",
    "docspec/changes/_versions/guide/1.0.0/snapshot/assets/nested/figure.png",
    "docs/archive/guide_v1.0.0.md",
    "docs/guide/archive/v1.0.0.md",
])
def test_only_managed_snapshot_and_legacy_archive_content_is_frozen(path):
    assert freeze.is_frozen_path(path)


@pytest.mark.parametrize("path", [
    "docspec/changes/_versions/guide/1.0.0/exports/guide_v1.0.0.pdf",
    "docspec/changes/_versions/guide/1.0.0/proof/page_01.png",
    "docspec/changes/_versions/guide/history.md",
    "docspec/changes/_versions/guide/_preview/snapshot/document.md",
    "openspec/changes/_versions/guide/1.0.0/snapshot/document.md",
    "openspec/changes/archive/old.md",
    "docs/exports/archive/other-tool.txt",
    "docs/vendor/tool/archive/history.md",
    "docs/guide/_latest.md",
])
def test_outputs_previews_and_other_tools_are_not_frozen(path):
    assert not freeze.is_frozen_path(path)


@pytest.mark.parametrize("docs_layout", ["flat", "per-article"])
def test_freeze_writes_only_latest_deliverable_and_managed_history(
        make_project, write_leaf, monkeypatch, docs_layout):
    layout = _written_doc(make_project, write_leaf, monkeypatch, docs_layout=docs_layout)
    assert freeze_cmd.run(["guide", "--note", "Owner-authorized first version"]) == 0
    snap = _canonical(layout.planning_home, "guide", "1.0.0")
    assert snap.is_file()
    assert b"Approved operating instructions." in snap.read_bytes()
    assert not _legacy(layout, "guide", "1.0.0").exists()
    assert not _legacy_history(layout, "guide").exists()
    assert layout.docs_changelog("guide").is_file()
    assert not [p for p in layout.docs_dir.rglob("*") if p.is_file() and p != layout.docs_latest("guide")]
    assert freeze.verify(layout.planning_home, layout.project_root, layout.docs_dir) == []


def test_freeze_captures_only_referenced_assets_and_later_working_edits_do_not_change_history(
        make_project, write_leaf, monkeypatch):
    layout = _written_doc(make_project, write_leaf, monkeypatch,
                          docs_layout="flat",
                          body="Operating diagram.\n\n![Diagram](assets/diagram.svg)\n")
    original = b'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><rect width="20" height="20" fill="blue"/></svg>\n'
    working = _write(layout.docs_assets_dir("guide") / "diagram.svg", original)
    _write(layout.docs_assets_dir("guide") / "unused.svg", b"not referenced\n")
    assert freeze_cmd.run(["guide"]) == 0
    saved = _canonical(layout.planning_home, "guide", "1.0.0").parent / "assets" / "diagram.svg"
    assert saved.read_bytes() == original
    assert not (saved.parent / "unused.svg").exists()
    manifest_before = freeze.load_manifest(layout.planning_home).copy()
    working.write_bytes(original.replace(b"blue", b"red"))
    assert saved.read_bytes() == original
    assert freeze.load_manifest(layout.planning_home) == manifest_before
    assert freeze.verify(layout.planning_home, layout.project_root, layout.docs_dir) == []


@pytest.mark.parametrize("damage", ["tamper", "delete", "unregistered"])
def test_new_snapshot_asset_integrity_catches_tamper_delete_and_extra_files(
        make_project, damage):
    layout = Layout(make_project())
    snap = _write(_canonical(layout.planning_home, "guide", "1.0.0"), b"# Frozen\n")
    asset = _write(snap.parent / "assets" / "figure.png", b"original binary\x00\xff")
    freeze.record(layout.planning_home, layout.project_root, snap)
    freeze.record(layout.planning_home, layout.project_root, asset)
    before_manifest = freeze.load_manifest(layout.planning_home).copy()
    if damage == "tamper":
        asset.write_bytes(b"altered binary\x00\xff")
    elif damage == "delete":
        asset.unlink()
    else:
        _write(snap.parent / "assets" / "extra.png", b"unregistered image")
    problems = freeze.verify(layout.planning_home, layout.project_root, layout.docs_dir)
    assert problems, "managed version snapshot content must be scanned as well as legacy docs"
    expected = {"tamper": "tampered", "delete": "deleted", "unregistered": "not registered"}[damage]
    assert any(expected in message for _path, message in problems)
    assert freeze.load_manifest(layout.planning_home) == before_manifest, "verification must not bless damage"


def test_new_freeze_refuses_existing_legacy_history_until_explicit_migration(
        make_project, write_leaf, monkeypatch, capsys):
    layout = _written_doc(make_project, write_leaf, monkeypatch)
    old = _write(_legacy_history(layout, "guide"), b"# Original approved history\r\n")
    old_bytes = old.read_bytes()
    capsys.readouterr()
    assert freeze_cmd.run(["guide"]) == 1
    message = capsys.readouterr()
    assert "migrate" in (message.out + message.err).lower()
    assert old.read_bytes() == old_bytes
    assert not layout.docs_changelog("guide").exists()
    assert not _canonical(layout.planning_home, "guide", "1.0.0").exists()


@pytest.mark.parametrize("docs_layout", ["flat", "per-article"])
def test_versions_query_and_migration_dry_run_leave_every_file_unchanged(
        make_project, monkeypatch, capsys, docs_layout):
    layout = Layout(make_project(f"language: en\ndocs_layout: {docs_layout}\n"), docs_layout)
    old = _seed_legacy(layout, "guide", "1.0.0")
    _write(_legacy_history(layout, "guide"), b"# Version history\r\n")
    monkeypatch.chdir(layout.project_root)
    before = _files(layout.project_root)
    capsys.readouterr()
    assert cli.main(["versions", "guide", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    serialized = json.dumps(result)
    assert "guide" in serialized and "1.0.0" in serialized
    assert old.is_file()
    assert cli.main(["versions", "migrate", "guide", "--dry-run"]) == 0
    assert _files(layout.project_root) == before


@pytest.mark.parametrize("docs_layout", ["flat", "per-article"])
def test_explicit_migration_preserves_snapshot_and_history_bytes_and_rekeys_existing_hash(
        make_project, monkeypatch, docs_layout):
    layout = Layout(make_project(f"language: en\ndocs_layout: {docs_layout}\n"), docs_layout)
    original = b"# Approved history\r\n\r\nKeep punctuation, spacing and line endings.\r\n"
    old = _seed_legacy(layout, "guide", "1.0.0", original)
    history = _write(_legacy_history(layout, "guide"), b"# History\r\n| 1.0.0 | Approved |\r\n")
    old_history = history.read_bytes()
    old_key = old.relative_to(layout.project_root).as_posix()
    original_hash = freeze.load_manifest(layout.planning_home)[old_key]
    latest = _write(layout.docs_latest("guide"), b"A current editable deliverable.\n")
    monkeypatch.chdir(layout.project_root)
    assert cli.main(["versions", "migrate", "guide"]) == 0
    new = _canonical(layout.planning_home, "guide", "1.0.0")
    assert new.read_bytes() == original
    assert layout.docs_changelog("guide").read_bytes() == old_history
    assert not old.exists() and not history.exists()
    assert latest.read_bytes() == b"A current editable deliverable.\n"
    manifest = freeze.load_manifest(layout.planning_home)
    new_key = new.relative_to(layout.project_root).as_posix()
    assert old_key not in manifest
    assert manifest[new_key] == original_hash, "migration must preserve the registered hash, not rehash history"
    assert freeze.verify(layout.planning_home, layout.project_root, layout.docs_dir) == []
    after = _files(layout.project_root)
    assert cli.main(["versions", "migrate", "guide"]) == 0
    assert _files(layout.project_root) == after, "already-migrated history must not be rewritten"


@pytest.mark.parametrize("selected", [None, "alpha"])
def test_migration_defaults_to_all_but_explicit_article_stays_scoped(make_project, monkeypatch, selected):
    layout = Layout(make_project())
    alpha = _seed_legacy(layout, "alpha", "1.0.0", b"alpha\n")
    beta = _seed_legacy(layout, "beta", "2.0.0", b"beta\n")
    monkeypatch.chdir(layout.project_root)
    args = ["versions", "migrate"] + ([selected] if selected else [])
    assert cli.main(args) == 0
    assert not alpha.exists()
    assert _canonical(layout.planning_home, "alpha", "1.0.0").read_bytes() == b"alpha\n"
    if selected:
        assert beta.read_bytes() == b"beta\n"
        assert not _canonical(layout.planning_home, "beta", "2.0.0").exists()
    else:
        assert not beta.exists()
        assert _canonical(layout.planning_home, "beta", "2.0.0").read_bytes() == b"beta\n"


@pytest.mark.parametrize("same_bytes", [True, False])
def test_migration_collision_refuses_whole_batch_without_overwriting(make_project, monkeypatch, capsys, same_bytes):
    layout = Layout(make_project())
    old = _seed_legacy(layout, "alpha", "1.0.0", b"alpha\n")
    _seed_legacy(layout, "beta", "2.0.0", b"beta\n")
    destination = _write(_canonical(layout.planning_home, "alpha", "1.0.0"),
                         old.read_bytes() if same_bytes else b"different alpha\n")
    freeze.record(layout.planning_home, layout.project_root, destination)
    monkeypatch.chdir(layout.project_root)
    before = _files(layout.project_root)
    capsys.readouterr()
    assert cli.main(["versions", "migrate"]) != 0
    message = capsys.readouterr()
    diagnostic = (message.out + message.err).lower()
    assert "alpha" in diagnostic and "1.0.0" in diagnostic
    assert "unknown command" not in diagnostic
    assert _files(layout.project_root) == before


def test_migration_refuses_tampered_registered_history_without_hash_laundering(
        make_project, monkeypatch, capsys):
    layout = Layout(make_project())
    old = _seed_legacy(layout, "alpha", "1.0.0", b"approved\n")
    _seed_legacy(layout, "beta", "2.0.0", b"unrelated approved\n")
    old.write_bytes(b"tampered\n")
    monkeypatch.chdir(layout.project_root)
    before = _files(layout.project_root)
    capsys.readouterr()
    assert cli.main(["versions", "migrate"]) != 0
    message = capsys.readouterr()
    assert any(word in (message.out + message.err).lower() for word in ("tamper", "integrity"))
    assert _files(layout.project_root) == before


def test_migration_of_legacy_image_never_invents_historical_asset_from_current_docs(
        make_project, monkeypatch, capsys):
    layout = Layout(make_project())
    original = b"# Historical guide\n\n![Historical diagram](assets/diagram.svg)\n"
    _seed_legacy(layout, "guide", "1.0.0", original)
    current = _write(layout.docs_assets_dir("guide") / "diagram.svg", b"today's unrelated image")
    monkeypatch.chdir(layout.project_root)
    capsys.readouterr()
    assert cli.main(["versions", "migrate", "guide"]) == 0
    message = capsys.readouterr()
    assert any(word in (message.out + message.err).lower() for word in ("provenance", "historical", "unknown"))
    new = _canonical(layout.planning_home, "guide", "1.0.0")
    assert new.read_bytes() == original
    assert not (new.parent / "assets" / "diagram.svg").exists()
    assert current.read_bytes() == b"today's unrelated image"


def test_migration_move_failure_rolls_back_files_and_manifest(make_project, monkeypatch):
    layout = Layout(make_project())
    _seed_legacy(layout, "alpha", "1.0.0", b"alpha\n")
    _seed_legacy(layout, "beta", "2.0.0", b"beta\n")
    monkeypatch.chdir(layout.project_root)
    before = _files(layout.project_root)
    original_rename = Path.rename
    injected = []

    def fail_second_source(self, target):
        if self == _legacy(layout, "beta", "2.0.0"):
            injected.append(self)
            raise OSError("injected historical move failure")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", fail_second_source)
    assert cli.main(["versions", "migrate"]) != 0
    assert injected, "the migration must reach the simulated move failure"
    assert _files(layout.project_root) == before


def _two_frozen_versions(make_project, write_leaf, monkeypatch) -> Layout:
    layout = _written_doc(make_project, write_leaf, monkeypatch, body="First approved text.\n")
    assert freeze_cmd.run(["guide"]) == 0
    latest = layout.docs_latest("guide")
    latest.write_text(latest.read_text(encoding="utf-8").replace("First approved text.", "Second approved text."),
                      encoding="utf-8")
    assert render_cmd.run(["guide"]) == 0
    assert freeze_cmd.run(["guide"]) == 0
    return layout


def test_export_and_proof_keep_older_version_outputs_without_overwriting_latest_delivery(
        make_project, write_leaf, monkeypatch):
    layout = _two_frozen_versions(make_project, write_leaf, monkeypatch)
    assert cli.main(["export", "guide", "--version", "1.0.1"]) == 0
    assert cli.main(["proof", "guide", "--version", "1.0.1"]) == 0
    newest = layout.version_export("guide", "1.0.1", "pdf")
    delivery = layout.docs_export("guide", "1.0.1", "pdf")
    assert newest.is_file() and delivery.read_bytes() == newest.read_bytes()
    before_docs = _files(layout.docs_dir)
    assert cli.main(["export", "guide", "--version", "1.0.0"]) == 0
    assert cli.main(["proof", "guide", "--version", "1.0.0"]) == 0
    assert layout.version_export("guide", "1.0.0", "pdf").is_file()
    assert sorted(layout.version_proof("guide", "1.0.0").glob("page_*.png"))
    assert sorted(layout.version_proof("guide", "1.0.1").glob("page_*.png"))
    assert _files(layout.docs_dir) == before_docs


def test_unfrozen_preview_export_does_not_replace_latest_frozen_pdf(
        make_project, write_leaf, monkeypatch):
    layout = _two_frozen_versions(make_project, write_leaf, monkeypatch)
    assert cli.main(["export", "guide"]) == 0
    before_docs = _files(layout.docs_dir)
    assert cli.main(["export", "guide", "--latest"]) == 0
    assert layout.version_export("guide", "latest", "pdf").is_file()
    assert _files(layout.docs_dir) == before_docs


def test_export_reads_captured_frozen_png_after_current_image_changes(
        make_project, write_leaf, monkeypatch):
    from PIL import Image
    import pypdfium2 as pdfium

    layout = _written_doc(make_project, write_leaf, monkeypatch,
                          docs_layout="flat",
                          body="Approved colored diagram.\n\n![Diagram](assets/diagram.png)\n")
    working = layout.docs_assets_dir("guide") / "diagram.png"
    working.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (20, 20), "blue").save(working)
    original = working.read_bytes()
    assert freeze_cmd.run(["guide"]) == 0
    saved = _canonical(layout.planning_home, "guide", "1.0.0").parent / "assets" / "diagram.png"
    assert saved.read_bytes() == original
    Image.new("RGB", (20, 20), "red").save(working)
    assert cli.main(["export", "guide"]) == 0
    reader = pdfium.PdfDocument(str(layout.version_export("guide", "1.0.0", "pdf")))
    colors = set()
    try:
        for page in reader:
            bitmap = page.render(scale=1)
            image = bitmap.to_pil().convert("RGB")
            colors.update(color for _count, color in image.getcolors(image.width * image.height))
            bitmap.close()
            page.close()
    finally:
        reader.close()
    assert (0, 0, 255) in colors, "the exported image must match the captured blue version"
    assert (255, 0, 0) not in colors, "the current red image must not leak into historical PDF"


def test_new_snapshot_missing_asset_refuses_export_even_when_current_asset_exists(
        make_project, monkeypatch, capsys):
    layout = Layout(make_project())
    snap = _write(_canonical(layout.planning_home, "guide", "1.0.0"),
                  b"# Frozen guide\n\n![Diagram](assets/diagram.svg)\n")
    freeze.record(layout.planning_home, layout.project_root, snap)
    _write(layout.docs_assets_dir("guide") / "diagram.svg",
           b'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"/>')
    monkeypatch.chdir(layout.project_root)
    capsys.readouterr()
    assert cli.main(["export", "guide"]) == 1
    message = capsys.readouterr()
    assert any(word in (message.out + message.err).lower() for word in ("asset", "image"))
    assert not layout.version_export("guide", "1.0.0", "pdf").exists()


def test_legacy_image_export_refuses_current_asset_substitution(make_project, monkeypatch, capsys):
    layout = Layout(make_project())
    _seed_legacy(layout, "guide", "1.0.0",
                 b"# Legacy guide\n\n![Historical diagram](assets/diagram.svg)\n")
    _write(layout.docs_assets_dir("guide") / "diagram.svg",
           b'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"/>')
    monkeypatch.chdir(layout.project_root)
    capsys.readouterr()
    assert cli.main(["export", "guide"]) == 1
    message = capsys.readouterr()
    diagnostic = (message.out + message.err).lower()
    assert any(word in diagnostic for word in ("historical", "provenance", "legacy"))
    assert "asset" in diagnostic or "image" in diagnostic
    assert not layout.docs_export("guide", "1.0.0", "pdf").exists()


@pytest.mark.parametrize("keep", [False, True])
def test_highest_export_preserves_old_pdf_and_journal_bytes_before_cleaning_docs(
        make_project, write_leaf, monkeypatch, keep):
    layout = _two_frozen_versions(make_project, write_leaf, monkeypatch)
    old_pdf_bytes = b"Original historical PDF bytes: never reconstruct or silently discard."
    old_tex_bytes = b"% Original independently compiled journal source\r\nHistorical content.\r\n"
    old_pdf = _write(layout.docs_export("guide", "1.0.0", "pdf"), old_pdf_bytes)
    old_tex = _write(layout.docs_journal_export("guide", "1.0.0", "ieee", "tex"), old_tex_bytes)
    args = ["export", "guide"] + (["--keep"] if keep else [])
    assert cli.main(args) == 0
    assert layout.version_export("guide", "1.0.0", "pdf").read_bytes() == old_pdf_bytes
    saved_tex = _version_root(layout.planning_home, "guide", "1.0.0") / "exports" / "journals" / "ieee" / "guide_v1.0.0.tex"
    assert saved_tex.read_bytes() == old_tex_bytes
    assert not old_pdf.exists() and not old_tex.exists()
    assert layout.docs_export("guide", "1.0.1", "pdf").is_file()


def test_highest_export_refuses_conflicting_historical_artifact_without_changing_docs(
        make_project, write_leaf, monkeypatch, capsys):
    layout = _two_frozen_versions(make_project, write_leaf, monkeypatch)
    _write(layout.docs_export("guide", "1.0.0", "pdf"), b"The originally delivered PDF.")
    canonical = _write(layout.version_export("guide", "1.0.0", "pdf"), b"A conflicting archived PDF.")
    before_docs = _files(layout.docs_dir)
    capsys.readouterr()
    assert cli.main(["export", "guide"]) == 1
    message = capsys.readouterr()
    assert any(word in (message.out + message.err).lower() for word in ("collision", "conflict", "differ"))
    assert _files(layout.docs_dir) == before_docs
    assert canonical.read_bytes() == b"A conflicting archived PDF."


def test_orphan_historical_pdf_refuses_cleanup_without_creating_a_fake_version(
        make_project, write_leaf, monkeypatch, capsys):
    layout = _two_frozen_versions(make_project, write_leaf, monkeypatch)
    orphan = _write(layout.docs_export("guide", "0.9.0", "pdf"), b"PDF whose historical Markdown is missing.")
    before_docs = _files(layout.docs_dir)
    capsys.readouterr()
    assert cli.main(["export", "guide"]) == 1
    message = capsys.readouterr()
    assert any(word in (message.out + message.err).lower() for word in ("snapshot", "markdown", "orphan"))
    assert orphan.read_bytes() == b"PDF whose historical Markdown is missing."
    assert _files(layout.docs_dir) == before_docs
    assert not _version_root(layout.planning_home, "guide", "0.9.0").exists()


def test_register_legacy_moves_arbitrary_files_to_reserved_collection_without_creating_versions(
        make_project, monkeypatch):
    layout = Layout(make_project())
    incoming = layout.project_root / "incoming-history"
    original = {
        "approved.docx": b"original arbitrary office bytes\x00\xff\r\n",
        "nested/data.bin": b"\x00\x01\x02historical binary payload",
        "v9.8.7.md": b"# An imported filename does not establish a managed version.\r\n",
    }
    for relative, content in original.items():
        _write(incoming / relative, content)
    monkeypatch.chdir(layout.project_root)
    assert cli.main(["freeze", "register-legacy", str(incoming), "--into", "archive-collection"]) == 0
    saved_root = layout.planning_home / "changes" / "_versions" / "_legacy" / "archive-collection" / "snapshot"
    assert {p.relative_to(saved_root).as_posix(): p.read_bytes()
            for p in saved_root.rglob("*") if p.is_file()} == original
    assert not incoming.exists()
    assert not layout.docs_dir.exists(), "registration must not put historical deliverables back in docs"
    assert layout.existing_versions("archive-collection") == []
    registered = freeze.load_legacy(layout.planning_home)
    assert all((saved_root / relative).relative_to(layout.project_root).as_posix() in registered
               for relative in original)
    assert all(freeze.is_frozen_path(saved_root / relative) for relative in original)
    assert freeze.verify(layout.planning_home, layout.project_root, layout.docs_dir) == []


def test_registered_reserved_collection_tamper_cannot_be_blessed_by_registering_again(
        make_project, monkeypatch):
    layout = Layout(make_project())
    incoming = layout.project_root / "incoming"
    _write(incoming / "legacy.dat", b"approved arbitrary bytes\x00\xff")
    monkeypatch.chdir(layout.project_root)
    assert cli.main(["freeze", "register-legacy", str(incoming), "--into", "collection"]) == 0
    saved_root = layout.planning_home / "changes" / "_versions" / "_legacy" / "collection" / "snapshot"
    saved = saved_root / "legacy.dat"
    manifest_before = (layout.planning_home / ".freeze.yaml").read_bytes()
    saved.write_bytes(b"modified arbitrary bytes\x00\xff")
    before = _files(layout.project_root)
    assert cli.main(["freeze", "register-legacy", str(saved_root)]) == 1
    assert _files(layout.project_root) == before
    assert (layout.planning_home / ".freeze.yaml").read_bytes() == manifest_before
    assert any("tampered" in detail for _path, detail in
               freeze.verify(layout.planning_home, layout.project_root, layout.docs_dir))


def test_default_migration_preserves_registered_old_legacy_collection_bytes_and_hashes(
        make_project, monkeypatch):
    layout = Layout(make_project())
    old_root = layout.docs_dir / "archive" / "legacy" / "old-import"
    originals = {
        "approved.docx": b"historical office file\r\n\x00\xff",
        "nested/table.bin": b"\x01\x02old binary table",
        "v7.8.9.md": b"# Arbitrary imported filename\r\n",
    }
    files = [_write(old_root / relative, content) for relative, content in originals.items()]
    freeze.record_legacy(layout.planning_home, layout.project_root, files)
    original_hashes = {
        relative: freeze.load_legacy(layout.planning_home)[
            (old_root / relative).relative_to(layout.project_root).as_posix()]
        for relative in originals
    }
    monkeypatch.chdir(layout.project_root)
    before = _files(layout.project_root)
    assert cli.main(["versions", "migrate", "--dry-run"]) == 0
    assert _files(layout.project_root) == before
    assert cli.main(["versions", "migrate"]) == 0
    new_root = layout.planning_home / "changes" / "_versions" / "_legacy" / "old-import" / "snapshot"
    assert not [p for p in old_root.rglob("*") if p.is_file()]
    manifest = freeze.load_legacy(layout.planning_home)
    for relative, content in originals.items():
        saved = new_root / relative
        assert saved.read_bytes() == content
        assert manifest[saved.relative_to(layout.project_root).as_posix()] == original_hashes[relative]
        assert (old_root / relative).relative_to(layout.project_root).as_posix() not in manifest
    assert layout.existing_versions("old-import") == []
    assert freeze.verify(layout.planning_home, layout.project_root, layout.docs_dir) == []


@pytest.mark.parametrize("malformed", [
    "root-list", "duplicate-root-key", "duplicate-file-key", "table-list",
    "numeric-digest", "numeric-file-key", "null-table", "invalid-digest",
])
@pytest.mark.parametrize("dry_run", [True, False])
def test_malformed_freeze_manifest_refuses_migration_without_changing_any_file(
        make_project, monkeypatch, capsys, malformed, dry_run):
    layout = Layout(make_project())
    old = _seed_legacy(layout, "guide", "1.0.0", b"approved historical bytes\n")
    key = old.relative_to(layout.project_root).as_posix()
    digest = freeze.load_manifest(layout.planning_home)[key]
    texts = {
        "root-list": "- not a mapping\n",
        "duplicate-root-key": f"frozen: {{}}\nfrozen:\n  {key}: {digest}\n",
        "duplicate-file-key": f"frozen:\n  {key}: {'0' * 64}\n  {key}: {digest}\n",
        "table-list": "frozen: []\n",
        "numeric-digest": f"frozen:\n  {key}: 123\n",
        "numeric-file-key": f"frozen:\n  123: {digest}\n",
        "null-table": "frozen: null\n",
        "invalid-digest": f"frozen:\n  {key}: not-a-hash\n",
    }
    _write(layout.planning_home / ".freeze.yaml", texts[malformed].encode("utf-8"))
    monkeypatch.chdir(layout.project_root)
    before = _files(layout.project_root)
    capsys.readouterr()
    args = ["versions", "migrate"] + (["--dry-run"] if dry_run else [])
    assert cli.main(args) == 1
    diagnostic = capsys.readouterr()
    assert "unknown command" not in (diagnostic.out + diagnostic.err).lower()
    assert _files(layout.project_root) == before


def test_old_raw_crlf_hash_dry_run_is_read_only_and_real_migration_rekeys_original_hash(
        make_project, monkeypatch):
    layout = Layout(make_project())
    original = b"# Approved pre-normalization snapshot\r\n\r\nKeep raw historical bytes.\r\n"
    old = _write(_legacy(layout, "guide", "1.0.0"), original)
    old_key = old.relative_to(layout.project_root).as_posix()
    original_raw_hash = hashlib.sha256(original).hexdigest()
    manifest = layout.planning_home / ".freeze.yaml"
    _write(manifest, f"frozen:\n  {old_key}: {original_raw_hash}\n".encode("utf-8"))
    monkeypatch.chdir(layout.project_root)
    before = _files(layout.project_root)
    assert cli.main(["versions", "migrate", "guide", "--dry-run"]) == 0
    assert _files(layout.project_root) == before
    assert cli.main(["versions", "migrate", "guide"]) == 0
    new = _canonical(layout.planning_home, "guide", "1.0.0")
    assert new.read_bytes() == original
    updated = freeze.load_manifest(layout.planning_home)
    assert old_key not in updated
    assert updated[new.relative_to(layout.project_root).as_posix()] == original_raw_hash
    after = _files(layout.project_root)
    assert freeze.verify(layout.planning_home, layout.project_root, layout.docs_dir, read_only=True) == []
    assert _files(layout.project_root) == after


def _symlink_or_actual_platform_skip(link: Path, target: Path, *, directory=False) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target, target_is_directory=directory)
    except OSError as exc:
        unsupported = {errno.EPERM, errno.EACCES, errno.ENOTSUP}
        if getattr(exc, "winerror", None) == 1314 or exc.errno in unsupported:
            pytest.skip(f"actual filesystem does not permit symlink creation: {exc}")
        raise


@pytest.mark.parametrize("escape", ["source", "destination"])
def test_migration_rejects_real_symlink_escape_without_moving_or_modifying_external_files(
        make_project, monkeypatch, tmp_path, capsys, escape):
    layout = Layout(make_project())
    old = _seed_legacy(layout, "guide", "1.0.0", b"approved\n")
    outside = tmp_path / "outside-managed-project"
    outside.mkdir()
    external = _write(outside / "document.md", b"approved\n")
    if escape == "source":
        old.unlink()
        _symlink_or_actual_platform_skip(old, external)
    else:
        target = layout.planning_home / "changes" / "_versions" / "guide"
        _symlink_or_actual_platform_skip(target, outside, directory=True)
    monkeypatch.chdir(layout.project_root)
    before = _files(layout.project_root)
    before_external = _files(outside)
    capsys.readouterr()
    assert cli.main(["versions", "migrate", "guide"]) == 1
    message = capsys.readouterr()
    assert any(word in (message.out + message.err).lower()
               for word in ("escape", "outside", "symlink", "symbolic link", "managed", "leaves"))
    assert _files(layout.project_root) == before
    assert _files(outside) == before_external
    assert (old if escape == "source" else target).is_symlink()


@pytest.mark.parametrize("operation", ["export", "proof"])
def test_latest_public_operation_preserves_unknown_version_proof_without_inventing_a_version(
        make_project, write_leaf, monkeypatch, capsys, operation):
    layout = _two_frozen_versions(make_project, write_leaf, monkeypatch)
    assert cli.main(["export", "guide"]) == 0
    proof_dir = layout.docs_exports_dir / "_proof" / "guide"
    original_page = b"unversioned previously reviewed PNG bytes\x00\xff"
    _write(proof_dir / "page_01.png", original_page)
    note = _write(proof_dir / "user_note.txt", b"Operator's own proof notes must remain.\r\n")
    prior_versions = layout.existing_versions("guide")
    prior_snapshots = {
        version: layout.docs_snapshot("guide", ".".join(map(str, version))).read_bytes()
        for version in prior_versions
    }
    capsys.readouterr()
    assert cli.main([operation, "guide"]) == 0
    message = capsys.readouterr()
    assert "unknown" in (message.out + message.err).lower()
    preserved_root = layout.planning_home / "changes" / "_versions" / "guide" / "_legacy-proof"
    preserved = [p for p in preserved_root.rglob("page_01.png") if p.read_bytes() == original_page]
    assert len(preserved) == 1
    assert note.read_bytes() == b"Operator's own proof notes must remain.\r\n"
    assert layout.existing_versions("guide") == prior_versions
    assert all(layout.docs_snapshot("guide", ".".join(map(str, version))).read_bytes() == prior_snapshots[version]
               for version in prior_versions)
    directories = {p.relative_to(preserved_root).as_posix() for p in preserved_root.iterdir() if p.is_dir()}
    assert not any(p.is_file() for p in preserved_root.rglob("document.md"))
    _write(proof_dir / "page_01.png", original_page)
    assert cli.main([operation, "guide"]) == 0
    assert {p.relative_to(preserved_root).as_posix() for p in preserved_root.iterdir() if p.is_dir()} == directories
    assert len([p for p in preserved_root.rglob("page_01.png") if p.read_bytes() == original_page]) == 1
    assert note.read_bytes() == b"Operator's own proof notes must remain.\r\n"


def _frozen_blue_image(make_project, write_leaf, monkeypatch) -> tuple[Layout, Path]:
    from PIL import Image

    layout = _written_doc(make_project, write_leaf, monkeypatch, docs_layout="flat",
                          body="Approved image.\n\n![Blue diagram](assets/diagram.png)\n")
    working = layout.docs_assets_dir("guide") / "diagram.png"
    working.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (20, 20), "blue").save(working)
    assert freeze_cmd.run(["guide"]) == 0
    return layout, _canonical(layout.planning_home, "guide", "1.0.0").parent / "assets" / "diagram.png"


@pytest.mark.parametrize("track", ["pdf", "journal"])
def test_export_refuses_tampered_frozen_image_even_if_it_is_still_a_valid_png(
        make_project, write_leaf, monkeypatch, capsys, track):
    from PIL import Image

    layout, saved = _frozen_blue_image(make_project, write_leaf, monkeypatch)
    args = ["export", "guide"] + (["--journal", "ieee"] if track == "journal" else [])
    assert cli.main(args) == 0
    saved.chmod(stat.S_IREAD | stat.S_IWRITE)
    Image.new("RGB", (20, 20), "red").save(saved)
    before = _files(layout.project_root)
    capsys.readouterr()
    assert cli.main(args) == 1
    message = capsys.readouterr()
    assert "tamper" in (message.out + message.err).lower() or "integrity" in (message.out + message.err).lower()
    assert _files(layout.project_root) == before


def test_frozen_image_crlf_only_change_is_tampering_while_markdown_line_endings_are_not(
        make_project, write_leaf, monkeypatch):
    layout, saved = _frozen_blue_image(make_project, write_leaf, monkeypatch)
    original = saved.read_bytes()
    assert b"\r\n" in original, "real PNG signature provides a byte-level CRLF boundary"
    manifest_before = (layout.planning_home / ".freeze.yaml").read_bytes()
    saved.chmod(stat.S_IREAD | stat.S_IWRITE)
    saved.write_bytes(original.replace(b"\r\n", b"\n"))
    problems = freeze.verify(layout.planning_home, layout.project_root, layout.docs_dir, read_only=True)
    assert any("tampered" in detail for _path, detail in problems)
    assert (layout.planning_home / ".freeze.yaml").read_bytes() == manifest_before
    saved.write_bytes(original)
    assert freeze.verify(layout.planning_home, layout.project_root, layout.docs_dir, read_only=True) == []

    markdown = _canonical(layout.planning_home, "separate", "1.0.0")
    _write(markdown, b"# Approved text\r\n\r\nStable semantic content.\r\n")
    freeze.record(layout.planning_home, layout.project_root, markdown)
    markdown.write_bytes(markdown.read_bytes().replace(b"\r\n", b"\n"))
    assert freeze.verify(layout.planning_home, layout.project_root, layout.docs_dir, read_only=True) == []


def _create_real_windows_junction(link: Path, target: Path) -> None:
    if os.name != "nt":
        pytest.skip("NT directory-junction case requires an actual Windows runtime")
    link.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                            capture_output=True, text=True, errors="replace")
    assert result.returncode == 0, f"actual junction creation failed: {result.stdout} {result.stderr}"
    assert link.resolve() == target.resolve()


def test_windows_version_directory_junction_cannot_make_proof_delete_external_user_files(
        make_project, write_leaf, monkeypatch, tmp_path, capsys):
    if os.name != "nt":
        pytest.skip("NT directory-junction case requires an actual Windows runtime")
    layout = _two_frozen_versions(make_project, write_leaf, monkeypatch)
    assert cli.main(["export", "guide"]) == 0
    original = _version_root(layout.planning_home, "guide", "1.0.1")
    outside = tmp_path / "external-version-target"
    original.rename(outside)
    _write(outside / "proof" / "user_document.txt", b"External user files must survive proof.\r\n")
    _create_real_windows_junction(original, outside)
    try:
        before_external = _files(outside)
        before_docs = _files(layout.docs_dir)
        capsys.readouterr()
        assert cli.main(["proof", "guide", "--version", "1.0.1"]) == 1
        message = capsys.readouterr()
        assert "unknown command" not in (message.out + message.err).lower()
        assert _files(outside) == before_external
        assert _files(layout.docs_dir) == before_docs
    finally:
        # rmdir removes this junction entry only; never recursively traverse its external target.
        assert original.resolve() == outside.resolve()
        original.rmdir()


def test_windows_snapshot_asset_junction_cannot_feed_external_assets_into_journal_export(
        make_project, write_leaf, monkeypatch, tmp_path, capsys):
    if os.name != "nt":
        pytest.skip("NT directory-junction case requires an actual Windows runtime")
    layout, saved = _frozen_blue_image(make_project, write_leaf, monkeypatch)
    assets = saved.parent
    outside = tmp_path / "external-image-assets"
    outside.mkdir()
    _write(outside / "diagram.png", saved.read_bytes())
    _write(outside / "user_document.txt", b"Unrelated external user material.")
    saved.chmod(stat.S_IREAD | stat.S_IWRITE)
    saved.unlink()
    assets.rmdir()
    _create_real_windows_junction(assets, outside)
    try:
        before_external = _files(outside)
        before_docs = _files(layout.docs_dir)
        before_manifest = (layout.planning_home / ".freeze.yaml").read_bytes()
        capsys.readouterr()
        assert cli.main(["export", "guide", "--journal", "ieee"]) == 1
        message = capsys.readouterr()
        assert "unknown command" not in (message.out + message.err).lower()
        assert _files(outside) == before_external
        assert _files(layout.docs_dir) == before_docs
        assert (layout.planning_home / ".freeze.yaml").read_bytes() == before_manifest
    finally:
        assert assets.resolve() == outside.resolve()
        assets.rmdir()


def test_windows_proof_output_junction_cannot_delete_external_user_files(
        make_project, write_leaf, monkeypatch, tmp_path, capsys):
    if os.name != "nt":
        pytest.skip("NT directory-junction case requires an actual Windows runtime")
    layout = _two_frozen_versions(make_project, write_leaf, monkeypatch)
    assert cli.main(["export", "guide"]) == 0
    output = layout.version_proof("guide", "1.0.1")
    outside = tmp_path / "external-proof-output"
    outside.mkdir()
    _write(outside / "user_document.txt", b"Existing external user material must not be deleted.")
    _create_real_windows_junction(output, outside)
    try:
        before_external = _files(outside)
        before_docs = _files(layout.docs_dir)
        capsys.readouterr()
        assert cli.main(["proof", "guide", "--version", "1.0.1"]) == 1
        message = capsys.readouterr()
        assert "unknown command" not in (message.out + message.err).lower()
        assert _files(outside) == before_external
        assert _files(layout.docs_dir) == before_docs
    finally:
        assert output.resolve() == outside.resolve()
        output.rmdir()


def test_unchanged_markdown_and_image_are_still_a_noop_in_dry_run_and_freeze(
        make_project, write_leaf, monkeypatch):
    layout, _saved = _frozen_blue_image(make_project, write_leaf, monkeypatch)
    before = _files(layout.project_root)
    assert cli.main(["freeze", "guide", "--dry-run"]) == 1
    assert _files(layout.project_root) == before
    assert cli.main(["freeze", "guide"]) == 1
    assert layout.existing_versions("guide") == [(1, 0, 0)]
    assert _files(layout.project_root) == before


def test_image_only_change_can_freeze_a_new_version_and_retains_the_previous_image(
        make_project, write_leaf, monkeypatch):
    from PIL import Image

    layout, previous_image = _frozen_blue_image(make_project, write_leaf, monkeypatch)
    previous_image_bytes = previous_image.read_bytes()
    previous_md = _canonical(layout.planning_home, "guide", "1.0.0").read_bytes()
    working = layout.docs_assets_dir("guide") / "diagram.png"
    Image.new("RGB", (20, 20), "red").save(working)
    new_image_bytes = working.read_bytes()
    assert new_image_bytes != previous_image_bytes
    before_preview = _files(layout.project_root)
    assert cli.main(["freeze", "guide", "--dry-run"]) == 0
    assert _files(layout.project_root) == before_preview
    assert cli.main(["freeze", "guide"]) == 0
    new_md = _canonical(layout.planning_home, "guide", "1.0.1")
    assert new_md.read_bytes() == previous_md, "the release change is only the referenced image"
    assert (new_md.parent / "assets" / "diagram.png").read_bytes() == new_image_bytes
    assert previous_image.read_bytes() == previous_image_bytes
    assert _canonical(layout.planning_home, "guide", "1.0.0").read_bytes() == previous_md
    assert layout.existing_versions("guide") == [(1, 0, 0), (1, 0, 1)]
    assert freeze.verify(layout.planning_home, layout.project_root, layout.docs_dir, read_only=True) == []


@pytest.mark.parametrize("payload,expected", [
    ({"tool_name": "Bash", "tool_input": {"command": "rm -rf docspec/changes/_versions"}}, 2),
    ({"tool_name": "Bash", "tool_input": {"command": "rm -rf docspec/changes/_versions/guide"}}, 2),
    ({"tool_name": "Bash", "tool_input": {"command": "rm -rf docspec/changes/_versions/guide/1.0.0"}}, 2),
    ({"tool_name": "Bash", "tool_input": {"command": "rm -f docspec/changes/_versions/guide/1.0.0/snapshot/document.md"}}, 2),
    ({"tool_name": "Write", "tool_input": {"file_path": "docspec/changes/_versions/guide/1.0.0/snapshot/document.md"}}, 2),
    ({"tool_name": "Write", "tool_input": {"file_path": "docspec/changes/_versions/guide/1.0.0/snapshot/assets/diagram.png"}}, 2),
    ({"tool_name": "Write", "tool_input": {"file_path": "docspec/changes/_versions/guide/1.0.0/exports/guide_v1.0.0.pdf"}}, 0),
    ({"tool_name": "Write", "tool_input": {"file_path": "docspec/changes/_versions/guide/1.0.0/proof/page_01.png"}}, 0),
    ({"tool_name": "Write", "tool_input": {"file_path": "docspec/changes/_versions/guide/_preview/exports/guide_vlatest.pdf"}}, 0),
    ({"tool_name": "Read", "tool_input": {"file_path": "docspec/changes/_versions"}}, 0),
    ({"tool_name": "Read", "tool_input": {"file_path": "docspec/changes/_versions/guide"}}, 0),
    ({"tool_name": "Read", "tool_input": {"file_path": "docspec/changes/_versions/guide/1.0.0"}}, 0),
], ids=[
    "delete-versions-root", "delete-article-root", "delete-version-root", "delete-snapshot",
    "write-snapshot", "write-frozen-image", "write-export", "write-proof", "write-preview",
    "read-versions-root", "read-article-root", "read-version-root",
])
def test_hook_stdin_protects_snapshot_ancestors_but_allows_outputs_and_reads(
        make_project, monkeypatch, payload, expected):
    layout = Layout(make_project())
    snap = _write(_canonical(layout.planning_home, "guide", "1.0.0"), b"# Protected history\n")
    freeze.record(layout.planning_home, layout.project_root, snap)
    monkeypatch.chdir(layout.project_root)
    before = _files(layout.project_root)
    data = {"cwd": str(layout.project_root), **payload}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(data)))
    # The destructive-looking strings are hook input only; no shell executes them.
    assert cli.main(["hook", "guard"]) == expected
    assert _files(layout.project_root) == before


def test_public_baseline_records_image_only_unfrozen_edits_and_clears_them_after_freeze(
        make_project, write_leaf, monkeypatch, capsys):
    from PIL import Image

    layout, _saved = _frozen_blue_image(make_project, write_leaf, monkeypatch)
    working = layout.docs_assets_dir("guide") / "diagram.png"
    Image.new("RGB", (20, 20), "red").save(working)
    assert cli.main(["baseline", "changed-image", "--by", "gpt"]) == 0
    capsys.readouterr()
    assert cli.main(["baseline", "show", "changed-image", "--json"]) == 0
    changed = json.loads(capsys.readouterr().out)
    assert changed["documents"]["guide"] == {"version": "1.0.0", "unfrozen-edits": True}

    assert cli.main(["freeze", "guide"]) == 0
    assert cli.main(["baseline", "frozen-image", "--by", "gpt"]) == 0
    capsys.readouterr()
    assert cli.main(["baseline", "show", "frozen-image", "--json"]) == 0
    final = json.loads(capsys.readouterr().out)
    assert final["documents"]["guide"] == {"version": "1.0.1", "unfrozen-edits": False}
    assert cli.main(["baseline", "show", "changed-image", "--json"]) == 0
    original_baseline = json.loads(capsys.readouterr().out)
    assert original_baseline["documents"]["guide"] == changed["documents"]["guide"], "prior baseline remains sealed history"


@pytest.mark.parametrize("face,changes_state", [
    ("version-proof", False),
    ("legacy-proof", False),
    ("preview-output", False),
    ("snapshot-asset", True),
    ("working-asset", True),
])
def test_handover_fingerprint_tracks_source_images_but_not_regenerated_version_artifacts(
        make_project, face, changes_state):
    from dspx.engine import handover as ho

    layout = Layout(make_project("language: en\ndocs_layout: flat\n"), "flat")
    snapshot = _write(_canonical(layout.planning_home, "guide", "1.0.0"),
                      b"# Approved guide\n\n![Diagram](assets/diagram.png)\n")
    freeze.record(layout.planning_home, layout.project_root, snapshot)
    _write(layout.docs_latest("guide"), b"# Current guide\n\n![Diagram](assets/diagram.png)\n")
    paths = {
        "version-proof": layout.version_proof("guide", "1.0.0") / "page_01.png",
        "legacy-proof": layout.planning_home / "changes" / "_versions" / "guide" / "_legacy-proof" / "unknown-digest" / "page_01.png",
        "preview-output": layout.version_proof("guide", "latest") / "page_01.png",
        "snapshot-asset": snapshot.parent / "assets" / "diagram.png",
        "working-asset": layout.docs_assets_dir("guide") / "diagram.png",
    }
    target = _write(paths[face], b"original artifact or source image bytes\x00\xff")
    before = ho.state_fingerprint(layout)
    target.write_bytes(b"changed artifact or source image bytes\x00\xff")
    after = ho.state_fingerprint(layout)
    assert (before != after) is changes_state
