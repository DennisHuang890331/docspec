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

from dspx.engine.layout import Layout
from dspx.engine.schema import Schema


class ModelError(Exception):
    """末節檔載入/解析失敗。"""


# 圖片資產：放在末節的 corpus 目錄下 `assets/`（無 concept.yaml，故 leaf_dirs 掃不到、引擎不當它末節）。
# 交付散文以 markdown `![caption](assets/<file>)` 引用；backend-neutral（Typst image() / LaTeX includegraphics 皆吃）。
ASSET_DIR_NAME = "assets"
IMAGE_EXTS = (".svg", ".png", ".jpg", ".jpeg", ".gif", ".pdf")


def docs_asset_files(layout, article: str) -> list:
    """交付側可嵌入圖檔（`docs/assets/` 下，依檔名排序）。Model A：圖（drawio＋PNG）住交付側
    docs/、非 corpus。draft 的 aperture 投這些、check ⑨／export 對它解析 `![](assets/<name>)`。"""
    adir = layout.docs_assets_dir(article)
    if not adir.is_dir():
        return []
    return sorted((p for p in adir.iterdir()
                   if p.is_file() and p.suffix.lower() in IMAGE_EXTS), key=lambda p: p.name)


def docs_drawio_files(layout, article: str) -> list:
    """交付側 `.drawio` 源檔（`docs/assets/` 下，依檔名排序）。drawio 源亦為交付物。"""
    adir = layout.docs_assets_dir(article)
    if not adir.is_dir():
        return []
    return sorted((p for p in adir.iterdir()
                   if p.is_file() and p.suffix.lower() == ".drawio"), key=lambda p: p.name)


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


def _normalize_newlines(data: bytes) -> bytes:
    """位元級指紋的換行正規化（fingerprint v2 D1）：hash 前 `\\r\\n`→`\\n`。

    換行符是 git autocrlf／編輯器／OS 的產物、非內容——同一份源料在 CRLF worktree 與 LF
    worktree 必須算出相同指紋（帳本入版控後跨 worktree 檢出不得假 stale）。孤 `\\r`（老 Mac
    格式）刻意不處理：git/編輯器不會產生，過度正規化反而稀釋「內容真的變了」的偵測面。
    以 parsed 結構計算的軸（anc/deps/norm/gloss/purpose）與 universal-newlines 的 prose 天然免疫。
    """
    return data.replace(b"\r\n", b"\n")


# 決策 active 狀態（draft 只投 active 條目；norm 軸只 hash active normative）。
# aperture 與 model 共用單一來源——「投給 agent 的活決策」與「入帳的活決策」定義不可能漂移。
ACTIVE_DECISION_STATUSES = ("proposed", "accepted")


def decision_index(leaves: list) -> dict:
    """全專案決策索引：決策/history id → {section, statement, kind, status}。

    供 realizes 解析（跨文件撈共享真相）與 deps 指紋使用。
    """
    index: dict = {}
    for leaf in leaves:
        for e in leaf.decisions:
            if e.get("id"):
                index[str(e["id"])] = {"section": leaf.section, "statement": e.get("statement"),
                                       "kind": "decision", "status": e.get("status"),
                                       "superseded_by": e.get("superseded-by")}
        for e in leaf.history:
            if e.get("id"):
                index[str(e["id"])] = {"section": leaf.section, "statement": e.get("statement"),
                                       "kind": "history", "status": e.get("status"),
                                       "superseded_by": e.get("superseded-by")}
    return index


_DEAD_DECISION_STATUSES = ("superseded", "deprecated", "retired")


def _is_dead_decision(rec: dict) -> bool:
    """退場決策＝已搬進 history（kind=history）或 status 屬退場集。"""
    return rec.get("kind") == "history" or rec.get("status") in _DEAD_DECISION_STATUSES


def _live_successor(start_id, dindex: dict) -> dict | None:
    """沿 `superseded_by` 鏈走，回第一個「活決策」（kind=decision 且 status 非退場）的
    {id, statement}；走到頭仍無活決策（鏈尾仍死／接替已 retire／無 superseded_by）→ None。

    一跳解析會把讀者導向另一個死決策（甚至導回已 retire 的原始真相）＝defeat FG-1，故必須
    走到終端活決策。visited 防環（supersede 真環另由 check 抓）。
    """
    seen: set = set()
    cur = start_id
    while cur and str(cur) not in seen:
        seen.add(str(cur))
        rec = dindex.get(str(cur))
        if rec is None:
            return None
        if not _is_dead_decision(rec):
            return {"id": str(cur), "statement": rec.get("statement")}
        cur = rec.get("superseded_by")
    return None


def realized_statements(leaf, dindex: dict) -> list:
    """本節 realizes 的決策（撈來源 statement＋status）；跨文件。

    紀律：realizes 應指向真相最源頭（權威方的決策）。status 一併帶回——supersede/deprecate
    只改 status 不改 statement，下游須據此轉 stale（見 deps_fingerprint）。退場時 `superseded_by`/
    `successor_statement` 帶**終端活接替**（沿鏈走、非一跳），讓 aperture 前景化活真相、不讓
    draft/factcheck 默默錨回死真相（FG-1 語義半＋Round-8 FINDING-1 的鏈式修正）。
    """
    out = []
    if leaf.concept is None:
        return out
    for rid in (leaf.concept.get("realizes") or []):
        rec = dindex.get(str(rid))
        if rec is not None:
            succ = _live_successor(rec.get("superseded_by"), dindex) if _is_dead_decision(rec) else None
            out.append({"id": str(rid), "statement": rec["statement"],
                        "from_section": rec["section"], "kind": rec["kind"],
                        "status": rec.get("status"),
                        "superseded_by": succ["id"] if succ else None,
                        "successor_statement": succ["statement"] if succ else None})
    return out


def deps_fingerprint(leaf, dindex: dict) -> str:
    """本節對「上游被 realizes 決策」的依賴指紋。

    hash statement **＋ status**：改 rationale 不動 statement 仍不觸發下游；但 supersede/deprecate
    改 status＝決策死了，下游必須轉 stale-upstream 重渲（否則 draft 繼續渲染死真相、status 卻報
    synced＝false-green，違 draft「只給 active 決策」契約）。無 realizes → 空字串。

    v2 補**終端活接替** (succ_id, succ_stmt)（第二跳入帳）：A→B 有信號（A 的 status 變）、
    B→C 第二跳時 A 的三元組一個 byte 都不動＝零信號，但 aperture 投給 draft 的活真相
    （successor_statement）已從 B 換成 C。值取自 `realized_statements` 既有解析（與投影同一
    函式輸出＝投什麼就 hash 什麼，不可能漂移；零新遍歷）。附帶收益：終端接替 C 的 statement
    文字被改寫也有信號（draft 渲染的正是它）。活決策（無接替）succ 兩欄為 None＝單跳語義不變。
    """
    items = sorted((r["id"], r["statement"], r.get("status"),
                    r.get("superseded_by"), r.get("successor_statement"))
                   for r in realized_statements(leaf, dindex))
    if not items:
        return ""
    h = hashlib.sha256()
    for rid, stmt, status, succ_id, succ_stmt in items:
        h.update(json.dumps({"id": rid, "stmt": stmt, "status": status,
                             "succ_id": succ_id, "succ_stmt": succ_stmt},
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


def ancestor_normative_fingerprint(section: str, by_section: dict,
                                   concept_by_id: dict | None = None) -> str:
    """祖先集 active `normative` 決策的指紋（`norm` 軸；不符 → `stale-norm`）。

    aperture 沿祖先集把 active normative 決策投給 draft「落筆必須遵守」——投影輸入變了
    （新增/改寫/退場一條祖先 ruling）而下游散文的既有指紋軸全不動＝上游改規矩、下游全 synced
    的盲區，本軸關閉之。祖先集＝`ancestor_leaves`（路徑父鏈 ∪ governed-by 遞移閉包，與 aperture
    投影**共用同一函式**＝投什麼就 hash 什麼）；條目篩選同 aperture（`kind == normative` 且
    status ∈ active）。hash (祖先 section, id, statement) 排序後 canonical JSON——status 從
    active 退場＝條目自集合消失→指紋變，不需把 status 值入 hash。自己節的決策已在 own 軸
    （decisions.yaml 屬 source_hash），本軸只管祖先。無祖先 normative → 穩定空字串
    （與 deps 無 realizes 同一慣例）。
    """
    if concept_by_id is None:
        concept_by_id = _concept_by_id(by_section)
    items: list = []
    for anc, _is_governed in ancestor_leaves(section, by_section, concept_by_id):
        for e in anc.decisions:
            if e.get("kind") == "normative" and str(e.get("status")) in ACTIVE_DECISION_STATUSES:
                items.append((anc.section, str(e.get("id") or ""), e.get("statement")))
    if not items:
        return ""
    items.sort(key=lambda t: (t[0], t[1]))
    h = hashlib.sha256()
    for sec, did, stmt in items:
        h.update(json.dumps({"section": sec, "id": did, "stmt": stmt},
                            ensure_ascii=False).encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()[:16]


def content_hash(path: Path) -> str | None:
    """檔案內容的 sha256（前 16 碼，換行正規化後）。不存在 → None。

    刻意只看內容、不看 mtime——工作區可能在 Google Drive / OneDrive /
    Dropbox / 本機任一，各家同步都會擾動 mtime。
    """
    if not path.is_file():
        return None
    return hashlib.sha256(_normalize_newlines(path.read_bytes())).hexdigest()[:16]


def _config_purpose(layout) -> str:
    """`config.purpose` 字串（style 面 purpose 子軸的輸入）；缺檔/缺鍵/空＝""（穩定空值）。

    直接輕量讀 yaml、不走 load_config（避免重複吐 unknown-key 警告）；壞 config 由 bootstrap
    的 load_config fail-loud 擋在所有指令之前，這裡防禦性回空字串即可。
    """
    from dspx.engine.config import CONFIG_FILE_NAME
    path = layout.planning_home / CONFIG_FILE_NAME
    if not path.is_file():
        return ""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get("purpose") or "")


def style_fingerprint(layout) -> dict:
    """專案級寫作 doctrine 指紋（style 面）＝三子軸 mapping `{guide, gloss, purpose}`。

    doctrine 載體（writing-guide／glossary／config.purpose）注入 draft/edit/factcheck/develop 的
    aperture、承載跨節一致性，卻不在任何節的 own/anc/deps/prose——沒有本面，純 doctrine 變更
    對 staleness 完全隱形。status 標籤仍統一 `stale-style`（三者路由 edit、ack 語義、嚴重度相同），
    拆子軸的收益＝噪音收斂＋診斷指名哪個載體動了：
    - `guide`＝writing-guide.md 全檔 bytes（換行正規化後；整檔皆為投影內容，全檔 hash 正確）。
    - `gloss`＝glossary 各 term 的**投影索引欄位**（GLOSSARY_INDEX_FIELDS，與 aperture 注入
      白名單同源共用），依 id 排序後 canonical JSON。definition/english 只供下鑽、不注入索引
      → 改它們不構成散文義務、**零擾動**；純排序/註解變動亦然。glossary 壞到不可解析 →
      fallback 全檔（正規化）bytes（信號保住、不因壞檔靜默；壞檔的吵鬧由 loader domain error 負責）。
    - `purpose`＝config.purpose 字串（缺/空＝穩定空值）。purpose 投給 develop/draft 當北極星、
      與 doctrine 同屬專案級寫作指導，同家族併入 style 面、不值得獨立標籤。
    各子軸回前 16 碼；帳本 `style` 欄存本 mapping（fingerprint v2 格式的一部分）。
    """
    from dspx.engine.glossary import GLOSSARY_INDEX_FIELDS, glossary_path, load_glossary

    guide_h = hashlib.sha256()
    gp = layout.writing_guide
    guide_h.update(_normalize_newlines(gp.read_bytes()) if gp.is_file() else b"")

    gloss_h = hashlib.sha256()
    try:
        terms = load_glossary(layout)
        index = sorted(
            ({k: t.get(k) for k in GLOSSARY_INDEX_FIELDS if k in t} for t in terms),
            key=lambda t: str(t.get("id")))
        gloss_h.update(json.dumps(index, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    except ModelError:
        glp = glossary_path(layout)
        gloss_h.update(_normalize_newlines(glp.read_bytes()) if glp.is_file() else b"")

    purpose_h = hashlib.sha256(_config_purpose(layout).encode("utf-8"))

    return {"guide": guide_h.hexdigest()[:16],
            "gloss": gloss_h.hexdigest()[:16],
            "purpose": purpose_h.hexdigest()[:16]}


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
    # material 全文（backend-neutral 窄腰）：散檔 backend 由 material.md 讀入、store backend 由記錄餵。
    # own 軸 v5 與 aperture/lint 一律讀這裡，不再各自開檔——「換 parse 來源、指紋不變」的關鍵。
    material: str | None = None

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
        # 圖資產不再計入 source_hash：圖（drawio＋PNG）已移到交付側 docs/assets/（Model A），
        # corpus 源 hash 不得反向依賴交付物。節的過期由 concept/decisions/material 驅動如常，
        # 圖隨 draft 流程刷新（見 figure-embedding spec）。
        return files

    def source_hash(self) -> str:
        """投影輸入的彙總內容指紋（staleness／own 軸；fingerprint v5）。

        **v5＝hash 解析後結構、非檔案位元——與 backend 無關**：同內容的散檔 leaf 與 store leaf
        算出同一 own 值（這是「換 parse 來源、指紋不變」的地基）。三分類各以固定標籤取代檔名字串
        （檔名拓撲不再入 hash）：
        - concept：**解析後結構、去掉 `order` 鍵**的 canonical JSON（order＝位置元資料，章號由 render
          從 order＋樹位置推導、散文不重寫；改 order/對調兄弟不誤標 stale-own）。title 保留（渲進標題＝內容）。
        - decisions：`decisions` entries 的 canonical JSON（v3 的整檔位元 → 結構化；YAML 註解/鍵序/
          空殼容器不再擾動＝與 v3「order 去 hash」同向的順帶改進）。空＝不貢獻。
        - material：`material` 全文（換行正規化、CRLF 免疫）。缺＝不貢獻。
        anc/deps/norm/style/prose 五軸零改（本就 hash 解析後結構，只 own 軸的 decisions/material
        位元半邊搬到結構）。全 corpus own 值一次性改變，帳本版本閘（v5）＋`--rebaseline` 遷移吸收。"""
        h = hashlib.sha256()
        concept = self.concept if isinstance(self.concept, dict) else {}
        content = {k: v for k, v in concept.items() if k != "order"}
        h.update(b"concept\0")
        h.update(json.dumps(content, sort_keys=True, ensure_ascii=False).encode("utf-8"))
        h.update(b"\0")
        if self.decisions:
            h.update(b"decisions\0")
            h.update(json.dumps(self.decisions, sort_keys=True, ensure_ascii=False).encode("utf-8"))
            h.update(b"\0")
        if self.material is not None:
            h.update(b"material\0")
            h.update(_normalize_newlines(self.material.encode("utf-8")))
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


def leaf_from_dir(section: str, leaf_dir: Path) -> Leaf:
    """從一個具體資料夾（正式或 staging）讀出 Leaf——section 由呼叫端明確給
    （staging 路徑無法 relative_to 正式 corpus）。散檔 backend 的單一讀取源，material 一併讀入
    （own 軸 v5 與 aperture/lint 由 leaf.material 供給、backend-neutral）。"""
    concept_raw = _load_yaml(leaf_dir / "concept.yaml")
    if concept_raw is not None and not isinstance(concept_raw, dict):
        raise ModelError(f"{leaf_dir / 'concept.yaml'} top level must be a mapping")
    decisions_path = leaf_dir / "decisions.yaml"
    history_path = leaf_dir / "history.yaml"
    material_path = leaf_dir / "material.md"
    return Leaf(
        section=section,
        dir=leaf_dir,
        concept=concept_raw,
        decisions=_entries(_load_yaml(decisions_path), decisions_path),
        history=_entries(_load_yaml(history_path), history_path),
        has_material=material_path.is_file(),
        has_develop=(leaf_dir / "develop.md").is_file(),
        has_history=history_path.is_file(),
        # read_bytes().decode（非 read_text）＝**不做 universal-newline 翻譯**：孤 `\r` 保留為內容
        # 差異（own 軸 v5 只把 `\r\n`→`\n` 正規化，與 v3 一致；read_text 會把孤 `\r` 也翻成 `\n`）。
        material=(material_path.read_bytes().decode("utf-8") if material_path.is_file() else None),
    )


def load_leaf(layout: Layout, leaf_dir: Path) -> Leaf:
    return leaf_from_dir(layout.section_id(leaf_dir), leaf_dir)


def load_project(layout: Layout, schema: Schema | None = None) -> list[Leaf]:
    """載入 corpus/ 下所有末節，依 section 路徑排序。

    per-article backend 自動偵測（article-store-backend 階段 2）：某篇有 `corpus/<article>.yaml`
    store 檔＝走 StoreBackend（記錄→Leaf）；否則散檔 leaf 夾樹＝TreeBackend；同篇兩者並存 fail-loud。
    上層無感——兩路都吐同構的 Leaf 清單。"""
    from dspx.engine import store as _store

    leaves: list[Leaf] = []
    tree_dirs = layout.leaf_dirs()
    store_arts = _store.store_articles(layout)
    if not store_arts:
        # 常態快路徑：全散檔（現行行為逐 byte 不變）。
        return [load_leaf(layout, d) for d in tree_dirs]

    store_set = set(store_arts)
    for d in tree_dirs:
        art = layout.article_of(layout.section_id(d))
        if art in store_set:
            # 同篇既有 store 檔又有散檔葉 → fail-loud（backend_of 給指路訊息）。
            _store.backend_of(layout, art)
        leaves.append(load_leaf(layout, d))
    for art in store_arts:
        leaves.extend(_store.load_store_leaves(layout, art))
    leaves.sort(key=lambda lf: lf.section)
    return leaves
