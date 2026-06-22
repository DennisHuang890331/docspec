"""section 模型層：掃 corpus 樹、載入每個末節的檔，攤平成記憶體模型。

引擎其餘部分（check / status / instructions / publish）都吃這層的輸出。
這裡只「忠實載入 + 容錯」，不做任何語義判斷。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from dspx.layout import Layout
from dspx.schema import Schema


class ModelError(Exception):
    """末節檔載入/解析失敗。"""


def _load_yaml(path: Path) -> object:
    if not path.is_file():
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        position = ""
        mark = getattr(exc, "problem_mark", None)
        if mark is not None:
            position = f" (line {mark.line + 1})"
        raise ModelError(f"YAML parse failed: {path}{position}") from exc


def decision_index(leaves: list) -> dict:
    """全專案決策索引：決策/history id → {section, statement, kind, status}。

    供 realizes 解析（跨文件撈共享真相）與 deps 指紋使用。
    """
    index: dict = {}
    for leaf in leaves:
        for e in leaf.decisions:
            if e.get("id"):
                index[str(e["id"])] = {"section": leaf.section, "statement": e.get("statement"),
                                       "kind": "decision", "status": e.get("status")}
        for e in leaf.history:
            if e.get("id"):
                index[str(e["id"])] = {"section": leaf.section, "statement": e.get("statement"),
                                       "kind": "history", "status": e.get("status")}
    return index


def realized_statements(leaf, dindex: dict) -> list:
    """本節 realizes 的決策（撈來源 statement）；跨文件。

    紀律：realizes 應指向真相最源頭（權威方的決策），故一跳即足。
    """
    out = []
    if leaf.concept is None:
        return out
    for rid in (leaf.concept.get("realizes") or []):
        rec = dindex.get(str(rid))
        if rec is not None:
            out.append({"id": str(rid), "statement": rec["statement"],
                        "from_section": rec["section"], "kind": rec["kind"]})
    return out


def deps_fingerprint(leaf, dindex: dict) -> str:
    """本節對「上游被 realizes 決策」的依賴指紋。

    只 hash statement（＝aperture 真正投給 draft 的東西）：改 rationale 不動 statement
    就不觸發下游重渲染。無 realizes → 空字串。
    """
    items = sorted((r["id"], r["statement"]) for r in realized_statements(leaf, dindex))
    if not items:
        return ""
    h = hashlib.sha256()
    for rid, stmt in items:
        h.update(json.dumps({"id": rid, "stmt": stmt}, ensure_ascii=False).encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()[:16]


def ancestor_brief_fingerprint(section: str, by_section: dict) -> str:
    """祖先節（不含自己）的 brief/concept 指紋。

    用於分辨 staleness 兩種：自己的檔沒變、但某祖先的 brief/concept 變了 →
    子節的 fingerprint 跟著變 → status 標 stale-inherited（交給 edit 做敘事性對齊）。
    父 brief 一改，所有子孫的 fingerprint 都變＝天然傳播，不需額外傳播碼。
    """
    parts = [p for p in section.split("/") if p]
    h = hashlib.sha256()
    for i in range(1, len(parts)):                 # 只取祖先前綴，不含自己
        anc = "/".join(parts[:i])
        leaf = by_section.get(anc)
        if leaf is not None and leaf.concept is not None:
            inherited = {
                "concept": leaf.concept.get("concept"),
                "brief": leaf.concept.get("brief"),
            }
            h.update(json.dumps(inherited, sort_keys=True, ensure_ascii=False).encode("utf-8"))
            h.update(b"\0")
    return h.hexdigest()[:16]


def content_hash(path: Path) -> str | None:
    """檔案內容的 sha256（前 16 碼）。不存在 → None。

    刻意只看內容、不看 mtime——工作區可能在 Google Drive / OneDrive /
    Dropbox / 本機任一，各家同步都會擾動 mtime。
    """
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


@dataclass
class Leaf:
    """一個末節：一組同目錄檔。"""

    section: str                       # 相對 corpus/ 的路徑（POSIX）
    dir: Path
    concept: dict | None               # concept.yaml 內容
    decisions: list[dict] = field(default_factory=list)   # decisions.yaml entries
    history: list[dict] = field(default_factory=list)      # history.yaml entries
    has_material: bool = False
    has_develop: bool = False
    has_history: bool = False

    @property
    def article(self) -> str:
        return self.section.split("/", 1)[0]

    @property
    def concept_id(self) -> str | None:
        return None if self.concept is None else self.concept.get("id")

    @property
    def title(self) -> str:
        if self.concept and self.concept.get("title"):
            return str(self.concept["title"])
        return self.section.rsplit("/", 1)[-1]

    @property
    def order(self) -> float:
        if self.concept and isinstance(self.concept.get("order"), (int, float)):
            return float(self.concept["order"])
        return 0.0

    def source_files(self) -> list[Path]:
        """投影輸入（staleness 看這些）：concept + decisions + material。"""
        files = [self.dir / "concept.yaml", self.dir / "decisions.yaml"]
        if self.has_material:
            files.append(self.dir / "material.md")
        return [f for f in files if f.is_file()]

    def source_hash(self) -> str:
        """投影輸入的彙總內容指紋（staleness 用）。"""
        h = hashlib.sha256()
        for f in self.source_files():
            h.update(f.relative_to(self.dir).as_posix().encode("utf-8"))
            h.update(b"\0")
            h.update(f.read_bytes())
            h.update(b"\0")
        return h.hexdigest()[:16]


def _entries(raw: object, path: Path) -> list[dict]:
    """取 {entries: [...]} 結構的 entries；容錯。"""
    if raw is None:
        return []
    if not isinstance(raw, dict):
        raise ModelError(f"{path} top level must be a mapping (with entries)")
    entries = raw.get("entries") or []
    if not isinstance(entries, list):
        raise ModelError(f"{path} entries must be a list")
    out: list[dict] = []
    for e in entries:
        if not isinstance(e, dict):
            raise ModelError(f"{path} entries item must be a mapping: {e!r}")
        out.append(e)
    return out


def load_leaf(layout: Layout, leaf_dir: Path) -> Leaf:
    section = layout.section_id(leaf_dir)
    concept_raw = _load_yaml(leaf_dir / "concept.yaml")
    if concept_raw is not None and not isinstance(concept_raw, dict):
        raise ModelError(f"{leaf_dir / 'concept.yaml'} top level must be a mapping")

    decisions_path = leaf_dir / "decisions.yaml"
    history_path = leaf_dir / "history.yaml"
    return Leaf(
        section=section,
        dir=leaf_dir,
        concept=concept_raw,
        decisions=_entries(_load_yaml(decisions_path), decisions_path),
        history=_entries(_load_yaml(history_path), history_path),
        has_material=(leaf_dir / "material.md").is_file(),
        has_develop=(leaf_dir / "develop.md").is_file(),
        has_history=history_path.is_file(),
    )


def load_project(layout: Layout, schema: Schema | None = None) -> list[Leaf]:
    """載入 corpus/ 下所有末節，依 section 路徑排序。"""
    return [load_leaf(layout, d) for d in layout.leaf_dirs()]
