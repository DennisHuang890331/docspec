## Purpose

讓負責人與接手者能相信軟體任務的完成及封存結果：必要測試確實執行、證據對應目前需求與測試計畫、最新失敗不會被掩蓋，並保留既有歷史供查證。

## ADDED Requirements

### Requirement: Required scenario evidence before archive

系統 SHALL 在封存前確認每個新增或修改且以測試驗證的情境，其必要規劃測試都有對應實作任務的有效執行證據，或該實作任務有適用且有效的豁免。修改需求的行為規範句時，其現有情境也 SHALL 納入此檢查。只有測試計畫、只有檢查紀錄或匯入的完成標記，不足以證明測試驗證完成。

#### Scenario: Planned test omitted from task execution
- **WHEN** 兩個必要情境分別有 T1 與 T2，任務只執行 T1 且通過
- **THEN** 封存被拒絕，指出 T2 所屬情境缺少任務連結或執行證據
- **AND** 正式規格不新增 T2 的 verified-by

#### Scenario: Complete linked evidence
- **WHEN** 必要規劃測試均連到實作其需求的任務，且各任務的最新證據有效通過
- **THEN** 此項檢查通過，保留既有的其他封存檢查

#### Scenario: Valid waiver
- **WHEN** 實作必要需求的任務有仍有效且對應目前任務範圍的豁免
- **THEN** 其豁免範圍可免除測試證據要求，結果明示含豁免，不宣稱測試已通過

### Requirement: Latest attempt controls task verification

系統 SHALL 先選取同一任務及驗證方法的最新適用執行，再判斷成功、覆蓋與新鮮度。收集失敗、執行器失敗、逾時、未產出報告或只跑到部分測試，均 SHALL 保留為該次驗證未通過，不能退回舊成功。

#### Scenario: Latest attempt runs no planned tests
- **WHEN** 任務先有成功證據，下一次因篩選條件收集不到任何測試而失敗
- **THEN** 任務不再顯示完成，封存被拒絕，原因指向最新一次失敗

#### Scenario: Successful retry
- **WHEN** 失敗後重新執行全部必要測試並通過，且證據仍新鮮
- **THEN** 任務恢復完成，舊失敗保留在歷史

### Requirement: Evidence and signoff correspond to current verification scope

系統 SHALL 將完成證據對應到當時的需求、情境、任務驗證方法、測試計畫、執行政策與宣告檔案。測試簽收 SHALL 對應當時測試內容及其所承諾的情境。相關行為、測試位置、對應關係或略過政策改變後，舊證據不足以完成目前工作。

#### Scenario: Changed outcome after passing evidence
- **WHEN** 測試成功後，原情境的 THEN 被改成另一個要求
- **THEN** 受影響測試需要重新審閱簽收，相關任務需要重新產生證據；原有成功不能直接封存

#### Scenario: Test redirected inside the same file
- **WHEN** T1 已成功執行，之後其位置改到同一檔案的另一個測試
- **THEN** 原簽收與證據不能驗證新位置；即使檔案位元組未變，任務仍需重新簽收與執行

#### Scenario: Independent work remains valid
- **WHEN** 只修改另一個不被該任務實作或驗證的需求，且該任務的其他受監看內容沒有改變
- **THEN** 該任務的有效證據不因整份 change 有變動而失效

### Requirement: Legacy verification remains visible without false completion

系統 SHALL 保留舊證據與已封存紀錄。進行中工作使用缺少驗證範圍資料的舊證據或簽收時，SHALL 明示需重新簽收或驗證，不自動補填資料使其看似涵蓋現在的需求。此修正 SHALL 不重開或改寫已封存 change。

#### Scenario: Active legacy evidence
- **WHEN** 進行中任務僅有無法判斷需求與計畫版本的舊證據
- **THEN** 查詢可讀取原紀錄，完成判定提示補驗證，補齊後可正常完成

#### Scenario: Archived historical record
- **WHEN** 查詢升級前已封存的 change
- **THEN** 封存內容與當時狀態保留，歷史證據不被自動升級或覆寫

### Requirement: Portable test runner paths

系統 SHALL 保留已設定測試執行器的合法 Windows 路徑、引號及開頭環境變數，並維持 POSIX 指令的既有行為；遇到無法解讀的設定時 SHALL 明確指出格式問題。

#### Scenario: Windows executable with spaces and environment prefix
- **WHEN** Windows 的 test-command 使用環境變數前綴，以及以雙引號包住、含空白與反斜線的 Python 絕對路徑
- **THEN** 引擎能啟動該執行器、傳入環境變數及完整測試位置，並以 JUnit 結果判定

#### Scenario: Existing POSIX command
- **WHEN** test-command 使用既有 POSIX 引號與環境變數格式
- **THEN** 原有參數內容及環境變數仍正確傳給執行器
