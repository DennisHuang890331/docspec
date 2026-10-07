# 交接與驗證證據的過時原因

## Why

系統可以判斷過時，但整體指紋與一般錯誤訊息無法指出哪些內容改變，增加接手成本。

## What Changes

交接附加受管理檔案指紋清單；文字與 JSON 顯示一致的變動清單；驗證範圍差異顯示欄位及相關識別碼。

## Capabilities

### New Capabilities

- `stale-state-diagnostics`：交接與驗證證據的過時原因；本 change 補充既有核定流程。

### Modified Capabilities

無；前次 fix-workflow-integrity 保留原狀。

## Impact

僅 docspec 開發工作分支，使用合成資料；不開 PR、不推送、不新增並行產品能力。
