## Context

guide 直接投影 schema 的 workflow。先前修正 develop skill、生成規範及 archive 提醒時，schema 中的原話保存位置沒有同步。依既有裁定，治理紀錄是裁定／資訊的原始來源，change notes 是理由與討論，不是另一份裁定主檔。

## Decisions

- 只改 schema 的兩段敘述，保留其他 workflow 與模型契約。guide 完整文字、develop 子查詢及 JSON 都從該處讀取。
- 不要求補 notes、抄裁定或建立新檔案來通過封存；沿用現有完成與 drift 判定。
- 不把修正指引視為引擎能驗證對話真實性。保留 agent 遵循規則及人工審查的界線。
- 測試角色先重現舊指引再由實作者改來源；真實治理原話讀回與查詢前後指紋需一致。

## Validation

執行獨立投影案例、schema／guide／skills／init／archive 相關回歸，並在 Windows 與實際 WSL Linux runtime 使用新 wheel 的已安裝入口核對。報告區分本次窄幅驗證與尚未重跑的完整考場實驗，不回填舊結果。
