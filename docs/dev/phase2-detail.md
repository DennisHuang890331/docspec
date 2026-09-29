# 第二期細部設計：軟體領域（取代 OpenSpec）

- 狀態：細部設計草案，等使用者確認（第二期架構關卡）
- 依據：`docs/dev/phase2-design.md`（架構）、`docs/dev/system-design.md`
- 例子取自台中港專案的真實內容（task-entry-page 規格、dataset-library change），只節錄結構，不放進 repo 的測試資料。
- 第二期架構的四個待確認問題（phase2-design.md 第 8 節）在本文件先採建議值，標「暫定」。

---

## 1. 目錄

```
docspec/
├─ governance/ …                        第一期（決策含軟體設計決策）
├─ software/
│  ├─ config.yaml                       repo 登記、change 大小門檻、環境指紋欄位
│  ├─ specs/<能力>.yaml                  能力規格（現行基線），一個能力一個檔
│  ├─ changes/<change>.yaml             進行中的軟體 change，一個 change 一個檔
│  ├─ changes/_archive/<日期>-<change>.yaml   封存的 change（唯讀）
│  └─ baselines/<日期>-<change>.yaml     專案基線（封存時產生）
├─ corpus/ changes/ …                   文件領域（不動）
```

- 封存目錄叫 `_archive`，不叫 `archive`，避免和 docspec 自己的凍結區規則衝突（第一期已改成只認 `docs/…/archive/`）。
- 所有檔案都是引擎擁有的 YAML，各自封條，只能透過指令寫入。hook 會擋手改，和第一期的治理紀錄相同。

---

## 2. 能力規格檔

用 `task-entry-page` 為例，由 OpenSpec 的 spec.md 轉成：

```yaml
# docspec/software/specs/task-entry-page.yaml
capability: task-entry-page
purpose: >-
  The workspace home page is the only entrance to annotation work: it lists the tasks,
  shows video imports in progress, and creates new tasks from a video.
requirements:
  - id: R1
    title: The home page is the task list
    statement: >-
      The home page SHALL show the task list as its main content, with the first task row
      visible without scrolling at 1366×768 and at 130% interface size. …
    verification: [test, inspection]     # 驗證方法：test / demonstration / inspection / analysis
    based-on: [gov:D-claude-2]           # 依據的治理決策（可選）
    scenarios:
      - id: S1
        title: Opening a task from the home page
        when: the annotator opens the home page with at least one task
        then: the first task row is inside the first screen and activating its "開啟" control opens that task's editor
      - id: S2
        title: Many AI jobs exist
        when: hundreds of detection and tracking jobs have run
        then: the home page length and content are unchanged by them
  - id: R2
    title: Imports appear as task rows
    …
```

**編號規則**

- 需求編號在能力內唯一，情境編號在需求內唯一。完整引用寫成 `req:task-entry-page/R1`、`scn:task-entry-page/R1/S2`。
- **編號永不重用、永不改變**。需求改名只改 title，不改 id，所以所有引用都不會斷。
- 一條需求至少要有一個情境，規範句要有 SHALL 或 MUST。這兩條由 check 強制（沿用 OpenSpec 的規則）。

---

## 3. 軟體 change 檔

用 dataset-library 為例，只節錄結構：

```yaml
# docspec/software/changes/dataset-library.yaml
id: dataset-library
proposal:
  why: >-
    T2 requires queryable, reproducible management of sensor recordings together with T3
    annotation results. …
  what: [ "Add one shared home page at / that merges Recordings, Annotation tasks and Dataset versions …", … ]
  capabilities:
    new: [dataset-library, dataset-release]
    modified: [task-entry-page, workspace-deployment, annotation/recording-folder-format]
  code-areas: ["labelvault:services/portal/", "labelvault:services/workspace/static/"]
depends-on: []                       # 必須先封存的 change
design:                              # 敘述性內容；決策本身在治理層
  context: >- …
  goals: [ … ]
  non-goals: [ … ]
  risks: [ { risk: "Shared links can propagate corruption", mitigation: "…" } ]
  migration: [ … ]
  decisions: [gov:D-claude-7, gov:D-claude-13, gov:D-claude-15]   # 這個 change 的設計決策（治理層紀錄）
deltas:
  - op: modify-requirement           # 只改規範句；情境各自處理
    ref: task-entry-page/R1
    base: sha256:3f9a…               # 撰寫這筆差異時 R1 的指紋
    title: The home page is the dataset Overview
    statement: >-
      The home route / SHALL show the same Overview to every user … Recordings, Annotation
      tasks and Dataset versions SHALL be part of the home page and SHALL NOT be separate pages …
  - op: modify-scenario              # 只改 S1，不用重抄 S2
    ref: task-entry-page/R1/S1
    base: sha256:77c0…
    when: a user activates a task's "Open" control in the home page's task section
    then: the existing editor route opens, and the editor's return links bring the user back to the task section
  - op: add-scenario
    ref: task-entry-page/R1          # 新情境的編號由引擎配發（S3、S4…）
    title: Pre-annotating an unfinished task from Overview
    when: …
    then: …
  - op: remove-scenario
    ref: task-entry-page/R1/S2
    base: sha256:1b2d…
    reason: Overview no longer lists AI jobs at all
  - op: add-requirement
    capability: dataset-library
    title: Recording deletion is one step
    statement: …SHALL…
    verification: [test]
    based-on: [gov:D-claude-13]
    scenarios: [ … ]
tasks:
  - id: "6.6"
    title: Redesign Overview per the 2026/09/24 user request
    implements: [req:task-entry-page/R1]
    files:                           # 預計改動（事前宣告，也是多 agent 的寫入範圍）
      - labelvault:services/portal/overview.py
      - labelvault:services/workspace/static/overview.js
    verify:
      method: [test, inspection]
      test: "pytest tests/browser/test_entry_page.py"
      inspection: "screenshots at 1366x768 and 1920x1080, 100% and 130%"
    status: done
    evidence: [E-claude-31, E-claude-32]
```

**格式重點**

- 規格差異的動作共八種。需求層級：新增、修改、移除、改名；情境層級：新增、修改、移除，以及新增能力。
- **修改只寫改到的欄位**。只改情境就不必重寫需求本身，沒提到的欄位與情境都原樣保留。這解決 OpenSpec「MODIFIED 要整段重抄、漏抄一個就被擋」的問題。
- **移除要寫理由**，比照 OpenSpec 移除時要寫 Reason 的規則。
- 每筆修改或移除都記 `base`，也就是撰寫差異當下目標內容的指紋，由引擎自動填入，不用人寫。

---

## 4. 封存：差異併回規格

`docspec code archive <change>` 依序執行以下步驟。任何一步失敗就停下，並回報完成到哪一步，不會留下改一半的狀態：

1. **驗證**：change 本身通過 check。
2. **任務完成度**：每個任務都已完成，而且帶有符合其驗證方法的證據（第 5 節）；未完成但經裁定豁免的任務除外。前置 change（depends-on）必須已封存。
3. **基準指紋**：每筆修改或移除的 `base` 和現行規格一致。不一致代表別的 change 已經先改過同一條需求，這時停下並列出衝突，請 agent 重新對照現行規格後更新差異。這一步防止並行 change 靜默覆蓋彼此。
4. **套用差異**：在記憶體中把差異套到規格副本上，套完再跑一次 check。
5. **寫入**：原子性寫回受影響的規格檔。
6. **搬移**：change 移到 `changes/_archive/<日期>-<change>.yaml`，之後唯讀。
7. **記錄專案基線**（第 8 節）。
8. **後續效果全部由推導產生**，不需另外處理：
   - roadmap 裡指向 `swc:dataset-library` 的工作項目轉為完成；帶豁免的顯示「完成（含豁免 n 項）」。
   - 文件章節若 realizes 了被改到的需求，就轉為 stale-upstream。
   - 其他進行中的 change 若有任務實作被改到的需求，建立可疑標記。

`docspec code sync <change>` 只做第 3～5 步，把差異併回規格但 change 繼續進行，對應 OpenSpec 的 sync。

---

## 5. 任務、證據與完成規則

**證據紀錄**：`docspec/software/evidence/<E-id>.yaml`，一筆一檔、封條。

| 型別 | 必填內容 | 怎麼產生 |
|---|---|---|
| test-run | 指令、repo 與 commit、環境指紋、通過／失敗／略過數、離開碼 | `docspec code evidence run <task> -- <指令>`：引擎代為執行並自動擷取結果，不讓 agent 手填數字 |
| inspection | 看了什麼（例如截圖路徑與畫面尺寸）、結論 | `docspec code evidence add <task> --type inspection …` |
| real-model | 模型版本、測試資料、執行前後檢查的不變量 | 同上 |
| measurement | 量到的值、門檻、單位 | 同上；超過門檻會標成不合格 |
| acceptance | 你的驗收：agent 覆述，你回覆確認 | 同第一期裁定的覆述流程，記下你的回覆 |
| waiver | 依據哪條裁定、什麼情況下重新打開 | `docspec code evidence waive <task> --ruling RL-… --reopen-when …` |

**完成規則**：`docspec code task done <task>` 只在下列條件都成立時才接受。

- 任務的每一種驗證方法都有對應證據。例如 `test` 需要一筆 test-run，`inspection` 需要一筆 inspection；或者整個任務有一筆 waiver。
- test-run 的失敗數為 0。略過數為 0，除非任務的 verify 事先寫了 `allow-skips`（用來處理「沒有 GPU 時略過」這類已知狀況）。
- 證據的 commit 必須是改動檔案所在 repo 的 commit。

**環境指紋**：記錄 Python 版本、平台，以及 `software/config.yaml` 裡指定的環境變數與檢查結果。這是為了抓台中港實際踩到的問題：ROS 的 PYTHONPATH 汙染、torch 不存在導致整個測試檔被略過、GPU 看不到。

**驗收（暫定）**：只有驗證方法含 `demonstration` 或 `inspection` 的需求，封存前才需要一筆 acceptance；純 `test` 的需求以測試證據為準。

---

## 6. 設計決策與治理層的連結（暫定：併入治理層）

- `docspec code propose` 時，設計決策用第一期的 `docspec decision add` 建立，並在紀錄裡標明屬於哪個 change（新欄位 `change: dataset-library`）。
- 一頁現況的「目前有效設計」預設只列專案層決策；`docspec brief --design --change dataset-library` 列出某個 change 的有效決策。
- 決策仍須有裁定作依據，取代時仍須寫出完整新版（第一期規則不變）。

---

## 7. 追溯與影響（延伸第一期的追溯圖）

新增的節點與連結：

- 需求 `req:` ─依據→ 治理決策 `D-…`
- 任務 ─實作→ 需求；任務 ─改動→ 檔案 `labelvault:path`；任務 ─驗證於→ 證據（證據內含測試指令）
- 文件章節 ─實現→ 需求 `req:` 或 change `swc:`
- 工作項目 ─指向→ change `swc:`

影響傳遞規則：

- **決策被取代**：
  - 依據它的需求 → 可疑。
  - 實作那些需求的任務 → 已完成的標「需重看」，並列出它們的檔案與測試。
  - 實現那些需求的文件章節 → 轉為過時。
- **需求被 change 修改（封存時）**：
  - 其他進行中 change 裡實作它的任務 → 可疑。
  - 文件章節 → 過時。
- 台中港情境 S2：取代「/tasks 維持不變」→ 列出 `req:task-entry-page/R1`、任務 6.6（需重看）、`tests/browser/test_entry_page.py`、說明書第三章。

**文件章節 realizes 需求的做法**：沿用第一期的外部決策索引，加入 `req:` 條目。條目內容為需求的規範句與情境的正規化文字，狀態為有效或已移除。需求一改，指紋就變，章節自然轉為 stale-upstream，不需另寫機制。

---

## 8. 多 repo 與專案基線

```yaml
# docspec/software/config.yaml
repos:
  labelvault: tools/labelvault        # 名稱：相對專案根的路徑（各自是 git repo）
change-size-warning: {tasks: 30, capabilities: 4}
environment:
  env-vars: [PYTHONPATH, CUDA_VISIBLE_DEVICES]
  checks: ["python -c 'import torch'", "nvidia-smi -L"]
```

```yaml
# docspec/software/baselines/2026-09-30-dataset-library.yaml（封存時產生）
event: archive dataset-library
date: 2026-09-30
repos: {labelvault: 5e1c9a2}                  # 各 repo 當下的 commit
specs: {task-entry-page: sha256:…, dataset-library: sha256:…}
documents: {port-dataset-guide: 1.2.0}        # 已發布的文件版本
governance: {active-decisions: [D-claude-1, D-claude-15]}
```

- 文件發布時也會記一筆基線。
- 需要知道「某版文件描述的是哪個規格、哪個 commit」時，查基線即可。

---

## 9. 指令（暫定放在 `docspec code …`）

| 指令 | 作用 |
|---|---|
| `code spec list` ／ `code spec show <能力> [--req R1] [--json] [--md]` | 查規格；可只取一條需求（省讀取量） |
| `code change new <id> --why … --capabilities …` | 建立 change |
| `code change delta <id> --op modify-scenario --ref task-entry-page/R1/S1 --when … --then …` | 加一筆差異（引擎自動填 base） |
| `code change show <id> [--md] [--json]` | 查 change；`--md` 輸出給人或 PR 審查的版本 |
| `code change status <id>` | 任務進度、缺的證據、基準指紋是否仍一致、大小提醒 |
| `code task add <change> --title … --implements … --files … --verify-test "…"` | 新增任務 |
| `code task done <change> <task>` | 依完成規則檢查後勾選 |
| `code evidence run|add|waive …` | 產生證據（第 5 節） |
| `code sync <change>` ／ `code archive <change>` | 第 4 節 |
| `code import-openspec [--path openspec/]` | 匯入（第 10 節） |

所有查詢都支援 `--json` 與欄位過濾，讓 agent 只讀需要的部分（第一期裁定的 YAML 理由）。

---

## 10. OpenSpec 匯入

1. **規格**：解析 `## Purpose`、`### Requirement:`、`#### Scenario:`、`- **WHEN**`／`- **THEN**`，依出現順序編號 R1、R2…、S1、S2…。規範句保留原文。
2. **進行中的 change**：
   - proposal.md 的 Why、What Changes、Capabilities 轉成 proposal。
   - delta spec 的 ADDED、MODIFIED、REMOVED、RENAMED 轉成差異。MODIFIED 的整段需求會和現行規格逐情境比對，只把真的改了的部分轉成 modify-scenario 或 add-scenario。
   - tasks.md 的勾選狀態照搬。已勾的任務因為沒有證據，匯入後標為「匯入時已完成（無證據）」，不會被當成有證據的完成。
3. **design.md 的決策**：D1…D15 各建一條治理決策，依據欄位留空。
   - 標題含「supersede」或「以後者為準」的，標為「待合併」，列進待裁定清單，請 agent 寫出完整新版並經你確認。
   - discussion.md 不解析，只在匯入報告中註明「裁定散在討論檔，需人工整理成裁定紀錄」。
4. **已封存的 change**：轉進 `changes/_archive/`，只保留提案與差異作為歷史，不重放。
5. **匯入報告**：列出轉了多少規格、需求、情境、change、任務，以及哪些需要人工處理；最後跑 check。

---

## 11. skill（暫定命名）

- **dspx-propose**：
  - 先看 `docspec brief` 和相關規格，只讀需要的需求。
  - 需要你決定的事，建成待裁定問題並覆述確認。
  - 建立 change → 設計決策（治理層）→ 差異 → 任務（含檔案與驗證方式）。
  - 最後跑 `code change status` 看大小提醒。
- **dspx-implement**：
  - 一次處理一組任務，只改宣告過的檔案。
  - 用 `code evidence run` 跑測試並留下證據，再 `code task done`。
  - 遇到未涵蓋的設計問題就停下，建成待裁定問題。
- **dspx-verify**：對照需求、情境、有效決策與程式碼，找出三類問題：
  - 缺證據（完整性）
  - 情境沒被測到（正確性）
  - 違反有效決策（一致性）

  發現記成審查紀錄，建議性質、不擋。

---

## 12. 程式結構與施工順序

新模組：
- `engine/software/`：`specs.py`、`changes.py`、`delta.py`（套用與指紋）、`evidence.py`、`baseline.py`、`import_openspec.py`
- `commands/code/`：各指令

施工順序（每一步都保持既有測試通過）：

1. 規格檔：格式、讀寫、check、查詢、Markdown 輸出。
2. change 檔與差異：差異套用、基準指紋、sync。
3. 任務與證據：完成規則、`evidence run` 自動擷取、環境指紋。
4. 封存交易與專案基線。
5. 追溯圖延伸、影響傳遞、文件章節 realizes `req:`。
6. roadmap 的 `swc:` 指向與豁免。
7. OpenSpec 匯入與匯入報告。
8. 三個 skill；以台中港資料在本機跑驗收情境 S2、S5、S7、S8、S9。

---

## 13. 需要你決定的事

1. 軟體設計決策併入治理層（第 6 節）？
2. 不做 OpenSpec 的 store、workset、自訂 schema？
3. 你的驗收只在「展示／檢查」類需求才需要（第 5 節）？
4. 命名：指令 `docspec code …`、skill `dspx-propose`／`dspx-implement`／`dspx-verify`？
5. （新）匯入時，已勾選但沒有證據的任務標為「匯入時已完成（無證據）」，而不是直接算有證據的完成，這樣可以嗎？
6. （新）測試證據由引擎代跑指令並自動擷取結果（`evidence run`），不接受 agent 手填測試數字，這樣可以嗎？

---

## 附錄：新流程與 OpenSpec 流程的逐段比較（2026/09/30）

對 OpenSpec 行為的描述，依據原始碼（v1.13.2）與台中港專案的實際檔案。

1. **開工讀資料**
   - OpenSpec：agent 讀 AGENTS.md、交接檔、總進度檔（234 KB）、change 的 proposal／design／tasks，常常還要讀 discussion.md（260 KB），只能靠搜尋。
   - 新流程：先讀 `docspec brief`（上限 2000 字），需要細節時用過濾查詢，例如 `code spec show task-entry-page --req R1`、`code change status dataset-library --json`。
2. **討論與裁定**
   - OpenSpec：寫進 discussion.md；設計檔追加「D15 取代 D7 衝突處」。
   - 新流程：待裁定問題 → agent 覆述、你確認 → 裁定紀錄 → 寫出完整新版的決策（治理層）。
3. **提案**
   - OpenSpec：propose skill 寫四個 Markdown 檔；validate 只查格式。
   - 新流程：dspx-propose 透過指令建立 change。check 除了格式，也查引用，例如：
     - 差異指向的需求是否存在
     - 依據的決策是否有效
     - 任務實作的需求是否在這個 change 裡
     - 被修改的需求是否有任務負責
4. **修改一條需求**
   - OpenSpec：MODIFIED 要貼上整段需求，含全部情境，而且標題要一字不差；漏抄一個情境就被擋（dataset-library 就漏過）。
   - 新流程：只寫改到的情境，其他原樣保留；基準指紋由引擎自動填入。
5. **中途改設計**
   - OpenSpec：追加 D15，再靠人或子 agent 找出規格與任務中所有受影響的地方（例如 /tasks 那個矛盾）。
   - 新流程：新裁定 → 決策完整新版 → 影響分析自動列出受影響的需求、任務（需重看）、測試、文件章節。
6. **實作**
   - OpenSpec：apply skill 逐項做 tasks.md、自己打勾；檔案歸誰改、用哪個測試埠，靠 AGENTS.md 的口頭規則。
   - 新流程：任務事先宣告要改的檔案；證據由引擎代跑測試並擷取結果；沒有證據不能勾完成；略過的測試算失敗；記錄環境指紋。
7. **驗證**
   - OpenSpec：verify skill 由 agent 讀文件和程式碼寫報告（建議性質）。
   - 新流程：一樣是建議性質，但「哪條需求沒有任務、哪個情境沒有測試、哪個任務沒有證據」這類機械檢查由引擎算好，agent 只做語意判斷。
8. **封存**
   - OpenSpec：任務沒做完只警告，可以選擇繼續；以需求標題比對來合併差異；design.md 跟著 change 被封存；並行的 change 可能互相覆蓋（OpenSpec 自己的合併計畫文件有記載）。
   - 新流程：證據不齊就不能封存（豁免除外）；基準指紋不符就停下；決策留在治理層；自動記錄專案基線。
9. **文件同步**
   - OpenSpec：沒有這個功能，只能靠交接檔提醒人回去改。
   - 新流程：文件章節 realizes 需求，程式規格一改，章節就轉為過時。
10. **進度與交接**
    - OpenSpec：roadmap 角色讀檔案，手寫進 ROADMAP.md；交接檔一直往上加。
    - 新流程：roadmap 自動推導；一頁現況每次重新產生。

**沒有改變的部分**

- 流程形狀：探索 → 提案 → 實作 → 驗證 → 封存。
- 內容組成：提案／規格差異／設計／任務。
- skill 帶著 agent 做事、verify 只提建議、程式碼放在 git 分支、你在關鍵點做裁定。

**新流程的代價與因應**

- agent 不能直接改檔案，一律走指令，呼叫次數變多。
  - 因應：大量差異可以先寫成 YAML 片段，一次交給 `code change delta --from <檔案>`，由引擎驗證並填入基準指紋。
- 小任務也要留證據。
  - 因應：機械性的小修改可以只附一筆檢查紀錄（一句話說明看了什麼），或用裁定豁免。
- YAML 比 Markdown 難讀。
  - 因應：`--md` 輸出給人讀、給 PR 審查。
- 需要一次性匯入。
  - 因應：匯入報告會列出需要人工處理的項目。

---

## 14. 2026/09/30 使用者回饋與補充設計

**使用者確認**

- 接手的閱讀順序：AGENTS.md（工具會自動載入）→ 有交接文件就讀 → `docspec brief` → 需要細節時用 `code spec show …` 查詢。
- 討論與裁定沿用 docspec 的設計（第一期）。
- 修改需求只寫改到的情境：同意。
- 中途改設計走影響分析：同意。

**使用者要求補充**：propose 的檔案與互動設計、測試由誰寫與管理、roadmap 與一頁現況的運作。以下各節補充。

### 14.1 propose 會建立哪些檔案，彼此怎麼連

一次 propose 會新增或改動以下紀錄，全部都是一筆一檔：

- `software/changes/<change>.yaml`：提案、規格差異、設計說明、測試規劃、任務。
- `governance/decisions/D-….yaml`：這個 change 的設計決策（依據裁定、寫完整內容）。
- `governance/questions`、`rulings`：討論中需要你決定的事。
- `governance/roadmap/W-….yaml`：把工作項目連到這個 change（`swc:<change>`）。
- **不會動**的檔案：`software/specs/*.yaml`（現行規格）。規格只在 sync 或封存時才會被改。

連結關係：

```
裁定 ◀─依據── 決策 ◀─依據── 規格差異（改哪條需求／情境）──指向──▶ specs/<能力>.yaml 的 R1/S1
                   ▲                    ▲
                   │依據                │涵蓋
                 change ──包含──▶ 測試規劃 T1（測哪些情境、測試放在哪）
                   │                    ▲
                   └──包含──▶ 任務 6.6 ─實作→ 需求；─改動→ repo 檔案；─撰寫／執行→ T1
roadmap 工作項目 ──指向──▶ change
```

`docspec check` 對這些連結的檢查（格式以外）：

- 差異指向的能力、需求、情境必須存在（新增的除外）；基準指紋必須還對得上現行規格，否則提示「規格已被別的 change 改過」。
- 差異和需求依據的決策必須存在且有效（草稿、被取代、撤回的會報錯）。
- 每一筆新增或修改的需求至少有一個任務實作它；每個任務實作的需求都必須在這個 change 的差異裡，或是現行規格裡已有的需求。
- 每一個新增或修改的情境至少被一個測試規劃涵蓋；驗證方法不是 test 的，要有對應的檢查或展示任務。
- 任務宣告的檔案必須在已登記的 repo 裡。
- depends-on 指向的 change 必須存在，且不能形成循環。
- 超過大小門檻時提醒拆分（只提醒）。

### 14.2 測試由誰寫、誰管理

原則：**測試是程式碼**，放在程式 repo（例如 `tools/labelvault/tests/`），跟著 git 版本管理。docspec 不取代 pytest，只負責三件事：規劃「要測什麼」、記錄「哪個測試驗證哪個情境」、保存「跑過的結果」。

1. **規劃（propose，寫程式之前）**：
   - change 裡有一段「測試規劃」，每一筆列出：測試編號、測試位置（例如 `labelvault:tests/browser/test_entry_page.py::test_first_row_visible`）、涵蓋哪些情境、測試層級（單元／整合／瀏覽器／真模型）。
   - 規劃在實作前就寫好，由 propose 的 agent 依情境的 WHEN／THEN 擬定。這樣避免「寫程式的人事後自己出題、自己考」（系統工程審查的建議）。
2. **撰寫（implement）**：
   - 實作任務的 agent 依照測試規劃寫測試，和功能程式放在同一個任務裡（沿用你們 AGENTS.md「一個子 agent 負責實作、相關測試與修正」的規則）。
   - 測試檔也要列在任務宣告的檔案裡。
3. **執行與證據（implement）**：
   - `code evidence run <任務> -- <測試指令>` 由引擎代跑，記錄結果。
   - 失敗或無故略過的測試，任務就不能勾完成。
4. **檢查（verify）**：
   - 引擎檢查：每個情境是否都有測試規劃、規劃的測試檔是否存在、是否跑過而且通過。
   - agent 語意審查：測試是否真的驗證了 WHEN／THEN，而不只是跑過。建議由不同於實作者的 agent 來做。
5. **長期管理（archive 之後）**：
   - 封存時，「情境 ← 測試」的對應會併回規格。每個情境多一個欄位 `verified-by`，列出驗證它的測試。
   - 因此，任何時候都能回答「目前的規格由哪些測試驗證」。
   - 情境被修改時，它的測試自動列為需重看。
   - 測試檔被刪除或改名時，check 會報出引用斷了。
6. **回歸測試**：
   - `docspec code test [--capability …]` 依規格裡的 `verified-by` 組出要跑的測試清單並執行（也可以只輸出清單交給 CI）。
   - 完整測試仍由專案自己的 pytest 設定負責。

### 14.3 roadmap 與一頁現況怎麼運作

- **roadmap**：你（或 agent）只需要定義一次「里程碑」和「工作項目」，並把工作項目連到實際的 change 或文件。之後**不需要任何人去更新狀態**：每次查看時，工具依照連到的東西現在的狀態，當場算出進度。例如「標註工具資料庫功能」連到 `swc:dataset-library`：
  - change 還在進行 → 顯示「進行中」
  - change 封存 → 顯示「完成」
  - 封存時有 3 個任務經你裁定豁免 → 顯示「完成（含豁免 3 項）」
  - 前置項目還沒完成 → 顯示「卡住：等 ×× 完成」
  - 受到上游決策變更影響 → 顯示「卡住：需重看」
- **一頁現況**（`docspec brief`）：不是一個存起來的檔案，而是一個指令。每次執行時，從上述紀錄重新組出一頁摘要。
  - 所以它不會過時，也不會像 ROADMAP.md 那樣越寫越長。
  - 要給人看的檔案版本，用 `docspec brief --write` 重新產生 `docs/project/status.md`。
- **和現在的差別**：現在是 roadmap 角色的 agent 讀完所有檔案，再手寫進 ROADMAP.md；新設計是這份內容由工具算出來。

---

## 15. 2026/09/30 使用者裁定與修訂後的設計（取代第 1、3、5、9、11 節的對應部分）

**裁定**

1. change 的檔案結構改回 OpenSpec 的形式：一個 change 一個資料夾，每類內容一個檔（YAML）。**一律透過指令寫入**，由引擎驗證格式與引用、自動補內容指紋。
2. 任務沒有勾選欄位，完成與否由引擎依證據判定，解決「做完忘記打勾」的問題。
3. 寫測試的 agent 必須和實作的 agent 不同，運作方式類似 audit（紅隊）。
4. 指令群組名稱：`docspec code`。

**修訂後的 change 資料夾**

```
docspec/software/changes/<change>/
├─ proposal.yaml        為什麼改、改什麼、影響哪些能力與程式區塊、depends-on
├─ design.yaml          背景、目標／非目標、風險、遷移；決策以 gov:D-… 引用治理層
├─ specs/<能力>.yaml    對該能力的規格差異（需求／情境層級，含基準指紋）
├─ tests.yaml           測試規劃：測試位置、涵蓋哪些情境、層級、撰寫者（測試角色）
└─ tasks.yaml           任務：實作哪些需求、改動哪些檔案、驗證方式；沒有勾選欄位
```

封存後整個資料夾搬到 `software/changes/_archive/<日期>-<change>/`。

**任務完成的推導規則**

- 任務的每一種驗證方法都有合格證據時，自動算完成。
  - test：任務引用的測試規劃項目，在引擎代跑時全部通過，失敗 0，而且沒有未聲明的略過。
  - inspection／demonstration：有對應的檢查紀錄或使用者驗收紀錄。
  - 有經裁定的豁免也算完成（顯示「含豁免」）。
- 證據的 commit 之後，任務宣告的檔案又被改動（依 git 比對）→ 狀態退回「需重跑證據」，避免拿舊的結果證明新的程式。
- 狀態包括：未開始、進行中（已有部分證據或檔案已改動）、完成、完成（含豁免）、需重跑證據。

**測試角色（dspx-test，類似 audit）**

- 由測試角色依規格情境的 WHEN／THEN 從外部行為撰寫測試，不看實作；`tests.yaml` 由它建立，每筆記錄撰寫者。
- 測試檔屬於測試角色的寫入範圍，實作任務不得宣告這些檔案。引擎比對實作任務的變更範圍，若包含測試檔就警告。
- 測試失敗記成一筆發現，實作者修程式來解決。實作者認為測試寫錯時，提出「測試異議」，由測試角色回應（修改測試或駁回，都要寫理由），一來一回留紀錄；僵持時列入待裁定問題。
- 能力限制：引擎能用工具前綴區分不同家的 agent，無法區分同一家開出的兩個子 agent，這部分由角色分工與紀錄約束。

**skill 修訂**：dspx-propose、dspx-test（新增）、dspx-implement、dspx-verify。

**仍採建議值、使用者可再改的項目**

- 設計決策放在治理層（依本節裁定 1 的檔案結構確認）。
- 不做 OpenSpec 的 store、workset、自訂 schema。
- 你的驗收只在驗證方法為展示／檢查的需求才需要。
- 匯入時，OpenSpec 已打勾但沒有證據的任務，標為「匯入時已完成（無證據）」。

---

## 16. 2026/09/30 裁定：任務保留「完成」欄位，由程式寫入；第二期架構關卡通過

- tasks.yaml 每個任務保留看得見的完成欄位（`status`，以及 `completed-at`、`evidence`），方便人直接閱讀。
- 這些欄位**只由引擎寫入**：`docspec code evidence run` 跑完、失敗數為 0（而且沒有未聲明的略過）時，引擎自動把任務標為完成，並寫入證據編號與時間。檢查、展示類的驗證方法，在記錄檢查或驗收時一樣由引擎標記。
- agent 沒有「打勾」指令；手改 tasks.yaml 會被封條與 hook 擋下。
- 完成後，任務宣告的檔案若又被改動（依 git 比對證據的 commit 之後的變更），引擎在下一次 `check` 或 `code change status` 時把欄位改回「需重跑證據」。
- 其餘設計（第 15 節）使用者同意，**第二期架構關卡通過**，開始實作。

---

## 17. 實作紀錄（2026/09/29）

**P2-1／P2-2（規格、change 資料夾）**：完成。`code sync` 移到 P2-4 與封存一起做——封存前把差異寫進規格，會讓其他進行中 change 的基準指紋全部失效。

**P2-3（證據與自動完成）**：完成。實作細節與原設計的差異：

- **新鮮度改用檔案內容指紋，不用 git commit 比對**。每筆證據記下當時任務宣告檔案與測試檔的內容指紋；之後內容變了，這筆證據就不算數，任務退回「需重跑證據」。好處是未 commit 的改動也抓得到，沒有 git 也能用。commit 仍記在證據裡供追查。
- **引擎代跑時自動加 `--junitxml`**，逐一比對規劃測試是否真的有跑到、結果如何。規劃的測試沒出現在結果裡＝不通過（避免「測試檔被整個略過卻顯示綠燈」）。非 pytest 指令只能讀總數，會註明無逐項結果。
- 只有最新一筆同類證據算數：先過後失敗＝進行中。
- 任務狀態在 `code evidence …`、`code change status`、`code task list` 時由引擎寫回 tasks.yaml；`docspec check` 只提醒「紀錄的狀態落後於證據」，不寫檔。
- 測試撰寫者與執行者相同時提醒（引擎只能分辨工具前綴，屬輔助約束）。
- repo 設定可寫 `名稱: {path, test-command}`，預設 `python -m pytest`；`environment: {vars, checks}` 記入環境指紋，檢查失敗只提醒不擋。

**P2-4（封存與回歸測試）**：完成。

- `docspec code archive <change> [--dry-run]`：依序刷新任務狀態 → 嚴格檢查 → 完整性（任務都完成或豁免；檢查／展示類需求要有使用者驗收或豁免）→ 在副本上套差異並併入 `verified-by` → 寫規格、寫基線、搬資料夾。寫到一半失敗會還原規格、刪掉基線、資料夾搬回原處。
- 兩個 change 改同一個情境：先封存的成功，後者停下並列出衝突；先封存時會提醒哪些進行中的 change 改到同一個能力。
- 基線 `software/baselines/<日期>-<change>.yaml`：各規格的指紋、專案與各 repo 的 commit、證據編號、任務完成數、編號重配。
- 封存後 `code change show` 仍查得到；change id 不能重用。
- `docspec code test [--capability] [--list]`：依正式規格的 `verified-by` 每個 repo 跑一次，失敗時回報影響哪些情境；`--list` 只列清單給 CI。
- `docspec check` 會檢查 `verified-by` 指到的測試檔是否還在（刪除或改名＝引用斷了）。
- 情境被修改時，舊的 `verified-by` 保留、新規劃的測試附加上去；「需重看」的標示留到 P2-5 影響分析一起做。

**P2-5（串起治理層與文件樹）**：完成。

- 新的參照：`swc:<change>`（軟體 change）、`req:<能力>/R1`（需求）。追溯圖加入進行中 change、需求、任務、規劃測試的節點與邊（`engine/software/links.py`）。
- 決策被取代或撤回：依據它的進行中 change 與需求都建立可疑標記。change 被標記時，`code change status` 提醒、`code archive` 擋下，直到看過並用 `docspec impact clear` 清除。封存的 change 若改寫了需求的 based-on（不再引用舊決策），該需求的標記自動清除並寫明理由。
- roadmap 工作項目可連 `swc:<change>`：進行中＝進行中；被標記＝卡住（寫明原因）；封存＝完成；封存時有豁免任務＝完成（含豁免）。
- 文件章節可 `realizes: [req:<能力>/R1]`：需求全文（含情境）納入章節的上游指紋，封存改到該需求時章節轉 stale-upstream；指向不存在或已退役的需求，check 報錯。
- 情境被修改（WHEN／THEN 變了）時，舊的 `verified-by` 不再算數，改由這次規劃的測試接手；被拿掉的舊測試在封存輸出與基線中列出，交給測試角色更新或刪除（取代 P2-4 的「保留舊的」）。
- `docspec brief` 新增「軟體開發」段：每個進行中 change 的任務進度、可封存、需重跑證據、受上游影響。
- 補上修正用的指令：`code change design --remove-decision`、`code change undelta`、`code task remove`（已有證據者不可刪，改用豁免）、`code testplan remove`（有任務引用者不可刪）。

**P2-6（OpenSpec 匯入）**：完成。`docspec code import-openspec [--path openspec] [--dry-run]`。

- 現行規格：需求依出現順序編 R1…、情境編 S1…；GIVEN／AND／BUT 併入 WHEN 或 THEN；code fence 內的標題不算。驗證方法 OpenSpec 沒有，先一律設 test，報告提醒把要人看的需求改成 inspection／demonstration。
- 進行中的 change：ADDED／MODIFIED／REMOVED／RENAMED 轉成引擎的差異，一律經 `delta.prepare`，自動補基準指紋。MODIFIED 是整段取代，拆成 modify-requirement 與逐情境的 add／modify／remove-scenario；名稱對不上的列在報告裡，不猜。tasks.md 已打勾＝「匯入時已完成（無證據）」。
- 已封存的 change：保留提案、設計、任務作為歷史，差異不重放（現行規格已含其結果）。
- 匯入的 change 本來就沒有「任務→需求」「測試→情境」連結：平常 check 只合併成一則提醒，不讓專案 check 變紅；封存時照樣逐條擋下。補連結用新增的 `docspec code task set`。
- 只能匯入到空的軟體領域（防重複匯入）；`openspec/` 原檔不動；報告寫在 `docspec/software/import-openspec-report.md`。
- 台中港資料（本機副本，未進 repo）實測：8 份規格（105 條需求、210 個情境）與原檔數目一致；進行中的 dataset-library 轉出 88 筆差異、51 個任務（39 個匯入時已完成）；28 個已封存 change 轉為歷史；沒有名稱對不上的差異；匯入後專案 check 維持通過（2 則提醒）。
