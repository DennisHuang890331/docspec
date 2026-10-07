"""artispec init — 一鍵建 docspec 專案骨架（在 CWD 下建 docspec/ planning home）。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from dspx.engine.config import CONFIG_FILE_NAME
from dspx.engine.layout import CORPUS_DIR_NAME, PLANNING_DIR_NAME

NAME = "init"
HELP = "create an ArtiSpec project skeleton in the current directory (config.yaml + corpus/)"

_CONFIG_TEMPLATE = """\
# docspec project config. Missing keys fall back to defaults.
schema: section-driven        # built-in data model (section five-file)
language: {lang}              # interaction / deliverable language (e.g. zh-TW, en)
purpose:                      # overall goal of the whole forest/project, a sentence or two (shown as develop kickoff context)
# docs_layout: flat           # flat (<article>_latest.md + archive/) | per-article (one folder per article)
# audit:                      # audit red-team core attack faces + regulatory packs
#   core: [logic, completeness, clarity, discipline, consistency]
#   packs: {}
# autonomy:                   # publish locked to human (irreversible trigger stays with the human)
#   publish: human
"""

# 寫作守則：全文件共用一份「風格」（盲渲染下唯一的跨節連貫載體）。draft/edit 由 instructions 注入。
# 語言（套 concept.brief 慣例「鍵英文/值專案語言」）：通用骨架＝英文一份（語言中性 doctrine，
# 英文寫照樣產任何語言交付）；語言特定的東西（禁開場語、需求關鍵字字典、交付語言）留到 develop
# 時用「交付語言」填進「Project conventions」區——故交付語言是 develop 決策、不在 init 定。
_WRITING_GUIDE_BACKBONE = """\
# Writing guide

> Shared by the whole document. `apply` (rewrite mode) blind-renders each section against THIS file;
> `apply` (align mode) checks the whole document against it. Coherence comes from these rules, not from peeking at
> sibling sections.
>
> **SCOPE FENCE — writing doctrine only.** Term identity → `glossary.yaml`. Versioning / file
> layout / project ops → `config.yaml` & the publish workflow. If a rule isn't about how the
> prose reads, it's in the wrong file. If this file passes ~1 screen, the rule is probably
> section-specific and belongs in that section's `concept.brief`, not here.
>
> The backbone below is **canonical English** (language-neutral doctrine). Fill **Project
> conventions** in your **deliverable language** during `develop`. Engineering teams are the
> default tool users; each deliverable serves its recorded audience. Existing project conventions
> and explicit audience requirements take priority and may override these defaults in place.

## General discipline (backbone — keep)
1. **Constrained generation**: use only the projected aperture content. Never invent facts/
   numbers/rationale; mark anything missing as `[TBD]`.
2. **Render independently**: do not guess other sections' prose or invent a neighbour's content.
   Stable anchors to known concept ids may provide navigation; never hand-type drifting chapter
   numbers. Avoid vague "as above" or "the next section" in blind writing.
3. **Task and kind first**: make the purpose and usable result clear for the recorded audience.
   how-to: preconditions, ordered steps, expected result and failure handling; reference: fields,
   interfaces and limits for lookup; tutorial: learning steps; explain: reasons and trade-offs.
   Use the existing `brief.kind`; do not force an argument chain or every type into every document.
4. **Useful orientation, no filler**: keep necessary scope, preconditions and navigation that help
   the reader choose or perform a task. Avoid empty introductions and reciting the brief as boilerplate.
   Lead on the task, fact or decision; do not force every step to open with an argumentative conclusion.
5. **Choose readable form**: use steps for sequences, lists for parallel items, tables for useful
   comparisons or lookup, and prose for explanations and trade-offs. Honor `brief.layout`;
   do not force every rule or condition into a table.
6. **Honor the brief**: don't exceed `breadth`, don't go below `depth`, never touch `forbidden`.
7. **Normative force uses keywords** (see the deliverable-language dictionary below).
8. **Clean**: the deliverable carries no id / internal code / anchors (`{#…}`) / draft markers,
   **and no authoring-tool / governance vocabulary** — it is for domain readers, not for operators
   of this tool. Never surface backstage words (forest / governed-by / governance parent /
   Tier-1·2·3 / L2a / diamond fan-in / module-section / factcheck / raise a finding).
   Express document relationships in domain language instead: name the document (《…》), write "per
   the principles in 《…》" or "see 《…》", and "the sections of this spec" — not "module-sections".
   For a cross-reference to another SECTION (same document or internal cross-document), write the
   stable cross-reference **anchor** where the number belongs — `<!--@<target-concept-id>--><!--@-->`
   — and let `render` inject the live `§N` between the two invisible comments (re-derived every
   render, so it never dangles). The **anchor-injected `§N` IS the sanctioned form**; what is banned
   is a **hand-typed** chapter number / literal `§N` / 第 N 章 (a hand-typed number drifts on any
   reorder — the real corpus lost 94–107 cross-refs to exactly this). So write 「（詳見<錨>）」/
   "see §N (via the anchor)", never a number you typed yourself. External-standard clause citations
   (ISO 13849-1 §4.2) stay literal — the anchor is for internal references only.
9. **Density**: one idea per paragraph; use short, connected paragraphs as the task needs.
10. **No metaphors / nicknames** → state responsibilities plainly.
11. **Direct language**: use active verbs and precise terms. Instructions can address the reader;
    normative requirements need explicit actors. Keep an appropriate, consistent register.
12. **Read like a native** → write as a fluent native writer of the deliverable language would
    phrase it: natural idiom, varied sentence openings and length. NEVER calque English structure
    word-for-word — formal register is not stiff translationese. This matters most when the
    deliverable language is not English; the rules above follow the document's purpose, not a license to
    write translated-sounding prose. Chinese-translationese and AI-sounding-English are two
    different diseases with two different fixes, not the same rule in two languages — the naturalness
    bullet below is pre-seeded for zh-TW/en from `artispec reference writing-<lang>`; for any other
    language run that command yourself (or `artispec reference` for the index) and write the
    language's own defect list here — don't guess at what "sounds native" from this rule's name alone.

"""

# 自然度 bullet 種子＝docspec reference writing-{zh,en} 的濃縮版（動作句、非長篇論證+出處；論證/出處
# 留給 reference 指令查）。只有「語言本身」的通用規則（不分文類都成立）才進這裡；文類特有的東西
# （附錄A 規範詞/EARS、特定領域禁詞）留給 develop 依實際文類另外補——這條線是「通用 vs 文類特化」，
# 不是舊版「10 檔 genre×language profile」那種整份預寫文案（設計理由見
# openspec/changes/2026-06-30-chinese-writing-profiles/design.md「被否決的路」）。
_ZH_NATURALNESS_SEED = """\
- **Deliverable-language naturalness** (seeded from `artispec reference writing-zh`; re-run it for
  the full reasoning/citations, or if this is a normative/spec document also pull in the 規範詞
  與需求句紀律 table):
  - 動詞當家：把「進行/作出/予以/加以＋名詞」還原成動詞（「進行查核」→「查核」）；同類弱動詞
    （施加/執行/實施/造成/受到）逐個判斷，別無腦改。
  - 被字句只用在真正不如意的事：中性/正面的事不加「被」（「他被升為營長」→「他升為營長」）。
  - 「的」不連三層以上：定語堆疊三層以上拆成後置短句。
  - 連接詞只留扛邏輯的：純裝飾的「和／由於…所以／當…的時候」能省則省，因果/條件接榫
    （因為…所以、若…則）留著。
  - 冗詞與空範疇詞直接刪：「有很多問題存在」→「問題很多」；「作為一個…」通常是英文直譯可刪。
  - 結構性內容交給適合的版面：步驟用編號，並列或比較才用條列／表格；理由與取捨用段落，不為湊表格切斷條件。
  - 段落用內容銜接：指前文用「上述兩道措施」，不要「如前所述」這種報幕式連結。
  - 省去空泛報幕，直接給任務、規定或事實；真正影響操作的適用範圍、前置條件與導覽保留。
  - 語域一以貫之：選定正式度後不中途轉口語/行銷腔。
"""

_EN_NATURALNESS_SEED = """\
- **Deliverable-language naturalness** (seeded from `artispec reference writing-en`; re-run it for
  the full reasoning/citations, or for the RFC 2119 requirement-keyword table on a normative
  document):
  - Verb-centric: turn nominalizations back into verbs ("make a decision" → "decide"); scan
    `-tion`/`-ment`/`-ity` stacked with a weak verb (*is, has, undergoes*).
  - Active voice by default: "the system validates the request", not "the request is validated by
    the system"; use the passive only when the actor is unknown or irrelevant.
  - Cut the hedge-and-inflate pattern: say the claim directly, or mark it `[TBD]` — don't
    manufacture false modesty around a claim you're actually making.
  - Avoid the AI-ism word list: delve, tapestry, realm, leverage (as a verb), utilize, seamless,
    robust, boasts, testament to — prefer the plain, shorter word.
  - Em-dash / "not just X — it's Y" only for a genuine interruption or emphasis, never as default
    connective tissue between clauses.
  - No throat-clearing openers or closers: cut "In today's fast-paced world" and generic
    "In conclusion, X is a multifaceted topic" restatements.
  - Avoid empty self-narration; retain useful scope, prerequisites and navigation for the task.
  - Default to prose for explanation; reserve lists for genuinely enumerable, parallel items
    (avoid bullet-itis).
"""

_GENERIC_NATURALNESS_PLACEHOLDER = """\
- **Deliverable-language naturalness**: (fill-in guidance — this is the concrete face of backbone
  rule 12: ArtiSpec ships no bundled reference for this language yet. (1) run `artispec reference`
  to confirm, and check `writing-zh`/`writing-en` for the shape a reference doc takes; (2) draft
  concrete bad→good pairs for THIS project's language and genre, citing a real, checkable source
  — never invent an example or an equivalence a source doesn't actually make; (3) ask the human to
  confirm or adjust before treating this bullet as final — writing-guide.md is shared, load-bearing
  doctrine, not something to silently auto-fill)
"""


def _naturalness_seed(lang: str) -> str:
    """語言已知（zh-TW/zh-CN 等 zh 系、en）→ 種通用規則濃縮版；其他語言→維持填寫指引佔位。"""
    norm = lang.strip().lower()
    if norm.startswith("zh"):
        return _ZH_NATURALNESS_SEED
    if norm == "en" or norm.startswith("en-") or norm.startswith("en_"):
        return _EN_NATURALNESS_SEED
    return _GENERIC_NATURALNESS_PLACEHOLDER


def build_writing_guide(lang: str) -> str:
    """組出完整 writing-guide.md：語言中性 backbone（不變）＋ Project Conventions（自然度 bullet
    依 `--lang` 種對應語言的通用規則濃縮版；其餘 bullet 維持文類特化的填寫佔位，因為文類要 develop
    才決定）。"""
    deliverable_language_hint = (
        f"{lang} (confirm/adjust during develop; which terms keep their original language)"
        if lang.strip() else "(e.g. zh-TW / English; which terms keep their original language)"
    )
    return _WRITING_GUIDE_BACKBONE + f"""\
## Project conventions (fill during `develop`, in the deliverable language)
<!-- The only zone that grows. One concrete imperative per bullet; refine in place —
     supersede, don't stack near-duplicates. Machine-checkable term identity goes to
     glossary.yaml, not here. -->
- **Deliverable language**: {deliverable_language_hint}
{_naturalness_seed(lang)}\
- **Requirement keyword dictionary**: (deliverable-language tokens for MUST / MUST NOT / SHOULD / SHOULD NOT / MAY)
- **Banned openers / filler**: (deliverable-language list for rule 4)
- **Task and audience conventions**: (purpose-specific preconditions, steps, expected results,
  failure handling and limits; reuse recorded sources, never invent facts to fill a section)
- **Governance boundary**: keep decision provenance and test diaries in their source records;
  retain support conditions and unverified limits that affect use. Verification reports themselves
  still name the version, method, result and uncovered scope.
- **Global intro ownership**: (which section frames the whole document; others write no intro)
- **No backstage vocabulary**: (deliverable-language replacements for any authoring-tool / governance
  term — e.g. don't write 森林/治理父/governed-by/Tier-N/L2a/fan-in/factcheck/§<section>; name the
  document and say "依據《…》" / "詳見《…》" instead)
- **Other banned words / required phrasing**: (project-specific)
"""


# 術語權威（token 一致性）。realizes 給正名、glossary＋lint Vg 督促照用、aperture 注入寫作 agent。
# 桶＝待遇：module(自創詞/縮寫→用正名、展開、首次可附 english) /
#          standard(外部標準名→官方寫法逐字、不翻) / protocol(協定 token→位元組逐字、code 格式、不翻)。
_GLOSSARY_TEMPLATE = """\
# Project term authority (token consistency). Bucket = how draft must treat the term.
#   - id: <unique>
#     canonical: <the name prose must use>       # required
#     bucket: module | standard | protocol       # required; selects the treatment
#     code: <abbreviation, e.g. RMM>             # optional; module bucket → lint Vg2 (no bare code)
#     english: <English original>                # optional; drill-down only — gloss on first use / map to EN sources
#     definition: <one canonical sentence of what the term IS>  # optional; drill-down only (`artispec show <id>`), NOT injected
#     aliases_forbidden: [<other names>]         # optional; lint Vg1 nudges to canonical
terms: []
"""


# .gitattributes 腳手架（fingerprint v2 D2 防禦縱深第三層）：repo 端把 docspec 管的文字檔
# 釘 eol=lf——引擎讀端已正規化（D1）、寫端已釘 LF（D2），這層讓 git autocrlf 也不再翻譯換行
# ＝三層任一失守其餘仍保住。建議性、非閘門；既有專案自行補上（`artispec guide` 有提示）。
_GITATTRIBUTES_TEMPLATE = """\
# docspec: pin LF for the text files the engine fingerprints/writes, so fingerprints
# and the freeze hash net stay byte-identical across OS / git autocrlf / worktrees.
*.md text eol=lf
*.yaml text eol=lf
*.yml text eol=lf
"""


# 可整合的 agent 工具（chatgpt＝codex、google＝gemini 別名）
_AGENTS = ("claude", "antigravity", "codex", "gemini")
DEFAULT_AGENT = "claude"   # 非互動預設只裝這一家（要全裝＝ `--tool all`）
_ALIASES = {"chatgpt": "codex", "openai": "codex", "gpt": "codex", "google": "gemini"}


# AGENTS.md 受管區塊（`--agents-md`，opt-in）：Codex／Gemini／Antigravity／Claude Code 都讀專案根
# AGENTS.md。只寫 begin/end 標記之間，區塊外使用者內容原樣保留；重跑＝原地更新。
_AGENTS_MD_BEGIN = "<!-- docspec:begin -->"
_AGENTS_MD_END = "<!-- docspec:end -->"
_AGENTS_MD_VERSION = 4
_AGENTS_MD_ZH = """<!-- 由 `artispec init --agents-md` 產生；區塊內的修改會被覆寫。專案自己的規則寫在區塊外，衝突時以專案規則為準。 -->
## ArtiSpec 協作規範

### 一、開工
- 主 agent 開工時，讀完本檔後執行 `artispec handover` 看交接單，再用 `artispec roadmap` 找到本次工作，接著 `artispec roadmap show <工作編號>` 看這項工作的來源與問題；需要核對時才開它列出的原始紀錄。
- 先查有沒有相同範圍的 roadmap 工作，有就沿用；沒有才用 `artispec roadmap add --title "…" --ref swc:<change>` 新增，記下指令回傳的工作編號。文件工作用 `change:<change>` 或 `doc:<文件或章節>`。工作實體尚未建立時先記工作，建立後用 `artispec roadmap link <工作編號> --ref <參照>` 補連結，不虛構編號、不重複新增。這是開工規範，未連結的提醒不擋定版或封存。
- 結束一段工作、上下文快滿、或要換 agent 之前，用 `artispec handover write` 整份重寫交接單：這段做了什麼、進行中的事（派了誰、在等誰）、答應使用者的事、要注意的事、下一步。做完的事不必留；現況由 roadmap 推導，不寫進交接單。
- 需要細節時用查詢指令取需要的部分，例如 `artispec code spec show <能力> --req R1`、`artispec change show <change>`、`artispec decision list`，不整份讀檔。
- 變更查詢共用 `artispec change` 與 `artispec change show <change>`：前者預設列出進行中的文件和軟體變更，`--all` 加入歷史；後者唯讀呈現指定變更的狀態、問題與來源，不刷新任務、不執行測試。兩條線共用 `docspec/changes/` 容器，維持各自的格式、完成與封存條件。文件在需要受控修訂時用 `artispec change new`，軟體用 `artispec code change new`；文件 develop／apply 與既有 targets 流程照常使用，不為了對稱新增 proposal、design 或 tasks。舊軟體目錄仍可操作，只有明確執行 `artispec change migrate` 才搬移，查詢不自動遷移。
- `roadmap show` 是唯讀摘要，JSON 依版本提供 work、dependencies、governance、software、documents、actions、diagnostics；只沿明確引用、子項、前置項與必要來源整理。正常項目以數量概述，問題保留識別碼與原因，有效決策保留內容。缺資料不等於沒有限制；被取代的引用仍保留來源，不代表已授權把本工作改套新版。依摘要列出的動作與角色繼續：未簽收交測試角色，文件未定版仍須使用者明確要求才定版。查摘要不跑測試、不刷新或寫入紀錄、不重寫交接單，也不代替完整驗證。
- 提案前檢查誰操作、使用平台、啟動方式、安裝限制、連線／離線限制與交付方式。已有資訊、裁定或需求就直接引用；只有缺漏且影響設計時才詢問，沿用既有紀錄，不新增必填表單。修改需求時說明哪些限制保留、哪些依明確裁定取代，不默默漏掉原有限制。
- 分清操作者需安裝什麼、主機已有依賴，以及網路限制針對哪些程序或整台主機，不自行加強要求。驗收按已記錄的平台、啟動方式與限制，使用作者完成後的實際交付包；未涵蓋範圍及環境失敗須明示。交付含文件時，核對 latest 的待驗或可用敘述與當前證據，需修正則依負責人明確要求另定新版，不改歷史；仍沿用各領域的完成與定版條件。
- 子 agent 只讀派工指定的內容，不重讀整個專案現況。
- 文件查詢 `get`、`instructions`、`find`、`check`、`diff` 預設讀正式內容；在文件 change 中工作時，查詢與 `put`／`render` 都明確帶同一個 `--change <id>`，確認輸出的 context 與 source。指定草稿缺預覽或已過時時依診斷補 apply／render，不以正式舊文代替草稿查核；查詢不產生預覽或改寫 ledger。
- 文件按既有 writing-guide、brief 與 kind 寫給交付讀者；缺少專案風格才採工程團隊預設。保留實際操作、結果、故障處理及必要限制，不把治理來源或驗收流水帳反覆插入操作正文。
- 未封存的變動需求用 `realizes: [draft-req:<change>/<capability>/R<n>]` 指定來源；封存後保留原引用，由基線解析正式入口。這不是完成證據，缺失或失效依診斷處理，不猜同編號需求、不自動改連結。
- `check` 的 coverage 分清全專案結構與引用掃描、正文準備狀態；語意及交付審查未執行。過時正文仍可能掃過引用，check 通過不代表定版或交付完成。
- 工作摘要預設 JSON v2，以驗證範圍指紋與原始紀錄入口取代重複的簽收全文；`roadmap show <工作編號> --json --schema-version 1` 保留原 v1 結構。有效決策內容、原引用、問題原因與歷史差異仍保留。D 與 I 是背景依據，不是待交付成果；只有背景引用的工作需有理由手動結案，不會自動完成。

### 二、與使用者溝通
- 用白話，先講結論。
- 所有 agent（包含子 agent）對使用者與彼此的回報，一律使用本專案的語言：{lang_name}。派工時把這一點寫進派工內容。
- 不自創名詞，優先使用專案已有的用語。
- 對使用者提到任務、change、測試、紀錄時，先說它是什麼、做什麼用，編號只放在括號裡。
- 回報要分清「已實作」與「已驗證」：說明驗證了什麼、沒驗證什麼、證據在哪裡。不確定就說不確定。
- 使用者要求先討論時，不因為 change 已經存在就開始實作。agent 之間互相同意，不等於使用者批准。

### 三、使用者的決定與提供的資訊
- 需要使用者決定的事，用 `artispec question add` 記下並提出。
- 使用者做的決定用 `artispec ruling add` 記錄；使用者提供的現況資訊（例如電腦環境、名單格式、誰負責什麼）用 `artispec info add` 記錄。兩者都保存使用者原話。
- 使用者講得清楚就直接記；講得不清楚（指涉不明、前後矛盾、數字或範圍不確定）時，先用白話覆述，使用者確認後再記，覆述與確認回覆一併記下。
- 使用者明確用新裁定取代舊規則時，保留歷史與取代關係並落實新版，不重問已清楚授權的決定。不依同日條目的排列猜測先後；仍有實質衝突且未明確取代時，提出衝突、影響與建議，請使用者裁定。
- 新的裁定改變了某個有效的專案決策時，用 `artispec decision add --supersedes <舊決策> --based-on <新裁定>` 寫出完整的新版並 activate，不讓兩者並存；取代後執行 `artispec impact`。
- 方向改變（決策被取代或撤回）後，執行 `artispec impact`，逐項處理受影響的項目。
- 定版（`artispec freeze`）只在使用者明確要求時執行；交付時的專案基線（`artispec baseline`）也一樣。
- 使用者原話保存在治理紀錄；change 的 `notes.md` 記變更理由並連到相關紀錄，不維護第二份裁定全文。技術交接說明介面、檔案與重現方式，引用測試及證據；現行進度、簽收與驗證狀態仍以 CLI 為準。驗收只涵蓋當時版本與驗證範圍；若交付包含文件，驗收前須完成該內容定版，後續內容變更不沿用舊驗收。
- 文件封存的 notes 提醒是非阻擋提示，不代表治理裁定缺漏，也不代表封存已成功；查看原紀錄即可，不因提示重複抄錄或補造裁定。封存仍須符合既有目標完成與正式來源漂移檢查。

### 四、角色
- 主 agent：與使用者討論、設計、寫規格與任務、派工、審查與驗收。小範圍的機械式修改（改名、搬檔、設定值、幾十行以內）自己做，不另開子 agent。
- 實作者：依任務修改程式或文件。不修改測試檔；認為測試有錯時用 `artispec code testplan object` 提出。
- 測試角色：必須是和實作者不同的 agent。依規格的 WHEN／THEN 寫測試，寫完用 `artispec code testplan sign` 簽收。
- 不同會話可以用同一家 AI 工具。工具前綴与會話碼分開記錄；Codex 自動用 `CODEX_THREAD_ID`，未提供實際會話碼的工具可由控制器用 `DOCSPEC_ACTOR_ID` 傳入已保存的啟動識別碼。與偵測碼衝突報錯，不可為換角色而換碼。子 agent 若繼承實作者 thread id，須另啟動獨立會話；舊同工具紀錄缺碼時不能推論獨立或自動轉移作者。測試修改、刪除、簽收、異議回應只由原測試作者或負責人操作，不得冒用身分。
- 審查者：用乾淨的上下文獨立審查（文件用 dspx-factcheck，軟體用 dspx-verify 的語意審查）。不修改被審查的文件、程式或測試；文件審查的發現用 `artispec audit raise` 記進查核紀錄（這是審查者的本分，不算修改）。

### 五、派工
- 派工內容包含：目標；相關的裁定與決策（編號與位置）；要改的檔案與範圍；禁止事項；環境限制；驗收方式（通常是 `artispec code evidence run` 或 `artispec check`）；預期的回報內容。
- 預設不傳完整對話；只有任務確實依賴先前討論、而摘要不足時，才傳必要的歷史。
- 依難度選模型：規劃、設計、審查用高階模型；明確的實作用中階；機械式工作用最小的。測試角色依規格設計會抓到錯誤的測試、回應異議，不算機械式工作。派工時說明難度、所選模型與理由，模型依所用工具當期的官方建議，不把一家的型號套到另一家。
- 一個實作者負責一組相關任務，包括後續修正；不按每個任務各開一個 agent。相關的後續工作交回原本的 agent。
- 主 agent 交代清楚設計與範圍後，讓實作者做完再審查，不自己先做一遍再派人重做。

### 六、子 agent
- 只讀完成任務所需的相鄰程式與文件，不無目的地掃描整個專案。
- 資訊不足時不猜測；遇到沒涵蓋的設計問題，停下來回報主 agent，不自行決定設計、不縮小或跳過任務。
- 不自行再派工；需要拆分時先向主 agent 說明原因。
- 回報內容：修改的檔案、行為變化、驗證結果與證據編號、未解決的問題。派工裡要求的步驟（例如實際跑測試）沒做到，要明說哪一步沒做、為什麼，不回報「全部完成」。不貼整份程式或完整的測試紀錄。
- 開發中只跑相關測試，完成時跑一次完整測試。

### 七、交接與紀錄寫入
- ArtiSpec 不支援多個 agent 並行修改受管理紀錄或多人編輯。提案交給測試角色規劃與簽收，再交給實作者驗證；交棒前更新 roadmap 與整份 handover。派工依難度與範圍分組，明訂檔案負責人。
- 這不限制程式原始碼依檔案分工開發；受管理紀錄仍須依序寫入。缺 `based-on`、`realizes` 或 roadmap 連結只提醒；必要情境、測試、實作任務與有效證據是完成條件，缺少時不能宣稱完成或封存。文件與軟體的差異只記錄，不互相阻擋定版或封存。

### 八、硬限制
- `docspec/` 底下的紀錄只能透過 artispec 指令修改：文件內容用 `artispec get`／`artispec put`，治理紀錄與軟體規格、任務用各自的指令。`docspec/changes/_versions/.../snapshot/` 與舊版歷史快照不可修改；`docs/` 只保留最新公開投影，舊 PDF／proof 留在版本容器，不複製回 `docs/`。hook 會擋下受保護寫入，被擋時停下來回報，不換路徑重試。
- 使用者指定為受保護的資料只能讀取。
- 沒有權限（重啟服務、寫正式資料、改系統設定）時立刻停下，把要執行的指令交給使用者；不猜密碼、不繞路、不假裝完成。
- 大型檔案只做局部修改，不整檔重寫。

### 九、規則檔
- 本檔是專案唯一的規則檔，不另建各工具專用的規則檔。
- 修改區塊外的規則前，先向使用者說明要改什麼與原因，取得同意才改。

### 十、各工具
- Claude Code：專案沒有 CLAUDE.md 時會讀本檔（需 2.1.277 以上）。派工用 Agent 工具。
- Codex：原生讀 AGENTS.md；派工時不繼承完整歷史。
- Gemini、Antigravity：原生讀 AGENTS.md；派工時可指定模型。
"""
_AGENTS_MD_EN = """<!-- Generated by `artispec init --agents-md`; edits inside this block are overwritten. Put project rules outside the block; they win on conflict. -->
## ArtiSpec collaboration rules

### 1. Starting work
- The main agent reads this file, then runs `artispec handover` for the handover note and `artispec roadmap` to find the current work. Next run `artispec roadmap show <work-id>` for that work's sources and problems; open the referenced original records only when needed to check details.
- Check for existing roadmap work with the same scope and reuse it. Only when none exists, run `artispec roadmap add --title "…" --ref swc:<change>` and keep the returned work id. Document work links to `change:<change>` or `doc:<article-or-section>`. If the target does not exist yet, register the work first and add the reference with `artispec roadmap link <work-id> --ref <reference>` once it exists. Never invent an id or duplicate work. Registration is a workflow rule; missing links remain non-blocking for freeze/archive.
- Before ending a stretch of work, running out of context or handing over, rewrite the whole note with `artispec handover write`: what was done, what is in progress (who was assigned what, waiting on whom), promises to the owner, cautions, next step. Finished work need not stay; current status comes from the roadmap, not the note.
- Fetch details with queries — `artispec code spec show <capability> --req R1`, `artispec change show <change>`, `artispec decision list` — instead of reading whole files.
- Query both domains with `artispec change` and `artispec change show <change>`: the list defaults to active document and software changes; `--all` includes history. Show reads the named change's status, problems and sources without refreshing tasks or running tests. Both use the `docspec/changes/` container while retaining their own formats and completion/archive rules. Start a controlled document revision with `artispec change new` when needed; create a software change with `artispec code change new`. Keep document develop/apply and targets; do not add proposal, design or tasks merely for symmetry. Legacy software containers remain actionable and move only with explicit `artispec change migrate`; queries never migrate them.
- `roadmap show` is a read-only summary with versioned JSON sections work, dependencies, governance, software, documents, actions and diagnostics. It follows explicit references, children, prerequisites and necessary sources. Normal items are summarized by count; problems keep their ids and reasons, and effective decisions keep their content. Missing information does not mean no constraints. A superseded reference remains visible and does not authorize applying its replacement to this work. Follow the indicated actions and roles: unsigned tests go to the test role; an unfrozen document still requires the owner's explicit request to freeze. Reading the summary does not run tests, refresh or write records, rewrite the handover note, or replace full verification.
- Before proposing, check who will operate the result, their platform, startup method, installation restrictions, network/offline restrictions and delivery method. Cite existing information, rulings or requirements; ask only about missing facts or choices that affect the design. Use existing records, not a new mandatory form. When changing requirements, state which constraints remain and which an explicit ruling supersedes; never silently drop existing constraints.
- Separate operator setup, existing machine dependencies and whether network restrictions apply to specified processes or the whole host; do not strengthen requirements. Validate the recorded platforms, launch methods and restrictions using the actual finished delivery artifact after its author stops editing. State uncovered scope and environment failures. For document delivery, compare latest readiness or pending-verification claims with current evidence; freeze corrections as a new version only when the owner explicitly requests it, preserving history and existing domain completion/freeze rules.
- Subagents read only what their assignment names.
- Document queries `get`, `instructions`, `find`, `check` and `diff` default to official content. Within a document change, pass the same explicit `--change <id>` to queries and to `put` / `render`, then check the returned context and sources. Missing or stale draft prose needs the indicated apply/render step; do not review old official prose as the draft. Queries never generate previews or write ledgers.
- Write for the deliverable's audience using its existing writing-guide, brief and kind. Use engineering-team defaults only where project conventions are absent. Keep actionable steps, results, failure handling and necessary limits; keep governance provenance and test diaries in their source records.
- Link an unarchived changed requirement with `realizes: [draft-req:<change>/<capability>/R<n>]`. After archive, retain the original reference and follow its baseline to the formal source. This is not completion evidence; surface missing or invalid sources instead of guessing matching numbers or changing links automatically.
- Check coverage distinguishes project structure and reference scans from prose readiness. Semantic and delivery reviews are not performed; stale prose may still have its references scanned. Check success does not mean frozen or delivery complete.
- Work summaries default to JSON v2: saved scope fingerprints and original-record entry points replace repeated signed contracts. `roadmap show <work-id> --json --schema-version 1` retains the original v1 shape. Effective decision content, original references, problem reasons and historical differences remain. D and I are background basis, not deliverables; basis-only work needs a reasoned manual close and never completes automatically.

### 2. Talking to the owner
- Plain language, conclusion first.
- Every agent, subagents included, reports to the owner and to each other in the project's language: {lang_name}. Say so in every assignment.
- No invented terms; use the project's existing vocabulary.
- When mentioning a task, change, test or record, say what it is and what it is for first; ids go in brackets.
- Report "implemented" and "verified" separately: what was verified, what was not, where the evidence is. Say so when unsure.
- When the owner asks to discuss first, do not start implementing just because a change exists. Agents agreeing with each other is not the owner's approval.

### 3. The owner's decisions and information
- Record what the owner must decide with `artispec question add` and raise it.
- Record the owner's decisions with `artispec ruling add` and the information they give about the current situation (their environment, data formats, who does what) with `artispec info add`. Both keep the owner's own words.
- If the owner was clear, record it directly. If they were unclear (vague reference, contradiction, uncertain number or scope), restate it in plain words first and record it after they confirm, with your restatement and their reply.
- When the owner explicitly supersedes an old rule, keep its history and the supersession relationship and apply the new ruling; do not ask again about a clearly authorized decision. Never infer precedence from the order of entries on the same date. If a material conflict remains without explicit supersession, present the conflict, impact and recommendation for the owner to rule on.
- When a new ruling changes an active project decision, write the full new version with `artispec decision add --supersedes <old> --based-on <ruling>` and activate it; do not leave both standing. Then run `artispec impact`.
- After a direction change (a decision superseded or withdrawn), run `artispec impact` and handle each affected item.
- Freeze a version (`artispec freeze`) or pin a project baseline (`artispec baseline`) only when the owner explicitly asks.
- Preserve the owner's words in governance records. Change `notes.md` holds the rationale and references those records, without a second copy of rulings. Technical handoff describes interfaces, files and reproduction with links to tests and evidence; current progress, sign-off and verification status come from the CLI. Acceptance covers only the recorded version and verification scope. If delivery includes a document, freeze that content before accepting it; changed content does not inherit an old acceptance.
- The document archive's notes reminder is non-blocking. It neither proves missing rulings nor announces successful archive. Follow original records without duplicating or inventing rulings to satisfy it; target completion and official-source drift checks still apply.

### 4. Roles
- Main agent: discusses with the owner, designs, writes specs and tasks, assigns work, reviews and accepts. Small mechanical edits (renames, moves, settings, a few dozen lines) it does itself.
- Implementer: changes code or documents per its tasks. Never edits test files; objects with `artispec code testplan object` when a test looks wrong.
- Test role: a different agent from the implementer. Writes tests from the spec's WHEN/THEN and signs them off with `artispec code testplan sign`.
- Different sessions may use the same AI provider. Provider labels and session ids are recorded separately. Codex uses `CODEX_THREAD_ID`; without a detected session id, the controller may pass a recorded launch id through `DOCSPEC_ACTOR_ID`. Conflicting overrides are rejected; never change ids to switch roles. A child inheriting the implementer's thread id needs a separate session. Legacy same-provider records without ids cannot establish independence or automatically transfer authorship. Only the original test author or owner changes/removes/signs tests or answers objections; never impersonate an identity.
- Reviewer: reviews independently with a clean context (dspx-factcheck for documents, dspx-verify's semantic review for software). Never changes the documents, code or tests under review; records document findings with `artispec audit raise` (that is the reviewer's job, not a change).

### 5. Assigning work
- An assignment states: the goal; the relevant rulings and decisions (ids and where); files and scope; what not to do; environment limits; how it is accepted (usually `artispec code evidence run` or `artispec check`); what to report.
- Do not pass the whole conversation by default; pass history only when the task depends on it and a summary is not enough.
- Pick the model by difficulty: planning, design and review on a top model; clear implementation on a mid one; mechanical work on the smallest. The test role (designing tests that catch wrong behaviour, answering objections) is not mechanical work. Say the difficulty, the model and why; follow each tool's current official guidance and never map one vendor's models onto another's.
- One implementer owns a group of related tasks, including follow-up fixes; do not start an agent per task. Send related follow-ups back to the same agent.
- Once the design and scope are clear, let the implementer finish, then review; do not do the work first and then assign it again.

### 6. Subagents
- Read only the neighbouring code and documents the task needs; do not scan the whole project.
- Do not guess when information is missing; stop and report design questions the assignment does not cover. Never decide design, shrink or skip a task on your own.
- Do not assign work onward; explain to the main agent first when a task should be split.
- Report: files changed, behaviour changes, verification results with evidence ids, open problems. If a step the assignment asked for (such as actually running the tests) was not done, say which and why; never report "all done". No full code or full test logs.
- Run related tests during development and the full suite once at the end.

### 7. Handover and record writes
- ArtiSpec does not support concurrent agent writes to managed records or multi-user editing. Hand proposals to the test role for planning and sign-off, then to the implementer for verification. Update roadmap and rewrite the whole handover note before handing over. Group assignments by difficulty and scope, with explicit file ownership.
- Source-code development may still be divided by file ownership; managed records must be written sequentially. Missing `based-on`, `realizes` or roadmap links are reminders. Required scenarios, tests, implementing tasks and valid evidence are completion conditions: missing ones prevent completion or archive. Document/software differences are recorded without blocking the other domain's freeze or archive.

### 8. Hard limits
- Records under `docspec/` change only through artispec commands: document content via `artispec get` / `artispec put`, governance records and software specs/tasks via their commands. Frozen `docspec/changes/_versions/.../snapshot/` and legacy historical snapshots are immutable. `docs/` contains only the latest public projection; old PDF/proof stays in its version container and must not be copied back into `docs/`. When the hook blocks protected writes, stop and report instead of trying another path.
- Data the owner marks as protected is read-only.
- Without permission (restarting services, writing production data, system settings), stop and hand the command to the owner; never guess passwords, work around it, or pretend it is done.
- Edit large files locally; never rewrite them whole.

### 9. This file
- This is the project's only rules file; do not create tool-specific rules files.
- Before changing rules outside this block, tell the owner what and why and get their consent.

### 10. Per tool
- Claude Code: reads this file when the project has no CLAUDE.md (2.1.277 or later). Assign work with the Agent tool.
- Codex: reads AGENTS.md natively; do not pass the full history to subagents.
- Gemini, Antigravity: read AGENTS.md natively; subagents can be given a model.
"""


def agents_md_block(lang: str) -> str:
    """AGENTS.md 管理區塊：依專案主語言產生派工規範（2026/09/30 裁定）。"""
    from dspx.engine.config import lang_subtag
    body = _AGENTS_MD_ZH if lang_subtag(lang) == "zh" else _AGENTS_MD_EN
    body = body.replace("{lang_name}", _lang_name(lang))
    return f"{_AGENTS_MD_BEGIN}\n<!-- docspec:guidance-version {_AGENTS_MD_VERSION} -->\n{body}{_AGENTS_MD_END}\n"


def _lang_name(lang: str) -> str:
    """AGENTS.md 裡寫給 agent 看的語言名稱；繁簡要寫明，免得子 agent 用錯。"""
    low = (lang or "en").lower()
    if low.startswith("zh"):
        return "简体中文（zh-CN）" if any(k in low for k in ("cn", "hans", "sg")) else f"繁體中文（{lang}）"
    return {"en": "English", "ja": "日本語"}.get(low.split("-")[0], lang)


def _write_agents_md(project_root: Path, lang: str = "en") -> str:
    """把 docspec 受管區塊寫進（或原地更新）專案根 AGENTS.md。回傳 created/updated/unchanged。"""
    path = project_root / "AGENTS.md"
    if not path.is_file():
        path.write_text(agents_md_block(lang), encoding="utf-8", newline="\n")
        return "created"
    text = path.read_text(encoding="utf-8")
    begin, end = text.find(_AGENTS_MD_BEGIN), text.find(_AGENTS_MD_END)
    if begin != -1 and end > begin:
        tail = text[end + len(_AGENTS_MD_END):]
        new = text[:begin] + agents_md_block(lang).rstrip("\n") + tail
    else:
        new = text.rstrip("\n") + ("\n\n" if text.strip() else "") + agents_md_block(lang)
    if new == text:
        return "unchanged"
    path.write_text(new, encoding="utf-8", newline="\n")
    return "updated"


def _project_lang(config_path: Path, default: str) -> str:
    """AGENTS.md 用的語言：既有專案看 config.yaml 的 language，新專案用 --lang。"""
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        return str(data.get("language") or default)
    except (OSError, yaml.YAMLError):
        return default


def _claude_md_shadows_agents_md(project_root: Path) -> Path | None:
    """Claude Code 在有 CLAUDE.md 時不讀 AGENTS.md（除非 CLAUDE.md 以 `@AGENTS.md` 匯入）。
    回傳那份遮住 AGENTS.md 的 CLAUDE.md（供提示），沒有則 None。"""
    for cand in (project_root / "CLAUDE.md", project_root / ".claude" / "CLAUDE.md",
                 project_root / "CLAUDE.local.md"):
        if cand.is_file():
            try:
                if "@AGENTS.md" in cand.read_text(encoding="utf-8"):
                    return None
            except OSError:
                pass
            return cand
    return None


def _resolve_tools(raw: str | None) -> tuple[str, ...] | None:
    """解析 --tool；'all'/空＝全部。回傳 None＝有非法值。"""
    if not raw or raw.strip().lower() == "all":
        return _AGENTS
    picked = []
    for tok in raw.replace(" ", "").split(","):
        if not tok:
            continue
        name = _ALIASES.get(tok.lower(), tok.lower())
        if name not in _AGENTS:
            return None
        if name not in picked:
            picked.append(name)
    return tuple(picked) or _AGENTS


def _select_tools_interactive(project_root: Path) -> tuple[str, ...] | None:
    """questionary 勾選 agent（箭頭鍵/Space/Enter）；偵測已裝者預勾。"""
    import questionary
    # 偵測＝該工具**專屬**的 docspec 產物真的在（不只資料夾存在；資料夾可能是別的工具留的空殼）。
    # `.agents/skills` 由 codex/antigravity/gemini 共用、分不出是誰，故各取專屬記號；舊位也算。
    _markers = {
        "claude": [project_root / ".claude" / "skills" / "dspx-develop" / "SKILL.md"],
        "antigravity": [project_root / ".agents" / "workflows" / "dspx-develop.md",
                        project_root / ".agent" / "skills" / "dspx-develop" / "SKILL.md"],
        "codex": [project_root / ".codex" / "hooks.json",
                  project_root / ".codex" / "skills" / "dspx-develop" / "SKILL.md"],
        "gemini": [project_root / ".gemini" / "commands" / "dspx" / "develop.toml"],
    }
    detected = {tool for tool, ms in _markers.items() if any(m.is_file() for m in ms)}
    labels = {"claude": "Claude", "antigravity": "Antigravity", "codex": "Codex (ChatGPT)",
              "gemini": "Gemini CLI"}
    choices = [
        questionary.Choice(
            labels[a] + ("  (detected)" if a in detected else ""),
            value=a, checked=(a in detected))
        for a in _AGENTS
    ]
    picked = questionary.checkbox(
        "Select AI tools to configure (↑↓ move · Space toggle · Enter confirm)",
        choices=choices).ask()
    return tuple(picked) if picked else None


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="artispec init", description=HELP)
    parser.add_argument("--path", default=".", help="project root (default: current directory)")
    parser.add_argument("--tool", default=None,
                        help="agents to integrate (comma-separated): claude,antigravity,codex(chatgpt),gemini; default all")
    parser.add_argument("--agents-md", action="store_true",
                        help="also write an ArtiSpec-managed block into the project-root AGENTS.md "
                             "(read by Codex, Gemini, Antigravity and Claude Code); content outside "
                             "the block is kept, re-running updates it in place")
    parser.add_argument("--lang", default="zh-TW",
                        help="default hint for config.language (zh-TW or en); the deliverable language is ultimately decided in develop")
    parser.add_argument("--no-tex-hint", action="store_true",
                        help="turn off the typesetting-environment hint (suggests artispec doctor when tex.lock is missing/mismatched)")
    parser.add_argument("--no-update-check", action="store_true",
                        help="skip the non-blocking update check (git install: compares against GitHub HEAD with a ≤2s timeout, silent on any failure; directory install: offline snapshot reminder)")
    args = parser.parse_args(argv)
    lang = args.lang.strip()

    project_root = Path(args.path).resolve()
    home = project_root / PLANNING_DIR_NAME
    config_path = home / CONFIG_FILE_NAME

    is_reinit = config_path.is_file()   # 既有專案＝重新設定（照跑介面、不毀既有檔、刷新 skill）

    # 選 agent：--tool 優先；沒給且是真人終端→動畫＋questionary 勾選；否則預設**單一 claude**
    # （別灑全家＝避免 .claude/.agents/.codex/.gemini 多份污染專案；各家不共享 memory，
    #  故只該裝使用者實際在用的那家。要全裝＝明確 `--tool all`。）
    if args.tool is not None:
        tools = _resolve_tools(args.tool)
        if tools is None:
            sys.stderr.write(f"artispec: unknown agent '{args.tool}'. Choices: {', '.join(_AGENTS)} (or all)\n")
            return 2
    elif sys.stdin.isatty() and sys.stdout.isatty():
        from dspx.env.welcome import show_welcome
        show_welcome()             # 迴圈閃動畫＋按 Enter 才進選單（仿 OpenSpec，不直接跳）
        tools = _select_tools_interactive(project_root)
        if not tools:
            sys.stderr.write("artispec: no tool selected, cancelled.\n")
            return 2
    else:
        tools = (DEFAULT_AGENT,)   # 非 TTY（agent/CI/測試）：預設單一 agent，不灑三家

    home.mkdir(parents=True, exist_ok=True)
    (home / CORPUS_DIR_NAME).mkdir(exist_ok=True)
    (home / "explorations").mkdir(exist_ok=True)   # 思考級記錄的家（純 md、引擎零管理）
    # 治理層（專案最外層）：裁定／決策／唯一一份 roadmap。新專案一律啟用；既有專案重 init 不自動
    # 啟用（啟用會改變發布與 roadmap 的行為），改由 `artispec roadmap migrate` 明確轉換。
    if not is_reinit:
        (home / "governance").mkdir(exist_ok=True)
    # scaffold：既有檔不覆寫（保留使用者客製的 config/writing-guide/glossary），只補缺
    # config/glossary/writing-guide 骨架一律英文（語言中性 doctrine）；交付語言由 develop 填進
    # writing-guide 的 Project conventions 區，config.language 先放 --lang 預設提示。
    for fname, body in (
        (CONFIG_FILE_NAME, _CONFIG_TEMPLATE.replace("{lang}", lang)),
        ("writing-guide.md", build_writing_guide(lang)),
        ("glossary.yaml", _GLOSSARY_TEMPLATE),
    ):
        p = home / fname
        if not p.is_file():
            p.write_text(body, encoding="utf-8", newline="\n")

    # .gitattributes（專案根）：釘 LF、跨 OS 指紋位元一致；既有檔不覆寫（保留使用者客製）。
    gitattributes = project_root / ".gitattributes"
    if not gitattributes.is_file():
        gitattributes.write_text(_GITATTRIBUTES_TEMPLATE, encoding="utf-8", newline="\n")

    # 載入/刷新 skill 到選定 agent（重 init＝刷新，force 覆寫舊 skill 檔）
    from dspx.commands.maintenance._skills import _install
    from dspx.env.skills import SkillError
    try:
        install_results = _install(project_root, tools, force=True)
    except SkillError as exc:
        sys.stderr.write(
            f"artispec: project scaffold created, but skill install failed — {exc}\n"
            "Resolve the reported skill or hook-settings problem, then run "
            "`artispec init` again. Existing hook settings were not replaced on a read/validation error.\n")
        return 1

    print(f"{'Settings updated' if is_reinit else 'ArtiSpec project initialized'}: {project_root}")
    if is_reinit:
        print("  (existing config/writing-guide/glossary kept, not overwritten)")
    print(f"  docspec/: {CONFIG_FILE_NAME}  {CORPUS_DIR_NAME}/  writing-guide.md  glossary.yaml"
          + ("  governance/" if (home / "governance").is_dir() else ""))
    print("  .gitattributes: pins eol=lf for the fingerprinted text files (keeps fingerprints "
          "byte-identical across OS/worktrees)")
    print("  skills installed to (per tool = skill auto-load + command explicit invocation):")
    shared = any(t in tools for t in ("antigravity", "codex", "gemini"))
    _dest = {
        "claude": (".claude/skills/<name> (linked to .agents/skills/<name>)" if shared
                   else ".claude/skills/<name>/SKILL.md")
                  + " + .claude/commands/dspx/<id>.md (/dspx:<id>)",
        "antigravity": ".agents/skills/<name>/SKILL.md + .agents/workflows/<name>.md (native invocation)",
        "codex": ".agents/skills/<name>/SKILL.md (skills-only: $dspx-<name>)",
        "gemini": ".agents/skills/<name>/SKILL.md + .gemini/commands/dspx/<id>.toml (/dspx:<id>)",
    }
    for t in tools:
        print(f"    - {t:<11} → {_dest[t]}")
    # 逐檔結果不印（太吵），但舊位遷移要讓人看得到（刪了什麼／留了什麼）。
    for line in install_results:
        if line.startswith(("  - retired legacy", "  ! legacy", "  ! PATH:")):
            print(f"  {line.strip()}")
    if args.agents_md:
        state = _write_agents_md(project_root, _project_lang(config_path, lang))
        print(f"  AGENTS.md: ArtiSpec block {state}")
        if "claude" in tools and (shadow := _claude_md_shadows_agents_md(project_root)):
            print(f"  ⚠ Claude Code reads {shadow.name} instead of AGENTS.md here — add a line "
                  f"`@AGENTS.md` to {shadow.relative_to(project_root)} so Claude sees the block too.")
    print("\nNext: crystallize the article root with `artispec put <article> concept` (develop will ask you about audience/scope).")

    # 被動、離線、可關的排版環境提示：tex.lock 缺或與隨包期望錯位 → 叫跑 doctor。
    # 不連網、不下載；只讀本機 tex.lock。
    if not args.no_tex_hint:
        why = _tex_env_hint_reason()
        if why is not None:
            print(f"\nTypesetting-environment hint ({why}): run `artispec doctor` to check the export/PDF environment.")

    # 非阻塞更新檢查（有界超時、失敗全靜默；絕不擋 init、絕不改離開碼）。
    if not args.no_update_check:
        _print_update_check()
    return 0


def _github_head_sha(timeout: float = 2.0) -> str | None:
    """GitHub 上 docspec repo 的 HEAD commit sha。任何失敗由呼叫端吞掉。

    ★8.6 硬牆時鐘：socket `timeout` 不涵蓋 DNS 解析（getaddrinfo 可 hang 數十秒——dogfood
    實測 init 卡 2 分鐘的根因）。故整個抓取跑在 daemon thread、以 `join(deadline)` 硬上限收斂；
    逾時＝放棄該執行緒（daemon、不阻塞 init）、回 None。"""
    import threading
    result: dict = {}

    def _fetch() -> None:
        try:
            import json
            import urllib.request
            from dspx.env import _install_source
            api = f"https://api.github.com/repos/{_install_source.GIT_REPO}/commits/{_install_source.GIT_BRANCH}"
            req = urllib.request.Request(
                api, headers={"Accept": "application/vnd.github+json", "User-Agent": "artispec-init"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.load(resp)
            sha = data.get("sha")
            if isinstance(sha, str) and sha:
                result["sha"] = sha
        except Exception:  # noqa: BLE001 — 任何失敗＝靜默、無更新資訊
            pass

    th = threading.Thread(target=_fetch, daemon=True)
    th.start()
    th.join(timeout + 1.5)   # 硬牆：socket 逾時 + DNS/解析餘裕；逾此即放棄（daemon 續跑不阻塞）
    return result.get("sha")


def _print_update_check() -> None:
    """非阻塞更新提醒：git 裝比對 GitHub HEAD（落後印一行）；目錄裝離線印快照提醒。

    ★鐵律：任何例外（無網/DNS/HTTP/429/schema 意外/direct_url 缺/超時）一律**靜默跳過**——
    不印錯誤、不改離開碼、不阻塞 init。離線環境的 git 裝路徑＝完全無輸出（零煩擾）。
    """
    try:
        from dspx.env import _install_source
        src = _install_source.read_install_source()
        if src is None:
            return
        if src["kind"] == "dir":
            # 目錄安裝：**不連網**，直接印快照可能落後提醒＋更新指令。
            print(f"\nUpdate: this is a local build snapshot ({src['path']}) and may lag the source. "
                  f"To update: {_install_source.update_command(src)}")
            return
        if src["kind"] == "git":
            head = _github_head_sha()
            commit = src["commit"]
            if not head:
                return
            same = head.startswith(commit) or commit.startswith(head)
            if not same:
                print(f"\nUpdate available: your git install ({commit[:12]}) is behind the latest on GitHub. "
                      f"To update: {_install_source.update_command(src)}")
    except Exception:  # noqa: BLE001 — 更新檢查永不擋 init、永不改離開碼
        return


def _tex_env_hint_reason() -> str | None:
    """被動偵測：tex.lock 不存在或與隨包期望不一致 → 回一句原因；一致/無法判 → None。

    純讀本機 tex.lock（離線、不下載）。判準＝隨包 _MANIFEST tag 與 tex.lock 記的 tag。
    """
    from dspx.engine import paths
    lock = paths.read_tex_lock()
    if lock is None:
        return "typesetting environment not set up yet"
    try:
        from dspx.commands.maintenance.setup import _MANIFEST
    except Exception:  # noqa: BLE001
        return None
    declared_tag = lock.get("tinytex_tag")
    if declared_tag != _MANIFEST["tag"]:
        return f"tex.lock's TinyTeX version ({declared_tag}) does not match the bundled expectation ({_MANIFEST['tag']})"
    return None
