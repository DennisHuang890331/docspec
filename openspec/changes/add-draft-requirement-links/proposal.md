## Why

文件與軟體一起開發時，文件無法引用尚在軟體 change 中的新需求，只能等軟體封存後再補連結。這會讓合理的文件工作失去明確來源，或誘使操作者提早封存尚未完成的軟體。

## What Changes

- 新增 `draft-req:<change-id>/<capability>/R<n>`，只支援文件 `concept.realizes` 的需求層級。
- 活動 change 只解析它實際變動後的需求；有 base 衝突就回報原因，不猜另一個來源。
- 正式封存後，以既有已封條 baseline 與 renames 確認落地入口，保留原引用並跟隨目前正式需求。
- 文件投影、檢查、指紋、追溯與工作摘要共用來源結果，明示草稿、正式、退役、缺失或不可讀。
- 草稿引用與來源診斷屬軟體領域，不新增文件定版閘門；不自動改連結、重新簽收、重跑測試或改寫歷史。

## Capabilities

### New Capabilities

- `draft-requirement-sources`: 文件明確引用指定軟體 change 的變動需求，以及封存後可追查的正式來源。

### Modified Capabilities

無；現有 `openspec/specs/` 沒有已建立的對應能力規格。原 `req:` 仍只代表正式來源。

## Impact

涉及 `engine/software/links.py`、文件來源索引與指紋、check 軟體診斷、追溯圖、工作摘要及來源投影。沿用現有資料與 sealed 讀取，不增加保存檔案、baseline 欄位或 roadmap 成果種類。文件生成規範與範例由主代理整合；README 依負責人要求留待另案。
