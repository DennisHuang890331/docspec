## ADDED Requirements

### Requirement: Test plan listing exposes current sign-off state

既有 testplan list SHALL 以現行 signoff_problems 推導 unsigned、current、needs-review 或 unknown，文字按測試顯示狀態與原因；JSON SHALL 保留原紀錄並附加 signoffs（test、status、problems），不寫入受管理紀錄、不執行測試。這是 E11 找到的輸出缺漏修正，不新增查詢指令。

#### Scenario: Read unsigned and current tests
- **WHEN** 測試尚未簽收或其簽收仍有效
- **THEN** 列表可直接區分 unsigned 與 current，撰寫人標記不冒充簽收狀態

#### Scenario: Read changed or legacy sign-off
- **WHEN** 已簽收測試內容或情境改變，或舊簽收缺必要指紋
- **THEN** 顯示 needs-review 及原有驗證規則的原因

#### Scenario: Read unavailable signed test
- **WHEN** 已簽收測試無法讀取
- **THEN** 顯示 unknown 與原因，不誤稱 current，也不改寫測試或紀錄

### Requirement: Handover identifies changed managed files

交接單 SHALL 由同次受管理檔案讀取產生既有 state-fingerprint 與 state-manifest（version=1、files 為相對 POSIX 路徑至 sha256 指紋）；freshness SHALL 增加 changes-available 及 changes（path、kind=added|modified|removed）。

#### Scenario: Compare changed records
- **WHEN** 新交接後受管理檔案新增、修改或刪除
- **THEN** 文字與 JSON 列出相同差異，保留非阻擋 stale 狀態

#### Scenario: Read unchanged records
- **WHEN** 只查詢、修改 mtime 或外部非受管理檔案
- **THEN** 狀態仍 current，查詢不寫檔、不執行外部命令

#### Scenario: Legacy note
- **WHEN** 交接有可比較整體指紋但沒有有效 manifest
- **THEN** 仍依原算法判定 current/stale，changes-available 為 false 並明示無明細

#### Scenario: Unreadable state
- **WHEN** 紀錄不可讀或封條損壞
- **THEN** 回 unknown 且保留交接文字，不提供假完整差異

#### Scenario: Rewrite note
- **WHEN** 依目前狀態整份重寫交接
- **THEN** manifest 一起替換、狀態恢復 current，不追加歷史或保存原文副本

### Requirement: Evidence explains local verification scope differences

證據診斷 SHALL 比對已保存與目前驗證範圍，指出需求、情境、依據、測試、方法、執行設定及宣告檔案差異，沿用 why 與 roadmap details；SHALL 不改變效力判定或執行任何驗證。

#### Scenario: Relevant contract changes
- **WHEN** 必要情境或測試對應等驗證範圍改變
- **THEN** 原因包含相關 ref/id 與改變類別，證據需重驗證

#### Scenario: Irrelevant presentation changes
- **WHEN** 只變更標題或無關需求
- **THEN** 局部證據效力不變

#### Scenario: Old evidence
- **WHEN** 舊證據沒有可比較範圍內容
- **THEN** 保留一般補驗證原因，不虛構差異
