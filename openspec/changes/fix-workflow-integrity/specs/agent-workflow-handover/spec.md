## Purpose

提供能依說明實際走通的開工、提案、測試與交接流程，讓新接手者看得到已登記工作與交接後變動，避免過時或互相矛盾的規則造成流程錯誤。

## ADDED Requirements

### Requirement: Proposal can precede test planning

系統 SHALL 允許在提案階段建立尚未連結測試的測試型任務，明示待測試規劃；執行證據與封存前 SHALL 要求必要計畫與連結完整。提案 skill SHALL 能將此待辦交給測試角色，而非要求交棒前清除尚未規劃測試造成的缺口。

#### Scenario: Create task before planning tests
- **WHEN** 提案角色建立 verify=test 的任務，測試角色尚未提供測試編號
- **THEN** 任務成功建立並顯示待測試規劃；嘗試完成或封存仍被拒絕

#### Scenario: Test role completes planning
- **WHEN** 測試角色補上測試、情境連結及簽收，任務連上相應測試
- **THEN** 引擎可執行驗證，完成仍由實際證據決定

### Requirement: Work is registered once in roadmap

產生的協作規範與提案、文件工作 skills SHALL 要求開工先查既有 roadmap，沿用相同範圍的工作項目，缺少時才新增，並連到對應 swc、change 或 doc。這是工作流程規範，SHALL 不增加阻擋定版或封存的無連結門檻。

#### Scenario: Resume existing work
- **WHEN** 接手者繼續已有 roadmap 項目的 change
- **THEN** 說明指示沿用該工作與連結，不要求再新增一筆

#### Scenario: Start new work
- **WHEN** 專案沒有這次工作的 roadmap 項目
- **THEN** 說明指示新增並連到實際工作；在空 roadmap 上不假裝已有 W-id

### Requirement: Generated instructions follow current owner rulings

內建 skills、指令說明及產生的 AGENTS.md SHALL 一致使用現行流程：資訊與裁定分開、語意不清才覆述確認、roadmap 看現況、handover 整份重寫。角色可順序交接，SHALL 不指示不受支援的並行寫入，也不指向已移除的 govern 或 brief。

#### Scenario: Regenerate project instructions
- **WHEN** 專案重新執行 init --agents-md
- **THEN** 新區塊與內建 skills 使用相同現行規則，保留區塊外的專案規則

### Requirement: Handover freshness is visible

交接單 SHALL 保持單份整份重寫，並記錄足以比較交接時專案紀錄狀態的資料。讀取時若治理、工作、規格、證據或受管理文件狀態已改變，SHALL 提示交接可能過時；同一天的變更也須可辨識。單純讀取或未改變內容的檔案時間變動不應造成過時提醒，提醒 SHALL 不阻擋工作。

#### Scenario: Records change on the same day
- **WHEN** 寫完交接單後，同一天新增裁定或更新任務證據
- **THEN** 讀取交接單時顯示非阻擋過時提醒及查現況的指令

#### Scenario: Rewrite against current state
- **WHEN** 交接單按目前狀態整份重寫，之後專案紀錄內容未變
- **THEN** 過時提醒消失，讀取本身不再次使交接單過時

#### Scenario: Legacy note without freshness data
- **WHEN** 讀取沒有新鮮度資料的舊交接單
- **THEN** 原內容仍可讀，顯示無法確認新鮮度並建議下次交接重寫，不宣稱它是最新
