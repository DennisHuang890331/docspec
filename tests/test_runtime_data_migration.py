"""安全離線資產遷移：只用臨時合成檔案，不操作使用者工具或專案證據。"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import stat
from pathlib import Path

import pytest

from dspx import cli
from dspx.commands.maintenance import setup as setup_cmd
from dspx.engine import paths


def _migration():
    return importlib.import_module("dspx.engine.runtime_data").migrate_legacy_data


def _write(root, relative, content):
    destination = root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)


def _snapshot(root):
    if not root.exists():
        return None
    result = {}
    for item in sorted(root.rglob("*")):
        key = item.relative_to(root).as_posix()
        if item.is_symlink():
            result[key] = ("link", os.readlink(item))
        elif item.is_dir():
            result[key] = ("dir",)
        else:
            result[key] = ("file", item.read_bytes(), item.stat().st_mtime_ns)
    return result


def _legacy_assets(source):
    assets = {
        "fonts/SourceSerif4-Regular.otf": b"synthetic-font\x00\xff",
        "tinytex/bin/windows/tlmgr.bat": b"synthetic-tlmgr",
        "tinytex/bin/windows/xelatex.exe": b"synthetic-xelatex",
        "pandoc/pandoc.exe": b"synthetic-pandoc",
        "typst/typst.exe": b"synthetic-typst",
        "drawio/draw.io.exe": b"synthetic-drawio",
        "cache/archive.zip": b"synthetic-cache",
        "update-cache.json": b'{"checked": 123, "tag": "synthetic"}',
    }
    for relative, content in assets.items():
        _write(source, relative, content)
    lock = {
        "tinytex_root": str(source / "tinytex"),
        "fonts_dir": str(source / "fonts"),
        "tlmgr_path": str(source / "tinytex/bin/windows/tlmgr.bat"),
        "xelatex_path": str(source / "tinytex/bin/windows/xelatex.exe"),
        "pandoc_path": str(source / "pandoc/pandoc.exe"),
        "typst_path": str(source / "typst/typst.exe"),
        "drawio_path": str(source / "drawio/draw.io.exe"),
        "platform": "synthetic-windows",
        "tinytex_tag": "v-synthetic",
        "fonts": ["SourceSerif4-Regular.otf"],
        "tlmgr_packages": ["synthetic-package"],
        "custom_path": str(source / "keep-this-string"),
        "custom": {"path": str(source / "also-keep-this-string")},
    }
    _write(source, "tex.lock", json.dumps(lock, ensure_ascii=False).encode())
    return assets, lock


def test_migration_preserves_source_and_copies_asset_bytes_rebases_only_known_lock_fields(tmp_path):
    source, target = tmp_path / "docspec", tmp_path / "artispec"
    assets, lock = _legacy_assets(source)
    _write(source, "unrelated/evidence.txt", b"keep source evidence")
    _write(target, "installers/new-installer.exe", b"keep target installer")
    source_before = _snapshot(source)
    installer_before = (target / "installers/new-installer.exe").stat().st_mtime_ns

    result = _migration()(source=source, target=target)

    assert isinstance(result, dict) and result["status"] == "migrated"
    assert result["excluded"] == 1
    assert _snapshot(source) == source_before
    assert not (target / "unrelated").exists()
    for relative, content in assets.items():
        assert (target / relative).read_bytes() == content
    migrated_lock = json.loads((target / "tex.lock").read_text("utf-8"))
    expected = dict(lock)
    for key in ("tinytex_root", "fonts_dir", "tlmgr_path", "xelatex_path", "pandoc_path", "typst_path", "drawio_path"):
        expected[key] = str(target / Path(lock[key]).relative_to(source))
    assert migrated_lock == expected
    assert (target / "installers/new-installer.exe").read_bytes() == b"keep target installer"
    assert (target / "installers/new-installer.exe").stat().st_mtime_ns == installer_before


def test_migration_repeat_is_noop_even_with_target_extra_files(tmp_path):
    source, target = tmp_path / "docspec", tmp_path / "artispec"
    _legacy_assets(source)
    _migration()(source=source, target=target)
    _write(target, "installers/new.exe", b"existing")
    before = _snapshot(target)
    assert _migration()(source=source, target=target)["status"] == "unchanged"
    assert _snapshot(target) == before


def test_partial_matching_target_merges_missing_files_without_rewriting_existing(tmp_path):
    source, target = tmp_path / "docspec", tmp_path / "artispec"
    assets, _ = _legacy_assets(source)
    relative = "fonts/SourceSerif4-Regular.otf"
    _write(target, relative, assets[relative])
    existing_mtime = (target / relative).stat().st_mtime_ns
    assert _migration()(source=source, target=target)["status"] == "migrated"
    assert (target / relative).stat().st_mtime_ns == existing_mtime
    for name, content in assets.items():
        assert (target / name).read_bytes() == content


def test_readonly_source_asset_migrates_successfully_without_changing_source_mode(tmp_path):
    source, target = tmp_path / "docspec", tmp_path / "artispec"
    assets, _ = _legacy_assets(source)
    relative = "fonts/SourceSerif4-Regular.otf"
    original = source / relative
    original.chmod(original.stat().st_mode & ~stat.S_IWRITE)
    original_mode = original.stat().st_mode
    before = _snapshot(source)
    try:
        assert _migration()(source=source, target=target)["status"] == "migrated"
        assert (target / relative).read_bytes() == assets[relative]
        assert _snapshot(source) == before
        assert original.stat().st_mode == original_mode
    finally:
        # 只放寬此合成測試檔案，讓 Windows pytest 可清理自己的 tmp。
        original.chmod(original.stat().st_mode | stat.S_IWRITE)
        if target.exists():
            for item in target.rglob("*"):
                if item.is_file() and not item.is_symlink():
                    item.chmod(item.stat().st_mode | stat.S_IWRITE)


def test_external_and_null_known_lock_paths_are_not_rewritten(tmp_path):
    source, target = tmp_path / "docspec", tmp_path / "artispec"
    _, lock = _legacy_assets(source)
    # source 字串前綴相同仍不是 source 子路徑，不能直接做字串 replace。
    lock["pandoc_path"] = str(tmp_path / "docspec-backup/pandoc")
    lock["drawio_path"] = None
    _write(source, "tex.lock", json.dumps(lock).encode())
    _migration()(source=source, target=target)
    migrated = json.loads((target / "tex.lock").read_text("utf-8"))
    assert migrated["pandoc_path"] == lock["pandoc_path"]
    assert migrated["drawio_path"] is None


def test_missing_source_reports_missing_without_creating_target(tmp_path):
    source, target = tmp_path / "missing-docspec", tmp_path / "artispec"
    assert _migration()(source=source, target=target)["status"] == "missing"
    assert not source.exists() and not target.exists()


@pytest.mark.parametrize("conflict", ["fonts/SourceSerif4-Regular.otf", "tex.lock", "typst"])
def test_all_conflicts_are_preflighted_without_partial_copy(tmp_path, conflict):
    source, target = tmp_path / "docspec", tmp_path / "artispec"
    _legacy_assets(source)
    _write(target, "installers/keep.exe", b"keep")
    _write(target, conflict, b"different destination bytes")
    before = (_snapshot(source), _snapshot(target))
    with pytest.raises(ValueError):
        _migration()(source=source, target=target)
    assert (_snapshot(source), _snapshot(target)) == before


@pytest.mark.parametrize("payload", [b"{broken json", b"[]", b"null", b'{"typst_path": 42}'])
def test_bad_lock_is_preflighted_without_partial_copy(tmp_path, payload):
    source, target = tmp_path / "docspec", tmp_path / "artispec"
    _legacy_assets(source)
    _write(source, "tex.lock", payload)
    _write(target, "installers/keep.exe", b"keep")
    before = (_snapshot(source), _snapshot(target))
    with pytest.raises(ValueError):
        _migration()(source=source, target=target)
    assert (_snapshot(source), _snapshot(target)) == before


@pytest.mark.parametrize("placement", ["same", "target_inside_source", "source_inside_target"])
def test_overlapping_roots_rejected_before_write(tmp_path, placement):
    source = tmp_path / "data"
    target = source if placement == "same" else source / "new"
    if placement == "source_inside_target":
        target, source = source, source / "old"
    _legacy_assets(source)
    before = _snapshot(tmp_path)
    with pytest.raises(ValueError):
        _migration()(source=source, target=target)
    assert _snapshot(tmp_path) == before


def _symlink(link, destination, *, directory=False):
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(destination, target_is_directory=directory)
    except OSError as exc:
        pytest.skip(f"test host cannot create symlinks: {exc}")


@pytest.mark.parametrize("side", ["source", "target"])
def test_external_links_rejected_without_touching_link_destination(tmp_path, side):
    source, target, external = tmp_path / "docspec", tmp_path / "artispec", tmp_path / "outside"
    _legacy_assets(source)
    external.mkdir()
    (external / "evidence").write_bytes(b"external bytes")
    if side == "source":
        _symlink(source / "fonts/external", external, directory=True)
    else:
        _symlink(target / "fonts", external, directory=True)
    before = _snapshot(tmp_path)
    with pytest.raises(ValueError):
        _migration()(source=source, target=target)
    assert _snapshot(tmp_path) == before


def test_relative_internal_tinytex_symlink_is_preserved(tmp_path):
    source, target = tmp_path / "docspec", tmp_path / "artispec"
    _write(source, "tinytex/bin/x86_64-linux/xetex", b"synthetic-engine")
    _symlink(source / "tinytex/bin/x86_64-linux/xelatex", "xetex")
    before = _snapshot(source)
    assert _migration()(source=source, target=target)["status"] == "migrated"
    link = target / "tinytex/bin/x86_64-linux/xelatex"
    assert link.is_symlink() and os.readlink(link) == "xetex"
    assert link.read_bytes() == b"synthetic-engine"
    assert _snapshot(source) == before


def test_link_to_excluded_source_content_is_rejected_before_write(tmp_path):
    source, target = tmp_path / "docspec", tmp_path / "artispec"
    _legacy_assets(source)
    _write(source, "unrelated/engine", b"excluded source content")
    _write(target, "installers/keep.exe", b"keep installer")
    _symlink(source / "tinytex/engine", "../unrelated/engine")
    before = (_snapshot(source), _snapshot(target))
    with pytest.raises(ValueError):
        _migration()(source=source, target=target)
    assert (_snapshot(source), _snapshot(target)) == before


@pytest.mark.parametrize("side", ["source", "target"])
def test_linked_root_or_ancestor_is_rejected_before_write(tmp_path, side):
    source, target = tmp_path / "docspec", tmp_path / "artispec"
    _legacy_assets(source)
    _write(target, "installers/keep.exe", b"keep installer")
    alias = tmp_path / "alias"
    if side == "source":
        _symlink(alias, source, directory=True)
        migration_source, migration_target = alias, target
    else:
        _symlink(alias, target, directory=True)
        migration_source, migration_target = source, alias / "new-root"
    before = _snapshot(tmp_path)
    with pytest.raises(ValueError):
        _migration()(source=migration_source, target=migration_target)
    assert _snapshot(tmp_path) == before


def test_source_mutation_during_copy_prevents_publish(tmp_path, monkeypatch):
    source, target = tmp_path / "docspec", tmp_path / "artispec"
    _legacy_assets(source)
    _write(target, "installers/keep.exe", b"keep")
    before = _snapshot(target)
    copy2 = shutil.copy2
    changed = []

    def mutate_after_copy(src, dst, *args, **kwargs):
        result = copy2(src, dst, *args, **kwargs)
        if not changed and Path(src).is_relative_to(source):
            changed.append(Path(src))
            Path(src).write_bytes(b"source changed while copying")
        return result

    monkeypatch.setattr(shutil, "copy2", mutate_after_copy)
    with pytest.raises(ValueError):
        _migration()(source=source, target=target)
    assert changed, "copy hook must exercise a real mid-copy source mutation"
    assert _snapshot(target) == before


def test_late_copy_error_prevents_partial_publish(tmp_path, monkeypatch):
    source, target = tmp_path / "docspec", tmp_path / "artispec"
    _legacy_assets(source)
    _write(target, "installers/keep.exe", b"keep")
    before = (_snapshot(source), _snapshot(target))
    copy2 = shutil.copy2
    copied = []

    def fail_after_one_copy(src, dst, *args, **kwargs):
        if copied:
            raise OSError("synthetic copy error")
        copied.append(Path(src))
        return copy2(src, dst, *args, **kwargs)

    monkeypatch.setattr(shutil, "copy2", fail_after_one_copy)
    with pytest.raises(OSError):
        _migration()(source=source, target=target)
    assert copied, "copy hook must exercise a real partial staging copy"
    assert (_snapshot(source), _snapshot(target)) == before


@pytest.mark.parametrize("readonly", [False, True])
def test_publish_error_rolls_back_new_files_and_preserves_existing_target(tmp_path, monkeypatch, readonly):
    source, target = tmp_path / "docspec", tmp_path / "artispec"
    assets, _ = _legacy_assets(source)
    _write(target, "installers/keep.exe", b"keep installer")
    _write(target, "fonts/SourceSerif4-Regular.otf", assets["fonts/SourceSerif4-Regular.otf"])
    original = source / "drawio/draw.io.exe"
    if readonly:
        original.chmod(original.stat().st_mode & ~stat.S_IWRITE)
    original_mode = original.stat().st_mode
    before = (_snapshot(source), _snapshot(target))
    link = os.link
    published = []

    def fail_after_one_publish(src, dst, *args, **kwargs):
        if published:
            raise OSError("synthetic publication failure")
        result = link(src, dst, *args, **kwargs)
        published.append(Path(dst))
        return result

    monkeypatch.setattr(os, "link", fail_after_one_publish)
    try:
        with pytest.raises(OSError, match="synthetic publication failure"):
            _migration()(source=source, target=target)
        assert published, "failure must occur after a new file has been published"
        assert (_snapshot(source), _snapshot(target)) == before
        assert original.stat().st_mode == original_mode
    finally:
        original.chmod(original.stat().st_mode | stat.S_IWRITE)


def _offline(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("migration must not download or install tools")

    monkeypatch.setattr(setup_cmd.urllib.request, "urlopen", unexpected)
    for name in ("_ensure_fonts", "_ensure_pandoc", "_ensure_typst", "_ensure_tinytex", "_ensure_drawio", "_ensure_packages", "_write_lock"):
        monkeypatch.setattr(setup_cmd, name, unexpected)


def test_setup_explicit_migration_only_is_offline_and_preserves_source(tmp_path, monkeypatch):
    source, target = tmp_path / "docspec", tmp_path / "artispec"
    _legacy_assets(source)
    before = _snapshot(source)
    monkeypatch.setattr(paths, "legacy_data_dir", lambda: source, raising=False)
    monkeypatch.setattr(paths, "data_dir", lambda: target)
    _offline(monkeypatch)
    assert cli.main(["setup", "--migrate-data"]) == 0
    assert (target / "typst/typst.exe").read_bytes() == b"synthetic-typst"
    assert _snapshot(source) == before


def test_setup_missing_legacy_reports_and_never_downloads(tmp_path, monkeypatch, capsys):
    source, target = tmp_path / "docspec", tmp_path / "artispec"
    monkeypatch.setattr(paths, "legacy_data_dir", lambda: source, raising=False)
    monkeypatch.setattr(paths, "data_dir", lambda: target)
    _offline(monkeypatch)
    assert cli.main(["setup", "--migrate-data"]) == 0
    out = capsys.readouterr()
    assert "missing" in (out.out + out.err).lower() or "not found" in (out.out + out.err).lower()
    assert not target.exists()


def test_setup_failed_migration_is_nonzero_and_preserves_both_roots(tmp_path, monkeypatch):
    source, target = tmp_path / "docspec", tmp_path / "artispec"
    _legacy_assets(source)
    _write(target, "typst/typst.exe", b"conflicting binary")
    before = (_snapshot(source), _snapshot(target))
    monkeypatch.setattr(paths, "legacy_data_dir", lambda: source, raising=False)
    monkeypatch.setattr(paths, "data_dir", lambda: target)
    _offline(monkeypatch)
    assert cli.main(["setup", "--migrate-data"]) == 1
    assert (_snapshot(source), _snapshot(target)) == before


@pytest.mark.parametrize("command", [["--help"], ["--version"], ["version"], ["doctor"]])
def test_read_only_commands_do_not_migrate_assets(tmp_path, monkeypatch, command):
    from dspx.commands.maintenance import version as version_cmd

    source, target = tmp_path / "docspec", tmp_path / "artispec"
    _legacy_assets(source)
    before = _snapshot(source)
    monkeypatch.setattr(paths, "legacy_data_dir", lambda: source, raising=False)
    monkeypatch.setattr(paths, "data_dir", lambda: target)
    for name in ("resolve_typst", "resolve_pandoc", "resolve_xelatex", "resolve_drawio", "resolve_fonts_dir"):
        monkeypatch.setattr(paths, name, lambda: None)
    monkeypatch.setattr(version_cmd, "_typst_version", lambda: "not installed")
    monkeypatch.setattr(version_cmd, "_pandoc_version", lambda: "not installed")
    monkeypatch.setattr(version_cmd, "_tinytex_version", lambda: "not installed")
    _offline(monkeypatch)
    cli.main(command)
    assert _snapshot(source) == before
    assert not target.exists()
