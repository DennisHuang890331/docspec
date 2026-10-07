## Purpose

讓負責人已記錄的裁定、豁免與驗收在後續變更中維持正確效力，防止撤回或過期的授權放行目前工作，同時維持文件與軟體各自管理的既定邊界。

## ADDED Requirements

### Requirement: Waiver remains tied to effective authority

系統 SHALL 在推導進行中任務完成與封存時重新確認豁免依據仍為有效裁定，且豁免對應目前任務範圍。裁定被駁回或取代後，該豁免 SHALL 不再作為完成依據，並列出原因。重啟條件的語意由負責人判斷，不要求引擎自行推論。

#### Scenario: Owner rejects waiver ruling
- **WHEN** 任務因裁定而豁免，之後負責人駁回該裁定，且沒有其他有效完成證據
- **THEN** 任務不再顯示完成含豁免，封存被拒絕並指出失效裁定

#### Scenario: Historical waiver does not hide later verification
- **WHEN** 豁免依據已失效，但目前任務已有最新且有效的完整驗證證據
- **THEN** 任務可依該證據完成，歷史豁免不遮蔽實際驗證結果

### Requirement: Rejected decision basis reaches dependent software work

系統 SHALL 沿已記錄連結顯示裁定駁回對決策、需求、任務、測試與進行中 change 的影響。軟體封存 SHALL 拒絕以依據已失效的決策放行，清除可疑標記不等於恢復失效依據。

#### Scenario: Rejected ruling behind active decision
- **WHEN** 軟體 change 引用有效決策，而負責人駁回該決策所依據的裁定
- **THEN** 影響檢視列出相關軟體工作，該 change 封存被拒絕並指出依據失效

#### Scenario: Unrelated change remains independent
- **WHEN** 被駁回裁定與另一個軟體 change 沒有依據或影響連結
- **THEN** 此裁定失效不單獨阻擋該無關 change 封存

#### Scenario: Archived work remains historical
- **WHEN** 受影響任務已封存
- **THEN** 系統標示需重看並保留歷史，不重開或改寫已封存任務

### Requirement: Owner acceptance applies to the current version

對需要負責人驗收的需求，系統 SHALL 分別判斷驗證是否完成及是否有目前範圍與內容的有效使用者驗收。agent 的 inspection 或 demonstration 成功 SHALL 不自動更新使用者驗收。

#### Scenario: Code changed after owner acceptance
- **WHEN** 使用者驗收版本 A，宣告檔案改成版本 B，agent 再為 B 寫 inspection 通過紀錄
- **THEN** 系統可承認 B 的 inspection，但封存仍要求 B 的使用者驗收或有效豁免

#### Scenario: Current acceptance
- **WHEN** 使用者已驗收目前需求及宣告內容，其他完成條件亦滿足
- **THEN** 使用者驗收檢查通過，不要求重複確認同一版本

### Requirement: Domain independence is preserved

系統 SHALL 保留文件與軟體互不阻擋的規則；本能力的軟體封存檢查不新增文件同步門檻，文件定版也不因無關軟體失敗而受阻。缺少依據連結的提醒 SHALL 仍為非阻擋提醒。

#### Scenario: Software failure alongside independently ready document
- **WHEN** 軟體 change 有失敗證據，但文件本身滿足定版條件
- **THEN** 文件仍可定版，既有差異紀錄保留
