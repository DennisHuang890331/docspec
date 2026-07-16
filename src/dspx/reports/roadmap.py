"""roadmap：計劃待辦 backlog（artifact＝「計劃了、還沒做」的耐久記錄）。

定位（SoT §1 roadmap bullet ＋ memory roadmap-artifact-design；change-event-layer 改版統一
無狀態模型——真專案 22 條中 10 條 done 帶長篇 done-to 佔近半篇幅之實證）：
- 只收「計劃了、還沒做、關於本森林文件」的工作；**在檔＝待辦、掉出＝完成**（不再有
  `status`/`done-to` 欄——這兩欄已刪，見 `validate_roadmap`）。
- 兩個 store（按 owner 分）：
  - per-doc（單一文件 owner）＝sibling 密封檔 `corpus/<article>.roadmap.yaml`。
  - forest（跨文件、無單一 owner）＝`<planning_home>/roadmap.yaml`（森林級）。
  - **按需生成**：沒待辦＝無檔；load 回 []。view 永遠可算。
- 完成分流（兩條路，見 `roadmap-archive` 相關 requirement）：
  (a) 晉升為 change（`change new --from-roadmap`）→ 收攏為 id/title/promoted-to、change
      archive 交易時 prune 出 roadmap.yaml；(b) 小工作無需開單 → `docspec roadmap done <id>
      --note "..."`（`mark_done`）把該 entry 移出 roadmap.yaml、append 一行進
      同層的 `roadmap-archive.yaml`（append-only，僅供人事後查閱、非引擎讀取）。
- 這層只「忠實載入＋結構驗證」；語義與「做不做」一律不判（→ derive / audit）。
  unblocked/blocked 是 derive 視圖（Seam 2），非 check error。
"""

from __future__ import annotations

import datetime
from pathlib import Path

import yaml

from dspx.engine.layout import Layout

KINDS = ("gap", "task")
ROADMAP_FILE = "roadmap.yaml"
ROADMAP_ARCHIVE_FILE = "roadmap-archive.yaml"
FOREST_TARGET = "forest"

# 已刪除的舊欄——出現即 check 報錯、指向分流機制。
_RETIRED_FIELDS = ("status", "done-to")


from dspx.engine.model import ModelError


class RoadmapError(ModelError):
    """roadmap 操作失敗（id 不存在等）。ModelError 子類＝既有 fail-loud/CLI 友善錯誤路徑一體。"""


def _roadmap_scope(path: Path) -> str:
    """密封 scope 標籤（自 path.name 推得）：forest 檔＝roadmap.yaml、doc 檔＝<article>.roadmap.yaml。"""
    n = path.name
    if n == ROADMAP_FILE:
        return "forest"
    suffix = ".roadmap.yaml"
    return f"doc:{n[:-len(suffix)]}" if n.endswith(suffix) else f"doc:{n}"


def _load_entries(path: Path, store: str) -> list[dict]:
    """讀密封 roadmap 檔（{entries:[...]}）；缺席→[]。標每筆 `_store`。封條不符 fail-loud 指路 fsck。"""
    from dspx.engine.sealed import load_sealed
    _rev, entries = load_sealed(path, list_key="entries", error_cls=RoadmapError)
    return [{**e, "_store": store} for e in entries]


def doc_roadmap_path(layout: Layout, article: str) -> Path:
    """per-doc roadmap 檔＝**sibling 密封檔** `corpus/<article>.roadmap.yaml`（一篇一檔 store 兄弟；
    形狀命中 hook `_is_store_file`＝自動守手改）。"""
    return layout.corpus_dir / f"{article}.roadmap.yaml"


def forest_roadmap_path(layout: Layout) -> Path:
    return layout.planning_home / ROADMAP_FILE


def forest_roadmap_archive_path(layout: Layout) -> Path:
    return layout.planning_home / ROADMAP_ARCHIVE_FILE


def load_doc_roadmap(layout: Layout, article: str) -> list[dict]:
    """讀 `corpus/<article>.roadmap.yaml`；缺席→[]。標 `_store="doc:<article>"`。"""
    return _load_entries(doc_roadmap_path(layout, article), f"doc:{article}")


def load_forest_roadmap(layout: Layout) -> list[dict]:
    """讀 forest roadmap.yaml；缺席→[]。標 `_store="forest"`。"""
    return _load_entries(forest_roadmap_path(layout), "forest")


def all_entries(layout: Layout, leaves: list) -> list[dict]:
    """forest 全部 entry ＋ 每個 article-root 的 doc roadmap（每個 distinct article 一份）。"""
    out: list[dict] = list(load_forest_roadmap(layout))
    seen_articles: list[str] = []
    for leaf in leaves:
        art = leaf.article
        if art and art not in seen_articles:
            seen_articles.append(art)
    for art in seen_articles:
        out.extend(load_doc_roadmap(layout, art))
    return out


def validate_roadmap(entries: list[dict]) -> list[str]:
    """結構驗證：id 唯一（跨所有載入）、kind∈KINDS、無已退休欄、target 形式合法。

    target 形式＝`forest` literal 或一個字串 id（section id / section 路徑）。
    optional 欄（priority/note/promoted-to/from-audit/waits-on）optional，不查形式。
    `status`/`done-to` 已刪——出現即報錯、指向分流機制（`docspec roadmap done` 或晉升為 change）。
    **collapsed entry（含 promoted-to）豁免 kind/target 必填**——晉升後 entry 收攏為
    id/title/promoted-to 三欄（搬家不複製），kind/target 已隨內容搬走；殘留 kind/target 之類
    「實質內容」不是 check 的事（那是 lint Vr2 軟提醒）。
    target 死引用＋放對檔＋depends-on/from-audit 死引用＋環＋promoted-to 反查＝check 層
    （需要 layout/leaves/change 脈絡）。
    """
    errs: list[str] = []
    seen: set[str] = set()
    for e in entries:
        rid = e.get("id")
        where = f"roadmap[{rid or e!r}]"
        if not rid:
            errs.append(f"{where}: missing id")
        elif str(rid) in seen:
            errs.append(f"duplicate roadmap id: {rid}")
        else:
            seen.add(str(rid))
        for field in _RETIRED_FIELDS:
            if field in e:
                errs.append(
                    f"{where}: \"{field}\" field is no longer used -- presence in roadmap.yaml "
                    "always means backlog; route completion instead: `docspec roadmap done "
                    f"{rid or '<id>'} --note \"...\"` for small direct work, or promote to a "
                    "change (`change new --from-roadmap`) whose archive prunes the entry")
        if e.get("promoted-to"):
            continue   # collapsed pointer: id/title/promoted-to only, no kind/target required
        if e.get("kind") not in KINDS:
            errs.append(f"{where}: kind \"{e.get('kind')}\" not in {KINDS}")
        target = e.get("target")
        if target is None or (isinstance(target, str) and not target.strip()):
            errs.append(f"{where}: missing target")
        elif not isinstance(target, str):
            errs.append(f"{where}: target must be a string (section id or forest), got "
                        f"{type(target).__name__}")
    return errs


# ── 完成分流：小工作直接結案（★task 4.1）───────────────────────────────

def now_date() -> str:
    return datetime.date.today().isoformat()


def _write_entries(path: Path, entries: list[dict]) -> None:
    """寫回密封 roadmap 檔（`_store` 標籤不落盤，寫入前剝除）；entries 淨空＝整檔刪除。"""
    if not entries:
        if path.is_file():
            path.unlink()
        return
    from dspx.engine.sealed import write_sealed
    clean = [{k: v for k, v in e.items() if k != "_store"} for e in entries]
    write_sealed(path, kind="roadmap", scope=_roadmap_scope(path), revision=1,
                 list_key="entries", items=clean)


def _append_archive(path: Path, record: dict) -> None:
    """roadmap-archive.yaml 追加一行（append-only；不手改）。"""
    import yaml
    from dspx.engine.model import _load_yaml
    existing: list[dict] = []
    if path.is_file():
        raw = _load_yaml(path) or {}
        existing = list(raw.get("entries") or [])
    existing.append(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = yaml.safe_dump({"entries": existing}, allow_unicode=True, sort_keys=False,
                          width=10000)
    path.write_text(body, encoding="utf-8", newline="\n")


def mark_done(layout: Layout, leaves: list, rid: str, note: str) -> dict:
    """`docspec roadmap done <id> --note "..."`：把 entry 移出 roadmap.yaml、append 一行進
    同層 roadmap-archive.yaml（append-only，{id, title, note, date}）。找遍 forest + 各 doc
    article 的 roadmap.yaml；找不到該 id → RoadmapError。"""
    from dspx.engine.sealed import load_sealed

    candidates: list[Path] = [forest_roadmap_path(layout)]
    seen_articles: list[str] = []
    for leaf in leaves:
        art = leaf.article
        if art and art not in seen_articles:
            seen_articles.append(art)
            candidates.append(doc_roadmap_path(layout, art))

    for roadmap_path in candidates:
        if not roadmap_path.is_file():
            continue
        _rev, entries = load_sealed(roadmap_path, list_key="entries", error_cls=RoadmapError)
        match: dict | None = None
        remaining: list[dict] = []
        for e in entries:
            if match is None and str(e.get("id")) == str(rid):
                match = e
                continue
            remaining.append(e)
        if match is None:
            continue
        _write_entries(roadmap_path, remaining)
        record = {"id": match.get("id"), "title": match.get("title"), "note": note,
                  "date": now_date()}
        # 完工紀錄一律進單一 forest archive（純 append、不封條；roadmap-archive 收斂）。
        _append_archive(forest_roadmap_archive_path(layout), record)
        return record

    raise RoadmapError(f"no roadmap entry \"{rid}\" found (searched forest + per-doc stores)")


def archived_roadmap_ids(layout: Layout) -> list[str]:
    """roadmap-archive.yaml 裡已封存的 entry id 清單（B5：id 配置跨區唯一＋check 撞號用）。"""
    path = forest_roadmap_archive_path(layout)
    if not path.is_file():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return []
    entries = data.get("entries") if isinstance(data, dict) else data   # {entries:[…]}（現行）或裸 list（防禦）
    if not isinstance(entries, list):
        return []
    return [str(e.get("id")) for e in entries if isinstance(e, dict) and e.get("id")]


def next_roadmap_id(layout: Layout, leaves: list) -> str:
    """全庫下一個 `R<n>` id——掃 forest＋各 doc＋**roadmap archive**（B5，engine-record-integrity）：
    done 封存過的序號永不重發，「R3」不會前世今生指兩件事。"""
    nums: list[int] = []
    ids = [str(e.get("id", "")) for e in all_entries(layout, leaves)]
    ids += archived_roadmap_ids(layout)
    for rid in ids:
        if rid.startswith("R") and rid[1:].isdigit():
            nums.append(int(rid[1:]))
    return f"R{(max(nums) + 1) if nums else 1}"


def add_entry(layout: Layout, leaves: list, *, kind: str, title: str, target: str,
              what: str = "", priority: str = "", depends_on: list | None = None,
              from_audit: str = "") -> dict:
    """`docspec roadmap add`＝roadmap 的唯一引擎寫入門（甲案；取代 agent 手編 roadmap.yaml）。
    驗欄位 → 路由（target=forest→forest 檔、target=section→該篇 doc 檔）→ 生 id → append + 密封 save。"""
    if kind not in KINDS:
        raise RoadmapError(f"kind \"{kind}\" not in {KINDS}")
    if not title.strip():
        raise RoadmapError("title must be non-empty")
    if not target.strip():
        raise RoadmapError("target must be non-empty (a section path/id, or 'forest')")
    if target == FOREST_TARGET:
        path = forest_roadmap_path(layout)
    else:
        from dspx.reports.audit import article_of_target
        art = article_of_target(target, leaves)
        if art is None:
            raise RoadmapError(
                f"target \"{target}\" does not resolve to any section "
                "(use a full section path/id, or 'forest' for a cross-document item)")
        path = doc_roadmap_path(layout, art)
    entry: dict = {"id": next_roadmap_id(layout, leaves), "kind": kind,
                   "title": title.strip(), "target": target}
    if what.strip():
        entry["what"] = what.strip()
    if priority.strip():
        entry["priority"] = priority.strip()
    if depends_on:                                    # #11：依賴（驅動 blocked/unblocked 視圖＋check DAG 驗）
        entry["depends-on"] = [d for d in depends_on if str(d).strip()]
    if from_audit.strip():                            # #11：晉升溯源鏈（check 驗死引用）
        entry["from-audit"] = from_audit.strip()
    from dspx.engine.sealed import load_sealed
    _rev, existing = load_sealed(path, list_key="entries", error_cls=RoadmapError)
    existing.append(entry)
    _write_entries(path, existing)
    return entry
