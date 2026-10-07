"""明確、離線遷移受控資產；保留來源與目的既有內容。

只處理已知資產，不操作專案紀錄或未知根項目。此 API 用於停止其他
setup 程序後的單人升級，並非支援多個程序同時寫入的資料庫交易。
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

from dspx.engine import paths

ASSET_DIRECTORIES = ("tinytex", "fonts", "pandoc", "typst", "drawio", "cache")
ASSET_FILES = ("tex.lock", "update-cache.json")
_LOCK_PATHS = (
    "tinytex_root", "fonts_dir", "tlmgr_path", "xelatex_path",
    "pandoc_path", "typst_path", "drawio_path",
)


class MigrationError(ValueError):
    """來源不安全、內容改變或目的衝突；不應覆寫或部分發布。"""


@dataclass(frozen=True)
class _Entry:
    kind: str
    signature: tuple[int, ...]
    digest: str | None = None
    link: str | None = None
    directory_link: bool = False


def _signature(info: os.stat_result) -> tuple[int, ...]:
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns)


def _reparse(info: os.stat_result) -> bool:
    return bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _plain_directory_chain(path: Path) -> None:
    """先檢查每個存在的祖先，避免透過連結／Windows junction 寫到外面。"""
    for candidate in reversed((path, *path.parents)):
        try:
            info = candidate.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or _reparse(info):
            raise MigrationError(f"linked directory is not allowed: {candidate}")
        if not stat.S_ISDIR(info.st_mode):
            raise MigrationError(f"directory path conflicts with a file: {candidate}")


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_link(path: Path, root: Path) -> str:
    link = os.readlink(path)
    if Path(link).is_absolute():
        raise MigrationError(f"absolute link is not allowed: {path}")
    try:
        resolved = (path.parent / link).resolve()
    except (OSError, RuntimeError) as exc:
        raise MigrationError(f"invalid link: {path}: {exc}") from exc
    if not resolved.is_relative_to(root):
        raise MigrationError(f"link escapes the data directory: {path}")
    return link


def _entry(path: Path, root: Path) -> _Entry:
    before = path.lstat()
    signature = _signature(before)
    if stat.S_ISLNK(before.st_mode):
        return _Entry("link", signature, link=_safe_link(path, root),
                      directory_link=path.is_dir())
    if _reparse(before):
        raise MigrationError(f"unsupported reparse point: {path}")
    if stat.S_ISDIR(before.st_mode):
        return _Entry("directory", signature)
    if not stat.S_ISREG(before.st_mode):
        raise MigrationError(f"unsupported asset type: {path}")
    digest = _digest(path)
    if _signature(path.lstat()) != signature:
        raise MigrationError(f"source changed while reading: {path}")
    return _Entry("file", signature, digest=digest)


def _snapshot(source: Path) -> tuple[dict[str, _Entry], list[str]]:
    manifest: dict[str, _Entry] = {}
    selected = set(ASSET_DIRECTORIES + ASSET_FILES)
    names = sorted(item.name for item in source.iterdir())

    def visit(path: Path) -> None:
        entry = _entry(path, source)
        manifest[path.relative_to(source).as_posix()] = entry
        if entry.kind == "directory":
            for child in sorted(path.iterdir()):
                visit(child)
            if _signature(path.lstat()) != entry.signature:
                raise MigrationError(f"source directory changed while reading: {path}")

    for name in names:
        if name in selected:
            visit(source / name)
            kind = manifest[name].kind
            if name in ASSET_DIRECTORIES and kind not in ("directory", "link"):
                raise MigrationError(f"asset directory is not a directory: {source / name}")
            if name in ASSET_FILES and kind != "file":
                raise MigrationError(f"asset metadata is not a regular file: {source / name}")
    for relative, entry in manifest.items():
        if entry.kind == "link":
            destination = (source / relative).resolve()
            if destination.relative_to(source).as_posix() not in manifest:
                raise MigrationError(f"link target is not a selected managed asset: {source / relative}")
    return manifest, [name for name in names if name not in selected]


def _rebased_lock(source: Path, target: Path) -> tuple[bytes, list[dict]]:
    try:
        lock = json.loads((source / "tex.lock").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise MigrationError(f"invalid tex.lock: {source / 'tex.lock'}: {exc}") from exc
    if not isinstance(lock, dict):
        raise MigrationError("tex.lock must contain a JSON object")
    changes = []
    for key in _LOCK_PATHS:
        value = lock.get(key)
        if value is None:
            continue
        if not isinstance(value, str):
            raise MigrationError(f"tex.lock {key} must be a path string or null")
        old_path = Path(value)
        if old_path.is_absolute():
            normalized = Path(os.path.abspath(old_path))
            if normalized.is_relative_to(source):
                new_value = str(target / normalized.relative_to(source))
                lock[key] = new_value
                changes.append({"field": key, "before": value, "after": new_value})
    return (json.dumps(lock, ensure_ascii=False, indent=2) + "\n").encode("utf-8"), changes


def _preflight(target: Path, manifest: dict[str, _Entry], hashes: dict[str, str]) -> list[str]:
    _plain_directory_chain(target)
    missing = []
    for relative, expected in manifest.items():
        destination = target / relative
        _plain_directory_chain(destination.parent)
        if not os.path.lexists(destination):
            missing.append(relative)
            continue
        actual = _entry(destination, target)
        matches = actual.kind == expected.kind
        if expected.kind == "file":
            matches = matches and actual.digest == hashes[relative]
        elif expected.kind == "link":
            matches = matches and actual.link == expected.link
        if not matches:
            raise MigrationError(f"destination conflict (nothing overwritten): {destination}")
    return missing


def _mkdir_owned(directory: Path, created: list[Path]) -> None:
    if directory.is_dir():
        return
    _mkdir_owned(directory.parent, created)
    directory.mkdir()
    created.append(directory)


def _writable_owned_file(path: Path, root: Path) -> None:
    """Windows 無法刪唯讀檔；只調整本次建立的普通檔案，不跟隨 links。"""
    if os.name != "nt":
        return
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    if not stat.S_ISREG(info.st_mode) or _reparse(info) or info.st_mode & stat.S_IWRITE:
        return
    _plain_directory_chain(path.parent)
    if not path.resolve().is_relative_to(root.resolve()):
        raise MigrationError(f"owned file escapes cleanup root: {path}")
    path.chmod(info.st_mode | stat.S_IWRITE)


def migrate_legacy_data(source: str | Path | None = None,
                        target: str | Path | None = None) -> dict:
    """回傳 migrated／unchanged／missing 與逐檔 before/after SHA-256。

    全批預查後先複製到獨佔 staging、核對來源，再發布缺少項目。既有目的
    檔案完全不重寫；失敗只回復本次建立的檔案／空目錄。來源始終保留。
    """
    source = Path(os.path.abspath(source if source is not None else paths.legacy_data_dir()))
    target = Path(os.path.abspath(target if target is not None else paths.data_dir()))
    _plain_directory_chain(source)
    _plain_directory_chain(target)
    if source.is_relative_to(target) or target.is_relative_to(source):
        raise MigrationError(f"source and target must not overlap: {source}, {target}")
    result = {"source": str(source), "target": str(target), "status": "missing",
              "excluded": 0, "excluded_names": [], "items": [], "lock_paths": []}
    if not source.exists():
        return result

    manifest, excluded = _snapshot(source)
    result.update(excluded=len(excluded), excluded_names=excluded)
    lock_bytes = None
    hashes = {relative: entry.digest for relative, entry in manifest.items() if entry.kind == "file"}
    if "tex.lock" in manifest:
        lock_bytes, result["lock_paths"] = _rebased_lock(source, target)
        hashes["tex.lock"] = hashlib.sha256(lock_bytes).hexdigest()
    missing = _preflight(target, manifest, hashes)
    missing_set = set(missing)
    for relative, entry in manifest.items():
        result["items"].append({
            "path": relative, "source": str(source / relative), "target": str(target / relative),
            "kind": entry.kind, "before_sha256": entry.digest,
            "after_sha256": hashes.get(relative), "link": entry.link,
            "action": "created" if relative in missing_set else "unchanged",
        })
    result["status"] = "unchanged"
    if not missing:
        return result

    anchor = target
    while not anchor.is_dir():
        anchor = anchor.parent
    stage = Path(tempfile.mkdtemp(prefix=".artispec-migrate-", dir=anchor))
    stage_identity = stage.stat().st_dev, stage.stat().st_ino
    created_files: list[Path] = []
    created_dirs: list[Path] = []
    try:
        for relative in missing:
            entry = manifest[relative]
            staged = stage / relative
            staged.parent.mkdir(parents=True, exist_ok=True)
            if entry.kind == "directory":
                staged.mkdir(exist_ok=True)
            elif entry.kind == "link":
                staged.symlink_to(entry.link, target_is_directory=entry.directory_link)
            else:
                if relative == "tex.lock":
                    staged.write_bytes(lock_bytes)
                    shutil.copystat(source / relative, staged)
                else:
                    shutil.copy2(source / relative, staged)
                _writable_owned_file(staged, stage)
                if _digest(staged) != hashes[relative]:
                    raise MigrationError(f"staged asset verification failed: {source / relative}")
        if _snapshot(source)[0] != manifest:
            raise MigrationError("source changed during copy; nothing published")
        if _preflight(target, manifest, hashes) != missing:
            raise MigrationError("destination changed during copy; nothing published")
        for relative in missing:
            destination = target / relative
            entry = manifest[relative]
            _plain_directory_chain(destination.parent)
            _mkdir_owned(destination.parent, created_dirs)
            if entry.kind == "directory":
                _mkdir_owned(destination, created_dirs)
            elif entry.kind == "link":
                destination.symlink_to(entry.link, target_is_directory=entry.directory_link)
                created_files.append(destination)
            else:
                # 同 volume 的 hard link 是不覆寫的原子發布；staging 刪除後留下完整檔。
                os.link(stage / relative, destination)
                created_files.append(destination)
        if _snapshot(source)[0] != manifest:
            raise MigrationError("source changed during publication; rolling back created assets")
        result["status"] = "migrated"
        return result
    except BaseException:
        for destination in reversed(created_files):
            if destination.is_relative_to(target):
                _plain_directory_chain(destination.parent)
                _writable_owned_file(destination, target)
                destination.unlink()
        for directory in reversed(created_dirs):
            # 包含為 target 建立的缺少祖先；都是本次已明確追蹤的空目錄。
            _plain_directory_chain(directory)
            directory.rmdir()
        raise
    finally:
        # recursive cleanup 限於本次 mkdtemp 的同一目錄，不刪未知目的項目。
        info = stage.lstat()
        if ((info.st_dev, info.st_ino) == stage_identity
                and not stage.is_symlink() and stage.resolve().is_relative_to(anchor.resolve())):
            # copy2 若在設定來源 mode 後拋錯，也要清掉自有 staging 的唯讀 bit。
            for relative in missing:
                if manifest[relative].kind == "file":
                    _writable_owned_file(stage / relative, stage)
            shutil.rmtree(stage)
