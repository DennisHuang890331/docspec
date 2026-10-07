## Why

docspec 已有治理、證據與封存機制，但正常操作仍可能使未驗證的工作被判為完成，或使已撤回的裁定繼續放行。這次 review 用合成資料重現十個情境；需要先修正完成判定，再改善開工與交接流程。

## What Changes

- 封存逐一確認必要情境有有效測試證據或適用的有效豁免；不能只看測試計畫存在與任務完成。
- 證據對應目前的需求、測試計畫與執行政策；最新失敗不能被舊成功蓋過，測試重新指定後必須重新簽收與執行。
- 豁免重新檢查裁定效力；撤回裁定的影響傳到相關決策與軟體工作；使用者驗收對應目前版本。
- 有連結或子項目的 roadmap 工作依實際狀態推導；文件區分已寫好與目前內容已定版；文字輸出列出卡住原因、失敗與缺口。
- 提案階段允許先建立待測試規劃的任務；在執行證據與封存時要求規劃完整。協作規範要求開工建立或沿用 roadmap 項目，並移除過時規則。
- 交接單記下當時專案紀錄狀態，之後變動時提醒；同一天的變動也能辨識，提醒不阻擋工作。
- 修正 review 暴露的 Windows 測試指令路徑解析與路徑斷言問題。
- **BREAKING**：部分過去可顯示完成或可封存的進行中工作，將因證據不足退回需補驗證；舊證據不刪除，已封存歷史不改寫。

## Capabilities

### New Capabilities

目前 `openspec/specs/` 為空，以下是首次建立的 OpenSpec 行為契約，不代表 docspec 從未有這些功能。

- `software-evidence-validity`：情境至證據的完整性、證據新鮮度、最新執行結果與跨平台測試指令。
- `governance-authorization-validity`：裁定撤回、豁免失效與目前版本的使用者驗收。
- `roadmap-state-truthfulness`：以連結推導狀態、文件定版狀態與可讀的缺口說明。
- `agent-workflow-handover`：可執行的提案順序、開工登記、一致的規範與交接過時提醒。

### Modified Capabilities

無既有 OpenSpec 能力可修改；現行設計仍以 `docs/dev/system-design.md` 的裁定及 `docs/dev/phase2-current.md` 為依據。

## Impact

- 軟體核心：`src/dspx/engine/software/{evidence,tasks,archive,changes,links}.py` 與 `commands/code/code.py`。
- 治理與現況：`engine/{governance,impact,roadmap_v2,handover,project_baseline}.py`、治理 CLI。
- agent 流程：`commands/maintenance/init.py`、內建 skills、現行設計、CHANGELOG 與 S4 驗收情境。
- 回歸測試使用合成專案；首次 review 的暫存重現程式只作參考，不引入個人路徑或真實專案資料。
- 保留文件與軟體互不阻擋、連結提醒不阻擋、測試角色簽收、已接受的身分與封條限制。不增加並行、多人權限或封存前強制完整重跑。
- 本 change 已獲負責人確認並授權實作，原話記於 `docs/dev/system-design.md`；E11 的全新 agent 實測另行取得執行指示。
