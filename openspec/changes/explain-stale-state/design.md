## Context

使用者已明確核定本計畫；後續明確裁定取代舊規則，歷史保留。與先前 fix-workflow-integrity 未提交成果共存。

## Goals / Non-Goals

目標：交接附加受管理檔案指紋清單；文字與 JSON 顯示一致的變動清單；驗證範圍差異顯示欄位及相關識別碼。

不新增工作摘要、stores、workset、多使用者或並行寫入能力；不自動判斷需求語意。

## Decisions

保留 state-version=1 與原整體 hash 算法；新增可選 state-manifest={version:1,files:{path:sha256}}，由同次 _checked_content 讀取算出。只比較有效 manifest；缺漏／不相容清單只影響明細可用性，管理紀錄不可讀則 unknown。freshness changes 排序使用相對 POSIX 路徑。scope 診斷不參與判定，只增補既有原因。

## Risks / Trade-offs

manifest 隨受管理檔案數量增長，只儲存相對路徑與指紋；不擴大讀取範圍。舊資料缺乏明細不得臆測。

## Migration Plan

讀取兼容舊整體指紋；下次交接 write 才產生 manifest，不批次改寫舊資料。

## Validation

E11 獨立審查發現 testplan list 文字無法區分未簽收與已簽收，接手者被迫讀原始 YAML。沿用既有指令附加現行簽收狀態；JSON 保留原欄位並加 signoffs（test、status、problems）。判定重用 signoff_problems；無簽收為 unsigned、有問題為 needs-review，讀取失敗為 unknown，其餘 current。不改簽收、驗證或封存門檻。

測試角色建立正反案例，確認修前失敗；實作單次讀取 manifest、相容與文字／JSON 診斷；實作 scope 差異與既有 why/details 整合；執行相關與完整回歸及獨立審查。公開報告本機、跨平台及未執行界線。
