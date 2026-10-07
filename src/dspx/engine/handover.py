"""交接單（2026/09/30 裁定）：一份、每次整份重寫。

現況（進度、失敗、缺漏）由 roadmap 與各項紀錄推導，不寫在這裡；交接單只記系統推導不出來的事：
這段做了什麼、進行中的事（派了誰、在等誰）、答應使用者的事、要注意的事、下一步。
做完的事不需要留，所以每次交接都整份重寫，不追加、不會越寫越長。
存在 `docspec/governance/handover.yaml`，封條保護，只能用 `artispec handover write` 改。
"""

from __future__ import annotations

import datetime
import hashlib
import os
from pathlib import Path

import yaml

from dspx.engine import governance as gv
from dspx.engine.layout import Layout
from dspx.engine.model import ModelError
from dspx.engine.store import atomic_write_store

FIELDS = ("done", "in-progress", "promises", "cautions", "next")
_KIND = "handover"
STATE_VERSION = 1
_IGNORED_DIRS = {"preview", "previews", "cache", ".cache", "__pycache__", ".pytest_cache",
                 "exports", "tmp", ".git"}
_IGNORED_SUFFIXES = {".pdf", ".pyc", ".tmp", ".bak"}


def path(layout: Layout) -> Path:
    return gv.gov_dir(layout) / "handover.yaml"


def load(layout: Layout) -> dict | None:
    p = path(layout)
    if not p.is_file():
        return None
    return gv.load_record(p, _KIND)


def _tree_files(root: Path, *, skip_archive: bool = False, skip_version_outputs: bool = False):
    """Only walk explicitly managed roots. Never follow a linked external repository."""
    if not root.exists():
        return
    def unreadable(exc):
        raise exc
    for folder, dirs, files in os.walk(root, followlinks=False, onerror=unreadable):
        dirs[:] = sorted(d for d in dirs if d not in _IGNORED_DIRS
                         and not (skip_archive and d == "_archive"))
        if skip_version_outputs:
            relative = Path(folder).relative_to(root).parts
            if relative and relative[0] == "_versions":
                if len(relative) == 2:
                    dirs[:] = [d for d in dirs if d not in ("_preview", "_legacy-proof")]
                elif len(relative) == 3 and relative[1] != "_legacy":
                    dirs[:] = [d for d in dirs if d != "proof"]
        for name in sorted(files):
            p = Path(folder) / name
            if p.suffix.lower() not in _IGNORED_SUFFIXES and ".tmp." not in name:
                yield p


def _managed_files(layout: Layout) -> list[Path]:
    from dspx.engine.software import io
    home = layout.planning_home
    roots = [gv.gov_dir(layout), layout.corpus_dir, home / ".ledger",
             home / "baselines", io.specs_dir(layout), io.evidence_dir(layout), io.baselines_dir(layout)]
    files = {p for root in roots for p in _tree_files(root)}
    files.update(_tree_files(home / "changes", skip_version_outputs=True))
    files.update(_tree_files(io.legacy_changes_dir(layout), skip_archive=True))
    # Project configuration and document-wide sources also affect the managed state.
    files.update(p for p in home.glob("*") if p.is_file()
                 and p.suffix.lower() in (".yaml", ".yml", ".md"))
    if io.config_path(layout).is_file():
        files.add(io.config_path(layout))
    files.update(_tree_files(layout.docs_assets_dir()))
    for article in layout.articles():
        files.update(_tree_files(layout.docs_assets_dir(article)))
        for p in (layout.docs_latest(article), layout.docs_ledger_legacy(article)):
            if p.is_file():
                files.add(p)
        for version in layout.existing_versions(article):
            files.add(layout.docs_snapshot(article, ".".join(map(str, version))))
    files.discard(path(layout))
    return sorted(files, key=lambda p: p.relative_to(layout.project_root).as_posix())


def _checked_content(p: Path, layout: Layout, *, article_stores: set[Path]) -> bytes:
    """An unreadable or broken sealed record must never establish a 'current' note."""
    content = p.read_bytes()
    # The managed path determines the schema. Missing identifying fields must not
    # turn a damaged article store into an arbitrary, apparently readable YAML file.
    if p in article_stores:
        from dspx.engine.store import load_article
        load_article(p)
        return content
    if p.suffix.lower() not in (".yaml", ".yml"):
        return content
    raw = yaml.safe_load(content.decode("utf-8"))
    relative = p.relative_to(layout.planning_home) if p.is_relative_to(layout.planning_home) else None
    if relative is not None and relative.parts[0] == gv.GOV_DIR_NAME:
        expected_kind = gv.kind_of_id(p.stem)
        if expected_kind:
            gv.load_record(p, expected_kind)
            return content
    if relative is not None and len(relative.parts) > 2 and relative.parts[0] == "software":
        if relative.parts[1] in ("specs", "evidence", "baselines", "changes"):
            if (not isinstance(raw, dict) or "body" not in raw
                    or not str(raw.get("kind", "")).startswith("software-")):
                raise gv.GovernanceError(f"malformed software record: {p}")
    if relative is not None and relative.parts[0] == "changes" and len(relative.parts) >= 3:
        start = 2 if relative.parts[1] in ("_archive", "_abandoned") else 1
        folder = layout.planning_home.joinpath(*relative.parts[:start + 1])
        inner = relative.parts[start + 1:]
        if (folder / "proposal.yaml").is_file() and inner:
            expected = ("delta" if inner[0] == "specs" else
                        Path(inner[0]).stem if len(inner) == 1 else None)
            if expected in ("proposal", "design", "tests", "tasks", "delta"):
                from dspx.engine.software import io
                io.load(p, expected)
                return content
    if raw is not None and not isinstance(raw, (dict, list)):
        raise gv.GovernanceError(f"malformed managed record: {p}")
    if not isinstance(raw, dict):
        return content
    kind = str(raw.get("kind") or "")
    if kind.startswith("governance-"):
        gv.load_record(p, kind[len("governance-"):])
    elif kind.startswith("software-"):
        from dspx.engine.software import io
        io.load(p, kind[len("software-"):])
    elif kind.startswith("baseline-"):
        from dspx.engine import project_baseline as pb
        pb._load(p, kind[len("baseline-"):])
    elif "article" in raw and "sections" in raw and "format" in raw:
        from dspx.engine.store import article_from_dict
        article_from_dict(raw, p)
    elif kind and "scope" in raw:
        from dspx.engine.sealed import load_sealed
        payload = [k for k in raw if k not in ("format", "kind", "scope", "revision", "integrity")]
        if len(payload) == 1:
            key = payload[0]
            load_sealed(p, list_key=key, error_cls=gv.GovernanceError)
    return content


def _manifest_fingerprint(files: dict[str, str]) -> str:
    """Keep the v1 aggregate byte-for-byte compatible with pre-manifest notes."""
    digest = hashlib.sha256(f"handover-state-v{STATE_VERSION}\n".encode())
    for path, fingerprint in sorted(files.items()):
        name = path.encode("utf-8")
        digest.update(len(name).to_bytes(8, "big"))
        digest.update(name)
        digest.update(bytes.fromhex(fingerprint.removeprefix("sha256:")))
    return "sha256:" + digest.hexdigest()


def state_snapshot(layout: Layout) -> tuple[str, dict]:
    """Collect checked bytes once; both fingerprints describe the same read."""
    from dspx.engine.store import store_articles, store_path
    article_stores = {store_path(layout, article) for article in store_articles(layout)}
    files = {}
    for p in _managed_files(layout):
        content = _checked_content(p, layout, article_stores=article_stores)
        files[p.relative_to(layout.project_root).as_posix()] = "sha256:" + hashlib.sha256(content).hexdigest()
    return _manifest_fingerprint(files), {"version": 1, "files": files}


def state_fingerprint(layout: Layout) -> str:
    return state_snapshot(layout)[0]


def _manifest_files(note: dict) -> dict[str, str] | None:
    manifest = note.get("state-manifest")
    if not isinstance(manifest, dict) or manifest.get("version") != 1:
        return None
    files = manifest.get("files")
    if not isinstance(files, dict):
        return None
    for name, fingerprint in files.items():
        if (not isinstance(name, str) or not name or name.startswith("/")
                or "\\" in name or ":" in name or any(part in ("", ".", "..") for part in name.split("/"))
                or not isinstance(fingerprint, str) or not fingerprint.startswith("sha256:")
                or len(fingerprint) != 71 or any(c not in "0123456789abcdef" for c in fingerprint[7:])):
            return None
    # A sealed but inconsistent/unsupported manifest cannot explain the old aggregate.
    if _manifest_fingerprint(files) != note.get("state-fingerprint"):
        return None
    return files


def freshness(layout: Layout, note: dict | None) -> dict:
    result = {"status": "unknown", "version": STATE_VERSION,
              "changes-available": False, "changes": [],
              "changes-reason": "缺少可比較的檔案明細，無法列出變動 (change details unavailable)",
              "next": "artispec roadmap; artispec handover write"}
    if not note or note.get("state-version") != STATE_VERSION or not note.get("state-fingerprint"):
        return {**result, "reason": "交接單未記錄可比較的狀態，無法確認新鮮度；下次交接請整份重寫 "
                "(no comparable state; freshness unknown)"}
    try:
        current, manifest = state_snapshot(layout)
    except (OSError, UnicodeError, ValueError, TypeError, ModelError, yaml.YAMLError) as exc:
        return {**result, "changes-reason": "紀錄無法讀取，無法列出完整變動 (change details unavailable)",
                "reason": f"紀錄無法讀取，無法確認交接新鮮度 (cannot confirm freshness): {exc}"}
    previous = _manifest_files(note)
    if previous is not None:
        files = manifest["files"]
        result.update({"changes-available": True, "changes-reason": None,
                       "changes": [{"path": name, "kind": "added" if name not in previous else
                                    "removed" if name not in files else "modified"}
                                   for name in sorted(previous.keys() | files.keys())
                                   if previous.get(name) != files.get(name)]})
    if current != note["state-fingerprint"]:
        return {**result, "status": "stale", "reason": "交接後專案紀錄已變動，交接單可能過時 "
                "(managed records changed; handover may be stale)"}
    return {**result, "status": "current", "reason": "受管理紀錄與交接時相同 (managed records unchanged)"}


def write(layout: Layout, note: dict, *, tool: str) -> Path:
    body = {k: [str(x).strip() for x in note.get(k) or [] if str(x).strip()] for k in FIELDS}
    if not any(body.values()):
        raise gv.GovernanceError("the handover note is empty — write at least what is in progress "
                                 "or what comes next")
    record = {"written-by": tool,
              "written-at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
              "state-version": STATE_VERSION, **{k: v for k, v in body.items() if v}}
    try:
        record["state-fingerprint"], record["state-manifest"] = state_snapshot(layout)
    except (OSError, UnicodeError, ValueError, TypeError, ModelError, yaml.YAMLError) as exc:
        # Keep the requested handover even when another domain needs repair; never label it fresh.
        record["state-error"] = str(exc)
    p = path(layout)
    p.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_store(p, gv.dump_record(_KIND, record))
    return p
