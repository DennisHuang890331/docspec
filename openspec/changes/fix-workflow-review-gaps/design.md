## Context

F1 與 F3 有實測來源，O4 有原始 JSON 大小及重複路徑；A1 為 agent 對歷史保存的過度解讀，修正指引而非改歷史儲存。後續核定取代先記錄的局部限制，裁定見 system-design.md。

## Goals / Non-Goals

**Goals:** 依據不冒充工作成果；同輪查核用同一明確上下文；摘要保留必要事實且避免重複全文；舊輸出有明確相容路徑。

**Non-Goals:** 草稿需求新命名空間、另一份進度 store、產品並行寫入、自動測試／重新簽收／語意判斷、改寫舊案例或 README 定稿。

## Decisions

1. D／I 由引用種類推導為背景，不增保存欄位。缺失與結構問題仍先診斷；資訊取代／撤回保留原引用與影響，完成歷史不重開。
2. 共用純讀取的文件 Context，正式底稿加指定 staging（含新文章、group、刪除及全域來源）；query hooks 僅讓既有 readers 取得本次 view，不建立落地副本或 disk cache。
3. get 改預設正式、--official alias 保留，--change 明確指定活動文件變更。查核 JSON 加上下文／來源 metadata，原主要 keys 保留；get raw YAML 不混入 metadata。
4. preview 未生成或落後須診斷；需要散文的 find／diff 不得回假 clean。結構 check 不需要散文 preview，但仍檢全專案及分列軟體問題。
5. 摘要共用原 build／完成判定。v2 的 signed 保留簽署與指紋，scope-source 提供原 tests.yaml 與 change show 入口，verification-scopes 按版本／指紋整理來源。v1 明確選取，不改 sealed 內容。
6. skills 只補影響決策的操作差異；既有 user 授權、role separation、非阻擋追溯與明確 freeze 要求保持。每份改動 skill 提升版本，生成 block 版本亦提升。

## Risks / Trade-offs

- get 使用者須在變更內帶 --change；生成規範、skills 與指南同步避免讀寫對象分歧。
- union 不能用正式 store 的查核結果代替 staging 的 group／父鏈；破損封條不能因 union 載入而洗白。
- 相同 ID 的不同歷史指紋不能合併；摘要原始全文仍可查，不以輸出縮短幅度作主要驗收。
- source integrity／必要證據與純提醒保持分開，不能以背景引用修法放寬軟體封存或文件定版。

## Validation

獨立測試先 RED 再 GREEN，原測試檔由測試角色所有；實作者依來源檔案所有權分工。執行相關回歸、Windows／實際 WSL Linux 完整回歸及 strict validation；實際 installed wheel 與隔離 query 行為另驗，結果不冒充全新 agent 或原考場重測。需要 skill 前向驗證時以隔離合成草稿、沒有答案的新 agent 只做查核，保留原始命令及受管理指紋。
