## Purpose

讓手動 agent 驗收保存實際命令、會話、環境與完成包來源，排除控制器編碼、時序與取樣造成的誤判；資料缺漏及外部失敗需明示，舊結果不可被新驗收覆蓋。

## ADDED Requirements

### Requirement: 真實執行紀錄
紀錄器 SHALL 保存 UTF-8 argv/cwd/退出碼/stdout/stderr/phase/session；事件讀取 MUST 去重開始與完成事件且明示缺失或未完成。

#### Scenario: 中文路徑與失敗命令
- **WHEN** 真實程序在含空白與中文的目錄以非零退出
- **THEN** 原輸出與退出碼保留，不把外層成功當程序成功。

#### Scenario: 事件缺漏
- **WHEN** 同一命令有開始與完成，或檔案缺失／事件未完成
- **THEN** 完成事件只計一次；不可取得的紀錄明示缺漏，不能自報補齊。

### Requirement: 來源與快照可信
來源定位 SHALL 只接受可唯一還原且在案例內的檔案；完成 checkpoint MUST 核對預期、複製前、複製後及來源複核的完整指紋，不覆蓋既有 checkpoint。

#### Scenario: 路徑可還原與歧義
- **WHEN** 提供相對、絕對或已宣告 WSL 映射路徑
- **THEN** 唯一實檔可定位；歧義、逃逸或無來源報錯，不以 substring 猜測。

#### Scenario: 作者仍在改檔
- **WHEN** 取樣前後新增、刪除或改寫檔案
- **THEN** 完成包被拒絕，不作通過評分；舊快照保持不變。

### Requirement: 互動等待與缺陷分類
GUI 驗收 SHALL 等待實際條件，超時記環境／控制器失敗；產品缺陷與 agent 忽略資訊分開，不降低產品原證據要求。

#### Scenario: 控制項尚未出現
- **WHEN** GUI 條件未成立
- **THEN** 等待至有限超時並保留失敗，不因固定延遲到時就宣稱成功。
