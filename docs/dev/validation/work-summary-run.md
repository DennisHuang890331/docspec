# 工作摘要與 Windows／Linux 完整驗證

日期：2026/09/30。開發分支：`claude/software-domain-redesign`。對應 OpenSpec changes：`add-work-summary`、`complete-cross-platform-validation`。本報告只使用合成案例；前批規則、過時診斷與 Windows E11 結果見 `workflow-handover-run.md`，不得當成本批修改後的驗證結果。

本批實作與核定驗證已完成：Windows／Linux 最終完整回歸各 1433 passed、1 skipped，兩平台 PDF／proof 各 83 passed、0 skipped，四份合成接手案例核心條件均通過。Linux 接手使用 Windows controller 操作 Linux runtime，線上字型安裝仍有校驗不符限制；詳見下列原始失敗、替代方式與驗證邊界。

## 1. 實作範圍與授權邊界

- 新增 `docspec roadmap show <W> [--json]`。JSON 以 `schema-version: 1` 提供 work、dependencies、governance、software、documents、actions、diagnostics，文字與 JSON 由同一份結果產生。
- 先 roadmap 找工作，再 show，必要時讀摘要提供的原始紀錄。只沿明確 refs、子項、前置項與必要來源取得資料；保留原引用、明確取代來源、有效決策內容及相關疑點。缺資料不推論為沒有限制，取代關係不自動授權改套新版。
- 沿用既有完成、簽收、證據及文件狀態判定；正常項目以數量概述，問題保留識別碼與原因。已封存軟體顯示歷史任務／簽收／證據，不用目前程式重新驗證或重開舊工作。
- actions 是固定規則的建議：未簽收或需重審的測試交測試角色；未定版文件仍須負責人明確要求才定版。摘要不執行任何建議，不把軟體問題改成文件定版阻擋。
- 查詢不跑測試、不刷新或寫入受管理紀錄、不重寫 handover、不新增紀錄型別，不縮小完整驗證範圍；不新增自動語意判斷、stores、workset 或產品並行寫入能力。
- 六份 skills 與中英 AGENTS 已加入上述讀取順序及邊界；develop／apply 為 2.2、propose 為 1.3、test／implement／verify 為 1.2。既有內容比對機制提示專案重新執行 `docspec init --agents-md`，保留區塊外自訂規則。

## 2. 獨立審閱與修正

測試角色與實作者分開；獨立審閱者未修改摘要程式。

- **封存歷史被當成目前驗證**：初版在封存後程式變動時，對舊任務產生 needs-rerun 與補證據 action。已改用封存紀錄並標明 historical；不再以現行測試內容推導歷史簽收。
- **相關疑點漏列**：初版只檢查工作／change 根引用，任務與測試或文件下的章節疑點可能被漏掉。已對納入節點讀取疑點並追到 trigger 來源；需求／情境節點的同族邊界也已補上並驗證。
- **文件來源命令無效**：整篇文件的 `docspec show guide` 無法定位，已改用 `docspec show guide --concepts`；章節仍使用可定位的原始查詢。
- **封存原因不完整**：初版只取 archive.blockers，未包含格式、引用與前置等驗證。已整合唯讀 `validate_change(strict=True)`，不使用會刷新任務的 archive.plan。
- **正常項目逐筆展開**：初版仍完整列出正常任務與簽收。文字已概述正常數量，保留異常明細、證據識別碼與有效決策內容；JSON 保存完整結果。
- **軟體前置循環與歷史依據漏列**：追加審查發現軟體提案的前置循環未明示、封存需求依據誤讀現行 spec。測試角色先以 `test_software_prerequisite_cycle_has_an_explicit_diagnostic`、`test_archived_requirement_basis_comes_from_saved_evidence_scope` 證實兩個失敗（同次其餘 5 passed、28 deselected，5.20 秒）；修正後明示循環並從已保存證據範圍讀歷史依據，完整 35 個摘要案例通過。

以上是工具輸出與流程設計缺陷，不是因 agent 記錯或跳步驟而新增限制。

## 3. 自動化、PDF 與跨平台結果

- 文件與協作規範相關回歸：107 passed，12.46 秒，Windows 本機；未修改測試來迎合文件變更。
- 工作摘要測試角色回歸：初輪 31 passed，18.07 秒；追加邊界後 Windows 摘要 35 passed，20.97 秒，Linux 摘要加簽收及 roadmap 共 50 passed，21.48 秒。最終完整回歸以完成時的 JUnit 數量為準。
- Windows 最終完整回歸：Windows 11（10.0.26200）、Python 3.12.13，1433 passed、1 skipped，382.22 秒，exit 0；已納入追加後的 35 個摘要案例。初輪為 1422 passed、1 skipped，401.52 秒，收集時摘要只有 24 案，保留為過程結果，不混當最終。
- Linux 最終完整回歸：WSL Ubuntu 24.04、Python 3.12.3，1433 passed、1 skipped，438.11 秒，exit 0；已包含 35 個摘要案例。初輪為 1422 passed、1 skipped，461.55 秒，保留為過程結果。
- Linux PDF：83 passed、0 skipped，15.59 秒（`tests/test_export.py`、`tests/test_proof.py`）。官方字型 ZIP checksum 與鎖定值不符，正常 setup 拒絕安裝；改走既有 `DOCSPEC_FONTS_SRC` 離線路徑，從 Windows 受控工具鏈複製缺少的 TW-Sung 字型，未改 manifest、產品碼或測試斷言。這不代表官方下載路徑通過，詳見下方安裝證據。
- Windows PDF：最終完整回歸 JUnit 中 `tests.test_export` 75 案與 `tests.test_proof` 8 案，共 83 passed、0 skipped、0 failed；另有 export_dx 32 案不混算指定的 PDF／proof 範圍。初輪相同範圍也是 83 passed。
- OpenSpec strict validation：6 passed、0 failed。格式及契約檢查不能取代行為驗證。

完整回歸需保留必要證據、角色分離、明確授權、文件／軟體互不阻擋等既有正反情境。查詢測試需核對文字與 JSON 的來源、識別碼及原因一致，並確認讀取前後受管理檔案不變、不呼叫測試執行器、不刷新狀態。

Windows 最終 JUnit 為 `TEMP/docspec-summary-windows-final.xml`，Linux 為 `/home/dennis/.cache/docspec-workflow-validation/summary-linux-final.xml`；獨立解析兩份各 1434 個案例，其中各 1433 通過，指定 PDF／proof 範圍各 83 通過、無略過或失敗。兩平台唯一略過均為 `tests.test_fail_loud_batch::test_group_yaml_malformed_warns_not_silent`：舊 group.yaml render 警告路徑已淘汰，由 store check 測試涵蓋現行檢查；不是缺少 PDF／排版工具造成的略過。

Linux 工具鏈為 WSL Ubuntu 24.04 x86_64、Python 3.12.3、Typst 0.15.0、Pandoc 3.10、19 個字型與既有受控 TinyTeX。`TEMP/docspec-linux-toolchain-report.json` 保留安裝及 PDF 結果。官方 `Fonts_Sung.zip` 期待 SHA256 `25cb90ddf7c98bfeebd9e88a79c63dcde7eaaf81409a15b323ace744bade7867`，實得 `8212daab91a32f8c1ccc8ebc69d272df33780e8928210bf858f201241fc6afa5`；舊 ZIP 無法取得。離線 `TW-Sung-98_1.ttf` 為 35,320,040 bytes，來源與目的檔 SHA256 同為 `9a3b74fe1a69fe1b3470b5ed780bf678c42a25cef93a13f280a5f31f795f0c56`。這證明既有受控字型複製一致，未證明新下載 ZIP 正確；線上安裝的 pinned hash 不符仍是已知限制。

## 4. 四份全新 agent 接手實測

本批要求 Windows 與 Linux 各兩份正常／過時的隔離合成專案。案例在接手前建立 facts、build-log 與 managed-before 清單，評分資料置於案例外，接手者不讀答案或前一段對話。

- Windows 案例根：`TEMP/docspec-e11-summary-cases/run-20260930-201323-371365`。
- Linux 案例根：`/home/dennis/.cache/docspec-workflow-validation/e11-summary-cases/run-20260930-201332-728571`。
- Windows 接手：兩份全新 agent 均完成且 exit 0；以下事實已由獨立審查核對，不只採信最終回覆。正常案先 roadmap 找 W-gpt-1，再查 summary，辨識有效 D-gpt-1／RL-gpt-1、未簽收 T1、零證據與 not-started；過時案辨識 D-gpt-2 取代 D-gpt-1、原引用與 S-gpt-1 保留、T1 簽收有效但 E-gpt-2 最新失敗、文件已寫且未定版。兩案均沿用既有工作，在盤點後才改寫交接，沒有代簽、執行測試或冒稱完成。
- Linux 接手：Linux 本機 agent CLI 未登入；採用全新 Windows agent 作 controller，只透過 WSL 操作 Linux 專案與 Linux docspec／Python。首輪兩案在讀寫前遭 `Wsl/Service/E_ACCESSDENIED`，保留為 controller sandbox／harness 環境失敗；之後重新開兩個 ephemeral controller，以較寬啟動權限重跑完成。獨立核對所有完成指令均經 WSL 操作指定案例，未讀案外答案。這可驗證 Linux 專案與 CLI 的執行行為，不能宣稱已測試 Linux 原生 controller、登入整合或原 sandbox 設定。

每案獨立核對：使用既有工作而不重複建立；辨識有效決策、原引用與取代來源；正常案辨識未簽收與零證據，過時案辨識最新失敗及未定版文件；保留問題識別碼與原因；原始資料不能因摘要而被自動套用或修改；依授權盤點後才整份重寫交接，且不能偽稱完成。

Windows 兩案與 Linux 重跑兩案核心接手條件 PASS。依 managed-before 清單對 docspec/**、docs/** 的逐檔指紋核對，四案唯一改變皆為 handover.yaml；合成程式與測試來源另比對未改。各平台 W 數仍為正常案 1／過時案 2，證據數仍為 0／2；獨立讀回四份新交接均 current、changes=[]。正常案任務仍 not-started，Linux agent 也核實文件尚未寫出；過時案任務仍 in-progress，最新失敗、未解疑點及未定版文件均保留，沒有被宣稱完成。未實際執行定版，不把跨領域定版操作算作 E11 已驗證。

Windows 查詢成本：正常案 20 次 shell、18 次 docspec（含 4 次 help、1 次交接寫入），summary 查詢 1 次；過時案 22 次 shell、18 次 docspec（含 1 次 help、1 次交接寫入），summary 查詢 3 次。扣除 help 與寫入後，唯讀 docspec 呼叫分別為 13／16 次。前批對照為 43／45 次 shell、37／38 次 docspec；這是觀察到的下降，沒有控制全部因素，不能保證固定節省比例。必要的需求版本及文件正文核對仍須回原始來源。

Linux 查詢成本：正常案 34 次 shell、26 次 docspec（含 9 次 help、1 次交接寫入），summary 查詢 3 次；過時案 27 次 shell、25 次 docspec（含 6 次 help、1 次交接寫入），summary 查詢 4 次。扣除 help 與寫入後，唯讀 docspec 呼叫分別為 16／18 次。沒有 Linux 前版受控對照，不推論固定節省。兩平台都支持集中現況後按需讀來源，尚不能宣稱一個指令即可判斷所有語意。

另外計算「首次 summary 之後，回原始紀錄的唯讀 docspec 查詢」，排除 help、roadmap、handover 與目錄探索；重複讀取算次數，失敗嘗試另標明。Windows 正常案 9 次、7 類來源（裁定、決策、change、spec、測試、證據、任務）；Windows 過時案 10 次，其中 1 次 get 被拒絕，涉及 6 類（裁定、決策、change、spec、證據、文件）。Linux 正常案 10 次、8 類，Linux 過時案 11 次、8 類（前述七類加文件）。此外直接讀原始檔的 shell 呼叫，四案依 Windows 正常／過時、Linux 正常／過時為 0／2／2／1 次，分別讀 0／2／5／4 個檔案；這些不混入 docspec 來源跳轉數。摘要降低尋找線索的成本，但本輪接手者仍核對多類來源，不能把「總 shell 次數」直接稱為來源跳轉或保證一頁知全況。

Windows 過時案一次 get 少填類型被正常拒絕，兩案各重讀一次 UTF8 AGENTS；Linux 兩案誤用 `code tasks` 被拒絕後改為 `code task`，正常案另遇缺少 rg 與探索尚未存在的 docs 目錄。分別記為 agent 探索、讀取編碼及環境工具缺漏，不新增產品阻擋。Windows 詳細報告及結構化核對存於案例根的 independent-review.md／independent-observations.json；Linux 觀測資料存於 Linux 案例根，完整事件及獨立報告存於 `TEMP/docspec-linux-summary-agent-eval/`，保留首輪與 retry，不把首輪失敗改記成功。

## 5. 重跑方式、限制與證據

合成案例由 `scripts/validation/build_handover_cases.py` 建立；每次使用新目錄，原始證據留在案外，不納入使用者真實資料。機械回歸可由 CI 執行；全新 agent 接手在流程修改或發布前由人啟動，不把付費 agent 執行列為每次 CI 的必要自動流程。

完整回歸在 repo 根設定 `PYTHONPATH=src`、`PYTHONUTF8=1`，執行 `python -m pytest -q -p no:cacheprovider --tb=short -ra --junitxml=<案外結果檔>`；Windows 使用 uv 臨時依賴環境，包含 pytest、pyyaml、questionary、platformdirs、pdfplumber、pypdfium2。接手案例另外使用持久環境，避免證據保存的 Python 路徑隨臨時環境刪除：Windows E11 為 `TEMP/docspec-e11-fixtures/.venv/Scripts/python.exe`（獨立查證 3.12.13），Linux 為 `/home/dennis/.cache/docspec-workflow-validation/venv/bin/python`（3.12.3）。這些環境分開記錄，不以一個環境的結果代稱另一個環境。

上述結果分開說明 Windows／Linux 的 Python、作業系統、完整回歸與 PDF 結果、controller/runtime 差別、未執行的路徑及失敗後採取的替代方式。本次未執行遠端 CI matrix，不把本機成功代稱遠端通過，也不把四個合成成功案例當成所有 agent 的可靠性保證。

本次不開 PR、不推送、不改 main；保留既有未提交成果。工作摘要的查詢結果不會取代治理來源，也不代表原本 SR16 的任意欄位查詢或固定兩千字限制已完整實現。
