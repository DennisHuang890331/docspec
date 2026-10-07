## 1. Independent behavior tests

- [x] 1.1 測試角色建立唯讀新／舊版本發現、同版雙副本拒絕、保留目錄與初次freeze案例。
- [x] 1.2 測試角色建立snapshot/assets完整凍結、工作圖變動、缺圖不fallback、Read／Write防護案例。
- [x] 1.3 測試角色建立migration乾跑／全批次預檢／hash與路徑碰撞／中途回復／重跑，以及sealedbaseline、unknown asset／proof provenance、register-legacy all搬移與保留名稱案例。
- [x] 1.4 測試角色建立按版export/proof、preview與latest輸出隔離及舊版不prune案例。
- [x] 1.5 獨立角色先建立 history symlink／directory 拒絕及普通檔反例，另建立 handover 忽略再生產物、仍追蹤來源圖片的案例；保存修前與修後證據。

## 2. Layout, freeze and migration

- [x] 2.1 實作新write路徑、舊read fallback、duplicate拒絕、article history路徑與普通change排除版本樹；依1.1驗證並核對文件契約。
- [x] 2.2 實作完整snapshot資產保存、hash與hook防護、初次freeze與失敗回復；依1.2驗證，不更改獨立行為案例。
- [x] 2.3 實作 `versions [article] [--json]` 與 `versions migrate [article] [--dry-run]`，保持原snapshot／sealedbaseline、不洗白manifest；依1.3驗證與遷移說明核對。
- [x] 2.4 history 路徑於 render／capture 前預檢，handover 排除版本輸出且保留來源追蹤；依1.5驗證，不擴成整條 freeze 的跨檔交易。

## 3. Export and proof

- [x] 3.1 實作選定版snapshot/assets、版本exports/proof、preview與既有latest輸出；依1.4驗證。
- [x] 3.2 核對缺圖診斷、版本選取與格式再生未改snapshot／baseline；用實際PDF/proof產物驗證。

## 4. Documentation and review

- [x] 4.1 更新核定裁定、現行設計、操作指南、CHANGELOG及僅release skill路徑／版本；README保持既有短版。
- [x] 4.2 執行OpenSpec strict validation、release skill YAML／name／version 檢查與文件連結／路徑核對，結果據實記錄，保留既有 compatibility。
- [x] 4.3 獨立review檢查實作、測試語意、原hash／sealedbaseline保存與錯誤回復；不改原驗收案例，history follow-up 另以獨立測試角色先建立新檔案再修來源。
- [x] 4.4 完成 Windows／實際 WSL Linux 全套回歸、PDF/proof、最終 wheel 新安裝／升級及已安裝版本查詢／搬移；結果與 skips、前輪六案限制記於 `docs/dev/validation/document-version-storage-run.md`。
