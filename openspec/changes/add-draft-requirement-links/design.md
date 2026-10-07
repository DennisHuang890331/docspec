## Context

目前 `requirement_index_entries` 只索引正式 req:。文件的 realizes 檢查將未知前綴視為 corpus id；`deps_doc_fingerprint` 僅排除字面 req:，會把新語法誤當文件硬依賴。軟體封存已保存封條 baseline 的 capability 指紋、change 身份、folder 與可選 renames，沒有可任意補造的完整舊規格副本。

負責人已明確授權採用 F2 提案與本輪實作，README 不在此輪。動機與可見行為見 proposal 和 delta spec。

## Goals / Non-Goals

**Goals:**

- 集中需求來源判定，讓投影、指紋、檢查及摘要一致。
- 先驗身份、sealed 讀取與 base 衝突；沒有足夠資料就回診斷。
- 保留兩領域獨立完成、歷史 bytes 及原引用。

**Non-Goals:**

- 不新增 stores、索引檔、baseline 欄位、情境草稿語法或 roadmap 成果類型。
- 不改需求完成、簽收或證據演算法；不主動掃描外部 repo。

## Decisions

1. 在 `software/links.py` 建立 `resolve_requirement_source(layout, ref)`。結果包含 original-ref、source-kind、state、source-ref、change、baseline、statement、fingerprint、based-on 與 diagnostics。state 區分 draft、formal、retired、unresolved、base-conflict、unknown；不得以正式 id 存在代替落地證明。
2. 活動來源先讀唯一 change，再沿用現有 preview_specs 投影與衝突檢查；依 touched_refs 找實際變動的需求，沿用投影 renames。只展開文件實際引用的 draft，避免將整個軟體草稿變成文件的另一份全域狀態。
3. 封存來源讀唯一容器、原 deltas、唯一已封條 baseline；確認 change、容器名稱與能力指紋，再使用既有 renames 找正式入口。合法 shared／legacy 搬移不要求舊 folder 全路徑仍存在。沒有舊全文時不重造舊來源，也不強行對目前完整 spec 指紋做相等檢查，因為後續合法變更應可追查。
4. 文件索引條目帶 source-kind 與 source metadata；原正式 req: 的指紋輸入保持相容。draft 指紋包含規範句、情境的 WHEN／THEN、verification 與 based-on；描述性標題、mtime 與測試 verified-by 位置不屬這份規則指紋。不把來源由 draft 變 formal 本身當作文件改寫授權。文件專屬指紋以共用軟體來源種類排除兩種前綴。
5. draft 未解析錯誤放入 software_errors，realizes 的 corpus 死引用檢查不再錯認它。文件投影仍能顯示不完整來源；check 整體退出碼仍反映軟體問題。原正式 req: 檢查語義保留。
6. 追溯圖使用原 draft 節點與實際依據，封存後也連至落地正式需求。摘要只沿已建立的文件連結查來源和治理依據，不能自動改引用或清除可疑標記。

## Risks / Trade-offs

- 舊 baseline 的資訊不足以證明特定來源 → 明示 unknown；不能為避免診斷而補寫歷史。
- 同名容器或壞封條造成不唯一來源 → 使用既有身份檢查與 sealed 讀取，列出診斷，不猜替代者。
- 新 metadata 意外改變舊正式指紋 → 正反回歸檢查原 req: 及無關來源，只有新 draft 加入額外來源指紋。
- 文件新語法錯入硬依賴 → 來源種類排除與可定版／軟體不能封存的配對案例。

## Migration Plan

不搬移或重寫資料。新語法只在明確建立連結時啟用；舊證據、文件版本、簽收與 baseline 不重新封條。生成規範、skill 版本與裁定記錄由本輪主代理整合；根 README 留待後續定稿。
