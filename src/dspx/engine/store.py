"""storage access layer（DAL）：corpus 真相的唯一讀寫窄腰。

階段 2（article-store-backend）：把散布式 corpus（一節一夾多檔）收成「一篇一檔」的
`corpus/<article>.yaml` 引擎獨占 store，並與現行散檔（TreeBackend）**並存、per-article
自動偵測**。上層（load_project / aperture / lint / status / render）只講 `Leaf`（記憶體模型），
不碰儲存拓撲——這是「換 backend 的 parse 來源，指紋除 own 軸外逐 bit 不變」的結構性原因
（設計 §0.4：讀取端 80% 已走 load_project→Leaf 窄腰）。

核心不變式（測試釘死）：
- **canonical serializer 冪等**：`load→dump→load` 不動點、`dump(dump(x)) == dump(x)`。
  這是「landing 換一節、旁節 byte 不變」的地基。
- **integrity 封條**：內容 payload（format/article/revision/sections 的 **schema 無關** json
  canonical）的 sha256 寫進 `integrity:`；loader 驗、不符 fail-loud 指路 `docspec store fsck`。
  刻意與寫入 schema 的鍵序解耦（換 schema 不假報 integrity 不符）。
- **多行字串一律 literal block**（自訂 representer）：PyYAML 預設把含 `\n` 的字串引號化＋
  轉義＝git diff 不可讀，必須覆寫。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from dspx.engine.layout import Layout
from dspx.engine.model import Leaf, ModelError, _normalize_newlines

# store 檔格式版本（頭 `format:`）；與 ledger 指紋版本無關。
STORE_FORMAT_VERSION = 1

STORE_HEADER = ("# docspec article store — engine-owned single-file corpus for this article.\n"
                "# Never edit by hand: an integrity seal guards the body; the next docspec command\n"
                "# will fail loud and point you at `docspec store fsck`. Use get/put.\n")

# 記錄頂層鍵的 canonical 序（group 節點另有自己的鍵，見 _record_key_order）。
_LEAF_RECORD_ORDER = ("path", "kind", "concept", "decisions", "history", "material")
_GROUP_RECORD_ORDER = ("path", "kind", "title", "order", "numbering")

# 分類標籤（own 軸 v5 用固定標籤取代檔名字串）。
CAT_CONCEPT = "concept"
CAT_DECISIONS = "decisions"
CAT_MATERIAL = "material"


class StoreError(ModelError):
    """store 檔載入/序列化/封條驗證失敗。ModelError 子類＝既有 fail-loud 路徑一體。"""


# ── canonical serializer ──────────────────────────────────────────────

class _CanonicalDumper(yaml.SafeDumper):
    """canonical YAML dumper：多行字串一律 literal block（`|`），其餘走 SafeDumper。"""


def _str_representer(dumper: yaml.SafeDumper, data: str):
    # 含換行的字串 → literal block scalar（可讀、git diff 友善）。PyYAML 對「含行尾空白」等
    # 無法用 block 忠實表示的字串會自行退回引號式（忠實優先於樣式）——冪等測試會抓到不忠實。
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_CanonicalDumper.add_representer(str, _str_representer)


def _yaml_dump(obj: object) -> str:
    """canonical dump：block style、unicode 直出、不折行、鍵序照給定結構（不再字典序）。"""
    return yaml.dump(
        obj,
        Dumper=_CanonicalDumper,
        allow_unicode=True,
        width=10000,
        sort_keys=False,
        default_flow_style=False,
    )


def _ordered_mapping(d: dict, key_order: tuple[str, ...] | list[str]) -> dict:
    """依 key_order 重排一個 mapping：宣告序在前，未宣告的剩鍵以字典序在後（決定性）。

    None 值的鍵一律剔除（缺席＝合法空，沿 contract-slimming；也保證 dump 不冒 `key: null`）。
    """
    out: dict = {}
    for k in key_order:
        if k in d and d[k] is not None:
            out[k] = d[k]
    for k in sorted(d):
        if k not in out and d[k] is not None:
            out[k] = d[k]
    return out


def _canonical_concept(concept: dict, schema) -> dict:
    """concept mapping → 依 concept fieldmap 宣告序排鍵；brief 子鍵亦排。"""
    if not isinstance(concept, dict):
        return {}
    order = _fieldmap_order(schema, "concept")
    out = _ordered_mapping(concept, order)
    brief = out.get("brief")
    if isinstance(brief, dict):
        out["brief"] = _ordered_mapping(brief, _brief_field_order(schema))
    return out


def _canonical_entry(entry: dict, schema) -> dict:
    """decisions/history entry → 依 decisions fieldmap 宣告序排鍵。"""
    if not isinstance(entry, dict):
        return {}
    return _ordered_mapping(entry, _fieldmap_order(schema, "decisions"))


def _fieldmap_order(schema, artifact_id: str) -> list[str]:
    """某 artifact 的 fieldmap 宣告序（dict 插入序＝YAML 宣告序）；無 schema → []（退字典序）。"""
    if schema is None:
        return []
    art = schema.by_id(artifact_id)
    fm = getattr(art, "schema", None) if art is not None else None
    return list(fm.keys()) if isinstance(fm, dict) else []


def _brief_field_order(schema) -> list[str]:
    if schema is None:
        return []
    art = schema.by_id("concept")
    fm = getattr(art, "schema", None) if art is not None else None
    if isinstance(fm, dict) and isinstance(fm.get("brief"), dict):
        fields = fm["brief"].get("fields")
        if isinstance(fields, dict):
            return list(fields.keys())
    return []


# ── 記錄 / article 模型 ───────────────────────────────────────────────

@dataclass
class SectionRecord:
    """store 內一節記錄：leaf（concept/decisions/history/material）或 group（title/order/numbering）。"""

    path: str
    kind: str                                   # "leaf" | "group"
    concept: dict | None = None
    decisions: list[dict] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)
    material: str | None = None
    group: dict | None = None                   # kind==group 的 {title, order, numbering}

    def to_yaml_obj(self, schema) -> dict:
        """canonical 序列化用的 plain dict（鍵序決定性、None/空剔除）。"""
        if self.kind == "tombstone":
            # 暫存 partial store 的退場記號（landing 時從正式 store 移除該 path）。
            return {"path": self.path, "kind": "tombstone"}
        if self.kind == "group":
            body: dict = {"path": self.path, "kind": "group"}
            meta = self.group or {}
            for k in ("title", "order", "numbering"):
                if meta.get(k) is not None:
                    body[k] = meta[k]
            return body
        body = {"path": self.path, "kind": "leaf"}
        if self.concept is not None:
            body["concept"] = _canonical_concept(self.concept, schema)
        if self.decisions:
            body["decisions"] = [_canonical_entry(e, schema) for e in self.decisions]
        if self.history:
            body["history"] = [_canonical_entry(e, schema) for e in self.history]
        if self.material is not None:
            body["material"] = _normalize_material(self.material)
        return body


@dataclass
class Article:
    """一篇 store 的記憶體模型：頭（format/article/revision）＋依 path 排序的扁平記錄清單。"""

    name: str
    revision: int
    records: list[SectionRecord] = field(default_factory=list)

    def sorted_records(self) -> list[SectionRecord]:
        return sorted(self.records, key=lambda r: r.path)

    def leaf_records(self) -> list[SectionRecord]:
        return [r for r in self.sorted_records() if r.kind == "leaf"]

    def group_records(self) -> list[SectionRecord]:
        return [r for r in self.sorted_records() if r.kind == "group"]

    def record_by_path(self, path: str) -> SectionRecord | None:
        for r in self.records:
            if r.path == path:
                return r
        return None


def _normalize_material(text: str) -> str:
    """material 文字入 store 前正規化：`\\r\\n`→`\\n`（CRLF 免疫，與指紋 v2 同慣例）。"""
    return _normalize_newlines(text.encode("utf-8")).decode("utf-8")


# ── serialize / hash / integrity ──────────────────────────────────────

def _core_dict(article: Article, schema) -> dict:
    """serialize 用的 canonical body（schema 鍵序、人讀友善；不含 integrity 行/註解頭）。"""
    return {
        "format": STORE_FORMAT_VERSION,
        "article": article.name,
        "revision": article.revision,
        "sections": [r.to_yaml_obj(schema) for r in article.sorted_records()],
    }


def _hash_payload(article: Article) -> dict:
    """封條所涵蓋的**schema 無關**內容 payload（只認結構與內容、不認鍵序/序列化樣式）。

    integrity 必須與寫入時用的 schema 鍵序**解耦**——否則換 schema（鍵序不同）會對同內容算出不同
    封條＝假 integrity 不符。故 hash 走 json canonical（sort_keys），不走 YAML 序列化位元。"""
    recs: list[dict] = []
    for r in article.sorted_records():
        if r.kind == "tombstone":
            recs.append({"path": r.path, "kind": "tombstone"})
        elif r.kind == "group":
            recs.append({"path": r.path, "kind": "group",
                         "group": {k: v for k, v in (r.group or {}).items() if v is not None}})
        else:
            recs.append({
                "path": r.path, "kind": "leaf",
                "concept": r.concept,
                "decisions": list(r.decisions),
                "history": list(r.history),
                "material": (_normalize_material(r.material) if r.material is not None else None),
            })
    return {"format": STORE_FORMAT_VERSION, "article": article.name,
            "revision": article.revision, "sections": recs}


def _integrity_of(article: Article) -> str:
    """封條＝schema 無關內容 payload 的 sha256（全 64 碼；不截斷）。"""
    body = json.dumps(_hash_payload(article), sort_keys=True, ensure_ascii=False)
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


# ── 分類粒度 hash（change 層 fork key `<article>#<path>#<category>` 用）───

def record_category_payload(rec: SectionRecord, category: str):
    """一節記錄某分類的 schema 無關 payload（concept dict／decisions list／material 文字）。"""
    if category == CAT_CONCEPT:
        return rec.concept
    if category == CAT_DECISIONS:
        return list(rec.decisions)
    if category == CAT_MATERIAL:
        return _normalize_material(rec.material) if rec.material is not None else None
    return None


def category_hash(rec: SectionRecord, category: str) -> str:
    """某節某分類內容的 canonical JSON sha256（缺席＝`null` 的穩定 hash）。

    change 層 fork 守門用逐節逐分類粒度（`<article>#<path>#<category>`），使第三方動同篇別節/
    別分類不觸發本節本分類的漂移警報。"""
    body = json.dumps(record_category_payload(rec, category), sort_keys=True, ensure_ascii=False)
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def dump_article(article: Article, schema) -> str:
    """一篇 Article → canonical store 檔文字（含註解頭＋integrity 封條）。

    冪等：body 從排序後記錄決定性產生、integrity 從 schema 無關 payload 決定性重算 ⇒
    `dump(dump(x)) == dump(x)`。
    """
    core = _core_dict(article, schema)
    integrity = _integrity_of(article)
    full = {
        "format": core["format"],
        "article": core["article"],
        "revision": core["revision"],
        "integrity": integrity,
        "sections": core["sections"],
    }
    return STORE_HEADER + _yaml_dump(full)


def _parse_store_text(text: str, path: Path) -> dict:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise StoreError(f"store parse failed: {path} ({exc})") from exc
    if not isinstance(data, dict):
        raise StoreError(f"store top level must be a mapping: {path}")
    return data


def article_from_dict(data: dict, path: Path, *, verify: bool = True) -> Article:
    """從已解析的 store dict 建 Article；verify=True 時驗 integrity 封條（fail-loud）。"""
    fmt = data.get("format")
    if fmt != STORE_FORMAT_VERSION:
        raise StoreError(f"{path}: unsupported store format {fmt!r} "
                         f"(engine speaks format {STORE_FORMAT_VERSION})")
    name = str(data.get("article") or "")
    if not name:
        raise StoreError(f"{path}: store is missing 'article'")
    revision = data.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool):
        raise StoreError(f"{path}: store 'revision' must be an integer")
    raw_sections = data.get("sections")
    if raw_sections is None:
        raw_sections = []
    if not isinstance(raw_sections, list):
        raise StoreError(f"{path}: store 'sections' must be a list")

    records: list[SectionRecord] = []
    for raw in raw_sections:
        if not isinstance(raw, dict):
            raise StoreError(f"{path}: each section record must be a mapping, got {raw!r}")
        spath = str(raw.get("path") or "")
        if not spath:
            raise StoreError(f"{path}: a section record is missing 'path'")
        kind = str(raw.get("kind") or "leaf")
        if kind == "tombstone":
            records.append(SectionRecord(path=spath, kind="tombstone"))
            continue
        if kind == "group":
            meta = {k: raw.get(k) for k in ("title", "order", "numbering") if raw.get(k) is not None}
            records.append(SectionRecord(path=spath, kind="group", group=meta))
            continue
        concept = raw.get("concept")
        if concept is not None and not isinstance(concept, dict):
            raise StoreError(f"{path}: section {spath!r} concept must be a mapping")
        decisions = _coerce_entries(raw.get("decisions"), path, spath, "decisions")
        history = _coerce_entries(raw.get("history"), path, spath, "history")
        material = raw.get("material")
        if material is not None and not isinstance(material, str):
            raise StoreError(f"{path}: section {spath!r} material must be a string block")
        records.append(SectionRecord(
            path=spath, kind="leaf", concept=concept,
            decisions=decisions, history=history,
            material=material))

    article = Article(name=name, revision=revision, records=records)

    if verify:
        stored = data.get("integrity")
        expect = _integrity_of(article)
        if stored != expect:
            raise StoreError(
                f"{path}: integrity seal mismatch — the store file was edited outside the engine "
                f"(expected {expect}, found {stored!r}). Run `docspec store fsck --accept` to adopt "
                "the external change, or restore the file from git/Drive history.")
    return article


def _coerce_entries(raw, path: Path, spath: str, cat: str) -> list[dict]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise StoreError(f"{path}: section {spath!r} {cat} must be a list")
    for e in raw:
        if not isinstance(e, dict):
            raise StoreError(f"{path}: section {spath!r} {cat} entry must be a mapping: {e!r}")
    return list(raw)


def load_article(path: Path, *, verify: bool = True) -> Article:
    """讀 `corpus/<article>.yaml` → Article（verify=True 驗封條）。"""
    if not path.is_file():
        raise StoreError(f"store file not found: {path}")
    data = _parse_store_text(path.read_text(encoding="utf-8"), path)
    return article_from_dict(data, path, verify=verify)


# ── per-article 自動偵測 ──────────────────────────────────────────────

def legacy_store_path(layout: Layout, article: str) -> Path:
    """前一代扁平位置 `corpus/<article>.yaml`（dossier-layout 前）。讀端 fallback 用。"""
    return layout.corpus_dir / f"{article}.yaml"


def store_path(layout: Layout, article: str) -> Path:
    """一篇的 store 檔路徑（dossier-layout）：`corpus/<article>/article.yaml`。

    fallback：新位不存在而**舊扁平位存在** → 回舊位（讀寫都留在舊位＝不隱式半遷移；
    `docspec store migrate-layout` 一次收編）。新專案/已遷專案一律新位。"""
    new = layout.article_store(article)
    if not new.is_file():
        old = legacy_store_path(layout, article)
        if old.is_file():
            return old
    return new


def article_has_store(layout: Layout, article: str) -> bool:
    return layout.article_store(article).is_file() or legacy_store_path(layout, article).is_file()


def article_has_tree(layout: Layout, article: str) -> bool:
    """該篇有散檔 leaf 夾樹（`<corpus>/<article>/` 下任一 concept.yaml，非封存）。
    dossier 案卷夾（只含定名 yaml、無 concept.yaml）不算散檔樹。"""
    art_dir = layout.section_dir(article)
    if not art_dir.is_dir():
        return False
    for cp in art_dir.rglob("concept.yaml"):
        if cp.is_file() and not layout.is_archived_path(cp.parent):
            return True
    return False


def backend_of(layout: Layout, article: str) -> str:
    """該篇用哪個 backend：'store' | 'tree' | 'none'；同篇兩者並存 → fail-loud。"""
    has_store = article_has_store(layout, article)
    has_tree = article_has_tree(layout, article)
    if has_store and has_tree:
        raise StoreError(
            f"article {article!r} has BOTH a store file (corpus/{article}.yaml) and a scattered "
            "leaf-folder tree — the engine cannot tell which is the truth. Remove one: keep the "
            f"store and delete corpus/{article}/, or `docspec store dump {article}` then delete "
            "the store file.")
    if has_store:
        return "store"
    if has_tree:
        return "tree"
    return "none"


# Drive 同步衝突副本檔名（`<stem> (N).yaml`）＋暫存（`*.tmp.drive*`）：引擎只讀固定 store 名，
# 這些副本一律隱形（否則 load_project 會把 `a (1).yaml` 當文章 `a (1)` 載入而炸）。衛生 check 另 WARN。
import re as _re
_CONFLICT_STORE_RE = _re.compile(r".* \(\d+\)$")


def store_articles(layout: Layout) -> list[str]:
    """corpus/ 下所有文章名（依名排序）：dossier 案卷夾（`corpus/<夾>/article.yaml`）∪
    前一代扁平檔（`corpus/<article>.yaml`，fallback 期）。`_` 前綴隱形；Drive 衝突副本/暫存隱形。"""
    if not layout.corpus_dir.is_dir():
        return []
    names: set[str] = set()
    for d in layout.corpus_dir.iterdir():
        if (d.is_dir() and not d.name.startswith("_")
                and not _CONFLICT_STORE_RE.match(d.name)
                and (d / "article.yaml").is_file()):
            names.add(d.name)
    for p in layout.corpus_dir.glob("*.yaml"):
        if not (p.is_file() and not p.name.startswith("_")):
            continue
        if p.name.endswith((".audit.yaml", ".roadmap.yaml")):
            continue   # 前一代 sibling 治理密封檔不是文章 store
        if _CONFLICT_STORE_RE.match(p.stem) or ".tmp.drive" in p.name.lower():
            continue   # Drive 同步垃圾：引擎隱形（衛生 check 會 WARN）
        names.add(p.stem)
    return sorted(names)


# ── store → Leaf（讀端窄腰；上層無感）─────────────────────────────────

def leaf_from_record(layout: Layout, rec: SectionRecord) -> Leaf:
    """單一 leaf 記錄 → Leaf（與散檔 leaf_from_dir 逐欄等價）。

    history/material 直接由記錄餵。
    Leaf.dir 指向散檔會在的名目路徑（不存在＝讀檔式讀取者自然回退，材料改走 leaf.material）。
    change 層 union view 逐節建 Leaf 亦走此（正式記錄與 staging overlay 記錄同構）。"""
    section = rec.path
    return Leaf(
        section=section,
        dir=layout.section_dir(section),
        concept=rec.concept,
        decisions=list(rec.decisions),
        history=list(rec.history),
        has_material=rec.material is not None,
        has_history=bool(rec.history),
        material=rec.material,
    )


def leaves_from_article(layout: Layout, article: Article) -> list[Leaf]:
    """一篇 store 的 leaf 記錄 → Leaf 清單（與散檔 load_leaf 逐欄等價）。"""
    return [leaf_from_record(layout, rec) for rec in article.leaf_records()]


def load_store_leaves(layout: Layout, article: str, *, verify: bool = True) -> list[Leaf]:
    return leaves_from_article(layout, load_article(store_path(layout, article), verify=verify))


# ── tree → Article（★遷移橋 only：散檔讀取碼一律集中在此段，`store migrate`/`store dump`/
#    `store load` 專用；正常讀寫路徑 store-only、不得走這裡）────────────────

def load_tree_leaves(layout: Layout, article: str | None = None) -> list[Leaf]:
    """散檔（一節一夾）→ Leaf 清單。**僅 migrate/dump/load 遷移橋用**——store-only 世界的
    正常讀取走 `model.load_project`（store）。article=None＝全散檔樹；否則只該篇。"""
    from dspx.engine.model import load_leaf
    out: list[Leaf] = []
    for d in layout.leaf_dirs():
        sec = layout.section_id(d)
        if article is None or layout.article_of(sec) == article:
            out.append(load_leaf(layout, d))
    out.sort(key=lambda lf: lf.section)
    return out


def tree_articles(layout: Layout) -> list[str]:
    """仍有散檔葉夾樹的文章名（依名排序）。**僅 migrate 遷移橋用**。"""
    seen: list[str] = []
    for d in layout.leaf_dirs():
        art = layout.article_of(layout.section_id(d))
        if art and art not in seen:
            seen.append(art)
    return sorted(seen)


def article_from_leaves(name: str, leaves: list[Leaf], groups: list[dict],
                        revision: int = 1) -> Article:
    """散檔 leaves（該篇）＋group 記錄 → Article。material 由 leaf.material 帶（load 端已讀入）。"""
    records: list[SectionRecord] = []
    for lf in leaves:
        records.append(SectionRecord(
            path=lf.section, kind="leaf",
            concept=lf.concept,
            decisions=list(lf.decisions),
            history=list(lf.history),
            material=lf.material))
    for g in groups:
        records.append(SectionRecord(path=g["path"], kind="group", group={
            k: g.get(k) for k in ("title", "order", "numbering") if g.get(k) is not None}))
    return Article(name=name, revision=revision, records=records)


def group_records_from_tree(layout: Layout, article: str) -> list[dict]:
    """散檔該篇的 group.yaml → group 記錄清單（path/title/order/numbering）。"""
    out: list[dict] = []
    art_dir = layout.section_dir(article)
    if not art_dir.is_dir():
        return out
    for gy in sorted(art_dir.rglob("group.yaml")):
        if layout.is_archived_path(gy.parent):
            continue
        # group.yaml 所在夾若同時是 leaf（含 concept.yaml）＝非純 group 節點，跳過（其 meta 由 concept 帶）。
        if (gy.parent / "concept.yaml").is_file():
            continue
        try:
            data = yaml.safe_load(gy.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise StoreError(f"{gy}: malformed group.yaml ({exc})") from exc
        meta = data if isinstance(data, dict) else {}
        rec = {"path": layout.section_id(gy.parent)}
        for k in ("title", "order", "numbering"):
            if meta.get(k) is not None:
                rec[k] = meta[k]
        out.append(rec)
    return out


# ── store 側 group 查詢（render/lint/forest 讀端 store-aware）────────────

def store_group_meta(layout: Layout, article_obj: Article, section: str) -> dict | None:
    """store 內某 group 節點的 meta（title/order/numbering）；非 group/不存在 → None。"""
    rec = article_obj.record_by_path(section)
    if rec is not None and rec.kind == "group":
        return dict(rec.group or {})
    return None


# render/lint/forest 的 group 讀端在熱路徑上會反覆查同一 store——依 (path, mtime, size) 快取
# 已解析 Article（group 讀不需每次重驗封條：load_project 起手已驗過）。
_ARTICLE_CACHE: dict[str, tuple] = {}


def cached_article(layout: Layout, article: str) -> Article | None:
    """該篇 store 的（快取）Article；無 store → None。group 讀端用（verify=False，主載入已驗）。"""
    p = store_path(layout, article)
    if not p.is_file():
        return None
    stat = p.stat()
    key = (stat.st_mtime_ns, stat.st_size)
    hit = _ARTICLE_CACHE.get(str(p))
    if hit is not None and hit[0] == key:
        return hit[1]
    art = load_article(p, verify=False)
    _ARTICLE_CACHE[str(p)] = (key, art)
    return art


def group_meta(layout: Layout, section: str) -> dict | None:
    """render/lint/forest 的 store-aware group 查詢：該篇是 store → 回 group meta（非 group＝{}）；
    非 store → None（呼叫端回退讀 group.yaml 檔）。"""
    article = layout.article_of(section)
    if not article_has_store(layout, article):
        return None
    art = cached_article(layout, article)
    if art is None:
        return None
    rec = art.record_by_path(section)
    return dict(rec.group or {}) if (rec is not None and rec.kind == "group") else {}


def atomic_write_store(path: Path, text: str) -> None:
    """原子寫 store 檔：tmp 同目錄 + os.replace。"""
    import os
    import tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".store-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def save_article_to(path: Path, article: Article, schema) -> None:
    """一篇 Article → canonical dump → 原子寫到指定路徑（官方 store 或 change staging 的 partial store）。"""
    atomic_write_store(path, dump_article(article, schema))


def save_article(layout: Layout, article: Article, schema) -> None:
    """一篇 Article → canonical dump → 原子寫 `corpus/<article>.yaml`（引擎獨占寫）。"""
    save_article_to(store_path(layout, article.name), article, schema)
