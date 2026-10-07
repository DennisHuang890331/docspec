## Why

`check passed` 容易被解讀成正文與交付皆通過；其實主要是結構與機械引用檢查，過時預覽仍可能被掃描。負責人已授權補足已查／未查範圍，維持原判定。

## What Changes

- JSON 新增版本化 coverage，文字從同一結果顯示。
- 全專案結構、引用掃描、預覽同步、正文語意與交付審查分清。
- 過時但存在的預覽標示已掃引用、正文待處理；正式正文同步未評估則明示。
- 保留 ok、errors、software_errors、index 範圍及退出碼。

## Capabilities

### New Capabilities
- `check-coverage-explanation`: 唯讀、與既有判定一致的檢查範圍說明。

### Modified Capabilities
無。

## Impact

query/check.py、生成指引及新行為案例；不執行測試、不渲染正文、不新增完成閘門。
