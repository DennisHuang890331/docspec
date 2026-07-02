<div align="center">

# docspec

**跟 AI agent 一起寫長篇技術文件，全篇保持前後一致，產出乾淨的 Markdown 與排版完整的 PDF。**

![Python](https://img.shields.io/badge/python-%E2%89%A53.11-blue)
![License](https://img.shields.io/badge/license-PolyForm%20NC%201.0.0-orange)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey)
<!-- TODO: repo 公開後補 CI 徽章 https://github.com/<owner>/docspec/actions -->

[English](README.en.md) · [中文](README.md)

</div>

> [!WARNING]
> **非商業授權。** docspec 採 PolyForm Noncommercial 1.0.0 授權。個人寫作、學術研究、學生專題、
> 開源專案文件、不收費的社群分享皆免費；商業使用——販售所寫內容、作為公司知識庫、撰寫商業產品
> 的規格文件——須另行取得授權。本專案為 source-available，非 OSI 定義的開源。

docspec 是給長篇文件用的 spec-driven 撰寫工具。你和 AI agent 在結構化的後台把每一節的概念與決策
講清楚，引擎再把它渲染成散文，並在文件成長的過程中守住前後一致。你只讀渲染出來的成品。

## 特色

- **愈長愈一致** — 章節有穩定 id、共用一份寫作守則，改一處不會讓別處悄悄失準；跨文件邊讓多份
  文件之間也保持同步。
- **先結構、後散文** — 你檢查的是概念與決策，不是一整面潤過的散文；散文由引擎產生。
- **乾淨 Markdown 與排版 PDF** — 每份文件渲染成 Markdown、匯出成 Typst 排版 PDF；期刊 LaTeX 軌
  可 emit `.tex` 供投稿。
- **道地散文** — 一套寫作守則加潔淨 lint，壓制英文的 AI 腔與中文的翻譯腔（[看真實產出](docs/showcase/)）。
- **在你的 agent 裡跑** — Claude Code、Antigravity、Codex，同一套 skill。

## 快速開始

需要 `uv` 與 Python ≥ 3.11（Windows／Linux 已測，macOS 尚未實機驗證）。

```bash
git clone <repo-url> && cd docspec
uv tool install --from . docspec
uv tool update-shell          # 把 uv 的工具 bin 加進 PATH（只需一次），再開新終端
docspec init --tool claude    # 建專案並把 skill 裝進你的 agent
```

寫作流程都在 agent 對話裡透過內建 skill 進行，不是你自己敲 docspec 指令。你會親手打的只有安裝與
維護那幾個：

| 指令 | 做什麼 |
|---|---|
| `docspec init` | 建專案、把 skill 裝進 agent |
| `docspec setup` | 下載 PDF 排版資產（只在要出 PDF 時） |
| `docspec doctor` / `upgrade` / `version` | 體檢 / 更新 / 看版本 |

`docspec --help` 列的是這些給人用的指令；agent 在背後用的完整清單在 `docspec --help-all`。

## 運作方式

一個 docspec 專案分兩層。**後台**（`corpus/`）每節放幾個結構化 YAML 檔——一句話的概念、一份 brief
（受眾、範圍、深度），以及這節實現了哪些決策；邏輯與完整性都住在這層，給 agent 和引擎看。**前台**
（`docs/`）是渲染出來的散文成品——每節各自獨立渲染、再確定性組裝。**人只讀前台。** 章節有穩定 id，
搬資料夾或改名都不會斷引用；跨節的連貫靠一份共用的寫作守則，而不是 agent 互相參照。

這一切都在 agent 對話裡用六個 skill 驅動，引擎在背後把關。

### 寫你的第一份文件

`docspec init` 之後，在專案裡打開你的 agent，說你想寫什麼：

1. **「用 develop 開一份講 X 的文件。」** agent 建好章節骨架，並問你受眾、範圍、深度。你這時審的是
   大綱——概念與決策——不是散文。
2. **「draft 這一節。」** agent 把這節渲染成散文寫進 `docs/`，你在那裡讀。
3. **「edit」再「factcheck」**——先潤一遍稿，再把每條主張對一手來源查核。
4. 一版定稿就**「publish」**：引擎跑完所有閘、凍結一份唯讀的版本快照、記一筆 changelog；要 PDF 就
   **「出成 PDF」**。

你不必親手改後台、也不必自己敲引擎指令——你只跟 agent 對話，每一步讀渲染出來的 `docs/` 檔。在對話
裡看起來像這樣：

```text
你： 我要寫一份 zenoh 控制平面的技術文件，先用 develop 起大綱
AI： [develop] 建好 corpus/zenoh/intro/——記下骨架（這步不寫散文）
        ├─ 概念：為什麼用 zenoh 當控制平面
        └─ 決策：控制平面用 zenoh、不用 MQTT
你： 大綱可以，draft 這一節
AI： [draft] 盲渲染成散文 → docs/zenoh/_latest.md
你： publish
AI： [publish] 所有閘綠 → 凍結唯讀 v1 快照、升版、記 changelog
```

六個 skill：

| skill | 做什麼 |
|---|---|
| **develop** | 長出／重整一節的概念與決策（受眾、範圍、深度）；先有骨架，不寫散文 |
| **draft** | 把一節渲染成散文，只看得到那一節 |
| **edit** | 潤稿：逐行 → 文句 → 校對 |
| **factcheck** | 對抗式查核，每條主張對一手來源；只標記、不擋發行 |
| **publish** | 不可逆發行：所有閘綠 → 凍結唯讀快照 → 升版 → 記 changelog |
| **release** | 互動排版：匯出 → 看頁面圖 → 調旋鈕 → 重出 |

這是迴圈、不是流水線：factcheck 抓到問題就退回 develop 或 draft。日後改動上游某節，引擎會把每個需要
重新同步的下游節標出來，一致性不會在你沒察覺時悄悄跑掉。

## 設計

docspec 底層的幾個設計決定：

- **語義與引擎分離** — 引擎是薄的、確定性的守門員：id 唯一、無死引用、無環、完整性、以內容雜湊
  判斷過期、發行凍結，不做任何語義判斷；內容正確性由不阻塞的 factcheck／audit 標記，不擋發行。
- **省 token 的寫作模型** — 文章是結構層的投影。每一節盲渲染——只看該節，加上引擎投影的光圈
  （aperture，僅相關的上游真相），不需載入整份持續成長的文件。只有內容雜湊改變的節會重渲，因此
  每次動作的 token 成本不隨文件長度增長。
- **寫作風格系統** — 寫作守則骨幹規則、於 `docspec init --lang` 時依語言種入的道地準則、glossary
  術語一致、潔淨 lint（V1–V17，含中文報幕式元敘述與英文 AI 套話規則）、可查核出處的寫作參考
  （`docspec reference writing-zh/en`）。
- **交付物與後台分離** — 人只讀 `docs/`；`corpus/` 供 agent 與引擎使用，潔淨閘門確保後台詞彙不
  進入交付物。
- **多文件森林治理** — `governed-by`／`realizes` 邊在文件間傳播過期狀態，使整套規格不致悄悄
  自相矛盾。

## 產出 PDF

裝上 export 相依、跑一次 setup；它會把受控的排版資產下載進使用者資料夾，不碰你的系統環境：

```bash
uv tool install --from ".[export]" docspec
docspec setup
```

**預設用 Typst** 排版（約 22MB binary、原生 CJK、docspec 自帶房屋樣式模板）。內容是 backend-neutral
的（Markdown＋圖片），所以同一份源料能走兩條軌：預設 Typst 軌（自編、跑忠實度檢查），以及 BYO
期刊 LaTeX 軌——經 slot 契約 emit 一份 `.tex` 供你自行編譯（內附 IEEE、Elsevier adapter）。圖表由
委派的 subagent 用 drawio 畫成、嵌成高解析 PNG；`docspec setup --with-drawio` 裝受控 drawio。

## Showcase

六份由 agent 從零驅動 docspec 寫成的文件——三種文體 × 中英雙語，每一份都通過結構、潔淨、渲染忠實度
閘門，並匯出成排版 PDF。點進去讀渲染成品或開 PDF：

| 文體 | 語言 | 讀全文 | PDF |
|---|---|---|---|
| 小說——短篇 | 正體中文 | [讀](docs/showcase/deliverables/novel-zh.md) | [PDF](docs/showcase/pdfs/novel-zh.pdf) |
| 小說——短篇奇幻 | 英文 | [讀](docs/showcase/deliverables/novel-en.md) | [PDF](docs/showcase/pdfs/novel-en.pdf) |
| 隨筆 | 正體中文 | [讀](docs/showcase/deliverables/essay-zh.md) | [PDF](docs/showcase/pdfs/essay-zh.pdf) |
| 隨筆 | 英文 | [讀](docs/showcase/deliverables/essay-en.md) | [PDF](docs/showcase/pdfs/essay-en.pdf) |
| 學術綜述 | 正體中文 | [讀](docs/showcase/deliverables/academic-zh.md) | [PDF](docs/showcase/pdfs/academic-zh.pdf) |
| 學術綜述 | 英文 | [讀](docs/showcase/deliverables/academic-en.md) | [PDF](docs/showcase/pdfs/academic-en.pdf) |

這些文件怎麼做出來的——用哪些模型、什麼方法、完整的 prompt——寫在 **[docs/showcase/](docs/showcase/)**，
連做得不夠好的地方也照實交代。

## 開發 / 貢獻

歡迎開 issue 或 PR。開發環境、如何跑測試，以及 Windows 加非 ASCII 路徑為什麼要用
`uv run --no-editable`，都寫在 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 授權

**PolyForm Noncommercial 1.0.0** — 任何非商業用途免費；商業使用須另向作者取得授權。Source-available，
非 OSI 開源。使用界線見本文最上方，第三方元件見 [`LICENSE`](LICENSE) 與 [`NOTICE.md`](NOTICE.md)。

## 致謝

docspec 是 [OpenSpec](https://github.com/Fission-AI/OpenSpec) 的 prose-first 衍生版本，獨立運作、
不依賴它。感謝 OpenSpec 團隊先做出了 spec-driven 的 agent 工作流。
