"""Independent regression: freeze must preflight the history write target."""

from __future__ import annotations

import errno
import hashlib
import json
from pathlib import Path

import pytest

from dspx import cli
from dspx.engine.layout import Layout


def _written_document(make_project, write_leaf, monkeypatch, docs_layout: str) -> Layout:
    home = make_project(f"language: en\ndocs_layout: {docs_layout}\n")
    layout = Layout(home, docs_layout)
    write_leaf(home, "guide/Operation", concept={
        "id": "c-guide-operation", "title": "Operation", "order": 1,
    })
    monkeypatch.chdir(layout.project_root)
    assert cli.main(["render", "guide"]) == 0
    latest = layout.docs_latest("guide")
    latest.write_text(latest.read_text(encoding="utf-8") + "Approved instructions.\n",
                      encoding="utf-8", newline="\n")
    assert cli.main(["render", "guide"]) == 0
    return layout


def _fingerprints(directory: Path) -> dict[str, str]:
    return {p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in directory.rglob("*") if p.is_file()} if directory.exists() else {}


def _file_symlink(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target)
    except OSError as exc:
        if exc.errno in (errno.EPERM, errno.EACCES, errno.ENOSYS) or getattr(exc, "winerror", None) == 1314:
            pytest.skip(f"real file symlinks unavailable in this environment: {exc}")
        raise
    assert link.is_symlink()
    assert link.resolve() == target.resolve()


@pytest.mark.parametrize("docs_layout", ["flat", "per-article"])
@pytest.mark.parametrize("has_previous_version", [False, True], ids=["first-freeze", "next-freeze"])
@pytest.mark.parametrize("target_scope", ["outside-project", "inside-project"])
def test_freeze_rejects_history_file_symlink_before_creating_version(
        make_project, write_leaf, monkeypatch, tmp_path,
        docs_layout, has_previous_version, target_scope):
    layout = _written_document(make_project, write_leaf, monkeypatch, docs_layout)
    history = layout.docs_changelog("guide")
    if has_previous_version:
        assert cli.main(["freeze", "guide"]) == 0
        assert history.is_file()
        history.unlink()
        latest = layout.docs_latest("guide")
        latest.write_text(latest.read_text(encoding="utf-8") + "A real content revision.\n",
                          encoding="utf-8", newline="\n")
    else:
        history.parent.mkdir(parents=True, exist_ok=True)

    target = ((tmp_path / "another-project" / "owner-notes.md") if target_scope == "outside-project"
              else (layout.project_root / "owner-notes.md"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"Owner file: never append document history here.\r\n")
    original_target = target.read_bytes()
    _file_symlink(history, target)
    new_version = "1.0.1" if has_previous_version else "1.0.0"
    new_snapshot = layout.version_snapshot("guide", new_version)
    baseline_directory = layout.planning_home / "baselines"
    baseline_before = _fingerprints(baseline_directory)
    manifest = layout.planning_home / ".freeze.yaml"
    manifest_before = manifest.read_bytes() if manifest.exists() else None

    result = cli.main(["freeze", "guide"])
    observed = {
        "exit": result,
        "target_bytes_preserved": target.read_bytes() == original_target,
        "new_snapshot_absent": not new_snapshot.exists(),
        "baselines_preserved": _fingerprints(baseline_directory) == baseline_before,
        "manifest_preserved": (manifest.read_bytes() if manifest.exists() else None) == manifest_before,
        "history_remains_symlink": history.is_symlink(),
    }
    expected = {"exit": 1, "target_bytes_preserved": True, "new_snapshot_absent": True,
                "baselines_preserved": True, "manifest_preserved": True,
                "history_remains_symlink": True}
    assert observed == expected, json.dumps(observed, indent=2)


@pytest.mark.parametrize("docs_layout", ["flat", "per-article"])
def test_regular_history_allows_first_and_next_freeze(
        make_project, write_leaf, monkeypatch, docs_layout):
    layout = _written_document(make_project, write_leaf, monkeypatch, docs_layout)
    assert cli.main(["freeze", "guide"]) == 0
    history = layout.docs_changelog("guide")
    original_history = history.read_bytes()
    latest = layout.docs_latest("guide")
    latest.write_text(latest.read_text(encoding="utf-8") + "A real content revision.\n",
                      encoding="utf-8", newline="\n")
    assert cli.main(["freeze", "guide"]) == 0
    assert history.read_bytes().startswith(original_history)
    assert layout.version_snapshot("guide", "1.0.1").is_file()


def test_freeze_rejects_existing_history_directory_before_creating_version(
        make_project, write_leaf, monkeypatch):
    layout = _written_document(make_project, write_leaf, monkeypatch, "flat")
    history = layout.docs_changelog("guide")
    history.mkdir(parents=True)
    marker = history / "owner-notes.txt"
    marker.write_bytes(b"Existing user directory: preserve all contents.\r\n")
    before = _fingerprints(history)
    baseline_before = _fingerprints(layout.planning_home / "baselines")
    assert cli.main(["freeze", "guide"]) == 1
    assert _fingerprints(history) == before
    assert history.is_dir()
    assert not layout.version_snapshot("guide", "1.0.0").exists()
    assert not (layout.planning_home / ".freeze.yaml").exists()
    assert _fingerprints(layout.planning_home / "baselines") == baseline_before
