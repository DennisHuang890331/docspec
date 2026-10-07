## Context

負責人核定完整相關摘要、問題優先；原始內容另查。追溯完整性只相對於既有連結。

## Decisions

引擎組合 roadmap、治理效力、文件同步/定版、證據推導及抽出的簽收檢視；CLI 只格式化。schema-version 為 1，包含 work、dependencies、governance、software、documents、actions、diagnostics。來源去重但不刪去理由；只走子工作、前置工作、refs 與必要來源。不走語意匹配或反向擴張至無關工作。

固定建議說明簽收、失敗證據、取代關係及未定版狀態，不代替負責人裁定。舊引用保留，取代紀錄顯示目前版本，不自動改連結。

## Risks and Compatibility

資料損壞須報錯；缺失及循環不能顯示完成。舊專案未啟用治理層明示需要 migration，不自動遷移。缺連結是涵蓋範圍警告，不自動創建完成條件。既有列表欄位與命令保留。
