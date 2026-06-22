"""planning home 尋根與標準路徑解析（section 模型）。

佈局慣例：
    <project>/
    ├── docs/
    │   └── <article>/
    │       ├── _latest.md             publish 投影成品（人讀唯一窗口；活的、可改）
    │       └── archive/v<N>.md        已發行凍結快照（不可變；任何 archive/ 內禁改）
    └── docspec/                       ← planning home（判定：本目錄含 config.yaml）
        ├── .freeze.yaml               凍結區 hash 清單（publish 記、lint V11 抽查）
        ├── config.yaml
        └── corpus/                   章節架構（資料夾樹鏡像文章骨架）
            └── <article>/<…>/<leaf>/  末節資料夾（含 concept.yaml 即為末節）
                ├── concept.yaml  decisions.yaml  material.md  develop.md  history.yaml

「末節（leaf）」＝任何含 concept.yaml 的資料夾。section 路徑＝相對 corpus/ 的路徑。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dspx.config import CONFIG_FILE_NAME

PLANNING_DIR_NAME = "docspec"
CORPUS_DIR_NAME = "corpus"
CONCEPT_FILE = "concept.yaml"
# corpus 內 `_` 開頭的目錄＝引擎隱形（退場封存區 _archive/ 等）：
# status/check/render/draft 一律跳過，被退場的節不再被當活節掃出來。
ARCHIVE_DIR_NAME = "_archive"


_LEVELS = ("major", "minor", "patch")


def parse_semver(text: str) -> tuple[int, int, int] | None:
    """解析 `X.Y.Z` → (major, minor, patch)；不合格回 None。"""
    parts = text.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        return None
    return tuple(int(p) for p in parts)  # type: ignore[return-value]


def next_version(prev: tuple[int, int, int] | str | None, level: str) -> str:
    """從前版 bump 出下一個 semver 字串。

    prev 無 → `1.0.0`；否則依 level 加對應位、低位歸零：
      patch → +0.0.1 ｜ minor → +0.1.0（patch 歸零）｜ major → +1.0.0（minor/patch 歸零）。
    """
    if level not in _LEVELS:
        raise ValueError(f"unknown level \"{level}\" (must be one of {', '.join(_LEVELS)})")
    if prev is None:
        return "1.0.0"
    if isinstance(prev, str):
        parsed = parse_semver(prev)
        if parsed is None:
            raise ValueError(f"cannot parse previous semver \"{prev}\"")
        prev = parsed
    major, minor, patch = prev
    if level == "major":
        return f"{major + 1}.0.0"
    if level == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


class LayoutError(Exception):
    """找不到 docspec planning home。"""


def find_planning_home(start: Path | None = None) -> Path:
    """從 start（預設 CWD）向上尋根。

    命中條件：某祖先目錄本身是含 config.yaml 的 docspec/，
    或其下有 docspec/config.yaml。到檔案系統根仍無 → LayoutError。
    """
    origin = (start or Path.cwd()).resolve()
    for candidate in (origin, *origin.parents):
        if candidate.name == PLANNING_DIR_NAME and (candidate / CONFIG_FILE_NAME).is_file():
            return candidate
        nested = candidate / PLANNING_DIR_NAME
        if (nested / CONFIG_FILE_NAME).is_file():
            return nested
    raise LayoutError(
        f"no planning home found from {origin} up to the filesystem root"
        f" (looking for a {PLANNING_DIR_NAME}/ directory containing {CONFIG_FILE_NAME})"
    )


@dataclass(frozen=True)
class Layout:
    """標準路徑解析器。缺席的選配目錄回報為空，不報錯。"""

    planning_home: Path
    # 真實專案預設＝flat（見 config.DEFAULTS / bootstrap）；此 dataclass fallback 留 per-article
    # 僅供測試直接建 Layout(home) 用。flat＝docs/<article>_latest.md＋docs/archive/<article>_v<N>.md。
    docs_layout: str = "per-article"

    @property
    def project_root(self) -> Path:
        return self.planning_home.parent

    @property
    def corpus_dir(self) -> Path:
        return self.planning_home / CORPUS_DIR_NAME

    @property
    def writing_guide(self) -> Path:
        """專案級寫作守則（draft 渲染時注入；全文件共用同一份風格）。"""
        return self.planning_home / "writing-guide.md"

    @property
    def docs_dir(self) -> Path:
        return self.project_root / "docs"

    # ── section 路徑 ↔ 資料夾 ────────────────────────────────────

    def section_dir(self, section: str) -> Path:
        """section 路徑（相對 corpus/，POSIX 斜線）→ 絕對資料夾。"""
        return self.corpus_dir.joinpath(*[p for p in section.split("/") if p])

    def section_id(self, leaf_dir: Path) -> str:
        """末節資料夾 → section 路徑（相對 corpus/，POSIX 斜線）。"""
        return leaf_dir.relative_to(self.corpus_dir).as_posix()

    @property
    def corpus_archive_dir(self) -> Path:
        """退場節的扁平封存區（corpus/_archive/）；引擎隱形、可回復。"""
        return self.corpus_dir / ARCHIVE_DIR_NAME

    def is_archived_path(self, p: Path) -> bool:
        """p（corpus 內某資料夾）是否落在 `_` 開頭的隱形目錄下（如 _archive）。"""
        try:
            rel = p.relative_to(self.corpus_dir)
        except ValueError:
            return False
        return any(part.startswith("_") for part in rel.parts)

    def article_of(self, section: str) -> str:
        """section 路徑的第一段＝文章名。"""
        parts = [p for p in section.split("/") if p]
        return parts[0] if parts else ""

    def docs_latest(self, article: str) -> Path:
        if self.docs_layout == "flat":
            return self.docs_dir / f"{article}_latest.md"
        return self.docs_dir / article / "_latest.md"

    def docs_snapshot(self, article: str, version: str) -> Path:
        # version＝semver 字串（X.Y.Z）。凍結快照一律收進 archive/ 子夾（兩種 layout 皆然）
        # ——凍結＝資料夾級規則（任何 archive/ 內禁改），不靠檔名 pattern。見 dspx.freeze。
        if self.docs_layout == "flat":
            return self.docs_dir / "archive" / f"{article}_v{version}.md"
        return self.docs_dir / article / "archive" / f"v{version}.md"

    def docs_changelog(self, article: str) -> Path:
        if self.docs_layout == "flat":
            return self.docs_dir / "revision_history" / f"{article}.md"
        return self.docs_dir / article / "changelog.md"

    # ── export 產物（終端衍生物，可重生；絕不在 archive/ 下）─────────

    @property
    def docs_exports_dir(self) -> Path:
        """export 產物夾＝docs/exports/（兩種 layout 共用、扁平）。

        docx/pdf 是可隨時重生的終端投影，刻意**不放 archive/**——避開
        freeze hash-net / lint V11 / PreToolUse hook（凍結是 archive/ 資料夾級規則）。
        """
        return self.docs_dir / "exports"

    def docs_export(self, article: str, version: str, fmt: str) -> Path:
        """export 產物路徑：docs/exports/<article>_v<version>.<fmt>。"""
        return self.docs_exports_dir / f"{article}_v{version}.{fmt}"

    def existing_versions(self, article: str) -> list[tuple[int, int, int]]:
        """已發行 semver 清單（scheme-aware；供 publish 算下一版）。

        從 archive 快照檔名解析 `X.Y.Z` → (major, minor, patch) tuple（可直接比較/排序）。
        不合 semver 的檔名跳過；無快照回空清單。
        """
        if self.docs_layout == "flat":
            root, pattern = self.docs_dir / "archive", f"{article}_v*.md"
            stem_prefix = f"{article}_v"
        else:
            root, pattern = self.docs_dir / article / "archive", "v*.md"
            stem_prefix = "v"
        if not root.is_dir():
            return []
        out = []
        for p in root.glob(pattern):
            tail = p.stem[len(stem_prefix):]
            parsed = parse_semver(tail)
            if parsed is not None:
                out.append(parsed)
        return out

    # ── 盤點 ─────────────────────────────────────────────────────

    def leaf_dirs(self) -> list[Path]:
        """corpus/ 下所有末節資料夾（含 concept.yaml），依 section 路徑排序。"""
        if not self.corpus_dir.is_dir():
            return []
        leaves = [p.parent for p in self.corpus_dir.rglob(CONCEPT_FILE)
                  if p.is_file() and not self.is_archived_path(p.parent)]
        return sorted(leaves, key=lambda p: self.section_id(p))

    def articles(self) -> list[str]:
        """corpus/ 下的文章名（末節路徑的第一段）。"""
        seen: list[str] = []
        for leaf in self.leaf_dirs():
            art = self.article_of(self.section_id(leaf))
            if art and art not in seen:
                seen.append(art)
        return seen
