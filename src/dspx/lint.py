"""lint：交付物潔淨度（報告；publish 時 ERROR 級當閘）。

潔淨規則的權威 SoT＝capability `deliverable-cleanliness`（openspec/specs/，由 change
deliverable-cleanliness-truthful 落定，取代已 rebaseline 移出的歷史 engine-spec §6）。
  V1 docs 洩漏代號/id           ERROR
  V2 docs 殘留內部錨點           ERROR
  V3 docs 殘留鷹架痕跡           ERROR
  V4 docs 殘留 placeholder 類    ERROR  ← [TBD]/[TBD: …]/[TODO]/[FIXME]/[待補] 與裸填空 <…>/{…}
  V5 material 分塊文法           ERROR
  V7 material 雜思痕跡           ERROR
  V8 骨肉漂移（corpus↔docs）      WARN
  V9 realizes 指向退場決策        WARN
  V10 跨文件數字一致             WARN   ← 同 snake_case 指涉的同單位值相互衝突（advisory、不阻塞）
  V11 凍結區（archive/）被竄改    ERROR  ← 已發行版本不可變（見 dspx.freeze）
  V12 docs 殘留 GFM 警示/暫停旗   ERROR  ← `> [!WARNING]` 等 alert；draft 撞決策衝突刻意產生、絕不該 ship
  Vg1/Vg2 術語一致               WARN
  Ve1 死錨點連結（export 破）     WARN  ← `](#x)` 對不上任何標題 slug → xelatex PDF 整份失敗
  Ve2 非標準 markdown（@import）  WARN  ← MPE 指令不會在 docx/PDF 渲染
  Ve3 非 backend-neutral 圖記法     WARN  ← ```mermaid（不渲染）或 raw `{=latex}`/`{=tex}`（TikZ）
                                          ＝非 backend-neutral；改用嵌入式 drawio 圖片
  V6（散文滲入 docs 偵測）→ 後補。

  export-safety（Ve）＝把「匯出時才炸的機械問題」前移成 lint 事前驗證：交付物潔淨＝
  export-clean by construction。只收**機械 drift**（死連結、非標準語法、非中立圖記法）。
  ★Ve3 註記（隨 typst-default-dual-track 轉向更新）：交付物的圖必須是 **backend-neutral 嵌入圖片**
  （`dspx-diagram` 的委派 subagent 把 drawio 渲成 SVG、`![](assets/…)` 嵌入；兩條 export 軌都吃）。
  兩類機械 drift 在此 WARN：(a) ```mermaid——受控 toolchain 不渲染、只變佔位框；(b) raw `{=latex}`/
  `{=tex}` 區塊（舊 TikZ 寫法）——LaTeX-only、預設 Typst 軌會被剝掉而消失。兩者都非 backend-neutral，
  與 Ve2 的 @import 同類，故 WARN 前移、導向改用 drawio 圖片。字體/留白仍＝export 設定、不進此處。
  （TikZ／mermaid→TikZ 教條已退場；diagrams travel as images。）
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from dspx.check import run_check
from dspx.layout import Layout
from dspx.model import Leaf
from dspx.schema import Schema

ERROR = "ERROR"
WARN = "WARN"

_ANCHOR_RE = re.compile(r"\{#[^}]+\}")
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
# V4 placeholder 類（掃描在剝程式碼後做）：括號式 [TBD]/[TBD: …]/[TODO]/[FIXME]/[XXX]/[待補]/
# [待填]，與裸填空 <…>/{…}（後者僅在含 placeholder 關鍵字時抓，避免誤殺泛型 <T>/變數 {value}）。
_PLACEHOLDER_RE = re.compile(
    r"\[\s*(?:TBD|TODO|FIXME|XXX|待補|待填)\b[^\]]*\]"
    r"|[<{]\s*(?:TBD|TODO|FIXME|XXX|待補|待填|placeholder|fill[\s-]?in|tktk)\b[^>}]*[>}]",
    re.IGNORECASE,
)
# V12 GFM 警示/暫停旗（剝程式碼後、逐行）：blockquote 開頭的 [!NOTE|TIP|IMPORTANT|WARNING|CAUTION]。
_ALERT_RE = re.compile(r"^\s*>\s*\[!(?:NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]", re.IGNORECASE | re.MULTILINE)
# V10 數字一致：number+unit token 與同行最近的 snake_case 指涉（如 e_stop / task_assign）。
# 封閉單位集抑制誤報；snake_case（至少一個底線）才當 key，排除 timeout/status 等裸詞與 CJK 鄰詞。
_NUM_UNIT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(ms|s|Hz|%)\b")
_SNAKE_RE = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)+")
# V3 只抓 docspec 自己塞的鷹架佔位字（instructions 模板的 {id}/{title}/{order}/{name}）；
# generic `<…>` 在技術散文太氾濫（KE 模板 <vehicle_id>、泛型 <T> 都合法），不再誤殺。
_SCAFFOLD_RE = re.compile(r"\{(?:id|title|order|name)\}")
# 潔淨掃描（V1–V4）前剝掉程式碼：fenced ```…``` 與 inline `…` 內是內容（KE 模板/JSON/
# 變數名/泛型），不是交付物洩漏的機械。同 V6 對 material code block 的處理。
_FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_MATERIAL_HEADING_RE = re.compile(r"^##\s+(\w+):\s+.+\{#m-[^}]+\}\s*$")
_NOISE_RE = re.compile(r"🟡|\[TBD\]", re.IGNORECASE)
_MATERIAL_TYPES = ("src", "fact", "framing", "eg", "layout")


@dataclass(frozen=True)
class Finding:
    rule: str
    level: str
    where: str
    detail: str


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    parts = text.split("\n")
    for i in range(1, len(parts)):
        if parts[i].strip() == "---":
            return "\n".join(parts[i + 1:])
    return text


def _lint_docs(layout: Layout, articles: list[str], all_ids: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    for article in articles:
        path = layout.docs_latest(article)
        if not path.is_file():
            continue
        body = _strip_frontmatter(path.read_text(encoding="utf-8"))
        # 隱形章節標記（<!-- dspx:section … -->）讀者看不到、publish 會剝除——
        # 不算交付物洩漏，掃描前先去掉所有 HTML 註解，免得誤判 V2/V3。
        # 再剝掉程式碼區塊：裡面的 KE 模板/JSON/變數名是內容，不是機械。
        body = _HTML_COMMENT_RE.sub("", body)
        body = _FENCED_CODE_RE.sub("", body)
        body = _INLINE_CODE_RE.sub("", body)
        where = f"docs/{article}/_latest.md"
        for the_id in sorted(all_ids):
            if the_id in body:
                findings.append(Finding("V1", ERROR, where, f"leaked internal code/id \"{the_id}\""))
        for m in _ANCHOR_RE.findall(body):
            findings.append(Finding("V2", ERROR, where, f"leftover internal anchor \"{m}\""))
        if _SCAFFOLD_RE.search(body):
            findings.append(Finding("V3", ERROR, where, "leftover scaffold placeholder ({id}/{title}/{order}/{name})"))
        for m in dict.fromkeys(_PLACEHOLDER_RE.findall(body)):
            findings.append(Finding("V4", ERROR, where, f"leftover placeholder \"{m.strip()}\""))
        for m in _ALERT_RE.findall(body):
            findings.append(Finding("V12", ERROR, where,
                                    "leftover GFM alert/admonition (e.g. `> [!WARNING]`) -- "
                                    "draft emits these as a stop-and-flag marker; never ship one"))
    return findings


def _lint_numbers(layout: Layout, articles: list[str]) -> list[Finding]:
    """V10 跨文件數字一致（WARN、非阻塞、不改寫）。

    把每個 number+unit token 關聯到「同一行最近的 snake_case 指涉」（如 e_stop、task_assign）。
    全文蒐集後，同一 (指涉, 單位) 出現相互衝突的值 → WARN。封閉單位集 + snake_case-only key
    抑制誤報（不同度量如 timeout 1000ms vs 延遲 100ms 因指涉不同而不衝突）。
    """
    findings: list[Finding] = []
    for article in articles:
        path = layout.docs_latest(article)
        if not path.is_file():
            continue
        body = _strip_frontmatter(path.read_text(encoding="utf-8"))
        body = _HTML_COMMENT_RE.sub("", body)
        body = _FENCED_CODE_RE.sub("", body)
        body = _INLINE_CODE_RE.sub("", body)
        where = f"docs/{article}/_latest.md"
        # (key, unit) -> 值集合
        seen: dict[tuple[str, str], set[str]] = {}
        for line in body.splitlines():
            for nm in _NUM_UNIT_RE.finditer(line):
                # 最近的「在此數字之前」的 snake_case 指涉
                keys = [s.group(0) for s in _SNAKE_RE.finditer(line) if s.start() < nm.start()]
                if not keys:
                    continue
                key = keys[-1]
                seen.setdefault((key, nm.group(2)), set()).add(nm.group(1))
        for (key, unit), vals in sorted(seen.items()):
            if len(vals) > 1:
                joined = " vs ".join(sorted(f"{v}{unit}" for v in vals))
                findings.append(Finding("V10", WARN, where,
                    f"number drift: \"{key}\" has conflicting {unit} values ({joined}) -- "
                    "reconcile against the source (advisory; does not block publish)"))
    return findings


def _lint_material(leaf: Leaf) -> list[Finding]:
    path = leaf.dir / "material.md"
    if not path.is_file():
        return []
    findings: list[Finding] = []
    where = f"{leaf.section}/material.md"
    prose_run = 0          # V6：連續純文字行（非條列/引文/表格/標題/空白/程式碼）計數
    prose_start = 0
    in_code = False        # 圍欄式程式碼區塊內＝結構化內容（draft 要逐字渲染），非散文
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_code = not in_code
            prose_run = 0          # 圍欄行本身＝結構化、且重置散文計數
            continue
        if in_code:
            continue              # 程式碼內容行不算散文
        if line.startswith("## "):
            m = _MATERIAL_HEADING_RE.match(line)
            if not m:
                findings.append(Finding("V5", ERROR, where,
                                        f"line {lineno}: heading does not match `## <type>: <title> {{#m-<anchor>}}`"))
            elif m.group(1) not in _MATERIAL_TYPES:
                findings.append(Finding("V5", ERROR, where,
                                        f"line {lineno}: type \"{m.group(1)}\" not in {_MATERIAL_TYPES}"))
        if _NOISE_RE.search(line):
            findings.append(Finding("V7", ERROR, where, f"line {lineno}: stray-thought marker (🟡/[TBD])"))
        # V6：偵測散文滲入（material 應只用條列/引文/表格）
        stripped = line.strip()
        is_structured = (not stripped or stripped.startswith(("-", "*", ">", "|", "#", "<!--"))
                         or re.match(r"^\d+[.)]", stripped))
        if is_structured:
            prose_run = 0
        else:
            prose_run += 1
            if prose_run == 1:
                prose_start = lineno
            if prose_run == 4:
                findings.append(Finding("V6", WARN, where,
                    f"from line {prose_start}: >=4 consecutive lines of plain prose -- material should use bullets/quotes/tables; prose belongs in docs"))
    return findings


def _lint_drift(layout, leaves: list[Leaf]) -> list[Finding]:
    """V8 骨肉漂移：corpus 章節 vs docs/_latest 不一致（提醒 docspec render）。"""
    from dspx.render import parse_section_bodies
    findings: list[Finding] = []
    by_article: dict[str, set] = {}
    for leaf in leaves:
        by_article.setdefault(leaf.article, set()).add(leaf.section)
    for article, corpus_sections in by_article.items():
        path = layout.docs_latest(article)
        if not path.is_file():
            continue
        rendered = set(parse_section_bodies(path.read_text(encoding="utf-8")))
        where = f"docs/{article}/_latest.md"
        for missing in sorted(corpus_sections - rendered):
            findings.append(Finding("V8", WARN, where,
                f"section \"{missing}\" exists in corpus but not projected into docs (run docspec render {article})"))
        for orphan in sorted(rendered - corpus_sections):
            findings.append(Finding("V8", WARN, where,
                f"docs has orphan section \"{orphan}\" (no such section in corpus; run docspec render {article})"))
    return findings


def run_lint(layout: Layout, leaves: list[Leaf], schema: Schema) -> list[Finding]:
    index = run_check(leaves, schema).index
    # 只比 concept/decision/history 的 id（sec-…、決策 id）；
    # 殘留 markdown 標題錨點 {#…} 由 V2 抓，不納入 V1 以免誤殺常用字。
    all_ids = set(index.ids)
    articles = sorted({leaf.article for leaf in leaves})
    findings = _lint_docs(layout, articles, all_ids)
    findings.extend(_lint_numbers(layout, articles))
    for leaf in leaves:
        findings.extend(_lint_material(leaf))
        findings.extend(_lint_realizes(leaf, index))
    findings.extend(_lint_glossary(layout, articles))
    findings.extend(_lint_export_safety(layout, articles))
    findings.extend(_lint_drift(layout, leaves))
    findings.extend(_lint_freeze(layout))
    findings.extend(_lint_roadmap(layout, leaves))
    return findings


def _lint_freeze(layout: Layout) -> list[Finding]:
    """V11 凍結區完整性：archive/ 內已發行快照被竄改/刪除/未登記 → ERROR（歷史不可變）。"""
    from dspx import freeze
    findings: list[Finding] = []
    for rel, problem in freeze.verify(layout.planning_home, layout.project_root, layout.docs_dir):
        findings.append(Finding("V11", ERROR, rel,
                                f"frozen area (archive/) {problem} -- published versions are immutable"))
    return findings


def _lint_glossary(layout, articles: list[str]) -> list[Finding]:
    """術語一致性提醒（皆 WARN；精確同物異名判定→audit）。
    Vg1 同物異名：docs 出現某詞的 aliases_forbidden → 提醒改正名。
    Vg2 縮寫裸奔：module 桶的 code（如 RMM）在 docs 散文出現 → 提醒中文化。
    """
    from dspx.glossary import load_glossary
    terms = load_glossary(layout)
    if not terms:
        return []
    findings: list[Finding] = []
    for article in articles:
        path = layout.docs_latest(article)
        if not path.is_file():
            continue
        body = _HTML_COMMENT_RE.sub("", _strip_frontmatter(path.read_text(encoding="utf-8")))
        where = f"docs/{article}/_latest.md"
        for t in terms:
            canonical = t.get("canonical", "")
            for alias in (t.get("aliases_forbidden") or []):
                if alias and str(alias) in body:
                    findings.append(Finding("Vg1", WARN, where,
                        f"possible synonym \"{alias}\" -> canonical name should be \"{canonical}\" (confirm context; precise judgment is in audit)"))
            code = t.get("code")
            # Vg2 只在「整篇從未在地化（canonical 從不出現）卻裸用縮寫」時報——若 canonical 已在
            # 文中出現過（首用已展開/在地化），後續裸用縮寫是合法 shorthand，不再每次誤報
            # （否則 ODD/MRM 這類已正確 gloss 的縮寫每次裸用都被 WARN，訓練作者忽略 Vg2）。
            if (t.get("bucket") == "module" and code and _bare_token(str(code), body)
                    and not (canonical and str(canonical) in body)):
                findings.append(Finding("Vg2", WARN, where,
                    f"module abbreviation \"{code}\" used bare and never localized -> "
                    f"introduce it as \"{canonical}\" (bucket 1)"))
    return findings


def _bare_token(token: str, body: str) -> bool:
    """token 以獨立字詞出現（前後非英數）。"""
    return re.search(r"(?<![A-Za-z0-9])" + re.escape(token) + r"(?![A-Za-z0-9])", body) is not None


_ROADMAP_OPEN_MAX = 7  # per-doc 開啟項上限：超過＝backlog 變筆記傾倒場（軟提醒）


def _lint_roadmap(layout: Layout, leaves: list[Leaf]) -> list[Finding]:
    """roadmap 軟提醒（皆 WARN、非阻塞；「該不該做」是 audit，這裡只抓機械徵兆）。
    Vr1 per-doc 開啟項（open）過多（>7）→ backlog 淪為筆記傾倒場。
    Vr2 status:doing 但 target 節無 develop.md 活動 → doing 沒拉進 develop。
    Vr3 status:done 缺 done-to → 完成記錄不完整（去向不明）。
    """
    from dspx import roadmap as roadmap_mod

    findings: list[Finding] = []

    # target（section id ∪ section 路徑）→ leaf，供解析 develop.md 活動。
    by_target: dict[str, Leaf] = {}
    for leaf in leaves:
        by_target[leaf.section] = leaf
        if leaf.concept_id:
            by_target[str(leaf.concept_id)] = leaf

    # Vr1：每個 distinct article 的 per-doc roadmap 開啟項計數。
    seen_articles: list[str] = []
    for leaf in leaves:
        if leaf.article and leaf.article not in seen_articles:
            seen_articles.append(leaf.article)
    for art in seen_articles:
        entries = roadmap_mod.load_doc_roadmap(layout.section_dir(art), art)
        opens = [e for e in entries if e.get("status") == "open"]
        if len(opens) > _ROADMAP_OPEN_MAX:
            findings.append(Finding("Vr1", WARN, f"corpus/{art}/roadmap.yaml",
                f"{len(opens)} open items (>{_ROADMAP_OPEN_MAX}) -- don't let the backlog become a notes dump; "
                "split, start, or drop some"))

    # Vr2/Vr3：跨全部 entry（含 forest）。
    for e in roadmap_mod.all_entries(layout, leaves):
        rid = e.get("id")
        store = e.get("_store", "roadmap")
        where = f"{store}/roadmap.yaml"
        status = e.get("status")
        if status == "doing":
            leaf = by_target.get(str(e.get("target")))
            if leaf is None or not (leaf.dir / "develop.md").is_file():
                findings.append(Finding("Vr2", WARN, where,
                    f"entry \"{rid}\" status:doing but target \"{e.get('target')}\" has no develop.md "
                    "activity -- starting work means pulling it into develop.md"))
        elif status == "done" and not e.get("done-to"):
            findings.append(Finding("Vr3", WARN, where,
                f"entry \"{rid}\" status:done missing done-to -- the completion record has no destination"))
    return findings


_ANCHOR_LINK_RE = re.compile(r"\]\(#([^)\s]+)\)")   # markdown 內部連結 [文字](#anchor)
_HEADING_RE = re.compile(r"^#{1,6}\s+(.*\S)\s*$")
_IMPORT_RE = re.compile(r"(?m)^@import\b")           # MPE include 指令
_MERMAID_FENCE_RE = re.compile(r"(?m)^\s*```+\s*mermaid\b")   # Ve3a：不渲染的 mermaid 圖記法
_RAW_LATEX_FENCE_RE = re.compile(r"(?m)^\s*```+\s*\{=(?:latex|tex)\}")  # Ve3b：LaTeX-only raw 區塊（舊 TikZ）
_INLINE_FMT_RE = re.compile(r"`[^`]*`|\*\*?|__?")
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_SLUG_DROP_RE = re.compile(r"[^\w.\- ]", re.UNICODE)  # 保留 \w(含 CJK)/._- 與空白；其餘剝
_FIRST_LETTER_RE = re.compile(r"[^\W\d_]", re.UNICODE)  # 第一個「字母」（含 CJK，非數字/底線）


def _slugify(text: str) -> str:
    """仿 pandoc auto_identifier：標題文字 → 錨點 slug（供 Ve1 解析內部連結是否命中）。

    剝 inline 格式/連結 → 去非（英數/CJK/._-/空白）→ 空白轉連字號 → 小寫 →
    去開頭非字母段（pandoc：識別字不以數字/標點開頭）。CJK 比照 pandoc 視為字母、保留。
    """
    t = _MD_LINK_RE.sub(r"\1", text)
    t = _INLINE_FMT_RE.sub("", t)
    t = _SLUG_DROP_RE.sub("", t)
    t = re.sub(r"\s+", "-", t.strip()).lower()
    m = _FIRST_LETTER_RE.search(t)
    return t[m.start():] if m else ""


def _lint_export_safety(layout: Layout, articles: list[str]) -> list[Finding]:
    """Ve＝export-safety：把「匯出才炸的機械問題」前移成事前 lint（皆 WARN、非阻塞）。

    Ve1 死錨點連結：`](#x)` 的 x 對不上任何標題 slug → xelatex PDF 整份編譯失敗
                    （HTML 只變死連結、xelatex 嚴格擋）。
    Ve2 非標準 markdown：`@import` 等 MPE 指令 → 不會在 docx/PDF 交付物渲染。
    Ve3 非中立圖記法：```mermaid（不渲染）或 raw `{=latex}`/`{=tex}`（LaTeX-only TikZ，預設 Typst
                      軌會被剝掉）→ 改用嵌入式圖片（dspx-diagram：drawio 渲成 PNG）。
    """
    findings: list[Finding] = []
    for article in articles:
        path = layout.docs_latest(article)
        if not path.is_file():
            continue
        body = _HTML_COMMENT_RE.sub("", _strip_frontmatter(path.read_text(encoding="utf-8")))
        # 標題 slug 集（連結解析基準）：取剝程式碼前的全標題（標題不會在 code fence 內起算）
        slugs = {_slugify(m.group(1)) for line in body.splitlines()
                 if (m := _HEADING_RE.match(line))}
        # 連結/指令掃描在「剝掉程式碼」後做：code fence/inline code 裡的 `](#x)`、@import 是內容範例
        scan = _INLINE_CODE_RE.sub("", _FENCED_CODE_RE.sub("", body))
        where = f"docs/{article}/_latest.md"
        seen: set[str] = set()
        for m in _ANCHOR_LINK_RE.finditer(scan):
            anchor = m.group(1)
            if anchor not in slugs and anchor not in seen:
                seen.add(anchor)
                findings.append(Finding("Ve1", WARN, where,
                    f"internal link \"#{anchor}\" matches no heading -- PDF export (xelatex) will fail entirely; fix or remove"))
        if _IMPORT_RE.search(scan):
            findings.append(Finding("Ve2", WARN, where,
                "contains non-standard markdown (MPE) directives like `@import` -- they won't render in the docx/PDF deliverable; remove or use standard syntax"))
        # Ve3 掃 body（不剝 code fence——這些記法本身就是 fence）：非 backend-neutral 圖記法。
        if _MERMAID_FENCE_RE.search(body):
            findings.append(Finding("Ve3", WARN, where,
                "contains a ```mermaid diagram -- mermaid does not render in the controlled toolchain (it ships as a placeholder box); author the diagram as an embedded image instead (the dspx-diagram subagent renders drawio to a raster PNG, embedded with `![](assets/...)`)"))
        if _RAW_LATEX_FENCE_RE.search(body):
            findings.append(Finding("Ve3", WARN, where,
                "contains a raw `{=latex}`/`{=tex}` block (LaTeX-only, e.g. TikZ) -- it is not backend-neutral and the default Typst track strips it (the figure silently disappears); author the diagram as an embedded image instead (drawio rendered to a raster PNG via the dspx-diagram subagent)"))
    return findings


def _lint_realizes(leaf: Leaf, index) -> list[Finding]:
    """V9：realizes 指向已退場（history）的決策 → 警告改指最新（源頭）。"""
    findings: list[Finding] = []
    for rid in ((leaf.concept or {}).get("realizes") or []):
        rec = index.ids.get(str(rid))
        if rec is not None and rec.kind == "history":
            findings.append(Finding("V9", WARN, f"{leaf.section}/concept.yaml",
                                    f"realizes points to retired decision \"{rid}\" ({rec.section}) -- should point to the latest decision that supersedes it"))
    return findings
