## Why

最新已安裝版本的 `artispec guide develop` 仍要求裁定原話存進 change notes，與負責人已核定、且 skills／生成規範已採用的治理分工矛盾。這會讓依指令投影工作的 agent 重複保存裁定，是工具指引缺陷。

## What Changes

- 修正 section-driven workflow 的兩段治理說明：ruling／info 保存負責人原話，notes 保存變更理由並引用原紀錄。
- 保留明確內容直接記錄、不清楚才釐清的規則，以及必要測試／證據與領域各自完成的條件。
- 驗證完整、develop 與 JSON guide 使用相同來源，查詢不改寫合成專案。
- 記錄尚未核定的功能與後續同題比較，保留原實測結果。

## Capabilities

### New Capabilities
- `guide-governance-contract`: 指令投影與既有治理分工一致。

### Modified Capabilities
- None. 不新增記錄語法、欄位、完成算法或操作步驟。

## Impact

產品只調整內建 schema 的 workflow 敘述；guide 的程式與輸出結構不變。工程文件預設、F2、check 新輸出與 README 定稿仍屬待討論項目，不因修正既有裁定而一併實作。
