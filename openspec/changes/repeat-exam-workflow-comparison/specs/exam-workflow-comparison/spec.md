## Purpose

以相同合成任務在 Windows 與實際 Linux runtime 重跑完整文件及軟體交付，再驗一次變更與全新接手，核對工具修正的效果與限制；原結果保留，避免只用回歸或自報冒稱流程通過。

## ADDED Requirements

### Requirement: 同題雙平台與獨立角色
實測 MUST 保持兩班 16 人、兩間 4×4、CSV／排座／座位輸出、教師短手冊、一次容量變更及未完成時接手的契約；測試作者與實作者分離。

#### Scenario: 初版與第二次交付
- **WHEN** 兩平台執行流程
- **THEN** 各有實際安裝入口、獨立簽收、引擎有效證據、文件定版 PDF/proof 與軟體接受／封存，資料與評分放隔離案例外。

#### Scenario: 接手時工作未完成
- **WHEN** 初次交付後注入一次容量／剩餘座位變更
- **THEN** 無前文新會話先盤點有效決策、原引用、簽收、最新證據與未定版內容，沿用工作後寫新交接；缺必要證據不得先封存。

### Requirement: 比較有據且不回填歷史
報告 SHALL 獨立核對完成包、實際命令與文件可用性，分開工具、環境與 agent 問題；不得宣稱未執行平台、原六案或固定用量比例通過。

#### Scenario: 平台與 GUI 邊界
- **WHEN** Linux 由 Windows controller 經 WSL 執行
- **THEN** 明示 runtime，Windows GUI／Explorer 及指定 EXE 網路隔離依原契約實驗，不代稱 Linux 原生 controller 或整機實體斷網。

#### Scenario: 新舊比較
- **WHEN** 比較流程、文件、接手與查詢成本
- **THEN** 列原與新證據、模型與環境差異及紀錄缺漏，保留舊檔，不以單輪觀察宣稱因果。
