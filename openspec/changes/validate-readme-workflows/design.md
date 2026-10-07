## Context
支援 Windows 與 Linux。Windows controller 經 WSL 操作要標明是 Linux runtime 驗收，不代稱原生 Linux controller。只使用合成資料。

## Decisions
- 全新參與者只拿 README、其連結的操作指南、安裝產物與合成任務，不提供評分事實或先前對話。
- 每平台執行新建、升級與過時交接三案；新建軟體的測試由獨立測試角色撰寫及簽收。
- 紀錄器呼叫實際已安裝 console script，保存參數、退出碼與輸出；來源碼入口不能代替安裝驗收。
- 預存事實、內容指紋與評分資料放案外。查詢次數從紀錄計算，無法取得的 shell 歷史明示缺漏。
- 獨立審查核對產物與改動；本輪只修有證據的工具／README 流程缺陷。

## Validation
執行兩平台完整回歸、釘版 PDF／proof、乾淨及升級 wheel 安裝、hook 實際攔截與六次 agent 實測。網路／環境失敗不算通過，離線資產記錄來源。唯讀查詢不改紀錄或完成判定。

## 後續 README 裁定

2026/10/01 負責人要求首頁更精簡，且不要出現 docspec。README 改為短版入口，完整流程移至 `docs/user-guide.md`，保留實際安裝套件與資料路徑，避免虛構 `pip install artispec`。依 GitHub 官方 README 說明，首頁呈現用途、開始方式、文件入口與維護者，較長的操作細節另查。這是後續文件整理；原六案使用的 README 及 wheel 證據不改寫，也不據此宣稱新首頁已通過全新 agent 實測。

## 實測後的修復

已重現並修復 `put` 外部引用判定、material-first 檢查例外及直接 Read payload 誤擋；各由測試角色先建立正反案例。新建文件實際 proof 又發現內建 Typst 的行內 code 樣式把 Pandoc 的換行 delimiter 及高亮 token 包成小框，合併程式行並改變縮排。新增三個實際 PDF 座標回歸案例後，將高亮 code 區塊的 token 呈現限定於區塊內，保留換行、空白行與縮排；更新自家來源模板的完整性基準，不改既有封存快照、fidelity 門檻或完成判定。

另發現同 provider 的實作者與獨立測試者都使用 `gpt` 會被當成同一 agent。可沿用現有字串欄位擴充 actor 標籤，但涉及本輪限定不變的身分／完成流程，先提出方案待負責人確認，未實作。不冒稱其他 provider 或 owner 簽收。
