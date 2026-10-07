# 實測缺口第一批修正與驗證

日期：2026/10/02。對應 OpenSpec change：`fix-workflow-review-gaps`。

負責人授權：「可以交給你修改並紀錄好具體修正了啥」。範圍、取代關係與限制已記入 [設計裁定](../system-design.md)。只用隔離合成資料；指定分支開發，不提交、推送或開 PR，保留原有未提交成果。

## 1. 具體變更

- **工作完成與背景依據**：`engine/roadmap_v2.py` 將 D／I 排除於交付成果，但保留來源效力、原引用、有效替代者與查詢入口。只有背景引用的工作需有理由手動結案，不會因有一條決策就完成。相關失聯依據與取代循環餵入共用來源診斷，列表與 show 都不能宣稱完成；正常多階替代與無關失聯來源不誤擋。必要證據、Q／RL 待處理及 SR7 已完成工作只標記待審的順序不變。
- **文件查詢上下文**：新增 `engine/document_context.py`，供 get、instructions、find、check、diff 共用。預設讀正式來源；明確 `--change <id>` 只讀該 change 的來源聯集，包含相關父節、群組、共用依據及設定。輸出 context／source／diagnostics；get 的原始 YAML stdout 保留，提示寫 stderr。缺失、過時或仍含已刪章節的 preview 明確診斷，不改查正式舊文。官方與草稿封條損壞會報錯，不自動修復；讀取不寫 ledger 或產生 preview。
- **來源讀取窄口**：store、glossary、model 及 check 的窄口接受已驗證的記憶體上下文；change 的既有 OverlayLayout 對所選 glossary/config 使用相同來源，讓正常 render 能消除對應診斷。沒有改 render、封存、指紋或各領域完成算法。
- **摘要版本與重複全文**：`engine/work_summary.py` 與 roadmap CLI 預設 v2；`--schema-version 1` 保留原結構。簽收者及時間等 metadata 保留，已保存的 scenario scope 只輸出版本與指紋，另附真實 tests.yaml 路徑及 change show 入口。相同 `(version, fingerprint)` 去重並保留每個來源；同需求不同歷史範圍不合併。有效決策全文、原引用、原因、動作與診斷不截斷；舊缺範圍不捏造指紋。原簽收與證據檔案不改寫。
- **損壞指紋的邊界修補**：已保存的範圍版本或指紋若是 mapping／list，原 v1 能回報需要重看，v2 曾在索引時崩潰。新增最小型別防護，保留原簽收狀態、原因與動作，但不建立無效 scope-source／索引；不重新計算或補寫指紋。
- **skills 與生成規範**：develop 2.5、apply 2.5、factcheck 2.3、release 3.4、verify 1.5、implement 1.6；生成區塊版本 2。明定同一 change id 的查寫、歷史快照與 latest 公開投影、版本對應的驗收、技術交接來源及 notes 理由／治理原話分工。更新指南與 CHANGELOG；舊專案的刷新提示沿用現有機制，區塊外使用者內容與既有標記保留。

## 2. 驗證方式與結果

獨立測試角色先建立正反案例、保存真實 RED，再由實作者修程式；新案例只由測試角色維護。同檔單一負責人，實作者未改新測試求綠燈。原案例的錯誤 fixture 假設另列校正，不以變更 v1 API 或移除必要斷言解決。

- Roadmap 初版 18 案：10 failed／8 passed；來源一致性另 9 案：6 failed／3 passed。補齊失聯背景負例後共 29 案，新案及 47 個相關回歸共 76 passed。
- 文件上下文初版 32 案：27 failed／5 passed；實作後 32 passed，測試角色另外補來源、刪除、新篇及封條邊界。
- 摘要 v2 初版 13 案：11 failed／2 passed；包含唯讀、v1 相容、歷史指紋、全文保留、有效及失敗原因與來源入口。原 v1 活動簽收沒有 signed 全文；全文去重案例改用真正引擎驗證並封存的紀錄，沒有擴張原 API。

文件最後共 57 案，摘要共 16 案，roadmap 共 29 案，合計 102 個新行為案例。整批 98 案先通過，後續搜尋定位與損壞指紋分別先保存 RED 再修復；損壞指紋三案實際 3 failed，修復後獨立摘要全 16 passed。既有測試只將已核定的 get 正式預設及摘要預設版本更新，沒有放寬損壞資料、必要證據或唯讀斷言。

第一次完整回歸 Windows 1969 passed／4 failed／1 skipped，Linux 1966 passed／4 failed／4 skipped。四個失敗為 check 錯誤前綴的三個相容案例與 develop skill 的一個措辭案例；修正前綴與原話保存措辭，既有斷言未改。原失敗、來源指紋及中間 wheel 保留，沒有用後續成功覆蓋。

最終結果：

- **Windows 11／Python 3.12.13**：1976 passed／1 skipped，599.24 秒；退出碼 0。略過的是既有散檔 group.yaml 壞檔警告路徑，store 模型已有對應硬閘。
- **實際 WSL Ubuntu-24.04 Linux／Python 3.12.3**：1973 passed／4 skipped，706.52 秒；退出碼 0。三個是必須在實際 Windows 執行的 NT directory junction 案，另一個與 Windows 相同。
- **PDF／proof／程式區塊版面座標**：兩平台各 86 passed／0 skipped，從最終完整回歸 XML 核對，使用既有受控釘版工具與字型；未放寬測試或另下載未核對資產。
- **最終 wheel**：SHA256 `0a70fa504adde47265e0695429a58d817e40991744eb3f6e3273dc84c721957a`，173 個套件檔逐位元與目前來源一致，唯一 console script 是 artispec。兩個隔離環境的 dspx 均從 site-packages 載入；移除 PYTHONPATH，在 repo 外複製測試後兩平台各 102 passed。
- **獨立 review**：摘要／簽收 21 個相關案例通過，另以真正封存的合成資料逐筆透過 scope-source 回讀完整原簽章。刪除目前測試來源後仍可追查，不重開歷史工作；查詢禁止外部執行／刷新／交接寫入，逐位元未改。
- **開發 change 與交付檢查**：最終 OpenSpec `validate --all --strict --no-interactive` 為 15 passed／0 failed；`git diff --check` 退出碼 0。分支仍是 `claude/software-domain-redesign`、HEAD 仍為 `5a942b6`，未提交、推送或開 PR；只有既有換行提示，沒有 whitespace error。
- **來源穩定**：最終兩平台完整執行前後及完成核對時的來源指紋一致；最後分開 Python bytecode cache，避免跨 OS 共用 cache 讓 traceback 的檔名誤導平台。原未提交成果、兩份 README、原考場資料及歷史交接未改寫。

skills 結構檢查補充：通用 skill-creator quick validator 直接檢查六份檔案，均因既有 `compatibility` 欄位不在它的允許清單而拒絕；沒有為通過而刪掉產品安裝說明。案外暫存副本只排除此欄位後六份皆通過，產品自己的 init／skills／規範更新回歸與下節實際生成技能操作另行通過。這是通用檢查器格式落差，不能稱原檔直接通過該檢查器。

## 3. 全新 agent 前向查核

本輪另建兩份合成文件案例，每平台一名無前文接手者；只提供任務、安裝後 CLI、AGENTS 與生成的 factcheck 2.3，答案、預檢與指紋置於案外。Windows 使用 fork none 子 agent；Linux 因 controller 的 agent thread 數限制，改以已登入的 Codex CLI 開新 thread，不 resume，不帶開發前文。兩案都使用實際已安裝 artispec。Linux 仍是 Windows controller 透過 WSL 執行，不是原生 Linux agent。

預先建立一份已同步但故意寫錯數值的草稿，以及同 change 中另一份來源已變、預覽尚過時的文件。兩名接手者都以指定 change 查核，正確定位草稿 9 名與有效來源 6 名的矛盾；各只新增一筆合法 audit finding。對過時預覽明示查核未完成，未因 check 結構通過而宣稱正文乾淨，也未自行 render、刷新或修稿。

獨立核對受管理內容與實際記錄：兩案唯一變動都是 visitor-guide 的新 audit.yaml，沒有改 corpus 內容、staging、docs、ledger、治理來源或生成規範，查詢與審查本身沒有寫入。Windows 機械核對 13／13 通過；Linux 12／13，唯一未過是完整路徑 substring，接手者以 change 容器加 preview 短路徑定位。獨立語意核對能唯一還原正確來源並確認實際命中位置，判兩案達標；保留原機械 false、原回答及說明，沒有重寫答案或改評分器求通過。

實際 recorder 計數：Windows 28 次 CLI（27 查詢含 5 help、1 次 audit 寫入），3 次 CLI 非零；Linux 24 次（23 查詢含 2 help、1 次 audit 寫入），4 次 CLI 非零。兩案預覽過時的非零是預期診斷；猜測 audit list／get docs 類別與錯讀原始 audit 路徑是 agent 表現，依 help／audit show 更正，不列本輪工具缺陷。

Windows 首次 recorder 的外層 cp950 stdout 無法輸出符號而失敗，底層 CLI 與日誌已正確 UTF-8；接手者以 PYTHONUTF8 重查，未改案或錄製器。此項歸驗收環境，失敗保留。Windows collaboration 沒有可匯出的完整 shell 歷史，因此只能獨立核對已錄的 28 次與檔案指紋，不能宣稱已完全排除未錄 CLI；Linux 有完整新 thread JSONL 工具事件，26 次 shell 呼叫（24 recorder、2 唯讀 cat），5 次 shell 非零，未觀察到直接 CLI。

這是本批 CLI／skill 前向操作驗證，不代稱考場應用重跑、原六案重新通過、完整 agent 行為保證或固定用量降低。

原始執行紀錄保存在 repo 外受控 Temp；來源基準及指紋位於 `artispec-workflow-followup-20261002-140722`。報告不收真實專案資料或完整 agent 對話。

## 4. 未修改與限制

尚未封存需求的文件引用（F2）仍需另一份設計提案。本輪不新增 stores、紀錄種類、並行寫入、自動語意判斷或完成算法。README 回來再改的待辦保留。

原考場實測的軟體、手冊、歷史證據、最終交接與當時缺陷紀錄均不回填。修正的回歸與本輪隔離接手結果另記；不因程式修好就改寫原實測為無缺陷通過。notes／治理分工的規範已更新，CLI 封存提醒的整合仍待下一批；平台 GUI 與操作限制的更完整指引、驗收控制器可靠性與取包範圍仍保留 roadmap 待辦。
