## Why

指令已改成 artispec，但 Python 安裝套件與使用者工具目錄仍沿用 docspec，造成使用者以為未完成改名。負責人於 2026/10/07 核定完整安裝命名及升級處理，並將目前開發分支改為 dev、整理提交後推到遠端 dev。

## What Changes

- **BREAKING** 安裝 distribution 改為 `artispec`，唯一 console script 仍是 `artispec`；保留 Python `dspx` 與專案資料 `docspec/`、`corpus`、`DOCSPEC_*`、管理標記。
- 使用者工具根改為 `platformdirs.user_data_dir("artispec", appauthor=False)`；新增明確、離線的 `setup --migrate-data`，保留舊來源，核對資產並重指已知 lock 路徑，不覆寫目的衝突。
- 修正新 distribution 的安裝來源解析、升級指令與 dev 更新檢查；同步安裝說明與裁定，不把 README 宣稱定稿或 PyPI 已發布。
- 將本機開發分支改為 dev，完成核對與提交後推到遠端 dev；未完成流程驗收照實標示，不動 main、不開 PR。

## Capabilities

### New Capabilities
- `artispec-installation`: 安裝命名、來源識別、受控工具目錄及舊版本安全升級。

### Modified Capabilities
無。現有正式規格的工作摘要與工程文件要求不變。

## Impact

pyproject／lock、安裝來源與更新提醒、paths／setup／doctor、新舊 wheel 升級驗證、Windows／實際 WSL Linux 回歸、安裝指南與開發紀錄。真實專案資料不進 repo，歷史封條與原實測結果不改；roadmap unlink 修法仍待裁定，本批不實作。
