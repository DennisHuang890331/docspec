# 現行規則、過時原因與 E11 交接驗證

日期：2026/09/30。分支：`claude/software-domain-redesign`。對應 OpenSpec changes：`align-current-workflow`、`explain-stale-state`、`validate-agent-handover`。本報告只使用合成案例；前次 `fix-workflow-integrity` 成果保留，見 `workflow-integrity-run.md`。

## 1. 修改與判定邊界

- 依後續明確裁定整理 SR2、SR8、SR11、SR21、分期與驗收；保留歷史原文並標明取代，不能用同日排列猜測先後。正文採不清楚才覆述、交接整份重寫、追溯提醒非阻擋、完成須有效證據；產品並行寫入與 S6 取消，base fingerprint 保留。
- 提案 skill 升為 1.2，生成中英 AGENTS 規則先查操作人、平台、啟動、安裝、連線與交付限制；已有資料引用，缺漏且影響設計才詢問。沿用既有資訊／裁定，不新增必填表單。SR16 明示仍有未實現目標，工作摘要本批不新增。
- Windows 與 Linux 都是產品支援平台。以下分開記錄自動化測試、跨平台合成建案，以及只在 Windows 跑過的全新 agent 行為實測，不能互相代稱。
- 交接由同次受管理檔案讀取產生原本的整體指紋及 `state-manifest={version:1,files:{相對路徑:sha256}}`。`state-version=1` 與 aggregate 算法不變；只保存路徑／hash，不複製全文、不掃整個外部 repo、不保存追加歷史。
- `freshness` 附加 `changes-available`、`changes`（path、kind）與 `changes-reason`。文字與 JSON 共用明細；無有效 manifest 的舊單仍依整體指紋判定，不能臆測明細。不可讀／封條損壞回 unknown。獨立 review 找到「沒有交接單時文字漏報損壞治理」的 P2，已修正並有正反回歸。
- 軟體證據 `why`／roadmap `details` 指出 requirements、scenario、based-on、tests、methods、runners、files 等差異與識別碼；不完整或不相容舊 scope 保留一般補驗證提示。診斷不改效力、不執行測試、不重簽。
- E11 發現 `code testplan list` 文字不顯示簽收狀態。已補 unsigned／current／needs-review／unknown，沿用 signoff_problems；JSON 保留原欄位並附加 `signoffs=[{test,status,problems}]`。沒有新增指令或放寬簽收門檻。

## 2. 自動化驗證

測試角色與實作者分開；先跑出修前失敗，再實作。

- 第一批診斷基線：16 failed、2 passed，8.20 秒。失敗是缺少 manifest／changes 與 scope 原因不具體。
- 擴充後 `test_stale_diagnostics.py` 共 44 項：新增／修改／刪除、舊格式、無效清單、不可讀、單次 checked read、唯讀、mtime／外部檔案不誤觸、scope 增刪／取代、缺欄位退回一般原因、生成規範更新等。
- 44 項加既有 workflow 回歸：122 passed，60.98 秒；init／skills 原有回歸另 63 passed。
- E11 輸出修正先跑出 8 failed，2.90 秒；實作後 8 passed，3.15 秒。涵蓋同一列表不同簽收狀態、測試／情境改變、legacy、不可讀，以及同檔其他測試變動不影響此測試。每例檢查文字／JSON 一致、原欄位相容、不寫紀錄、不呼叫 subprocess。
- Windows 第一輪完整測試：1390 passed、1 skipped，359.37 秒（E11 簽收列表小修之前）。Python 3.12.13。
- Windows 最終完整測試：1398 passed、1 skipped，344.37 秒，包含簽收列表新增 8 項；唯一略過是原本已退役的散檔 group.yaml 警告路徑。
- Ubuntu 24.04 WSL、Python 3.12.3：相關六檔 185 passed，111.18 秒（E11 簽收列表小修之前）。
- Linux 首輪完整測試：1378 passed、13 skipped，396.68 秒；收集案例在簽收列表小修之前，故另外重跑最後版本。13 個略過為 12 個缺受控 Typst／字型或 pandoc 的 PDF／proof 測試，以及 1 個既有退役路徑，沒有新加 skip。
- Linux 最終完整測試：1386 passed、13 skipped，379.41 秒，包含簽收列表新增 8 項；略過原因與首輪相同。兩平台本次新增的 52 項診斷／簽收列表案例皆執行通過。

OpenSpec 四份 change（含前次修復）`validate --all --strict`：4 passed、0 failed；`git diff --check` 通過。

完整回歸保留「缺追溯依據只提醒」、「必要證據不能省略」、「軟體錯誤不擋文件定版」等既有正反情境。OpenSpec strict validation 檢查格式與契約，不能取代行為驗證。

## 3. E11 方法、預先事實與結果

使用兩份隔離合成專案，各以全新 `codex exec --ephemeral` 開始，沒有 resume 或前文。提示只提供各自專案位置、CLI 入口、一般接手盤點及重寫交接的任務；不提供答案。要求只查專案內資料，評分清單與建置紀錄放在兩案外。

建置者先建立 `facts.json` 與 CLI build-log，再交接；獨立審查者交叉核對事件、最終回覆及實際讀回紀錄，未只採信 agent 自稱完成。

正常案例預先條件：已有 W-gpt-1 與 improve-entry change，T1 未簽收、任務 not-started、沒有證據；交接 current。結果：找到 RL-gpt-1／D-gpt-1、既有工作及未簽收測試；下一步為測試角色審查簽收後實作與驗證。沒有重複工作或代簽，重寫後交接經獨立讀回為 current。

過時案例預先條件：D-gpt-2 明確取代 D-gpt-1；E-gpt-1 pass 後 E-gpt-2 fail，兩筆 scope 與宣告檔案指紋相同；文件已寫、render 同步但未定版；原交接 stale。結果：辨識新決策、最新失敗、S-gpt-1 待處理與文件未定版；保留 W-gpt-1／W-gpt-2，沒有用舊 pass 宣稱完成。重寫後交接經獨立讀回為 current，軟體任務仍 in-progress。

兩案核心接手條件通過。測試源碼、實作、正式規格、delta 與測試計畫均由獨立審查比對未改；既有證據數不變，沒有定版或封存。未逐位元比對整棵目錄，不擴大宣稱完全沒有其他檔案活動。

兩位接手者也辨識合成測試只檢查 runtime 輸入是否 ready，不能證明畫面行為。這是刻意簡化的驗證載體，不把其 pass 當作真實產品正確的證明。

本次實測沒有執行文件定版，不能把「軟體失敗仍可文件定版」算作 E11 操作驗證；該規則由既有自動化回歸涵蓋。兩個成功案例也不代表所有 agent 都能正確接手。

## 4. 發現的分類

- **工具輸出缺漏，已修**：未簽收與已簽收的 testplan 文字相同，正常案 agent 必須讀原始 tests.yaml；現在既有指令直接顯示簽收效力，8 個新增回歸驗證。
  - 修後也在原 E11 兩案讀回原指令：正常案顯示 `T1 sign-off: unsigned` 及待簽收原因；過時案顯示 `T1 sign-off: current`。測試簽收有效與執行結果失敗可以同時存在，不能混為功能完成。
- **可改善的讀取成本，僅提案**：要拼合 handover、roadmap、decision/ruling、change/spec/task、testplan、evidence；過時案另讀 impact/trace 與文件來源。現有工具取得得到，問題是資訊分散。
- **agent 表現，不加阻擋**：兩案各有指令探索錯誤，例如 audit list；兩者也把大量現況抄進交接 cautions/done。既有規則已說明來源與用途，不能把這些全部歸為工具錯誤或新增強制門檻。
- **實測環境，已修入口**：首次兩案都因 PowerShell 不允許執行 PS1 停止，中文 stdin 也轉成問號；未進入產品盤點。保留失敗紀錄，不算產品驗收通過或產品邏輯失敗。改成 CMD 入口與可讀提示後，用全新專案與會話重跑，未變更機器 ExecutionPolicy。

## 5. 工作摘要的下一批建議（未實作）

正常案觀察到 43 次 shell 命令，其中 37 次呼叫 docspec、10 次查 help；過時案為 45 次、38 次、8 次。這是實際總成本，含重讀、help 與探索錯誤，不是必要最小次數。

建議後續只做「指定既有工作項的唯讀摘要」：沿其 refs 列目前有效決策與取代來源、相關任務／測試簽收、最新證據原因、文件撰寫／定版狀態，附原始紀錄入口。保留完整範圍驗證，摘要省略不等於義務消失。先用這兩案評估能否減少來源跳轉，再裁定介面與讀取預算；本批沒有新增該介面。

參考 OpenSpec 時採用責任劃分，不複製另一套紀錄：[Work 實驗](https://github.com/Fission-AI/OpenSpec/blob/main/openspec/work/README.md) 將目標、路徑、工作與結果分開，仍非完整 CLI 生命週期；[交接提案](https://github.com/Fission-AI/OpenSpec/blob/main/openspec/initiatives/context-store-and-initiatives/work-items/13-agent-handoff-output-and-delivery-polish/plan.md) 明確延後，提醒提供現況、來源與可採取行動，不強塞唯一 next command。本次沿用 docspec 既有 roadmap、change、證據與 handover，沒有引入 goal／slice／result 的重複帳本。

兩份新交接文字約 1,926 與 2,000 個序列化字元（不含 manifest），不是精準中文字數，也不能宣稱達成 SR16。限制長度時不能截掉必要原因。

## 6. 重跑與原始證據

完整測試在 repo 根目錄、已安裝 pytest、pyyaml、questionary、platformdirs、pdfplumber、pypdfium2 的 Python 環境執行。Windows PowerShell：

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
$env:PYTHONUTF8 = '1'
python -m pytest -q -p no:cacheprovider --tb=short -ra
```

Linux shell：

```sh
PYTHONPATH="$PWD/src" PYTHONUTF8=1 python -m pytest -q -p no:cacheprovider --tb=short -ra
```

PDF／proof 另需受控排版工具及字型；測試的 skip 原因須保留在結果，不能自行改測試來消除略過。

可重跑腳本：`scripts/validation/build_handover_cases.py`。需要持久 Python 環境與 pytest、pyyaml、questionary、platformdirs；不要用程序結束即刪除的環境，因為 evidence runner 會保留 Python 路徑。

```text
<持久環境的 Python> scripts/validation/build_handover_cases.py --output-dir <暫存目錄>/e11
```

腳本每次建立新 run-*，不覆寫或刪舊案；產生共用 run-docspec.py、Windows CMD／可選 PS1、Linux shell 入口。facts、factcheck、build-log 與 setup 在案外，禁止提供給接手者。腳本內的前置 assert 通過只代表案例成立，不等於完成 agent 實測。

跨平台建置已實跑：Windows 原生 Python 與 CMD 入口正常；Ubuntu WSL 建案所有前置 assert 通過，再從兩案分別執行 Linux Python／shell 入口，確認交接 current／stale 以及簽收 unsigned／current 均正確。Linux 只驗建案與 CLI，沒有宣稱已執行全新 agent 接手。

本機原始記錄保留於 TEMP/docspec-e11-fixtures：首次環境失敗 run-20260930-174813-821839；成功接手 run-20260930-175117-573688。後者含 facts、build-log、兩份 events.jsonl／result.md、independent-review.md 與 independent-observations.json。原始事件未加入 repo；repo 只保存合成建置腳本與整理後報告。

未開 PR、未推送、未修改 main；既有工作區成果保留。遠端 CI 尚未執行，本機測試不得代稱遠端 matrix 全數通過。
