<div align="center">

# docspec

**跟 AI agent 一起寫長篇技術文件，產出乾淨的 Markdown 與排版完整的 PDF，過程中保持前後一致。**

![Python](https://img.shields.io/badge/python-%E2%89%A53.11-blue)
![License](https://img.shields.io/badge/license-PolyForm%20NC%201.0.0-orange)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey)
<!-- TODO: repo 公開後補 CI 徽章 https://github.com/<owner>/docspec/actions -->

English: [README.en.md](README.en.md)

</div>

你跟 agent 先把每一節的邏輯與決策講清楚，docspec 再把它渲染成散文，同時守住結構。文件變長時不容易自相矛盾。你只看渲染出來的成品，後台的細節交給 agent。

## 這給誰用

- 想跟 AI agent 共筆一份會持續成長的長篇技術文件或手冊，但擔心它愈寫愈不一致、前後矛盾。
- 在維護多章節的規格或 wiki，需要全篇前後一致，改一處不會讓別處悄悄失準。
- 最後要的是一份能交付的 PDF，排版要完整，不只是一份 Markdown。

## 看它跑起來

你主要是在 AI agent（Claude Code / Antigravity / Codex）的對話裡呼叫內建 skill，引擎在背後把關：

```text
你： 我要寫一份 zenoh 控制平面的技術文件，先用 develop 起大綱
AI： [develop] 建好 corpus/zenoh/intro/，記下骨架（這步不寫散文）
        ├─ 概念：為什麼用 zenoh 當控制平面
        └─ 決策：控制平面用 zenoh、不用 MQTT

你： 大綱可以，draft 這一節
AI： [draft] 盲渲染成散文 → docs/zenoh/_latest.md

你： publish
AI： [publish] 所有閘門綠 → 凍結 v1 唯讀快照、升版、記 changelog

你： 出成 PDF
AI： [release] 匯出 → 看頁面圖 → 調排版旋鈕 → docs/exports/zenoh.pdf
```

<!-- TODO: 放一張 docs/exports/zenoh.pdf 的頁面截圖（zenoh dogfood 樣本） -->
> 📄 **成品長這樣：**（PDF 頁面截圖待補）

## 快速開始

> **需要** `uv` ＋ Python ≥ 3.11。Windows / Linux 已測，macOS 尚未實機驗證。

```bash
git clone <repo-url> && cd docspec
uv tool install --from . docspec
uv tool update-shell          # 把 uv 的工具 bin 加進 PATH（只需一次），再開新終端
docspec init --tool claude    # 建工作目錄並把 skill 裝進你的 agent
```

裝完之後，寫作流程都在你的 agent 對話裡進行，走六個 skill：develop → draft → edit → factcheck → publish，要 PDF 再多一步 release。你不是自己去打 `docspec publish`，而是在對話裡叫 agent 執行，引擎在背後把關。其中 publish 不可逆，那個板機留在人手上——要你點頭它才會真的凍結發行。

你真正會親手敲的 CLI，是安裝與維護那幾個：

| 指令 | 做什麼 |
|---|---|
| `docspec init` | 開專案、把 skill 裝進 agent |
| `docspec setup` | 下載 PDF 排版資產（只在要出 PDF 時） |
| `docspec doctor` / `upgrade` / `version` | 體檢 / 更新 / 看版本 |

`docspec --help` 列的就是這些給人用的指令；agent 在背後用的完整清單，要 `docspec --help-all` 才看得到。

## 你用到的六個 skill

skill 只給判斷與態度。欄位、格式、流程這些機械細節不寫死在 skill 裡，而是由 `docspec guide` 即時投影出來。

| skill | 做什麼 | 什麼時候用 |
|---|---|---|
| **develop** | 長出、重整章節的概念與決策大綱（受眾、範圍、深度）。先有骨架，不寫散文。 | 開新文件、或重整結構 |
| **draft** | 把一節寫成散文，一次只看那一節的脈絡，所以不會去引用看不到的鄰節而出錯。 | 結構定了，要寫散文 |
| **edit** | 出版社式潤稿：逐行 → 文句 → 校對。 | 散文寫好、要打磨 |
| **factcheck** | 對抗式查核，每條主張都對一手來源。只標記、不改，也不擋發行。 | 任何時候想驗證 |
| **publish** | 不可逆發行：所有閘綠 → 凍結唯讀快照 → 升版 → 記 changelog。 | 一版定稿了 |
| **release** | 互動排版：匯出 → 看頁面圖 → 調旋鈕 → 重出。只動呈現，不動內容。 | 要產 PDF |

這是一個迴圈，不是流水線。factcheck 抓到問題，就退回 develop 或 draft。

## 產出 PDF

PDF 交付是 docspec 的重點之一。先把 export 相依裝上，再跑一次 `docspec setup`，它會下載受控的排版資產（TinyTeX ＋ OFL 字型），裝進使用者資料夾，不碰你的系統環境：

```bash
uv tool install --from . docspec --with pdfplumber --with pypdfium2 --with pypandoc_binary
docspec setup
```

接著在 agent 裡用 release skill 互動調版：匯出 → 看頁面圖 → 調排版旋鈕 → 重出，調到滿意為止。（底層的 `docspec export` 是 agent 指令，由 skill 驅動，不必你親手打。）

## 三家 agent，一套 skill

`docspec init` 會把同一套 SKILL.md 裝進 Claude Code、Antigravity、Codex 三家，技能目錄結構一致，所以同一套寫作守則在哪家 agent 都能用。

<details>
<summary><b>原理：它怎麼做到不矛盾（想深入再點開）</b></summary>

用 AI 寫文件最常見的失敗，是它一邊想邏輯一邊雕字，最後產出讀起來很順、卻空洞又自相矛盾的東西；而你明明只想先看邏輯對不對，卻被迫先讀一大篇潤過的散文。docspec 把這兩件事拆開：

- **後台 `corpus/`（給 agent 和引擎）**：每個章節用幾個結構化小檔，記「一句話概念＋寫作邊界（brief：給誰看、寫多深）＋它實現了哪些決策」。這層只在乎邏輯嚴謹、事實完整，不管文筆。
- **前台 `docs/`（給人）**：把後台盲渲染成散文成品——每一節獨立寫、看不到鄰節。**人只讀這層。**

章節有穩定 id，搬資料夾或改名都不會斷引用。跨章節的連貫不靠 agent 互相偷看，而是靠一份共用的寫作守則加上確定性的組裝。

```text
corpus/zenoh/intro/concept.yaml          docs/zenoh/_latest.md（渲出來、給人讀的）
  concept: 為什麼用 zenoh 當控制平面    ──▶   ## 為什麼用 zenoh 當控制平面
  brief:  {audience: 開發者, depth: 概念}        zenoh 以 pub/sub 取代輪詢……
corpus/zenoh/intro/decisions.yaml                （依 brief 與決策生成，只放決策說的）
  - statement: 控制平面用 zenoh、不用 MQTT
```

引擎只做確定性的把關（結構、完整性）；內容語義對不對，交給不擋路的 factcheck。
</details>

## 為什麼用 docspec

- **先審邏輯，再審文筆**：你檢查的是大綱與決策，不是一整面潤過的散文。
- **人只讀 `docs/` 成品**，後台 `corpus/` 的細節留給 agent 和引擎。
- **引擎只擋結構、不擋語義**：機械漂移由它確定性攔下，事實對錯靠非阻塞的查核去標記，不卡你發行。

## 開發 / 貢獻

歡迎開 issue 或 PR。開發環境、如何跑測試，以及 Windows 加非 ASCII 路徑為什麼要用 `uv run --no-editable`，都寫在 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 授權

**PolyForm Noncommercial 1.0.0**：任何非商業用途免費，商業使用需另外向作者取得授權。這是 source-available 的非商業授權，不是 OSI 定義的那種「開源」。隨附的第三方元件各自保留原授權，詳見 [`LICENSE`](LICENSE) 與根目錄的 [`NOTICE.md`](NOTICE.md)。

## 致謝

docspec 改寫自 [OpenSpec](https://github.com/Fission-AI/OpenSpec)，獨立運作、不依賴它。感謝 OpenSpec 團隊先做出了 spec-driven 的 AI agent 工作流，才有這個 prose-first 的衍生版本。
