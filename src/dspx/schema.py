"""section-driven schema 載入。

機制照 OpenSpec：一份 schema.yaml 宣告「有哪些 artifact、各有什麼欄、彼此什麼
關係、各帶 instruction/template」。語意是 docspec 的「讀寫契約 / aperture 投影」，
不是生產依賴 DAG（requires 一律 []，迴圈內永遠可寫）。

prose（instruction/template）一律外掛檔，不內嵌 YAML 字串。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path

import yaml

DEFAULT_SCHEMA = "section-driven"

# 引擎只認的引用箭頭（封閉集）；schema 可覆寫，預設為此。
DEFAULT_RELATION_KINDS = ("realizes", "governs", "supersedes")


class SchemaError(Exception):
    """schema 缺失、格式錯誤或引用檔不存在。"""


@dataclass(frozen=True)
class Aperture:
    """讀寫契約：哪些 skill 可讀/寫此 artifact，是否投影進 docs。"""

    read: tuple[str, ...]
    write: tuple[str, ...]
    projects_into: str | None  # "docs" 或 None


@dataclass(frozen=True)
class Artifact:
    """末節的一個組成檔。"""

    id: str
    generates: str               # 檔名，如 concept.yaml
    kind: str                    # "yaml" | "md"
    description: str
    template: Path | None
    instruction: Path | None
    aperture: Aperture
    schema: dict | None          # kind==yaml 的欄位 meta-schema
    block_grammar: dict | None   # kind==md 的分塊文法
    entries: bool                # True = 此 yaml 檔為 {entries: [...]} 結構


@dataclass(frozen=True)
class Schema:
    name: str
    version: int
    description: str
    root: Path
    artifacts: tuple[Artifact, ...]
    skills: dict[str, dict]                      # skill -> {reads, writes}
    projection: dict                            # {produces, driven-by, reads}
    relation_kinds: tuple[str, ...] = field(default=DEFAULT_RELATION_KINDS)
    workflow: dict = field(default_factory=dict)  # 迴圈/skill/邊界敘事（guide 投影、不漂移）
    project_files: tuple[dict, ...] = field(default=())  # 專案級檔（非 artifact）的 agent 契約；guide 投影
    filing_rules: tuple[dict, ...] = field(default=())  # 跨 skill 普世存檔律（只放引擎真會擋的）；guide 投影

    def by_id(self, artifact_id: str) -> Artifact | None:
        for a in self.artifacts:
            if a.id == artifact_id:
                return a
        return None

    def by_generates(self, filename: str) -> Artifact | None:
        for a in self.artifacts:
            if a.generates == filename:
                return a
        return None

    @property
    def yaml_artifacts(self) -> tuple[Artifact, ...]:
        return tuple(a for a in self.artifacts if a.kind == "yaml")


def required_field_names(fieldmap: dict | None) -> list[str]:
    """從欄位 meta-schema 萃取必填欄路徑（巢狀用 dot，如 `brief.audience`）。
    讓 agent 一眼知道「完整」的定義——給 instructions/new/guide 投影。"""
    out: list[str] = []
    for fname, spec in (fieldmap or {}).items():
        if not isinstance(spec, dict):
            continue
        if spec.get("required"):
            out.append(fname)
        if spec.get("type") == "object" and isinstance(spec.get("fields"), dict):
            out.extend(f"{fname}.{s}" for s in required_field_names(spec["fields"]))
    return out


def builtin_schemas_root() -> Path:
    return Path(str(files("dspx").joinpath("schemas")))


def available_schemas(root: Path | None = None) -> list[str]:
    root = root or builtin_schemas_root()
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if (p / "schema.yaml").is_file())


def _resolve_ref(schema_dir: Path, ref: object, *, owner: str, key: str) -> Path | None:
    if ref is None:
        return None
    path = schema_dir / str(ref)
    if not path.is_file():
        raise SchemaError(f"schema \"{schema_dir.name}\" {owner}.{key} references a nonexistent file: {path}")
    return path


def _parse_aperture(spec: dict, *, owner: str) -> Aperture:
    if not isinstance(spec, dict):
        raise SchemaError(f"artifact \"{owner}\" aperture must be a mapping")
    projects = spec.get("projects-into")
    return Aperture(
        read=tuple(spec.get("read") or ()),
        write=tuple(spec.get("write") or ()),
        projects_into=None if projects in (None, "null") else str(projects),
    )


def load_schema_from(schema_dir: Path) -> Schema:
    yaml_path = schema_dir / "schema.yaml"
    if not yaml_path.is_file():
        raise SchemaError(f"schema definition not found: {yaml_path}")
    try:
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise SchemaError(f"schema parse failed: {yaml_path} ({exc})") from exc
    if not isinstance(data, dict):
        raise SchemaError(f"schema top level must be a key-value mapping: {yaml_path}")

    for required in ("name", "version", "artifacts"):
        if required not in data:
            raise SchemaError(f"schema \"{schema_dir.name}\" missing required key: {required}")
    if not isinstance(data["artifacts"], list) or not data["artifacts"]:
        raise SchemaError(f"schema \"{schema_dir.name}\" artifacts must be a non-empty list")

    artifacts: list[Artifact] = []
    for entry in data["artifacts"]:
        if not isinstance(entry, dict) or "id" not in entry or "generates" not in entry:
            raise SchemaError(f"schema \"{schema_dir.name}\" artifact entry missing id/generates: {entry}")
        kind = entry.get("kind")
        if kind not in ("yaml", "md"):
            raise SchemaError(f"artifact \"{entry['id']}\" kind must be yaml/md, got: {kind}")
        artifacts.append(
            Artifact(
                id=entry["id"],
                generates=entry["generates"],
                kind=kind,
                description=entry.get("description", ""),
                template=_resolve_ref(schema_dir, entry.get("template"), owner=entry["id"], key="template"),
                instruction=_resolve_ref(schema_dir, entry.get("instruction"), owner=entry["id"], key="instruction"),
                aperture=_parse_aperture(entry.get("aperture") or {}, owner=entry["id"]),
                schema=entry.get("schema") if kind == "yaml" else None,
                block_grammar=entry.get("block-grammar") if kind == "md" else None,
                entries=bool(entry.get("entries", False)),
            )
        )

    return Schema(
        name=data["name"],
        version=int(data["version"]),
        description=data.get("description", ""),
        root=schema_dir,
        artifacts=tuple(artifacts),
        skills=dict(data.get("skills") or {}),
        projection=dict(data.get("projection") or {}),
        relation_kinds=tuple(data.get("relation-kinds") or DEFAULT_RELATION_KINDS),
        workflow=dict(data.get("workflow") or {}),
        project_files=tuple(data.get("project-files") or ()),
        filing_rules=tuple(data.get("filing-rules") or ()),
    )


def load_schema(name: str | None = None, *, root: Path | None = None) -> Schema:
    name = name or DEFAULT_SCHEMA
    root = root or builtin_schemas_root()
    schema_dir = root / name
    if not (schema_dir / "schema.yaml").is_file():
        names = ", ".join(available_schemas(root)) or "(none)"
        raise SchemaError(f"unknown schema \"{name}\". Available schemas: {names}")
    return load_schema_from(schema_dir)
