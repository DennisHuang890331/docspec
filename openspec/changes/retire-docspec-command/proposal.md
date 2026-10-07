## Why
負責人明確要求移除舊指令別名。既有 hook 探查仍依賴舊入口，刷新時也可能刪掉其他工具的設定或覆寫損壞設定。

## What Changes
- 只提供 `artispec`；保留安裝套件、Python 名稱、資料目錄、環境變數與管理標記。
- 更新現行命令說明與生成規範，保留歷史紀錄原文。
- hook 解析新入口，只刷新自家 hook；損壞設定報錯並保留原檔。

## Capabilities
### New Capabilities
- `command-retirement`：移除舊入口與安全更新 hook 的行為契約。
### Modified Capabilities
無。本次授權取代 `rename-tool-artispec` 保留舊入口的部分；該 change 保留作為歷史紀錄。

## Impact
既有自動化須改用 artispec。在同一環境重裝新 wheel 會移除該套件原有的舊入口，不搬資料，也不清除其他環境的安裝。
