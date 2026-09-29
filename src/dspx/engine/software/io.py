"""軟體領域的路徑與封條讀寫（與治理層同一套紀律：canonical dump＋integrity 封條＋原子寫）。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from dspx.engine.layout import Layout
from dspx.engine.model import ModelError
from dspx.engine.sealed import integrity_of
from dspx.engine.store import _yaml_dump, atomic_write_store

SOFTWARE_DIR = "software"
FORMAT_VERSION = 1
ARCHIVE_DIR = "_archive"          # 不叫 archive：docspec 的凍結區只認 docs/…/archive/


class SoftwareError(ModelError):
    """軟體領域操作失敗（沿用 ModelError 的 fail-loud／CLI 友善錯誤路徑）。"""


# ── 路徑 ─────────────────────────────────────────────────────────────────

def root(layout: Layout) -> Path:
    return layout.planning_home / SOFTWARE_DIR


def specs_dir(layout: Layout) -> Path:
    return root(layout) / "specs"


def spec_path(layout: Layout, capability: str) -> Path:
    return specs_dir(layout) / f"{capability}.yaml"


def changes_dir(layout: Layout) -> Path:
    return root(layout) / "changes"


def change_dir(layout: Layout, cid: str) -> Path:
    return changes_dir(layout) / cid


def archive_dir(layout: Layout) -> Path:
    return changes_dir(layout) / ARCHIVE_DIR


def evidence_dir(layout: Layout) -> Path:
    return root(layout) / "evidence"


def baselines_dir(layout: Layout) -> Path:
    return root(layout) / "baselines"


def config_path(layout: Layout) -> Path:
    return root(layout) / "config.yaml"


def has_software(layout: Layout) -> bool:
    return root(layout).is_dir()


# ── 封條讀寫 ─────────────────────────────────────────────────────────────

def _seal(kind: str, body) -> str:
    return integrity_of(f"software-{kind}", "project", FORMAT_VERSION, "body", body)


def dump(kind: str, body) -> str:
    header = (f"# docspec software {kind} — engine-owned; never edit by hand.\n"
              f"# Change it through `docspec code …`; a hand-edit breaks the integrity seal.\n")
    return header + _yaml_dump({"format": FORMAT_VERSION, "kind": f"software-{kind}",
                                "integrity": _seal(kind, body), "body": body})


def write(path: Path, kind: str, body) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_store(path, dump(kind, body))


def load(path: Path, kind: str):
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SoftwareError(f"not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise SoftwareError(f"YAML parse failed: {path}") from exc
    if not isinstance(raw, dict) or "body" not in raw:
        raise SoftwareError(f"malformed software {kind} file (missing `body`): {path}")
    if raw.get("kind") != f"software-{kind}":
        raise SoftwareError(f"{path} is not a software {kind} file (kind={raw.get('kind')})")
    if raw.get("integrity") != _seal(kind, raw["body"]):
        raise SoftwareError(f"integrity seal mismatch: {path} — the file was edited by hand. Restore it "
                            f"(e.g. `git checkout -- {path.name}` in its folder) and make the change "
                            f"through `docspec code …`; hand edits cannot be adopted.")
    return raw["body"]


def fingerprint(obj) -> str:
    body = json.dumps(obj, sort_keys=True, ensure_ascii=False)
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def as_list(v) -> list:
    if v is None:
        return []
    return [str(x) for x in (v if isinstance(v, list) else [v])]
