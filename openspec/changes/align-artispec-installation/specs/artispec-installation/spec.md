## Purpose

讓 ArtiSpec 的安裝套件、執行指令與使用者工具位置一致，提供舊安裝的明確安全升級方式，保留既有專案與驗收歷史，使 Windows 與 Linux 使用者可以核對實際安裝來源及工具狀態。

## ADDED Requirements

### Requirement: 安裝與執行名稱一致
新 distribution SHALL 名為 artispec，唯一 console script SHALL 為 artispec。Python dspx、專案 docspec/、corpus、DOCSPEC_* 與歷史管理標記 MUST 保留。

#### Scenario: 安裝新 wheel
- **WHEN** 在乾淨環境安裝本輪 wheel
- **THEN** metadata 與 wheel 使用 artispec 名稱、artispec 指令可執行，沒有 docspec console script。

#### Scenario: 升級舊 uv tool
- **WHEN** 用新 wheel 取代舊 docspec tool 安裝
- **THEN** 新 tool 位於 artispec 安裝環境，其他 tool 與既有專案資料不變。

### Requirement: 明確遷移受控工具
新工具根 SHALL 使用 artispec 名稱。setup --migrate-data SHALL 為明確、離線的獨立遷移模式，保留舊來源，核對受控資產內容並更新 lock 的已知來源內路徑；MUST NOT 操作專案紀錄或未知舊根項目。

#### Scenario: 舊資產與目的額外資料
- **WHEN** 舊根有受控工具與字型，目的根另有 installers
- **THEN** 資產內容一致、已知 lock 路徑指向新根，舊來源及目的 installers 保留，明示未遷移未知項目。

#### Scenario: 重複執行
- **WHEN** 目的已有相同內容
- **THEN** 再次遷移不重寫既有檔案；來源不存在時明確回報，不下載或宣稱已搬移。

### Requirement: 遷移失敗保留原資料
遷移 SHALL 預檢全部衝突、重疊路徑、損壞 lock 與不受控連結，核對複製期間來源是否改變。失敗 MUST 保留來源及原目的檔案，MUST NOT 覆寫衝突或留下已知不完整的發布。

#### Scenario: 內容衝突或損壞來源
- **WHEN** 目的同路徑內容不同、來源 lock 損壞、外部連結或複製失敗
- **THEN** 明確報錯，保留原資料，不以失敗或部分遷移宣稱升級完成。

### Requirement: 查詢與來源識別
version、doctor 與來源查詢 SHALL 使用新安裝 metadata 並維持唯讀；dev 更新檢查 SHALL 查 dev 而非 main。既有工具若需遷移，診斷 SHALL 指出明確遷移命令。

#### Scenario: 未遷移的舊工具
- **WHEN** 使用者查詢新版而只有舊工具目錄
- **THEN** 提供實際診斷與遷移提示，不自動寫檔或替使用者完成遷移。

### Requirement: 驗證與開發發布如實標示
dev 發布 SHALL 保留本輪與既有未完成驗收的真實狀態；安裝成功、文件定版或 strict 通過 MUST NOT 替代軟體必要證據或兩域完整流程完成條件。

#### Scenario: 推送開發成果
- **WHEN** 完成本輪核對後提交並推 dev
- **THEN** 保留兩案未完成接受／封存、需求變更與接手的註記，不動 main、不開 PR。
