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
                ├── concept.yaml  decisions.yaml  material.md  history.yaml

「末節（leaf）」＝任何含 concept.yaml 的資料夾。section 路徑＝相對 corpus/ 的路徑。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dspx.engine.config import CONFIG_FILE_NAME

PLANNING_DIR_NAME = "docspec"
CORPUS_DIR_NAME = "corpus"
CONCEPT_FILE = "concept.yaml"
# corpus 內 `_` 開頭的目錄＝引擎隱形（退場封存區 _archive/ 等）：
# status/check/render/draft 一律跳過，被退場的節不再被當活節掃出來。
ARCHIVE_DIR_NAME = "_archive"
LEDGER_DIR_NAME = ".ledger"   # 機器簿記（指紋帳本）住 docspec/ 內、不汙染 docs/（交付物）
ASSET_DIR_NAME = "assets"     # 圖資產（drawio 源＋渲染圖）的資料夾名；交付側 docs/assets/


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

    def docs_assets_dir(self, article: str | None = None) -> Path:
        """圖資產（`.drawio` 源＋渲染圖）的家＝**交付側 `docs/assets/`**（非 corpus）。
        drawio／圖是交付物，住 docs/；交付物 `docs/<article>_latest.md` 的扁平 `![](assets/<name>)`
        相對解析即 `docs/assets/<name>`，使 .md 自足、`.drawio` 源也進交付集。
        per-article docs layout 時為 `docs/<article>/assets/`（與該文件 _latest.md 同層）。"""
        if self.docs_layout == "flat" or article is None:
            return self.docs_dir / ASSET_DIR_NAME
        return self.docs_dir / article / ASSET_DIR_NAME

    # ── 文章案卷（dossier-layout：一篇一夾、內檔定名、層級決定住址）──────

    def article_dir(self, article: str) -> Path:
        """文章案卷夾 `corpus/<article>/`——該篇**全部**紀錄住同一夾、內檔定名
        （article/audit/roadmap/ledger/verdicts.yaml）；文章名只出現在夾名，
        改名＝改一個夾名全部跟著走。"""
        return self.corpus_dir / article

    def article_store(self, article: str) -> Path:
        """密封 store（真相）＝案卷內定名檔 article.yaml。"""
        return self.article_dir(article) / "article.yaml"

    def article_audit(self, article: str) -> Path:
        return self.article_dir(article) / "audit.yaml"

    def article_roadmap(self, article: str) -> Path:
        return self.article_dir(article) / "roadmap.yaml"

    def article_ledger(self, article: str) -> Path:
        """render 指紋帳本（機器簿記，隨卷）。"""
        return self.article_dir(article) / "ledger.yaml"

    def article_verdicts(self, article: str) -> Path:
        """裁決日誌（append-only，隨卷；整篇退役隨夾保全、不再變孤兒）。"""
        return self.article_dir(article) / "verdicts.yaml"

    def archived_article_dir(self, article: str) -> Path:
        """退場案卷 `corpus/_archive/<article>/`——與活案卷同拓撲（state=location）。"""
        return self.corpus_archive_dir / article

    @property
    def explorations_dir(self) -> Path:
        """思考級記錄的家（比照 OpenSpec explorations/）：純 md、不密封、引擎零管理。"""
        return self.planning_home / "explorations"

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

    def docs_ledger(self, article: str) -> Path:
        """機器簿記：render 記的各節指紋表。dossier-layout：**隨卷**住 `corpus/<article>/ledger.yaml`
        ——per-article 紀錄不散居；docs/ 只放人讀的交付物。"""
        return self.article_ledger(article)

    def docs_ledger_prev(self, article: str) -> Path:
        """前一代帳本位置（`docspec/.ledger/<article>.sections.yaml`）。讀端 fallback：
        舊佈局照讀、下次 render 寫進案卷；`store migrate-layout` 一次收編。"""
        return self.planning_home / LEDGER_DIR_NAME / f"{article}.sections.yaml"

    def docs_ledger_legacy(self, article: str) -> Path:
        """最舊帳本位置（docs/ 底下的隱藏 sidecar）。read_ledger 的最後一層 fallback。"""
        if self.docs_layout == "flat":
            return self.docs_dir / f".{article}.sections.yaml"
        return self.docs_dir / article / ".sections.yaml"

    def verdicts_journal(self, article: str) -> Path:
        """裁決日誌的家（隨卷）；change 情境由 OverlayLayout 覆寫導向 preview。"""
        return self.article_verdicts(article)

    def docs_snapshot(self, article: str, version: str) -> Path:
        # version＝semver 字串（X.Y.Z）。凍結快照一律收進 archive/ 子夾（兩種 layout 皆然）
        # ——凍結＝資料夾級規則（任何 archive/ 內禁改），不靠檔名 pattern。見 dspx.reports.freeze。
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

    @property
    def docs_journal_dir(self) -> Path:
        """journal 軌產物根夾＝docs/exports/journals/（與 Typst 軌 latest PDF 分離）。"""
        return self.docs_exports_dir / "journals"

    def docs_journal_export(self, article: str, version: str, journal_id: str, fmt: str) -> Path:
        """journal 軌 emit 路徑：docs/exports/journals/<journal_id>/<article>_v<version>.<fmt>。

        per-journal 子夾＝①不與 latest 交付物混；②雙 adapter（ieee/elsevier）不互蓋
        （先前都寫同一 docs/exports/<article>_v<N>.tex 互覆寫）。"""
        # journal_id 防護：取末段檔名、剔分隔符（BYO --template 可能給夾路徑）。
        safe = "".join(c for c in Path(journal_id).name if c.isalnum() or c in "-_") or "journal"
        return self.docs_journal_dir / safe / f"{article}_v{version}.{fmt}"

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
        """corpus/ 下的文章名（散檔末節路徑的第一段 ∪ 一篇一檔 store 檔 `<article>.yaml`）。

        store 篇無 leaf 夾（真相收在單檔），必須另從 `corpus/*.yaml` 補列——否則遍歷全文章的
        指令（render/publish/mv/rename-term/change）會漏掉 store 篇。直接 glob（不 import store，避免
        循環）：corpus 底下的頂層 `.yaml`（非 `_` 前綴）即 store 檔。"""
        seen: list[str] = []
        for leaf in self.leaf_dirs():
            art = self.article_of(self.section_id(leaf))
            if art and art not in seen:
                seen.append(art)
        if self.corpus_dir.is_dir():
            import re as _re
            conflict = _re.compile(r".* \(\d+\)$")   # Drive 衝突副本 `<stem> (N).yaml` 隱形
            for p in sorted(self.corpus_dir.glob("*.yaml")):
                # sibling 治理密封檔（`<a>.audit.yaml`/`<a>.roadmap.yaml`）不是文章、不入列。
                if p.name.endswith((".audit.yaml", ".roadmap.yaml")):
                    continue
                if (p.is_file() and not p.name.startswith("_") and p.stem not in seen
                        and not conflict.match(p.stem) and ".tmp.drive" not in p.name.lower()):
                    seen.append(p.stem)
            # dossier-layout：案卷夾（corpus/<article>/article.yaml）＝文章（夾名即文章名）。
            for d in sorted(self.corpus_dir.iterdir()):
                if (d.is_dir() and not d.name.startswith("_") and d.name not in seen
                        and not conflict.match(d.name) and (d / "article.yaml").is_file()):
                    seen.append(d.name)
        return seen
