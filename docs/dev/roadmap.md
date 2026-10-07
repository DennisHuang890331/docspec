# 開發 roadmap

此檔記錄本 repo 的後續開發待辦；OpenSpec change 的實作與驗收明細仍由各自的 tasks.md 管理。

最新核定（2026/10/07）：開發分支已由 `claude/software-domain-redesign` 改為 `dev`，安裝套件與使用者工具資料改為 `artispec`；先驗證新 wheel，再安全升級工具／字型、整理成果提交並推送遠端 `dev`。此授權取代舊安裝名稱與不提交／不推送限制；不動 main、不開 PR。專案 `docspec/`、`corpus`、`dspx`、環境變數及 markers 保留，工具資料僅在明確 `setup --migrate-data` 時離線複製，來源作備份、目的衝突拒絕。README 只修安裝／升級資訊，內容與呈現仍待負責人重整；自用開發切換尚未進行。見[最新裁定](system-design.md#開發分支安裝套件與工具資料升級20261007)及[升級指南](../user-guide.md#upgrade-an-existing-project)。

本次由 `align-artispec-installation` 管理，實際回歸及安裝升級證據另見[本批報告](validation/installation-upgrade-run.md)。

本批最終回歸（2026/10/07）：Windows **2135 passed／1 skipped**、實際 WSL Linux **2132 passed／4 skipped**，各 2136 項、0 failed／0 error，原退出碼及 XML 已核；276 個 src／tests／pyproject／lock 檔前後 bytes 相同。四個已安裝 wheel 乾淨／升級情境合計 50 命令、88 項核對、696 次套件檔案比對通過；Windows 23,620／Linux 20,751 個受管工具檔已明確遷移、原來源保留。全域 uv tool 已升級為 `artispec v0.1.0` 唯一入口，實際全域 doctor／deep 中文一頁實編與 16 個套件的 pip check 均 exit0；舊工具資料與 2026/10/06 wheel 備份保留。共用新 wheel 已更新，成果已本機提交為 `a919a9e`；遠端 `dev` 推送因 GitHub 尚未登入而待完成。這些機械與安裝結果不補足同題兩案的接受／封存、變更與接手驗收。

前輪驗證（2026/10/04）：核心修正及機械回歸已完成，Windows 2096 passed／1 skipped、實際 WSL Linux 2093 passed／4 skipped，OpenSpec strict 23 passed。Windows 實測已輸出兩房 HTML 與兩份原生列印 PDF；Linux 新版手冊 1.0.1 與 ZIP 已完成，原包 GUI 已獨立核過，新包不直接沿用該結果。Linux 新版獨立核對通過，Windows 紙面審查亦通過；Windows 錯誤連結的合法恢復待裁定，最新同題兩案尚未初版接受／封存、需求變更或新會話接手。此次升級不修 unlink、不補造完整 workflow passed；驗證完成但尚未 archive 的 change 保留原狀態。明細見[本輪紀錄](validation/workflow-alignment-run.md)。

## 待回來討論

- [ ] **roadmap 錯誤連結的合法恢復**（2026/10/04，同題驗證新缺口）
  - agent 將裸裁定編號誤加入工作；工具接受非法格式，又沒有移除入口，補正確連結仍會阻擋文件定版。隔離的新 wheel 專案已真實重現。
  - [最小修法](proposals/roadmap-link-recovery.md)：add／link 寫入前檢查格式，新增明確 unlink，只更正指定連結、保留其餘資料及原失敗，不放寬完成判定。待裁定；原實測不手改封條。

- [ ] **測試檔外的共用來源追蹤**（2026/10/04，新觀察）
  - Windows 同題實測修正 conftest 後，19 筆簽收仍 current；現行指紋涵蓋同檔內容，該任務亦未宣告外檔 fixture。沒有證明假完成：排座仍保留失敗證據，先前 CSV 證據不使用修改的 fixture。
  - [具體提案](proposals/explicit-test-sources.md) 採測試作者明確宣告共用來源，簽收與證據共用指紋，不猜依賴或新增紀錄種類。尚待裁定；不擴入本輪已核定範圍，也不在實驗中更換 wheel。

- [ ] **來源狀態與查詢範圍的呈現**（2026/10/04，非阻擋觀察）
  - 明確引用 `gov:W`／`gov:M` 時，治理來源列讀原紀錄的 status；兩類紀錄不保存 status，因此可能顯示 unknown，而現有 roadmap 查詢可取得完整推導狀態。是否讓來源列共用該判定，留待討論，沒有改完成算法。
  - 現有 `roadmap --milestone` 的 items／統計只包含相關工作，但 JSON children 索引仍有無關工作的空 key。獨立安裝核對保留原過度字串 assertion 的失敗，改按實際來源紀錄核對；索引整理屬後續呈現建議，不把此結果當成完成判定失敗。
  - 原觀察及既有入口的[驗證紀錄](validation/summary-source-commands-run.md) 保留，這輪先修無法執行的提示。

- [ ] **用 ArtiSpec 管理自己的開發**（2026/10/04）
  - 負責人提出後續採用本工具開發本工具；[切換提案](proposals/self-host-development.md) 建議下一輪小修正試行、固定管理 wheel 與獨立候選環境。
  - 本輪 OpenSpec changes 不中途切換；正式切換、最小能力基線與試行工作尚待討論，不雙寫兩套進度。

- [ ] **縮小版考場座位完整流程驗收**（2026/10/01）
  - 已核定題目；先準備兩平台案例，再驗初版、一次變更及一次全新會話接手。
  - 現況（2026/10/02）：兩案初版與一次容量變更均完成獨立測試、引擎證據、實際 Windows GUI、Explorer 雙擊、指定 EXE 對外連線隔離、合成負責人接受與軟體封存；兩份手冊各有 1.0.0、1.1.0、三頁 PDF／proof。無前文接手盤點與最終交接均已獨立核對，交接新鮮度為 current，測試與歷史資料未被改寫。inline delta 修正完整回歸：Windows 1874 passed／1 skipped、實際 WSL Linux 1871 passed／4 skipped；OpenSpec strict 14 passed。原輪發現 F1／F2／F3 等缺口，不能宣稱整體無缺陷通過；後續第一批已修 F1／F3，另記[修正與驗證](validation/workflow-review-gaps-run.md)，不回填原輪結果。原來源見[身分修正報告](validation/agent-instance-identity-run.md)與[正式案例結果](validation/exam-seating-workflow-run.md#11-第二次交付與最終核對20261002)。
  - 明細：[validate-exam-seating-workflow](../../openspec/changes/validate-exam-seating-workflow/tasks.md)。原輪先完成測試與缺陷紀錄，第一批修正已另獲授權；其餘修正須另提案，不回填前輪六案未通過項目。
  - 2026/10/04 最新授權：除 README 外按 OpenSpec 完成本輪修正、同題比較，完成後才遷移自用開發。[重跑方案](proposals/repeat-exam-workflow.md) 維持題目、CSV、讀者、一次變更與接手時機，分平台另建新案。四項修正已實作，驗證器追加競寫保護後 Windows 完整回歸 2087 passed／1 skipped、實際 WSL Linux 2084 passed／4 skipped；最終 wheel 安裝與查詢通過。兩案訪談、提案、獨立測試及方法核對完成。Windows 作者已停止：19 筆簽收有效、63 個案例通過，988 個包檔與 ZIP 一致；錯誤工作引用仍阻擋定版，2328 檔完整 checkpoint 保留，等待合法恢復方案裁定。Linux 已產生初版 ZIP、手冊定版與四頁 PDF／proof，native checkpoint 134 檔指紋一致，實際 Windows GUI 仍待驗收。兩案未完成初版接受／封存、唯一變更或新會話接手；沒有把 ready 或階段退出成功算成交付通過，見[本輪修正紀錄](validation/workflow-alignment-run.md)。

- [x] **以工程團隊為預設的文件風格**（2026/10/03）
  - 負責人明確指出工具預設給工程團隊使用，要求參考 LabelVault 文件風格，現有排座操作說明不適合作為預設標準。
  - 已唯讀對照指定專案的 README／部署手冊、合成排座 latest、writing-guide 模板、schema 與 develop／verify 指引；只整理抽象風格，不收真實專案內容或資產。
  - [具體提案](proposals/engineering-document-style.md)：按任務與文件用途組織，直接交代前置條件、實際操作、預期結果及故障處理；分清使用工具的工程團隊與交付文件讀者，不強制每節寫成論述，也不把驗收流水帳與裁定來源反覆插入操作正文。既有 kind／brief／writing-guide 可承載，不新增必填表單或完成閘門。
  - 2026/10/04 已按最新授權實作 writing-guide、schema、develop 2.6／apply 2.6／factcheck 2.4 及生成規範 4。獨立反例確認保留穩定錨點導航、既有自訂指南與 brief；軟體問題不誤擋文件寫作。完整回歸、新 wheel 已通過；工程 how-to／reference 兩個全新案例及兩份同題教師手冊均完成獨立內容審查。五項任務核對後，change 已[正式封存](../../openspec/changes/archive/2026-10-04-engineering-document-defaults/verification.md)，兩條需求同步為正式 spec。Windows 手冊仍未定版，兩域完整流程另待驗證；既有實測文件與 README 不改寫。

- [ ] **繼續修改中英文 README**（2026/10/01）
  - 負責人原話：「幫我加gemini 再來我要討論其他事情先在roadmap上面紀錄REAME還要回來在修改」。
  - 現況：中英文版本已建立，致謝已補 Gemini；負責人仍要回來討論及修改 README，尚未定稿。
  - 範圍：[英文 README](../../README.md)、[繁體中文 README](../../README.zh-TW.md)。
  - 下次動作：接續負責人的 README 意見，先釐清要調整的內容與呈現方式，再同步修改兩版；目前先討論其他事情。
  - 相關開發 change：[validate-readme-workflows](../../openspec/changes/validate-readme-workflows/tasks.md)。既有六案驗收限制保持原紀錄，此待辦不代表已通過。

## 實測發現：已完成的修正與待討論項目

原裁定是先記錄、後續才修改；2026/10/02 已明確授權第一批，以 `fix-workflow-review-gaps` 處理。2026/10/03 要求繼續修正，封存提醒與既有交付指引由 `align-delivery-guidance` 處理。原實測來源與分類見[正式案例報告](validation/exam-seating-workflow-run.md#9-缺陷與改善建議待後續處理)，新修正與驗證另見[第一批報告](validation/workflow-review-gaps-run.md)及[後續提醒／交付報告](validation/delivery-guidance-run.md)。下列未涵蓋部分仍須另提案，不回填原實測結果。

- [x] **資訊引用的工作完成判定與原因缺漏**：第一批已修 D／I 同作背景依據，不算待交付成果；只有背景的工作不自動完成。保留原引用、效力及審閱提醒，相關失聯／取代循環由列表與 show 共用診斷。29 新案、相關回歸、兩平台完整回歸及安裝包驗證通過，明細見修正報告。
- [ ] **文件引用尚未封存的新需求**：2026/10/04 已按明確授權實作 [F2 提案](proposals/draft-requirement-links.md) 的 `draft-req:<change>/<capability>/R<n>`，共用來源解析供章節、查核、追溯與工作摘要使用。封存後仍保留原引用，解析已封條 baseline 的正式來源；缺失、損壞或 base 衝突不猜同編號需求。獨立 35 案、完整回歸與兩平台新安裝通過；同題流程驗收進行中，不提早封存軟體。
- [x] **交付後手冊與當前證據的核對提示**：verify 1.6、生成規範 3 與指南已補交付時核對 latest 的待驗／可用敘述與當前證據。確有差異時明確修正，依負責人要求另定新版；保留歷史，不新增跨域完成閘門。此項完成的是指引，不回填原實測手冊或宣稱重跑完整交付。
- [x] **跨平台 GUI 與不可寫目錄的驗收指引**：verify 1.6 與規範已要求按記錄的平台、啟動方式、權限及實際完成交付包核對，明示未覆蓋與環境失敗；headless 或另一 OS 的測試不能冒充未操作的 GUI 示範。沒有將 NTFS 等特定例子變成全專案新必測條件；原必要證據與接受保留。
- [ ] **實測控制器的可靠性**：已集中 UTF-8 命令、原退出碼、session／phase、Codex 真實事件去重、受控來源定位及條件等待；新的 participant runner 核對 resume UUID、真實成功事件、timeout 與自己的子程序清理。兩平台獨立案例通過；真實 GUI 等待及全流程紀錄仍待本輪重跑核對。原 cp950、resume、來源誤判與 shell history 缺漏保留；控制器問題不混成產品缺陷或 agent 表現。
  - 2026/10/04：來源查詢提示的追加修正已結案，最新完整回歸 Windows 2096 passed／1 skipped、實際 WSL Linux 2093 passed／4 skipped；兩個實測安裝仍沿用原 wheel。案外合成控制器能力與實際案例分開：Windows 真 EXE 已雙擊、匯入 16 人、安排 R1、輸出兩房 HTML，並經原生列印存出兩份一頁橫式 PDF；首個 R1 reader 誤判保留，另只讀字形復核通過，R2 真續接 exit0。Linux 原包已在 Windows 私有 Chrome154 完成匯入、排座、下載 HTML 與兩頁橫式 PDF，獨立審查通過；新版手冊與包已完成，原作者停止，新包 GUI 仍未核。root 親閱紙面；獨立後續核對已完成；預設關聯、正式交付與完整接手仍待完成，不提前建立產品完成證據。
- [x] **離線與安裝限制的訪談表述**：propose 1.6、verify 1.6、規範及指南已分清操作者安裝、主機依賴與程序／整機網路限制；按已有裁定引用，缺漏影響設計才問，不自行加強或降低。沒有相應環境仍列未驗證，不算通過。
- [x] **工作摘要 JSON 的重複歷史內容**：原實測 Windows W1 是 37,639 UTF-8 bytes／1,003 行，含十組封存簽收 contract。第一批已修預設 v2 與明確 v1 相容模式；保留有效決策、簽署 metadata、原因與不同歷史指紋，相同指紋去重並列原紀錄入口，不截字數、不宣稱固定節省比例。含損壞指紋的 16 個獨立新案、兩平台完整回歸及安裝包驗證通過；原歷史不改寫。
- [x] **公開測試交接檔的現況重複**：第一批已在 implement skill 與生成規範明定技術交接保存介面、重現方式及來源入口，易變進度、簽收與驗證現況由 CLI 取得，不自動改寫舊交接檔。生成與更新回歸、兩平台最終驗證已通過；本輪全新 agent 另驗文件 factcheck 指引，沒有代稱考場或 implement 完整行為重跑。
- [x] **文件 change 封存提醒與治理來源的整合**：後續 CLI 提醒已提供可選理由與原 ruling／info／decision 查詢，明示非阻擋，不再聲稱裁定空白或封存必然成功。機械觸發、完成／漂移條件及 notes／治理 bytes 保留；獨立七案、兩平台相關回歸與安裝驗證通過，不新增語意判斷或表單。
- [x] **guide 的治理指引仍有舊規則**（2026/10/03）：已實際重現後，按既有裁定以 `fix-guide-governance-contract` 修正 schema 的兩段指引。四個獨立新案加原七個封存案例 RED／GREEN，兩平台相關回歸各 111 passed，新 wheel 的八次已安裝 CLI 各通過；三種 guide 同源、原話及查詢前後指紋不變。只補治理分工，不改完成算法或實作新風格，見[本次驗證](validation/guide-governance-run.md)。
- [x] **文件 preview 的查核上下文**：第一批五指令共用正式預設與明確 `--change`、同一唯讀來源與 preview 診斷。查核不以正式舊文代替草稿，find 每筆命中也指向實際來源。57 個獨立案例、兩平台完整回歸、安裝包與全新 agent 前向查核已通過，明細及驗收限制見修正報告。
- [x] **check 的通過範圍可以說得更清楚**：2026/10/04 已按授權新增同源 `coverage` 文字／JSON，區分結構、實際引用掃描、過時／缺失／未評估正文、軟體，以及未做的語意審查與交付驗收。維持原 `ok`、errors、software_errors、退出碼及非阻擋提醒。獨立案例、完整回歸與兩平台新 wheel 查詢通過；factcheck 亦改為看實際來源與診斷，不能從 check green 推論所有引用有效。同題完整流程另記，不相加成此項機械驗證。
- [ ] **驗收指紋範圍與取包時機**：已實作完整 manifest 與停止作者後的 checkpoint 核對，區分不可變歷史、追加 history、測試作者來源與公開投影；來源、預期、副本、取樣後須一致，新失敗副本不取代舊包。獨立正反案例已通過，實際交付包仍待重跑驗收。原還原公開舊 PDF／proof、過早取 980 檔的失敗保留，不因機械測試通過而結案。
