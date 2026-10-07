## Why
README 需要提供精簡的 ArtiSpec 入口，完整文件／軟體流程與尚未發布功能的本機安裝方式放在連結的操作指南。安裝與流程宣稱須由實際已安裝入口的紀錄支持。

## What Changes
- 重整英文 README：用途、開始使用、共同導航與兩域流程概要；依後續明確裁定，首頁不出現舊名稱，完整本機安裝、操作與升級邊界移至 `docs/user-guide.md`。
- 手動執行六案隔離的全新 agent 實測，測試與審查角色獨立。
- 案外保存命令與事實核對資料，分開記錄工具、環境與 agent 問題。

## Capabilities
### New Capabilities
- `readme-workflow-validation`：可操作的說明文件與驗收證據。
### Modified Capabilities
無。

## Impact
不新增紀錄種類或完成規則。agent 驗收手動啟動，CI 維持機械回歸。若實測找到需要改完成規則的缺口，先提出具體方案交負責人裁定。
