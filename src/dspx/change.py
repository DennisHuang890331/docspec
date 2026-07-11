"""change 事件層：修改容器 + 暫存（草稿分支）+ union view + 收案落地。

北極星（proposal / design D1–D8）：只借 OpenSpec 的修改紀律（容器/暫存/收案），不借文字
delta。暫存的是**結構化真相 + 重渲染**（整檔替換、非三方合併）。

- change 容器＝`changes/<id>/`（專案根、與 corpus/roadmap/audit 同級）：
    change.yaml（引擎獨占寫；無 status 欄——狀態＝位置＋導出）＋notes.md（跨節討論、永不入盲寫）。
- 位置＝狀態：`changes/<id>/`（active）｜`changes/_archive/<id>/`（accepted）｜
    `changes/_abandoned/<id>/`（dropped）。
- 暫存＝草稿分支：`changes/<id>/staging/` 鏡像 **workspace（專案根）相對路徑**（copy-on-write：
    corpus 章節＝複製整個節資料夾；森林級檔/外部 file target＝複製該檔）。正式面 archive 前 byte 不動。
- union view：有 change context 時「staging 優先、正式補底」合成森林；無 context 逐 byte 同現行。
- 預覽：`docspec render --change <id>` 從 union view 渲染到 `changes/<id>/preview/<article>_latest.md`
    ＋ staging 側 sidecar 帳本；預覽成品與帳本從正式版 seed（★G2）。
"""

from __future__ import annotations

import datetime
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from dspx.layout import CORPUS_DIR_NAME, LEDGER_DIR_NAME, Layout
from dspx.model import Leaf, content_hash

CHANGES_DIR = "changes"
ARCHIVE_DIR = "_archive"
ABANDONED_DIR = "_abandoned"
STAGING_DIR = "staging"
PREVIEW_DIR = "preview"
CHANGE_FILE = "change.yaml"
NOTES_FILE = "notes.md"

PUBLISH_POLICIES = ("advisory", "release-bound")
# action ∈ 驗收判準選擇器 ＋ apply 模式選擇器（雙重語義，★#16）
ACTIONS = ("create", "revise", "align", "redraft", "review", "retire", "move")
ORIGINS = ("auto", "manual")
# target ref 的型別（section＝現有節 concept.id；create＝corpus 路徑，出生後回填 id；
# file＝引擎視野外的檔路徑；term＝glossary 術語）。
TARGET_KINDS = ("section", "create", "file", "term")

# change id 形狀：字母數字 + `-`，不得像路徑/保留名（與檔名安全一致）。
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

STATE_ACTIVE = "active"
STATE_ARCHIVED = "archived"
STATE_ABANDONED = "abandoned"

_MACHINE_HEADER = (
    "# docspec change container (maintained by the `docspec change` commands; do not edit by "
    "hand — the engine owns this file, there is no status field, state = location).\n")


class ChangeError(Exception):
    """change 容器操作失敗（id 非法、publish 缺失、ref 型別錯、載入壞檔等）。"""


# ── target / change model ─────────────────────────────────────────────

@dataclass
class Target:
    """一個 target：ref（concept.id / 路徑 / 檔 / 術語）＋origin（auto|manual）＋action。

    action 是**驗收判準選擇器**與 **apply 模式選擇器**雙重語義（★#16）。
    file target 另記 `baseline`（add-target 當下的 hash，收案時比對 hash≠baseline＝做過事）。
    """

    ref: str
    action: str
    origin: str = "manual"
    kind: str = "section"
    baseline: str | None = None      # file target：add 當下 hash
    validator: str | None = None     # file target：落地後跑的 validator（可選）
    dest: str | None = None          # move action：目的地 section 路徑
    note: str | None = None

    def to_dict(self) -> dict:
        out: dict = {"ref": self.ref, "action": self.action, "origin": self.origin}
        if self.kind != "section":
            out["kind"] = self.kind
        if self.baseline is not None:
            out["baseline"] = self.baseline
        if self.validator:
            out["validator"] = self.validator
        if self.dest:
            out["dest"] = self.dest
        if self.note:
            out["note"] = self.note
        return out

    @classmethod
    def from_dict(cls, d: dict) -> "Target":
        if not isinstance(d, dict):
            raise ChangeError(f"target must be a mapping, got {d!r}")
        return cls(
            ref=str(d.get("ref") or ""),
            action=str(d.get("action") or ""),
            origin=str(d.get("origin") or "manual"),
            kind=str(d.get("kind") or "section"),
            baseline=d.get("baseline"),
            validator=d.get("validator"),
            dest=d.get("dest"),
            note=d.get("note"),
        )


@dataclass
class Change:
    """一張 change 的記憶體模型（change.yaml；引擎獨占寫、無 status 欄）。"""

    id: str
    title: str
    why: str
    created: str
    publish: str
    seeds: list[str] = field(default_factory=list)
    targets: list[Target] = field(default_factory=list)
    fork_hashes: dict[str, str] = field(default_factory=dict)  # workspace-rel path -> 官方 hash
    promoted_from: str | None = None   # roadmap/audit id（晉升搬家鏈接；archive audit WARN 用）
    abandoned: dict | None = None      # {date, reason}
    state: str = STATE_ACTIVE
    dir: Path | None = None            # 容器目錄（載入時填）

    def to_dict(self) -> dict:
        out: dict = {
            "id": self.id,
            "title": self.title,
            "why": self.why,
            "created": self.created,
            "publish": self.publish,
        }
        if self.seeds:
            out["seeds"] = list(self.seeds)
        out["targets"] = [t.to_dict() for t in self.targets]
        if self.fork_hashes:
            out["fork-hashes"] = dict(self.fork_hashes)
        if self.promoted_from:
            out["promoted-from"] = self.promoted_from
        if self.abandoned:
            out["abandoned"] = dict(self.abandoned)
        return out

    @classmethod
    def from_dict(cls, d: dict, *, state: str = STATE_ACTIVE,
                  cdir: Path | None = None) -> "Change":
        if not isinstance(d, dict):
            raise ChangeError("change.yaml top level must be a mapping")
        targets = [Target.from_dict(t) for t in (d.get("targets") or [])]
        return cls(
            id=str(d.get("id") or ""),
            title=str(d.get("title") or ""),
            why=str(d.get("why") or ""),
            created=str(d.get("created") or ""),
            publish=str(d.get("publish") or ""),
            seeds=[str(s) for s in (d.get("seeds") or [])],
            targets=targets,
            fork_hashes=dict(d.get("fork-hashes") or {}),
            promoted_from=(str(d["promoted-from"]) if d.get("promoted-from") else None),
            abandoned=(dict(d["abandoned"]) if isinstance(d.get("abandoned"), dict) else None),
            state=state,
            dir=cdir,
        )

    def target_by_ref(self, ref: str) -> Target | None:
        for t in self.targets:
            if t.ref == ref:
                return t
        return None


# ── 路徑解析 ──────────────────────────────────────────────────────────

def changes_root(layout: Layout) -> Path:
    return layout.project_root / CHANGES_DIR


def _state_root(layout: Layout, state: str) -> Path:
    root = changes_root(layout)
    if state == STATE_ARCHIVED:
        return root / ARCHIVE_DIR
    if state == STATE_ABANDONED:
        return root / ABANDONED_DIR
    return root


def change_dir(layout: Layout, cid: str, state: str = STATE_ACTIVE) -> Path:
    return _state_root(layout, state) / cid


def change_yaml_path(cdir: Path) -> Path:
    return cdir / CHANGE_FILE


def notes_path(cdir: Path) -> Path:
    return cdir / NOTES_FILE


def staging_dir(cdir: Path) -> Path:
    return cdir / STAGING_DIR


def preview_dir(cdir: Path) -> Path:
    return cdir / PREVIEW_DIR


def planning_home_rel(layout: Layout) -> Path:
    """planning_home 相對 project_root（通常＝`docspec`）。"""
    return layout.planning_home.relative_to(layout.project_root)


# ── 狀態偵測 / 載入 ───────────────────────────────────────────────────

def change_state(layout: Layout, cid: str) -> str | None:
    """cid 現在的狀態（active/archived/abandoned）；不存在 → None。"""
    for state in (STATE_ACTIVE, STATE_ARCHIVED, STATE_ABANDONED):
        if change_yaml_path(change_dir(layout, cid, state)).is_file():
            return state
    return None


def load_change_at(cdir: Path, state: str) -> Change:
    p = change_yaml_path(cdir)
    if not p.is_file():
        raise ChangeError(f"change container not found: {p}")
    from dspx.model import ModelError, _load_yaml
    try:
        raw = _load_yaml(p)
    except ModelError as exc:
        raise ChangeError(str(exc)) from exc
    if raw is None:
        raise ChangeError(f"change.yaml is empty: {p}")
    return Change.from_dict(raw, state=state, cdir=cdir)


def load_change(layout: Layout, cid: str) -> Change:
    """載入 cid（任何狀態：先 active、再 archive、再 abandoned）；不存在 → ChangeError。"""
    state = change_state(layout, cid)
    if state is None:
        raise ChangeError(f"no change \"{cid}\" (looked in changes/, _archive/, _abandoned/)")
    return load_change_at(change_dir(layout, cid, state), state)


def _iter_change_ids(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    out = []
    for d in sorted(root.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        if change_yaml_path(d).is_file():
            out.append(d.name)
    return out


def active_change_ids(layout: Layout) -> list[str]:
    return _iter_change_ids(changes_root(layout))


def iter_active_changes(layout: Layout) -> list[Change]:
    out = []
    for cid in active_change_ids(layout):
        try:
            out.append(load_change_at(change_dir(layout, cid, STATE_ACTIVE), STATE_ACTIVE))
        except ChangeError:
            continue
    return out


def all_change_states(layout: Layout) -> dict[str, str]:
    """全部 change id → 狀態（active/archived/abandoned）。check 的 promoted-to 反查用。"""
    out: dict[str, str] = {}
    for state, root in (
            (STATE_ACTIVE, changes_root(layout)),
            (STATE_ARCHIVED, changes_root(layout) / ARCHIVE_DIR),
            (STATE_ABANDONED, changes_root(layout) / ABANDONED_DIR)):
        for cid in _iter_change_ids(root):
            out.setdefault(cid, state)
    return out


# ── 儲存（引擎獨占寫）────────────────────────────────────────────────

def save_change(change: Change) -> None:
    """把 change.yaml 寫回容器目錄（引擎獨占寫、機器 header）。"""
    if change.dir is None:
        raise ChangeError("cannot save a change with no container dir")
    change.dir.mkdir(parents=True, exist_ok=True)
    body = yaml.safe_dump(change.to_dict(), allow_unicode=True, sort_keys=False, width=10000)
    change_yaml_path(change.dir).write_text(_MACHINE_HEADER + body, encoding="utf-8", newline="\n")


def now_date() -> str:
    return datetime.date.today().isoformat()


# ── seed → auto targets 波及（D6，v1 刻意窄：一跳）──────────────────

def auto_targets_for_seed(layout: Layout, leaves: list[Leaf], seed: str) -> list[Target]:
    """從 seed 算 auto targets（D6，一跳為限）：
    - decision/concept seed → 反向 realizes（concept.realizes 含此 id 的節）＝確定命中（action=revise）。
    - term:<術語> seed → gloss 指紋軸受影響（用到該術語的文章）＋rename-term dry-run 命中＝候選。
    盲區（散文引用/圖/schema）＝開單時終端印提醒（呼叫端投影、不落檔）。"""
    out: list[Target] = []
    seen: set[str] = set()

    if seed.startswith("term:"):
        return out   # 術語 seed 的候選解析交由呼叫端（rename-term dry-run），此處不自動入單

    def _ref_of(lf) -> str:
        return (str(lf.concept.get("id")) if lf.concept and lf.concept.get("id")
                else lf.section)

    # ★8.2 seed 決策擁有節：擁有此決策的節也自動入單（改決策就得改它的家；否則 canonical
    #     case 逼人手動 stage 父節、踩 8.1）。掃 decisions/history 找 id == seed 的擁有節。
    for lf in leaves:
        for e in (lf.decisions + lf.history):
            if str(e.get("id")) == seed:
                ref = _ref_of(lf)
                if ref not in seen:
                    seen.add(ref)
                    out.append(Target(ref=ref, action="revise", origin="auto"))

    # decision/concept id：反向 realizes（下游實現節）＋ 節本身即 seed（concept id seed）
    for lf in leaves:
        if lf.concept is None:
            continue
        realizes = [str(r) for r in (lf.concept.get("realizes") or [])]
        cid = str(lf.concept.get("id") or "")
        if seed in realizes or seed == cid:
            ref = cid or lf.section
            if ref not in seen:
                seen.add(ref)
                out.append(Target(ref=ref, action="revise", origin="auto"))
    return out


# ── 驗證 ─────────────────────────────────────────────────────────────

def validate_id(cid: str) -> str | None:
    """change id 安全/形狀驗證；壞 → 原因，好 → None。"""
    if not cid:
        return "change id must not be empty"
    if not _ID_RE.match(cid):
        return ("change id must be lowercase alphanumeric with '-' (no spaces, slashes, or "
                "leading '-'); it becomes a directory name under changes/")
    if cid.startswith("_"):
        return "\"_\"-prefixed ids collide with the engine's _archive/_abandoned areas"
    return None


def validate_change(change: Change) -> list[str]:
    """change.yaml 欄位級結構驗證（check 與寫時共用）。"""
    errs: list[str] = []
    reason = validate_id(change.id)
    if reason:
        errs.append(f"change[{change.id or '?'}]: {reason}")
    if not change.title:
        errs.append(f"change[{change.id}]: missing title")
    if change.publish not in PUBLISH_POLICIES:
        errs.append(f"change[{change.id}]: publish \"{change.publish}\" not in {PUBLISH_POLICIES}")
    seen_refs: set[str] = set()
    for t in change.targets:
        where = f"change[{change.id}] target[{t.ref or '?'}]"
        if not t.ref:
            errs.append(f"{where}: missing ref")
        elif t.ref in seen_refs:
            errs.append(f"{where}: duplicate target ref")
        else:
            seen_refs.add(t.ref)
        if t.action not in ACTIONS:
            errs.append(f"{where}: action \"{t.action}\" not in {ACTIONS}")
        if t.origin not in ORIGINS:
            errs.append(f"{where}: origin \"{t.origin}\" not in {ORIGINS}")
        if t.kind not in TARGET_KINDS:
            errs.append(f"{where}: kind \"{t.kind}\" not in {TARGET_KINDS}")
    return errs


# ── 暫存（copy-on-write）─────────────────────────────────────────────

def workspace_rel(layout: Layout, abspath: Path) -> str:
    """abspath 相對 project_root 的 POSIX 路徑（staging 鏡像的 key）。"""
    return Path(abspath).resolve().relative_to(layout.project_root.resolve()).as_posix()


def staging_target(cdir: Path, layout: Layout, official: Path) -> Path:
    """official（正式面某檔/夾）在 staging 內的鏡像路徑。"""
    rel = workspace_rel(layout, official)
    return staging_dir(cdir).joinpath(*rel.split("/"))


# 一個節「自己的來源檔」白名單（★P0 檔案粒度：staging 一節只複製這些＋assets/，
# **絕不遞迴子章節資料夾**——父/根節的 staging 永不代表其子樹，子節是各自獨立的鏡像路徑）。
_SECTION_OWN_FILES = ("concept.yaml", "decisions.yaml", "material.md", "develop.md",
                      "history.yaml", "history.md", "group.yaml")
_SECTION_ASSET_DIR = "assets"


def _has_own_files(d: Path) -> bool:
    """d（staging 或正式節夾）直接含任一「自己的來源檔」＝真正被 stage 的節（非順帶建出的父路徑）。"""
    return d.is_dir() and (any((d / n).is_file() for n in _SECTION_OWN_FILES)
                           or (d / _SECTION_ASSET_DIR).is_dir())


def is_section_official_dir(layout: Layout, section: str) -> bool:
    return (layout.section_dir(section) / "concept.yaml").is_file()


def record_fork(change: Change, layout: Layout, official: Path) -> None:
    """記錄單一 official 檔 fork 當下的 hash（★#9 漂移守門）。node 級的 fork 記錄由
    stage_section 逐「自己的來源檔」呼叫（不遞迴子章節，見 _SECTION_OWN_FILES）。"""
    if official.is_file():
        change.fork_hashes[workspace_rel(layout, official)] = content_hash(official) or ""


def stage_section(change: Change, layout: Layout, section: str) -> Path:
    """corpus 節 copy-on-write（★P0 檔案粒度）：首次改該節時只複製它**自己的來源檔**
    （concept/decisions/material/develop/history/group ＋ assets/）進 staging——**不遞迴子章節
    資料夾**。回傳 staging 內該節路徑。已 stage（含自己的檔）＝直接回、不覆蓋既有暫存編輯。"""
    official = layout.section_dir(section)
    staged = staging_target(change.dir, layout, official)
    if _has_own_files(staged):
        return staged
    staged.mkdir(parents=True, exist_ok=True)
    if official.is_dir():
        for name in _SECTION_OWN_FILES:
            src = official / name
            if src.is_file():
                shutil.copy2(src, staged / name)
                record_fork(change, layout, src)
        adir = official / _SECTION_ASSET_DIR
        if adir.is_dir():
            dst = staged / _SECTION_ASSET_DIR
            if not dst.exists():
                shutil.copytree(adir, dst)
            for f in sorted(adir.rglob("*")):
                if f.is_file():
                    record_fork(change, layout, f)
    # create action：正式面尚無此節（staged 為空夾，agent 之後填 concept/…）。
    return staged


def stage_file(change: Change, layout: Layout, official: Path) -> Path:
    """森林級檔（glossary/writing-guide/config）或外部 file target 的 copy-on-write。
    回傳 staging 內該檔路徑。"""
    staged = staging_target(change.dir, layout, official)
    if staged.exists():
        return staged
    staged.parent.mkdir(parents=True, exist_ok=True)
    if official.is_file():
        shutil.copy2(official, staged)
        record_fork(change, layout, official)
    return staged


def unstage_section(change: Change, layout: Layout, section: str) -> None:
    """丟棄某節的 staging（★8.4 remove-target 用）：只刪它**自己的來源檔**＋assets/、清 fork_hashes
    對應項——**不 rmtree staging 節夾**（該夾可能巢狀著子章節的 staging，rmtree 會誤刪子節暫存）。"""
    official = layout.section_dir(section)
    staged = staging_target(change.dir, layout, official)
    for name in _SECTION_OWN_FILES:
        f = staged / name
        if f.is_file():
            f.unlink()
        change.fork_hashes.pop(workspace_rel(layout, official / name), None)
    adir = staged / _SECTION_ASSET_DIR
    if adir.is_dir():
        for f in sorted(adir.rglob("*")):
            if f.is_file():
                change.fork_hashes.pop(
                    workspace_rel(layout, official / _SECTION_ASSET_DIR / f.relative_to(adir)),
                    None)
        shutil.rmtree(adir)
    # 清 preview 側的入單標髒（該 target 已不在單，不再需要 stale 信號）
    article = section.split("/", 1)[0]
    ledger = _read_preview_ledger(change, article)
    rec = ledger.get(section)
    if isinstance(rec, dict) and rec.get("redraft"):
        rec.pop("redraft", None)
        ledger[section] = rec
        _write_preview_ledger(change, article, ledger)


def staged_sections(change: Change, layout: Layout) -> list[str]:
    """staging 內已鏡像的 corpus 節（含 concept.yaml 或空 create 節）section 路徑。"""
    corpus_root = staging_target_corpus(change.dir, layout)
    if not corpus_root.is_dir():
        return []
    out: list[str] = []
    for cp in sorted(corpus_root.rglob("concept.yaml")):
        rel = cp.parent.relative_to(corpus_root).as_posix()
        out.append(rel)
    # create 節可能尚無 concept.yaml——以資料夾（含任何檔或空）補列
    return out


def staging_target_corpus(cdir: Path, layout: Layout) -> Path:
    """staging 內的 corpus 根（staging/<planning_home_rel>/corpus）。"""
    return staging_dir(cdir).joinpath(*planning_home_rel(layout).parts) / CORPUS_DIR_NAME


# ── union view 載入 ──────────────────────────────────────────────────

def _resolved_section_dir(change: Change, layout: Layout, section: str) -> Path:
    """某節的 union 解析：staging 內**真正被複製的節**（直接含自己的來源檔）＝優先，否則正式
    corpus。注意：暫存某子節會**順帶建出**其父路徑資料夾（如 staging/.../guide/），但那不是
    「被 stage 的節」——它沒有自己的來源檔，不得遮蔽正式的同名祖先節（★P0 檔案粒度）。"""
    official = layout.section_dir(section)
    staged = staging_target(change.dir, layout, official)
    if _has_own_files(staged):
        return staged
    return official


def _load_leaf_from(section: str, leaf_dir: Path) -> Leaf:
    """從一個具體資料夾（正式或 staging）讀出 Leaf——不經 layout.section_id（staging 路徑
    無法 relative_to 正式 corpus），section 由呼叫端明確給。鏡像 model.load_leaf 的讀取。"""
    from dspx.model import ModelError, _entries, _load_yaml
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


def load_union(layout: Layout, change: Change) -> list[Leaf]:
    """union view：staging 優先、正式補底，合成森林 leaves（依 section 路徑排序）。

    節集合＝正式 corpus 活節 ∪ staging 內有 concept.yaml 的節（含新 create 節）。每節從
    「staging 整包（若存在）否則正式」讀 concept/decisions/material/... 建 Leaf。無 change
    context 時呼叫端仍走 model.load_project（逐 byte 同現行）。"""
    sections: list[str] = []
    seen: set[str] = set()
    for d in layout.leaf_dirs():
        sec = layout.section_id(d)
        if sec not in seen:
            seen.add(sec)
            sections.append(sec)
    for sec in staged_sections(change, layout):
        if sec not in seen:
            seen.add(sec)
            sections.append(sec)
    sections.sort()
    leaves: list[Leaf] = []
    for sec in sections:
        rd = _resolved_section_dir(change, layout, sec)
        if not (rd / "concept.yaml").is_file():
            continue   # create 節尚未結晶（無 concept.yaml）→ 不入 union（同正式 develop-only 語義）
        leaves.append(_load_leaf_from(sec, rd))
    return leaves


# ── OverlayLayout（render preview 用：staging 讀、preview 寫）──────────

class OverlayLayout:
    """薄包裝：對外暴露 render/read_ledger/write_ledger/style_fingerprint 用到的 Layout 介面，
    把讀導向「staging 優先」、把 render 產物（_latest / ledger）導向 change 的 preview 區。

    v1 union 粒度：corpus 節＝整包複製（section_dir 解析 staging-or-official）；writing-guide＝
    檔級 overlay。glossary/config 的 preview union 為 v1 已知窄口（landing 仍整檔搬回）。"""

    def __init__(self, base: Layout, change: Change):
        self._base = base
        self._change = change
        self._preview = preview_dir(change.dir)

    # ── 透傳屬性 ──
    @property
    def planning_home(self) -> Path:
        return self._base.planning_home

    @property
    def project_root(self) -> Path:
        return self._base.project_root

    @property
    def corpus_dir(self) -> Path:
        return self._base.corpus_dir

    @property
    def docs_dir(self) -> Path:
        return self._base.docs_dir

    @property
    def docs_layout(self) -> str:
        return self._base.docs_layout

    def is_archived_path(self, p: Path) -> bool:
        return self._base.is_archived_path(p)

    def article_of(self, section: str) -> str:
        return self._base.article_of(section)

    def section_id(self, leaf_dir: Path) -> str:
        return self._base.section_id(leaf_dir)

    def leaf_dirs(self):
        return self._base.leaf_dirs()

    def articles(self):
        return self._base.articles()

    def docs_assets_dir(self, article: str | None = None) -> Path:
        return self._base.docs_assets_dir(article)

    # ── staging-first 讀 ──
    def section_dir(self, section: str) -> Path:
        return _resolved_section_dir(self._change, self._base, section)

    @property
    def writing_guide(self) -> Path:
        staged = staging_target(self._change.dir, self._base, self._base.writing_guide)
        return staged if staged.is_file() else self._base.writing_guide

    # ── preview 產物（正式 docs 永不被暫存污染，D2）──
    def docs_latest(self, article: str) -> Path:
        return self._preview / f"{article}_latest.md"

    def docs_ledger(self, article: str) -> Path:
        return self._preview / f"{article}.sections.yaml"

    def docs_ledger_legacy(self, article: str) -> Path:
        # preview 無 legacy sidecar：回一個不存在的路徑（read_ledger 會略過）。
        return self._preview / f".{article}.legacy.none"


# ── preview seed（★G2）＋ render ──────────────────────────────────────

def seed_preview(layout: Layout, change: Change, article: str) -> None:
    """★G2：預覽成品檔與帳本 MUST 從正式版初始化。首次對某 article 存取 preview 前，把正式
    `_latest.md` 與正式 ledger 複製進 preview 區——否則首次 preview render 找不到既有散文、
    每節誤標 unwritten，淹沒 change 的真實範圍。已 seed（preview _latest 存在）＝不重複。"""
    pv = preview_dir(change.dir)
    pv_latest = pv / f"{article}_latest.md"
    if pv_latest.exists():
        return
    pv.mkdir(parents=True, exist_ok=True)
    off_latest = layout.docs_latest(article)
    if off_latest.is_file():
        pv_latest.write_text(off_latest.read_text(encoding="utf-8"), encoding="utf-8",
                             newline="\n")
    off_ledger = layout.docs_ledger(article)
    if not off_ledger.is_file():
        off_ledger = layout.docs_ledger_legacy(article)
    pv_ledger = pv / f"{article}.sections.yaml"
    if off_ledger.is_file():
        pv_ledger.write_text(off_ledger.read_text(encoding="utf-8"), encoding="utf-8",
                             newline="\n")


def _write_preview_ledger(change: Change, article: str, sections: dict) -> None:
    from dspx.render import LEDGER_FINGERPRINT_VERSION
    pv = preview_dir(change.dir)
    pv.mkdir(parents=True, exist_ok=True)
    data = {"article": article, "fingerprint": LEDGER_FINGERPRINT_VERSION, "sections": sections}
    (pv / f"{article}.sections.yaml").write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8", newline="\n")


def enlist_stale(layout: Layout, change: Change, section: str) -> bool:
    """入單標髒（★task 2.3）：對 staging 側（preview）帳本的該節設 redraft 旗標——status 遂顯
    stale-own，draft pickup 零改動接手；一次真重渲染（散文改）才清旗標＝synced。回傳是否標成。
    create target＝unwritten 天然不綠、無帳本記錄可標（回 False）。"""
    article = section.split("/", 1)[0]
    seed_preview(layout, change, article)
    ledger = _read_preview_ledger(change, article)
    rec = ledger.get(section)
    if not isinstance(rec, dict):
        return False   # 未撰寫（create 或正式面本就無散文）→ 無記錄可標
    rec["redraft"] = True
    ledger[section] = rec
    _write_preview_ledger(change, article, ledger)
    return True


# ── target ↔ section 解析（instructions / status / publish 用）────────

def section_of_ref(ref: str, leaves: list[Leaf]) -> str | None:
    """target ref（concept.id 或 section 路徑）→ 它所屬 section 路徑；找不到 → None。"""
    for lf in leaves:
        if lf.section == ref or (lf.concept_id and str(lf.concept_id) == ref):
            return lf.section
    return None


def article_of_ref(ref: str, leaves: list[Leaf], change: Change | None = None) -> str | None:
    """target ref → 所屬 article。section/concept.id 走 leaves；create 路徑取首段。"""
    sec = section_of_ref(ref, leaves)
    if sec is not None:
        return sec.split("/", 1)[0]
    t = change.target_by_ref(ref) if change else None
    if t is not None and t.kind == "create" and "/" in t.ref:
        return t.ref.split("/", 1)[0]
    return None


def changes_hitting_section(layout: Layout, section: str, concept_id: str | None,
                            leaves: list[Leaf]) -> list[tuple[Change, Target]]:
    """哪些 active change 的 target 命中此 section（instructions active-change context）。"""
    out: list[tuple[Change, Target]] = []
    for change in iter_active_changes(layout):
        for t in change.targets:
            if t.ref == section or (concept_id and t.ref == concept_id):
                out.append((change, t))
            elif t.kind == "create" and t.ref == section:
                out.append((change, t))
    return out


def changes_hitting_article(layout: Layout, article: str,
                            leaves: list[Leaf]) -> list[Change]:
    """哪些 active change 命中此 article（publish policy 閘）。"""
    out: list[Change] = []
    for change in iter_active_changes(layout):
        for t in change.targets:
            if article_of_ref(t.ref, leaves, change) == article:
                out.append(change)
                break
    return out


# ── 驗收全導出（per-action 現態判準、零時序；D4 / 3.1 / 3.1b）─────────

def _read_preview_ledger(change: Change, article: str) -> dict:
    """讀 change preview 區的 staging 側 sidecar 帳本（各節 own/anc/deps/norm/style/prose）。"""
    pv = preview_dir(change.dir) / f"{article}.sections.yaml"
    if not pv.is_file():
        return {}
    try:
        data = yaml.safe_load(pv.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {}
    sections = data.get("sections") if isinstance(data, dict) else None
    return dict(sections) if isinstance(sections, dict) else {}


def _preview_verdict_sections(change: Change, article: str) -> set[str]:
    """preview 區 verdicts journal 記過裁決（ack/ack-own/stale/redraft）的節集合（review/align
    的 ack 留痕證據）。"""
    pv = preview_dir(change.dir) / f"{article}.verdicts.yaml"
    if not pv.is_file():
        return set()
    try:
        data = yaml.safe_load(pv.read_text(encoding="utf-8")) or []
    except yaml.YAMLError:
        return set()
    out: set[str] = set()
    if isinstance(data, list):
        for e in data:
            if isinstance(e, dict) and e.get("section"):
                out.add(str(e["section"]))
    return out


@dataclass
class TargetStatus:
    ref: str
    action: str
    section: str | None
    done: bool
    detail: str


def derive_change_status(layout: Layout, change: Change, schema) -> list[TargetStatus]:
    """對每個 target 導出現態 done（讀本單 **staging 側**帳本，per-action 判準、零時序）。

    核心反作弊（3.1b）：revise/redraft 的 done 要求「入單標髒（stale/unwritten）→ apply 期有
    合法 render → 現在 synced **且散文確實改過**（preview prose ≠ 正式 baseline）」——單看當下
    synced 不足以證明本單做過事（否則一個本就 synced 的節矇過整個「驗收永不手勾」保證）。判準
    只讀本單 staging（preview 帳本＋preview 產物），別的單/零開單改的是正式面，互不污染（MOE R1
    由構造解掉）。"""
    from dspx.commands.status import _leaf_row
    from dspx.model import decision_index

    leaves = load_union(layout, change)
    by_section = {lf.section: lf for lf in leaves}
    dindex = decision_index(leaves)
    overlay = OverlayLayout(layout, change)

    # 各 article 的 preview 帳本 ＋ 正式 baseline 帳本（偵測「散文真改過」）。
    from dspx.render import read_ledger
    preview_ledgers: dict[str, dict] = {}
    official_ledgers: dict[str, dict] = {}
    verdict_sections: dict[str, set[str]] = {}

    def _for_article(article: str):
        if article not in preview_ledgers:
            preview_ledgers[article] = _read_preview_ledger(change, article)
            official_ledgers[article] = read_ledger(layout, article)
            verdict_sections[article] = _preview_verdict_sections(change, article)
        return (preview_ledgers[article], official_ledgers[article],
                verdict_sections[article])

    out: list[TargetStatus] = []
    for t in change.targets:
        section = section_of_ref(t.ref, leaves)
        if section is None and t.kind == "create":
            section = t.ref if "/" in t.ref else None
        done, detail = _derive_one(layout, change, schema, t, section, leaves,
                                   by_section, dindex, overlay, _for_article)
        out.append(TargetStatus(ref=t.ref, action=t.action, section=section,
                                 done=done, detail=detail))
    return out


def _sync_of(overlay, leaf, schema, preview_ledger, by_section, dindex) -> str:
    from dspx.commands.status import _leaf_row
    row = _leaf_row(overlay, leaf, schema, True, preview_ledger, by_section, dindex)
    return row["sync"]


def _derive_one(layout, change, schema, t, section, leaves, by_section, dindex,
                overlay, for_article) -> tuple[bool, str]:
    from dspx.commands.status import run_file_check

    # ── file target：hash ≠ 記錄 baseline（人語義確認在 archive 現場）──
    if t.kind == "file":
        official = layout.project_root / t.ref
        staged = staging_target(change.dir, layout, official)
        cur = content_hash(staged) if staged.is_file() else content_hash(official)
        if t.baseline is None:
            return False, "file target has no recorded baseline"
        if cur is not None and cur != t.baseline:
            return True, "file changed (hash ≠ baseline)"
        return False, "file unchanged (hash == baseline)"

    # ── move：真正的 mv 延到收案（G3）；apply 期只要 union check 綠即導出 done（結構意圖已記）──
    if t.action == "move":
        return True, "move intent recorded (real mv runs at archive)"

    if section is None:
        # retire 的 ref 可能已從 union 消失（已在 staging 退場）＝done
        if t.action == "retire":
            return True, "section retired in staging"
        return False, f"ref \"{t.ref}\" does not resolve to a section"

    leaf = by_section.get(section)
    if leaf is None:
        if t.action == "retire":
            return True, "section retired in staging"
        return False, f"section \"{section}\" not in union view"

    article = section.split("/", 1)[0]
    preview_ledger, official_ledger, verdicts = for_article(article)
    sync = _sync_of(overlay, leaf, schema, preview_ledger, by_section, dindex)

    if t.action == "retire":
        return False, "retire target still present as a live section (not yet retired in staging)"

    if t.action == "create":
        # create ⇔ ready + synced（concept 齊、欄位完整、散文已寫且 fresh）
        if run_file_check(leaf, schema):
            return False, "created section not ready (required fields incomplete)"
        if sync == "synced":
            return True, "created + synced"
        return False, f"created section is {sync} (needs prose)"

    if t.action in ("revise", "redraft"):
        if sync != "synced":
            return False, f"{sync} (rewrite the prose)"
        # ★反作弊：synced 還不夠——散文必須真的改過（preview prose ≠ 正式 baseline）
        pv_prose = _prose_of(preview_ledger.get(section))
        off_prose = _prose_of(official_ledger.get(section))
        if pv_prose is not None and pv_prose == off_prose:
            return False, ("synced but prose is byte-identical to the official baseline — no work "
                           "happened this change (enlist-stale → rewrite → synced is required)")
        return True, "synced (prose rewritten)"

    if t.action == "align":
        # align ⇔ 清髒（stale-inherited/style 消失）或 ack 留痕
        if sync in ("stale-own", "stale-upstream", "stale-norm"):
            return False, f"{sync} (a content change, not an alignment — rewrite)"
        if sync in ("stale-inherited", "stale-style"):
            return False, f"{sync} (align the prose or render --ack)"
        return True, "aligned (inherited/style cleared)"

    if t.action == "review":
        # review ⇔ ack 留痕（preview verdicts 有本節記錄）
        if section in verdicts:
            return True, "reviewed (verdict recorded)"
        return False, "no review verdict recorded (render --ack with a reason)"

    return False, f"unknown action \"{t.action}\""


def _prose_of(rec) -> str | None:
    if isinstance(rec, dict):
        return rec.get("prose")
    return None


def is_archivable(statuses: list[TargetStatus]) -> bool:
    return bool(statuses) and all(s.done for s in statuses)


# ── fork 漂移守門（★#9 / D5 / task 3.4）────────────────────────────────

def fork_drift(layout: Layout, change: Change) -> list[dict]:
    """逐 staged 檔比對 fork 當下的正式 hash 與現值；不符＝第三方（零開單直改或另單先收案）動過。
    回 [{path, forked, current}]（漂移清單，空＝無漂移）。"""
    drift: list[dict] = []
    for rel, forked in sorted(change.fork_hashes.items()):
        official = layout.project_root.joinpath(*rel.split("/"))
        cur = content_hash(official)
        if cur != forked:
            drift.append({"path": rel, "forked": forked, "current": cur})
    return drift


# ── 收案落地 primitives（whole-file/dir 替換、無文字合併；D3/G4/G5）────

def land_corpus_section(layout: Layout, change: Change, section: str) -> None:
    """把 staging 的節「自己的來源檔」整檔搬回正式 corpus（★P0：**只**動這個 target 節、逐檔
    覆蓋——永不 rmtree 官方節夾、永不觸及子章節資料夾或非 target 檔）。暫存中被刪除的來源檔
    （fork 時有、現在無）在正式面對應刪除（反映意圖）；子章節/旁節對 landing 完全隱形。"""
    official = layout.section_dir(section)
    staged = staging_target(change.dir, layout, official)
    if not _has_own_files(staged):
        return
    official.mkdir(parents=True, exist_ok=True)
    for name in _SECTION_OWN_FILES:
        sf = staged / name
        of = official / name
        if sf.is_file():
            shutil.copy2(sf, of)
        elif of.is_file() and workspace_rel(layout, of) in change.fork_hashes:
            of.unlink()   # 暫存中被作者刪除的來源檔 → 正式面同步刪（僅限本節自己的檔）
    sassets = staged / _SECTION_ASSET_DIR
    if sassets.is_dir():
        oassets = official / _SECTION_ASSET_DIR
        if oassets.exists():
            shutil.rmtree(oassets)
        shutil.copytree(sassets, oassets)


def land_file(layout: Layout, change: Change, official: Path) -> bool:
    """把 staging 的單檔整檔搬回正式路徑（森林級檔/外部 file target）。回傳是否有落地。"""
    staged = staging_target(change.dir, layout, official)
    if not staged.is_file():
        return False
    official.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(staged, official)
    return True


def slot_patch_deliverable(layout: Layout, change: Change, article: str,
                           sections: set[str]) -> list[str]:
    """slot 補丁（G5 純內容路）：把 preview `_latest.md` 中受影響節的散文塞回正式 `_latest.md`
    對應 marker 格、其餘格 byte 不動。回傳被補的節清單。補丁前呼叫端須先做 drift 偵測。"""
    from dspx.render import (GROUP_MARKER_RE, MARKER_RE, parse_section_bodies,
                             section_marker)
    official = layout.docs_latest(article)
    preview = preview_dir(change.dir) / f"{article}_latest.md"
    if not official.is_file() or not preview.is_file():
        return []
    preview_bodies = parse_section_bodies(preview.read_text(encoding="utf-8"))
    text = official.read_text(encoding="utf-8")
    lines = text.split("\n")
    out: list[str] = []
    patched: list[str] = []
    i = 0
    cur: str | None = None
    header_kept = False
    while i < len(lines):
        line = lines[i]
        m = MARKER_RE.match(line)
        gm = GROUP_MARKER_RE.match(line)
        if m:
            cur = m.group(1)
            out.append(line)
            i += 1
            # 保留 marker 後的第一行標題（render 產）；替換其後的散文塊直到下個 marker。
            if cur in sections and cur in preview_bodies:
                # 收集本節到下個 marker 的行
                # 先寫出接續的空行/標題行（render 生成的），再插入 preview 散文
                seg: list[str] = []
                j = i
                while j < len(lines) and not MARKER_RE.match(lines[j]) \
                        and not GROUP_MARKER_RE.match(lines[j]):
                    seg.append(lines[j])
                    j += 1
                # seg = [可能空行, 標題行, 空行, 舊散文...]；保留到標題行與其後一空行，換散文
                keep: list[str] = []
                k = 0
                while k < len(seg) and not seg[k].strip():
                    keep.append(seg[k]); k += 1
                if k < len(seg) and re.match(r"^#{1,6}\s", seg[k]):
                    keep.append(seg[k]); k += 1
                    if k < len(seg) and not seg[k].strip():
                        keep.append(seg[k]); k += 1
                out.extend(keep)
                body = preview_bodies.get(cur, "").strip()
                if body:
                    out.append(body)
                    out.append("")
                patched.append(cur)
                i = j
                continue
            continue
        if gm:
            cur = None
        out.append(line)
        i += 1
    official.write_text("\n".join(out), encoding="utf-8", newline="\n")
    return patched


def whole_file_replace_deliverable(layout: Layout, change: Change, article: str) -> bool:
    """整份換（G5 動結構路）：正式 `_latest.md` 以 preview 全文替換。"""
    official = layout.docs_latest(article)
    preview = preview_dir(change.dir) / f"{article}_latest.md"
    if not preview.is_file():
        return False
    official.parent.mkdir(parents=True, exist_ok=True)
    official.write_text(preview.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    return True


def move_to_state(layout: Layout, change: Change, new_state: str) -> Path:
    """把 change 容器整包搬到目標狀態根（_archive/_abandoned）；回新路徑。"""
    src = change.dir
    dst = change_dir(layout, change.id, new_state)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        raise ChangeError(f"cannot move change to {dst}: destination already exists")
    shutil.move(str(src), str(dst))
    change.dir = dst
    change.state = new_state
    return dst
