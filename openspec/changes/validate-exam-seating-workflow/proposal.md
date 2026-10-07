## Why

負責人要求驗證整個 ArtiSpec 流程，並同意沿用考場座位題目、縮小功能範圍。既有回歸與接手查詢不能代替完整交付；先前六案仍保留未通過及環境限制的紀錄。

## What Changes

- 準備兩班共 16 位合成學生、兩間各 4×4 座位的教室，僅做 CSV 匯入、排座位、座位表輸出。
- 完成初版軟體交付及一份手冊的定版、PDF、proof，再追加容量／剩餘座位一次變更；變更未完成時由全新會話接手至第二次交付。
- Windows 與實際 WSL Linux runtime 使用相同契約；題目、負責人回答、評分資料隔離，記錄實際已安裝入口的命令與結果。
- 先準備案例、再執行；目前只有 Codex，產品以 provider 判定角色而阻擋獨立會話。另提身分修法供負責人裁定，本 change 不暗中改產品判定。

## Capabilities

### New Capabilities
- `exam-workflow-validation`: 可追查、分平台的縮小版完整流程實測。

### Modified Capabilities
- None. 本案不修改產品完成條件或紀錄格式。

## Impact

新增案例產生器、機械契約測試與實測紀錄；實測資料放 repo 外。README 後續修訂仍留開發 roadmap，這次不重寫 README、不重跑升級案、不宣稱先前六案通過。
