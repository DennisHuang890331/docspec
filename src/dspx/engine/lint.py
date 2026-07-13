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
  V11 凍結區（archive/）被竄改    ERROR  ← 已發行版本不可變（見 dspx.reports.freeze）
  V12 docs 殘留 GFM 警示/暫停旗   ERROR  ← `> [!WARNING]` 等 alert；draft 撞決策衝突刻意產生、絕不該 ship
  V15 docs 殘留撰寫工具/治理詞彙   ERROR  ← forest/governed-by/治理父/fan-in/factcheck/Tier-N/L2a/§回引…＝後台詞洩進交付物（補 V1 覆蓋缺口）
  V16 規範語句逃避詞（同句 應/不得）WARN  ← 最好／儘量／酌情／如有可能／視情況／最大限度（必要時故意排除，見下）
  V17 英文 AI-ism 詞彙            WARN  ← delve/tapestry/seamless…封閉 13 組＋句首 In today's；robust 刻意排除（見下）
  V18 散文殘留半形標點           WARN  ← 散文面 span 內 normalize 會轉的半形標點（`,`/`.`/`:`/`;`/`?`/`!`）→ 指向 `docspec normalize`（不教手改）
  V19 brief 欄逐字複述祖先        WARN  ← concept.brief 子欄 strip 後 byte 等於最近提供該欄的祖先值（沿 aperture 祖先鏈）→ 指向刪欄改繼承／`docspec store tidy`
  V20 title 章號前綴             WARN  ← concept/group title 以大綱編號起頭（阿拉伯 `6.`／全形／頓號 `6、`／附錄字母 `A.`）→ 章號 render 推導、指向 `docspec store tidy`
  V21 散文未綁錨字面章號          WARN  ← 散文 `§9.2`／`第 6 章`／`見 §12` 未綁穩定錨（重排即漂）→ 改綁交叉引用錨（號碼 render 注入）；外部標準條號（`ISO … §4.2`）豁免
  Vg1/Vg2 術語一致               WARN
  Ve1 死錨點連結（export 破）     WARN  ← `](#x)` 對不上任何標題 slug → xelatex PDF 整份失敗
  Ve2 非標準 markdown（@import）  WARN  ← MPE 指令不會在 docx/PDF 渲染
  Ve3 非 backend-neutral 圖記法     WARN  ← ```mermaid（不渲染）或 raw `{=latex}`/`{=tex}`（TikZ）
                                          ＝非 backend-neutral；改用嵌入式 drawio 圖片
  Vr1 roadmap per-doc entry 過多（>7）  WARN  ← 在檔全是待辦（無 status 了）、別讓 backlog 變傾倒場
  Vr2 promoted entry 仍帶實質內容        WARN  ← 含 promoted-to 卻超出 id/title/promoted-to ＝搬家沒搬乾淨
  Vr3 roadmap↔audit 雙帳鏡像            WARN  ← entry.what 散文引用一條仍全文開放的 finding id ＝該晉升搬家、非複製
  Va1 promoted finding 仍帶全文          WARN  ← 含 promoted-to 卻 finding 欄仍有實質內容 ＝搬家沒搬乾淨
  Va2 finding 散文殘留行號錨點           WARN  ← `finding` 文字內 `L###`/`L###/###` 形態 ＝ render 後座標會漂
  V6（散文滲入 docs 偵測）→ 後補。

  export-safety（Ve）＝把「匯出時才炸的機械問題」前移成 lint 事前驗證：交付物潔淨＝
  export-clean by construction。只收**機械 drift**（死連結、非標準語法、非中立圖記法）。
  ★Ve3 註記（隨 typst-default-dual-track 轉向更新）：交付物的圖必須是 **backend-neutral 嵌入圖片**
  （`dspx-diagram` 的委派 subagent 把 drawio 渲成高解析 PNG、`![](assets/…)` 嵌入；兩條 export 軌都吃；
   用 PNG 不用 SVG——drawio 的 SVG 在 Typst 軌變黑塊）。
  兩類機械 drift 在此 WARN：(a) ```mermaid——受控 toolchain 不渲染、只變佔位框；(b) raw `{=latex}`/
  `{=tex}` 區塊（舊 TikZ 寫法）——LaTeX-only、預設 Typst 軌會被剝掉而消失。兩者都非 backend-neutral，
  與 Ve2 的 @import 同類，故 WARN 前移、導向改用 drawio 圖片。字體/留白仍＝export 設定、不進此處。
  （TikZ／mermaid→TikZ 教條已退場；diagrams travel as images。）

  finding 定位：交付物本文規則（V1–V4/V12/V13/V15/V16/V17/V18）的 where 帶章節定位
  `docs/<article>/_latest.md § <section-path>`——沿隱形 `dspx:section`/`dspx:group` 標記切段、
  逐段掃描；首個標記前的 preamble／整份無標記的檔案回退檔案級 where。去重單位＝每章節
  （同 token 洩漏兩章節＝兩筆各自可定位的 finding）。V10 為全文聚合檢查、維持檔案級。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from dspx.check import run_check
from dspx.engine.layout import Layout
from dspx.engine.model import Leaf
from dspx.engine.schema import Schema

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
# V13 保留範例/佔位 token 外洩（WARN，非阻塞）：RFC 2606 保留範例網域（example.com/net/org/edu，
# 含 user@example.* 信箱）、`lorem ipsum`、NANP 虛構電話 555-01xx。這些是「保留給範例、天生喊著我是假的」
# 的標準 token——agent 不知道作者/聯絡資料時被教用它們當明顯佔位（develop/draft stance），出現在發行
# 交付物＝多半是還沒填的佔位。封閉、機械可判、低誤報（不碰 John Doe 這種有真名歧義的）。WARN 非 ERROR：
# 一份「介紹 RFC 2606」的文件可能合法提及 example.com，留給人判斷。
_RESERVED_EXAMPLE_RE = re.compile(
    r"\bexample\.(?:com|net|org|edu)\b"   # RFC 2606 §3 保留網域（user@example.com 亦含）
    r"|\blorem ipsum\b"                   # 標準佔位文
    r"|\b555-01\d\d\b",                   # NANP 虛構電話段（555-0100..0199）
    re.IGNORECASE,
)
# V10 數字一致：number+unit token 與同行最近的 snake_case 指涉（如 e_stop / task_assign）。
# 封閉單位集抑制誤報；snake_case（至少一個底線）才當 key，排除 timeout/status 等裸詞與 CJK 鄰詞。
_NUM_UNIT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(ms|s|Hz|%)\b")
_SNAKE_RE = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)+")
# V3 只抓 docspec 自己塞的鷹架佔位字（instructions 模板的 {id}/{title}/{order}/{name}）；
# generic `<…>` 在技術散文太氾濫（KE 模板 <vehicle_id>、泛型 <T> 都合法），不再誤殺。
_SCAFFOLD_RE = re.compile(r"\{(?:id|title|order|name)\}")
# V15 撰寫工具／治理模型的後台詞彙（剝程式碼後、ERROR）：交付物是給領域讀者看的，不該洩漏操作
# 撰寫工具的人才懂的內部語。封閉、高信心黑名單——補 V1（只抓 dec-… 之類的 id）的覆蓋缺口。
# 刻意只收無歧義工具詞；領域雙關詞（上游/下游、ADR、裸 森林/鑽石）不機械擋，由 doctrine 節制。
_TOOL_VOCAB_RE = re.compile(
    r"governed-by"                                  # 治理邊（英文工具詞，常裸洩）
    r"|fan-(?:in|out)"                              # fan-in／fan-out 拓樸詞
    r"|factcheck"                                   # 引擎指令名洩進散文
    r"|治理父"                                       # governance parent
    r"|雙父"                                         # 鑽石雙父
    r"|機制節"                                       # 工具結構詞（mechanism-section）
    r"|文件森林"                                      # forest
    r"|[一二三四五六七八九十百\d]+\s*層\s*(?:文件)?森林"   # 「三層森林」「三層文件森林」
    r"|§\s*[一-鿿]+"                        # §回引 / §<中文章節名>（跨節指涉；§+數字＝標準條號不算）
    # Tier-N／層代號：兩側顯式 ASCII token 邊界（非英數/-/_）——識別碼子字串（tier2-doc-cleanup、
    # L2a-xxx）不命中；裸用 Tier-2／L2a（後接空白/CJK/標點）照抓。`\b` 對 `L2a-` 的 a↔- 界成立、
    # 是同型雷，故顯式類把 -、_ 一起排除。IGNORECASE 不影響斷言字母類。
    r"|(?<![A-Za-z0-9_-])Tier-?\d(?![A-Za-z0-9_-])"  # Tier-1/2/3 階層標籤
    r"|(?<![A-Za-z0-9_-])L[123][ab](?![A-Za-z0-9_-])"  # L1a/L2a/L2b/L3b 帶字母後綴層代號
    r"|raise.{0,12}finding",                       # raise 一筆 finding（引擎工作流措辭）
    re.IGNORECASE,
)
# V15 白名單 post-filter（D4）：`§`＋**單一**結構泛字（節/章/條/款/項）且無後續 CJK＝表格欄標
# 「§節」「§章」這類標籤用法，非跨節回引 → 跳過。主 regex 是 greedy（`[一-鿿]+` 吃光後續 CJK），
# 所以「命中恰為 §＋一個泛字」即隱含「其後無 CJK」；「§跨文件清單」（多字）或「§節名」照報。
_SECTION_LABEL_GENERICS = frozenset("節章條款項")


def _is_v15_whitelisted(match: str) -> bool:
    """V15 命中是否落在白名單（§＋單一結構泛字＝欄位標籤，跳過）。"""
    if not match.startswith("§"):
        return False
    cjk = match[1:].strip()
    return len(cjk) == 1 and cjk in _SECTION_LABEL_GENERICS
# V16 規範逃避詞（WARN，同句 應/不得）：封閉 6 詞——最好／儘量／酌情／如有可能／視情況／
# 最大限度——與規範關鍵字（應／不得）同一「偽句」（。！？；ㄧ切界）出現＝作者把該寫成可驗收的
# 規定軟化成無法驗收的裁量。`必要時` 刻意排除：它有合法的 EARS 條件觸發讀法（「必要時 X」＝
# 「當 X 情境發生時」），與其餘 6 詞「本質上就是無結構裁量/程度」不同——ground-truthing 在真實
# 語料中找到 10/10 的 `必要時` 都是合法條件觸發（含兩例正好與 `不得` 同句，本該是設計最強訊號的
# 情境，結果相反）。封閉詞表在真實語料尚未有任何命中（未被驗證有效，也未被證偽）——見 change
# deliverable-cleanliness-normative-escape-hatch design.md。WARN 非 ERROR：命中只代表「像是作者
# 迴避了可驗收的規定」，逃避詞的前提條件仍可能在文件別處被獨立、封閉地定義，那是人的判斷。
_ESCAPE_HATCH_RE = re.compile(r"最好|儘量|酌情|如有可能|視情況|最大限度")
# V17 英文 AI-ism 詞彙（WARN，非阻塞）：封閉 13 組 word-boundary、case-insensitive 觸發詞——LLM 生成
# 英文裡不成比例常見、單獨出現即是語域訊號的字（依 `docspec reference writing-en` 的 Orwell 式選詞
# 紀律；change deliverable-cleanliness-en-ai-isms）。出貨的詞表＝對 6 份已驗收英文交付物
# ground-truthing 後的收窄版，**不是** reference 文件散文清單的照抄：
#   - `robust` 整個排除——已驗收 survey 有 3 個合法 term-of-art 用法（paraphrase-robust、
#     robustness to imperfect retrieval），同中文輪 `進行` 的教訓：太常見的真技術語域詞不進封閉表。
#   - 裸 `leverage` → 只收動詞變位 leverages|leveraged|leveraging（合法名詞用法＋書目真論文標題被證實）。
#   - 裸 `realm` → 只收片語 in the realm of（novel profile 的奇幻 setting 詞是可預見碰撞）。
#   - 裸 `navigate` → 只收 navigate the complexit(y|ies)( of)?（UI 導航／航海領域合法）。
#   - 裸 `underscores` → 只收動詞語境 underscores (the|that|how|why|its)（snake_case 手冊會寫
#     "names use underscores" 名詞用法）。
#   - `utilization` 排除——CPU/link utilization 是標準工程詞彙；只收動詞 utilize/-s/-d/-ing。
# 已知且接受的誤報類（design.md Decision 2）：References 書目引用真論文標題
# 「Leveraging Passage Retrieval…」會中 `leveraging`——WARN 級、人一眼可 dismiss，不為它建
# 書目節偵測、也不為閃它放寬詞表。WARN 非 ERROR：每個觸發詞都有可想見的合法用途，取捨在人。
_AI_ISM_RE = re.compile(
    r"\b(?:"
    r"delve|delves|delved|delving"
    r"|tapestry"
    r"|in the realm of"
    r"|boasts"
    r"|showcases|showcased|showcasing"
    r"|seamless|seamlessly"
    r"|utilize|utilizes|utilized|utilizing"
    r"|testament to"
    r"|a myriad of"
    r"|plethora"
    r"|navigate the complexit(?:y|ies)(?: of)?"
    r"|underscores (?:the|that|how|why|its)"
    r"|leverages|leveraged|leveraging"
    r")\b",
    re.IGNORECASE,
)
# V17 句首 In today's 開場白（throat-clearing opener）：只抓「行首（僅前導空白）或句末標點之後」
# 的 In today's（直引號/彎引號皆收）＋任意接續——中句的 "in today's meeting" 是正常英文、不抓。
# 刻意 case-sensitive（大寫 In）：句首必大寫，且避開 "e.g. in today's …" 這類縮寫句點誤報。
_AI_ISM_OPENER_RE = re.compile(r"(?m)(?:^\s*|[.!?][\"')\]]?\s+)(In today[’']s)\b")
_NORMATIVE_KEYWORD_RE = re.compile(r"應|不得")
# 偽句切分（V16 專用、不共用）：僅供本規則判定「同句」，非通用中文斷句器，不需 material 的
# 表格/條列/程式碼感知——只在乎標點界定的子句。
_PSEUDO_SENTENCE_SPLIT_RE = re.compile(r"[。！？；]")

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


def _split_marker_segments(body: str) -> list[tuple[str | None, str]]:
    """把（已剝 frontmatter 的）交付物本文沿隱形章節標記切段：回傳 [(section-path|None, text)]。

    標記＝render 擁有的行級 `<!-- dspx:section <path> -->` 與 `<!-- dspx:group <path> -->`；
    首個標記之前的 preamble 段 section=None（finding 回退檔案級 where）。刻意不重用
    render.parse_section_bodies：它會丟掉標記後的標題行與 group 段文字——lint 要掃**全部**
    交付物文字（標題裡的洩漏也要抓），只消耗標記行本身。"""
    from dspx.engine.render import GROUP_MARKER_RE, MARKER_RE
    segments: list[tuple[str | None, str]] = []
    current: str | None = None
    buf: list[str] = []
    for line in body.split("\n"):
        m = MARKER_RE.match(line) or GROUP_MARKER_RE.match(line)
        if m:
            segments.append((current, "\n".join(buf)))
            current = m.group(1)
            buf = []
            continue
        buf.append(line)
    segments.append((current, "\n".join(buf)))
    return segments


def _scan_deliverable_text(body: str, where: str, all_ids: set[str]) -> list[Finding]:
    """對一段（已剝註解/程式碼的）交付物文字跑 V1–V4/V12/V13/V15/V16/V17 潔淨規則。

    `where`＝finding 定位（章節級 `docs/<a>/_latest.md § <section>` 或檔案級回退）。
    去重單位＝呼叫者給的這段文字（章節切段後＝每章節去重：同 token 洩漏兩章節＝兩筆各自可定位）。"""
    findings: list[Finding] = []
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
                                "apply (rewrite mode) emits these as a stop-and-flag marker; never ship one"))
    for m in dict.fromkeys(_RESERVED_EXAMPLE_RE.findall(body)):
        findings.append(Finding("V13", WARN, where,
                                f"reserved example/placeholder token shipped \"{m.strip()}\" -- "
                                "RFC 2606 example.* domains / lorem ipsum / 555-01xx signal "
                                "unfilled placeholder data (e.g. an author/contact never filled in)"))
    for m in dict.fromkeys(_TOOL_VOCAB_RE.findall(body)):
        if _is_v15_whitelisted(m):
            continue
        findings.append(Finding("V15", ERROR, where,
                                f"leaked authoring-tool/governance vocabulary \"{m.strip()}\" -- "
                                "the deliverable is for domain readers, not for operators of the "
                                "authoring tool; express document relationships in domain language: "
                                "cross-document, name the document (\"per 《…》\", \"see 《…》\"); "
                                "same-document, quote the target section's human title "
                                "(「詳見「〈章節標題〉」一節」), or for a §number reference bind a "
                                "cross-reference anchor (filing rule crossref-by-anchor, render-"
                                "injected); never a hand-typed § + number or a backstage id. "
                                "Never ship backstage terms (forest / governed-by / governance parent "
                                "/ Tier-N / L2a / fan-in / module-section / factcheck / raise a "
                                "finding / §back-ref)"))
    for m in dict.fromkeys(_AI_ISM_RE.findall(body)):
        findings.append(Finding("V17", WARN, where,
                                f"English AI-ism register tell \"{m.strip()}\" -- vocabulary "
                                "disproportionately common in LLM-generated English (see "
                                "`docspec reference writing-en`); prefer a plainer, more "
                                "specific word (advisory; a cited title or genuine term of "
                                "art may be legitimate -- the call is the author's)"))
    for m in dict.fromkeys(_AI_ISM_OPENER_RE.findall(body)):
        findings.append(Finding("V17", WARN, where,
                                f"English AI-ism opener \"{m}\" -- sentence-initial "
                                "\"In today's ...\" is throat-clearing (see `docspec reference "
                                "writing-en`); start with the actual claim instead"))
    seen_escape_hatch: set[str] = set()
    for sentence in _PSEUDO_SENTENCE_SPLIT_RE.split(body):
        if not _NORMATIVE_KEYWORD_RE.search(sentence):
            continue
        for m in _ESCAPE_HATCH_RE.findall(sentence):
            if m in seen_escape_hatch:
                continue
            seen_escape_hatch.add(m)
            findings.append(Finding("V16", WARN, where,
                                    f"normative escape-hatch hedge word \"{m}\" in the same sentence "
                                    "as a normative keyword (應/不得) -- looks like an unconditional, "
                                    "testable requirement was softened into an unverifiable one; "
                                    "either state a closed condition or drop the hedge"))
    return findings


def _doc_section_segments(text: str) -> list[tuple[str | None, str]]:
    """把交付物全文以 span 服務切成 [(section|None, masked_segment)]：章節歸屬 + code-strip
    單一權威（`mask_non_prose` 等長遮蔽 html_comment/fence/inline_code/marker）。

    取代舊 `_split_marker_segments`＋三條 `sub("")`：fence 狀態機優先 ⇒ fenced code 內的
    字面 `dspx:section` 行不再斬斷章節（D7 刻意行為修正）。遮蔽面 kinds 子集＝對齊舊剝除
    面（不剝 image path／URL，維持 V13 對圖 path 內 example.* 的既有覆蓋＝遷移行為鎖）。"""
    from dspx.engine.spans import (FENCE, HTML_COMMENT, INLINE_CODE, MARKER,
                            classify_deliverable, mask_non_prose)
    masked = mask_non_prose(text, kinds={HTML_COMMENT, FENCE, INLINE_CODE, MARKER})
    segments: list[tuple[str | None, str]] = []
    for sp in classify_deliverable(text):
        # 相鄰同章節併段（一章節一段、逐段去重＝與舊每章節去重同義）
        if segments and segments[-1][0] == sp.section:
            prev_sec, prev_txt = segments[-1]
            segments[-1] = (prev_sec, prev_txt + masked[sp.start:sp.end])
        else:
            segments.append((sp.section, masked[sp.start:sp.end]))
    return segments


def _lint_docs(layout: Layout, articles: list[str], all_ids: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    for article in articles:
        path = layout.docs_latest(article)
        if not path.is_file():
            continue
        file_where = f"docs/{article}/_latest.md"
        # 章節定位＋code-strip 走 span 服務（單一權威）：finding 的 where 指名含命中的章節
        # （`docs/<a>/_latest.md § <section>`）；首個標記前的 preamble／整份無標記＝檔案級回退。
        for section, segment in _doc_section_segments(path.read_text(encoding="utf-8")):
            where = f"{file_where} § {section}" if section else file_where
            findings.extend(_scan_deliverable_text(segment, where, all_ids))
    return findings


def _lint_punctuation(layout: Layout, articles: list[str]) -> list[Finding]:
    """V18 散文殘留半形標點（WARN、非阻塞）：散文面 span 內 `docspec normalize` 會轉換的
    半形標點 → 指向指令、不教手改。判定與 normalize 共用 `spans.propose_conversions`
    （單一權威、報必可修的閉環）；byte-exact span 與識別碼尾隨標點天然不觸發。

    每章節聚一筆 WARN（`where` 帶章節定位、與 V1–V17 同格式），避免逐字元洗版。"""
    from dspx.engine.spans import propose_conversions
    findings: list[Finding] = []
    for article in articles:
        path = layout.docs_latest(article)
        if not path.is_file():
            continue
        file_where = f"docs/{article}/_latest.md"
        # 依原文序聚章節（dict 保插入序）：同章節 N 筆殘留 → 一筆 WARN、指向跑一次 normalize。
        by_section: dict[str | None, int] = {}
        for c in propose_conversions(path.read_text(encoding="utf-8")):
            by_section[c.section] = by_section.get(c.section, 0) + 1
        for section, n in by_section.items():
            where = f"{file_where} § {section}" if section else file_where
            findings.append(Finding("V18", WARN, where,
                f"{n} half-width punctuation mark(s) in prose that would normalize to full-width "
                f"-- run `docspec normalize {article}` (deterministic; do not hand-edit)"))
    return findings


# ── V21 散文字面章號（deliverable-cleanliness／prose-crossref-anchors，P1b）──────
# 散文回引寫死章號（`§9.2`／`第 6 章`／`見 §12`）＝重排即漂（真語料實證：兩輪 SC 重構後
# 94–107 處失錨）。改綁穩定錨（`<!--@id-->`，號碼 render 注入）後號碼永遠算得出。此規則 WARN
# 指向改綁錨。**只抓未綁錨的字面**：render 注入的錨標籤（`<!--@id-->§6.5<!--@-->`）在掃描前
# 先以 `normalize_prose_anchors` 縮回裸綁定＝§6.5 消失、不誤報引擎自產。
# 字面章號形：§＋數字（半/全形，含小數）／`第 N 章`／`第 N 節`（N＝阿拉伯/全形/中文數字）。
_LITERAL_CHAPTER_RE = re.compile(
    r"§\s*[0-9０-９]+(?:[.．][0-9０-９]+)*"                       # §9 / §9.2 / § 12
    r"|第\s*[0-9０-９一二三四五六七八九十百]+\s*[章節]"          # 第 6 章 / 第三節
    r"|(?:Annex|Appendix)\s+[A-Z]\b"                          # Annex A / Appendix B（英文附錄交叉引用）
    r"|附錄\s*[A-Za-z0-9０-９]"                                # 附錄 A / 附錄1（中文附錄交叉引用）
)
# 外部標準條號白名單（D4）：`ISO 13849-1 §4.2` 指外部標準、非內部節，不誤報。判定＝章號命中
# 的**同一子句左窗**內出現標準代號（ISO/IEC/EN/GB…）。ground-truth 台中港語料校準零 FP。
_STANDARD_DESIGNATOR_RE = re.compile(
    r"(?:ISO(?:/IEC|/TS|/TR)?|IEC|IEEE|EN|DIN|ANSI|JIS|CNS|GB(?:/T)?|BS|UL|NFPA|"
    r"ASME|ASTM|API|SAE|RFC|MIL(?:-STD)?)\b")
# 子句硬界：句末標點＋換行（散文子句界）。表格分隔 `|` 另以「至多跨一格」的軟界處理（見下）。
_CLAUSE_BOUNDARY_RE = re.compile(r"[。！？；\n]")
_PIPE_RE = re.compile(r"\|")


def _is_external_standard_ref(segment: str, hit_start: int) -> bool:
    """章號命中是否為外部標準條號（左窗同子句內見標準代號＝是，跳過）。

    左窗＝命中位置往回 40 字，先在最近硬子句界（。！？；換行）截斷。表格 `|` 分隔以「至多跨
    一格」處理：允許條號落在標準名格的**相鄰描述格**仍豁免（`| IEC 61508-2 | …(§7.4.2.3) |`＝
    外部標準的條款、正當豁免），但與任何標準名相距**兩格以上**的 `§N`（`| ISO 12100 | … |
    依 §3 …`＝本表指涉他文件內部節）不豁免＝WARN。ground-truth：standards-applicability-matrix
    的 `依 §3` 曾被過度豁免＝漏報，而 `(§7.4.2.3)`／`(§11.2)` 是真外部條號、不可誤報。"""
    window_start = max(0, hit_start - 40)
    left = segment[window_start:hit_start]
    hard = None
    for hard in _CLAUSE_BOUNDARY_RE.finditer(left):
        pass
    if hard is not None:
        left = left[hard.end():]          # 散文硬子句界：只看命中所在子句
    pipes = [pm.start() for pm in _PIPE_RE.finditer(left)]
    if len(pipes) >= 2:
        left = left[pipes[-2] + 1:]       # 表格：至多回看一格（保留倒數第二個 `|` 之後）
    return _STANDARD_DESIGNATOR_RE.search(left) is not None


def _lint_prose_chapter_refs(layout: Layout, articles: list[str]) -> list[Finding]:
    """V21 散文字面章號（WARN、非阻塞）：散文 span 內未綁錨的字面章號 → 指向改綁穩定錨。

    掃描前先 `normalize_prose_anchors` 縮掉 render 注入的錨標籤（§6.5＝引擎自產、不報）；
    外部標準條號（`ISO … §4.2`）經左窗代號判定跳過。每章節聚一筆 WARN（帶章節定位）。"""
    from dspx.engine.render import normalize_prose_anchors
    from dspx.engine.spans import (FENCE, HEADING, HTML_COMMENT, INLINE_CODE, MARKER,
                            classify_deliverable, mask_non_prose)
    findings: list[Finding] = []
    for article in articles:
        path = layout.docs_latest(article)
        if not path.is_file():
            continue
        file_where = f"docs/{article}/_latest.md"
        # 先縮掉錨注入的號碼（引擎自產、非未綁錨字面）→ 再遮 code/comment/marker **＋ HEADING**。
        # HEADING 入遮蔽面（有別於 V1–V17 的 `_doc_section_segments`）：render 推導的附錄標題
        # `## 附錄 A 名稱` 是正當標題、非交叉引用——不遮會被新增的 `附錄 A` pattern 誤報。
        normalized = normalize_prose_anchors(path.read_text(encoding="utf-8"))
        masked = mask_non_prose(
            normalized, kinds={HTML_COMMENT, FENCE, INLINE_CODE, MARKER, HEADING})
        segments: list[tuple[str | None, str]] = []
        for sp in classify_deliverable(normalized):
            if segments and segments[-1][0] == sp.section:
                segments[-1] = (sp.section, segments[-1][1] + masked[sp.start:sp.end])
            else:
                segments.append((sp.section, masked[sp.start:sp.end]))
        for section, segment in segments:
            hits = [m for m in _LITERAL_CHAPTER_RE.finditer(segment)
                    if not _is_external_standard_ref(segment, m.start())]
            if not hits:
                continue
            where = f"{file_where} § {section}" if section else file_where
            sample = hits[0].group(0).strip()
            findings.append(Finding("V21", WARN, where,
                f"{len(hits)} un-anchored literal chapter reference(s) in prose "
                f"(e.g. \"{sample}\") -- literal section numbers drift on any reorder; bind a "
                f"stable cross-reference anchor to the target section's id instead (the number "
                f"is then render-injected and never dangles). External-standard clause citations "
                f"(e.g. ISO 13849-1 §4.2) are exempt."))
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
        from dspx.engine.spans import (FENCE, HTML_COMMENT, INLINE_CODE, MARKER,
                                mask_non_prose)
        body = mask_non_prose(path.read_text(encoding="utf-8"),
                              kinds={HTML_COMMENT, FENCE, INLINE_CODE, MARKER})
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
    # backend-neutral：優先 leaf.material（store/散檔皆由此供給）、退回開檔（防禦）。
    text = leaf.material
    if text is None:
        path = leaf.dir / "material.md"
        if not path.is_file():
            return []
        text = path.read_text(encoding="utf-8")
    findings: list[Finding] = []
    where = f"{leaf.section}/material.md"
    prose_run = 0          # V6：連續純文字行（非條列/引文/表格/標題/空白/程式碼）計數
    prose_start = 0
    in_code = False        # 圍欄式程式碼區塊內＝結構化內容（draft 要逐字渲染），非散文
    for lineno, line in enumerate(text.splitlines(), 1):
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
    from dspx.engine.render import parse_section_bodies
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
    findings.extend(_lint_punctuation(layout, articles))
    findings.extend(_lint_prose_chapter_refs(layout, articles))
    for leaf in leaves:
        findings.extend(_lint_material(leaf))
        findings.extend(_lint_realizes(leaf, index))
    findings.extend(_lint_glossary(layout, articles))
    findings.extend(_lint_export_safety(layout, articles))
    findings.extend(_lint_drift(layout, leaves))
    findings.extend(_lint_brief_dup(leaves))
    findings.extend(_lint_title_prefix(layout, leaves))
    findings.extend(_lint_orphan_assets(layout, leaves))
    findings.extend(_lint_freeze(layout))
    findings.extend(_lint_roadmap(layout, leaves))
    findings.extend(_lint_audit_findings(layout, leaves))
    return findings


def _lint_orphan_assets(layout: Layout, leaves: list[Leaf]) -> list[Finding]:
    """V14 孤兒圖檔（WARN）：**交付側 `docs/assets/`**（Model A：圖住交付側）有可嵌入圖檔
    （.png/.svg/.jpg…），但該文件交付物完全沒引用它的 basename ＝渲了卻忘了嵌入（或舊圖已換、殘留）。
    `.drawio` 源檔不算（docs_asset_files 只收可嵌入圖格式、不含 .drawio）。WARN 非阻塞。

    孤兒判定跟著資產夾的共用範圍走：
    - flat layout：`docs/assets/` 是**全專案共用**——孤兒＝「沒有任何文件引用」，故取
      全部 article 引用的**聯集**、對共用夾**單趟**掃（逐 article 掃會把只被 A 引用的圖
      對 B、C…各誤報一次＝恆誤報且重複 N 次）。
    - per-article layout：各 article 資產夾獨立，維持逐 article 比對。"""
    from dspx.engine.render import find_image_refs
    from dspx.engine.model import docs_asset_files
    findings: list[Finding] = []
    articles = sorted({lf.article for lf in leaves})

    def _refs(article: str) -> set[str]:
        path = layout.docs_latest(article)
        if not path.is_file():
            return set()
        return {ref.rsplit("/", 1)[-1] for ref in find_image_refs(path.read_text(encoding="utf-8"))}

    if layout.docs_layout == "flat":
        union: set[str] = set()
        for article in articles:
            union |= _refs(article)
        for asset in docs_asset_files(layout, None):
            if asset.name not in union:
                findings.append(Finding(
                    "V14", WARN, f"docs/assets/{asset.name}",
                    "image asset is not referenced by any deliverable "
                    "(rendered but never embedded, or a stale leftover)"))
        return findings

    for article in articles:
        refs = _refs(article)
        for asset in docs_asset_files(layout, article):
            if asset.name not in refs:
                findings.append(Finding(
                    "V14", WARN, f"docs/assets/{asset.name}",
                    "image asset is not referenced by the deliverable "
                    "(rendered but never embedded, or a stale leftover)"))
    return findings


def _lint_freeze(layout: Layout) -> list[Finding]:
    """V11 凍結區完整性：archive/ 內已發行快照被竄改/刪除/未登記 → ERROR（歷史不可變）。"""
    from dspx.reports import freeze
    findings: list[Finding] = []
    for rel, problem in freeze.verify(layout.planning_home, layout.project_root, layout.docs_dir):
        detail = f"frozen area (archive/) {problem} -- published versions are immutable"
        if problem.startswith("not registered"):
            # 「未登記」死路變岔路口：附遷移指路的兩條正路（刪除/竄改訊息不加）
            detail += (" (pre-docspec legacy versions: run 'docspec publish register-legacy "
                       "<dir>', or keep them outside archive/ (e.g. docs/legacy/))")
        findings.append(Finding("V11", ERROR, rel, detail))
    return findings


def _lint_glossary(layout, articles: list[str]) -> list[Finding]:
    """術語一致性提醒（皆 WARN；精確同物異名判定→audit）。
    Vg1 同物異名：docs 出現某詞的 aliases_forbidden → 提醒改正名。
       比對前先**遮蔽正名**：把 body 中該 term 的 canonical 每處出現換成等長佔位字元，
       再比別名——「別名⊂正名」（alias 行控 ⊂ canonical 行控中心）時，寫對正名不再恆誤報；
       裸用別名（未被 canonical 覆蓋）仍抓得到。
    Vg2 縮寫裸奔：module 桶的 code（如 RMM）在 docs 散文出現 → 提醒中文化。
    掃描文字剝 HTML 註解＋fenced/inline code（與 V1–V4 同前處理）：code 內的別名 token
    是內容（欄位名/範例），不是散文用詞。
    """
    from dspx.engine.glossary import load_glossary
    terms = load_glossary(layout)
    if not terms:
        return []
    findings: list[Finding] = []
    for article in articles:
        path = layout.docs_latest(article)
        if not path.is_file():
            continue
        from dspx.engine.spans import (FENCE, HTML_COMMENT, INLINE_CODE, MARKER,
                                mask_non_prose)
        body = mask_non_prose(path.read_text(encoding="utf-8"),
                              kinds={HTML_COMMENT, FENCE, INLINE_CODE, MARKER})
        where = f"docs/{article}/_latest.md"
        for t in terms:
            canonical = t.get("canonical", "")
            # 遮蔽法：canonical 出現處換等長 \x00 佔位（等長保位移穩定、\x00 不與任何別名相交）
            masked = (body.replace(str(canonical), "\x00" * len(str(canonical)))
                      if canonical else body)
            for alias in (t.get("aliases_forbidden") or []):
                if alias and str(alias) in masked:
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


_ROADMAP_OPEN_MAX = 7  # per-doc entry 上限：超過＝backlog 變筆記傾倒場（軟提醒）
_FINDING_ID_IN_PROSE_RE = re.compile(r"\bF\d+\b")


def _lint_roadmap(layout: Layout, leaves: list[Leaf]) -> list[Finding]:
    """roadmap 軟提醒（皆 WARN、非阻塞；「該不該做」是 audit，這裡只抓機械徵兆）。統無狀態模型
    後：在檔＝待辦，故 Vr1 直接數全部 entry（不再篩 status:open）；舊 Vr2（status:doing 無
    develop.md）/舊 Vr3（status:done 缺 done-to）隨欄位刪除一起退場，同代號改指新規則：
    Vr1 per-doc entry 數過多（>7）→ backlog 淪為筆記傾倒場。
    Vr2 含 promoted-to 卻仍帶實質內容（超出 id/title/promoted-to）→ 搬家沒搬乾淨。
    Vr3 entry 的 what 散文引用一條仍全文開放的 audit finding id → 雙帳鏡像，該晉升搬家、非複製。
    """
    from dspx.reports import audit as audit_mod
    from dspx.reports import roadmap as roadmap_mod

    findings: list[Finding] = []

    # Vr1：每個 distinct article 的 per-doc roadmap entry 計數（全部 entry＝全部待辦）。
    seen_articles: list[str] = []
    for leaf in leaves:
        if leaf.article and leaf.article not in seen_articles:
            seen_articles.append(leaf.article)
    for art in seen_articles:
        entries = roadmap_mod.load_doc_roadmap(layout.section_dir(art), art)
        if len(entries) > _ROADMAP_OPEN_MAX:
            findings.append(Finding("Vr1", WARN, f"corpus/{art}/roadmap.yaml",
                f"{len(entries)} entries (>{_ROADMAP_OPEN_MAX}) -- don't let the backlog become a "
                "notes dump; split, start, promote, or `docspec roadmap done` some"))

    # 開放且仍帶全文的 finding（供 Vr3 鏡像偵測）。
    open_full_findings: dict[str, dict] = {}
    for f in audit_mod.all_findings(layout, leaves):
        fid = f.get("id")
        if fid and f.get("status") == "open" and f.get("finding") and not f.get("promoted-to"):
            open_full_findings[str(fid)] = f

    for e in roadmap_mod.all_entries(layout, leaves):
        rid = e.get("id")
        store = e.get("_store", "roadmap")
        where = f"{store}/roadmap.yaml"

        # Vr2：promoted-to 存在卻超出 id/title/promoted-to（搬家不複製沒落實）。
        if e.get("promoted-to"):
            extra = sorted(set(e) - {"id", "title", "promoted-to", "_store"})
            if extra:
                findings.append(Finding("Vr2", WARN, where,
                    f"entry \"{rid}\" carries promoted-to but still has {extra} -- move, don't "
                    "copy: collapse to id/title/promoted-to only"))

        # Vr3：what 散文引用一條仍全文開放的 finding id。
        what = str(e.get("what") or "")
        for m in _FINDING_ID_IN_PROSE_RE.finditer(what):
            fid = m.group(0)
            if fid in open_full_findings:
                findings.append(Finding("Vr3", WARN, where,
                    f"entry \"{rid}\" what mirrors open audit finding {fid} in prose -- "
                    "double-ledger; promote (move, don't copy) instead of duplicating"))
                break
    return findings


_LINE_ANCHOR_PROSE_RE = re.compile(r"(?<![A-Za-z0-9])L\d+(?:/\d+)*(?![A-Za-z0-9])")


def _lint_audit_findings(layout: Layout, leaves: list[Leaf]) -> list[Finding]:
    """audit 軟提醒（皆 WARN、非阻塞）：
    Va1 finding 含 promoted-to 卻仍帶實質 finding 全文 → 搬家沒搬乾淨（一事一帳）。
    Va2 finding 散文（`finding` 欄）殘留行號形錨點（`L123`/`L123/124`）→ render 後座標會漂，
        改綁穩定節路徑／§slug（targets 裡的行號錨點是 check ERROR，這裡管散文內文的軟提醒）。
    """
    from dspx.reports import audit as audit_mod

    findings: list[Finding] = []
    for f in audit_mod.all_findings(layout, leaves):
        fid = f.get("id")
        store = f.get("_store", "audit")
        where = f"{store}/audit.yaml"
        body = str(f.get("finding") or "")

        if f.get("promoted-to") and body.strip():
            findings.append(Finding("Va1", WARN, where,
                f"finding \"{fid}\" carries promoted-to but still has a full finding body -- "
                "move, don't copy: collapse to id/face/severity/status/promoted-to"))

        if body and _LINE_ANCHOR_PROSE_RE.search(body):
            findings.append(Finding("Va2", WARN, where,
                f"finding \"{fid}\" prose contains a line-number-shaped anchor (e.g. L###) -- "
                "coordinates rot on re-render; bind a stable section identifier or §<slug> instead"))
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
        from dspx.engine.spans import (FENCE, HTML_COMMENT, INLINE_CODE, MARKER,
                                mask_non_prose)
        raw = path.read_text(encoding="utf-8")
        # 標題 slug 集（連結解析基準）：對遮蔽 fence/comment/marker 的文字取標題——fence 內的
        # `#` 註解行不再被誤當標題（span 服務為底；遷移行為鎖對真實語料逐 byte 驗過無差異）。
        body = mask_non_prose(raw, kinds={HTML_COMMENT, FENCE, MARKER})
        slugs = {_slugify(m.group(1)) for line in body.splitlines()
                 if (m := _HEADING_RE.match(line))}
        # 連結/指令掃描在遮蔽 code（fence＋inline）後做：code 裡的 `](#x)`、@import 是內容範例
        scan = mask_non_prose(raw, kinds={HTML_COMMENT, FENCE, INLINE_CODE, MARKER})
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
        # Ve3 掃保留 fence 的文字（這些記法本身就是 fence，不可遮）：非 backend-neutral 圖記法。
        ve3_src = mask_non_prose(raw, kinds={HTML_COMMENT, MARKER})
        if _MERMAID_FENCE_RE.search(ve3_src):
            findings.append(Finding("Ve3", WARN, where,
                "contains a ```mermaid diagram -- mermaid does not render in the controlled toolchain (it ships as a placeholder box); author the diagram as an embedded image instead (the dspx-diagram subagent renders drawio to a raster PNG, embedded with `![](assets/...)`)"))
        if _RAW_LATEX_FENCE_RE.search(ve3_src):
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


# ── V19 brief 逐字複述祖先 / V20 title 章號前綴（contract-slimming D6）──────────
# 兩者皆 WARN、非阻塞（絕不影響 publish 閘）。下列判定原語是 lint 與 `docspec store tidy` 的
# **單一權威**——tidy 刪欄／剝前綴時 import 同一組常數/函式，判定不漂移。

# brief 差異制的可繼承子欄（concept.brief 下）。tidy 逐字複述剝除也走這份清單。
BRIEF_FIELDS = ("audience", "depth", "breadth", "forbidden", "layout", "kind")


def _brief_of(leaf: Leaf) -> dict:
    """leaf.concept.brief（保證回 dict；缺/型別錯＝空 dict）。"""
    brief = (leaf.concept or {}).get("brief") if leaf.concept else None
    return brief if isinstance(brief, dict) else {}


def _brief_field_present(val: object) -> bool:
    """該 brief 欄是否「有提供值」（供 nearest-ancestor 搜尋停在第一個非空祖先）。"""
    if isinstance(val, str):
        return bool(val.strip())
    if isinstance(val, list):
        return len(val) > 0
    return val is not None


def _brief_field_equal(child_val: object, anc_val: object) -> bool:
    """child 與祖先值是否 byte 等值（唯一觸發條件）：字串 strip 後逐 byte 比、list 逐元素
    結構等值（字串元素 strip）。改寫過的特化（哪怕一字之差）永不等值＝永不誤報。"""
    if isinstance(child_val, str) and isinstance(anc_val, str):
        return child_val.strip() == anc_val.strip()
    if isinstance(child_val, list) and isinstance(anc_val, list):
        def _norm(xs: list) -> list:
            return [x.strip() if isinstance(x, str) else x for x in xs]
        return _norm(child_val) == _norm(anc_val)
    return child_val == anc_val


def brief_dup_fields(leaf: Leaf, by_section: dict, concept_by_id: dict) -> list[str]:
    """回傳該 leaf 的 brief 中「與最近提供該欄的祖先值 byte 等值」的欄名清單。

    最近祖先＝沿 aperture 同一條祖先鏈（`model.ancestor_leaves`，路徑父鏈優先、淺→深）第一個
    對該欄有提供非空值者。lint（V19）與 `docspec store tidy`（刪這些欄改繼承）共用此判定。"""
    from dspx.engine.model import ancestor_leaves
    brief = _brief_of(leaf)
    if not brief:
        return []
    ancestors = ancestor_leaves(leaf.section, by_section, concept_by_id)
    dup: list[str] = []
    for fld in BRIEF_FIELDS:
        child_val = brief.get(fld)
        if not _brief_field_present(child_val):
            continue
        for anc, _is_governed in ancestors:          # nearest-first
            anc_val = _brief_of(anc).get(fld)
            if not _brief_field_present(anc_val):
                continue
            if _brief_field_equal(child_val, anc_val):
                dup.append(fld)
            break                                    # 停在最近提供該欄的祖先
    return dup


def _lint_brief_dup(leaves: list[Leaf]) -> list[Finding]:
    """V19：brief 子欄與最近祖先 byte 等值 → WARN（指向刪欄改繼承／`docspec store tidy`）。"""
    from dspx.engine.model import _concept_by_id
    by_section = {lf.section: lf for lf in leaves}
    concept_by_id = _concept_by_id(by_section)
    findings: list[Finding] = []
    for leaf in leaves:
        for fld in brief_dup_fields(leaf, by_section, concept_by_id):
            findings.append(Finding("V19", WARN, f"{leaf.section}/concept.yaml",
                f"brief.{fld} is byte-identical to the value inherited from the nearest ancestor "
                f"that supplies it -- delete the field to inherit it (batch cleanup: `docspec store tidy`)"))
    return findings


# title 大綱編號前綴（章號 render 推導、title 欄不該手寫）。tidy 只剝阿拉伯式（D7），故兩式分開。
#   arabic / 全形數字 / CJK 頓號-句號式：`6.` `6.1` `６．` `6、` `6。`
#   —— 數字後必接 `[.、．。]` 之一，故 `5G` 這類「數字＋字母」的名稱本體不誤觸。
_TITLE_ARABIC_PREFIX_RE = re.compile(r"^\s*[0-9０-９]+[.、．。]")
#   附錄字母式：`A.`（大寫字母＋點）或 `附錄 A`／`附錄A`／`附錄 1`（附錄＋編號字元）。
_TITLE_APPENDIX_PREFIX_RE = re.compile(r"^\s*(?:[A-Z]\.|附錄\s*[A-Za-z0-9０-９])")


def title_numbering_prefix(title: object) -> str | None:
    """回傳 title 開頭命中的大綱編號前綴字串（無則 None）。

    lint（V20）與 `docspec store tidy` 剝除共用此判定——tidy 僅剝 arabic 式（`_TITLE_ARABIC_PREFIX_RE`，
    見 D7：附錄型 v1 不動）。`5G 網路架構` 型（數字後接字母、非編號標點）刻意不觸發。"""
    if not isinstance(title, str):
        return None
    m = _TITLE_ARABIC_PREFIX_RE.match(title) or _TITLE_APPENDIX_PREFIX_RE.match(title)
    return m.group(0) if m else None


def _lint_title_prefix(layout: Layout, leaves: list[Leaf]) -> list[Finding]:
    """V20：concept / group 記錄的 title 以大綱編號起頭 → WARN（指向 `docspec store tidy`）。
    ★store-only：group title 由 store 記錄枚舉（非散檔 group.yaml）。"""
    from dspx.engine import store as _store
    findings: list[Finding] = []

    def _flag(where: str, title: str, pref: str) -> None:
        findings.append(Finding("V20", WARN, where,
            f"title \"{title}\" begins with an outline-numbering prefix \"{pref.strip()}\" -- "
            f"numbering is render-derived; drop the prefix from the title (batch cleanup: `docspec store tidy`)"))

    for leaf in leaves:
        title = (leaf.concept or {}).get("title")
        pref = title_numbering_prefix(title)
        if pref:
            _flag(f"{leaf.section}/concept.yaml", title, pref)

    for art in _store.store_articles(layout):
        art_obj = _store.cached_article(layout, art)
        for rec in (art_obj.group_records() if art_obj is not None else []):
            title = (rec.group or {}).get("title")
            pref = title_numbering_prefix(title)
            if pref:
                _flag(f"{rec.path}/group.yaml", title, pref)
    return findings
