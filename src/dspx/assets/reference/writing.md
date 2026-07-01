<!--
  docspec-bundled writing reference. Two independent, flat topics — zh and en are two different
  diseases with two different diagnostic traditions, not one template filled in twice (see
  openspec/changes/2026-06-30-chinese-writing-profiles/design.md for why the earlier "3-layer
  shared-core" framing was dropped after an adversarial review: it didn't survive contact with
  either "does the authoring agent need to know this" or internal citation scrutiny).

  Consulted by `develop` (via `docspec reference writing-<lang>`) when drafting or refining a
  project's writing-guide.md "Project conventions" section — NOT auto-injected. `develop` reads
  the relevant topic, proposes concrete conventions grounded in it, and asks the human before
  crystallizing them (the human may want different emphasis, a narrower scope, or none of it).

  Every claim below must be traceable to a real, checkable source. Do not add an example or an
  equivalence between two authors'/traditions' claims that neither source actually makes — that is
  exactly the failure mode ("borrowing a name to manufacture symmetry") the adversarial review
  caught in an earlier draft of this material.
-->

<!-- topic: writing-zh -->
# 中文寫作道地化參考（翻譯腔／西化中文）

> 適用任何正式中文文件（技術、報告、說明、規格）。例句全部逐字引自外部來源（余光中／維基歐化中文／
> Beginneros／VoiceTube／思果），出處見文末；禁任何自擬句子或自造用法。
> 總則：剷除惡性歐化，保留良性歐化（必要術語、承載精確的邏輯接榫）。
> 一把尺：凡中文本來就能說得同樣精確，就不歐化它；歐化若換來更精確，才留。
> 「規範詞與需求句紀律」只有規範／工程文件用得到；一般敘述性文件略過。

- **交付語言**：zh-TW（正體中文）。區域用詞（台灣/大陸）由交付語言決定，以國教院樂詞網查證，本檔不列詞表。標點依教育部《重訂標點符號手冊》。
- 保留原文：國際標準編號、協定 token、程式識別字。英文縮寫首見寫「中文全稱(EN)」，其後沿用縮寫。

---

## 詞 — 選什麼字

選詞是翻譯腔最隱蔽的一層：句子結構再順，選錯一個術語，讀者就得在腦裡把它譯回英文才懂。

一個概念，全文只用一個名字。首見定錨，之後一律沿用，不要在同一份文件裡一會兒「執行緒」一會兒「線程」、一會兒「快取」一會兒「緩存」。查得到通行或官方中譯就照用，別自己另起爐灶；真的查不到才自譯，而且首見綁上原文。

自譯時的取捨，大致是：有既定中譯就用既定中譯；遇到同形歧義（像 fail-safe 與 fail-secure 中文都叫「失效安全」），首見綁原文再補一句界定；沒有既定譯名，就譯成一個「不必回頭看英文也讀得懂」的詞並綁原文；連這種詞都譯不出來，寧可直接保留英文。最該避免的是把兩個名詞硬黏成一個生造詞——讀者得先還原成英文才懂的，等於沒譯。已有完整既定形式的術語也別自行縮短，砍掉的字往往正是它跟別的術語對仗、區別的地方。

譯法本身有先後：能意譯就意譯；純專名或無對應母語詞才音譯；國際公認的字母符號用形譯（X 光、API）。

縮寫首見寫「中文全稱(EN 縮寫)」，之後全文用縮寫，不再與全稱交替。人名、機構、產品依官方指定中譯，沒有才音譯，全文一致。

> 引擎能替你守的只有一件：同一概念有沒有混用兩種寫法、縮寫有沒有首見定義（對 glossary）。其餘——譯得對不對、生不生造、砍沒砍字——機器看不出來，靠人審。

---

## 句 — 怎麼造句

中文句子的毛病，九成可以歸到連淑能那幾條英漢對比軸，和賀陽歸納的幾類歐化句法上。逐一說。

**動詞當家。** 中文的動詞可以直接當謂語，不必像英文那樣把動作塞進名詞再配一個萬能動詞。最好抓的是「進行/作出/予以/加以＋名詞」：「進行查核」就是「查核」，「作出檢討」就是「檢討」〔Beginneros〕；「本校的校友對社會作出了重大的貢獻」不如「本校的校友對社會貢獻很大」〔余光中〕。同類的弱動詞還有施加、執行、實施、造成、受到等等，但它們後面接的不一定都是動作名詞（「受到攻擊」「造成損壞」是正常中文），所以這些只是候選，掃出來要逐個判斷，別無腦改。

名詞化還有一種藏在主語或謂語裡：把動作或形容詞包成抽象名詞。「這本傳記的可讀性頗高」是「這本傳記很好看」，「具有很高的知名度」是「很有名」，「書籍的選購，只好委託你了」是「選購書籍，只好委託你了」〔余光中〕。技術術語裡「冪等性」「可用性」這類已固定的詞根不在此列，別硬還原。

**被字句要省。** 漢語的「被」本來帶不如意、受損的語感；中性或正面的事不加「被」。「他被升為營長」就說「他升為營長」，「我不會被你這句話嚇倒」就說「你這句話嚇不倒我」〔余光中〕。施事者明確就用主動句，不重要就用無主句或把字句，別逢英文被動一律譯成「被」。真正描述不期望的事——遭攻擊、被駁回——才是「被」該出場的地方。連帶一提物稱與人稱：中文偏好讓人或具體事物當主語，英文那種以抽象名詞、以文件（「本文旨在」）、以無靈名詞（「數據顯示」）當主語的句子，落到中文要還原成人或動作在做事。（注意：這條指的是「被…所」這類**譯借的被動結構**，不是要求中文每句都補一個顯式主詞——中文本就常見零主詞/主題化句〔如「這件事，已經處理了」〕，這是漢語的常態語法，不是缺陷，不要為了「主動化」硬塞回一個主詞。）

**「的」不要串。** 定語前置是中文常態，但層層堆在名詞前，讀者就得從右往左找中心詞。兩層以內還好，三層以上拆成後置短句。連著三個「的」一定要重組——「彎彎的楊柳的稀疏的倩影」是病句，朱自清原句是「彎彎的楊柳投下稀疏的倩影」〔余光中引〕。形容詞貼著名詞時，「的」常可省。

**繫詞「是…的」要省。** 「他是很聰明的」就是「他很聰明」〔維基·歐化中文〕。把「是+形容詞+的」這個框架當訊號，多半能拆掉。

**連接詞少用。** 英文靠連接詞顯性標出因果條件（形合），中文靠語序時序暗示（意合）。「我們在公園唱歌和跳舞」裡的「和」是多的，「唱歌跳舞」即可〔VoiceTube〕；「由於…所以」二擇一；「當…的時候」往往直接說時間就好。介詞同理：「我們今天已經討論過關於諾羅病毒的事了」應作「我們今天討論過諾羅病毒了」〔VoiceTube〕。但承載精確因果、條件的接榫（因為…所以、若…則…）不在此砍——這正是那把尺：砍掉純裝飾的連接，留下扛邏輯的。

**冗詞與假複數。** 「有很多問題存在」是「問題很多」，「基於這個原因」是「因此」〔余光中〕。空範疇詞（…的問題、…的情況、在…方面）直接刪。無生命名詞不加「們」：「所有的醫生們」是「所有醫生」；「他是有名的作家之一」是「他是位有名的作家」；「作為一個…」開頭通常是 as 的直譯，可刪可重組〔VoiceTube〕。一句裡兩個近義詞疊用，擇一即可——思果把「他們的關係是愛和惱怒的混合體」收成「他們兩人恩怨難分」〔思果〕，就是這個手藝。

**標點守官方規範。** 並列連用的單字、詞語之間用頓號，別拿逗號或斜線代替〔教育部·重訂標點符號手冊〕。斜線少用；窮舉時的頓號合法，該禁的是用「等/之類」逃避窮舉。中英文之間、數字與單位的排版空格依專案約定一致。

**長度順其自然。** 一句講清一件事為度；太長先問拆不拆得開、改不改得成條列，但只在「拆了更清楚」時才拆，為湊短而硬切會更糟。含多個條件的句子本來就長，別硬斷它的條件鏈。段落也一樣——一段一個主題，主題講完就分段，不靠固定行數。

代詞方面：其、該、此、它每個只指一個對象，有歧義就重複名詞——中文容許、甚至偏好關鍵詞重複，不必像英文刻意換代詞。

---

## 篇 — 怎麼組段

**結構性的內容交給版面。** 規則、介面、狀態機、責任分配、選項比較，用表格、編號、粗體標籤承重，版面本身就傳達邏輯，不必用散文長句扛三層條件。行政院《文書處理手冊》要的「分項條列」就是這個道理。但反過來——論證、取捨、因果鏈該留在散文裡，別把所有東西都塞進表格，那會切斷文氣、產出一份只有格子沒有論述的文件。表格放的是並列的事實，散文走的是推理。

**段落要連貫。** 一段只講一個主題，主題句領頭，先給結論再補細節。句與句之間，讓每句開頭呼應前句已知的東西、句尾才帶出新資訊，讀者就不必回頭確認在講誰。段與段之間用內容銜接——「上述兩道措施」「這個限制」——指前文講過的事，而不是「如前所述」「第三節提到」這種報幕式的連結。

**不要報幕。** 別寫「本節規範…」「本節說明…」「本節不討論…」「可驗證性：」「設計依據：」「如下所示：」這類元敘述。直接給結論、規定、事實就好。要表達某條可驗證，就把它寫成驗收得了的句子（「輸入超過 N 位元組時，系統應截斷並回傳…」），而不是先報一句「本節描述系統如何處理超長輸入」。全文概觀節同理：不敘述文件自身章節走法（「先以…再以…最後…」、「本規範把這項工作拆成…」），直接給主題與核心命題。

**語域別漂。** 選定正式程度後一以貫之，不要中途轉成口語、招呼或行銷腔（「讓我們」「其實很簡單」「相信你已經…」）。論證也別套同一個模子——需要解釋取捨時就解釋，不必每節都用同一句「之所以…是因為…此處否決…」。行政院《文書處理手冊》一句話概括這份守則的目標：簡、淺、明、確。

---

## 規範詞與需求句紀律（規範／工程文件才需要）

一般敘述性文件略過本節。只有當文件要下「義務」（規格、需求、標準、合約這類）時，才需要這一層的紀律。

### 規範詞

對標 CNS / GB-T 1.1 / ISO·IEC Directives Part 2 的標準體系：

| 強度 | 用 | 別用 |
|---|---|---|
| 要求 | **應 / 不應** | 需要、要 |
| 推薦 | **宜 / 不宜** | 最好、建議 |
| 允許 | **可** | 得、能夠 |
| 能力 | **能** | — |
| 禁止 | **不得** | 不可、不允許 |

同一強度全文一詞，不混用。規範詞要省著用：一份滿是「應」的文件，每條的分量都被稀釋；推薦性的內容用「宜」，別用「應」硬抬強度。

### 需求句紀律

規範文件比一般散文多一層：需求句得寫到能驗收。

一句一需求——一個「應/不應/不得」只講一件事，別用「且/並/然後」串起好幾個義務（並列的受詞不算，「記錄使用者 ID 和時間戳」是一個動作）。每條寫出主詞：誰（哪個系統、子系統、角色）在做。理由和解法外移：「應」句只寫做什麼，「為了…」放進 rationale，「用 Redis」放進設計。

可驗收的判準，當作校稿時的人工核對清單（不是引擎硬閘）：每條能不能寫出驗收測試、有沒有量化指標或明確的成功/失敗判斷；有沒有用到「友善/足夠/適當/快速/大量/若干」這種模糊量詞，該換成數字或封閉清單；有沒有開放列舉——「PDF、Word 等」要改成完整的「PDF 與 DOCX」；有沒有「可能時/必要時/視情況/最大限度」這類逃生條款讓需求無法驗收，有就刪掉或改成無條件的「應」。

條件式需求照 EARS 五種句型寫：無條件（系統應…）、狀態（在某狀態期間，系統應…）、事件（當某事件時，系統應…）、選用功能（具備某可選功能時，系統應…）、不期望（若發生某不期望情況，則系統應…）。這套是 EARS（Mavin）定的英文骨架，中文照搬其邏輯，措辭從簡。

### 這條線 lint 能守到哪（鐵律 1）

只有機械上確定、邊界封閉、不會誤報的，才讓引擎攔；其餘是 doctrine，人來判。

**引擎可硬攔（接既有 Vg 家族）：** 術語一致性——同一概念對 glossary 偵測多種寫法、縮寫未首見定義。

**只做弱提示（WARN，易誤報，別當錯）：** 名詞化候選詞只掃封閉四詞「進行/作出/予以/加以＋名詞」（更廣的弱動詞會大量誤報，留 doctrine）；開放列舉「等/之類/等等」要限在句末或無後接數量詞時才報（「甲乙丙等三人」是合法的）；句長過長只提示考慮拆分；在含「應/不得」的章節，逃生詞「最好/儘量/酌情/必要時/如有可能/視情況/最大限度」是封閉字面、在規範語境幾乎必然是缺陷，確定度夠高，值得比一般 WARN 更強。

**只能 doctrine + 人判（機器看不出）：** 被字句該不該省、定語長不長、連接詞冗不冗、代詞指代清不清、段落連不連貫、選詞（自創/砍字/譯名信達）對不對、規範詞要不要換成 EARS 條件句——全是語義層。詞層那一節除了「同概念變體」之外，沒有引擎兜底，別以為有。

---

## 參考資料（要看逐字壞→好對照，或拿不準時去讀）

語言學骨幹：
- 連淑能《英漢對比研究》十大對比軸 — https://baike.baidu.com/item/英汉对比研究/10585925
- 賀陽《現代漢語歐化語法現象研究》（商務 2008，逐詞類分章＋良性/惡性歐化） — https://www.cp.com.cn/book/978-7-100-06066-0_22.html
- 王力《中國現代語法》〈歐化的語法〉（繫詞、被字句源頭）
- 余光中〈論中文的常態與變態〉（壞→好範例最密） — https://www.translators.com.cn/archives/2007/10/1071
- 維基〈歐化中文〉（跨學者交叉索引＋範例表） — https://zh.wikipedia.org/wiki/歐化中文
- 思果《翻譯研究》（名詞化、翻譯腔範例）

官方規範與技術寫作實務：
- 教育部《重訂標點符號手冊》修訂版（頓號/斜線/十五種標點） — https://language.moe.gov.tw/001/upload/files/site_content/m0001/hau/Revised_Handbook_of_Punctuation.pdf
- 行政院《文書處理手冊》「簡淺明確／分項條列」— https://www.ey.gov.tw/Page/43FD318D966A30DD
- 阮一峰《中文技術文檔的寫作規範》— https://github.com/ruanyf/document-style-guide
- yikeke《中文技術文檔寫作風格指南》— https://zh-style-guide.readthedocs.io/

範例對照（本檔例句來源）：
- Beginneros〈歐化中文的常見例子〉— https://beginneros.com/triviaDetail.php?trivia_id=1240
- VoiceTube〈十大常見翻譯腔〉— https://tw.blog.voicetube.com/archives/19126/

術語查證：
- 國教院樂詞網（台灣首選） — https://terms.naer.edu.tw/
- 全國科技名詞委·術語在線 — https://www.termonline.cn/

需求寫作（規範文件適用）：
- EARS（Mavin） — https://alistairmavin.com/ears/
- ISO/IEC/IEEE 29148 ; INCOSE GtWR ; GB/T 1.1-2020 ; RFC 2119 — https://www.rfc-editor.org/rfc/rfc2119

<!-- topic: writing-en -->
# English Writing Naturalness Reference (AI-sounding prose)

> Applies to any formal English document (technical, report, spec). This is a DIFFERENT disease
> from Chinese translationese, not its mirror image — English AI-writing tells are mostly not about
> foreign-grammar calque, they are about a narrow, repetitive register that heavy LLM pretraining
> converges on regardless of the source language. Do not assume a Chinese-translationese fix
> transfers here unmodified; where a technique genuinely transfers (e.g. nominalization-hunting),
> it is noted below as a borrowed *method*, not a shared *rule*.

---

## Word choice — what NOT to reach for

A small, closed set of words and phrases has become disproportionately common in LLM-generated
English and reads as a tell on its own, independent of grammar:
**delve, tapestry, realm, boasts, showcases, seamless, robust, leverage (as a verb), utilize (for
"use"), navigate (the complexities of), testament to, underscores, in the realm of, a myriad of,
plethora.** None of these are wrong in isolation; the tell is *reaching for the ornate Latinate word
when a shorter Anglo-Saxon one says the same thing* — Orwell's own diagnosis of pretentious diction:
"never use a long word where a short one will do," and prefer "the Anglo-Saxon word" over "the
Latin or Greek one" wherever an everyday equivalent exists (Orwell, *Politics and the English
Language*, 1946). This is a genuinely English-internal register question (Anglo-Saxon vs. Latinate
vocabulary), not an import of Chinese 歐化 analysis — the operative test is Orwell's, not a
cross-lingual one.

One concept, one name throughout a document — pick the term the standard/spec itself uses and keep
it; don't alternate between a full term and an invented shorthand once introduced (Strunk & White,
*The Elements of Style*: "omit needless words," "make definite assertions").

---

## Sentence-level tells

**Verb-centric, not nominalized.** Prefer a plain verb over a noun-plus-light-verb construction:
"conduct an investigation of" → "investigate"; "make a decision" → "decide." Scan specifically for
`-tion`/`-ment`/`-ity`/`-ance` nominalizations stacked with a weak verb (*is, has, undergoes,
provides*) — this is the "zombie noun" pattern (Helen Sword, *Stylish Academic Writing* /
"Zombie Nouns," 2012 — her argument is scoped to academic prose specifically; treat it as a useful
*scanning method* for any register, not as evidence that all nominalization is always wrong).

**Active voice, by default.** "The system validates the request" over "the request is validated by
the system" (Orwell's fourth rule: "never use the passive where you can use the active"; Strunk &
White: "use the active voice"; also Google's and Microsoft's developer style guides both name active
voice as a default). Use the passive deliberately when the actor is unknown or irrelevant, not as a
reflex.

**Cut the hedge-and-inflate pattern.** "It's important to note that," "it's worth mentioning,"
"one might argue," stacked qualifiers ("may potentially," "could possibly") — say the claim directly
or mark what's actually uncertain as `[TBD]`, don't manufacture false modesty around a claim you're
actually making. This overlaps Orwell's rule to cut any word that can be cut, and Strunk & White's
"omit needless words."

**The em-dash / "not just X — it's Y" construction, used as connective tissue rather than for genuine
interruption or emphasis, is a widely observed marker of LLM-generated prose** (see e.g. Wikipedia's
essay/guideline "Signs of AI writing," WP:AITELL, which documents this and several other patterns
below from crowd-sourced editorial observation — cited here as a documented, checkable pattern list,
not a formal linguistic authority). Use an em-dash only where a genuine aside or a hard break in the
sentence's structure calls for it; do not use it as a default way to bolt a second clause onto a
first.

**Rule-of-three list padding** ("fast, reliable, and scalable"; "clear, concise, and actionable") —
watch for triads that are decorative rather than doing real distinguishing work; if two of the three
items say the same thing in different words, cut to what's actually distinct. (Unlike Chinese 排比,
which is a legitimate, celebrated rhetorical device in its own right — this is specifically about
*mechanical, content-free* triads, not parallelism as a device.)

---

## Paragraph / document-level tells

**No throat-clearing openers or closers.** Avoid "In today's fast-paced world," "In today's digital
landscape," and their close relatives; avoid closing a section with a generic, content-free summary
restating what was just said ("In conclusion, X is a multifaceted topic that..."). If a section needs
a closing thought, it should add something (a consequence, a caveat), not restate the opening.

**No self-narration of the document's own structure.** "This document is divided into three parts:
first... then... finally..." or "this section will discuss X" is signposting the reader could infer
from the headings themselves; state the content directly. (This matches the Chinese-side "禁報幕"
rule exactly — it is one of the few defects that is genuinely the same phenomenon in both languages,
independent of grammar, because it is about document structure rather than sentence grammar.)

**Bullet-itis.** Converting ordinary connected reasoning into a bulleted list by default flattens an
argument into disconnected fragments; reserve lists for genuinely parallel, enumerable items (Google
Developer Documentation Style Guide and Microsoft Writing Style Guide both favor prose for
explanation and reserve lists/tables for steps, options, and parallel data — matching the Chinese
"結構性的內容交給版面" rule, but note the boundary runs the other way for English: default to prose,
reach for a list only when the content is genuinely enumerable, whereas the failure mode here is
*overusing* lists rather than avoiding them).

---

## Requirement keyword dictionary (normative documents only)

Use RFC 2119 keywords (MUST, MUST NOT, SHOULD, SHOULD NOT, MAY) with capitalized, consistent usage;
RFC 8174 clarifies that only the capitalized forms carry normative force — lowercase "must"/"should"
in ordinary prose are not requirements and should not be treated as such. One requirement per
sentence; name the actor (the system, the component) explicitly; keep rationale out of the
requirement sentence itself.

---

## Where this lint can actually gate (iron law 1)

Only mechanically certain, closed-boundary, low-false-positive patterns belong to the engine; the
rest is doctrine + human judgment.

**Could plausibly be a closed-list WARN:** the specific AI-ism word list above (delve, tapestry,
realm, boasts, seamless, leverage-as-verb, ...) is a closed, low-false-positive set — flagging it is
similar in spirit to the existing backstage-vocabulary lint family. Sentence-initial "In today's
[fast-paced/digital/...] world/landscape" is similarly closed and safe to flag.

**Everything else here (nominalization judgment, active/passive appropriateness, hedge-pattern
severity, rule-of-three padding, bullet-itis, throat-clearing) is semantic and stays doctrine + human
judgment** — the same discipline applied on the Chinese side: don't turn taste into a hard gate just
because a pattern is common.

---

## Sources

- George Orwell, "Politics and the English Language" (1946) — the six rules on metaphor, word
  length, cutting words, active voice, jargon/foreign phrases, and breaking these rules before
  saying anything barbarous. https://www.orwellfoundation.com/the-orwell-foundation/orwell/essays-and-other-works/politics-and-the-english-language/
- William Strunk Jr. & E. B. White, *The Elements of Style* — "omit needless words," active voice,
  definite/concrete language.
- Helen Sword, "Zombie Nouns" (*New York Times*, 2012) / *Stylish Academic Writing* (Harvard UP, 2012) — nominalization diagnosis, scoped to academic prose.
- Google Developer Documentation Style Guide — https://developers.google.com/style
- Microsoft Writing Style Guide — https://learn.microsoft.com/en-us/style-guide/welcome/
- Wikipedia, "Wikipedia:Signs of AI writing" (WP:AITELL) — crowd-documented list of common
  LLM-prose patterns (em-dash overuse, "not just X — it's Y", throat-clearing openers, empty
  summaries, rule-of-three padding, etc.); cited as an observed-pattern catalogue, not a formal
  linguistic authority. https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing
- RFC 2119 / RFC 8174 — requirement keyword conventions. https://www.rfc-editor.org/rfc/rfc2119
