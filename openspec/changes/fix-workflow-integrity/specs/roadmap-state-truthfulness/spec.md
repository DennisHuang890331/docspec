## Purpose

讓 roadmap 以可查證的狀態呈現進度，區分工作內容已完成與正式交付，並使負責人直接從文字輸出看出卡住原因、驗證失敗及尚未定版的內容。

## ADDED Requirements

### Requirement: Linked work cannot be manually completed

對具有完成條件連結或子項目的工作，系統 SHALL 依其連結及子項目推導狀態。手動結案 SHALL 僅適用於沒有可推導完成條件也沒有子項目的小工作；決策約束連結本身不是完成條件。

#### Scenario: Manual close of active software work
- **WHEN** 工作連到仍有未完成任務的 swc，使用者或 agent 執行 roadmap done
- **THEN** 指令拒絕並指向實際完成條件，工作不顯示完成

#### Scenario: Unlinked small work
- **WHEN** 工作沒有完成條件連結及子項目，操作者附理由執行 roadmap done
- **THEN** 工作可手動結案，保留理由

#### Scenario: Previously closed item gains linked work
- **WHEN** 原本手動結案的工作新增未完成的 change 連結或子項目
- **THEN** 目前狀態依新連結或子項目推導，舊手動結案紀錄不覆蓋它

### Requirement: Document completion reflects current frozen content

整份文件的交付工作 SHALL 只有在目前可交付內容已定版時才顯示完成；曾定版過舊內容不足以完成新交付。章節寫作工作 SHALL 可依章節內容是否已寫好推導，不把章節完成等同整份文件定版。軟體差異狀態 SHALL 按既有非阻擋規則呈現。

#### Scenario: Revised document after previous freeze
- **WHEN** 文件已有定版版本，新內容已寫好並同步，但未再次定版
- **THEN** 連到整份文件的工作顯示尚未完成，文字說明為已寫好但尚未定版

#### Scenario: Current content frozen
- **WHEN** 目前文件內容已定版，文件本身沒有其他阻擋條件
- **THEN** 該文件交付工作顯示完成；若只有 stale-software，顯示差異提醒而不使文件交付退回未完成

### Requirement: Text view exposes actionable reasons

roadmap 的文字與 JSON 檢視 SHALL 使用同一份狀態推導，文字輸出列出卡住原因、相關軟體任務的失敗或證據缺口，以及文件尚未定版等重要差異。父項目 SHALL 能反映未完成子項目的原因。

#### Scenario: Blocked by prerequisite
- **WHEN** 工作因前置工作未完成而卡住
- **THEN** 文字輸出直接列出前置工作及原因，不必改用 JSON 才能發現

#### Scenario: Active software with failed evidence
- **WHEN** 軟體 change 仍進行中且最新測試失敗
- **THEN** roadmap 在進行中狀態旁列出失敗摘要及取得細節的指令
