## Why

同題實測發現 `roadmap show` 為問題提供不存在的 `question show`。獨立測試另重現工作與里程碑的同類入口錯誤；提示成功查出來源，卻無法讓接手者開啟原紀錄。

## What Changes

- 修正摘要的問題、工作、里程碑來源提示，使用現有唯讀指令。
- 覆蓋問題的各種有效狀態，保留原題內容及已回答／撤回問題的查詢入口。
- 文字與 JSON 沿用同一份摘要；查詢不寫檔、不執行驗證、不改完成判定。
- 分開保存修正前後測試及安裝版本，不回填實測的原失敗。

## Capabilities

### New Capabilities
- `work-summary-source-commands`: 摘要提供可實際執行的既有來源查詢。

### Modified Capabilities
- None.

## Impact

只調整摘要來源的命令提示與行為回歸。不新增 CLI 子命令、紀錄種類或資料格式；README、歷史裁定、封存來源及原案例不改。這是已授權的工具缺陷修正，獨立於尚待裁定的 roadmap unlink 提案。
