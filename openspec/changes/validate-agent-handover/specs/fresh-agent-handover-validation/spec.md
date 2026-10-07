## ADDED Requirements

### Requirement: Fresh agents can recover current work from project records

驗證 SHALL 使用兩份隔離合成專案與無前文 agent；參與者 SHALL 引用資訊來源、沿用工作項，查閱現況後才整理交接；SHALL 不使用真實資料。

#### Scenario: Current handover
- **WHEN** 接手正常交接且測試待簽收的專案
- **THEN** 接手者指出既有工作項、待簽收測試與可執行下一步

#### Scenario: Stale handover
- **WHEN** 交接後決策取代、出現最新失敗證據且文件未定版
- **THEN** 接手者辨識四項狀態與來源，依現況更新交接，不誤報完成

### Requirement: Review separates workflow defects from agent behavior

獨立審查 SHALL 對照預先建立的事實清單，分別記錄資訊缺漏、輸出誤導與 agent 忽略資訊；報告 SHALL 提出工作摘要後續需求，不在本批新增該介面。

#### Scenario: Assess handover results
- **WHEN** 兩份接手結果完成
- **THEN** 審查逐項列出證據與限制；只有流程缺陷列入修正，不以單次成功保證所有 agent
