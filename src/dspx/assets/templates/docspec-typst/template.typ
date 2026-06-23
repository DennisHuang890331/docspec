// docspec-typst — docspec 自帶的 Typst 交付模板（pandoc typst-writer template）。
// 統一字型（最穩、零缺字）：CJK＝思源宋體（Source Han Serif TC，字數全＋有真 SemiBold）、
// 拉丁＝Source Serif 4（同 Adobe Source 家族）、程式碼＝Source Code Pro。標題/內文/強調
// 同一家族，只靠字級與字重區分（不再混 TW-Sung/TW-Kai，避免缺字 tofu 與混體）。
// pandoc 變數（title／body／author 等）由 export 經 -V 注入；字型靠 typst --font-path 受控字型夾。
// ★編譯一律 --ignore-system-fonts，故這裡的 family 名只會解析到 bundled 字型（確定性）。

$if(highlighting-definitions)$
$highlighting-definitions$

$endif$
#let _serif = ("Source Serif 4", "思源宋體")
#let _mono = ("Source Code Pro", "思源宋體")

#set page(
  paper: "a4",
  margin: (x: 2.2cm, top: 2.6cm, bottom: 2.4cm),
  numbering: "1",
  number-align: center,
)

#set text(
  font: _serif,
  size: $if(fontsize)$$fontsize$$else$11pt$endif$,
  lang: "$if(lang)$$lang$$else$zh$endif$",
)
#set par(justify: true, leading: $if(leading)$$leading$$else$0.95em$endif$)

// 強調＝同家族 SemiBold（思源宋體有真 SemiBold，不靠合成）
#show strong: it => text(font: _serif, weight: "semibold")[#it.body]

// 標題＝同家族 SemiBold；字級階梯由內文衍生，溫和遞減（×1.30/1.15/1.05/1.0）。
// 刻意比舊版（1.45/1.25/1.10）收斂：避免 section 標題壓過文件標題（見下方 title=1.45em）。
#show heading: set text(font: _serif, weight: "semibold")
#set heading(numbering: "$if(heading-numbering)$$heading-numbering$$else$1.1$endif$")
#show heading.where(level: 1): set text(size: 1.30em)
#show heading.where(level: 2): set text(size: 1.15em)
#show heading.where(level: 3): set text(size: 1.05em)
#show heading: it => block(above: 1.1em, below: 0.6em)[#it]

// 程式碼＝Source Code Pro（CJK fallback 思源宋體）
#show raw: set text(font: _mono, size: 0.92em)

// 表格＝GitHub 風：表頭淺灰底＋粗體、細灰格線、cell padding 舒服、整表置中
#set table(
  inset: (x: 8pt, y: 6pt),
  stroke: 0.5pt + rgb("#d0d7de"),
  align: left + horizon,
)
#show table.cell.where(y: 0): set text(weight: "bold")
#show table.cell.where(y: 0): set table.cell(fill: rgb("#f6f8fa"))
#show figure.where(kind: table): set align(center)
#show figure.where(kind: image): set align(center)
#set figure(numbering: "1")

// ── 標題區塊 ──
// 文件標題＝最大元素（1.45em，比 level-1 heading 的 1.30em 大），字級隨內文 base_size 縮放，
// 故 base_size 調小時標題與整份一起縮，永遠維持 title > H1 > H2 > H3 > 內文 的層級。
$if(title)$
#align(center)[
  #text(font: _serif, weight: "bold", size: 1.45em)[$title$]
]
$if(subtitle)$
#v(0.3em)
#align(center)[#text(font: _serif, size: 1.1em, fill: rgb("#57606a"))[$subtitle$]]
$endif$
$if(author)$
#v(0.6em)
#align(center)[#text(size: 11pt)[$for(author)$$author$$sep$ · $endfor$]]
$endif$
$if(date)$
#v(0.2em)
#align(center)[#text(size: 10pt, fill: rgb("#57606a"))[$date$]]
$endif$
#v(1.4em)
$endif$

$for(header-includes)$
$header-includes$

$endfor$
$body$
