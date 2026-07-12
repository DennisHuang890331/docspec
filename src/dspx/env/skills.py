"""內建 skill 的盤點與讀取。

權威 skill 原始檔以套件資料形式隨 dspx 散布（`src/dspx/assets/skills/<name>/SKILL.md`——
住 `assets/` 底下，跟 `assets/templates/`／`assets/fonts/`／`assets/reference/` 同一類：
出貨資料，非可執行程式碼；模組同名的 `src/dspx/skills.py` 才是讀它的程式碼，兩者不要混淆）。
本模組只負責「列出有哪些、讀出 frontmatter＋本文」；安裝/產生到三工具
（Claude／Antigravity／Codex）的邏輯在 commands/skills_cmd.py。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path

import yaml

from dspx.env.frontmatter import FrontmatterError, parse_frontmatter


class SkillError(Exception):
    """skill 缺失、frontmatter 損壞或缺必要欄。"""


@dataclass(frozen=True)
class Skill:
    """一個內建 skill：權威原始檔 + 解析出的中介資料。

    `kind` 區分兩類：
      - "workflow"（預設）＝五個作者工作流 skill（develop/apply/factcheck/
        publish/release）：裝成 skill（自動載入）＋command（人顯式叫用 slash/workflow）。
      - "support" ＝craft skill（如 dspx-diagram），由 apply/develop 委派的 subagent
        載入、非工作流階段、不產 slash command；它隨帶 scripts/ 等輔助檔一起落地。
    """

    name: str
    description: str
    body: str
    source: Path  # 權威 SKILL.md 的絕對路徑
    kind: str = "workflow"
    frontmatter: dict = field(default_factory=dict)  # 原始 frontmatter（compatibility/license/metadata…）

    @property
    def is_workflow(self) -> bool:
        return self.kind == "workflow"

    @property
    def compatibility(self) -> str | None:
        """環境需求一行（PATH 自救等）——skill-redesign 後住 frontmatter，body 零環境雜訊。"""
        c = self.frontmatter.get("compatibility")
        return str(c) if c else None

    @property
    def aux_files(self) -> list[Path]:
        """skill 目錄內除 SKILL.md 外的所有檔（scripts/、NOTICE.md…），供 support skill 隨帶安裝。"""
        skill_dir = self.source.parent
        return [
            p for p in sorted(skill_dir.rglob("*"))
            if p.is_file() and p.name != "SKILL.md" and "__pycache__" not in p.parts
        ]

    @property
    def text(self) -> str:
        """重組完整 SKILL.md（frontmatter + 本文），保證 name/description 齊全，並**保留原始
        frontmatter 其餘欄**（compatibility/license/metadata…）——否則環境需求（PATH 自救）在安裝
        當下被丟掉、body 又已無環境雜訊＝零落點。name/description 置頂，其餘照原序。"""
        meta = {k: v for k, v in self.frontmatter.items() if k not in ("name", "description")}
        ordered = {"name": self.name, "description": _fold(self.description), **meta}
        block = yaml.safe_dump(ordered, allow_unicode=True, sort_keys=False, width=4096).strip()
        return f"---\n{block}\n---\n{self.body}"


def _fold(value: str) -> str:
    """把可能含換行的 description 壓成單行（frontmatter 一行一值，最穩）。"""
    return " ".join(value.split())


def builtin_skills_root() -> Path:
    """內建 skill 資料夾（套件資料，住 assets/ 底下）。"""
    return Path(str(files("dspx").joinpath("assets", "skills")))


def _load_one(skill_dir: Path) -> Skill:
    md = skill_dir / "SKILL.md"
    if not md.is_file():
        raise SkillError(f"skill \"{skill_dir.name}\" missing SKILL.md: {md}")
    try:
        meta, body = parse_frontmatter(md.read_text(encoding="utf-8"), source=md)
    except FrontmatterError as exc:
        raise SkillError(str(exc)) from exc
    name = meta.get("name") or skill_dir.name
    description = meta.get("description")
    if not description:
        raise SkillError(f"skill \"{name}\" frontmatter missing description: {md}")
    kind = str(meta.get("kind") or "workflow").strip().lower()
    if kind not in ("workflow", "support"):
        kind = "workflow"
    return Skill(
        name=str(name),
        description=_fold(str(description)),
        body=body.lstrip("\n"),
        source=md,
        kind=kind,
        frontmatter=dict(meta),
    )


def available_skills(root: Path | None = None) -> list[Skill]:
    """列出全部內建 skill（依 name 排序）。"""
    root = root or builtin_skills_root()
    if not root.is_dir():
        return []
    skills = [
        _load_one(p)
        for p in sorted(root.iterdir())
        if (p / "SKILL.md").is_file()
    ]
    return sorted(skills, key=lambda s: s.name)
