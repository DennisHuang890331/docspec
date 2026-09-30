"""專案基線（系統設計 SR10；2026/09/30 裁定甲、乙都做）。

回答「文件第三版描述的是哪個規格、哪個 commit」這類問題：

- 甲、文件定版時自動記下：`docspec freeze` 每凍結一個文件版本，就寫一筆
  `docspec/baselines/documents/<文件>@<版本>.yaml`：當下每份軟體規格的內容指紋、各程式 repo 的 commit、
  進行中的軟體 change、有效的專案決策。
- 乙、交付時一次釘住整個專案：`docspec baseline <名稱>` 寫 `docspec/baselines/<名稱>.yaml`：
  所有文件目前的定版版本（以及工作版本是否有尚未定版的修改）、軟體規格、各 repo 的 commit、
  有效決策、進行中的 change（文件與軟體）。

紀錄一筆一檔、封條保護，只由指令寫入，寫了就不改（名稱不可重複）。
"""

from __future__ import annotations

import datetime
import re
from pathlib import Path

import yaml

from dspx.engine.layout import Layout
from dspx.engine.model import ModelError
from dspx.engine.sealed import integrity_of
from dspx.engine.store import _yaml_dump, atomic_write_store

BASE_DIR = "baselines"
DOC_DIR = "documents"
FORMAT_VERSION = 1
_BAD_NAME = re.compile(r"[\\/\s]|^\.|^_")


class BaselineError(ModelError):
    """專案基線操作失敗。"""


def root(layout: Layout) -> Path:
    return layout.planning_home / BASE_DIR


def _seal(kind: str, body) -> str:
    return integrity_of(f"baseline-{kind}", "project", FORMAT_VERSION, "body", body)


def _write(path: Path, kind: str, body: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = (f"# docspec project baseline ({kind}) — engine-owned; never edit by hand.\n"
            + _yaml_dump({"format": FORMAT_VERSION, "kind": f"baseline-{kind}",
                          "integrity": _seal(kind, body), "body": body}))
    atomic_write_store(path, text)


def _load(path: Path, kind: str) -> dict:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise BaselineError(f"cannot read baseline {path}: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("kind") != f"baseline-{kind}" or "body" not in raw:
        raise BaselineError(f"{path} is not a {kind} baseline")
    if raw.get("integrity") != _seal(kind, raw["body"]):
        raise BaselineError(f"integrity seal mismatch: {path} — baselines are written once by docspec "
                            f"and never edited")
    return raw["body"]


def _now() -> str:
    return datetime.datetime.now().replace(microsecond=0).isoformat()


# ── 目前狀態的快照 ─────────────────────────────────────────────────────────

def software_state(layout: Layout) -> dict:
    """軟體規格指紋、各 repo commit、進行中的軟體 change。沒有軟體領域時只記專案 repo 的 commit。"""
    from dspx.engine.software import changes as swc
    from dspx.engine.software import evidence as ev
    from dspx.engine.software import io as swio
    from dspx.engine.software import specs as sp
    out: dict = {}
    repos = {"project": ev._git(layout.project_root, "rev-parse", "HEAD")}
    if swio.has_software(layout):
        try:
            out["specs"] = {cap: swio.fingerprint(spec) for cap, spec in sp.load_all(layout).items()}
        except swio.SoftwareError:
            out["specs"] = "unreadable (see docspec check)"
        for name, path in swc.repos(layout).items():
            repos[name] = ev._git(path, "rev-parse", "HEAD") if path.is_dir() else None
        dirty = {name: bool(ev._git(path, "status", "--porcelain")) for name, path in swc.repos(layout).items()
                 if path.is_dir() and ev._git(path, "rev-parse", "HEAD")}
        if any(dirty.values()):
            out["uncommitted-changes-in"] = sorted(k for k, v in dirty.items() if v)
        active = swc.list_active(layout)
        if active:
            out["active-changes"] = active
    out["repos"] = {k: v for k, v in repos.items() if v}
    return out


def governance_state(layout: Layout) -> dict:
    from dspx.engine import governance as gv
    if not gv.has_governance(layout):
        return {}
    try:
        gov = gv.load_governance(layout)
    except gv.GovernanceError:
        return {"decisions": "unreadable (see docspec check)"}
    return {"decisions": sorted(str(d["id"]) for d in gov.decisions
                                if gv.decision_effective_status(d, gov) == "active")}


def _latest_frozen(layout: Layout, article: str) -> str | None:
    versions = layout.existing_versions(article)
    return ".".join(str(p) for p in max(versions)) if versions else None


def _has_unfrozen_edits(layout: Layout, article: str, version: str | None) -> bool:
    from dspx.env.frontmatter import parse_frontmatter
    from dspx.engine.render import strip_anchor_bindings, strip_markers
    latest = layout.docs_latest(article)
    if not latest.is_file():
        return False
    if version is None:
        return True
    snap = layout.docs_snapshot(article, version)
    if not snap.is_file():
        return True
    _meta, body = parse_frontmatter(latest.read_text(encoding="utf-8"))
    clean = strip_anchor_bindings(strip_markers(body)).strip() + "\n"
    return clean != snap.read_text(encoding="utf-8").strip() + "\n"


# ── 甲：文件定版時自動記下 ───────────────────────────────────────────────────

def doc_record_path(layout: Layout, article: str, version: str) -> Path:
    return root(layout) / DOC_DIR / f"{article.replace('/', '__')}@{version}.yaml"


def record_doc_version(layout: Layout, article: str, version: str, *,
                       software_divergence: list[str] | None = None) -> Path | None:
    path = doc_record_path(layout, article, version)
    body = {"document": article, "version": version, "frozen-at": _now(),
            "software": software_state(layout), "governance": governance_state(layout)}
    if software_divergence:
        # 定版時仍落後於軟體需求的章節（差異記下、不擋定版）
        body["software-divergence"] = list(software_divergence)
    try:
        _write(path, "document", body)
    except OSError:
        return None
    return path.relative_to(layout.project_root)


def doc_version_record(layout: Layout, article: str, version: str) -> dict:
    path = doc_record_path(layout, article, version)
    if not path.is_file():
        raise BaselineError(f"no recorded state for \"{article}\" v{version} (versions frozen before "
                            f"this feature existed have none)")
    return _load(path, "document")


# ── 乙：交付時一次釘住整個專案 ───────────────────────────────────────────────

def project_path(layout: Layout, name: str) -> Path:
    return root(layout) / f"{name}.yaml"


def create(layout: Layout, leaves: list, name: str, *, note: str, tool: str) -> dict:
    name = name.strip()
    if not name or _BAD_NAME.search(name):
        raise BaselineError("baseline name must not be empty, contain spaces or slashes, or start "
                            "with '.' or '_'")
    path = project_path(layout, name)
    if path.exists():
        raise BaselineError(f"baseline \"{name}\" already exists; baselines are never overwritten")
    documents = {}
    warnings = []
    for article in sorted({lf.article for lf in leaves}):
        v = _latest_frozen(layout, article)
        unfrozen = _has_unfrozen_edits(layout, article, v)
        documents[article] = {"version": v, "unfrozen-edits": unfrozen}
        if v is None:
            warnings.append(f"document \"{article}\" has never been frozen")
        elif unfrozen:
            warnings.append(f"document \"{article}\" has edits after v{v} that are not frozen")
    from dspx.engine import change as doc_chg
    doc_active = doc_chg.active_change_ids(layout)
    sw = software_state(layout)
    if doc_active:
        warnings.append(f"document change(s) still open: {', '.join(doc_active)}")
    if sw.get("active-changes"):
        warnings.append(f"software change(s) still open: {', '.join(sw['active-changes'])}")
    if sw.get("uncommitted-changes-in"):
        warnings.append(f"uncommitted changes in: {', '.join(sw['uncommitted-changes-in'])} "
                        f"(the recorded commit does not include them)")
    body = {"name": name, "created-at": _now(), "created-by": tool, "documents": documents,
            "software": sw, "governance": governance_state(layout)}
    if note.strip():
        body["note"] = note.strip()
    if doc_active:
        body["open-document-changes"] = doc_active
    if warnings:
        body["warnings"] = warnings
    _write(path, "project", body)
    return body


def load(layout: Layout, name: str) -> dict:
    path = project_path(layout, name)
    if not path.is_file():
        raise BaselineError(f"no baseline \"{name}\" (see `docspec baseline list`)")
    return _load(path, "project")


def list_all(layout: Layout) -> list[dict]:
    d = root(layout)
    if not d.is_dir():
        return []
    out = []
    for p in sorted(d.glob("*.yaml")):
        try:
            b = _load(p, "project")
        except BaselineError:
            continue
        out.append({"name": b["name"], "created-at": b.get("created-at"), "note": b.get("note"),
                    "warnings": len(b.get("warnings") or [])})
    return sorted(out, key=lambda r: str(r["created-at"]))


def validate(layout: Layout) -> list[str]:
    """check：基線檔的封條完整。"""
    d = root(layout)
    if not d.is_dir():
        return []
    errs = []
    for p in sorted(d.glob("*.yaml")):
        try:
            _load(p, "project")
        except BaselineError as exc:
            errs.append(str(exc))
    for p in sorted((d / DOC_DIR).glob("*.yaml")) if (d / DOC_DIR).is_dir() else []:
        try:
            _load(p, "document")
        except BaselineError as exc:
            errs.append(str(exc))
    return errs
