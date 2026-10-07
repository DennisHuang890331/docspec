## Context

既有 _cmd_archive 的 notes 提醒只檢查文字是否超出標題／--why 種子，但將此檢查誤稱為人的裁定缺失，且在真正 archive 檢查前輸出 Archiving anyway。已有治理原話仍被要求重複記錄，未完成 target 或 fork drift 拒絕時也可能誤導讀者。

## Goals / Non-Goals

**Goals:** 提醒說明其真實範圍、指向既有治理來源；交付指引不自行加強限制，不以來源測試冒充實際交付驗證。

**Non-Goals:** 新掃描或解析 notes 引用、裁定完整性判斷、新必填表單、跨域完成閘門、產品並行寫入、F2 引用格式、README 定稿或改寫歷史。

## Decisions

1. 保留 notes 的既有機械觸發條件；只替換提示。額外理由或引用文字仍不觸發。是否有文字不是來源已驗證的證明。
2. 提示提供 ruling／info／decision list 查詢入口；已有原話不重抄，不因提示補造裁定。不新讀治理紀錄、不寫 notes，不調整 archive gate 的順序。
3. 只有真正 run_archive 成功才輸出封存成功；非阻擋提示明示 target completion 與 fork-drift checks 仍適用。
4. 窄補 propose／verify 及生成規範：依記錄的限制驗收，指出未涵蓋環境；取完成後交付包，核對 latest 的待驗敘述。新定版仍須負責人明確要求，文件與軟體完成互不阻擋。
5. 不把特定案例的 NTFS、GUI 或整機斷網變成全部專案的必測條件；也不要求新工具或測試表單。

## Validation

獨立測試角色建立真正 file-target archive 七案，確認成功落地、未完成及 fork drift 拒絕、原 notes／治理 bytes 不變。保存原始 RED 與最終 GREEN；首次競態下的通過另列而不冒充 RED。兩平台執行相關回歸、已安裝 wheel 驗證及 strict validation；平台、略過與未重跑範圍分開記錄。
