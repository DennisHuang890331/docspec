## Why

文件與軟體修改散在兩個根目錄，接手需先猜領域才能找紀錄。使用者核定保守整理：共用容器與查詢，保存兩域格式及完成條件。

## What Changes

- 新軟體 change 放共用 changes，舊路徑仍可操作。
- 唯讀 change／change show，JSON v1，沿用既有判定與來源。
- 明確 migrate：全批次預檢、內容不變、中途失敗回復。
- 寫入防護、交接、roadmap、匯入與封存配合共用路徑；封存乾跑唯讀。

## Capabilities

### New Capabilities
- `change-navigation`: 共用容器與領域查詢。

### Modified Capabilities
無。

## Impact

不新增紀錄種類；文件 targets／staging 與軟體 delta／test／task 各自保留。合成測試及全新接手驗證，不提交、不推送。
