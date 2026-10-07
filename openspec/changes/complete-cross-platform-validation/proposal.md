## Why

Linux 先前缺少排版工具，且只有 Windows 完成兩次全新接手，不能代表兩平台完整驗收。

## What Changes

用既有 setup 安裝 Linux 釘版工具與字型，執行雙平台完整回歸與 PDF/proof。摘要完成後兩平台各跑正常/過時全新 agent 接手，事前保存案外事實與內容指紋，獨立核對。

## Capabilities

### New Capabilities
- `cross-platform-handover-validation`: 雙平台機械回歸與手動接手驗收。

### Modified Capabilities
無。

## Impact

合成隔離案例；不更改系統執行政策、不放寬測試。CI 僅機械回歸；全新 agent 於流程改動或發布前手動啟動。
