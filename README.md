# docspec

English: [README.en.md](README.en.md)

給 AI agent 和人一起寫**文件**的 spec-driven 工具。把工程界「先把規格定清楚、再實作」的紀律搬到寫作上：讓 agent 先想清楚邏輯（這節在講什麼、根據哪些決策），再渲染成乾淨的散文給人讀。引擎只做確定性的把關，語義對錯交給不擋路的查核。

改寫自 [OpenSpec](https://github.com/Fission-AI/OpenSpec)，專門為人＋AI 共筆技術文件、wiki、規格而調整。獨立運作，不依賴 OpenSpec。

> **狀態**：早期、單人維護、用 git 安裝（沒有 PyPI release）。需要 `uv` ＋ Python ≥ 3.11。Windows／Linux 有測，macOS 尚未實機驗證。

## 核心想法

用 AI 寫文件最常見的失敗，是它一邊想邏輯一邊雕字，最後產出「讀起來順、但空洞又自相矛盾」的東西；而且你只想先看邏輯對不對，卻被迫先讀一大篇潤過的散文。

docspec 把這兩件事拆開，各管各的：

- **後台 `corpus/`（給 agent 和引擎）**：每個章節用幾個結構化小檔，記「一句話概念＋寫作邊界＋它實現了哪些決策」。這層只在乎邏輯嚴謹、事實完整，不在乎文筆。
- **前台 `docs/`（給人）**：把後台**盲渲染**成散文成品。**人只讀這層。**

章節有穩定 id，搬資料夾或改名都不會斷引用。跨章節的連貫不靠 agent 互相偷看，而是靠一份共用的寫作守則 ＋ 確定性的組裝。

大概長這樣——你（透過 agent）填後台的結構化小檔，docspec 渲出前台散文：

```
corpus/zenoh/intro/concept.yaml          docs/zenoh/_latest.md（渲出來、給人讀的）
  concept: 為什麼用 zenoh 當控制平面    ──▶   ## 為什麼用 zenoh 當控制平面
  brief:  {audience: 開發者, depth: 概念}         zenoh 以 pub/sub 取代輪詢……（依 brief
corpus/zenoh/intro/decisions.yaml                與決策生成；只放決策說的、不自己編）
  - statement: 控制平面用 zenoh、不用 MQTT
```

## 你怎麼用它：六個 skill

實際的工作流是六個內建 **skill**，裝進你的 AI agent（Claude Code / Antigravity / Codex）。你在對話裡叫它們，引擎在背後把關。skill 本身只給**判斷與態度**；機械細節（欄位、格式、流程）由 `docspec guide` 即時投影，不寫死在散文裡漂走。

| skill | 做什麼 | 什麼時候用 |
|---|---|---|
| **develop** | 發展編輯。長出、重整章節的概念與決策大綱（受眾、範圍、深度、結構）。先有骨架，這一步不寫散文。 | 開新文件、或要重整結構 |
| **draft** | 盲渲染散文。一次一節，只看投影給它的脈絡，不偷看別節——所以不會去引用看不到的鄰節而出錯。 | 結構定了，要把某節寫成散文 |
| **edit** | 出版社式潤稿：逐行 → 文句 → 校對。確定性的事交引擎，要判斷的才派乾淨的子代理。 | 散文寫好、要打磨 |
| **factcheck** | 對抗式查核。每條主張都對一手來源、攻擊大綱的缺漏與矛盾。**只標記、不改**，而且不擋發行。 | 任何時候想驗證 |
| **publish** | 不可逆發行（你扣板機）。所有閘全綠 → 凍結唯讀快照 → 升版 → 記 changelog。 | 一版定稿了 |
| **release** | 互動排版。把凍結的快照排成交付 PDF：匯出 → 看頁面圖 → 調格式旋鈕 → 重出，直到好看。只動呈現，不動內容。 | 要產 PDF 交付 |

這是**迴圈**，不是流水線：factcheck 抓到問題，就退回 develop 或 draft。

## 安裝

docspec 是獨立 CLI（套件名 `dspx`、指令名 `docspec`），透過 git 安裝（PyPI 名稱已被佔用）。

```bash
git clone <repo-url> && cd docspec
uv tool install --from . docspec
uv tool update-shell      # 把 uv 的工具 bin 加進 PATH（只需一次），然後開新終端
docspec --version
```

改了原始碼要重裝、吃到最新版（`--no-cache` 不可省，否則 uv 給你快取的舊 wheel）：

```bash
uv tool install --from . docspec --reinstall --no-cache
```

要產 PDF 的話，多裝 export 相依，並跑一次 `docspec setup` 下載受控排版資產（TinyTeX ＋ OFL 字型，裝進使用者資料夾，不碰系統環境）：

```bash
uv tool install --from . docspec --with pdfplumber --with pypdfium2 --with pypandoc_binary
docspec setup
```

## 快速開始

```bash
docspec init --tool claude     # 建工作目錄，並把 skill 裝進你的 agent（省略 --tool 會互動詢問）
```

接著主要在 agent 裡走 develop → draft → edit → factcheck → publish（要 PDF 再 release）。

你（人）平常其實只碰三個指令，其餘都是 agent 透過 skill 自己呼叫的：

- `docspec init` — 開專案
- `docspec publish <article>` — 定稿發行（不可逆，你扣板機）
- `docspec export <article>` — 出 PDF

`docspec --help` 只列這些給人的指令；完整清單（給 agent 的）在 `docspec --help-all`。

## 三家 agent，一套 skill

`docspec skills install`（`init` 會自動跑）把同一套 SKILL.md 裝進 Claude Code、Antigravity、Codex，三家的技能目錄結構一致，所以同一套寫作守則在哪家都能用。

## 開發／貢獻

歡迎開 issue 或 PR。開發環境、跑測試、以及 Windows＋非 ASCII 路徑為什麼要用 `uv run --no-editable`，都寫在 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 授權

**PolyForm Noncommercial 1.0.0** — 任何**非商業**用途免費（個人、研究、教育、非營利、政府機關）；**商業使用需另外向作者取得授權**。詳見 [`LICENSE`](LICENSE)。這是 source-available、非商業授權，不是 OSI 定義的「開源」。

隨附的第三方元件各自保留原授權：PDF 模板的 document class（`docspec-cas`）是**改自** Elsevier CAS class 的修改版，依 LPPL 1.3c 規定**重新命名**後散布（見 [`NOTICE.md`](src/dspx/assets/templates/docspec-cas/NOTICE.md)）；字型為 SIL OFL 1.1 或政府開放資料（`docspec setup` 時下載，見 [`FONT-LICENSES.md`](src/dspx/assets/templates/docspec-cas/fonts/FONT-LICENSES.md)）。

## 致謝

docspec 站在 [OpenSpec](https://github.com/Fission-AI/OpenSpec) 的概念與原則上——感謝 OpenSpec 團隊先做出 spec-driven 的 AI agent 工作流，才有這個 prose-first 的衍生版本。
