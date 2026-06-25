"""section 模型層：掃 corpus 樹、載入每個末節的檔，攤平成記憶體模型。

引擎其餘部分（check / status / instructions / publish）都吃這層的輸出。
這裡只「忠實載入 + 容錯」，不做任何語義判斷。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from dspx.layout import Layout
from dspx.schema import Schema


class ModelError(Exception):
    """末節檔載入/解析失敗。"""


# 圖片資產：放在末節的 corpus 目錄下 `assets/`（無 concept.yaml，故 leaf_dirs 掃不到、引擎不當它末節）。
# 交付散文以 markdown `![caption](assets/<file>)` 引用；backend-neutral（Typst image() / LaTeX includegraphics 皆吃）。
ASSET_DIR_NAME = "assets"
IMAGE_EXTS = (".svg", ".png", ".jpg", ".jpeg", ".gif", ".pdf")


class _DuplicateKeyError(yaml.YAMLError):
    """同一 mapping 內出現重複 key（PyYAML 預設會靜默只留最後一個、吞掉前面）。"""


class _DupCheckLoader(yaml.SafeLoader):
    """SafeLoader 子類：偵測同層重複 mapping key 並 fail-loud。

    PyYAML 預設對 `{a: 1, a: 2}` 靜默只留 `a: 2`、丟掉前者——讓重複 `statement:`/`id:`
    這類決策 key 默默汙染記錄而 check 仍綠（F3）。這裡 override mapping 建構，遇重複 key
    raise `_DuplicateKeyError`（帶 key 名與行號）。合法 merge key `<<` 由 PyYAML 在
    flatten_mapping 階段先消化、不會走到這裡，故不誤判。
    """

    def construct_mapping(self, node, deep=False):  # noqa: D102 (見類別 docstring)
        self.flatten_mapping(node)
        seen: set = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                hashable = key in seen
            except TypeError:
                hashable = False   # unhashable key（罕見）→ 交給父類常規錯誤路徑
            if hashable:
                line = key_node.start_mark.line + 1
                raise _DuplicateKeyError(
                    f"duplicate mapping key {key!r} (line {line})"
                )
            try:
                seen.add(key)
            except TypeError:
                pass
        return super().construct_mapping(node, deep=deep)


def _load_yaml(path: Path) -> object:
    if not path.is_file():
        return None
    try:
        return yaml.load(path.read_text(encoding="utf-8"), Loader=_DupCheckLoader)
    except _DuplicateKeyError as exc:
        raise ModelError(f"YAML duplicate key: {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        position = ""
        mark = getattr(exc, "problem_mark", None)
        if mark is not None:
            position = f" (line {mark.line + 1})"
        raise ModelError(f"YAML parse failed: {path}{position}") from exc


def decision_index(leaves: list) -> dict:
    """全專案決策索引：決策/history id → {section, statement, kind, status}。

    供 realizes 解析（跨文件撈共享真相）與 deps 指紋使用。
    """
    index: dict = {}
    for leaf in leaves:
        for e in leaf.decisions:
            if e.get("id"):
                index[str(e["id"])] = {"section": leaf.section, "statement": e.get("statement"),
                                       "kind": "decision", "status": e.get("status")}
        for e in leaf.history:
            if e.get("id"):
                index[str(e["id"])] = {"section": leaf.section, "statement": e.get("statement"),
                                       "kind": "history", "status": e.get("status")}
    return index


def realized_statements(leaf, dindex: dict) -> list:
    """本節 realizes 的決策（撈來源 statement＋status）；跨文件。

    紀律：realizes 應指向真相最源頭（權威方的決策），故一跳即足。status 一併帶回——
    supersede/deprecate 只改 status 不改 statement，下游須據此轉 stale（見 deps_fingerprint）。
    """
    out = []
    if leaf.concept is None:
        return out
    for rid in (leaf.concept.get("realizes") or []):
        rec = dindex.get(str(rid))
        if rec is not None:
            out.append({"id": str(rid), "statement": rec["statement"],
                        "from_section": rec["section"], "kind": rec["kind"],
                        "status": rec.get("status")})
    return out


def deps_fingerprint(leaf, dindex: dict) -> str:
    """本節對「上游被 realizes 決策」的依賴指紋。

    hash statement **＋ status**：改 rationale 不動 statement 仍不觸發下游；但 supersede/deprecate
    改 status＝決策死了，下游必須轉 stale-upstream 重渲（否則 draft 繼續渲染死真相、status 卻報
    synced＝false-green，違 draft「只給 active 決策」契約）。無 realizes → 空字串。
    """
    items = sorted((r["id"], r["statement"], r.get("status"))
                   for r in realized_statements(leaf, dindex))
    if not items:
        return ""
    h = hashlib.sha256()
    for rid, stmt, status in items:
        h.update(json.dumps({"id": rid, "stmt": stmt, "status": status},
                            ensure_ascii=False).encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()[:16]


def _path_parents(section: str, by_section: dict) -> list:
    """路徑父鏈（不含自己），由淺到深；只回有 leaf 的祖先。"""
    parts = section.split("/")
    out = []
    for depth in range(1, len(parts)):
        anc = by_section.get("/".join(parts[:depth]))
        if anc is not None:
            out.append(anc)
    return out


def ancestor_leaves(section: str, by_section: dict, concept_by_id: dict) -> list:
    """祖先集＝對「路徑父邊 ∪ governed-by 邊」做遞移閉包。

    回傳 [(ancestor_leaf, is_governed)]，依「先路徑父鏈、再跨樹治理」順序：路徑父鏈優先且
    淺→深，確保無 governed-by 的單樹 path-only 行為逐欄等價（單樹回歸不變式）。visited 防環去重。
    aperture（繼承投影）與 model（staleness 指紋）共用本函式＝祖先集定義單一來源、不漂移。
    """
    result: list = []
    visited: set = {section}      # 自己不算祖先（self-governed 環自保）

    def collect(leaf, is_governed: bool) -> None:
        if leaf.section in visited:
            return
        visited.add(leaf.section)
        result.append((leaf, is_governed))

    self_leaf = by_section.get(section)
    queue: list = [self_leaf] if self_leaf is not None else []
    for anc in _path_parents(section, by_section):
        collect(anc, False)
        queue.append(anc)

    i = 0
    while i < len(queue):
        leaf = queue[i]
        i += 1
        if not leaf.concept:
            continue
        for target_id in (leaf.concept.get("governed-by") or []):
            gov = concept_by_id.get(str(target_id))
            if gov is None or gov.section in visited:
                continue
            collect(gov, True)
            queue.append(gov)
            for anc in _path_parents(gov.section, by_section):
                if anc.section not in visited:
                    collect(anc, True)
                    queue.append(anc)
    return result


def _concept_by_id(by_section: dict) -> dict:
    return {lf.concept["id"]: lf for lf in by_section.values()
            if lf.concept and lf.concept.get("id")}


def ancestor_brief_fingerprint(section: str, by_section: dict,
                               concept_by_id: dict | None = None) -> str:
    """祖先節（不含自己）的 brief/concept 指紋。

    祖先集＝路徑父鏈 ∪ governed-by 鏈（與 aperture 同一定義）。自己的檔沒變、但某祖先（含跨樹
    治理父）的 brief/concept 變了 → 子節 fingerprint 跟著變 → status 標 stale（交給 edit 對齊）。
    父 brief 一改，所有子孫（含被治理的跨樹子）的 fingerprint 都變＝天然傳播。
    無 governed-by 的單樹節：祖先集＝純路徑父鏈、雜湊內容與順序皆與擴展前等價（回歸不變式）。
    """
    if concept_by_id is None:
        concept_by_id = _concept_by_id(by_section)
    h = hashlib.sha256()
    for anc, _is_governed in ancestor_leaves(section, by_section, concept_by_id):
        if anc.concept is None:
            continue
        inherited = {
            "concept": anc.concept.get("concept"),
            "brief": anc.concept.get("brief"),
        }
        h.update(json.dumps(inherited, sort_keys=True, ensure_ascii=False).encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()[:16]


def content_hash(path: Path) -> str | None:
    """檔案內容的 sha256（前 16 碼）。不存在 → None。

    刻意只看內容、不看 mtime——工作區可能在 Google Drive / OneDrive /
    Dropbox / 本機任一，各家同步都會擾動 mtime。
    """
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


@dataclass
class Leaf:
    """一個末節：一組同目錄檔。"""

    section: str                       # 相對 corpus/ 的路徑（POSIX）
    dir: Path
    concept: dict | None               # concept.yaml 內容
    decisions: list[dict] = field(default_factory=list)   # decisions.yaml entries
    history: list[dict] = field(default_factory=list)      # history.yaml entries
    has_material: bool = False
    has_develop: bool = False
    has_history: bool = False

    @property
    def article(self) -> str:
        return self.section.split("/", 1)[0]

    @property
    def concept_id(self) -> str | None:
        return None if self.concept is None else self.concept.get("id")

    @property
    def title(self) -> str:
        if self.concept and self.concept.get("title"):
            return str(self.concept["title"])
        return self.section.rsplit("/", 1)[-1]

    @property
    def order(self) -> float:
        if self.concept and isinstance(self.concept.get("order"), (int, float)):
            return float(self.concept["order"])
        return 0.0

    def asset_files(self) -> list[Path]:
        """本節圖片資產（`assets/` 下的圖檔，依檔名排序）。

        draft 的 aperture 投這些（知道可放哪些圖）；亦計入 source_hash（改圖→該節 stale）。
        """
        adir = self.dir / ASSET_DIR_NAME
        if not adir.is_dir():
            return []
        return sorted(
            (p for p in adir.iterdir()
             if p.is_file() and p.suffix.lower() in IMAGE_EXTS),
            key=lambda p: p.name,
        )

    def source_files(self) -> list[Path]:
        """投影輸入（staleness 看這些）：concept + decisions + material + 圖片資產。"""
        files = [self.dir / "concept.yaml", self.dir / "decisions.yaml"]
        if self.has_material:
            files.append(self.dir / "material.md")
        files = [f for f in files if f.is_file()]
        files.extend(self.asset_files())   # 圖片改動也算源變動 → 該節 stale
        return files

    def source_hash(self) -> str:
        """投影輸入的彙總內容指紋（staleness 用）。"""
        h = hashlib.sha256()
        for f in self.source_files():
            h.update(f.relative_to(self.dir).as_posix().encode("utf-8"))
            h.update(b"\0")
            h.update(f.read_bytes())
            h.update(b"\0")
        return h.hexdigest()[:16]


def keyed_list(raw: object, path: Path, key: str, *, error: type = ModelError) -> list[dict]:
    """從 `{<key>: [...]}` 結構取該 list；對「誤名頂層 key」**fail-loud**（不靜默當空）。

    這是 decisions/history（key=entries）、audit（findings）、roadmap（entries）、glossary（terms）
    四個 loader 共用的契約：一個**有內容**的頂層 mapping 卻缺正確 key（例如 audit.yaml 誤寫成
    `entries:` 而非 `findings:`），不可靜默解析成 0 條——那會讓 `check`/`ready`/publish 對結構壞掉的
    檔 false-green（與已修的 `_entries` 同類）。真正空（`raw=None`/空檔/`{<key>: []}`）仍合法。
    - raw is None / 空 dict → []（合法空）
    - 非 mapping → raise（頂層型別錯）
    - 有內容但缺 key → raise（附「did you mean '<key>:'?」hint）
    - key 在但非 list → raise
    回過濾掉非-dict 項的 list。"""
    if raw is None:
        return []
    if not isinstance(raw, dict):
        raise error(f"{path} top level must be a mapping (with '{key}:')")
    if key not in raw and raw:
        wrong = ", ".join(sorted(repr(k) for k in raw))
        raise error(
            f"{path} top-level mapping has key(s) {{{wrong}}} but no '{key}:' list "
            f"— did you mean '{key}:'?")
    items = raw.get(key) or []
    if not isinstance(items, list):
        raise error(f"{path} '{key}' must be a list")
    return [it for it in items if isinstance(it, dict)]


def _entries(raw: object, path: Path) -> list[dict]:
    """取 {entries: [...]} 結構的 entries（decisions/history）；誤名頂層 key fail-loud。"""
    out = keyed_list(raw, path, "entries")
    # entries 項若非 dict，keyed_list 已過濾；這裡維持原本「非 dict 即 raise」的嚴格度
    raw_items = raw.get("entries") if isinstance(raw, dict) else None
    if isinstance(raw_items, list):
        for e in raw_items:
            if not isinstance(e, dict):
                raise ModelError(f"{path} entries item must be a mapping: {e!r}")
    return out


def load_leaf(layout: Layout, leaf_dir: Path) -> Leaf:
    section = layout.section_id(leaf_dir)
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


def load_project(layout: Layout, schema: Schema | None = None) -> list[Leaf]:
    """載入 corpus/ 下所有末節，依 section 路徑排序。"""
    return [load_leaf(layout, d) for d in layout.leaf_dirs()]
