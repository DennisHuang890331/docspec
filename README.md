<div align="center">

<img src="docs/assets/logo.png" alt="docspec logo" width="200">

### docspec — 跟 AI agent 一起寫長篇技術文件，愈寫愈長也不走樣，最後匯出乾淨的 Markdown 或排版完整的 PDF

![CI](https://github.com/DennisHuang890331/docspec/actions/workflows/test.yml/badge.svg) ![Python](https://img.shields.io/badge/python-%E2%89%A53.11-blue) ![License](https://img.shields.io/badge/license-PolyForm%20NC%201.0.0-orange) ![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey)

[English](README.en.md) · [中文](README.md)

</div>

docspec 是給長篇技術文件用的 spec-driven 撰寫工具，要解決的是「漂移」：文件愈長，前面某節一改，後面某節就悄悄跟它對不上，往往要等讀者發現才有人知道。用 docspec，你和 agent 先在結構化的後台敲定每一節的概念與決策，再由一層薄的確定性引擎渲染成散文；上游一改，引擎就點名哪些節因此過期。你只審結構，只讀渲染出來的成品。

> 採 PolyForm Noncommercial 1.0.0，source-available：非商業用途免費；商業使用須另行取得授權。見[授權](#-授權)。

## ✨ 重點

- 🌱 **長了也不走樣。** 不論改一節、改一條共享決策，還是改全域文風，引擎都會指出哪些節因此過期、為什麼過期。它追蹤的是每一節所依賴內容的雜湊值，不是檔案的修改時間；Google Drive、OneDrive 每次同步都會改寫時間戳，專案放在裡面照樣判得準。
- 🧱 **先結構、後散文。** 每一節都是盲渲染：agent 只看得到這一節自己的後台，外加引擎算好的一份投影——也就是這節必須遵守的上游事實；文件整體長到多大，它都看不到。各節要一致，靠的是一份共用的寫作守則，不是反覆重讀全文。所以文件再長，寫一節、改一節，費的工都差不多。
- ⚙️ **確定性引擎，不靠 LLM 打分。** 它只擋自己能百分之百判定的機械性錯誤：死引用、相依環、缺欄或格式壞掉的欄位、內部術語洩漏、`[TBD]` 殘留。凡取決於文意的，一律只給非阻塞的提示，不設閘門；也因為它只擋斷得定的錯，真正擋下來的才值得信。
- 🧹 **交付物潔淨。** 內部 id、鷹架、佔位符、殘留的後台術語一旦洩進散文，publish 就拒絕執行。另有一道非阻塞 lint，照固定字表標出常見的 AI 腔詞——只標不擋，算不算問題由你判斷。
- 📄 **可驗證的 PDF。** 匯出時，引擎會回頭核對成品 PDF：原文少一個字元就判失敗。渲染悄悄吃掉 CJK 文字這種事，當下就攔下來，不會出貨到讀者手上。PDF 預設由 Typst 渲染；要投稿期刊，也能改成 emit 一份 `.tex`。
- 🔗 **整組文件一起同步。** 用 `governed-by` 和 `realizes` 把相關文件連起來；上游文件一改，過期狀態會一路傳到每一個依賴它的下游節。整組規格裡哪些該重新同步一目了然，不會無聲地各自漂走。

## 📚 成品展示

六份文件，橫跨三種文體、兩種語言，每一份都是 agent 從零用 docspec 寫出來的，結構、潔淨、渲染忠實度各道閘全過，最後出成排版完整的 PDF。

| 文體 | 語言 | 讀全文 | PDF |
|---|---|---|---|
| 小說——短篇 | 正體中文 | [讀](docs/showcase/deliverables/novel-zh.md) | [PDF](docs/showcase/pdfs/novel-zh.pdf) |
| 小說——短篇奇幻 | 英文 | [讀](docs/showcase/deliverables/novel-en.md) | [PDF](docs/showcase/pdfs/novel-en.pdf) |
| 隨筆 | 正體中文 | [讀](docs/showcase/deliverables/essay-zh.md) | [PDF](docs/showcase/pdfs/essay-zh.pdf) |
| 隨筆 | 英文 | [讀](docs/showcase/deliverables/essay-en.md) | [PDF](docs/showcase/pdfs/essay-en.pdf) |
| 學術綜述 | 正體中文 | [讀](docs/showcase/deliverables/academic-zh.md) | [PDF](docs/showcase/pdfs/academic-zh.pdf) |
| 學術綜述 | 英文 | [讀](docs/showcase/deliverables/academic-en.md) | [PDF](docs/showcase/pdfs/academic-en.pdf) |

用了哪些模型、怎麼跑、完整 prompt 是什麼，都在 [docs/showcase/](docs/showcase/)；連做得不夠好的地方也照實交代。

## 🚀 快速開始

需要 `uv` 與 Python ≥ 3.11（Windows／Linux 已測，macOS 尚未實機驗證）。

```bash
uv tool install git+https://github.com/DennisHuang890331/docspec
uv tool update-shell          # 把 uv 的工具 bin 加進 PATH（只需一次），再開新終端
docspec init                  # 建專案；裝進 Claude Code、Codex 或 Antigravity（擇一，或 --tool all 全裝）
```

寫作全在 agent 對話裡走內建 skill，你親手要打的 docspec 指令，只有安裝與維護那幾個：

| 指令 | 做什麼 |
|---|---|
| `docspec init` | 建專案、把 skill 裝進 agent |
| `docspec setup` | 下載 PDF 排版工具鏈（只在要出 PDF 時） |
| `docspec doctor` / `upgrade` / `version` | 環境體檢 / 對齊受控 PDF 工具鏈 / 看版本 |

`docspec --help` 列的是這些給人用的指令，agent 在背後用的完整清單則在 `docspec --help-all`。注意 `docspec setup` 對齊的是 PDF 工具鏈（冪等，且會對齊已裝資產），而不是 docspec 程式本身；要更新 docspec，重跑上面的安裝指令即可。

## 🧠 運作方式

docspec 專案分兩層。**後台**（`corpus/`）每節放幾個 YAML 檔：一段簡短的概念、這節的決策，還有一份 brief，定出受眾、深度、廣度。**前台**（`docs/`）是渲染出來的散文，一份文件一個檔，由各節組裝而成。兩層分開正是重點：你審結構與決策，不必在潤過的散文裡打撈；散文從結構重新生成，不必另外再維護一份。**你只讀前台。**

```text
myproject/
├─ docspec/corpus/peft-survey/       # 後台——給 agent 和引擎
│  └─ lora-family/                    #   一個末節
│     ├─ concept.yaml                 #     概念 + brief
│     └─ decisions.yaml               #     這節的決策
└─ docs/peft-survey_latest.md         # 前台——渲染出的散文（你只讀這個）
```

引擎把這些 YAML 渲染成散文：

```yaml
# corpus/peft-survey/lora-family/concept.yaml
title: "低秩重參數化：LoRA 及其變體"
concept: "把 LoRA 及其後續方法，統一看成一個注入凍結權重矩陣的低秩更新。"
brief:
  audience: 與綜述其餘章節相同的技術讀者
  depth: 機制層——說清楚分解方式，以及為什麼可以合併
  breadth: "LoRA、QLoRA、AdaLoRA、DoRA、VeRA——並非每個變體"
# corpus/peft-survey/lora-family/decisions.yaml
entries:
  - id: dec-lora-merge
    statement: "LoRA 的更新活在權重空間，訓練後可併回凍結矩陣；併好的模型不增加任何推論延遲。"
```
```markdown
# docs/peft-survey_latest.md（渲染出來的；你只讀這個）
## 低秩重參數化：LoRA 及其變體
……這個低秩更新直接加進權重空間裡的凍結矩陣，因此可以永久併入；除了基礎模型本身既有的開銷之外，不增加任何延遲。
```

這段是簡化版；真實的 `concept.yaml` 還會帶 `id`、`order`、`status`，每條決策也有 `kind` 與 `status`。欄位是固定的一套：多打一個引擎不認得的欄位，`check` 直接報錯，不會默默吞掉。章節 id 與內容無關且永久固定，把一節搬走或改名，指向它的引用都不會斷。

過期狀態沿四條軸傳遞，`docspec status` 逐節標出：這節自己的源料變了（own）、它 `realizes` 的決策變了（upstream）、上層某節的 brief 變了（inherited）、共用的寫作守則或 glossary 變了（style）。每一軸都對應到該做的修法——該重寫的重寫，只需重套文風的重套。

## ✍️ 撰寫流程

你在 agent 對話裡說要寫什麼，它呼叫五個 skill，引擎在背後把關：

| skill | 做什麼 |
|---|---|
| **develop** | 長出／重整一節的概念與決策（受眾、深度、廣度）；先有骨架，不寫散文 |
| **apply** | 將一節對齊其來源：rewrite 模式盲渲染散文（原 draft）、align 模式潤稿與對齊（原 edit） |
| **factcheck** | 對抗式查核，每條主張對一手來源；只標記、不擋發行 |
| **publish** | 不可逆發行：所有閘綠 → 凍結唯讀快照 → 升版 → 記 changelog |
| **release** | 互動排版：匯出 → 看頁面圖 → 調旋鈕 → 重出 |

這是迴圈，不是流水線：factcheck 抓到問題，工作就退回 develop 或 apply，再重新走回 publish。節要晉級也得整批過關：develop 階段的思考草稿要先榨乾、欄位齊全，`docspec ready` 才放行，所以引擎的索引裡不會有看起來完成、其實還空著的節。agent 遵循的完整契約（欄位、流程、規則）由 `docspec guide` 即時投影，不靠會過時的說明文件。

## 📄 匯出 PDF

裝上 export 相依套件，跑一次 setup。setup 會把受控工具鏈下載進使用者資料夾，不碰你的系統環境：

```bash
uv tool install "docspec[export] @ git+https://github.com/DennisHuang890331/docspec"
docspec setup
```

**預設 Typst。** docspec 自帶一套自家風格的 Typst 模板，原生 CJK、不依賴 LaTeX，還附隨筆、手冊、小說、學術論文等版面 profile。`docspec export <article>` 出 PDF 時會拿成品跟源料逐位元核對；渲染掉字，匯出當下就擋，不會留給讀者去發現。

**帶你自己的期刊模板。** docspec 還有一條「只 emit 不代編」的期刊軌，供投稿用：它填一份固定的 slot 契約（標題、作者、摘要、關鍵詞、正文），再寫出一份 `.tex` 給 Overleaf 或你自己的 LaTeX 工具鏈。內建 IEEE、Elsevier、IET 的 adapter，這幾本期刊用 `docspec export <article> --journal ieee` 就夠了。要用 docspec 沒內建的期刊，把那本期刊的 LaTeX 模板放進一個資料夾，傳 `--template <dir>`；release skill 會先讀該期刊自帶的 sample `.tex`，把你文章的標題、作者、摘要、關鍵詞、正文，對映到期刊自己的巨集上。這樣 emit 出來的 `.tex`，用期刊自己的流程就編得起來；編譯由你自己來。

## 📐 工程圖

工程圖是文件的一部分，不是匯出時才硬加上去的。哪一節需要圖，`apply` 就交給專門的繪圖 skill **dspx-diagram**，由它畫成 draw.io 原生檔，再渲成高解析 PNG 嵌進交付物。落到頁面上的是向量的方塊與連線，不是 ASCII 圖，也不是沒渲染的 mermaid 區塊。要用繪圖功能，先跑一次 `docspec setup --with-drawio` 把繪圖器裝好。

## ✂️ 刻意不做什麼

引擎從不判斷語義。沒有「這段對不對」的語義閘、沒有 verbatim transclude、沒有文類型別系統——這些都認真評估過，最後刻意砍掉。連過期狀態也只作用在內容的位元層：兩節後來彼此矛盾、卻沒有任何一節的源料變動，引擎不會出聲；要調和，是 factcheck 的事——它只標記、不擋路，不是閘門。正因為引擎只裁決機械上能確定的事，它才是一道你信得過的閘；文意層的問題，全部留給人判斷。

## 📜 授權

docspec 採 **PolyForm Noncommercial 1.0.0**：個人寫作、學術研究、學生專題、開源專案文件、不收費的社群分享皆免費。商業使用（販售所寫內容、作為公司知識庫、撰寫商業產品的規格文件）須另向作者取得授權。本專案為 source-available，非 OSI 定義的開源。第三方元件見 [`LICENSE`](LICENSE) 與 [`NOTICE.md`](NOTICE.md)。

## 🙏 致謝

docspec 是 [OpenSpec](https://github.com/Fission-AI/OpenSpec) 的 prose-first 衍生版本，可獨立運作，不依賴 OpenSpec（OpenSpec 只用在 docspec 自身的開發上）。

docspec 由作者負責設計，程式實作與測試由 Anthropic 的 [Claude](https://claude.com/claude-code)（Claude Code）完成。
