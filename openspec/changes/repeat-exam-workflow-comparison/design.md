## Context

見 docs/dev/proposals/repeat-exam-workflow.md 及原 exam-seating-workflow-run.md。四個產品／基礎設施 change 已授權，README 除外；修正與兩平台回歸完成後才固定新 wheel 開始。

## Goals / Non-Goals

核對同題流程與文件可用性，不增加功能、換讀者、放寬測試或回填舊結果。

## Decisions

- 沿用既有 build_exam_workflow_cases 的 case_contract、CSV、負責人答案及變更事件；案外先保存 prompt/protocol/oracle/wheel hashes。兩平台新案同輪來源，actual installed CLI 透過 recorder。
- 初版訪談／需求後另開 test 作者會話，實作角色不改測試。初版由控制器核對包／GUI／文件／接受後注入唯一變更，準備到未完成再派 fresh agent，無前文只公開資料與任務。
- 新 helper 保存啟動與 shell 事件、階段與真實 session；GUI 有條件等待；finalized 包先 checkpoint 再獨立審查。歷史、測試、公開投影分類核對，不把合法新增封存視為改舊封條。
- 兩平台完整回歸與 PDF/proof 記實際結果，Windows 現有隔離 helper 僅控制指定 EXE 的對外連線。無法完成就記失敗與影響，不假稱環境通過。

## Risks / Trade-offs

新會話不同模型／runtime 影響比較 → 保存實際版本，不宣稱因果。agent 忽略來源 → 獨立對照事實清單，不把行為當產品修正。長流程中斷 → 保存 checkpoint、同會話續接核對，不把續接叫 fresh。

## Migration Plan

不遷移舊案例，所有新實測在 repo 外；新比較報告與 roadmap 記結果，README 原 bytes 保留。
