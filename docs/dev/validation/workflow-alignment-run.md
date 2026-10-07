# 現行文件規則、草稿需求與查核範圍驗證

日期：2026/10/04。本輪獲授權按 OpenSpec 修正除 README 外的流程，完成後重跑同題考場實驗，再處理自用開發遷移。**核心修改與機械回歸已完成，同題完整流程仍未通過。** 最新機械結果：Windows 2096 passed／1 skipped、實際 WSL Linux 2093 passed／4 skipped，OpenSpec strict 23 passed／0 failed；以下較早結果保留各次真實階段，不取代此最新結果。

目前實測切面：Windows 已真雙擊 EXE、匯入 16 人、安排 R1、輸出兩房 HTML，並經原生列印存出兩份一頁橫式 PDF；root 已親閱，紙面原始紀錄及直接 PDF 讀取的獨立審查已通過，文件仍未定版。Linux 原包在 Windows 私有 Chrome 已完成真匯入、排座、HTML、兩頁橫式 PDF，並通過獨立審查；新版教師手冊 1.0.1 與 ZIP 已完成，停止點、包及歷史的獨立核對已通過。預設關聯啟動兩次停在控制器守衛，列未驗，不把原包 GUI 結果直接算到新包。兩案未接受／封存初版，尚未注入容量事件或全新會話接手。Windows 工作的格式錯誤連結仍使文件定版 NO-GO，最小合法恢復方案等待負責人裁定；不破壞封條繞過。README 未改，自用開發未遷移。

## 實際變更

- 工程文件預設按任務、讀者與既有 kind 組織，涵蓋操作、結果、限制與故障處理。既有 writing-guide、自訂內容與明確讀者優先；教師手冊不因工具給工程團隊使用而改成開發報告。保留穩定錨點導航與盲寫邊界，不要求每種文件都形成論述鏈。
- 文件可引用 `draft-req:<change>/<capability>/R<n>`。單一解析供正文來源、指紋、追溯與工作摘要使用；封存後保留原引用，按封條 baseline 與 rename 解析正式來源。缺失、損壞、重複或 base 衝突有診斷，不能猜同編號需求。這些列在 `software_errors`，不另加文件完成閘門。
- `check` 新增同源 coverage v1：結構、實際掃描的引用與錨點、正文是否可查、軟體問題，以及尚未做的語意審查與交付驗收。既有 `ok`、退出碼及各域完成判定不變；正式正文同步未評估時不宣稱 current。
- 驗收共用 UTF-8 命令紀錄、原退出碼、phase／session、真實 Codex 事件去重、受控來源定位與完整 manifest。新 runner 核對 resume、成功完成事件及 timeout 子程序清理；無法確認停止寫入者時不取 checkpoint。
- develop／apply 為 2.6、factcheck 為 2.4、生成規範為 4。雙 README 與舊案例結果不在本批改寫範圍。

以上分別由 `engineering-document-defaults`、`add-draft-requirement-links`、`explain-check-coverage`、`harden-workflow-validation` 管理；同題比較另由 `repeat-exam-workflow-comparison` 管理。

## 獨立案例與原失敗

本批案外證據根目錄：
`C:/Users/zxc22/AppData/Local/Temp/artispec-workflow-comparison-20261003-71f369f6/`。

- 草稿來源：最終同一份 35 案對已核實的舊 wheel 為 34 failed／1 passed；現行來源在 Windows、實際 WSL Linux 各 35 passed。最早 fixture 兩處設定錯誤另存，不能把修正前後說成測試完全未變。
- 文件規則、coverage、驗收 helper 及舊 init：先兩平台各 62 passed；再加入 factcheck 的來源反例及四項實際布局反例，最終 Windows／實際 WSL Linux 各 **67 passed、0 skipped**。包含本輪 49 案及既有 18 案；兩平台最後 retry 的測試及 helper 指紋前後相同，不說成新增前後測試沒有改變。中間取樣分類曾將封存內的版本歷史誤算追加，獨立正例抓到後修正；原 66 passed／1 failed 保留。
- participant runner：原 8 failed／6 passed，修正後兩平台各 14 passed、0 skipped，同測試指紋。這是明確標示的 subprocess stub，**不是全新 agent 完整流程**。
- 三份 skills 的通用 `quick_validate` 未通過：其欄位白名單不接受產品既有 `compatibility`。已核實舊 wheel 也有此欄位；沒有刪欄位或修改檢查器冒稱通過。

證據：`f2-final-green.*`、`f2-linux-final-green.*`、`f2-independent-review-final.json`、`independent-frozen-{windows,linux}-green.*`、`independent-final-extended-{windows,linux}-retry1-green.*`、`participant-{red,green}.*`、`participant-linux-green.*`。資料契約核對採 `independent-source-review-corrected.json` 的實際 schema／kind／closed／entries／requires；原審查把不存在的頂層 fields 比成 None 的部分已撤回，不用作契約證據。

## 第一遍完整回歸

- Windows：2077 passed、3 failed、1 skipped，589.01 秒。
- 實際 WSL Ubuntu-24.04 Linux：2074 passed、3 failed、4 skipped，663.11 秒，由 Windows controller 啟動。
- 兩次回歸的 `src`／`tests` 全檔指紋前後相同。略過是既有退役警告路徑，Linux 另有三項只適用 Windows 的 junction；略過不算通過。

兩平台同樣失敗於三個既有測試：`test_instructions_apply_projects_authoring_three_blocks` 固定要求舊倒金字塔用詞；`test_archive_warns_on_empty_notes` 固定要求已淘汰的裁定缺漏提醒；`test_skills_carry_human_ruling_stances` 固定要求在 notes 直接重記裁定。測試角色已按現行明確裁定修正檢驗，保留三區塊、zero-inference、治理來源、非阻擋提醒與來源 bytes 等實際行為。AST 核對只修改授權三個方法，兩檔回歸兩平台各 45 passed、0 skipped；第一遍語意檢驗有一個錯誤字面 assertion，也另保存後修正。原完整失敗保存在 `windows-full.*`、`linux-full.*`，沒有覆寫成成功。

另找到 factcheck 舊句把 aggregate check green 當成所有識別碼都解析成功。草稿來源失效可只列軟體診斷，因此這個推論不成立；獨立反例真實重現後，已改為檢查 coverage、相關文件／軟體診斷及實際來源。不改完成算法。

## 最終完整回歸

- Windows：**2085 passed、1 skipped**，623.46 秒。
- 實際 WSL Ubuntu-24.04 Linux：**2082 passed、4 skipped**，691.18 秒；Windows controller 啟動。
- 兩平台 exit 0，`src`／`tests` 全部檔案前後指紋相同；略過原因與第一遍相同，沒有 PDF／proof 環境略過或放寬條件。
- OpenSpec strict：22 passed、0 failed。這是機械驗證，不代稱 agent 完整流程通過。

證據：`windows-final-full.*`、`linux-final-full.*`。來源與測試後續未改時，不再重跑整套；實測若發現並修正新缺陷，另保存新版本與相關驗證。

## 最終安裝包

新 wheel SHA-256：`d88cd4e18539d55f2fcb847e58843555740b7d0a465eb0803f75c983d7c0bdad`。
Windows 與實際 WSL Linux 分別新建 venv、移除 PYTHONPATH 並安裝該 wheel。173 個套件成員及完整集合與來源／已安裝檔案一致，唯一入口為 artispec，自身 Scripts／bin 沒有 docspec；模組來源為各自 site-packages。

兩平台各 18 次真實 console 呼叫，含 10 次查詢；init、guide、instructions、roadmap show、coverage 及活動／失效草稿來源符合預期，查詢前後指紋全部相同。無必要證據的 archive 確實拒絕。此 smoke 沒有建立虛假 owner 接受，也沒有宣稱完整實驗或封存落地已驗。最初把額外 PyInstaller 與產品安裝綁在一起的離線 resolver 失敗，以及控制器 cp950 印出問題，原紀錄保留後分步修正。

證據：`independent-fixed-wheel-install-{windows,linux}.json`、`independent-fixed-wheel-{win32,linux}-console-{events,result}.json`。原生 Windows build 依賴另釘版安裝至本批受控環境，不拿 Linux binary 冒稱 Windows EXE。

## 同題重跑已啟動

案外準備核對原輪兩案的 TASK、CSV、合成負責人資料、唯一容量事件、接手任務及 oracle，共六個輸入逐檔位元組一致；共同 contract SHA-256 為 `7b6266b52ffa7184082b1d24a238c9f7025f59b8ad4be2d5b6a2b8644d0dcedf`。雙 README 保留本輪開始時的指紋；公開操作指南採已核准的現行修正，這是實驗介入，不能稱所有條件完全相同。

Windows、實際 WSL Linux 新案分別由沒有前文的真實 CLI 會話訪談，兩次均正常結束且取得完整根會話 shell 事件。它們提出的問題涵蓋操作者、Windows 離線雙擊、安裝限制、規則、輸出與文件；控制器只依原合成資料回答實際提問，沒有提供未來容量事件或評分答案。兩案最初自行使用未指定 UTF-8 的 PowerShell 讀取，出現亂碼後重讀；原命令與輸出保留，這與外層紀錄器的 UTF-8 保真分開記錄。

兩個原會話已完成提案、需求、任務及文件來源，獨立核對沒有實質功能範圍衝突。Windows 提出 Python／Tkinter 程式包，Linux 提出本機 HTML／JavaScript 包；原需求沒有指定語言，兩者屬參與者技術選擇，仍須核對操作與交付限制。比較將明示此差異，不把技術方案造成的差異當成單一工具修正的效果。手冊規劃已使用草稿需求連結，但尚不能代稱定版、封存解析及完整交付均已驗證。

Windows 獨立測試會話 `01a10534-4b66-7b92-b3cd-83004fe88a8c` 已完成 19 筆測試與簽收，原實作者是 `01a1051b-4d95-74e2-b8a1-6cfbba5b80b8`。控制器以已安裝的 testplan 查詢核對 19 筆均為 current、作者與簽署為同一測試真會話；同為 gpt 的不同真會話沒有被拒絕。自我執行的 63 個案例均因尚無實作模組而出現 setup errors，零通過、零跳過；引擎保留四筆失敗證據，沒有完成冒稱。

測試角色提出 Q-gpt-1：同一 room-export/R1 宣告 test、inspection，卻包含純 Windows 紙面／列印視覺情境，現行需求層級的方法會要求它也有自動測試。該角色保留未覆蓋，不用 CSS 字串假冒實際視覺結果。原提案與測試 checkpoint 已保存，原提案者正在以既有流程修正方法分工，再由原測試作者核對簽收範圍。這先分類為合成案例的提案方法設定與控制器核對觀察，沒有放寬完成算法或修改產品引擎。控制器另有一次使用不存在的 question show 指令、實際退出碼 2，原命令保留，不算產品故障。

後續方法核對已完成：原提案者把紙面視覺情境原文移到獨立 inspection 需求及任務，原測試作者只重新簽收範圍受影響的 T12／T13；19 筆 current，原測試程式未改。實測另找到案外 recorder 的真實競寫缺陷：同時追加時，原 Windows JSONL 第 147 行損壞；完整原檔與指紋已保存，不能宣稱該階段 recorder 取得完整。獨立合成試驗的三次 16 程序寫入只各取得 15／15／14 筆完整記錄。

此控制器缺陷已有獨立行為案例的真 RED（1 failed／1 passed），修正以 Windows 檔案鎖／Linux flock 只保護完整 JSONL 追加，30 秒有界等待；不增加產品並行寫入支援。固定測試 SHA-256 為 `809e48d30850a130289c9d741a57ebca36e84aca58648d77b0779801be6d6d9b`，新 helper 為 `7eebddb6c7bdd07ea3e5ba1ec3fd403627fb566089d03b90dbf34e89bc4b7c86`。Windows／實際 WSL Linux 新增兩案各通過，完整 runtime／runner 各 44 passed，前後指紋不變。另存的 `post-recorder-lock-full` 完整回歸為 **Windows 2087 passed／1 skipped（566.69 秒）**、**實際 WSL Linux 2084 passed／4 skipped（691.41 秒）**，兩平台 exit 0、src／tests 前後相同；略過仍是原退役警告路徑與 Linux 的三項 Windows junction，沒有 PDF／proof 略過。上節的完整回歸是追加修正之前的結果，原紀錄保留。舊階段 helper／缺漏 log 保留，停止作者後才受控更新外部副本；產品 wheel 與原案例條件未改。證據在 `independent-recorder-concurrency-regression/`、`{windows,linux}-post-recorder-lock-full.*`。

Windows controller 對 WSL UNC 路徑的外層紀錄另遇真實 `msvcrt.locking` errno 22。原查詢、內層命令及外層失敗均保留；控制器改在本機保存 Windows transport log，Linux 實際命令 log 仍由 Linux runtime 寫入原 native 路徑，兩層以 phase／session 及 `native_product_log` 連結。不宣稱 UNC 鎖已支援，也不把原外層缺漏補造成成功。新階段已真實重試：兩層 exit 0、stdout／stderr 相同、受管理內容前後不變，原 participant／UNC logs 完整保留，native controller log 原前綴不變；證據在 `controller-audits/linux-browser-test-review-local-transport/receipt.json`。

兩案已進入原提案者的實作階段，尚未驗收交付。Windows 實作者依原測試跑引擎後提出 O1：共用 conftest fixture 的 generator 延遲捕捉班級變數，產生重複／漏人資料，16 個案例未到產品 validator 即失敗。這是測試作者資料缺陷及前次來源審查漏查，原 E-gpt-6 與審查保留並另更正；實作者未改測試，停止後交原測試作者處理。這個案例驗證異議分工，不列產品缺陷或把未完成任務算通過。

O1 已由原測試作者修正：只把該 fixture 的延遲 generator 改成立即建立清單，其他 fixture／oracle 及四份主要測試檔未改；直接完整案例為 63 passed、0 errors、0 skipped。之後正式核對只更新受影響的五筆簽收，O1 標為 test-fixed，19 筆 current、gaps 0；50 個受保護檔案（含實作、測試及原失敗證據）未改，原實作者才續跑引擎與建置。修正後、重簽前的觀察另存：conftest 未宣告於原指紋範圍，因此簽收仍 current。此案沒有證明假完成：排座任務仍是失敗，先前 CSV 成功不使用改動的 fixture。改善範圍列在[明確測試來源提案](../proposals/explicit-test-sources.md)，尚未核定，不在實驗中改引擎或 wheel。

Linux 原實作者已正常停止，完整直接案例為 113 passed、0 failed、0 errors、0 skipped；引擎測試層分別取得 93／13／5 passed，不把重疊的層級相加。初版 ZIP 的八個根目錄成員、CRC、manifest、原 CSV、實作來源及手冊 PDF 相符，SHA-256 為 `7c24fa9290bbeb0b887f220deb0a31eae9db22266355812b8bc375e756882cf4`；必要 inspection／demonstration 仍未完成，任務與工作尚未全部完成。

Windows controller 複製 Linux checkpoint 時遇深層 UNC 路徑 WinError 3，該次新副本由 helper 自行清除，沒有成功 sidecar，原失敗保留。改由實際 Linux runtime 建立唯一 `implemented-v1-ready-native`，134 個檔案的來源、預期、副本及取樣後 manifest 全等；Windows UNC traversal 另漏看深層兩檔，錯誤 verifier 亦保留，最終完整核對在 Linux 完成。不改產品、來源、舊 checkpoint 或歷史來繞過問題。

root 已直接閱讀 Linux latest 與四張 proof：中文、規則、恢復步驟、16 人與兩考場 32 格圖可讀，沒有截字；第二頁留白偏大，列為排版觀察。正文仍含控制器／待驗收敘述，GUI 完成後應由原作者依實據修訂 current 與必要新版，舊版不改。snapshot Markdown 與 latest 的 raw bytes 不同，只差 latest frontmatter 及六個管理註解，正文與圖 URI 相同，不誤報成定版後改文。來源在 `independent-linux-implement-v1-facts.json`、`independent-linux-v1-document-comparison.json` 與 `independent-linux-v1-root-proof-review.md`；這是獨立 agent 審查，不冒稱負責人人工接受或實際 Windows GUI 已通過。

Windows 手冊已寫並產生 preview PDF／proof，但真正定版 dry-run 被 W-gpt-1 的裸引用 `RL-gpt-11` 阻擋。作者補 `gov:RL-gpt-11` 後原錯值仍在，已提出 Q-gpt-2，沒有手改封條或豁免。原輸入錯誤屬 agent 表現；工具接受非法格式、且只有新增而無合法更正入口，是另項流程缺口。root 另用相同已安裝 wheel 的隔離專案十次真實命令重現：初始 check green，錯格式 link 返回 0，check red，補正後仍 red，unlink 返回 2、工作 bytes 不變。來源在 `independent-roadmap-link-recovery/repro-f6307188257641bea87ea194c4691799/`。已提出[最小恢復方案](../proposals/roadmap-link-recovery.md)，等待負責人裁定；Windows 案不視為 first-ready，不更換 wheel 或直接改封條，Linux 實機驗證繼續。

Windows 作者已於 06:40:29 UTC 停止。第一次完整取樣因 headless 圖例 probe 的深層 profile 路徑遇 WinError 206；失敗保留，改用較短的唯一案外目的地，2328 個檔案前後及副本指紋一致，不排除 cache／profile。獨立實際探測複製前後 msedge.exe 數皆 0，沒有殺除使用者程序；原 probe 的真實 argv／會話／建立時間已核對，用途只是手冊圖例，不當作實際 GUI 或首版交付通過。

停止點獨立審查另逐檔核對 Windows 包的 988 個檔案與 ZIP、12 個軟體來源及建置指紋；ZIP SHA-256 為 `de67478aaa8577a1eff16dda5b64d46c198315fcad6f3fc2ec934f1baace4d6a`。EXE 是 x64 GUI PE，Python／Tcl／Tk 依賴存在；19 筆簽收 current，E7–E10 為引擎真實取得的 63 passed、0 failed、0 skipped。任務 1–3 完成，任務 4 的 demonstration 與任務 5／6 仍待驗，手冊仍為 0.0.0 的預覽。包與來源一致不代表 Windows 操作、定版、接受或封存已通過。來源在 `independent-exam-reviews/windows-fixture-objection/stopped-first-delivery-review/attempt-3/review.md/json`，原輸入、測試、簽收及 E1–E6 的位元組保持不變。

同一次審查真實重現摘要提示缺陷：官方 `roadmap show --json` 的 question.command 建議 `artispec question show Q-gpt-2`，已安裝 CLI 返回 2，查詢前後檔案不變。這與上文控制器自行猜錯命令不同；前者是工具產生的無效入口，後者是控制器操作錯誤。原 JSON、退出碼、兩層命令紀錄及指紋保存於 `attempt-3/generated-question-query-defect.json`。後續 `fix-summary-source-commands` 已將 Q／W／M 提示改為現有唯讀入口，獨立固定案例先得兩平台各 6 failed／3 passed，修正後相關回歸各 81 passed／0 skipped。最終完整回歸 Windows 2096 passed／1 skipped、實際 WSL Linux 2093 passed／4 skipped，新候選 wheel 安裝與原停止點核對通過、strict 23 passed；此項已按 OpenSpec 結案。未另設查詢 API 或改完成判定，兩個實測安裝未換，見[修正報告](summary-source-commands-run.md)。

GUI 控制器的合成能力驗證與案例驗收分開。私有 Chrome 154 已有真實可見 trusted click、可讀 owned PrintWindow、兩種 IP 的指定 EXE WFP 阻擋／解除證據。原選檔失敗經單次新 trace 找到：對話框由同私有 EXE 的子 PID 承載，owner 指向原主視窗，原只找主 PID 的 selector 漏掉；只能說明新 trace 的實據，不能倒推原失敗窗口。新 guard 的機械 17 案及真正 owned child dialog 核對通過，但原固定 input ID selector 仍失敗，尚未選 CSV、下載或 GUI 存 PDF；所有退出／清理及原失敗收據另存，不冒稱案例功能通過。控制器仍在補足限定的輸入欄位觀測，尚未操作 Linux 完成包或接受／封存。

後續案外語意控制器的 v3 因匯入本機不存在的 pywinauto API 停止，屬控制器實作錯誤，未選入 CSV；原記錄及清理保存。依真套件 source 修正的 v4 已取得真正 filename Edit／Combo 的語意、editable 與 ValuePattern，但 Open 尚無合格映射，仍停止。只讀 exact-ID1 新 trace 後才真實確認為 Win32 SplitButton（50031），native HWND、UIA RuntimeId／PID、單一 dialog ancestor 與完整 ownership 一致；Name／Value／子樹未讀。三程序真退出 0、filters 由新 engine 核對已消失、來源與設定指紋相同。v5 最小 Open／Save 映射尚在案外驗證，不把 smoke、metadata 或 API 文件當成實際選檔、下載、列印或案例接受通過。

v5 已實際送入原生 filename 欄位並 Invoke Open，但舊關閉等待拒絕後停止。拒絕當下沒有原生可見狀態取樣，保存的 DOM 也在輸入之前，故「對話框短暫隱藏」只是推測，不能說已匯入 CSV。另設唯讀關閉觀察器：隱藏仍不算銷毀，也不授權後續輸入；真正 owned Win32 視窗生命周期的九個案例及原輸入 guard 十七案通過。v6 才取得 Open 之後的新 UTC DOM、expected CSV 內容與 trusted change；新 Blob 下載及真正可見列印預覽亦取得。Save 的實際 filename Edit 可識別，但 native ID1／UIA Win32 Button 的語意為 null，控制器未輸入 PDF 路徑、沒有 PDF 成品，整段 full IO 仍失敗。root 已實際查看本次 CSV 及 preview 兩張 owned 圖；這些只屬合成能力驗證，沒有操作考場包或寫產品證據。原失敗不改寫，來源在 `gui-controller/chrome154-headful-io-v6-09d6ec586bc9/`，root 畫面核讀另存 `root-visible-v6-review.md`。

v6 獨立唯讀審查已逐項核實：53 bytes 的新下載與選取 CSV 完全一致；新 DOM 的取樣時間晚於 native Open Invoke；source／copy 各 273 檔完整 before／after manifest 相同。三個程序退出收據皆 0，停止 holder 後新的唯讀 WFP engine 核兩個 filter 已不存在。設定證據有明確缺漏：association／policy 只有當時 finally 的 readback 比較布林，沒有序列化原始 after 欄位，不能宣稱獨立逐欄核對通過，也不能拿稍後取樣補成當時資料。原 result SHA-256 保持 `d2b45cebfcc48fef97871bee17f8d0e668e5440373e2bd0cbfed007d13b40025`；審查在 `independent-gui-reviews/chrome154-native-io-v6-09d6ec586bc9/independent-review.md/json`。

Windows EXE 原成品另以中文、空白的短案外目錄準備完整副本：988 個包檔及 ZIP 的逐檔 bytes／SHA／CRC 相符，原 project 與保留 checkpoint 各 2328 檔前後不變。這是取樣與操作方案準備，尚未啟 EXE 或盤點真控件；不假設 ttk 必然提供可用 UIA Button、Edit、TabItem。兩個 GUI controller 共用 Windows desktop，因此桌面輸入依序執行。來源在 `gui-controller/windows-exe/prepared-1a4a282f/final-preparation-review.json` 及 `windows-exe-gui-proposal.md`。

後續兩次 EXE 首次盤點均在真正雙擊之前停止。第一次原 Explorer argv 沒找到精確資料夾的新窗；只讀補查有一個新 Shell 視窗，但實際路徑不匹配，不接管或盲關，原 launcher 的最後退出碼／creation 亦無法復原。不能將 timeout 推論成某一已確認原因。第二次改用 [Microsoft 的 Shell.Explore](https://learn.microsoft.com/en-us/windows/win32/shell/shell-explore) 開資料夾，真實 void call、新 HWND、精確路徑、COM EXE 項目及可見 UIA ListItem 已取得；原 native foreground 檢查仍拒絕，故沒有雙擊、EXE 啟動或產品操作。新認領 Explorer 已精確關閉，WFP filters 152440／152441 已消失，EXE processes 為空。來源／checkpoint 各 2328 檔、package 988 檔及事前副本 1000 檔全相同，metadata／policy 保存真正 before／after pair。來源在 `gui-controller/windows-exe/execute-main-{a220a8b331db,v2-1befc54889a9}/`；前次 tool exit1 與 intended2 不混稱實際原生退出，第二次真實 exit2。

另一次最小 Save-caption trace 也在初始 native foreground 等待停止，未點列印、未啟 observer、未取得 caption 或 PDF。 browser／holder 真退出 0、filter 清理及同次 raw 設定 pair 已保存；原 aggregate cleanup=false 是沿用要求 observer exit0 的條件，即使 observer 尚未啟動，也仍保留原值並另列各實際啟動資源。兩次不同視窗的前景拒絕當下沒有保存 foreign HWND／PID，因此原因仍未知，不能拿後續 document.hasFocus 推論 native foreground 或是哪個外窗搶焦點。來源在 `gui-controller/chrome154-save-ID1-caption-trace-90744cc43e31/`。下一步只準備限定 owned window 的請求焦點與當時 metadata，後續輸入仍須原 exact-foreground／visibility／hit-test guard；尚未宣稱已修好或完成案例 GUI。

追加的受控焦點請求已有實測：保存真正 native facts 與 `SetForegroundWindow` BOOL，再對相同 owned HWND／PID／RuntimeId／GA_ROOT 請求原生 UIA SetFocus；只有真正 `GetForegroundWindow` 相等才續原輸入 guard。新 Save-caption trace 的 Win32 請求為 0，UIA 請求後原前景檢查通過；沒有讀外窗內容或改設定。真 caption 才確認為 UIA `存檔(S)`、native `存檔(&S)`；raw 字串不同，按既有 accelerator normalization 取得相同 `存檔`，原 whitelist 缺這個語系用詞。該次只讀 caption，沒有 filename 輸入或 PDF，root 亦實際查看 owned 預覽圖。來源在 `gui-controller/chrome154-save-ID1-caption-trace-v2-a59009bcc8c1/`；最小 alias 和完整 IO 正另驗，不將診斷成功算成 PDF 或案例通過。

Windows 的 v3 首次盤點則已真由精確 Explorer 項目雙擊 EXE，actual main PID 20836／HWND 16322146，Win32 18 節點、UIA 22 節點與 owned PrintWindow2 都由實際有界 worker 取得，真 exit0。root 親看 1096×819 的初始圖，中文、選 CSV 與兩房分頁可讀；排座／輸出呈現停用樣式。實際 ttk 功能控件只提供空 title／TkChild／Pane，不能假造 Button 語意，也不能把 native enabled=true 當 ttk 可用。因此尚未 CSV、排座或輸出，下一步先以 root 已核可見控件與新 runtime HWND 做限定操作，並核真正新輸出。app 退出 0、認領 Explorer 已關、filters 152444／152445 消失，source／checkpoint／package 與全部事前副本未變；來源在 `gui-controller/windows-exe/execute-main-v3-f526541df67a/`。這只完成首次啟動與只讀盤點，不能列作 task demonstration／inspection 已接受。

合成控制器 v7 已實際完成原生 CSV 選檔、Blob 下載、可見列印及原生另存 PDF。選入與下載的 53 bytes／SHA 相同；PDF 為 55,971 bytes、1 頁，並非 CDP printToPDF。root 親看三張 owned 畫面與真正 PDF 的 render，nonce、中文及內容均可讀。observer／browser／holder 三程序真退出 0，兩個 filters 由新唯讀 engine 核對已消失；當次設定 raw before／after pair、來源與副本完整 manifest、12 個 helper 與 runtime 指紋相符。原 result 與命令紀錄保留，獨立審查另作。來源在 `gui-controller/chrome154-headful-io-v7-a5d5145c76c7/`。此結果只證明合成控制器能操作，不代表考場案例已操作、接受或封存。

Windows 成品的下一次獨立操作已真匯入 CSV：以已核圖片的可見 CSV 標籤對準新 runtime HWND，再沿完整 native hit／foreground guard 點選；真 chooser 填入同 SHA 的原 16 人名單副本、Open 並確認視窗銷毀。root 親看當次 `owned-main-after-CSV.png`（`52c63c2e9b24ef02238bf4217f278112fb82346335c3eab3aa7dc31fd715008d`），畫面寫明 16 位學生已載入、下一步為安排座位；輸出仍停用。真 app exit0、owned Explorer 關閉、WFP 清理完成，source／checkpoint／package／既有副本及 metadata／policy raw pair 不變。來源在 `csv-0529f5d9/CSV 匯入/`。此階段沒有安排、輸出、接受或封存，未提前建立 passing demonstration 證據。

Windows 隨後另一次真正安排操作亦正常退出。fresh CSV 載入後才按已核可視標籤及新 HWND 的 Arrange，當次 R1 畫面為完整 4×4、16 人、班級／座號／姓名與前方標示；root 親看確認可讀、正交班級交錯、輸出按鈕正常樣式。新圖 SHA-256 為 `4357830b2d86b000f4bebae21b0bdc9083b42395e1cf8ea3a99505d545230a03`；來源在 `arr-88198012/排座操作/`。沒有點 R2 或輸出，也沒有 HTML／列印成品；尚不從 R1 圖推論另一房的呈現或整段交付通過。原 CSV、軟體及受管內容維持不變，當次真退出／清理保存。

Linux 建出的八檔初版也已在 Windows 私有 Chrome154 取得實際初始畫面，root 親看中文與未選檔狀態，三個後續按鈕仍停用。原 input 真的提供 UIA `students-file`／Button，native root／PID／hit 與 DOM 相符，無需猜坐標或改 artifact；這不是功能操作。來源在 `gui-controller/actual-linux-v1-initial-c80e9f09bddf/`，當次 source UTC、完整八檔原／副本 SHA、raw 設定 pair、browser／holder 真 exit0 及 filters gone 保存；observer 沒有啟動。獨立 parser 已按本版 combined HTML 的真 schema 建立及核十二個記憶體正反案例，仍等待真正下載檔，不以舊 markup 或預先生成檔冒充。

Chrome v7 及 Windows 首次盤點 v3 的另角色獨立審查已完成，五張 owned 圖及真 PDF 重新閱讀／render、原收據與前後指紋一致，五十項可取得檢查通過。明示外層退出碼完整 envelope 的取得限制、指定 EXE WFP 不等整機斷網，以及 ttk Pane 不能推論功能 Button；原失敗與收據 bytes 保留。來源在 `independent-gui-reviews/chrome154-v7-windows-exe-v3/`。後續實際 CSV、安排與 Linux 初始盤點另做獨立審查，不把 actor 自評當成另一角色。

三個實際案例階段的另角色審查也已完成：五十五項可取得檢查通過，root 及審查者各自讀當次圖；R1 原 16 人資料與 CSV 相符，但沒有宣稱 R2 或紙面已驗。Windows source／checkpoint 各 2328 檔、package 988 檔不變；私有副本只追加已列明的二十六／三十個 controller 檔，不能稱整份副本 raw manifest 相同。Linux 八檔原／副本的實際 bytes 相符。CSV 舊 readonly phase 標籤原文保留，依真正 session／actions 分類，不倒改歷史。來源在 `independent-gui-reviews/actual-case-initial-csv-arrange/`；外層 Windows shell envelope 的取得限制仍在。

Linux 初版的完整私有瀏覽器操作亦已真退出 0：原 322 bytes／SHA 名單經原生選檔匯入 16 人，真正 Arrange 產生 iframe，Blob 下載 HTML 與當次 srcdoc bytes 一致，獨立 parser 核 16 人各一次、32 格與正交規則通過。真正 iframe 列印及原生另存得到 70,902 bytes PDF（`4b2fd7709459f1bd85f54e8090b42703c9488a70da1fdaf266cc204a1a513a54`），兩頁均 A4 橫式，R1／R2 各一頁。root 已親看四張 owned 操作圖及兩頁 render，R1 的 16 個姓名／班級／座號、R2 的 16 個空位與前方／列欄標示可讀、無可見裁切。原契約不要求兩房都有人或平均分配，沒有把這個分布判為錯誤。

另由測試角色完成當次成品的獨立唯讀審查，70 項可核對檢查通過，報告保存於案外 `independent-gui-reviews/actual-linux-v1-fullIO/independent-review.json` 與 `.md`。審查重新以真 CLI 讀取實際下載 HTML 與原名單，直接解析 PDF 的兩頁、32 個座位及姓名，並逐格對照 HTML；兩頁重新 render 的 pixels 與原 proof 相同。原八個包檔、收據、命令紀錄、parser 與完整來源指紋在審查前後不變。此結果只證明當次 Linux 建置包在 Windows 私有 Chrome 的功能與輸出，不代表 Explorer 檔案關聯、原生 Linux GUI、負責人接受或封存已通過。

這次 source target 與根 frame 分別固定，不把兩種 CDP 識別碼假定相等；沒有插產品 nonce、isTrusted 標記、呼叫 app core 或用 printToPDF 代替原生操作。observer／browser／holder 三程序真 exit0、新唯讀 engine 核 filters 152454／152455 已消失、exact private image 無殘留；11 項 integrity、原／副本八檔的當次 SHA、metadata／policy raw pair 保存。來源在 `gui-controller/actual-linux-v1-fullIO-bbed0bb214a3/`，另角色審查結果如上。這個 slice 不證明 Explorer 預設關聯啟動、原生 Linux GUI、交付接受或軟體封存。原作者其後已獲准整理 current 教師手冊、保留 1.0.0 並以合法新版本重包；該續接尚未完成，不將舊包的 GUI 結果自動算到新包。

Windows 後續已在 fresh session 證明真正輸出資料夾欄位的固定語意：當次 native Edit ID1152 的 HWND、PID、creation、UIA RuntimeId 與祖先鏈前後一致，限定讀取 CurrentName 得到 folder 白名單匹配。原 LabeledBy=null 盤點保留，不回填；未輸入資料夾、未選取、未產生 HTML 或 PDF。真退出 0、原受管來源／checkpoint 2328 檔與 package 988 檔不變，指定 EXE 的 WFP filters 152458／152459 清除。來源為 `cap-12bf5ddb/資料夾標籤/`；輸出仍待實跑。

Linux 包的 Explorer 預設關聯另一次真嘗試返回 1：控制器在發現超過一個新 Chrome native 候選後、讀取 UIA／URI 或開 Explorer 前停止。原當下候選清單未保存，不能斷言恰兩個或原因；未資格認領的視窗不關閉，cleanup 狀態明示未知。原 launcher exit 0、七項來源／包／association／policy integrity 相同，原失敗保留於 `gui-controller/actual-linux-v1-Explorer-a0bb84139753/`。之後新唯讀 native 觀測顯示一個一般候選及其 owner／TOOLWINDOW popup，只是新的觀測，不能回填失敗當下；未讀其 title、UIA、URI 或 profile。啟動驗收仍未通過，屬控制器／環境限制，尚無這一步的產品失敗證據。

只針對這個固定一般視窗的續接同樣真返回 1，沒有再啟 Chrome：當次 native HWND／PID／creation／owner／style／image 相符，單一選取 tab 亦成立，但原自有 blank marker 與 case URI 比對均 false。未知 URI 原文及其他 tab 內容未保存；未認領、focus、Explorer 操作、雙擊、截圖或關窗。原失敗 bytes 與七項 integrity 保留，原未認領視窗的 cleanup 仍 unknown；來源為 `actual-linux-v1-Explorer-resume-3991513a15b9/` 與兩次失敗的有界摘要。停止擴大這條測試路徑，不冒充檔案關聯通過，也不改整機設定。

Windows EXE 後續真輸出已返回 0：fresh 原名單→Arrange→Export→當次重證 folder 欄位→ValuePattern 寫入自有空目錄→已證普通 Select-folder Button 真 physical click，chooser 已消失。真正產生的 `R1.html`／`R2.html` 經未改 parser 的真子程序核對：32 格、16 人各一次、班級／座號／姓名正確且符合正交規則，R1=16 人／0 空位、R2=0 人／16 空位。HTML SHA 分別為 `24e105f20dac6914542c516fd77ef2818e33f0c094b8dd770c6a5f0c6e822ebe`、`3b55110c8aa7770e438a3ab985a96541234117b9605c3a921a356323f475d077`，來源為 `out-049e5a73/實際輸出/actual-output/`。checker 前後輸出不變，真 app exit0／owned main gone／私有 image 無殘留，來源／checkpoint／package 及原 CSV 保留。這次沒有點 R2 tab、列印或產生 PDF，不提前記成完整交付、接受或封存。

另角色已核對上述原輸出與完整收據，五十項可取得檢查通過，來源為 `independent-gui-reviews/windows-actual-output-corrected/`。首輪獨立審查 exit1／四十九項保留；兩個審查器假設另更正：CSV Open snapshot 比 selected 多兩個非身分欄位，其原身分欄位完全相同；WFP stdout 只是 ACK，真正 API readback 在原 holder events，不能要求兩層物件整份相等。更正按原 holder 的完整欄位及出現次數核對，沒有改原收據或重跑 GUI／產品，也沒有新證實的產品缺陷。原 source／checkpoint 各 2328 檔、package 988 檔不變，副本只追加該 session 的 38 個 controller 檔。外層 shell 完整 envelope 取得限制仍明示。

Linux 手冊回饋續接在 900 秒控制器上限返回 124，未取得成功 turn 或完成回答；六個 command result 及 turn completion 不可得，原事件不回填。作者已開 `refine-teacher-manual` 文件 change，留下六組 material／concept、I-gpt-4／RL-gpt-12，沿用 W-gpt-1／2；latest、1.0.0 及原包仍不變。核 Windows 自有程序 cleanup 及原生 Linux 該 actor 在案例目錄的 active process 均空，取得 `manual-feedback-v1-timeout-native` 完整停止點，來源／副本／after 指紋相同。其後同一真 UUID 以新 phase 續接既有準備，不把逾時算完成，不注入下一需求事件。此為控制器時間上限及未完成續接，沒有據此宣稱產品錯誤或修改產品。

root 另直接讀取 Windows 最新手冊與三頁 preview proof：正文按範圍、CSV、操作及恢復組織，圖例和中文可讀，未見截字；未把接近頁尾的跨頁段落誤判成溢出。開頭仍有待驗提醒，超容量的「請修正名單」可更明確說明不得任意減人，列為作者內容精度觀察，不改產品。首版 R1 圖例已自然顯示容量與空位數，後續唯一事件須依實際新增的契約與文件差異比較，不強造功能失敗。來源在 `independent-windows-v1-root-preview-review.md`；未定版狀態不因 proof 可讀而改為完成。

Linux 原作者以同一真 UUID 續接後已正常返回 exit0，成功完成事件、41 次 shell 命令及整份新交接保存，沒有回填前次逾時缺漏。教師手冊合法定版為 1.0.1，版本 PDF／proof 位於 `changes/_versions/`，文件目錄維持 latest；root 親閱四頁，操作、輸入格式、結果、限制與故障處理可用，正文沒有驗收流水帳，整圖獨占第三頁所致的留白不是裁切。新 ZIP 保留八個 member，只有手冊與 package-manifest 改變，其他六個程式／CSV 檔相同；原 1.0.0、測試、簽收及既有證據保留。新版實際引擎 E-gpt-5 為 5 passed／0 failed／0 skipped，不以這五案冒稱完整測試再次執行。新原生停止點 `manual-feedback-v1-final-native-independent` 為 168 檔，來源、預期、副本、after 及 sidecar 全部相同；作者已停止。沒有新版 GUI、接受或封存。

上述新版已完成另一角色的獨立唯讀核對，16 項必要檢查通過、真程序 exit0。四頁 proof 與直接讀取 PDF 後獨立重繪的像素完全一致，25 筆測試簽收 current；42 個精確受保護路徑及舊停止點／歷史相同，原「13 來源」分組無法獨立辨識，沒有猜數量。新版 PDF 為 305,370 bytes／SHA `55c33b4cc2695f8c67b5b0754e0d6c794d4deb23ad2397cc7f72450a350be345`，ZIP 為 267,650 bytes／SHA `2c344863c6a43119424e717eeaa41efa732c5e584041180595fa97dbfafe7270`，八個 member 的 CRC／hash 及內外清單核過。兩次已安裝原生查詢 exit0、前後 168 檔不變。舊 E1 失敗、E2–4 及 900 秒逾時缺漏仍保留。新會話最後整體 exit0 不代表 41 個命令都成功，四次 exit1 原文保留。交接將新版量測腳本誤稱初版來源、額外加強整機離線／主機無 Python 條件，分列 agent 文字與範圍觀察，未新增產品閘門。來源在 `independent-gui-reviews/linux-manual-feedback-1.0.1/independent-review.json` 及 `.md`；新版 GUI／預設關聯與接受仍未驗證。

Windows 兩房紙面後續：R1 原生 Ctrl+P／另存確實得到 PDF，但首個只去空白的抽字檢查返回 exit1；原收據與 PDF 保留。root 親閱發現內容完整，另只讀診斷確認抽字將「人／方／面」寫成 Unicode 相容部首。新 reader 只將來源與 PDF 兩邊 NFKC 後去空白，保留 raw text、原缺漏及 codepoints；不增加語意別名，也不略過標題、姓名、16 座位與空位檢查。既存 R1 PDF 無重印復核 exit0，再以唯一續接真列印 R2，子程序／launcher／PowerShell 均 exit0。兩份 PDF 各一頁 A4 橫式，R1 16 人／0 空位，R2 0 人／16 空位；root 已親看兩頁與原生 preview，方向與標籤可讀、無可見裁切。PDF SHA 分別為 `6b35ceab2c1a2f773b92ddf7c354d620a3b02dd4f12e15557a4a974a2dd39903`、`ebcd2ebc8775ab00b19ed0fdddb16cbd3ad61fa154a801c0ed5c6851260a4268`。自有 browser／holder 正常退出，當次私有 filters 消失，七項 integrity 與原兩房 HTML 相同；既存未能確認的 installed Chrome frame 未碰，不宣稱已清除。這是控制器比對修正，沒有新產品缺陷；原 R1 exit1、新只讀 exit0、R2 GUI exit0 分列，獨立紙面審查仍進行中。來源在 `gui-controller/actual-Windows-R2-paper-success-bounded-summary.json` 與 `root-windows-two-room-paper-visual-review.json`。

工程文件風格的獨立 how-to／reference 小案例已完成，兩份實際正文均通過獨立 agent 的來源與用途核對；來源四檔及每案七次結案查詢前後的內容不變。Windows how-to 可按命令匯出、保留衝突原檔、另存及確認後覆寫；Linux reference 可查預設、欄位、空資料、錯誤與限制。reference 的目錄錯誤表列有一處可更精確的措辭，獨立重播已核對未開覆寫與允許覆寫的兩條分支，列為作者內容精度觀察，沒有改產品或文稿。

Windows 紙面另角色審查已完成：修正版 53 項核對通過、真 exit0，123 個原始檔前後 SHA 相同。首輪 50／53 的三個 reviewer 假設錯誤另存，沒有改原 R1 失敗或產品資料。審查者亦直接以 pypdf 打開兩份真 PDF，頁數、pagebox 及完整 raw text 與已保存收據逐值／逐字一致，真子程序與 shell exit0，輸入 bytes 相同；不是只重算 actor 的文字結論。兩份 PDF／source／preview 已由 root 與審查者各自親閱。現有 Windows 教師手冊三頁 preview 的內容審查也已完成，具備完整教師操作脈絡，待驗提醒與超容量措辭列 agent 內容觀察，仍為 0.0.0／未定版。來源為 `independent-gui-reviews/windows-two-room-paper/independent-review.md`、`final-addendum.md`、`independent-paper-review-corrected.json` 與 `direct-PDF-read-105828876140.json`。

工程文件預設的最後一項同題手冊審查已完成，`engineering-document-defaults` 五項任務全數核對後，按 OpenSpec 同步兩條正式需求並封存至 `openspec/changes/archive/2026-10-04-engineering-document-defaults/`；驗證明細在該目錄 `verification.md`，正式規格為 `openspec/specs/engineering-document-guidance/spec.md`。封存後 strict 真 exit0、23 passed／0 failed（21 個活動 change 與兩個正式 spec）。這只結案文件預設，不結案草稿引用的完整兩域實測、驗收工具整合或同題比較。

Windows 小案例內派只讀事實審查子會話的 UUID、完成證據及取得限制另存；Linux 採單一作者、案外審查。計數分開：Windows 44 次 installed CLI、其中 36 次 read/help queries；Linux 45 次 CLI、其中 27 次 queries。shell 事件及直接程式呼叫是其他層級，不能相加；兩案用途與派工條件不同，不當作嚴格用量對照。小案例只授權草稿，沒有文件定版、PDF 或軟體接受與封存，也不替代兩域實驗。來源及結論見 `engineering-style-runs/fresh-style-summary.md/json`。

## 尚待完成

最終來源回歸與新 wheel 兩平台安裝查詢已完成；文件預設封存後的 strict 再核為 23 passed／0 failed（21 個活動 change 與兩個正式 spec）。同題實驗仍待 Windows 工作連結的合法恢復與文件定版、新 Linux 包的實際交付核對、兩案初版接受／封存、唯一容量變更、全新會話接手、獨立比較及收尾。已完成的私有 GUI／紙面切面如上，不將整段交付判為通過。同題實測不代替先前 README 六案，也不把操作者不用安裝 Python 擴成「主機絕無 Python」或新增整機離線完成閘門；未取得的環境結果照實保留。

自用開發方向先保留[切換提案](../proposals/self-host-development.md)。本輪依原 OpenSpec 完成，不在驗證途中切換進度來源。
