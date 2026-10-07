## Context
本次核定只改執行名稱，保留安裝套件與資料格式。修改前先在 repo 外保存當時 checkout 的 wheel，作為隔離升級的基準；不冒稱已發布版本。

## Decisions
- Console metadata 只列 artispec；逐項區分命令、套件名、路徑與紀錄識別碼。
- 由舊／新執行檔 basename 與 hook 子命令判斷歸屬；混合項目保留其他工具的子項與設定。
- 寫入前解析及驗證設定；JSON 或 hook 結構損壞時報出路徑與原因，保留原始內容。
- 找不到新入口時提示 PATH，不選 docspec。既有封存紀錄不改寫。

## Validation
測試角色先建立會失敗的正反案例，再由實作者修復。驗證兩平台安裝、舊版升級、空白／中文路徑、hook 實際攔截與設定保留、回歸、PDF／proof 與 strict validation；環境限制另記。
