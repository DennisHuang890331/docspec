## Purpose

讓文件在軟體尚未完成時即可明確引用指定 change 的變動需求，並在封存後保留原引用與可驗證的落地入口。來源解析說明追溯與過時原因，不代表軟體完成，也不替使用者授權採用新規則。

## ADDED Requirements

### Requirement: 明確定位活動草稿需求

系統 SHALL 接受文件 concept.realizes 的 `draft-req:<change-id>/<capability>/R<n>`，只解析唯一指定 change 中實際受差異變動的需求，並先檢查既有 base 指紋。能力名稱可包含 `/`；第一版不支援情境引用。

#### Scenario: 新增與修改需求
- **WHEN** 文件引用活動 change 新增的需求，或修改需求或其情境所形成的需求
- **THEN** 投影取得該 change 變動後的需求，明示 draft 狀態與原引用

#### Scenario: 無關需求與不同 change
- **WHEN** 文件引用該 change 未變動的需求，或兩個 change 使用相同 R 編號
- **THEN** 未變動的需求回報 unresolved，兩個 change 的來源各自解析而不混合

#### Scenario: 基準衝突及情境語法
- **WHEN** 差異基準與目前正式規格衝突，或引用包含 R 後的 S 編號
- **THEN** 回報 base-conflict 或不支援的來源診斷，不投影看似有效的需求

### Requirement: 封存來源的落地與後續追查

系統 SHALL 使用指定 change 的既有已封條 baseline、容器身份及 renames，解析目前正式需求；保留原 draft-req 字串，並列 baseline 與正式入口。沒有有效且唯一的落地資料時 MUST 不借同編號正式需求猜來源。

#### Scenario: 封存與重配
- **WHEN** 指定 change 已正式封存，baseline 證明相應能力落地，且編號沿用或有保存的 renames
- **THEN** 顯示 formal 狀態、原引用、baseline 路徑及目前正式入口；能力名稱包含 `/` 與容器合法搬移仍可追查

#### Scenario: 缺失或不可讀資料
- **WHEN** baseline 缺失、封條損壞、容器身份重複、差異撤去，或需求退役
- **THEN** 分別提供 unresolved、unknown 或 retired 等明確診斷，不能冒稱已落地或換用另一個 change

### Requirement: 共用來源及過時說明

系統 SHALL 讓來源投影、check、追溯與工作摘要共用來源判定；需求、情境或依據變更 MUST 能影響文件的軟體來源指紋。查詢 MUST 唯讀，不能改寫連結、影響標記、簽收、證據、文件或舊基線。

#### Scenario: 相應來源變更
- **WHEN** 引用需求的 statement、情境或 based-on 變更
- **THEN** 文件沿用 stale-software 與影響提醒；mtime 或無關需求變更不造成該來源過時

#### Scenario: 投影與工作摘要
- **WHEN** 操作者查詢文件投影或相關工作摘要
- **THEN** 文字與 JSON 都提供原引用、來源狀態與必要診斷，保留有效治理依據與原查詢入口

### Requirement: 獨立完成與歷史相容

系統 MUST 保持文件與軟體獨立完成。草稿需求及其缺失診斷屬軟體來源，不能新增文件定版的軟體硬閘；原 req: 的正式來源意義、軟體必要證據及歷史 bytes SHALL 保持。

#### Scenario: 軟體未完成而文件就緒
- **WHEN** 文件按原規則就緒且負責人要求定版，引用的軟體 change 仍缺必要證據
- **THEN** 文件可以定版並記下軟體差異，軟體仍不能封存

#### Scenario: 查詢與舊版本
- **WHEN** 查詢含新語法或舊正式 req: 的專案及歷史紀錄
- **THEN** 不執行外部命令，不寫受管理檔案，不修改舊文件、證據、簽收或 baseline 的封條
