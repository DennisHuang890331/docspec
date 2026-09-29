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
