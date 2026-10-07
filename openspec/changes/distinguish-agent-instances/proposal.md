## Why

不同 Codex 會話同為 gpt，現行引擎以工具名稱比對，誤擋獨立測試簽收。負責人明確裁定「都是GPTagent沒有關係不應該被拒絕」，並要求解決。測試／實作分工應區分實際會話，不能要求換供應商。

## What Changes

- 沿用工具前綴及現有 tests.yaml／tasks.yaml，新增可選會話欄位。
- 同工具有不同實際會話碼時允許分工，同會話仍不能簽收自己的實作測試。
- 作者修改、刪除、簽收、異議與同作者診斷共用判定；簽收仍核對原有指紋。
- Codex 自動使用 CODEX_THREAD_ID；沒有可偵測碼時接受控制器保存的 DOCSPEC_ACTOR_ID，與真實碼衝突則報錯。
- 舊紀錄缺碼沿用保守 provider 判定，不回填歷史，不新增 store 或並行寫入。

## Capabilities

### New Capabilities
- `agent-instance-identity`: 同供應商不同會話的角色判定與相容處理。

### Modified Capabilities
- None.

## Impact

影響軟體任務／測試寫入、作者權限與診斷；不改 ID、封條格式、完成算法或測試／情境指紋。更新生成規範、test／implement skills 版本及指南。新 wheel 與兩平台回歸驗證此修正，完整考場流程另依其 change 管理。
