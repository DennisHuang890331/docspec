"""render：把末節散文確定性組裝進 docs/<article>/_latest.md。

★薄引擎鐵律：引擎不寫一個字。散文由 draft（agent）盲渲染、直接寫進 _latest.md 各節；
render 只做確定性的事——讓章節骨架（標題/順序/層級）跟 outline 對齊，保留每節已寫散文，
並記下「有散文的節」的當下源 hash（staleness 用）。

章節邊界＝隱形標記 `<!-- dspx:section <id> -->`（讀者看不到；render 靠它定位每節）。
publish 凍結時會完全剝除這些標記。
"""

from __future__ import annotations

import hashlib
import re

import yaml

from dspx.env.frontmatter import FrontmatterError, parse_frontmatter, render_frontmatter
from dspx.engine.layout import LEDGER_DIR_NAME, Layout
from dspx.engine.model import (
    Leaf,
    ancestor_brief_fingerprint,
    ancestor_normative_fingerprint,
    decision_index,
    deps_fingerprint,
    style_fingerprint,
)

# 指紋帳本的算法/格式版本（頂層 `fingerprint:` 鍵）。v2＝四項算法（換行正規化、deps 二跳、
# style 三子軸、norm 新軸）；v3＝own 軸把 `order`（位置元資料）排除於 concept.yaml 貢獻之外
# （contract-slimming：改 order/搬位不誤標 stale-own）；v4＝prose 軸把散文交叉引用錨後的 render
# 注入號碼正規化掉（prose-crossref-anchors：`<!--@id-->§6.5<!--@-->` 的 §6.5 每次 render 重算、
# 排除於 prose 指紋——重排刷新號碼不誤標 prose drift，與 v3 order-out-of-hash 同構）。無此鍵＝v1。
# v5＝own 軸改讀「解析後結構」而非檔案位元（article-store-backend 階段 2）：decisions/material 的
# 位元半邊搬到結構化 JSON/文字，own 值與 backend（散檔/store）無關；anc/deps/norm/style/prose 零改。
# 任一低於現行版本的帳本＝不可比、需一次 `--rebaseline` 遷移（見 read_ledger_version /
# ledger_needs_migration）。
LEDGER_FINGERPRINT_VERSION = 5


def read_ledger(layout: Layout, article: str) -> dict:
    """讀某文章的指紋帳本（各節 own/anc/deps/prose）。

    來源優先序：① 機器簿記 `docspec/.ledger/<article>.sections.yaml`（現行位置）；② 舊位置 sidecar
    `docs/.../.sections.yaml`（自動遷移：下次 render 會寫進 ①）；③ 更舊格式 ＝`_latest.md`
    frontmatter 的 `sections`。都沒有 → {}。"""
    import sys
    for ledger in (layout.docs_ledger(article), layout.docs_ledger_legacy(article)):
        if not ledger.is_file():
            continue
        try:
            data = yaml.safe_load(ledger.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            # 壞掉的 sidecar（如 Drive/OneDrive sync 衝突截斷）：**可見警告、非靜默**——
            # 否則 drift 偵測會默默失效（手改交付物不再被抓）。注意：render **不會**默默修復
            # （那會把待重寫的 stale 信號永久吸收成新基準）——render 遇壞帳本會隔離備份並拒跑。
            sys.stderr.write(
                f"docspec: ⚠ ledger sidecar {ledger} is malformed ({exc}); "
                "staleness/drift signals are unavailable. Restore it from git/Drive history, "
                "or run `docspec render <article> --rebaseline` to quarantine it and rebuild "
                "the baseline (this permanently absorbs any pending stale signals).\n")
            return {}
        sections = data.get("sections") if isinstance(data, dict) else None
        return dict(sections) if isinstance(sections, dict) else {}
    # 更舊格式 fallback：frontmatter 內的 sections（遷移前的舊交付物）
    latest = layout.docs_latest(article)
    if latest.is_file():
        try:
            meta, _ = parse_frontmatter(latest.read_text(encoding="utf-8"))
        except FrontmatterError as exc:
            # 人手改 `_latest.md` 把 frontmatter 改壞時，別讓 status/diff/check 噴 traceback。
            sys.stderr.write(
                f"docspec: ⚠ {latest} frontmatter is malformed ({exc}); treating as no ledger.\n")
            return {}
        sections = meta.get("sections")
        return dict(sections) if isinstance(sections, dict) else {}
    return {}


def write_ledger(layout: Layout, article: str, hashes: dict,
                 groups_fp: str | None = None) -> None:
    """把指紋帳本寫進隱藏 sidecar（機器簿記，與人讀的 `_latest.md` 分離）。

    `groups_fp`＝該文章 group.yaml 骨架面指紋（title/order；D4）——status 比對它偵測
    「改了 group.yaml 但沒人提醒重新 render」的盲區。
    頂層一律寫 `fingerprint: <版本>`（v2 起）：算法一改、舊值與新算法現值不可比，版本鍵讓
    讀端確定性判別、不靠啟發式（見 read_ledger_version）。"""
    ledger = layout.docs_ledger(article)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {"article": article, "fingerprint": LEDGER_FINGERPRINT_VERSION}
    if groups_fp is not None:
        data["groups"] = groups_fp
    data["sections"] = hashes
    ledger.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8", newline="\n")


def read_ledger_version(layout: Layout, article: str) -> int | None:
    """指紋帳本的算法/格式版本。

    None＝無帳本（全新文章，render 直接以現行版本入帳）；1＝v1（sidecar 無頂層 `fingerprint`
    鍵，或更舊的 frontmatter-sections 格式＝本 change 前的算法）；≥2＝頂層版本鍵的值。
    壞檔（不可解析）→ None——壞帳本由 render 的隔離閘／read_ledger 的警告另行負責，這裡不重複。
    v1 的舊值與 v2 算法現值**不可比**：status 顯 needs-migration、render 拒跑，
    `docspec render <article> --rebaseline` 一次遷移。"""
    for ledger in (layout.docs_ledger(article), layout.docs_ledger_legacy(article)):
        if not ledger.is_file():
            continue
        try:
            data = yaml.safe_load(ledger.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            return None
        if not isinstance(data, dict):
            return 1
        fp = data.get("fingerprint")
        return fp if isinstance(fp, int) and not isinstance(fp, bool) else 1
    latest = layout.docs_latest(article)
    if latest.is_file():
        try:
            meta, _ = parse_frontmatter(latest.read_text(encoding="utf-8"))
        except FrontmatterError:
            return None
        if isinstance(meta.get("sections"), dict):
            return 1        # 更舊格式（frontmatter 內嵌 sections）＝v1
    return None


def ledger_needs_migration(layout: Layout, article: str) -> bool:
    """帳本存在且版本低於現行算法版本＝需一次顯式 `--rebaseline` 遷移。"""
    version = read_ledger_version(layout, article)
    return version is not None and version < LEDGER_FINGERPRINT_VERSION


def read_ledger_groups(layout: Layout, article: str) -> str | None:
    """讀帳本記的 group.yaml 骨架面指紋；缺檔/壞檔/舊帳本（無 groups 欄）→ None（無信號）。"""
    for ledger in (layout.docs_ledger(article), layout.docs_ledger_legacy(article)):
        if not ledger.is_file():
            continue
        try:
            data = yaml.safe_load(ledger.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            return None   # 壞檔警告由 read_ledger 負責，這裡不重複
        groups = data.get("groups") if isinstance(data, dict) else None
        return str(groups) if isinstance(groups, str) else None
    return None


def verdicts_path(layout: Layout, article: str):
    """verdicts journal 的家：`docspec/.ledger/<article>.verdicts.yaml`（機器簿記、不進 docs/）。"""
    return layout.planning_home / LEDGER_DIR_NAME / f"{article}.verdicts.yaml"


def verdict_entry(verb: str, section: str, reason: str,
                  own_before: str | None, own_after: str | None,
                  prose: str | None) -> dict:
    """一筆 verdicts journal 記錄——四動詞（ack/ack-own/stale/redraft）schema 均一、可按節 grep。

    `own_before`/`own_after`＝裁決前後帳本的 `own` 值（stale/redraft 不動指紋＝兩者相同）；
    `prose`＝該節當下散文指紋。`when`＝ISO 8601（含時區）。"""
    import datetime
    return {
        "when": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "verb": verb,
        "section": section,
        "reason": reason or "",
        "own_before": own_before,
        "own_after": own_after,
        "prose": prose,
    }


def append_verdicts(layout: Layout, article: str, entries: list[dict]) -> None:
    """append-only verdicts journal：對 `docspec/.ledger/<article>.verdicts.yaml` 追加記錄。

    每筆＝一個 YAML list item（整檔恆為合法 YAML list）。**只 append**——任何指令不得重寫/
    重排/重生此檔（sections 帳本每輪 render 整檔重生，正因如此 reason 住這裡不住那裡）；
    引擎也永不讀它當輸入（純留痕簿記、供人/agent 考古）。空 entries＝不建檔、不動檔。"""
    if not entries:
        return
    path = verdicts_path(layout, article)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        for e in entries:
            fh.write(yaml.safe_dump([e], allow_unicode=True, sort_keys=False))


def groups_fingerprint(layout: Layout, article: str) -> str:
    """文章骨架的 group.yaml 比對面指紋：全部（非封存）group.yaml 的路徑＋title＋order。

    title/order 變動＝「交付物骨架變了、需重新 render」（D4，與 concept 的 title/order 同性質）；
    只取這兩欄、不 hash 整檔——group.yaml 加註解不算骨架變動。store 篇由記錄枚舉 group（與散檔同構）。"""
    from dspx.engine import store as _store
    h = hashlib.sha256()
    if _store.article_has_store(layout, article):
        art = _store.cached_article(layout, article)
        for rec in (art.group_records() if art else []):
            meta = rec.group or {}
            h.update(f"{rec.path}\0{meta.get('title')!r}\0{meta.get('order')!r}\0".encode("utf-8"))
        return h.hexdigest()[:16]
    art_dir = layout.section_dir(article)
    if art_dir.is_dir():
        for gy in sorted(art_dir.rglob("group.yaml")):
            if layout.is_archived_path(gy.parent):
                continue
            meta = _group_meta(layout, layout.section_id(gy.parent))
            rel = gy.parent.relative_to(layout.corpus_dir).as_posix()
            h.update(f"{rel}\0{meta.get('title')!r}\0{meta.get('order')!r}\0".encode("utf-8"))
    return h.hexdigest()[:16]

# markdown 圖片引用 ![alt](path "optional title")：抓 path（到空白或 ) 為止）。
# alt 用 lazy `.*?`（停在後接 `(` 的那個 `]`），alt 內裸 `]`（如 `errors[]`）不再咬斷整條引用——
# 舊 `[^\]]*` 會在第一個 `]` 斷掉，讓 V14／check ⑨／export 收圖同時看不見這條引用。
# 已知邊界：alt 含字面 `](` 仍提早截斷（CommonMark 本要求跳脫，不為它建 parser）。
# 單一定義：所有消費端一律走 find_image_refs，勿另寫圖片 regex 分岔。
IMAGE_REF_RE = re.compile(r"!\[.*?\]\(\s*([^)\s]+)")

# 路徑抓到 `-->` 為止（lazy＋兩端 trim），不用 `\S+`——含空白的 section 路徑（如「附錄 A」）
# 才能寫入/讀回對稱，散文不因標記解析失敗被靜默歸前節或丟棄。lint 的歸節直接 import 這兩條
# （單一真相源，勿另寫 regex 分岔）。
MARKER_RE = re.compile(r"^<!--\s*dspx:section\s+(.+?)\s*-->\s*$")
# 分組（非末節）節點標記：與 section marker 區隔，使 parse_section_bodies 切斷前一節、
# 忽略分組標題行（分組無散文、不記指紋、不進 lint 的 section 集合）。publish 一併剝除。
GROUP_MARKER_RE = re.compile(r"^<!--\s*dspx:group\s+(.+?)\s*-->\s*$")
# 關閉式標記（作者誤以為標記像 HTML 成對、手加的 `<!-- /dspx… -->`）：publish 凍結時一併剝除
# （快照零機械痕跡契約）。刻意不進 parse_section_bodies——節內的關閉式行仍算該節散文
# （手改如常計入 prose 指紋、diff 照抓），剝除只保護凍結快照。
CLOSING_MARKER_RE = re.compile(r"^<!--\s*/\s*dspx\b[^>]*-->\s*$")


# ── 散文交叉引用錨（prose-crossref-anchors, P1b）───────────────────────────────
# 散文回引不再手寫死章號（`§9.2`／`第 6 章`）——改綁一個穩定錨，號碼由 render 每次重算注入。
# 形式（一體兩件）：`<!--@<id>-->` 綁定（隱形 html-comment，spans.py 已認得且保護）＋緊隨的
# render 擁有的可見標籤（`§6.5`／`附錄 A`／numbering:none 目標的標題名）＋closing sentinel
# `<!--@-->`（空 id 的 html-comment）。三者一體：markdown→PDF 兩個 comment 不渲染，讀者只見標籤。
#   `…詳見 <!--@sec-bc9bfc7a-->§6.5<!--@--> 的狀態轉移…`
# render 組裝時對每 body 掃此形、以目標當下 outline 號碼重寫兩 comment 之間的標籤（號碼 derive、
# 不入源）；重排即自動刷新（open question 定案＝body 帶當下號碼、指紋正規化掉）。標籤含 `§` 由
# render 決定（numbering:none 目標注標題名、不吐空 `§`）。id 綁定字串本身 byte 不變。
_ANCHOR_ID = r"[A-Za-z0-9_-]+"
# 綁定開頭（捕捉 id；空 id 的 sentinel `<!--@-->` 不命中——`+` 要求至少一字元）。
_ANCHOR_OPEN_RE = re.compile(r"<!--@(" + _ANCHOR_ID + r")-->")
# 完整引用：綁定 + 標籤（inline、非跨行）+ sentinel。標籤 lazy，render 重寫其內容。
_ANCHOR_REF_RE = re.compile(r"<!--@(" + _ANCHOR_ID + r")-->(.*?)<!--@-->")


def normalize_prose_anchors(body: str) -> str:
    """把散文交叉引用錨後的 render 注入號碼縮回裸綁定（prose 指紋正規化用，D2）。

    `<!--@id-->§6.5<!--@-->` → `<!--@id--><!--@-->`：號碼刷新（6.5→7.2＝重排）對 prose 指紋
    透明，只有綁定本身變（改錨目標＝retarget）或其餘散文變才算 prose 變動。與 v3 的
    order-out-of-hash 同構延伸。冪等（再跑不再縮）。"""
    if "<!--@" not in body:
        return body
    return _ANCHOR_REF_RE.sub(r"<!--@\1--><!--@-->", body)


def _protected_mask(body: str) -> list[bool]:
    """body 中「byte-exact 不可動」的位置遮罩（code fence／inline code／image／URL）。

    錨解析只在散文 span 動（spec：只在 prose span、code/URL/識別碼 byte-exact）——綁定所在的
    html_comment 刻意**不**遮（錨就住 comment 裡），但落在 fence/inline code/image/url 內的
    錨樣式字串一律跳過、byte 不動。"""
    from dspx.engine.spans import FENCE, IMAGE, INLINE_CODE, URL, classify_deliverable
    protected = [False] * len(body)
    byte_exact = {FENCE, INLINE_CODE, IMAGE, URL}
    for sp in classify_deliverable(body):
        if sp.kind in byte_exact:
            for p in range(sp.start, sp.end):
                protected[p] = True
    return protected


def resolve_prose_anchors(body: str, label_for) -> str:
    """render 組裝時的散文錨解析注入 pass：以 `label_for(id)` 重算兩 comment 間的可見標籤。

    `label_for(anchor_id) -> str | None`：回該錨目標當下的可見標籤（`§6.5`／`附錄 A`／標題名），
    None＝無法解析（目標不存在/退役——標籤留空，check 另報死引用 ERROR）。只在散文 span 動；
    落在 code/URL 內的錨樣式 byte 不動。確定性、冪等（未重排連跑兩次 byte 同）。"""
    if "<!--@" not in body:
        return body
    protected = _protected_mask(body)

    def repl(m: re.Match) -> str:
        if any(protected[m.start():m.end()]):
            return m.group(0)            # 落在 code/URL 內：byte-exact 不動
        label = label_for(m.group(1))
        return f"<!--@{m.group(1)}-->{label or ''}<!--@-->"

    return _ANCHOR_REF_RE.sub(repl, body)


def iter_prose_anchor_ids(body: str) -> list[tuple[str, int]]:
    """抽出 body 散文 span 內每個錨綁定的 `(id, offset)`（依出現序、去重前）。

    供 `check` 收死引用（跨文件散文引用第一次可驗）。只認散文 span 內的綁定；code/URL 內的
    錨樣式不算引用。sentinel `<!--@-->`（空 id）天然不命中。"""
    if "<!--@" not in body:
        return []
    protected = _protected_mask(body)
    out: list[tuple[str, int]] = []
    for m in _ANCHOR_OPEN_RE.finditer(body):
        if any(protected[m.start():m.end()]):
            continue
        out.append((m.group(1), m.start()))
    return out


def strip_anchor_bindings(text: str) -> str:
    """把散文交叉引用錨的隱形綁定剝掉、留下當下可見標籤（publish 凍結快照用）。

    `<!--@id-->§6.5<!--@-->` → `§6.5`：發行快照是不可變的、號碼凍結在發行當下（正是所需——
    published 版本永不重算）。零機械痕跡契約：綁定 comment 一併消失。落在 code fence 內的錨樣式
    亦一併還原（快照不留任何 `<!--@…-->`）；code 內出現此精確配對的機率可忽略。"""
    return _ANCHOR_REF_RE.sub(r"\2", text)


def prose_hash(body: str) -> str:
    """一段散文本身的指紋（diff 偵測手改交付物用）。

    v4：hash 前把散文交叉引用錨後的 render 注入號碼正規化掉（`normalize_prose_anchors`）——
    號碼刷新（重排）對 prose 指紋透明，只有綁定/其餘散文真變才算 prose 變（D2）。"""
    return hashlib.sha256(
        normalize_prose_anchors(body).strip().encode("utf-8")).hexdigest()[:16]


def find_image_refs(body: str) -> list[str]:
    """從一段散文抽出 markdown 圖片引用的路徑（`![alt](path)`），依出現序。"""
    return [m.group(1) for m in IMAGE_REF_RE.finditer(body)]


def section_marker(section: str) -> str:
    return f"<!-- dspx:section {section} -->"


def group_marker(section: str) -> str:
    return f"<!-- dspx:group {section} -->"


# 標題層級上限＝四級（中文期刊規範 GB/T 3179：編號到 1.1.1.1 為極限）。markdown 標題＝`#`×(depth+1)，
# 上限 5（經 --shift-heading-level-by=-1 後＝typst L4＝四級，模板地板）。更深：render clamp 到此（防靜默
# 吐 `#######`＝CommonMark 字面文字、破版），且由 `docspec check` 結構不變式 fail-loud 擋下（見 check._check_hierarchy）。
MAX_HEADING_LEVEL = 5


def _humanize_segment(segment: str) -> str:
    """分組節點標題 fallback：去前綴序號（`^\\d+[-_]`）、分隔符轉空白、拉丁字首字大寫、CJK 原樣。"""
    s = re.sub(r"^\d+[-_]", "", segment)
    s = s.replace("-", " ").replace("_", " ").strip()
    words = [
        (w[:1].upper() + w[1:]) if (w[:1].isascii() and w[:1].isalpha()) else w
        for w in s.split(" ")
    ]
    return " ".join(w for w in words if w)


# 壞 group.yaml 已警告過的檔（同輪 render 對同檔多次讀取只警告一次，防洗版）
_warned_group_files: set[str] = set()


def _group_meta(layout: Layout, group_section: str) -> dict:
    """讀分組節點可選 `group.yaml`（`title`／`order`）；缺檔 → {}（向後相容）。

    壞檔（非法 YAML／讀取失敗）→ {} 但 **stderr 指名警告、非靜默**——否則中文標題會
    默默降級成 humanize slug（機械 drift、人不會發現）。fallback 行為維持、不擋 render。"""
    import sys

    from dspx.engine import store as _store
    smeta = _store.group_meta(layout, group_section)   # store-aware：該篇是 store→由記錄供 meta
    if smeta is not None:
        return smeta
    gy = layout.section_dir(group_section) / "group.yaml"
    try:
        if gy.is_file():
            data = yaml.safe_load(gy.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except (OSError, yaml.YAMLError) as exc:
        key = str(gy)
        if key not in _warned_group_files:
            _warned_group_files.add(key)
            sys.stderr.write(
                f"docspec: ⚠ {gy} is malformed ({exc}); its title/order are ignored "
                "and the heading falls back to the humanized slug — fix the file.\n")
    return {}


def _group_title(layout: Layout, group_section: str, segment: str) -> str:
    """分組節點標題：優先取該節點目錄可選 `group.yaml` 的 `title`（在地化，治中文文件冒英文 slug 標題）；
    缺檔／壞檔／無 title → fallback 回路徑末段 humanize（向後相容，既有專案 render 不變）。"""
    title = _group_meta(layout, group_section).get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return _humanize_segment(segment)


def _group_order(layout: Layout, group_section: str) -> float | None:
    """分組節點可選排序鍵：`group.yaml` 的 `order`（數值）；缺/非數值 → None（維持預設 0.0）。"""
    order = _group_meta(layout, group_section).get("order")
    if isinstance(order, bool):   # bool 是 int 子類，排除
        return None
    if isinstance(order, (int, float)):
        return float(order)
    return None


# 章號政策（D7）：concept.yaml／group.yaml 的可選 `numbering` 欄，決定 render 推導的標題編號形態。
# arabic＝正常層級編號（6./6.1）；appendix＝字母序（附錄 A／A.1）；none＝不編號（如修訂歷史）。
# 沿樹向下繼承（子節無顯式值＝跟最近祖先政策；根默認 arabic）。規則住 schema、被 guide 投影。
NUMBERING_POLICIES = ("arabic", "appendix", "none")
# 頂層附錄的標題前綴（附錄 A）；其子節退回阿拉伯前綴（A.1）。export #09 的 `^附錄\s?[A-Z]`
# 去編號後處理即以此形態為輸入假設（相容測試釘死）。
APPENDIX_HEADING_PREFIX = "附錄 "


def _group_numbering(layout: Layout, group_section: str) -> str | None:
    """分組節點的可選章號政策：`group.yaml` 的 `numbering`；缺/非法值 → None（沿用繼承/默認）。"""
    val = _group_meta(layout, group_section).get("numbering")
    return val if val in NUMBERING_POLICIES else None


def _depth(article: str, section: str) -> int:
    """文章內深度（article 之後的路徑段數）。根節(section==article)＝0。"""
    return len([p for p in section.split("/") if p]) - 1


# ── outline 排序拓樸：引擎單一共用來源（render 正史；aperture document map／`docspec status` group 列
#    一律 import 這三個函式，勿另寫副本——副本已實證漂移：漏讀 group.yaml order、退回字典序）──

def outline_order_by_section(layout: Layout, leaves: list[Leaf]) -> dict[str, float]:
    """建構 section → order：leaf `concept.order` 為底、合併 concept-less 分組節點的
    `group.yaml` `order`（缺則不入表＝排序時預設 0.0，既有行為）。`leaves` 通常為單一
    article 的葉集合；跨 article 混傳亦安全（section 路徑含 article 前綴、不相撞）。"""
    order_by_section = {
        lf.section: lf.order for lf in leaves if lf.concept is not None
    }
    # 分組節點（無 concept）排序：讀其 group.yaml 的可選 order；缺則維持預設 0.0（既有行為）。
    # 治「concept-less 分組節點固定 order=0.0 排到有序兄弟最前」（B8）。
    for lf in leaves:
        parts = [p for p in lf.section.split("/") if p]
        for i in range(2, len(parts)):
            gs = "/".join(parts[:i])
            if gs in order_by_section:
                continue   # 本身是 leaf（concept.order 優先）或已處理
            go = _group_order(layout, gs)
            if go is not None:
                order_by_section[gs] = go
    return order_by_section


def outline_sort_key(section: str, order_by_section: dict[str, float]) -> list:
    """沿路徑逐層 (order, name) 當排序鍵，做 outline order 拓樸。"""
    parts = [p for p in section.split("/") if p]
    key = []
    for i in range(1, len(parts) + 1):
        prefix = "/".join(parts[:i])
        key.append((order_by_section.get(prefix, 0.0), parts[i - 1]))
    return key


def outline_group_nodes(leaves: list[Leaf]) -> list[str]:
    """分組節點集合＝render 產 group marker 的同一套推導（path prefixes parts[:i]，
    i in range(2, len(parts))、本身非 leaf 節）；跨 leaf 去重、保排序。"""
    leaf_sections = {lf.section for lf in leaves}
    out: list[str] = []
    seen: set[str] = set()
    for lf in leaves:
        parts = [p for p in lf.section.split("/") if p]
        for i in range(2, len(parts)):
            gs = "/".join(parts[:i])
            if gs in seen or gs in leaf_sections:
                continue
            seen.add(gs)
            out.append(gs)
    return out


def outline_numbering(layout: Layout, art_leaves: list[Leaf],
                      article: str) -> dict[str, str | None]:
    """為一篇文章的每個節點（leaf＋分組節點）推導層級章號標籤（D4/D7）。

    回傳 section → 顯示標籤：str（如 `6.`／`6.1`／`附錄 A`／`A.1`）或 None（`numbering: none`＝不
    編號）；不在表內的 section（如文章根節＝文件標題）＝無編號。章號 derive 自 outline 排序拓樸
    （與 render／aperture document-map／`docspec status` 同一套 `outline_order_by_section`＋
    `outline_sort_key`）＋各節 `numbering` 政策——corpus title 永不含章號，單一真相＝order＋樹位
    置＋政策，重排即自動重編號（散文不動、指紋照 F2 沿用）。

    編號規則：逐層以「有效政策」（顯式 numbering，否則繼承最近祖先，否則 arabic）分派兄弟序號——
    arabic 兄弟走獨立整數計數（1,2,3…）、appendix 兄弟走獨立字母計數（A,B,C…）、none 兄弟不編號且
    兩計數皆跳過（不佔號、不使後續兄弟錯位）。子節標籤＝`<父前綴><.><自身序>`。頂層阿拉伯尾綴一點
    （`6.`）以符 export #09 去編號輸入形態；附錄字母只用在進入附錄子樹的第一層，更深層退阿拉伯（A.1）。
    """
    leaf_by_section = {lf.section: lf for lf in art_leaves}
    group_sections = set(outline_group_nodes(art_leaves))
    order_by_section = outline_order_by_section(layout, art_leaves)

    # children：parent section → 直屬子節點（含 leaf 與分組節點）。頂層節點 parent＝article；
    # 根節（section==article）＝文件標題，不入編號、無 parent。
    children: dict[str, list[str]] = {}
    for section in list(leaf_by_section) + list(group_sections):
        if section == article:
            continue
        parent = section.rsplit("/", 1)[0]
        children.setdefault(parent, []).append(section)

    def own_policy(section: str) -> str | None:
        if section in leaf_by_section:
            lf = leaf_by_section[section]
            val = lf.concept.get("numbering") if lf.concept else None
            return val if val in NUMBERING_POLICIES else None
        return _group_numbering(layout, section)

    labels: dict[str, str | None] = {}

    def assign(parent: str, parent_prefix: str, parent_policy: str) -> None:
        kids = sorted(children.get(parent, []),
                      key=lambda s: outline_sort_key(s, order_by_section))
        arabic_n = 0
        appendix_i = 0
        for kid in kids:
            eff = own_policy(kid) or parent_policy    # 繼承：最近祖先政策；根默認 arabic
            if eff == "none":
                labels[kid] = None
                assign(kid, parent_prefix, "none")    # none 子樹整體不編號
                continue
            # 附錄字母只在「進入附錄子樹的第一層」；父已是 appendix（更深層）＝退回阿拉伯（A.1）。
            letter_mode = eff == "appendix" and parent_policy != "appendix"
            if letter_mode:
                appendix_i += 1
                token = chr(ord("A") + appendix_i - 1)
                if parent_prefix:
                    disp = child_prefix = f"{parent_prefix}.{token}"
                else:
                    disp = f"{APPENDIX_HEADING_PREFIX}{token}"
                    child_prefix = token
            else:
                arabic_n += 1
                token = str(arabic_n)
                if parent_prefix:
                    disp = child_prefix = f"{parent_prefix}.{token}"
                else:
                    # 頂層裸整數尾綴一點（6.）＝符 export #09 `^\d+\.\s` 去編號輸入形態；
                    # 傳給子節的前綴不含尾點（子節＝6.1，非 6..1）。
                    disp = f"{token}."
                    child_prefix = token
            labels[kid] = disp
            assign(kid, child_prefix, eff)

    assign(article, "", "arabic")
    return labels


def parse_section_bodies(text: str, on_discard=None) -> dict[str, str]:
    """從現有 _latest.md 解析每節已寫散文（去掉 marker 與其後第一行標題）。

    〔#02〕`on_discard` 選配回呼：本函式對「無主內容」——首個 marker 前的 preamble、
    group marker 後的區塊（分組節點無散文槽）——一律丟棄；傳入回呼即逐塊回報
    `(位置, 原始內容)`（位置＝`"preamble"` 或該 group section id），由呼叫端決定要不要警告。
    預設 `None`＝既有呼叫端（detect_drift／lint／check）行為位元零變化。"""
    _, body = parse_frontmatter(text)
    lines = body.split("\n")
    bodies: dict[str, str] = {}
    current: str | None = None
    discard_loc = "preamble"    # current=None 時 buf 的歸屬位置（preamble 或 group section id）
    buf: list[str] = []

    def flush():
        if current is None:
            # 無主內容：照舊丟棄；有回呼才回報（#02，render 據此吐 WARN）。
            if on_discard is not None and buf:
                on_discard(discard_loc, "\n".join(buf))
            return
        block = buf[:]
        # 去掉前導空行 + 一行 markdown 標題（render 會重生標題）
        while block and not block[0].strip():
            block.pop(0)
        if block and re.match(r"^#{1,6}\s", block[0]):
            block.pop(0)
        bodies[current] = "\n".join(block).strip()

    for line in lines:
        m = MARKER_RE.match(line)
        if m:
            flush()
            current = m.group(1)
            buf = []
            continue
        gm = GROUP_MARKER_RE.match(line)
        if gm:
            # 分組標記：切斷前一節，隨後的分組標題行歸 current=None（忽略、不算任何節的散文）
            flush()
            current = None
            discard_loc = gm.group(1)
            buf = []
            continue
        # 無主行（preamble／group 後）也入 buf——owned 節行為不變，無主塊靠 flush 回報（#02）
        buf.append(line)
    flush()
    return bodies


def render_article(layout: Layout, leaves: list[Leaf], article: str,
                   ack_sections: set[str] | None = None,
                   ack_own_sections: set[str] | None = None,
                   reason: str = "",
                   rebaseline: bool = False) -> dict:
    """同步 docs/<article>/_latest.md 骨架；保留已寫散文；回報統計。

    `ack_sections`（F5）：作者確認這些節已對齊上游（散文依設計合理不需改）→ 重蓋其
    `anc`＋`style` 指紋至現值、清掉 `stale-inherited`／`stale-style`。守門：若該節其實
    `stale-own`/`stale-upstream`（own/deps 真的變了＝需重寫散文），ack **拒絕**並保住信號——ack 只清
    「祖先 brief／寫作 doctrine 動了但本節散文合理不需改（已符新風格／術語）」這一類，不能拿來吞掉
    真正的 re-draft 需求。

    `ack_own_sections`：內容軸（own/deps）的 acknowledge——源料變了但散文依設計合理不需改
    （結構接線／元資料類變更）→ 只把該節 `own`＋`deps` 蓋至現值，`anc`／`style` 沿用舊帳本值
    （被 stale-own 遮蔽的 stale-inherited/stale-style 自然浮出），並清掉 `redraft` 旗標。
    與 `ack_sections` 正交可組合（同節雙旗標＝全四軸蓋現值；ack 守門在 ack-own 先蓋後自然通過）。
    無帳本記錄（未撰寫）→ 跳過並回報於 `ack_own_skipped`。

    `rebaseline`：顯式重建基準——**忽略舊帳本**、每個有散文的節以現行算法全軸重算（散文與
    `_latest.md` 內容原樣保留、只重算指紋）。v1→v2 帳本遷移、deliverable-missing、壞帳本三情境
    共用此語義；遷移當下未處理的 stale 信號（含 redraft 旗標）被吸收成新基準——訊息由指令層明講。

    `reason`：本輪裁決理由——執行成功的 ack/ack-own 一律寫入 append-only verdicts journal
    （`--ack` 的 reason 選配可空；強制性由指令層把關）。被拒絕/跳過的裁決不留 journal。

    回傳 {sections, drafted, written_path, acked, ack_refused, ack_owned, ack_own_skipped}。
    """
    ack_sections = ack_sections or set()
    ack_own_sections = ack_own_sections or set()
    by_section = {lf.section: lf for lf in leaves}   # 全專案，供祖先 brief 查找
    dindex = decision_index(leaves)                  # 全專案決策索引，供 deps 指紋
    art_leaves = [lf for lf in leaves if lf.article == article]
    order_by_section = outline_order_by_section(layout, art_leaves)
    art_leaves.sort(key=lambda lf: outline_sort_key(lf.section, order_by_section))
    # 章號 derive（D4/D7）：leaf 與分組節點標題編號一律推導自 outline 拓樸＋numbering 政策，
    # 組裝時前綴進 heading（corpus title 不含章號）。None＝該節不編號（numbering: none／根節）。
    numbers = outline_numbering(layout, art_leaves, article)

    # 散文交叉引用錨解析器（P1b）：跨全專案（所有 article）建 section→label 與 id→section，
    # 使散文回引可跨文件解析當下 outline 號碼。號碼 derive（每次 render 重算）、不入源、prose 指紋
    # 正規化掉——重排幾次都不漂。all_numbers 逐 article 併（section 路徑含 article 前綴、不相撞）。
    all_numbers: dict[str, str | None] = {}
    for other in sorted({lf.article for lf in leaves}):
        other_leaves = [lf for lf in leaves if lf.article == other]
        all_numbers.update(outline_numbering(layout, other_leaves, other))
    id_to_section: dict[str, str] = {}
    title_by_section: dict[str, str] = {}
    for lf in leaves:
        title_by_section[lf.section] = lf.title
        if lf.concept and lf.concept.get("id"):
            id_to_section[str(lf.concept["id"])] = lf.section
    for did, rec in dindex.items():          # decision/history id → 其所在節（D3：綁決策解析到擁有節）
        id_to_section.setdefault(did, rec["section"])

    def _anchor_label(anchor_id: str) -> str | None:
        """散文錨 id → 當下可見標籤：`§6.5`／`附錄 A`／numbering:none 目標的標題名；
        目標不存在/退役＝None（標籤留空、check 報死引用）。"""
        sec = id_to_section.get(anchor_id)
        if sec is None:
            return None
        label = all_numbers.get(sec)
        if label is None:                    # numbering:none 或根節＝無號碼可注 → 注標題名（不吐空 §）
            return title_by_section.get(sec) or None
        bare = label.rstrip(".")             # 去頂層尾點（`6.`→`6`）；引用讀 `§6`
        if label.startswith(APPENDIX_HEADING_PREFIX):
            return bare                      # 附錄 A：裸標籤、不套 §
        return f"§{bare}"

    latest = layout.docs_latest(article)
    existing_bodies: dict[str, str] = {}
    discarded: list[tuple[str, str]] = []   # 〔#02〕無主散文塊 (位置, 原始內容)——寫檔時吐 WARN
    if latest.is_file():
        existing_bodies = parse_section_bodies(
            latest.read_text(encoding="utf-8"),
            on_discard=lambda loc, block: discarded.append((loc, block)))
    # 上次帳本：F2——指紋綁「散文上次基於什麼源料寫」。散文未重寫時沿用舊源指紋，
    # 不被「現在源料」抹掉 stale-own/stale-upstream 信號（sidecar 優先、舊 frontmatter fallback）。
    # --rebaseline＝顯式重置基準：忽略舊帳本（v1 值與 v2 算法不可比；或作者明示重建），
    # 每節走 _current() 全軸重算——吸收警語由指令層輸出。
    prior_ledger = {} if rebaseline else read_ledger(layout, article)
    # 專案級寫作 doctrine（writing-guide＋glossary）指紋：全文件共用一份，整輪 render 算一次。
    # 散文未重寫時沿用舊值（保住 stale-style 信號）；散文重寫/首次撰寫才記現值（見下方 _current）。
    style_now = style_fingerprint(layout)

    # 根節（section==article）＝文章標題＋全域導言；存在就由它當 `#`，
    # 否則退回印一行純標題（導言由人/文類決定，render 不強制生）。
    has_root = any(lf.section == article for lf in art_leaves)
    # 無 root section→封面標題用 corpus/<article>/group.yaml 的 title（缺則 humanize slug）
    #   ＝治「CJK 文件封面標題冒拼音/英文 slug」（A1）；與分組節點在地化標題同一機制。
    out: list[str] = [] if has_root else [f"# {_group_title(layout, article, article)}", ""]
    hashes: dict[str, str] = {}
    drafted = 0
    acked: list[str] = []
    ack_refused: list[str] = []
    ack_owned: list[str] = []
    verdicts: list[dict] = []     # 本輪執行成功的裁決（ack/ack-own）→ 寫檔後 append 進 journal
    emitted_groups: set[str] = set()
    prose_bodies: list[str] = []   # 非空節散文（CJK 封面提示的語言偵測用）
    for lf in art_leaves:
        depth = _depth(article, lf.section)
        # 補產祖先分組節點標題（文章內深度 1..depth-1），使階層連續、不跳級。
        # 分組節點無散文、不記指紋；同一分組單次 render 只出現一次（冪等）。
        parts = [p for p in lf.section.split("/") if p]
        for i in range(2, len(parts)):
            group_section = "/".join(parts[:i])
            if group_section in emitted_groups or group_section in by_section:
                continue  # 已產過，或本身是末節（將以自己的標題出現）→ 不另產分組標題
            emitted_groups.add(group_section)
            out.append(group_marker(group_section))
            # 分組標題：group.yaml title 優先（在地化）、缺則 humanize；章號前綴 derive（None＝不編號）；
            # 層級 clamp 至上限（防 #######）——章號深度與 `#` clamp 獨立（clamp 後仍帶完整點分編號）。
            gtitle = _group_title(layout, group_section, parts[i - 1])
            glabel = numbers.get(group_section)
            gtext = f"{glabel} {gtitle}" if glabel else gtitle
            out.append("#" * min(i, MAX_HEADING_LEVEL) + " " + gtext)
            out.append("")
        # 末節標題：層級＝depth+1，clamp 至上限（過深由 check fail-loud 擋；clamp 只防靜默破版）。
        # 章號前綴 derive（None＝根節/numbering:none＝不編號）；章號深度與 `#` clamp 獨立。
        label = numbers.get(lf.section)
        heading_text = f"{label} {lf.title}" if label else lf.title
        heading = "#" * min(depth + 1, MAX_HEADING_LEVEL) + " " + heading_text
        # 散文交叉引用錨：組裝時解析注入當下 §號碼（P1b）。只在散文 span 動、確定性、冪等；
        # 號碼 derive（不入源）、prose 指紋正規化掉——重排刷新號碼不誤標 drift。
        body = resolve_prose_anchors(existing_bodies.get(lf.section, "").strip(), _anchor_label)
        out.append(section_marker(lf.section))
        out.append(heading)
        out.append("")
        if body:
            prose_bodies.append(body)
            out.append(body)
            out.append("")
            # 有散文才記指紋：own=自己源、anc=祖先 brief、deps=realizes 共享真相、
            # prose=散文本身（diff 偵測手改）。
            # F2：指紋綁「散文上次基於什麼源料寫」。若散文自上次 render 未變（prose 指紋相同），
            # 沿用上次帳本的 own/anc/deps——不用「現在源料」重算，否則一跑 render（哪怕只重生
            # 骨架）就把 stale-own/stale-upstream 抹掉＝false-green。散文真的重寫（prose 變）或
            # 首次撰寫時，才以現在源料重算（這次散文確實基於現在源料寫）。
            prose_now = prose_hash(body)
            prev = prior_ledger.get(lf.section)

            def _current() -> dict:
                return {
                    "own": lf.source_hash(),
                    "anc": ancestor_brief_fingerprint(lf.section, by_section),
                    "deps": deps_fingerprint(lf, dindex),
                    "norm": ancestor_normative_fingerprint(lf.section, by_section),
                    "style": style_now,
                    "prose": prose_now,
                }

            def _reuse_or_current() -> dict:
                if isinstance(prev, dict) and prev.get("prose") == prose_now:
                    # 散文未重寫：own/anc/deps/norm/style 全沿用舊值＝保住既有 stale 信號
                    # （含 stale-norm/stale-style）。style 缺欄（軸上線前的帳本）以現值補基準
                    # （視既有內容為「當前 doctrine 已對齊」）；norm 缺欄不補——v1→v2 由版本閘
                    # ＋rebaseline 統一遷移，v2 帳本必有 norm，缺欄（手改）只是無信號、不假造基準。
                    rec = {"own": prev.get("own"), "anc": prev.get("anc"),
                           "deps": prev.get("deps"),
                           "norm": prev.get("norm"),
                           "style": prev.get("style") or style_now,
                           "prose": prose_now}
                    # 標髒旗標（stale/redraft 動詞）隨沿用分支攜帶＝信號跨（骨架）render 存活；
                    # 散文真重寫走 _current()（不含旗標）＝自然清除，無需顯式 un-mark 動詞。
                    if prev.get("redraft"):
                        rec["redraft"] = True
                    return rec
                return _current()

            def _verdict(verb: str, rec: dict) -> dict:
                return verdict_entry(verb, lf.section, reason,
                                     prev.get("own") if isinstance(prev, dict) else None,
                                     rec.get("own"), rec.get("prose"))

            # --ack-own：只對「有帳本記錄」的節生效；未撰寫（無記錄）→ 跳過（回報在
            # ack_own_skipped）——本輪若首寫散文本就走 _current() 全蓋，無需裁決。
            ack_own_hit = lf.section in ack_own_sections and isinstance(prev, dict)

            if lf.section in ack_sections:
                # F5：作者確認此節已對齊上游。只有當 own/deps 與帳本相符（即「僅 anc/norm/style
                # 變了」＝stale-inherited/norm/style、非 stale-own/upstream）才准重蓋章；否則拒絕、
                # 保住 re-draft 信號。重蓋集合＝anc＋norm＋style（規矩變了、散文合法不需變＝ack 語義）。
                # 同節同給 --ack-own：own/deps 先被 ack-own 蓋至現值 → 守門自然通過（全軸蓋章、
                # 正交可組合）；--ack 單獨用於 stale-own 的 refusal 語義逐字不變。
                cur = _current()
                prev_own = prev.get("own") if isinstance(prev, dict) else None
                prev_deps = prev.get("deps") if isinstance(prev, dict) else None
                if ack_own_hit or (
                        prev is not None and prev_own == cur["own"] and prev_deps == cur["deps"]):
                    rec = cur                      # 重蓋 anc/norm/style 至現值 → 清 stale-inherited/norm/style
                    if ack_own_hit:
                        ack_owned.append(lf.section)
                        verdicts.append(_verdict("ack-own", rec))
                    acked.append(lf.section)
                    verdicts.append(_verdict("ack", rec))
                else:
                    rec = _reuse_or_current()      # own/deps 真的變了＝需重寫散文，ack 不吞
                    ack_refused.append(lf.section)
            elif ack_own_hit:
                # --ack-own 語義：own+deps 蓋現值、anc/norm/style 沿用舊帳本值（被 stale-own 遮蔽的
                # stale-norm/stale-inherited/stale-style 自然浮出——precedence 本就只顯最重的）；
                # 清 redraft 旗標（作者的顯式反裁決）。
                cur = _current()
                rec = {"own": cur["own"], "anc": prev.get("anc"),
                       "deps": cur["deps"],
                       "norm": prev.get("norm"),
                       "style": prev.get("style") or style_now,
                       "prose": prose_now}
                ack_owned.append(lf.section)
                verdicts.append(_verdict("ack-own", rec))
            else:
                # F2：散文未重寫則沿用舊源指紋（保住 stale-own/upstream 信號）；
                #     散文重寫或首次撰寫才以現在源料重算。
                rec = _reuse_or_current()
            hashes[lf.section] = rec
            drafted += 1
        else:
            out.append("")

    # CJK 封面提示（Decision 9）：humanize fallback 真的打在封面（無 root 節、無 group.yaml
    # title）且內容 CJK 為主 → stderr 一行 advisory 提示（不改 exit code / 輸出檔）。
    # 語言偵測 fallback "en" 使空白/未撰寫文章保持沉默（無散文＝無提示噪音）。
    if not has_root:
        _cover_title = _group_meta(layout, article).get("title")
        if not (isinstance(_cover_title, str) and _cover_title.strip()):
            from dspx.engine.config import detect_language
            if detect_language("\n".join(prose_bodies), "en") == "zh":
                import sys
                sys.stderr.write(
                    f"docspec: ⚠ cover title falls back to the humanized slug "
                    f"\"{_group_title(layout, article, article)}\" but the article's content is CJK "
                    f"— add corpus/{article}/group.yaml with a localized title: to fix the cover "
                    f"heading.\n")

    # 保留現有 version（若有），render 不升版（升版是 publish 的事）。
    # 版本＝semver 字串；未發行的骨架預設 "0.0.0"（佔位、非真版）。
    version = "0.0.0"
    if latest.is_file():
        meta, _ = parse_frontmatter(latest.read_text(encoding="utf-8"))
        existing = meta.get("version")
        if existing not in (None, "", 0):
            version = existing

    # 指紋帳本搬進隱藏 sidecar（ISSUE-3）；`_latest.md` frontmatter 只留輕量 article/version
    # ——交付物開頭不再被巨大指紋表佔據。舊交付物若 frontmatter 仍帶 sections，這次 render 後
    # 即遷出（frontmatter 不再寫 sections、改寫 sidecar）。
    meta = {"article": article, "version": version}
    latest.parent.mkdir(parents=True, exist_ok=True)

    # 〔#02〕無主散文丟棄 WARN：preamble／group marker 後的內容不屬任何節、寫檔即被丟棄。
    # 防誤報：先剝除 render 自產行——group marker 後緊接的 `#…` 分組標題行、無 root 節時的
    # 封面 `#` 標題行（有 root 時 preamble 無自產行、標題行一律視為人寫＝寧報勿吞）——剝除後
    # 仍非空白才 WARN。advisory：只上 stderr，不改 exit code、不改輸出檔。
    if discarded:
        import sys
        for loc, block in discarded:
            blines = block.split("\n")
            while blines and not blines[0].strip():
                blines.pop(0)
            strip_own_heading = (loc != "preamble") or (not has_root)
            if strip_own_heading and blines and re.match(r"^#{1,6}\s", blines[0]):
                blines.pop(0)
            if "\n".join(blines).strip():
                where = ("the preamble (before the first section marker)"
                         if loc == "preamble" else f"group \"{loc}\"")
                sys.stderr.write(
                    f"docspec: ⚠ \"{article}\": unowned prose at {where} belongs to no section "
                    "and was DISCARDED by this render — hand-edits there are never preserved; "
                    "move the content into a section's own slot (or a corpus file).\n")

    latest.write_text(render_frontmatter(meta, "\n".join(out)), encoding="utf-8", newline="\n")
    # groups 指紋一併入帳（D4）：render 完成＝骨架與 group.yaml 對齊，蓋現值。
    write_ledger(layout, article, hashes, groups_fp=groups_fingerprint(layout, article))
    # 執行成功的裁決留痕（append-only journal）；被拒/跳過的不留。render 對 journal 只 append、
    # 永不重寫/重生（sections 帳本才是每輪重生的那個）。
    append_verdicts(layout, article, verdicts)

    return {
        "sections": [lf.section for lf in art_leaves],
        "drafted": drafted,
        "written_path": str(latest),
        "acked": acked,
        "ack_refused": ack_refused,
        "ack_owned": ack_owned,
        "ack_own_skipped": sorted(ack_own_sections - set(ack_owned)),
    }


def detect_drift(layout: Layout, article: str) -> list[dict]:
    """偵測交付物被手改：_latest 某節散文 ≠ 上次 render 記的 prose 指紋。

    回傳每個漂移節 {section, recorded, current}。沒 _latest 或沒記指紋 → 跳過。
    純確定性：只報「散文被改過」，不判斷改得對不對（那是 agent 的事）。
    """
    latest = layout.docs_latest(article)
    if not latest.is_file():
        return []
    text = latest.read_text(encoding="utf-8")
    recorded = read_ledger(layout, article)   # sidecar 優先、舊 frontmatter fallback
    bodies = parse_section_bodies(text)
    drift = []
    for section, body in bodies.items():
        rec = recorded.get(section)
        rec_prose = rec.get("prose") if isinstance(rec, dict) else None
        if rec_prose is None:
            continue                      # 沒基準（未撰寫/舊格式）→ 不算漂移
        if prose_hash(body) != rec_prose:
            drift.append({"section": section, "recorded": rec_prose,
                          "current": prose_hash(body)})
    return drift


def strip_markers(text: str) -> str:
    """移除所有隱形 section / group 標記，保留內容（publish 凍結快照用）。"""
    return "\n".join(
        line for line in text.split("\n")
        if not MARKER_RE.match(line) and not GROUP_MARKER_RE.match(line)
        and not CLOSING_MARKER_RE.match(line)
    )
