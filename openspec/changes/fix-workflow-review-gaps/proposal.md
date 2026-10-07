## Why

縮小版考場流程實測發現資訊引用使已封存軟體工作仍進行中且缺原因、查核新稿卻投影正式舊稿，以及工作摘要重複完整歷史簽收範圍。負責人審閱修法後已授權第一批實作，要求記錄具體差異及驗證。

## What Changes

- roadmap 的資訊與決策同作背景依據，成果仍沿用原領域完成判定，補齊未完成原因。
- get／instructions／find／check／diff 預設正式內容，指定 change 才讀同一只讀 union；顯示來源，不用舊稿冒充缺失或過時 preview。
- 工作摘要預設 JSON v2，以指紋及來源替代重複的歷史簽收全文；明確提供 v1 相容讀取。
- 同步 skills／生成規範／指南與版本，澄清歷史、交付及治理權威來源。

## Capabilities

### New Capabilities
- `followup-workflow-review`: 實測缺口的狀態、明確查核上下文及摘要相容修正。

### Modified Capabilities
- None. 既有領域完成算法重用；本 change 的新增要求描述這批修正，不覆寫封存規格。

## Impact

Python CLI、只讀投影、生成規範與 skills；get 的預設與摘要 JSON v2 是已核定的可觀察改動。Windows／實際 WSL Linux 以合成資料驗證。不變更保存紀錄格式、凍結歷史或完成所需證據。F2 草稿需求引用留待第二批；README 待辦不替負責人結案。
