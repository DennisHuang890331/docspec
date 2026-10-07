## Why

縮小版考場實測發現：CLI 修改 change 自己新增的情境時，繞過一般 delta 欄位驗證，將 `--reason` 寫進情境；後續檢查又判定它是不合法欄位。相同捷徑也可能覆寫需求或情境編號。這是工具寫入與檢查不一致，屬本輪已授權修正的流程缺陷。

## What Changes

- 自己新增的需求、內嵌情境及新增情境，在修改前套用既有操作欄位限制。
- 不合法修改在寫入前報錯，原內容與封條不變；只更新該操作容許的正文欄位，不改既有編號。
- CLI 說明 `--reason` 用於移除需求或情境，修改操作不接受它。
- 由獨立測試角色先重現，再驗證合法修改、拒絕寫入、簽收與證據判定、實際引擎測試及封存。

## Capabilities

### New Capabilities
- `software-delta-validation`: 編輯 change 自己新增內容時，與現有 delta 操作使用一致的欄位限制。

### Modified Capabilities
- None.

## Impact

修改 `engine/software/changes.py` 與 CLI help，新增獨立回歸。沿用既有 schema、簽收、證據與完成算法；不新增原因欄位、紀錄種類或自動修復舊封條。重建 wheel 並以新隔離 runtime 繼續實測，保留原 wheel、原安裝及失敗紀錄。
