## Why

使用者要求「之前文件的版本峰存在changes裡面 docs我只想要留latest」，確認版本目錄提案後再以「可以你開始實作了嗎?」授權開始。定版 Markdown、圖資產、歷史與再生輸出須分開，避免歷史版依賴目前圖檔或混入普通 change。

## What Changes

- 新定版寫入 `docspec/changes/_versions/<article>/<version>/snapshot/document.md`；同版引用的受管圖資產保存在 `snapshot/assets/`，整個 snapshot 凍結。
- 各版 exports／proof 放在該版目錄，預覽放文章根的 `_preview/`；`history.md` 放文章根。`docs/` 保留工作稿、工作資產與既有 latest 輸出。
- 新增唯讀 `artispec versions [article] [--json]` 與明確 `artispec versions migrate [article] [--dry-run]`。省略文章時處理全部；查詢不搬移。
- 讀取保留舊 `docs/archive/` fallback；同版新舊並存必須報錯。遷移預檢舊 `.freeze.yaml`、內容 hash、碰撞及路徑；只對驗證通過的原 hash 換 key，不改快照或既有 sealed baseline。
- 無版號的舊 proof 收文章根 `_legacy-proof/` 並標來源版未知；既有 register-legacy 的任意歷史檔收 `_versions/_legacy/<name>/snapshot/`，不假造版本號，all migration 包含此 collection。
- 普通文件／軟體 change、`_archive/` 格式與兩域完成條件維持既有契約。初次 freeze 不須先建立新 change。

## Capabilities

### New Capabilities
- `document-version-storage`: 定版目錄、當版資產、唯讀發現、安全搬移與再生輸出。

### Modified Capabilities
無；既有 change 領域流程與 software 完成規則不重設。

## Impact

涉及 layout／freeze／version migration、export／proof 的版本選取、snapshot 防護、查詢與歷史路徑、操作文件及 release skill。使用合成測試，由獨立測試角色新增行為案例；實作與當輪驗證結果見 `docs/dev/validation/document-version-storage-run.md`，tasks 依實際證據勾選，不把先前六案或機械回歸當作此案已通過的證據。
