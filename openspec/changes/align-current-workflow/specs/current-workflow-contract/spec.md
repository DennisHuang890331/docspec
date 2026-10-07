## ADDED Requirements

### Requirement: Current instructions follow explicit superseding rulings

現行設計、驗收情境與產生規範 SHALL 依明確取代的負責人裁定一致化；歷史原文 SHALL 保留並註記取代關係，同日排列 SHALL 不作為取代依據。

#### Scenario: Read current requirements
- **WHEN** 讀取 SR2、SR8、SR11、SR21 與第三期規劃
- **THEN** 內容描述不清楚才覆述、追溯提醒非阻擋、完成需有效證據、交接整份重寫；S6 已取消而 base fingerprint 保留

#### Scenario: Consult historical ruling
- **WHEN** 查詢已被取代的覆述、brief 或並行裁定
- **THEN** 原文仍存在，且可找到明確的取代規則

### Requirement: Proposal checks consequential delivery constraints

提案及生成的協作規範 SHALL 查閱既有操作人、平台、啟動方式、安裝、連線與交付限制；只有缺漏且影響設計時才詢問，沿用資訊與裁定紀錄並更新內建版本。

#### Scenario: Known constraints
- **WHEN** 資訊紀錄已保存不能安裝及 Windows 雙擊操作
- **THEN** 提案引用既有紀錄，不要求重新確認

#### Scenario: Missing consequential constraint
- **WHEN** 啟動或交付方案取決於尚未知道的環境限制
- **THEN** agent 先詢問缺少條件，事實記資訊、選擇記裁定，不新增必填表單

#### Scenario: Regenerate instructions
- **WHEN** 使用者更新舊版 skills 與 AGENTS 區塊
- **THEN** 新規則涵蓋上述檢查，保留區塊外自訂內容
