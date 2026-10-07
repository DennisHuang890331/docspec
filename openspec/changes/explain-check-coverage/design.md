## Context

既有 run_check 實際掃 selected_latest 圖片與正文錨，包含存在的過時預覽；preview_diagnostics 只評估 change 預覽，正式正文沒有同步評估。負責人已授權說明改進，判定不變。

## Goals / Non-Goals

新增可核對範圍；不新增同步判定算法或語意檢查，不把 preview 診斷變硬閘。

## Decisions

- query/check.py 在 run_check 與既有 diagnostics 後組 coverage.version=1。structure={scope:project,status:passed|failed}，software.status=passed|issues。
- prose.check=asset-references-and-anchors；articles 依所有 leaves 的 article 去重，每筆 references={status:performed|not-performed,path}、current_prose={status:current|deferred|not-assessed,reasons}。正文不存在 deferred 並列 prose-missing；預覽診斷原樣保留；官方存在標 not-assessed，不因 diagnostics 空而說 current。
- prose.semantic_review 與 delivery_review 均 not-performed。文字與 JSON 共用物件；舊 ok/errors/index/退出碼保留。這比另跑正式正文同步更窄，避免在查核說明中寫第二套完成算法。

## Risks / Trade-offs

performed 可能被誤解為通過 → 說明只表示引用掃描執行，錯誤仍看原 errors；官方同步未評估 → 明示可用 status 查同步，不冒稱已完成。

## Migration Plan

JSON 純新增欄位，文字補說明；舊紀錄、證據、封條與資料格式不變。
