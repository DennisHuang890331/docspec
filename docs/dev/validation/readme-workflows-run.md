# 移除舊指令與 README 流程驗收（2026/10/01）

## 現況與驗收範圍

`artispec` 已成為唯一套件入口；README 已補齊兩域流程與本機安裝。六案初次實測已執行，**本輪尚未整體驗收通過**：兩個新建案例暴露同工具的獨立 agent 身分辨識缺口，修正方案待負責人裁定。未完成的軟體流程不以機械回歸取代，也不把之前四案當本輪結果。

由 `retire-docspec-command`、`validate-readme-workflows` 管理，在 `claude/software-domain-redesign` 修改；未提交、推送、開 PR 或修改 main。案例、安裝環境、事實清單、完整命令紀錄及評分資料都位於 repo 外，只使用合成資料。repo 只保存本報告與可重現的建置／紀錄腳本。

## 具體修改

- console script 僅保留 `artispec`；安裝名 `docspec`、Python `dspx`、`docspec/`、`corpus`、`DOCSPEC_*` 及既有管理標記不變。
- 現行 help、錯誤、建議、guide、instructions、生成規範與內建參考改用新指令；歷史裁定、封存資料與舊版變更說明保留原文。
- hook 解析新入口的絕對路徑；缺少時提示 PATH，不回退舊指令。刷新只替換自家 hook，混合項目保留外部子項與設定；JSON／結構損壞報錯並保留內容。Gemini 的原有 hook 控制選项也保留。
- 英文 README 區分安裝名與執行名，介紹未發布版本的來源／wheel 安裝、共同導航、文件 develop／apply／定版／PDF／proof、軟體獨立測試／簽收／證據／封存及升級。刷新規範與資料搬移分開，定版仍須明確授權。
- 內容有變的 workflow skills 提高版本；既有專案用 `artispec init --agents-md --tool <實際工具>` 刷新。

## 測試先行與實測發現

移除入口／hook 的測試角色先建立失敗基線，實作者再修改來源。新建實測發現以下既有流程缺陷後，同一測試角色補上 52 個行為案例；修復前為 18 failed、34 passed。首次修復後正案 fixture 缺 `status` 導致 3 例全專案檢查失敗，測試角色補完整 fixture，保留原 `run_check.ok` 斷言。

- `put` 原來只查 corpus ID，拒絕有效的 `gov:D-…`、`gov:I-…`、`req:…`，還可能接受錯誤種類的 concept ID。現在重用 `check` 的 typed reference 判定與現有外部索引；不把外部 ID 放行給其他關係欄位，也不改非阻擋提醒。
- material 先寫入、concept 尚未建立時，`check`／`status` 的圖片檢查可能對 `None` 呼叫 `get`。現在維持原缺少 concept 診斷，避免例外中斷。
- hook 直接收到 `Read`／`read_file` 且附受保護路徑時會誤擋。現在只放行已知讀取工具；寫入、未知工具與沒有 tool name 的請求仍保護。修復後用實際已安裝 hook 再驗證，沒有只依賴 matcher 排除 Read。

這批相關回歸合計 **183 passed**：新增 52 案、engine write、put staging、hook payloads，以及既有 check／治理／軟體引用。正常／反向案例仍保留：缺失／草稿／錯種類來源拒絕且不寫入，缺必要證據不能完成，文件／軟體分別完成。

Linux 新建文件完成實際定版／export／proof 後，目視又找到 PDF 程式行合併的工具缺陷；manual profile 也無法修正。另派全新測試角色新增三例實際 PDF 座標驗證，修復前 **3 failed、0 skipped**：五個非空行位於同一 y 座標，空白行與縮排失真。修復讓高亮 token 沿用原文字間距、將換行 delimiter 呈現為 linebreak，不套用一般行內 code 小框；初次只修分行仍有 6pt 額外縮排，後續 scoped token 呈現同時修復。三例已 **3 passed**，涵蓋 default／tango、manual／pygments、plain fence，原 frozen bytes 不變且正常 fidelity 保持啟用。

內建模板來源更新後依維護工具重新產生 `.pack-hashes.json`，不使用 `--allow` 繞過完整性檢查，也不重新封條既有資料。該維護腳本另有過時 `from dspx import paths` 導致 ImportError，修正為現行 engine import。新增測試為 `tests/test_pdf_code_lines.py`；測試角色 baseline／controller events 保存於 `C:/Users/zxc22/AppData/Local/Temp/artispec-pdf-regression-role-20261001/`。

### 待裁定的流程缺口

Windows 新建的實作者與另外啟動的獨立測試 Codex agent 都誠實使用 `gpt`；簽收檢查因此把兩者視為同一實作者而拒絕。嘗試使用 `gpt-test` 也被目前工具標籤限制拒絕。Linux 新建另啟動全新外部 Codex 測試角色，已登錄 T1／T2／T3；T1 簽收也重現相同拒絕，沒有測試被簽收。此為工具把 provider 與 agent 身分混為一談，不能靠謊稱 `user`／其他 provider 驗收。

已提出方案：沿用現有 `created-by`、`written-by`、`signed.by` 字串欄位，允許同 provider 使用不同 agent 標籤；保留不同角色、必要簽收與有效證據條件，既有封存資料不改寫。因本輪要求沿用完成判定，且架構／流程變更須先確認，**尚未實作**。這不是新核定裁定。

也檢查了不同 provider 的替代執行方式：本機 Claude CLI 未登入，沒有憑證可做真實 Claude 測試；沒有借用它的名稱冒稱已執行。

## 安裝產物與機械驗證

修改前保留的基準 wheel 是當時 checkout 的真實建置，不宣稱是遠端發布版。兩者套件版本同為 0.1.0，所以隔離升級使用明確 reinstall。

- 基準 wheel：`C:/Users/zxc22/AppData/Local/Temp/artispec-retirement-baseline/docspec-0.1.0-py3-none-any.whl`，SHA256 `750519ca89b2ca95326d93d18dbc578c4005df581fdde1caa2ba1e4d76eb803b`。
- agent 初次案例 wheel r2：SHA256 `2e8a08bdb5efa49a2f11cfd282d2c2ea65d99d500d372ff5fe72e940158c93b7`。其失敗結果不在新版修復後回填成成功。
- 三項缺陷修復後 wheel r3：`C:/Users/zxc22/AppData/Local/Temp/artispec-retirement-final-wheel-r3/docspec-0.1.0-py3-none-any.whl`，SHA256 `3858aabc98599a80df8836011c97c2338f4a1b4cc2a28ce786ea89ad1eab48b3`。
- PDF 模板修復後 wheel r4：`C:/Users/zxc22/AppData/Local/Temp/artispec-retirement-final-wheel-r4/docspec-0.1.0-py3-none-any.whl`，SHA256 `ce5c6d60839e768cad34faa4a75a410b4a088b6b8ae8f53f4f129e929b132425`。
- 最終 wheel r5：`C:/Users/zxc22/AppData/Local/Temp/artispec-retirement-final-wheel-r5/docspec-0.1.0-py3-none-any.whl`，SHA256 `4cb1f210f7132714a0f659cd2fd8517d129a5d6e71f2738743dd4678a42f2d1b`。與 r4 逐 entry 比對，只改 README metadata 與對應 RECORD；所有執行碼、資產與入口相同。README 明示同 provider 身分限制，不把已知失敗當完整支援。
- Windows r3 wheel 隔離安裝／升級：**64 checks passed、42 次實際子程序**，其中 24 次 hook payload。紀錄：`C:/Users/zxc22/AppData/Local/Temp/artispec-package-windows-20261001-r4/package-retirement.json`。
- Linux r3 wheel 隔離安裝／升級：**64 checks passed、42 次實際子程序**。紀錄：`/home/dennis/.cache/docspec-workflow-validation/package-retirement-20261001-r3/package-retirement.json`。
- r4 wheel 再驗：Windows／Linux 各 **64 checks passed、42 次實際子程序**。最終紀錄分別為 `C:/Users/zxc22/AppData/Local/Temp/artispec-package-windows-20261001-r5/package-retirement.json`、`/home/dennis/.cache/docspec-workflow-validation/package-retirement-20261001-r4/package-retirement.json`。
- 最終 r5 wheel 安裝／升級再驗亦為兩平台各 **64 checks passed、42 次實際子程序**；正式最終紀錄是 `C:/Users/zxc22/AppData/Local/Temp/artispec-package-windows-20261001-r6/package-retirement.json`、`/home/dennis/.cache/docspec-workflow-validation/package-retirement-20261001-r5/package-retirement.json`。

腳本 `scripts/validation/check_package_retirement.py` 在原生 Windows Python／實際 Linux Python 執行，建立新環境及基準升級環境。確認 metadata 只有 artispec、同環境舊入口消失、空白／中文路徑、生成內容不重複、使用者內容與外部 hook 保留，以及 Claude／Codex／Gemini hook 實際寫入 exit 2、讀取與 staging exit 0；受管理內容指紋不變。不清理使用者其他安裝。

早期 Windows 安裝測試曾因 `.EXE` 大小寫比較產生假陰性、因舊生成器本身會刪 foreign hook 產生 fixture 問題；兩次失敗紀錄保留，分別修正平台比較、在舊生成完成後加入自訂設定再測升級。Linux 首次環境建立因沒有 ensurepip 失敗，改用空環境與 controller pip／uv 安裝；未改系統政策。命令引號／PATH 的 controller 失敗另外記錄，不算產品通過。

## 平台回歸與 PDF

修復前三項缺口的正式回歸，Windows／Linux 各 **1562 passed、1 skipped**；這兩份結果不認證後續 source 修復。修復後完整回歸：Windows **1614 passed、1 skipped**（435.67 秒）、Linux **1614 passed、1 skipped**（562.69 秒），退出碼均為 0。

PDF 呈現修復後最終完整回歸：Windows **1617 passed、1 skipped**（447.83 秒）、Linux **1617 passed、1 skipped**（562.30 秒），退出碼均為 0。JUnit 分別為 `C:/Users/zxc22/AppData/Local/Temp/artispec-retirement-windows-r4.xml`、`/home/dennis/.cache/docspec-workflow-validation/retirement-linux-r4.xml`；此份才認證最終來源程式與模板。

r3 當時兩平台 JUnit 均逐項核對 export 75、proof 8，共 **83 passed、0 skipped**。唯一 skip 是舊 group.yaml render warning path，非 PDF 工具缺失。原始 JUnit：`C:/Users/zxc22/AppData/Local/Temp/artispec-retirement-windows-r3.xml`、`/home/dennis/.cache/docspec-workflow-validation/retirement-linux-r3.xml`。r3 wheel 與當時 `src/dspx` 逐檔比對沒有差異；它不包含後來 PDF 模板修復。

上述 83 項是舊組合在 r3 當時的核對；最終 r4 的 JUnit 再逐項確認 export 75、proof 8、程式區塊座標 3，共 **86 passed、0 skipped**。r4 wheel 與最終 `src/dspx` 逐檔內容相同，r5 的程式／模板 entry 又與 r4 相同。只使用已取得的實際本機結果，不宣稱遠端 CI 通過。

本輪沿用既有使用者受控、釘版工具與字型，`setup --no-download` 僅確認現有受控資產，不宣稱唯讀或離線安裝保證。前輪 Linux 官方字型 ZIP checksum 失敗，以及從 Windows 受控字型補回 TW-Sung 的來源／指紋詳見 [前輪報告](work-summary-run.md)；本輪沒有把該下載失敗改算成功。沒有為消除 skip 放寬測試。

OpenSpec `validate --all --strict`：**10 passed、0 failed**。CI 維持機械回歸，未啟動遠端 CI。

## 六案與獨立核對進度

參與者 `fork_turns: none`，只提供案例 README、wheel 與任務，不提供事實答案。新建授權合成文件定版，測試另外委派；過時案只許必要查詢、整份交接與結果說明；升級案另許刷新規範與安裝。每次 CLI 由 `scripts/validation/record_installed_command.py` 呼叫實際已安裝入口，清除 PYTHONPATH，保存 argv、退出碼、stdout／stderr。實測不是來源碼入口。

- Windows 新建：已執行但**未通過**。獨立測試已撰寫，因上述身分限制未簽收；未實作、未取得證據、未封存，也沒有冒稱完成。早期 README 缺 delta `--purpose`、沒有清楚說明 draft 決策需 activate 已補入 README；原試跑資料保留。
- Windows 升級：核心保存與接手由獨立審查核對；基準同環境更新 r2、新入口可用、舊入口移除，未推進既有未完成工作。直接 Read hook 的 r2 限制明示，由 r3 機械測試另驗；參與者報告有退出碼錯述，沒有判為無限制全面通過。
- Windows 過時接手：核心事實與資料保存由獨立審查核對；有一項原始來源引用未被 log 支持，另外記錄。
- Linux 新建：外部全新獨立測試已撰寫與登錄，但同 `gpt` 身分拒絕簽收；尚未通過。文件已授權定版 v1.0.0、PDF／proof，初次 PDF 目視未過，失敗產物保存於案內 `validation-artifacts/failed-manual/`。r4 wheel 同 agent 續驗的實際 export／proof／PNG 目視確認換行已修復，定版快照、測試、原 RESULT 與失敗產物的雜湊不變；另寫 RETRY-RESULT，不能說成全新重跑通過。軟體不跳過簽收，未實作／無證據／未封存。獨立核對與原 oracle 衝突另列。
- Linux 升級：核心安裝及資料保存經獨立核對；guard 原 payload 版本及宿主派送證據有缺漏，原錯述保留。
- Linux 過時接手：核心事實與資料保存由獨立審查核對；controller quoting 失敗缺完整 shell 歷史，明示限制。

Windows 案外資料根目錄：`C:/Users/zxc22/AppData/Local/Temp/artispec-readme-windows-cases/run-20261001-014732-152536`。Linux：`/home/dennis/.cache/docspec-workflow-validation/readme-cases/run-20261001-014803-631093`。事實清單及 managed before manifests 都在案例之外；各 `*-commands.jsonl` 為實際命令紀錄。Linux agent 是全新 Windows controller 經 WSL 操作 Ubuntu-24.04 runtime，沒有宣稱原生 Linux agent。

前三案獨立審查產物：`C:/Users/zxc22/AppData/Local/Temp/artispec-readme-review-20261001/review-three-cases.json` 及 `REVIEW-three-cases.txt`，含逐原檔 SHA256、逐命令分類及來源轉換，未呼叫額外評分 CLI 混入參與者 log。

- Windows 過時案 29 筆 recorder：project query 19、help 1、handover write 2、non-CLI 7；兩筆非 CLI 失敗為報告引號錯誤及報告尚未建立。28 個預存受管理檔案只有交接單變更。RESULT 引用 `show guide --concepts` 但 log 沒有此命令；其他已記錄摘要能支持文件狀態，不能支持那一段額外概念 wording／audience 來源。列為 agent 來源引用未支持／可能漏記，不補造命令。
- Linux 過時案 24 筆：project query 15、version 1、help 1、handover write 1、non-CLI 6；一筆失敗為讀取尚不存在的報告。28 個預存受管理檔案只有交接單變更。兩案都保留原決策引用與疑點，不用舊 pass 蓋過新 fail，區分 current 簽收、已寫未定版文件與未完成 change。
- Windows 升級案 22 筆：project query 8、version 2、help 1、init 1、handover write 1、non-CLI 9；三筆 guard Write exit 2 是預期阻擋。18 個預存受管理檔案只有交接單改動；重算 backup 比對只變八個生成 skills、hook 與交接單，owner 文字／skill／theme／permissions／foreign hook 保留，無重複、舊入口不存在。RESULT 說阻擋 helper 外層 exit 1，原 log 是 2，列 agent 報告錯述。原 r2 直接 Read exit 2、正常 matcher 不派送的 Read helper exit 0 都保留，不能以 matcher 成功替代 direct payload。

參與者自報不取代紀錄。原始 source／test hash 另與既有引擎 evidence 核對，未改動。無法取得完整非 CLI shell 歷史、未實測宿主 hook 自動派送／重啟與真 frozen archive 的部分列限制；修復只針對工具／README 缺陷，agent 忽略或引用未記錄命令另列。

內建 agent 委派後續遇到 thread limit，Linux 新建的獨立測試與後續獨立審查改由外部 `codex exec --ephemeral` 啟動，沒有沿用對話。測試的完整 controller JSON events 與最終輸出保存於 `C:/Users/zxc22/AppData/Local/Temp/artispec-external-test-role-20261001/`；實際已安裝 CLI 仍記到案外 `new-commands.jsonl`，不是 source 執行。測試角色原始檔 SHA256 `86f08689430532e9069b9fa3b5a78f04000236c7536026c64f87d506d364d38d`，預實作 pytest 收集 `ModuleNotFoundError`，實際 Linux 命令 exit 2，外層 controller 回 exit 1；必須區分層級，未宣稱測試通過。一次未經 recorder 的目錄 glob 只確認 Unicode 路徑，仍列執行規則偏離；其餘引用／括號錯誤保留在紀錄，不補造成功。

### 後續獨立核對

外部 Windows 新建審查：`C:/Users/zxc22/AppData/Local/Temp/artispec-external-review-20261001/final.txt` 及完整 events。核對已安裝 metadata 僅 artispec、wheel 指紋、17 個新增受管檔及交接 manifest、測試當初寫入內容與現存 bytes 一致。133 筆紀錄中實際 CLI 100：project query 44、version／help 21、write attempts 30、init／setup 3、doctor 2；另 installation 2、external helpers 24、nested recorder wrappers 7，不把 wrapper 重算為 CLI。21 筆 nonzero 結果含合法拒絕、環境／探索錯誤與工具缺陷，不能全稱環境失敗。

審查確認 T1／T2／T3 全部未簽，無實作／有效證據／封存／已寫文件／定版／PDF／proof；來源準備不等於交付。Windows 測試檔 SHA256 `80a048d51bbba06c42a7e3ea70dd2358ebaad040a6ffbcbe7a5210a7d38af39c` 與當初寫入一致。原 recorder 沒有 agent/session 識別碼或獨立對話匯出，所以單靠這份 raw log 無法獨立證明 Windows tester 的乾淨上下文；主代理的委派說明不能替代該缺漏。Linux 新建外部測試則保存了獨立 controller events。

也發現 Windows 中間交接過早聲稱 scenarios 已建立，最終交接比 RESULT 成功寫入早卻聲稱已寫報告，列為 agent 表現。後來文件已可在省略非必填連結後正常 put／check／lint／render，仍未寫 prose，所以軟體簽收阻擋不能解釋文件未完成；不因 agent 停止而改工具完成條件。

第一次外部審查在 read-only sandbox 無法啟動 WSL／讀 UNC（E_ACCESSDENIED），Linux 升級列 unverified，沒有代稱通過。後來另啟全新審查，任務仍只讀，允許進程存取實際 WSL，未更改系統執行政策；結果與 events 保存於 `C:/Users/zxc22/AppData/Local/Temp/artispec-linux-upgrade-review-20261001/`。

Linux 升級獨立重算 18 個 trusted managed 原檔與 backup，backup 全匹配，current 17 個未變、只改 handover，無新增／刪除。實際 baseline 環境 reinstall、唯一入口、foreign hook／自訂規則／skill／theme／permissions 保留與無重複均有支援。非 managed 原檔除自訂 skill 外缺可信的預存雜湊，屬 participant backup 次級證據。37 筆紀錄：project query 13、version／help 9、init／write 3、installation attempts 2、external helpers 10；7 個 nonzero rows，含 pip／PATH、malformed payload、probe 預期錯誤。原 hook helper 版本覆寫，raw log 沒保存精確 JSON payload；只能支持標籤與返回結果，不能回填不存在的 payload。malformed JSON 真實 exit 2、RESULT 說 exit 1，列 agent 錯述。原 r2 direct Read 問題與正式 archive 缺 probe仍保留；最終 r4 的 mechanical recorder 另保存真實 stdin／命令／輸出並核對。

### 驗收建置本身的缺陷

獨立核對 Linux 新建時發現預存 `facts.new` 使用 `Hello, <name>!`、固定 `app/src/greeting.py` 與 `operator-guide`，但 controller 發題使用 `Hello Ada`、未限制文件 ID 或實作檔位置；案內 RL、delta 與測試彼此一致。原 facts 完整保留，不能事後改評分答案宣告符合。controller 的實際委派輸入可見主對話工具紀錄，但案外沒有預存完整發題檔，獨立評分因此保留來源限制。這是建置／發題流程缺陷，不把 agent 遵守案內需求說成違規，也不能把原案例當嚴格 oracle 驗收通過。

已修 `scripts/validation/build_readme_cases.py`：未來由同一契約產生 `OWNER-TASK.md`、案外 `new-agent-task.txt`、facts 與任務 SHA256；controller 須原封引用並在啟動前保存實際委派輸入。契約不固定任意文件 ID／實作路徑，只依 change 的宣告查實際位置。已核對產生的內容與雜湊一致；既有試跑 facts 未改。身分修復獲核定後，必須用這份一致的契約建全新兩平台新建案重跑，不能只續寫舊案補成完整通過。

### Linux 新建與續驗的最終獨立核對

報告：`C:/Users/zxc22/AppData/Local/Temp/artispec-readme-review-20261001/review-linux-new.json`、`review-linux-new.txt`。沒有改案例或前三案報告，未呼叫額外評分 CLI 混入 log。六案都已完成獨立核對，但驗收判斷與限制分案保留，不表示全數通過。

初次試跑 raw rows 0–133 共 134 筆：project query 26、guide／instructions 6、help 27、version 1、environment check 1、check／lint 4、CLI write attempts 38（35 成功、3 拒絕）、installation helpers 2、file helpers 28（其中 9 個寫入）、test helper 1；11 筆 nonzero。r4 同 agent 續驗 rows 134–148 共 15 筆：query 6、version 1、CLI writes 3、installation 1、file helpers 4（其中 report write 1），全部 exit 0。這份分類把指南及驗證另列，不能拿它與其他案不同口徑的 project query 數量直接比較，沒有宣稱用量降低比例。

獨立核對外部 tester 的完整會話事件，重建 test creation payload，SHA256 與當時 stdout、目前檔案相同；沒有實作者改測試或冒稱身分。實際 pytest exit 2 與 controller exit 1 分層，不能簡化成偽造結果。另有未經 recorder 的 glob 及兩次啟動前引號失敗，完整 shell 覆蓋仍有缺口。events 能支持獨立會話實際行為，但未保存外部 `codex --ephemeral` launcher argv；此旗標與乾淨啟動的完整參數不能只由 events 獨立證明，主對話的啟動工具紀錄不冒稱案外原始記錄。

唯一 freeze 在 row 113，v1.0.0；前後 frozen snapshot／test／failed PDF／PNG／初次 RESULT 與目前 SHA 全匹配。原失敗 PNG 的程式行合併、新 PNG 的 import／空白行／兩個 greet 分行，審查者都實際目視確認。最終 PDF SHA256 `d31dc763d49103b113596c2716e3036dfd0129bb8e9ff429d0838f320da1b748`、PNG `2b9f294376ecec22d94e97f2d6571e6392cc965cb231f0d5e130ee5968235464`。

結論仍是「初次部分完成，格式續驗成功」；T1／T2／T3 unsigned、API 未實作、無有效證據／封存，加上預存 oracle 衝突，不能算完整全新 README 新建案通過。這些剩餘限制未被清除或改成成功。

審查列出的不存在 `dspx-publish` skill 另區分：這是先前明確裁定移除、檢查併入 `freeze` 的現行設計，本身不算本輪安裝漏失。schema 的 `publish` 投影階段與既有 `autonomy.publish` 資料鍵仍保留，不能把內部階段名稱等同必須安裝一份 skill。本輪未改這個架構。

## 剩餘工作與交付狀態

已交付唯一入口、hook 安全更新、英文 README／升級說明、現況與裁定紀錄、提高版本的 skills、四項有實測證據的工具修復、驗收建置契約修正及全部六案獨立核對。最終 wheel、兩平台回歸與實際 hook 安裝驗證均已取得結果。指定分支與 HEAD `5a942b6` 保持，原本未提交成果保留；沒有提交、推送、PR 或修改 main。

未完成的是全新兩平台軟體新建完整驗收：須先裁定同 provider 的不同 agent 身分方案，再由測試角色建立相容／拒絕案例，修復並重建 wheel，用同一份預存合成契約與完整啟動紀錄開全新案例。舊試跑、oracle 衝突與報告缺漏不能回填消除。本輪 `validate-readme-workflows` 的完整驗收項目仍未勾選；不因回歸全過而封存成六案全數通過。
