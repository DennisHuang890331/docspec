// docspec-typst — docspec 自帶的 Typst 交付模板（pandoc typst-writer template）。
// 字型（全 OFL、已 bundle、零缺字）：Latin serif＝Source Serif 4、Latin sans＝Source Sans 3、
// mono＝Source Code Pro；**CJK 一律思源宋體(Source Han Serif TC)**。Latin 標題用 sans、內文用 serif。
// ★CJK 一律走 serif（思源宋）而非思源黑體：實測思源黑體(Source Han Sans TC)某些字（如「題」）的
//   ToUnicode 抽取有問題→破壞 pdfplumber 的 CJK 文字抽取→export render-fidelity 硬閘誤判 CJK loss。
//   硬閘（byte-lock）是承重設計，故 CJK 不走思源黑；中文標題用明體 Bold+放大（仍是常見學術慣例）。
// ★同理不用 covers:"latin-in-cjk"（也破壞 CJK 抽取）；中文全形標點 Source Serif/Sans 無→自動落思源宋。
// 版面隨 `profile`（文類）切換：default/academic/manual/essay/novel（見 design）。
// pandoc 變數（title/body/author/profile/lang/region/fontsize/leading）由 export 經 -V 注入；
// 字型靠 typst --font-path 受控字型夾、--ignore-system-fonts（確定性，family 名只解析 bundled）。

$if(highlighting-definitions)$
$highlighting-definitions$

$endif$
// ── profile（文類版面）──
#let profile = "$if(profile)$$profile$$else$default$endif$"

// ── 字型角色 ──
// CJK 一律思源宋（抽取乾淨）。★sans 受語言條件：CJK 文件**不**用 Source Sans 3——實測 typst 0.15 把
//   Source Sans 3 當 Latin-primary＋CJK fallback 時，CJK 字的子集 ToUnicode 壞掉（抽出 cid:0）→ 破壞
//   export render-fidelity 硬閘。故 CJK 文件的 sans 角色退回 serif（思源宋，安全）；非 CJL 文件才用真 sans。
#let _lang  = "$if(lang)$$lang$$else$zh$endif$"
// region＝CJK 在地化（figure supplement 繁/簡：region "tw" → 繁體「圖」，否則 typst lang:"zh" 預設簡體「图」）。
#let _region = "$if(region)$$region$$else$tw$endif$"
#let _sansok = _lang != "zh" and _lang != "ja" and _lang != "ko"
// ★CJK 字型名用 typst 註冊的 family＝「思源宋體」（非 "Source Han Serif TC"，typst 認不得後者）。
#let _serif = ("Source Serif 4", "思源宋體")
#let _sans  = if _sansok { ("Source Sans 3", "思源宋體") } else { _serif }
#let _mono  = ("Source Code Pro", "思源宋體")
// ★2026-07-08 台中港計畫真實審閱回饋（docspec-issues #09/#10）：default 內文改 sans，貼近
//   Claude.ai 網頁版 markdown 慣例；CJK 因 _sansok 對 zh/ja/ko 恆為 false 會安全退回思源宋，
//   不會踩 L20-22 註解所述之思源黑體 ToUnicode 抽取 bug。academic/paper/essay/novel 之 serif
//   身分不受影響（各自獨立分支，見上）。
#let _body  = if profile == "manual" or profile == "default" { _sans } else { _serif }   // 手冊/預設＝sans 內文（CJK 文件退 serif）
#let _head  = if profile == "novel" { _serif } else { _sans }    // 標題 sans（CJK 文件退 serif）；小說全 serif
#let _titlefont = if profile == "novel" { _serif } else { _sans }

// ── 段落模型：academic/paper/essay/novel＝首行縮排（書本感、靠縮排標示段落）；default/manual＝段距 block。
//   ★段距 spacing 是「段落區塊之間」的間距，不是行距 leading；實測在 typst 0.15 設成 = leading（0.7em）
//   會讓下一段首行壓上一段末行（overlap）——typst 段距須清掉一整行 advance（~1em+），不是只 ≥ leading。
//   故 prose 段距＝leading + 0.4em（≈1.1em，緊湊書本節奏、不重疊；隨 leading 旋鈕一起縮放）。
// ★2026-07-08（docspec-issues #10）：default 行距放寬至 1.0em（無 leading 旋鈕覆寫時），
//   貼近 Claude.ai 網頁版舒適閱讀行距；其餘 profile 之 0.7em 基準不變。
#let _lead   = $if(leading)$$leading$$else$(if profile == "default" { 1.0em } else { 0.7em })$endif$
// paper＝雙欄學術版（IEEE/會議/期刊風）；段落模型同 academic（首行縮排）。
#let _twocol = profile == "paper"
#let _prose  = profile == "academic" or profile == "paper" or profile == "essay" or profile == "novel"
// 首行縮排：novel 用 1.5em（≈書籍 0.3"／中文 2 字慣例，比 article 深）；其餘 prose 1em；block 不縮排。
#let _indent = if profile == "novel" { 1.5em } else if _prose { 1em } else { 0pt }
#let _parspace = if _prose { _lead + 0.4em } else { 0.95em }
// 標題編號：essay/novel 不編號（安靜/文學）；★2026-07-08（docspec-issues #09/#10）default 併入
//   不編號陣營——docspec 專案慣例把 §編號直接寫進 concept.title（如「0 系統目標」「1.1 架構設計」），
//   引擎再疊加十進位自動編號會產生雙重編號（真實案例：台中港計畫 system-concept export 實測）。
//   academic/paper/manual 三個仍走引擎編號（未把手寫編號慣例带進 concept.title 的專案受益）。
#let _headnum = if profile == "essay" or profile == "novel" or profile == "default" { none } else { "1.1" }
// 側邊界：paper 雙欄＝窄邊（每欄才夠寬，對齊 IEEE ~1.76cm）；prose 單欄窄版心（行長 62–72 字）；manual 寬些容程式碼/表；
//   ★default 貼近 Claude.ai 聊天氣泡的窄欄閱讀寬度（docspec-issues #10；首版 3.2cm 使用者實測回饋
//   偏窄，調寬至比 essay/novel 的 3.5cm 更寬鬆，欄寬明顯窄於印刷向 profile）。
#let _mx = if profile == "paper" { 1.8cm } else if profile == "manual" { 2.5cm } else if profile == "essay" or profile == "novel" { 3.5cm } else if profile == "default" { 3.8cm } else { 3.0cm }
// 內文字級：paper 雙欄慣例 10pt（欄窄）；其餘 11pt；`fontsize` 旋鈕可覆寫。
#let _bodysize = $if(fontsize)$$fontsize$$else$(if profile == "paper" { 10pt } else { 11pt })$endif$

// 場景分隔（thematic break `---`）：novel＝置中花飾 * * *；★2026-07-08（docspec-issues #10）
//   default＝滿版細線（GitHub/Claude.ai 風）——短置中線（35%–65%）在段落留白已多時，讀者會誤認
//   為浮空的底線（台中港計畫真實審閱回饋，見 issue #10「副帶發現」）；其餘 profile 維持置中細線。
#let horizontalrule = if profile == "novel" {
  align(center)[#v(0.8em) #text(font: _body, tracking: 0.35em)[\* \* \*] #v(0.8em)]
} else if profile == "default" {
  align(center)[#v(0.5em) #line(length: 100%, stroke: 0.5pt + rgb("#d0d7de")) #v(0.5em)]
} else {
  align(center)[#v(0.4em) #line(start: (35%, 0%), end: (65%, 0%), stroke: 0.5pt + rgb("#888888")) #v(0.4em)]
}

#set page(
  paper: "a4",
  margin: (x: _mx, top: 2.6cm, bottom: 2.4cm),
  numbering: "1",
  number-align: center,
  columns: if _twocol { 2 } else { 1 },   // paper＝雙欄；標題/摘要用 place(scope:parent) 跨欄
)
#set columns(gutter: 16pt)               // 欄間距（單欄時無作用）

#set text(
  font: _body,
  size: _bodysize,
  lang: "$if(lang)$$lang$$else$zh$endif$",
  region: _region,                    // 繁體圖說（消費 export 傳的 -V region；缺則 tw house 預設）
  cjk-latin-spacing: auto,            // 漢字↔Latin/數字 自動 ¼em 間距；勿手動插空格
)
#set par(
  justify: true,
  leading: _lead,
  first-line-indent: (amount: _indent, all: false),   // all:false＝標題後/章首首段不縮排
  spacing: _parspace,
)

// 強調＝serif 家族 SemiBold（思源宋有真 SemiBold；不靠合成粗體）
#show strong: set text(font: _serif, weight: "semibold")

// ── 標題：Latin sans（novel serif）──
// ★type-scale 的承重原則：**文件標題必須明顯領先章節標題**，章節層級之間只走小步差，
//   靠「字重＋段前空白」而非「大字級」彼此區分（西方學術慣例：LaTeX article title \LARGE≈1.73×、
//   section \Large≈1.44×；但 title 因獨佔頁首＋作者列分隔而顯著主導）。
//   先前 title 拉丁 1.7／CJK 1.5em、H1 1.4em ⇒ title 只比 H1 大 1.07–1.21×，章節標題視覺上與標題等大
//   （壓測＋人實證的「title 跟 section name 大小不成比例」）。改成 title 大幅領先、H1 收斂：
//   拉丁 title 2.0em（≈22pt on 11pt）／CJK 1.75em（≈19pt，介於中文「小二」18pt 與「二號」22pt，
//   單行置中標題不顯重，且明顯大於 節標題）；paper（雙欄）title 1.7em＝跨兩欄置頂、明顯主導
//   （IEEE 標題本就大；title/H1=1.7/1.15≈1.48×）。title/H1：拉丁 1.54×、CJK 1.35×、paper 1.48×＝清楚階層。
#let _titlesize = if _twocol { 1.7em } else if _sansok { 2.0em } else { 1.75em }
// 用 `set text`（非 text[#it] 包裹）＝沿用原模板已驗證可抽取的結構（包裹會掉末字的 CJK 抽取）。
// weight semibold＝CJK 思源宋真 SemiBold（無 Bold，避免合成假粗體破壞 CJK 抽取；Latin 合成不影響）。
// 標題字級階梯（比例 × 內文 _bodysize＝**絕對長度**，見下方「★em 陷阱」）。中文期刊規範（GB/T 3179）：
//   一級14–15pt／二級12–14pt／三級10.5–12pt（皆黑體）；四級＝五號（＝正文字級）黑體、永不更小＝最深地板。
//   對齊內文 11pt：一級 1.3×＝14.3pt、二級 1.16×＝12.8pt、三級 1.05×＝11.5pt、四級 1.0×＝11pt。
//   paper（雙欄）最收斂（IEEE/ACM＝靠字重不靠大字級）；essay 更安靜。
//   **編號到四級（1.1.1.1）已是極限，五級以下不產出**（render clamp＋check ERROR）。
// ★em 陷阱（本檔踩過、量出來才發現）：typst **內建**就按層級放大 heading（L1≈1.4×／L2≈1.2×／L3+≈1.0×）。
//   若用 `set text(size: 1.3em)`，那個 em 是相對「已被內建放大」的字級 → **相乘**（一級 1.4×1.3=1.82em→20pt，
//   竟比 title 還大）。故 heading 字級一律寫成 **比例 × _bodysize（絕對 pt）**，與內建縮放不相乘。title 不是
//   heading（不受內建縮放）故可續用 em。
#let _h1 = if profile == "paper" { 1.15 } else if profile == "essay" { 1.25 } else { 1.3 }
#let _h2 = if profile == "paper" { 1.05 } else if profile == "essay" { 1.12 } else { 1.16 }
#let _h3 = if profile == "paper" { 1.0 } else { 1.05 }
#let _h4 = 1.0
#set heading(numbering: _headnum)
#show heading: set text(font: _head, weight: "semibold")
// 標題不兩端對齊：justify 是內文設定，會讓「換行的標題」首行被拉開成醜醜的大字距
//   （長英文標題＝壓測實證的「Retrieval-Augmented   Generation   for」）。標題一律 ragged。
#show heading: set par(justify: false)
// ×_bodysize＝絕對長度，避開上述 em 與內建縮放相乘的陷阱
#show heading.where(level: 1): set text(size: _h1 * _bodysize)
#show heading.where(level: 2): set text(size: _h2 * _bodysize)
#show heading.where(level: 3): set text(size: _h3 * _bodysize)
// 四級＝最深層：字級鎖在內文（_h4 × body＝1.0×）、永不更小（中文期刊地板）
#show heading.where(level: 4): set text(size: _h4 * _bodysize)
// novel 章首：換頁＋下沉＋置中（覆寫 level-1；首段不縮排由 par all:false 處理）
#show heading.where(level: 1): it => if profile == "novel" {
  pagebreak(weak: true)
  v(30%)   // 章首下沉約 ⅓（書籍 chapter-opener 慣例：標題起於頁面 ⅓–½ 處）
  align(center)[#text(font: _serif, weight: "regular", size: 1.6 * _bodysize)[#it.body]]
} else {
  block(above: 1.5em, below: 0.6em)[#it]
}
// 標題段前間距＝約一行（對齊中文「段前空一行」；> 段距 1.1em 才與內文分隔）；段後較小＝把標題綁在其後文字。
#show heading.where(level: 2): it => block(above: 1.25em, below: 0.5em)[#it]
#show heading.where(level: 3): it => block(above: 1.05em, below: 0.45em)[#it]
// 四級＝最深層、內文字級地板：靠段前空白＋編號區分（非縮小字級）。五級以下不產出（render clamp＋check）。
#show heading.where(level: 4): it => block(above: 0.95em, below: 0.32em)[#it]

// 程式碼＝Source Code Pro（CJK fallback 思源宋）
#show raw: set text(font: _mono, size: 0.92em)
// 程式碼區塊＝GitHub 風淺灰底＋圓角＋內距＋滿欄。原本 raw block 無容器、貼齊內文左界、
//   與散文糊在一起像沒排版（壓測實證的醜）。fill/inset/radius 不動文字內容＝不影響 byte-lock。
#show raw.where(block: true): it => block(
  fill: rgb("#f6f8fa"), inset: (x: 10pt, y: 8pt), radius: 4pt,
  width: 100%, stroke: 0.5pt + rgb("#d0d7de"),
)[#it]
// 行內程式碼＝淡灰底小圓角（與散文區隔，不喧賓）
#show raw.where(block: false): box.with(
  fill: rgb("#eff1f3"), inset: (x: 3pt), outset: (y: 3pt), radius: 2pt,
)

// 表格＝GitHub 風：表頭淺灰底＋粗體、細灰格線、cell padding 舒服、整表置中
#set table(
  inset: (x: 8pt, y: 6pt),
  stroke: 0.5pt + rgb("#d0d7de"),
  align: left + horizon,
)
#show table.cell.where(y: 0): set text(weight: "bold")
#show table.cell.where(y: 0): set table.cell(fill: rgb("#f6f8fa"))
// ★表格內：不對齊兩端＋不自動斷字。窄欄 + justify + 連字號＝整欄硬斷成「parti-tion」
//   「exe-cution」（壓測實證的醜）。表格欄寬由 export 把 pandoc 等分百分比改 auto（依內容定寬），
//   cell 文字改 ragged-right（不 justify、不 hyphenate）＝乾淨、保留完整單字。
#show table.cell: set par(justify: false)
#show table: set text(hyphenate: false)
#show figure.where(kind: table): set align(center)
#show figure.where(kind: image): set align(center)
// 高表格（pandoc 把表包成不可分頁的 #figure）→ 允許跨頁，否則底列溢出/疊行、前頁留近空白的孤兒標題頁
#show figure.where(kind: table): set block(breakable: true)
#show figure.caption: set text(size: 0.9em)   // 圖說 body−1~−2、label 由 figure 加粗
#set figure(numbering: "1")

// ── paper（雙欄）圖表浮動：自動依內容寬決定跨欄、一律浮頁頂（＝LaTeX table*/table[t] 行為）──
//   量圖表「自然寬」（不設限＝auto 欄展開到內容最大需求寬）：> 單欄寬就 scope:"parent" 跨兩欄、
//   否則留單欄；兩者都 float 到頁頂（使用者要再調整 placement 另說）。單欄 profile 不動。
//   ★單欄寬要自己從頁幾何算（layout(size) 給的是整個文字區寬≈兩欄，不是單欄）：colw=(頁寬−2邊界−欄距)/2。
#show figure: it => if _twocol {
  context {
    let colw = (210mm - 2 * _mx - 16pt) / 2          // a4 寬 − 兩側邊界 − 欄距，再除二
    if measure(it.body).width > colw {
      place(top, float: true, scope: "parent", it)   // 寬＝跨兩欄
    } else {
      place(top, float: true, it)                     // 窄＝留單欄、浮頂
    }
  }
} else { it }

// ── 標題區塊 ──
// 文件標題＝最大元素（拉丁 2.0em／CJK 1.75em，明顯 > H1 1.3em），字級隨內文 base_size 縮放＝層級恆定。
$if(title)$
// 標題區塊：scope 內關 justify＝長標題換行首行不被拉開。雙欄(paper)＝place(scope:"parent",float)
//   把標題/作者浮到頁頂跨兩欄（IEEE 慣例）；單欄＝直接擺。
#let _titleblock = [
  #set par(justify: false)
  #align(center)[
    #text(font: _titlefont, weight: "semibold", size: _titlesize)[$title$]
  ]
  $if(subtitle)$
  #v(0.3em)
  #align(center)[#text(font: _titlefont, size: 1.15em, fill: rgb("#57606a"))[$subtitle$]]
  $endif$
  $if(author)$
  #v(0.6em)
  #align(center)[#text(size: 11pt)[$for(author)$$author$$sep$ · $endfor$]]
  $endif$
  $if(date)$
  #v(0.2em)
  #align(center)[#text(size: 10pt, fill: rgb("#57606a"))[$date$]]
  $endif$
  #v(1.0em)   // 標題區塊與正文的間距：約一行（先前 1.6em 過大、標題顯得跟內文脫節）
]
#if _twocol {
  place(top + center, _titleblock, float: true, scope: "parent")
} else {
  _titleblock
}
$endif$

$for(header-includes)$
$header-includes$

$endfor$
$body$
