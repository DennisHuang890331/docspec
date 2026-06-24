"""roadmap：計劃待辦 backlog（artifact＝「計劃了、還沒做」的耐久記錄）。

定位（SoT §1 roadmap bullet ＋ memory roadmap-artifact-design）：
- 只收「計劃了、還沒做、關於本森林文件」的工作；done **掉出**（不累積成大表）。
- 兩個 store（按 owner 分）：
  - per-doc（單一文件 owner）＝`corpus/<article>/roadmap.yaml`（root section dir，隨樹退場）。
  - forest（跨文件、無單一 owner）＝`<planning_home>/roadmap.yaml`（森林級）。
  - **按需生成**：沒待辦＝無檔；load 回 []。view 永遠可算。
- 這層只「忠實載入＋結構驗證」；語義與「做不做」一律不判（→ derive / audit）。
  unblocked/blocked 是 derive 視圖（Seam 2），非 check error。
"""

from __future__ import annotations

from pathlib import Path

import yaml

from dspx.layout import Layout

KINDS = ("gap", "task")
STATUSES = ("open", "doing", "done", "dropped")
ROADMAP_FILE = "roadmap.yaml"
FOREST_TARGET = "forest"


def _load_entries(path: Path, store: str) -> list[dict]:
    """讀 {entries:[...]}；缺席→[]。標每筆 `_store`。"""
    if not path.is_file():
        return []
    from dspx.model import ModelError, keyed_list
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries = keyed_list(raw, path, "entries", error=ModelError)  # 誤名頂層 key fail-loud
    out: list[dict] = []
    for e in entries:
        tagged = dict(e)
        tagged["_store"] = store
        out.append(tagged)
    return out


def doc_roadmap_path(layout: Layout, article: str) -> Path:
    """per-doc roadmap 檔＝該文件 root section dir 下的 roadmap.yaml。"""
    return layout.section_dir(article) / ROADMAP_FILE


def forest_roadmap_path(layout: Layout) -> Path:
    return layout.planning_home / ROADMAP_FILE


def load_doc_roadmap(article_root_dir: Path, article: str | None = None) -> list[dict]:
    """讀某文件 root dir 下的 roadmap.yaml；缺席→[]。標 `_store="doc:<article>"`。"""
    name = article if article is not None else article_root_dir.name
    return _load_entries(article_root_dir / ROADMAP_FILE, f"doc:{name}")


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
        out.extend(load_doc_roadmap(layout.section_dir(art), art))
    return out


def validate_roadmap(entries: list[dict]) -> list[str]:
    """結構驗證：id 唯一（跨所有載入）、kind∈KINDS、status∈STATUSES、target 形式合法。

    target 形式＝`forest` literal 或一個字串 id（section id / section 路徑）。
    optional 欄（priority/note/done-to/waits-on）optional，不查。
    target 死引用＋放對檔＋depends-on/from-audit 死引用＋環＝check 層（需要 layout/leaves 脈絡）。
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
        if e.get("kind") not in KINDS:
            errs.append(f"{where}: kind \"{e.get('kind')}\" not in {KINDS}")
        if e.get("status") not in STATUSES:
            errs.append(f"{where}: status \"{e.get('status')}\" not in {STATUSES}")
        target = e.get("target")
        if target is None or (isinstance(target, str) and not target.strip()):
            errs.append(f"{where}: missing target")
        elif not isinstance(target, str):
            errs.append(f"{where}: target must be a string (section id or forest), got "
                        f"{type(target).__name__}")
    return errs
