## Why

前輪外層編碼、會話核對、GUI 時序與產物取樣造成控制器失敗或評分誤判。負責人已授權改善驗收基礎設施，讓重跑保留真實結果且與產品缺陷分開。

## What Changes

- 共用 UTF-8 命令紀錄、會話／階段身分及原退出碼；保存實際啟動輸入。
- 從實際 Codex 事件核對 shell 操作，去除重複開始／完成事件，缺紀錄明示。
- 唯一定位來源與受控 Windows／WSL 路徑；GUI 等待實際條件。
- 完成包停止寫入後做前後 manifest 核對、不可覆寫的 checkpoint；分清快照、歷史、測試來源與公開投影。

## Capabilities

### New Capabilities
- `workflow-validation-recording`: 可核對的執行紀錄、來源定位與完成包取樣。

### Modified Capabilities
無。

## Impact

scripts/validation 的 evaluator 工具與控制器整合；評分資料仍在案外，原實測不改寫，產品判定不變。
