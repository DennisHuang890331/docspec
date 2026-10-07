# 縮小版考場座位流程驗證（2026/10/01–02）

本輪兩個完整案例已實際跑完：初版、一次容量變更、獨立測試、新會話接手、第二次交付及最終交接。兩版軟體均取得合成負責人接受並正式封存，手冊各有 1.0.0、1.1.0、PDF 與 proof；Windows GUI／Explorer 均實際操作。**仍有未修的工具／流程缺口，不判整體無缺陷通過**。最新結果見第十一節，第一至十節保留各階段 checkpoint，不回填舊實測。身分修正與其當時回歸見[驗證報告](agent-instance-identity-run.md)。

修正前 checkpoint：完成題目與兩平台案例準備，尚未執行整套 agent 流程；當時 provider 身分判定會阻擋不同 Codex 會話的獨立測試簽收。負責人後續已核定並修正，原大型考場座位實測及先前六案結果不改寫。

## 1. 已核定的題目與驗收

兩班各八位合成學生，兩間教室各 4×4 個座位。僅 CSV 匯入、排座位、輸出座位表；以班級加座號識別，全部恰好排一次、不能超容量、同班不能前後左右相鄰，斜角除外。未要求隨機、均分或強制使用每間教室，評分不能擅自追加。

一份短操作手冊說明輸入、操作、規則與限制，含一張與實際輸出一致的座位表示意圖；合成文件已授權依工具流程定版、PDF、proof。訪談保留 Windows、離線、雙擊、不能要求老師安裝開發工具的交付限制。開發者可安裝工具；Linux 結果不能替代 Windows 使用者操作驗證。

初版完整交付驗收後，只追加一次「教室容量與剩餘座位」，剩餘為容量減去已安排人數。變更未完成時由無前文的新會話接手，先查來源與沿用工作，再重寫交接，最後第二次交付。兩平台都須核對測試角色、簽收、引擎證據、封存及文件輸出，不能把查詢或文件完成當作軟體完成。

## 2. 案例準備與機械驗證

實作：[build_exam_workflow_cases.py](../../../scripts/validation/build_exam_workflow_cases.py)；測試由另一個開發 agent 先建立 [test_exam_workflow_contract.py](../../../tests/test_exam_workflow_contract.py)，實作者只修改產生器。這是開發時的分工，不是產品測試角色的簽收。

修前先收集 13 項，3 failed／10 setup errors，原因均為產生器尚不存在。實作後通過 14 項，獨立檢查補上控制器不可臨時創造負責人需求的說明。實際準備再抓到 Linux venv Python symlink 被 resolve 成系統 Python，以及 Windows 合成文字 CRLF／Linux LF 差異；修正後補原始 bytes 與真實 symlink 正例。另提供 README 引用的公開指南唯讀副本，避免接手者拿不到完整操作說明。

最終契約測試涵蓋 CSV 身分與可解性、題目不含答案、案外資料隔離、一次變更／接手、兩平台契約 hash、原始 UTF-8 bytes、保留 venv interpreter 路徑、重跑不覆寫舊 run、無產品或外部程序啟動、實際 CLI 路徑、無偽裝身分與公開指南的原 bytes／hash。

- Windows：測試角色執行 `pytest tests/test_exam_workflow_contract.py -q`，**17 passed，0 skipped**，2.64 秒。
- 實際 WSL Ubuntu-24.04 Linux runtime：相同測試檔，**17 passed，0 skipped**，3.52 秒；JUnit 位於 `/home/dennis/.cache/docspec-workflow-validation/exam-fixture-contract-final.xml`。
- `openspec validate --all --strict`：**12 passed，0 failed**；含本 change。

契約測試只啟動產生器，不執行產品 init、測試簽收、軟體驗證或文件輸出。原本完整回歸及 PDF／proof 結果仍以既有版本儲存報告為準，本次沒有假稱重跑它們。

## 3. 案外資料與證據位置

本次最新準備案例：

- Windows：`C:/Users/zxc22/AppData/Local/Temp/artispec-exam-workflow-windows/run-20261001-073023-586142-bce9c1ad/`。
- Linux：`/home/dennis/.cache/docspec-workflow-validation/exam-workflow-cases/run-20261001-073030-555613-fa87ef73/`。

先前準備 run 完整保留；較早 run 是換行／Python 路徑修正前的準備樣本，不用於正式接手。最新兩案使用相同 wheel SHA256 `0ffc4781204319f64a3ded648759034df082f8d5edd358da6859fd60c441ea27`，contract SHA256 `7b6266b52ffa7184082b1d24a238c9f7025f59b8ad4be2d5b6a2b8644d0dcedf`；README、TASK、CSV 及公開指南的 raw bytes hashes 相同。

`project/` 只有中英文 README、TASK.md、students.csv，未初始化。案外保存 persona、變更、接手說明、oracle、recorder config／程式、manifest 及公開指南副本。只將公開指南提供參與者，不提供整份案外資料。manifest 的 `participant_launches` 為空，`agent_workflow_executed: false`；尚無命令 log，不捏造查詢次數。後續須先保存啟動說明，再追加實際會話資訊及命令結果。

目前指向先前已驗的已安裝 wheel 入口，未建立本案例專用的新 runtime、未另驗案例依賴或終端交付。正式啟動前仍須確認測試／排版依賴及實際 CLI；現在的路徑、hash 不構成安裝或交付通過證據。Linux 是 Windows controller 透過 WSL 操作的實際 Linux runtime，不稱為原生 Linux agent。

## 4. 已確認的身分限制

環境：Codex 可用，Claude Code 已安裝但未登入，Gemini CLI 不在 PATH；負責人回答「目前只有 Codex」。本次沒有登入其他工具、修改認證或把 Codex 標成其他工具／user。

現行 [tasks.py](../../../src/dspx/engine/software/tasks.py) 的 `add_test` 以 `written-by: gpt` 記作者，`add_task` 以 `created-by: gpt` 記實作者；`sign_tests` 比對工具前綴。不同 Codex 會話均為 gpt，因此會拒絕獨立測試會話。`testplan set`、異議回應及 evidence 的同作者提醒也使用 provider，單改簽收就會造成判定不一致。

另檢查到 [code.py](../../../src/dspx/commands/code/code.py) 的 `testplan remove` 在作者檢查前即執行：未被任務引用的測試可由別人刪除，與測試作者管測試的規則不一致。這是待修的工具缺口，不是參與者故意跳步；本輪尚未改產品。

## 5. 身分修法原提案（後續已核定）

建議將「工具名稱」與「實際會話」分開，沿用現有檔案，另開 change 核定後實作：

- 工具仍是 claude／gpt／gemini／user，治理 ID、套件與資料目錄不改。
- 新的測試、任務與異議可附穩定會話欄位，例如 `written-by-instance`、`created-by-instance`、簽收的 `by-instance`、異議的 `by-instance`／`responded-by-instance`。比較工具與會話這一對值，同會話不因改角色名稱而取得簽收權。
- Codex 真實獨立會話可使用其 `CODEX_THREAD_ID`；已取得工具會話碼時，不允許以不同手填碼覆蓋，衝突須報錯。跨工具／未傳遞會話資訊時可由控制器透過 `DOCSPEC_ACTOR_ID` 傳入已保存的實際啟動識別碼。工具沒有可用碼時明示限制，不生成新碼讓每條命令變成不同作者。子 agent 若繼承同一 thread marker，不能據此認定獨立，須另啟動真正獨立會話。
- 測試修改、刪除、簽收、異議回應及同作者診斷共用身分 helper；簽收仍核對實際檔案、情境與測試指紋。實作者不能藉另一個任意標籤改同一測試；正常重啟應沿用原會話 ID，新作者承接另走明確授權，這批新建案例不需要自動轉移作者。
- 舊紀錄沒有會話碼時仍保留原 provider 判定。同 provider 且一方缺碼時不得推論為獨立；明示無法區分。封存紀錄、封條、舊證據不回填、不重新簽收、不自動授權。
- 不新增身份 store、不支援並行寫入；角色依序操作。會話碼是可追查的流程標記，不能防止人刻意偽造環境變數，不能宣稱是身分認證或安全隔離。

修法驗證須含：兩個真實 Codex 會話可分工；同會話改角色名稱仍拒絕；非作者不能修改／刪除／簽收；缺碼與舊紀錄保持保守；變更測試後簽收過時；文字與 JSON 判定一致；Windows／Linux 回歸與實際 wheel 重建。確認後才執行上述兩平台完整案例，不能直接放寬簽收條件補通過。

## 6. 正式案例執行 checkpoint

正式案例使用 release wheel，SHA256 `c5bc2a96ebc79b7b3a78b2d62e88d37b5c138afd7e46156921e234b86153f72c`。新 runtime 具有測試與排版依賴；先前 run 保留，不覆寫成通過。

- Windows：`C:/Users/zxc22/AppData/Local/Temp/artispec-exam-workflow-windows/run-20261001-090921-373328-875cd5ee/`。實作者 `01a0f6bb-25d7-7641-add9-64c13836784d`；獨立測試者 `01a0f6d1-0f40-7f33-b56f-d25b491d440a`。
- 實際 WSL Linux：`/home/dennis/.cache/docspec-workflow-validation/exam-workflow-cases/run-20261001-090921-533921-178a3113/`。實作者 `01a0f6bb-268f-7dc1-b99e-b734313ca7f3`；獨立測試者 `01a0f6d1-1955-7d33-847e-3beaaf240545`。參與者為 Windows Codex controller，產品與自動測試使用實際 Linux runtime。

訪談、提案、測試三階段各平台均 exit 0，保存於各 run 的 `participants/<phase>/`，含啟動命令、完整提示、JSONL、標準錯誤與答案。產品命令另由 recorder 保存真正已安裝入口、退出碼與輸出。phase 成功只表示參與者正常結束，不表示產品驗收通過。

兩案均先建立既有工作、需求與實作任務，再交獨立測試者：Windows T1–T10、Linux T1–T9 的簽收均有效，作者與實作者皆為 gpt，但實際會話不同。Windows 實際跑 17 個案例全部因未有 app 模組而失敗；Linux pytest 收集階段因未有 seating 模組而失敗。這些紅色基線不是完成證據。測試程式 bytes 在案外保存 `test-role-v1-snapshot.json`，供後續核對實作者未修改。

兩案皆選用 Tkinter、原生 Windows PyInstaller 資料夾包與自含 HTML；技術選擇來自 agent，沒有捏造成負責人裁定。原實作者已完成 implement-v1，各 exit 0，保留未驗收項目後整份重寫交接單。未注入變更，未啟動接手者。README 的後續討論工作保持未完成。

## 7. 初版收尾與獨立核對

身分問題已解決；以下是初版實測 checkpoint，**不判整套通過**。

- Windows 引擎 E-gpt-1／2／3 分別 12、2、3 個案例通過，合計 **17 passed、0 failed、0 skipped**。Linux 引擎 E-gpt-1／2 分別 18、3 個案例通過，合計 **21 passed、0 failed、0 skipped**。手動 pytest 與引擎證據分開保存。
- 實際 installed CLI 的唯讀簽收查詢仍為 Windows 10 current、Linux 9 current，與真實測試會話相符。Windows O1／O2 仍 open：控制器測試不能單獨證明 GUI 接線，待原測試作者評估；異議沒有改動測試或簽收。
- 原始 README、TASK、CSV 的 4 份內容與初始 manifest hash 一致；兩案共 8 個測試／輔助來源與測試角色快照一致。控制器另對保存的實際分配核對 16 位身分與姓名、恰好一次、座標唯一、兩室界限與所有正交鄰接，均符合事實清單。不是以實作自己的 validator 做審查。
- 兩份手冊各已定版 **1.0.0**，有同版 source snapshot、凍結圖片、3 頁 PDF 與 3 頁 proof；凍結圖片與當時來源 bytes 相同。獨立審查逐頁檢視，未見文字或完整兩室圖的明顯裁切，兩案 W-gpt-2 由既有判定顯示完成。
- Windows 軟體 change `exam-seating`、Linux 軟體 change `offline-exam-seating` 仍 active；沒有 acceptance、waiver 或成功 archive。兩案 archive dry-run 都拒絕。Windows W-gpt-1 的 GUI demonstration E-gpt-4 為 fail，Linux Windows 示範尚未執行。文件定版沒有被軟體問題擋住，軟體也沒有被文件完成冒充驗收。

兩份案例的 `controller-checkpoint.json` 與 `controller-query-commands.jsonl` 位於案外，控制器查詢與參與者呼叫分開。參與者 `commands.jsonl` 的 Windows 207 筆含 **204 筆已安裝產品呼叫、3 筆直接 pytest**；Linux 154 筆含 **152 筆已安裝產品呼叫、2 筆直接 pytest**。產品呼叫皆為 manifest 指定入口，沒有來源碼入口代替安裝。非零退出 Windows 10 筆、Linux 8 筆，包含紅色基線、無效引用／參數及拒絕封存，不能一律算產品缺陷。

按實際命令分類：Windows／Linux 分別 handover 查詢 3／5 次、roadmap 列表 4／3 次、工作摘要 6／7 次、CLI 來源查詢 7／5 次、測試列表／缺口 3／1 次、help 各 21 次、instructions／guide／狀態診斷各 24 次。這只計 recorder 保存的 CLI 分類；直接讀檔在 Codex JSONL 保存，未完整獨立分類成來源跳轉，也沒有完整 shell history。不用自報數字補缺漏，不與前次實測聲稱嚴格效率對照。

缺口分類：

- **環境未驗證**：兩案原生 Windows 包只在有 Python、網路可用的建置主機普通啟動；沒有真正離線、無 Python 乾淨主機及 Explorer 雙擊證據。Linux 自動測試仍是 Windows controller 操作實際 WSL runtime，不代替 Windows 交付示範。
- **agent 表現／案例測試限制**：Windows 滑鼠鍵盤操作未產生輸出，當時原因未確定，不能直接判成 ArtiSpec 工具錯誤。T9／T10 對 GUI 的語意覆蓋異議仍待原作者；未為消除失敗改測試或豁免需求。
- **既有工具限制**：尚未落地的新軟體需求不能直接作文件 `req:` 引用，兩案先沿用有效治理來源，記錄封存後補連結；沒有為補追溯提前封存。是否支援 change 中的引用留待另案評估，不擅自新增語意或完成算法。Linux freeze 的未有 managed review record 是提醒，沒有把案外獨立審查混稱受管理查核紀錄。

初版交付未完成，因此依核定順序保留一次變更、無前文接手與第二次交付未執行，不提前注入事件補驗收。後續須先取得實際 Windows 交付操作與當前成果的接受，才能繼續；本報告保留所有成功、失敗與未驗證項目。

## 8. 續測：兩條線交錯推進與初版實際交付

使用者確認續測後，沿用第六節兩案與原 A／B 真實會話，不另做一份冒充完整流程的案例。文件與軟體在同一專案交錯推進，共用治理／roadmap；受管理資料仍由單一寫入者依序操作。軟體尚未接受時文件可先定版，文件完成也不會讓軟體通過封存。

### 8.1 真實 Windows 操作與離線隔離

兩案均實際操作 Windows portable 的 CSV 選擇、排座、輸出、錯誤 CSV，以及另一份合法 C／D 名單的重新輸出；檢查沒有混入原名單。實際 HTML 的初次輸出 hash 與案內原輸出一致，獨立審查逐格核對兩室 32 席、16 個原身分恰好一次及全部正交鄰接。

Explorer 驗證使用自行開啟的專屬視窗，先由 Shell 確認精確 EXE 路徑，再實際雙擊唯一檔案控制項，核對新程序映像及 Tk 主視窗。沒有把 shell 啟動當成 Explorer 雙擊，也沒有擷取個人桌面或關閉使用者視窗。兩案普通啟動與隔離下雙擊均通過；修復後 Linux 案另外驗證新包。

離線測試採 Windows 原生動態 WFP session，對專屬交付包 EXE 的 APP_ID 設 IPv4／IPv6 outbound BLOCK；前後實際 API 讀回確認，session 結束會自動刪除測試 filters。正反探針先成功、封鎖後回 10013、未封鎖程序仍成功，移除或結束獨立 session 後恢復成功。未修改持久 Firewall、NIC 或執行政策。實作範圍依 [Microsoft 動態 session 說明](https://learn.microsoft.com/en-us/windows/win32/api/fwpmtypes/ns-fwpmtypes-fwpm_session0)及 [ALE filtering layers](https://learn.microsoft.com/en-us/windows/win32/fwp/management-filtering-layer-identifiers-)；原始探針及 API 紀錄在案外 `artispec-offline-probe/wfp/`。

這是指定 EXE 的對外連線隔離，**不是整台主機實體斷網、子程序隔離或乾淨無 Python 主機測試**。交付包與來源全檔 hash 一致；Python／Tcl／Tk 從交付包載入，但主機另注入 ASUS 中文輸入法 DLL，不宣稱所有 DLL 都只來自交付包或 Windows。原訪談要求老師不需安裝開發工具，agent 自行寫成主機不能已有 Python 的較強情境已明確澄清，原歷史不刪除。

### 8.2 成功、失敗與修正分開列

- **ArtiSpec 工具缺陷**：修改自己新增的情境繞過一般 delta 驗證，`--reason` 被封進情境，後續 validator 報未知欄位；相同捷徑可能覆寫編號。獨立測試角色先跑 50 案得到 28 failed／22 passed；修正寫入前欄位校驗及只更新可編輯欄位後，71 案通過。沿用既有 schema：修改不接受移除原因，不新增原因欄位、不自動清理舊封條。以 `fix-inline-delta-validation` 管理。
- **控制器問題**：早期 GUI 檔案對話框及焦點操作不可靠，不能直接判成程式錯誤；另有一次 PowerShell pipeline 將澄清中文變問號、一次錯誤 resume UUID、一次 mechanical harness 未把正常缺任務狀態列為預期結果。全部保留實際失敗與後續修正，不冒充產品缺陷或 agent 幻覺。問號治理來源保留，追加清楚來源；Linux 的明確取代關係亦保存。
- **合成軟體實作錯誤**：Linux 案原生 Windows 包在真正 NTFS 拒寫目錄上超過 120 秒無回應。原 B 確認 Python `NamedTemporaryFile` 在 Windows 的可寫探測造成大量拒寫重試，改為排他建立、只對檔名碰撞有限重試；原 A 的三份測試未改。實際 Linux 引擎重跑 18＋3 案通過，Windows 重新打包後，實際 GUI 顯示拒寫錯誤並能恢復可寫輸出。原包與 E-gpt-4 fail 保留。這是案例軟體的交付修復，不是 ArtiSpec 完成判定變更。

### 8.3 當前正式結果及來源

- Windows：E-user-1／2 為實際 GUI／離線雙擊示範；缺接受時 archive dry-run 仍拒絕。當前成果由合成負責人依實際審查接受為 E-user-3／4／5 後，正式封存至 `_archive/2026-10-01-exam-seating`，W-gpt-1 顯示 done。
- 實際 WSL Linux：修復後引擎 E-gpt-5／6 與 inspection E-gpt-7 保留；E-user-1 為真實修正版 Windows 示範。缺接受時 dry-run 拒絕，E-user-2／3 當前接受後正式封存至 `_archive/2026-10-01-offline-exam-seating`。軟體已封存，W-gpt-1 仍因背景資訊 refs 被當成未開始項而顯示 in-progress、沒有原因；此規則缺口另向負責人提案，不強制改成完成。
- 手冊：兩案仍為 1.0.0，各有三頁 PDF／proof、不可變 source／diagram snapshot。逐頁已審查、圖與初版輸出一致，但凍結時正文尚寫軟體待驗；這是當時版本，不能把它說成已同步後續接受。交接在封存後為 stale，後續變更與接手須辨識並更新 latest／產生新版，保留 1.0.0。
- 獨立審查：原測試來源 Windows 五份／Linux 三份及案例初始四檔 hash 全部保持；正式 archive、舊治理、失敗證據及凍結資料列在案外 `independent-review-v1.json`，供第二次交付逐檔核對。控制器負責實際操作及合成負責人當前接受，參與者沒有冒用 user 身分。

新隔離 runtime 安裝修正 wheel，SHA256 `59f0ec1ef4c1fa9c3783e0d698724e66b7b8ae79c5fd9cee99c114bc8f32be53`；172 個套件檔案與來源 bytes 一致、僅 artispec 入口。原 wheel／runtime 保留，以 `recorder-config-delta-guard.json` 明確切換，沒有悄悄覆寫參與者安裝。獨立五檔回歸兩平台各 158 passed；新 wheel 模組實測兩平台各 71 passed，另各六次真正 console script 呼叫驗證非法寫入拒絕且原 bytes 不變、合法修改可繼續；未建任務的草稿如實顯示缺任務。

此修正最終完整回歸：Windows **1874 passed、1 skipped**（492.87 秒）；實際 WSL Linux **1871 passed、4 skipped**（565.71 秒）。略過為既有退役路徑與 Linux 三個 Windows-only junction，沒有為 PDF／proof 放寬條件。OpenSpec strict validation **14 passed、0 failed**。完整回歸、實際案例及控制器測試分開計算，不相加成完整流程案例數。

兩案第一版正式封存後，才將已核定的一次容量／剩餘座位變更交給原 B，要求只準備需求、任務與交接。獨立新測試、紅色證據、沒有前文的 C 接手、第二次交付與最終查詢次數仍待執行，不能提前勾選完整流程驗收。

## 9. 缺陷與改善建議：待後續處理

依負責人「先紀錄缺陷後面在修改」的指示，以下是觀察與提案，不表示產品已修正或新設計已核定。兩平台案例繼續執行；仍須保留未完成與失敗狀態。

- **F1，工具缺陷／規則待裁定：資訊引用被當成完成項，且沒有原因。** 實際 WSL 案 `offline-exam-seating` 已正式封存、任務有當前證據與接受，但 W-gpt-1 仍為 in-progress、details 空。來源為工作既有 gov:I 引用；roadmap 的引用判定尚未涵蓋資訊種類，與背景決策的處理不一致。影響是交付後的工作狀態可能誤導接手者。建議資訊同決策作背景依據，仍診斷缺失、損壞與影響標記；是否改完成規則待負責人裁定。案例引用保持，沒有改成 done 或刪來源規避。
- **F2，現有能力限制：尚未封存需求的文件追溯。** 兩案的新 req: 只能在軟體需求落地後引用，先沿用治理來源。改善方向是界定 change 中需求的明確引用、落地後解析與變更失效規則；不得先封存未完成軟體來取得引用。這涉及設計，不在本輪加入。
- **O1，流程改善：交付時核對手冊正文的待驗敘述。** 1.0.0 定版時軟體尚待實際操作，後續接受不會也不應改寫凍結版本。第二次交付須將 latest 的舊敘述與新容量需求一起修正，另定新版。建議規範提示對照正文、當前證據與交付狀態；不是讓軟體狀態擋文件定版。
- **O2，驗收改善：標明測試方法與平台覆蓋。** headless GUI 控制器測試不能單獨證明視窗接線；實際 Linux 自動測試也未抓到 Windows NTFS 拒寫目錄的長時間重試。原案例已分別要求 demonstration、inspection、當前接受，這些 gate 正常拒絕不是缺陷。建議更清楚呈現各方法尚待證明的範圍，並使用實際交付包核對，不減少必要證據。
- **C1，控制器問題：編碼、會話與 GUI 操作可靠性。** 本輪確有中文變問號、錯誤 resume UUID、錯誤焦點／控制項及 callback 等待問題。應集中 UTF-8 保存、校驗真實會話碼、以精確控制項與原視窗消失判斷對話框結束，另核對預期退出碼。這屬實測基礎設施，與 ArtiSpec 核心及 agent 表現分開。
- **O3，訪談與環境說明：避免自行加強驗收條件。** 「老師不需安裝」不等於「主機不能已有 Python」；指定程序 WFP 隔離不等於整台主機斷網。報告須分別說明已有實證與未驗證部分。agent 的過度解讀、控制器無相應環境和工具缺陷不能混列。
- **O4，摘要可讀性：歷史簽收重複完整治理內容。** 獨立唯讀審查核實 Windows W1 的一次 roadmap JSON 為 37,639 UTF-8 bytes／1,003 行，含十組封存 signoff contract；同一 D-gpt-1／D-gpt-2 原文分別出現七／五次，實際 JSON paths 保存在案外評審。建議評估以來源入口追查完整歷史、摘要保留有效決策內容及必要原因，維持文字／JSON 一致與相容性；不硬截必要事實、不承諾固定用量降低。本輪不改 schema。
- **O5，流程改善：公開技術交接檔的易變狀態。** Linux `second-delivery-test-handoff.md` 在 A 完成後仍寫尚無測試計畫；新 C 以受管理簽收及 E-gpt-8 正確識別它已過時。建議技術檔保留介面、設計與來源入口，簽收及進度由即時計算的 CLI 取得，減少另一份會過時的文字狀態。這是規範改善提案，不是來源判定錯誤或此次 C 漏讀。
- **O6，提醒整合：文件 change 的 notes 與治理裁定。** 兩份文件 change 的 seed／realizes 已引用有效治理依據，封存仍提醒 notes.md 未另記人類裁定，要求 agent 補記。治理層原話已有保存，不能因此補造新裁定或把 warning 當封存失敗。建議後續釐清 notes 的變更理由與治理權威來源，提醒優先提供來源查詢，不要求重複抄錄原話；不新增必填表單或語意完整性推論。

- **F3，工具／skill 上下文缺口：預覽稿查核投影正式舊稿。** Linux 真實獨立 reviewer 的 `reviewer-report.md` 說明：依 skill 使用 instructions、find、check、diff 時，輸出是正式 1.0.0，數字查詢亦未找到新稿內容，不能證明 preview 已查核。審查者改以當前 preview、staging／治理來源及實際圖逐項核對，沒有冒稱舊稿查詢是新稿通過。現行這四個指令沒有明確的 `--change` 上下文選項，與 `get`／render 的 staging 操作不一致。建議另案評估統一明確選擇與標示查核對象，預設維持正式資料、不靠 active change 猜內容、不增加 store；本輪先記錄，不改 CLI 或 skills。

另列 **A1，agent／控制器提示解讀問題**：Windows C 為保存初版投影，於工具匯出 1.1.0 已保存並清理舊公開 PDF 後，把舊 `docs/exports/seating-manual_v1.0.0.pdf` 與 legacy proof 還原，並另建帶版號的 docs 備份。這與 docs 只留 latest 的方向不一致。不可變歷史應核對 `_versions/1.0.0/`，案外驗收備份與可重建的公開投影另分；不得把 C 的過度保存解讀說成工具未保存歷史。初版 canonical snapshot／exports／proof 的 bytes 另由獨立審查核對，本輪暫記觀察，不修改產品儲存規則。

另列 **C2，控制器時機問題**：第二版 EXE 建置完成時先複製 980 檔隔離包，但 Windows 作者最後加入四個交付檔案後，正式包成 984 檔。Explorer verifier 正確拒絕完整集合不一致，尚未操作桌面，原 980 個檔案及 EXE bytes 均不變。保留第一份 manifest／拒絕紀錄；待作者停手後，核對新增 CSV、HTML、PDF 與本次原始來源，再另記 final 全包指紋及隔離副本。這是控制器太早取包，不是產品封存或軟體功能錯誤；後續應以 final 包完成為取樣 checkpoint。

已修復的同 provider 會話判定及 inline delta 寫入問題另見身分報告及第八節；它們完成於本次「後續再修」指示前。合成軟體的 NTFS 重試問題由原實作者修復，原失敗證據保留；不把它列為 ArtiSpec 產品缺陷。其餘觀察待第二次交付與獨立審查後補入，README 討論待辦維持未完成。

## 10. 一次變更與新會話接手 checkpoint

兩案第一版實際驗收後才注入相同的一次容量／剩餘座位事件，各保存 `feature-event-injected.json`；沒有第二次需求事件。原 B 只準備新軟體 delta、實作任務、文件 change、沿用原工作並整份交接，沒有先寫程式或測試。Linux 原準備階段被使用者意外中斷；確認沒有殘留寫入者後，以同一 B 真實 UUID 在 `resume-capacity-preparation` 接續，原未完成 phase 紀錄保留。

- Windows：軟體 `room-seat-summary`，新增 R7 並修改 R4/S1；文件 `room-seat-summary-manual`。原 A 新增 `tests/test_room_summary.py`，四項新測試簽收 4/4 current，連既有任務1。引擎 E-gpt-7 為 **0 passed、7 failed、0 skipped**，舊輸出缺兩室摘要。原五份測試 hash 不變，六份當前測試來源保存於案外 `test-role-v2-snapshot.json`。
- 實際 WSL Linux：軟體 `add-room-seat-counts` 修改 R3，文件 `explain-room-seat-counts`。原 A 新增 `app/tests/test_room_counts.py`，七項簽收 7/7 current，連既有任務1；引擎 E-gpt-8 為 **3 passed、4 failed、0 skipped**，新摘要缺失、原輸出回歸仍通過。原三份測試／清單 hash 不變，四份當前來源另存快照。

新 C 使用沒有 resume thread 的真正新啟動，未收到前文或答案；提示只有公開接手任務、實際安裝入口及中性盤點要求。先查現況與來源，再重寫交接；第一階段不實作、不改測試／文件、不驗證或接受。Windows C 的真實 UUID 為 `01a0f7fb-6014-74b2-8ac8-0b7aceb1040d`，已指出追加裁定不取代原限制、四項簽收有效、七個案例失敗、初版接受不能沿用、手冊仍 1.0.0 且有舊待驗敘述，並分辨缺字原話與清楚的有效來源。Linux C 的盤點正在執行，尚未判通過。

Windows C 已接續第二階段實作，必須保留測試與歷史版本、新包另放新目錄；當前 Windows GUI、Explorer／隔離驗證及負責人接受由控制器實際執行後才准封存。第二次交付、版本原 bytes 核對、獨立盤點評分與最終命令統計仍待完成，不能把 phase exit 0 當成完整流程通過。

Windows 首次盤點已經獨立審查通過：24 個實際 command cells 中 23 個唯讀、1 個交接寫入；17 個已安裝產品呼叫中 16 個唯讀（含 help）、1 個交接寫入，沒有 file_change event。交接 manifest 中 65 個受管理檔案與盤點前快照一致，兩案各 23 個初版封存／證據／凍結輸出亦保持 bytes。這是接手盤點的驗收，不是第二次交付通過。

## 11. 第二次交付與最終核對（2026/10/02）

本節接續前述 checkpoint；實際執行兩個完整案例，不與前輪六案或機械測試相加。兩案文件與軟體在同一專案交錯進行，共用既有治理與工作項；同案的受管理寫入仍依序執行，不宣稱產品支援多人並行寫入。

### 11.1 無前文接手及當前驗證

兩個 C 的首次盤點均由獨立審查判定通過。Linux C 指出 RL-gpt-10 取代 RL-gpt-9、容量裁定是追加而非解除原限制、七項簽收有效、E-gpt-8 為 3 passed／4 failed、初版接受不可沿用，以及公開技術交接檔的「尚無測試計畫」已過時。Windows C 的盤點事實見第十節。兩案都沿用原工作，先盤點再整份交接。

Linux 首次盤點有 14 個 command cells：11 次唯讀、1 次交接寫入、交接輸入暫存檔建立與刪除各一次；16 次 installed CLI 中 15 次唯讀（含 help）、1 次交接寫入。其 65 檔 manifest 所用基準是在 A 新測試之前保存，62 檔相同，另三檔為 A 授權新增的任務測試連結、簽收及紅色證據；不冒稱全部是在 C 前後同時取樣全等。

第二階段實作結果：

- Windows：新測試由原 A 撰寫並簽收，C 未改其 bytes。引擎由 E-gpt-7 的 0 passed／7 failed，轉為 E-gpt-8 的 **7 passed、0 failed、0 skipped**，另有當前 inspection 與後續驗證；原功能直接回歸 17 passed，完整案例 pytest 24 passed。新包位於 `dist/room-seat-summary-v2/ExamSeating/`。
- 實際 WSL Linux：原 A 的七項測試保持，C 只改 HTML 摘要實作。引擎由 E-gpt-8 的 3 passed／4 failed，轉為 E-gpt-9 的 **7 passed、0 failed、0 skipped**，並有 E-gpt-10 inspection；原功能直接回歸 21 passed。新原生 Windows 包位於 `artifacts/windows-1.1.0/dist/ExamSeating/`，Linux 測試不能代稱該包已實際操作。

Linux C 曾因模型服務容量限制中斷，保存 `complete-capacity-delivery` 的 exit 1，再用相同 C UUID 於 `resume-capacity-delivery` 接續成功；不重新注入事件、不覆寫已凍結的版本。這是服務／環境失敗。一次 evidence add 因 shell 引號缺 conclusion 被拒絕，改正後才記 E-gpt-10；這是 agent 呼叫問題，不是 ArtiSpec 證據判定失效。

### 11.2 新版 Windows 包實際操作及接受

兩案第二版均在 Windows 實際匯入原 CSV、排座與匯出；錯誤 CSV 不得輸出，重新匯入 C／D 合法名單後只含新名單。獨立審查對實際 HTML 核對兩室 32 席、16 個身分恰好一次、零正交同班鄰接；每室容量 16，剩餘數按該室實際占座計算，可見文字與資料屬性一致。Linux 案另實際選 NTFS 拒寫目錄，錯誤提示後可恢復可寫輸出，自己的測試 ACE 已清除。

兩個 Explorer 驗證均實際雙擊精確 EXE，確認新程序映像與 Tk 視窗；前後 API 均核對指定 EXE 的 IPv4／IPv6 WFP BLOCK。當前 EXE SHA-256：

- Windows：`1777d0d1a66b1ec472ec70a581bd3359292ed6cb0b765d4b72d1961b7028810b`。
- Linux 案的原生 Windows 包：`f3a0bea56544349bae596bc1e7898e82548d2afd87952578b8cebc248ee140fc`。

成功操作與核對收據位於各案 `project/artifacts/controller-v2-acceptance/`，包含 SUMMARY、GUI 與 Explorer 原始結果。控制器按既定合成角色記錄當前 inspection／接受；內容明示是模擬負責人確認，**不是使用者的真實發布許可**。參與者沒有改成 user 代簽，也沒有沿用初版接受。

- Windows：缺本版接受時 dry-run 拒絕 R4／R7；E-user-6 inspection 與 E-user-7／8 接受後 dry-run 成功，實際封存至 `_archive/2026-10-01-room-seat-summary`。
- 實際 WSL Linux：缺本版接受時 dry-run 拒絕 R3；E-user-4 inspection 與 E-user-5 接受後 dry-run 成功，實際封存至 `_archive/2026-10-02-add-room-seat-counts`。

每案 `v2-acceptance-operations.json` 與 `controller-write-commands.jsonl` 保存控制器實際 args、退出碼與輸出。它們不混入只記參與者的 `commands.jsonl`；封存狀態亦由獨立已安裝 CLI 讀回確認。

控制器失敗同樣保留：Windows 在作者未結束包裝前先取 980 檔，正式包後來新增四份交付檔；原 980 檔與 EXE bytes 不變。先前 GUI 是同一程式的真實操作，補齊四份非程式附檔後才做 final 984 檔全包核對與 Explorer 驗證，不說首次 GUI 已測完整最終附檔。Linux 首次第二版 GUI 因其他視窗遮擋而未點進程式，不能算功能失敗；改以自己的視窗與精確控制項重試，僅擷取自己的 HWND，實際操作通過。初次失敗桌面截圖未納入 repo 或公開收據，未關閉或移動使用者的其他視窗。

### 11.3 文件、測試角色與歷史完整性

兩份手冊均定版 **1.1.0**，各有同版 snapshot、實際兩室座位及容量／剩餘圖、三頁 PDF 與三頁 proof。獨立審查逐頁檢視，圖文一致且可讀；兩案文件 change 均封存。正文凍結於本版 Windows 當前接受之前，仍記當時待驗狀態，後續接受不改寫它；交付狀態以當前證據與最終交接說明，不冒稱手冊已在接受後重新定版。

兩個 C 都實際另開沒有前文的文稿審查會話，原始 Codex session metadata 已核對；不是把 C 自審當獨立 review。Linux reviewer 指出的 preview 上下文缺口列為 F3，改讀當前 staging／preview 後完成審查，不用正式舊稿查詢冒充新稿查核。

原 A 的測試來源在第二次交付後仍保持：Windows 六份、Linux 四份與各自 v2 快照全等；案例初始 README／TASK／CSV 四檔保持。兩案 canonical 1.0.0 snapshot／圖片／PDF／proof 與舊軟體封存、舊失敗證據均保持 bytes。兩案文章總 history 正常追加 1.1.0，一列追加不等於歷史版本被覆寫；各自移除該新列可復算冷接手時的原 bytes 雜湊。

兩份 ZIP 由獨立審查逐 entry 比對原始來源並驗 CRC：Windows 984 檔，Linux 983 檔（含 bundle 外交付附檔），均通過。Windows agent 曾還原舊 docs 公開投影的 A1 仍未修正，不能因此宣稱 docs 只留 latest 的預期在這個案例完全符合。

### 11.4 環境清理與未通過項目

最後保存 14 個測試 filters 的 API 讀回後，關閉動態 WFP session，FwpmEngineClose0 回 0。另一個 query engine 確認全部測試 filter IDs 及專用 sublayer 已不存在；holder／watcher 與其 wrappers 自然退出。僅刪除指定的合成測試 profile，HRESULT 0；副本、manifest、失敗與模組來源紀錄均保留。原始紀錄位於案外 `artispec-offline-probe/private/cleanup-report.json` 與 `artispec-offline-probe/artifacts/wfp-cleanup-proof-20261002-000425.json`。

完整 runtime 取樣的 Python／Tcl／Tk 來自包內，但檔案對話框另有主機 IME、ink 與雲端 shell extensions；未追讀真實使用者資料，也不宣稱零外部 DLL。仍未驗證乾淨無 Python 主機、整台主機實體斷網或子程序連線隔離。Linux 仍是 Windows Codex controller 操作實際 WSL Ubuntu-24.04 runtime。

F1／F2／F3 及 O1–O6 維持第九節的待討論狀態，A1 與控制器問題另列。兩域產物與第二次封存有實證，不能把它們等同所有流程缺口已修或前輪六案已通過；README 討論待辦不勾選。

### 11.5 最終交接與實際命令計數

兩案均沿用首次無前文接手的 C 真實會話，於 `final-current-handover` 先讀過時原因、當前工作／change／證據與公開操作收據，再整份重寫交接。兩個 phase 均 exit 0；獨立審查以已安裝 CLI 確認 `freshness.status: current`，當前 manifest 的 Windows 78 檔／Linux 75 檔逐一符合實際 bytes。

- Windows：最終階段 22 個 shell command cells，21 次唯讀與一次交接寫入；15 次 installed CLI，14 次唯讀（含一次 help）與一次寫入。兩個工作顯示完成，但交接保留公開舊 proof／PDF、preview 查核限制及手冊的接受前歷史文字。
- 實際 WSL Linux：最終階段 22 個 shell command cells，19 次唯讀（含一次 helper 錯誤後改正）、一次交接寫入、輸入暫存檔建立／刪除各一次；14 次 installed CLI，13 次唯讀與一次寫入。交接指出當前軟體已接受封存，W-gpt-1 仍因 F1 顯示進行中，不強制完成。

審查前保存的 Windows 114 檔／Linux 102 檔來源在最終階段後全部不變；只改受管理的 handover，未再跑測試、寫證據／接受、修改工作引用、凍結版本或重新封存。實作者與原測試角色來源仍分開。

截至兩案最終階段結束，獨立從原始 `commands.jsonl` 重算：

- Windows：**477 筆**，包含 **472 次 installed product calls** 與五次 pytest 程序呼叫（其中一次 `--version`），29 次非零退出。原身分修正 runtime 271 次、delta guard 新 runtime 201 次；兩個安裝產物與切換紀錄均保存。
- Linux：**416 筆**，包含 **412 次 installed product calls**、兩次 pytest 與兩次案例輸出生成程序；生成程序一次因 Python 引號錯誤失敗、一次成功。共 19 次非零退出。原 runtime 172 次、新 runtime 240 次。

兩案 recorded `source_entrypoint_true` 均為零；產品呼叫實際走已安裝入口，其他程序另列，不能把 `source_entrypoint: false` 當成所有紀錄都是產品驗收。非零退出含紅色基線、合理拒絕及錯誤參數，不能按總數判產品缺陷。

按保存的 CLI args 固定分類，Windows／Linux 分別為：handover 查詢 11／19、roadmap 列表 13／12、工作摘要 22／24、change 列表 6／6、change show 19／23、治理／規格／證據原文查詢 59／21、測試／證據列表與缺口查詢 17／15、help 54／51、guide／instructions／內容及狀態診斷 63／56、版本查詢 3／4。其餘命令不擅自全部算成寫入或唯讀。

控制器自己的 `controller-write-commands.jsonl` 分別另有 19／13 次產品呼叫，內容包含 dry-run 與讀回，不因檔名而全算寫入；`controller-query-commands.jsonl` 各有一次早期唯讀簽收查詢。獨立審查自己的 CLI 亦另記在審查 checkpoint，不混入參與者總數。

計數與原 JSONL SHA-256 位於案外 `artispec-exam-controller/final-recorded-call-counts.json`，獨立審查再次重算一致。直接讀檔的來源跳轉可由各 phase 的 Codex JSONL 追查，但沒有完整 shell history，也未將所有跳轉獨立完整分類；不用 agent 自報補數，不宣稱與前輪實測是嚴格對照或達到固定用量降低。

收尾再執行 `openspec validate --all --strict`，**14 passed、0 failed**；檢查上述五份紀錄的相對連結與空白問題均正常。修正 wheel 的 172 個套件檔與目前來源逐檔相同，沒有在缺陷記錄階段補改產品。這些是收尾檢查，不說成又跑了一次完整回歸；第八節的 Windows 1874／Linux 1871 是此次來源版本已執行的完整回歸。紀錄維持指定分支與 HEAD `5a942b6`，未提交、推送或開 PR。

### 11.6 最終獨立報告與案外證據索引

獨立審查已鎖定最終 `independent-review-final.md` 與 `independent-review-final.json`，位於 `C:/Users/zxc22/AppData/Local/Temp/artispec-exam-controller/`。判定為兩案完整實測已執行、兩次合成交付與 current 交接完成；未判整體無缺陷通過，OpenSpec 2.4 保留未勾選。這與「沒有做完整流程」不同，也不取代負責人後續對修法的裁定。

控制器目錄另保存：

- `independent-review-*-v2-gui.json`：實際輸出身分、席位、鄰接、容量與剩餘數的獨立核對。
- `independent-review-*-v2-document.md/json`：六頁 proof 與兩份當版圖的逐頁審查。
- `independent-review-v2-packages.json`：ZIP 原 entry／CRC 與來源 bytes 核對。
- `independent-review-v2-reviewer-sessions.json`：獨立文稿及圖作者的真實會話 metadata。
- `independent-review-v2-archive-journals.json`、`independent-review-v2-cleanup.json`：接受前拒絕、實際接受／封存與環境清理。
- `final-recorded-call-counts.json`、`final-source-and-doc-check.json`：原紀錄總數／雜湊及收尾檢查。

審查者能完整列出的第二版唯讀 CLI checkpoint 共 49 次，Windows 24／Linux 25，包含截斷後的重查；這只計保存的 checkpoint，不是假稱完整審查 shell history，亦不混入 472／412 次參與者呼叫。原始案例、oracle、提示與失敗紀錄留案外；repo 只保存合成實測摘要、缺陷與待討論提案。
