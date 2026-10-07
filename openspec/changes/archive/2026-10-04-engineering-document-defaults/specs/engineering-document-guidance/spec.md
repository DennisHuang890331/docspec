## Purpose

讓工程團隊使用的文件規範依任務、文類及交付讀者組織內容，提供能操作且可核對的說明，同時保留既有專案風格、來源與定版權限，避免通用論述規則壓過文件用途。

## ADDED Requirements

### Requirement: 用途決定文件組織
生成指引 SHALL 依既有 kind 與讀者組織內容，保留有用的範圍、前置條件、步驟、結果及限制；MUST NOT 強制所有文類成為論述鏈或固定章節表單。

#### Scenario: 操作手冊與參考文件
- **WHEN** 文件為 how-to 或 reference
- **THEN** 指引按任務順序或查詢需求寫作，不強制前節結論成為後節前提。

#### Scenario: 交付讀者不同
- **WHEN** 工程團隊交付教師操作手冊
- **THEN** 指引採教師任務與既有 brief，不把開發驗收流水帳插入操作正文。

### Requirement: 刷新保留既有規範與完成條件
初始化 SHALL 保留自訂 writing-guide，既有來源、brief 繼承與定版要求不變；必要軟體證據缺漏 MUST NOT 被風格更新當作完成。

#### Scenario: 舊專案刷新
- **WHEN** 舊專案更新生成規範與 skills
- **THEN** 使用者 writing-guide bytes 不變，變更的內建規範提高版本。

#### Scenario: 各域完成條件仍獨立
- **WHEN** 軟體缺必要證據而文件符合自身定版條件並獲授權
- **THEN** 軟體不能封存，文件可以定版；文件風格不新增跨域完成閘門。
