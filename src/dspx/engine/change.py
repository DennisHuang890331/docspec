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

from dspx.engine.layout import Layout
from dspx.engine.model import Leaf, content_hash

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
    # ★比照 OpenSpec：change 容器收在引擎 home 夾（docspec/）底下，與 corpus/ledger/glossary 一致，
    # 不散在專案根（changes/ 是引擎內部修改事件管理狀態、非人要讀的東西；人只讀 docs/）。
    return layout.planning_home / CHANGES_DIR


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
    from dspx.engine.model import ModelError, _load_yaml
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


def record_fork(change: Change, layout: Layout, official: Path) -> None:
    """記錄單一 official 檔 fork 當下的 hash（★#9 漂移守門）。森林級檔（glossary/writing-guide/
    config）與外部 file target 的 copy-on-write 由 stage_file 呼叫；corpus 節走結構化 store fork
    key（見 _record_store_fork）。"""
    if official.is_file():
        change.fork_hashes[workspace_rel(layout, official)] = content_hash(official) or ""


# ── store-backed staging（★Phase C：結構化 merge-by-section-id、非 text-delta）──────
#
# store 篇的 staging＝`changes/<id>/staging/<article>.yaml`（partial store，只含被 stage 的節
# 記錄），非散檔鏡像。stage＝深拷貝正式記錄進 partial store；create＝leaf 記錄 concept=None
# 佔位；退場＝tombstone 記號。union＝正式記錄 ∪ staging overlay。landing＝讀正式 store→只換
# target 記錄→revision+1→canonical dump（旁節記錄全程同一物件＝byte 不變）。fork key＝逐節逐
# 分類 `<article>#<path>#<category>` 的 canonical JSON hash。

def staging_store_path(cdir: Path, article: str) -> Path:
    """partial store：`changes/<id>/staging/<article>.yaml`（只含被 stage 的節記錄）。"""
    return staging_dir(cdir) / f"{article}.yaml"


def _load_staging_article(cdir: Path, article: str):
    """讀 change 的 partial store（無 → None）；每次寫入都重封條，故 verify=True。"""
    from dspx.engine import store as _store
    p = staging_store_path(cdir, article)
    if not p.is_file():
        return None
    return _store.load_article(p, verify=True)


def _save_staging_article(cdir: Path, article_obj, schema=None) -> None:
    from dspx.engine import store as _store
    if schema is None:
        from dspx.engine.schema import load_schema
        schema = load_schema()
    _store.save_article_to(staging_store_path(cdir, article_obj.name), article_obj, schema)


def _store_fork_key(article: str, section: str, category: str) -> str:
    """store fork 守門 key：`<article>#<path>#<category>`（`#` 於節路徑/檔名非法＝安全判別符）。"""
    return f"{article}#{section}#{category}"


def _record_store_fork(change: Change, article: str, section: str, off_rec) -> None:
    """記正式記錄各分類 fork 當下的 hash（漂移守門逐節逐分類粒度）。"""
    from dspx.engine import store as _store
    for cat in (_store.CAT_CONCEPT, _store.CAT_DECISIONS, _store.CAT_MATERIAL):
        change.fork_hashes[_store_fork_key(article, section, cat)] = \
            _store.category_hash(off_rec, cat)


def _stage_store_section(change: Change, layout: Layout, section: str) -> None:
    """store 篇 stage：把正式 store 該 path 記錄深拷貝進 partial store（已 stage＝不覆蓋暫存編輯）。
    正式面尚無此節（create）＝落 leaf 記錄 concept=None 佔位（未結晶＝不入 union）。"""
    import copy

    from dspx.engine import store as _store
    article = layout.article_of(section)
    staging = _load_staging_article(change.dir, article)
    if staging is None:
        staging = _store.Article(name=article, revision=0, records=[])
    if staging.record_by_path(section) is not None:
        return   # 已 stage：不覆蓋既有暫存編輯（承檔案粒度 stage 的語義）
    official = _store.load_article(_store.store_path(layout, article), verify=False)
    off_rec = official.record_by_path(section)
    if off_rec is not None:
        staging.records.append(copy.deepcopy(off_rec))
        _record_store_fork(change, article, section, off_rec)
    else:
        staging.records.append(_store.SectionRecord(path=section, kind="leaf"))
    _save_staging_article(change.dir, staging)


def _unstage_store_section(change: Change, layout: Layout, section: str) -> None:
    """store 篇 unstage：從 partial store 移除該記錄＋清該節三分類 fork key。"""
    from dspx.engine import store as _store
    article = layout.article_of(section)
    staging = _load_staging_article(change.dir, article)
    if staging is not None:
        staging.records = [r for r in staging.records if r.path != section]
        _save_staging_article(change.dir, staging)
    for cat in (_store.CAT_CONCEPT, _store.CAT_DECISIONS, _store.CAT_MATERIAL):
        change.fork_hashes.pop(_store_fork_key(article, section, cat), None)


def stage_section(change: Change, layout: Layout, section: str) -> None:
    """corpus 節暫存化（★store-only：結構化 partial store）。把正式 store 該 path 記錄深拷貝進
    `changes/<id>/staging/<article>.yaml`（已 stage＝不覆蓋既有暫存編輯）；正式面尚無此節（create）＝
    落 leaf 記錄 concept=None 佔位（未結晶＝不入 union）。"""
    _stage_store_section(change, layout, section)


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
    """丟棄某節的 staging（★8.4 remove-target 用；★store-only）：從 partial store 移除該記錄＋
    清該節三分類 fork key＋清 preview 側入單標髒（該 target 已不在單，不再需要 stale 信號）。"""
    _unstage_store_section(change, layout, section)
    _clear_preview_redraft(change, section)


def _clear_preview_redraft(change: Change, section: str) -> None:
    """該 target 已不在單→清 preview 帳本的 redraft 標（backend-neutral，走 article 名）。"""
    article = section.split("/", 1)[0]
    ledger = _read_preview_ledger(change, article)
    rec = ledger.get(section)
    if isinstance(rec, dict) and rec.get("redraft"):
        rec.pop("redraft", None)
        ledger[section] = rec
        _write_preview_ledger(change, article, ledger)


# ── union view 載入（★store-only：正式記錄 ∪ staging overlay）──────────

def load_union(layout: Layout, change: Change) -> list[Leaf]:
    """union view：正式 store 記錄 ∪ staging overlay（整記錄蓋／tombstone 刪／pending-create 佔位），
    合成森林 leaves（依 section 路徑排序）。無 change context 時呼叫端走 model.load_project。"""
    leaves = _union_store_leaves(layout, change)
    leaves.sort(key=lambda lf: lf.section)
    return leaves


def _union_store_leaves(layout: Layout, change: Change) -> list[Leaf]:
    """每個 store 篇：正式記錄 dict ← staging overlay（整記錄蓋／tombstone 刪／pending-create 佔位）
    → 建 Leaf。concept=None（未結晶 create）＝不入 union（同散檔 develop-only 語義）。"""
    from dspx.engine import store as _store
    out: list[Leaf] = []
    for article in _store.store_articles(layout):
        official = _store.load_article(_store.store_path(layout, article), verify=False)
        recs = {r.path: r for r in official.records}
        staging = _load_staging_article(change.dir, article)
        if staging is not None:
            for r in staging.records:
                if r.kind == "tombstone":
                    recs.pop(r.path, None)
                else:
                    recs[r.path] = r
        for _path, r in recs.items():
            if r.kind == "leaf" and r.concept is not None:
                out.append(_store.leaf_from_record(layout, r))
    return out


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
    # ★store-only：corpus 節真相走 store 記錄（render preview 由 load_union 供 leaves），section_dir
    # 只服務「該節目錄」名目路徑（assets/docs_assets 等 backend-neutral 查詢），直接透傳正式路徑。
    def section_dir(self, section: str) -> Path:
        return self._base.section_dir(section)

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
    from dspx.engine.render import LEDGER_FINGERPRINT_VERSION
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


# ── put/get 寫讀路由（感知 active change：staging 優先、official 凍結）────────

def section_concept_id(layout: Layout, section: str) -> str | None:
    """讀某節正式 concept 的 id（供 put/get 判 target ref==concept.id）；缺/未結晶 → None。
    ★store-only：由正式 store 記錄供（尚無 store／尚無 concept＝None，靠 section 路徑匹配 target）。"""
    from dspx.engine import store as _store
    article = layout.article_of(section)
    art = _store.cached_article(layout, article)
    rec = art.record_by_path(section) if art is not None else None
    if rec is not None and rec.concept and rec.concept.get("id"):
        return str(rec.concept["id"])
    return None


def changes_staging_section(layout: Layout, section: str,
                            concept_id: str | None) -> list[Change]:
    """以此節（section 路徑或其 concept.id、或 create 路徑）為 target 的 active changes，
    去重（一張 change 即使多個 target 命中也只列一次）。"""
    out: list[Change] = []
    seen: set[str] = set()
    for change, _t in changes_hitting_section(layout, section, concept_id, []):
        if change.id not in seen:
            seen.add(change.id)
            out.append(change)
    return out


class RoutingAmbiguous(Exception):
    """一節被多張 active change 同時 stage：put/get 不得猜、要求 `--change <id>` 指名。"""

    def __init__(self, section: str, candidates: list[Change]):
        super().__init__(section)
        self.section = section
        self.candidates = candidates


def routing_change_for(layout: Layout, section: str, *,
                       explicit_id: str | None = None) -> Change | None:
    """某節 put/get 該路由到哪張 active change 的 staging？

    - `explicit_id` 指名：必須是 active 且以此節為 target，否則 ChangeError（不隱式加 target）。
    - 未指名：0 張命中 → None（照舊 official）；1 張 → 該張；多張 → RoutingAmbiguous。
    """
    concept_id = section_concept_id(layout, section)
    candidates = changes_staging_section(layout, section, concept_id)
    if explicit_id is not None:
        chosen = next((c for c in candidates if c.id == explicit_id), None)
        if chosen is not None:
            return chosen
        state = change_state(layout, explicit_id)
        if state is None:
            raise ChangeError(f"--change \"{explicit_id}\": no change by that id")
        if state != STATE_ACTIVE:
            raise ChangeError(f"--change \"{explicit_id}\" is {state}, not active "
                              "(only an active change has a staging branch to write into)")
        raise ChangeError(
            f"--change \"{explicit_id}\" does not target section \"{section}\" — enlist it first: "
            f"`docspec change add-target {explicit_id} {section} --action revise`")
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    raise RoutingAmbiguous(section, candidates)


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
    from dspx.commands.query.status import _leaf_row
    from dspx.engine.model import decision_index

    leaves = load_union(layout, change)
    by_section = {lf.section: lf for lf in leaves}
    dindex = decision_index(leaves)
    overlay = OverlayLayout(layout, change)

    # 各 article 的 preview 帳本 ＋ 正式 baseline 帳本（偵測「散文真改過」）。
    from dspx.engine.render import read_ledger
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
    from dspx.commands.query.status import _leaf_row
    row = _leaf_row(overlay, leaf, schema, True, preview_ledger, by_section, dindex)
    return row["sync"]


def _derive_one(layout, change, schema, t, section, leaves, by_section, dindex,
                overlay, for_article) -> tuple[bool, str]:
    from dspx.commands.query.status import run_file_check

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
    """逐 fork key 比對 fork 當下的正式 hash 與現值；不符＝第三方（零開單直改或另單先收案）動過。
    回 [{path, forked, current}]（漂移清單，空＝無漂移）。

    **backend 路由**：store fork key（`<article>#<path>#<category>`，含 `#`）比對正式 store 記錄
    的分類 hash；散檔 fork key（workspace 相對路徑）比對檔內容 hash。"""
    from dspx.engine import store as _store
    drift: list[dict] = []
    for rel, forked in sorted(change.fork_hashes.items()):
        if "#" in rel:
            cur = _store_current_category_hash(layout, rel)
        else:
            official = layout.project_root.joinpath(*rel.split("/"))
            cur = content_hash(official)
        if cur != forked:
            drift.append({"path": rel, "forked": forked, "current": cur})
    return drift


def _store_current_category_hash(layout: Layout, fork_key: str) -> str | None:
    """store fork key → 正式 store 該節該分類的現值 hash（記錄已不在＝退場等→回 None，觸發漂移）。"""
    from dspx.engine import store as _store
    article, section, category = fork_key.split("#", 2)
    if not _store.article_has_store(layout, article):
        return None
    art = _store.cached_article(layout, article)
    rec = art.record_by_path(section) if art is not None else None
    if rec is None:
        return None
    return _store.category_hash(rec, category)


# ── 收案落地 primitives（whole-file/dir 替換、無文字合併；D3/G4/G5）────

def land_corpus_section(layout: Layout, change: Change, section: str, schema=None) -> None:
    """把某 target 節從 staging 落地正式 corpus（★store-only：結構化 merge-by-section-id）。
    讀正式 store→只換 target 記錄→revision+1→canonical dump→原子寫。

    ★P0：**只**動這個 target 節、非 target 節 byte 全程不變——旁節記錄全程同一物件、序列化冪等
    ⇒ 其序列化 block byte 不變。"""
    _land_store_section(layout, change, section, schema)


def _land_store_section(layout: Layout, change: Change, section: str, schema=None) -> None:
    """store 篇結構化 landing（★P0 非 text-delta）：讀正式 store→**只**對 target path 換整筆記錄
    （pending-create 轉正／tombstone 刪／整筆替換）→revision+1→canonical dump→原子寫。

    非 target 記錄全程是**正式 store 的同一 parse 物件**（無任何逐行操作）；序列化冪等＋store 永遠
    是 canonical 產物 ⇒ 其序列化 block byte 不變。錨是 path key、替換單位是完整記錄。staging 無
    此節記錄（未動）＝landing 對該節無操作（no-op）。"""
    from dspx.engine import store as _store
    if schema is None:
        from dspx.engine.schema import load_schema
        schema = load_schema()
    article = layout.article_of(section)
    staging = _load_staging_article(change.dir, article)
    staged_rec = staging.record_by_path(section) if staging is not None else None
    if staged_rec is None:
        return   # 該節未被 stage（純 prose revise、記錄零改）→ 正式 store 不動
    official = _store.load_article(_store.store_path(layout, article), verify=False)
    is_tombstone = staged_rec.kind == "tombstone"
    new_records: list = []
    replaced = False
    for r in official.records:
        if r.path == section:
            replaced = True
            if not is_tombstone:
                new_records.append(staged_rec)   # 整筆換入（target）
            # tombstone：略過＝從正式移除
        else:
            new_records.append(r)                # 旁節：正式 store 的同一物件（byte 不變地基）
    if not replaced and not is_tombstone:
        new_records.append(staged_rec)           # pending-create 轉正（正式面原無此節）
    new_art = _store.Article(name=article, revision=official.revision + 1, records=new_records)
    _store.save_article(layout, new_art, schema)


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
    from dspx.engine.render import (GROUP_MARKER_RE, MARKER_RE, parse_section_bodies,
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
