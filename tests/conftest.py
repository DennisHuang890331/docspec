"""共用測試夾具（section 模型）。

★store-only-corpus（階段 3）：`write_leaf`／`write_group` 一律建 **store corpus**——每篇語料
buffer 起來，每次寫入即 materialize 成 `corpus/<article>.yaml`（引擎獨占單檔 store）。
**翻一次工廠、個測不動**：既有測試對 store 跑，一次跑就知有沒有漏。
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


@pytest.fixture(autouse=True)
def _isolate_codex_home(tmp_path, monkeypatch):
    """codex command 寫到 $CODEX_HOME（預設 ~/.codex）；測試一律導向 tmp，別污染真 home。"""
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "_codex_home"))


@pytest.fixture
def make_project(tmp_path):
    """建立含中文路徑的最小 docspec 專案，回傳 planning home。"""

    def _make(config_text: str = "language: zh-TW\ndocs_layout: per-article\n") -> Path:
        home = tmp_path / "中文專案" / "docspec"
        home.mkdir(parents=True)
        (home / "config.yaml").write_text(config_text, encoding="utf-8")
        return home

    return _make


@pytest.fixture
def _corpus_store():
    """store 語料建構器（★store-only）：buffer 每篇的 section 記錄，每次寫入 materialize 成
    `corpus/<article>.yaml`。回傳 (put_record, del_record) 供 write_leaf/write_group 共用同一 buffer。"""
    from dspx.engine import store as _store
    from dspx.engine.schema import load_schema

    schema = load_schema()
    buffers: dict[tuple[str, str], dict[str, object]] = {}

    def _materialize(home: Path, article: str) -> None:
        recs = list(buffers[(str(home), article)].values())
        art = _store.Article(name=article, revision=1, records=recs)  # type: ignore[arg-type]
        text = _store.dump_article(art, schema)
        # dossier-layout：案卷夾＋定名檔 corpus/<article>/article.yaml
        path = home / "corpus" / article / "article.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")

    def put_record(home: Path, section: str, rec) -> None:
        article = section.split("/", 1)[0]
        buffers.setdefault((str(home), article), {})[section] = rec
        _materialize(home, article)

    return put_record


@pytest.fixture
def write_leaf(_corpus_store):
    """在 store 建一個末節記錄（concept 必給，其餘可選）。★store-only：真相進 `corpus/<article>.yaml`。
    回傳該節名目資料夾路徑（相容既有測試；store 世界該夾不含實體檔）。

    附掛兩個 helper（省去個測改 signature）：
    - `write_leaf.group(home, section, title=…, order=…, numbering=…)`＝建 group 記錄（取代舊
      的直接寫 `group.yaml` 檔）。
    - `write_leaf.edit(home, section, concept=…, brief=…, decisions=…, material=…, …)`＝就地改
      既有 store 記錄（取代舊的直接改 `corpus/.../concept.yaml` 檔）。
    """
    from dspx.engine import store as _store
    from dspx.engine.layout import Layout
    from dspx.engine.schema import load_schema

    schema = load_schema()

    def _write(home: Path, section: str, *, concept: dict,
               decisions: list[dict] | None = None,
               history: list[dict] | None = None,
               material: str | None = None) -> Path:
        # 補齊 schema 必填欄預設，讓最小 fixture 也通過 check 的欄位驗證
        full = {"status": "draft", "concept": section, "brief": {}, **concept}
        rec = _store.SectionRecord(
            path=section, kind="leaf", concept=full,
            decisions=list(decisions) if decisions is not None else [],
            history=list(history) if history is not None else [],
            material=material)
        _corpus_store(home, section, rec)
        leaf = home / "corpus"
        for part in section.split("/"):
            leaf = leaf / part
        return leaf

    def _group(home: Path, section: str, *, title: str | None = None,
               order: float | None = None, numbering: str | None = None) -> None:
        meta = {k: v for k, v in (("title", title), ("order", order),
                                  ("numbering", numbering)) if v is not None}
        rec = _store.SectionRecord(path=section, kind="group", group=meta)
        _corpus_store(home, section, rec)

    def _edit(home: Path, section: str, *, concept: dict | None = None,
              brief: dict | None = None, concept_del: list[str] | None = None,
              decisions: list[dict] | None = None, history: list[dict] | None = None,
              material: str | None = None) -> None:
        layout = Layout(home)
        article = section.split("/", 1)[0]
        art = _store.load_article(_store.store_path(layout, article), verify=False)
        rec = art.record_by_path(section)
        if rec is None:
            raise AssertionError(f"write_leaf.edit: no store record for {section}")
        if rec.concept is None:
            rec.concept = {}
        if concept:
            rec.concept.update(concept)
        if brief is not None:
            cur = rec.concept.get("brief")
            cur = dict(cur) if isinstance(cur, dict) else {}
            cur.update(brief)
            rec.concept["brief"] = cur
        for k in (concept_del or []):
            rec.concept.pop(k, None)
        if decisions is not None:
            rec.decisions = list(decisions)
        if history is not None:
            rec.history = list(history)
        if material is not None:
            rec.material = material
        art.revision += 1
        _store.save_article(layout, art, schema)

    def _edit_replace(home: Path, section: str, old: str, new: str, *,
                      category: str = "concept") -> None:
        """忠實模擬舊測的 `cpt.write_text(cpt.read_text().replace(old,new))`：把 store 記錄的該分類
        序列化成 yaml 文字→字串替換→parse 回寫。concept 走 mapping、decisions 走 {entries:[...]}。"""
        layout = Layout(home)
        article = section.split("/", 1)[0]
        art = _store.load_article(_store.store_path(layout, article), verify=False)
        rec = art.record_by_path(section)
        if rec is None:
            raise AssertionError(f"write_leaf.edit_replace: no store record for {section}")
        import yaml as _yaml
        if category == "concept":
            txt = _yaml.safe_dump(rec.concept, allow_unicode=True, sort_keys=False)
            rec.concept = _yaml.safe_load(txt.replace(old, new))
        elif category == "decisions":
            txt = _yaml.safe_dump({"entries": rec.decisions}, allow_unicode=True, sort_keys=False)
            rec.decisions = (_yaml.safe_load(txt.replace(old, new)) or {}).get("entries") or []
        elif category == "material":
            rec.material = (rec.material or "").replace(old, new)
        art.revision += 1
        _store.save_article(layout, art, schema)

    def _edit_decision(home: Path, section: str, index: int, **fields) -> None:
        """設某節 decisions[index] 的欄位（模擬舊測 `data["entries"][idx][k]=v` 後寫回）。"""
        layout = Layout(home)
        article = section.split("/", 1)[0]
        art = _store.load_article(_store.store_path(layout, article), verify=False)
        rec = art.record_by_path(section)
        rec.decisions[index].update(fields)
        art.revision += 1
        _store.save_article(layout, art, schema)

    _write.group = _group               # type: ignore[attr-defined]
    _write.edit = _edit                  # type: ignore[attr-defined]
    _write.edit_replace = _edit_replace  # type: ignore[attr-defined]
    _write.edit_decision = _edit_decision  # type: ignore[attr-defined]
    return _write
