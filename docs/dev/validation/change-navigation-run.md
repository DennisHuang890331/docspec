# 共用 change 與 ArtiSpec 命名驗證

日期：2026/09/30～2026/10/01。分支 `claude/software-domain-redesign`；保留既有未提交成果，沒有提交、推送、PR 或 main 改動。所有案例為合成資料，實測資料留在 repo 外。

## 1. 實作範圍

新增 `artispec` 執行入口，保留 `docspec` 別名；安裝套件仍為 docspec、Python 套件仍為 dspx、管理目錄與 corpus 不改。主要介面、生成 AGENTS 及九個 skills 使用新指令，skills 版本提高；部分既有子指令提示仍使用可用的 docspec 別名，不宣稱所有歷史文字已改名。

新文件與軟體 change 共用 `docspec/changes/`。文件仍用 change.yaml／notes.md／staging／preview，軟體仍用 proposal／design／specs／tests／tasks；原啟動時機、建立指令與完成條件保留。文件 targets 沒改成軟體 tasks，文件沒有新增必填軟體四件套。

`artispec change [--all] [--json]` 預設列現行兩域變更；`change show <id> [--json]` 提供領域細節、判定及來源。JSON schema-version 為 1，文字與 JSON 共用結果。歷史只讀保存結果；未完成仍可正常查詢，損壞、缺失或重複則報錯。查詢不執行測試、不刷新任務、不寫交接、不搬移。

舊 software/changes 含歷史仍可讀取、修改及正常封存。明確 `change migrate --dry-run`／`change migrate` 才搬移容器；全批先檢查身分、路徑及封條，保持檔案 bytes，中途失敗回復已搬項目。其他軟體資料及歷史基線全文不跟著改寫。正常封存從實際來源位置搬入共用歷史，乾跑只在記憶體推導，實際封存交易才保存任務結果。

## 2. 測試與獨立審查

測試角色先建立 17 個共用契約，修前 12 failed、5 passed；失敗項目是尚未實作的共用路徑、查詢及遷移，保留文件格式與跨域名字約束原本已有。安全測試另擴充至 63 組，品牌新增 8 組；既有品牌測試只更新真實介面預期，保留路徑、舊管理標記與行為斷言。

案例涵蓋新舊路徑、現行與歷史、未簽收與最新失敗、文字／JSON、一律唯讀、封條破損、名字保留、匯入全批碰撞預檢、遷移不變與回復、hook 寫入保護、交接 unknown，以及 archive dry-run。原本文件定版與軟體證據的獨立完成規則由完整回歸保留。

獨立來源審查用隔離 temp 重現三個原案例未覆蓋的流程漏洞，之後已補修並建立案例：

- hook 原先只認絕對路徑，cwd 位於共用 change 內時的相對 tasks.yaml 會漏擋；現在依 cwd 正規化，文件 staging 仍可編輯。
- 現行副本與不同日期的歷史副本同 ID，查詢會拒絕，封存原先仍選現行副本；現在共用與領域封存／乾跑都拒絕重複。
- 非法 ID 可解析到管理目錄外；現在檢查 kebab-case、紀錄 ID 與實際路徑範圍，封存不能搬動外部資料。合成案例包含正斜線、反斜線、nested、absolute 及實際目錄連結。

這些是工具流程缺陷；沒有為 agent 的語文或忽略規則加入新限制。

## 3. Windows／Linux 最終回歸

- Windows：Python 3.12.13、Windows 11；**1521 passed、1 skipped，439.18 秒**。JUnit：`C:/Users/zxc22/AppData/Local/Temp/artispec-windows-final.xml`。
- Linux：WSL Ubuntu 24.04、Python 3.12.3；**1521 passed、1 skipped，527.83 秒**。JUnit：`/home/dennis/.cache/docspec-workflow-validation/artispec-linux-final.xml`。
- 兩平台 `test_export.py` 與 `test_proof.py` 各 **83 passed、0 skipped**，包含實際 PDF／proof；不把 test_export_dx 的其他機械案例混進這個數字。
- 唯一 skip 是早已退役的散檔 group.yaml warning 情境，仍由 store check 案例涵蓋；沒有為消除 skip 放寬測試。
- OpenSpec `validate --all --strict`：**8 passed、0 failed**；git diff --check 通過。

兩平台均用持久使用者環境執行 `python -m pytest -q -p no:cacheprovider --tb=short -ra --junitxml=<案外檔>`，設定 PYTHONPATH=src、PYTHONUTF8=1。沿用既有受控 Typst、pandoc、字型與 PDF 環境；本批沒有重新宣稱線上字型下載成功。Windows 初輪持久環境缺少 PDF 驗證套件，已安裝 pdfplumber／pypdfium2 後重跑；未把原失敗算通過。

初輪 XML 保留為 artispec-windows-full.xml／artispec-linux-full.xml：Windows 17 failed、1464 passed、10 skipped，Linux 12 failed、1478 passed、1 skipped。這輪尚在同步舊品牌斷言，Windows 還缺 PDF 驗證依賴；使用完成修正後的最終結果驗收，原失敗不刪除。

最終 wheel 為案外 `artispec-final-wheel/docspec-0.1.0-py3-none-any.whl`；Windows 隔離安裝與 Linux 使用者 cache target 安裝後，artispec／docspec 兩入口皆實際成功讀取合成軟體與文件 change。安裝索引名稱仍是 docspec。本批未執行遠端 CI，不把本機兩平台結果代稱遠端通過。

## 4. 四次全新 agent 接手

使用 `scripts/validation/build_change_navigation_cases.py`，延伸既有 builder，每次建立新隔離目錄。正常及過時案都加入文件 change，讓接手者實際從共用查詢找到兩域。答案及受管理內容指紋放案外；參與者只獲同一任務說明、案例位置及啟動方式，沒有前文或事實答案。

- Windows 根：`C:/Users/zxc22/AppData/Local/Temp/artispec-change-cases/run-20260930-235831-172577`。
- Linux 根：`/home/dennis/.cache/docspec-workflow-validation/artispec-change-cases/run-20260930-235840-770624`。

兩平台的正常／過時案均通過獨立核心核對。正常案辨識既有 W1、有效 D1／RL1、未簽 T1、零證據、文件未寫與未定版；過時案辨識 D2／RL2 的取代關係、原引用及 S1、有效簽收但 E2 最新失敗勝過相同範圍的 E1 通過，以及正文 written／synced／unfrozen 與 change preview stale-own 的差別。兩域容器格式與各自完成條件都保留。

四案都沿用既有工作，盤點後只重寫 handover。獨立逐檔核對正常案 18 檔、過時案 28 檔：受管理檔案唯一變更是 handover.yaml，沒有新增／刪除；工作、來源、測試、證據、程式與 runtime input 保留。新交接皆 freshness=current、changes=[]；軟體未完成與文件未定版沒有被改寫成完成。

Linux 參與者為全新 Windows controller，全部經 WSL 操作 Linux 專案與 Linux CLI；可以驗證 Linux runtime 的接手流程，不能宣稱 Linux 原生 controller／登入整合通過。

參與者自報唯讀呼叫依 Windows 正常／過時、Linux 正常／過時為 18／17／10／12 次，交接寫入為 2／1／2／1 次；其中兩次寫入是繁體用字校正。缺少可供獨立重播的 participant transcript，這些次數只作自報觀測，不作嚴格成本對照或節省比例結論。

Windows 參與者首次讀 AGENTS 用預設 PowerShell 解碼而亂碼，改 UTF-8 已解決。審查者另遇自身巢狀 Python cp950 輸出問題，改 UTF-8 後成功；分別記為環境問題。Windows 過時交接有少量簡體字、兩案把主規格稱為「已封存規格」而未證明確有封存；Linux 過時交接缺 in-progress 欄，但 next 保留兩工作。這些列 agent 文案／交接表現，不算本批工具流程漏洞。

本次 facts 中早期 roadmap／work-summary 快照在加入文件 change 連結前生成，後加的 changes 與 managed-before 才是本次兩域基準；獨立審查依建立順序區分，未誤判成參與者改動。未來 builder 已把 roadmap／summary 同步到擴充後再保存；沒有事後覆寫本次答案。核對腳本初版因誤讀 manifest 子欄及漏用 docs_layout 設定而報錯，修正後兩平台機械核對通過，屬案外 harness 錯誤。

獨立評分及機械讀回保存於各 run 案外 independent-review.md／independent-review.json／post-handover-check.json。本批沒有從自報查詢次數推導工具可降低固定比例用量。

## 5. 操作方式

接手先讀 handover 與 roadmap，以 roadmap show 找工作的完整相關現況；需要看修改容器時用 change／change show。文件與軟體的建立、實作及驗收仍走原領域流程。舊資料不必立即搬移；只有明確需要整理位置時才 dry-run 並 migrate。定版仍由負責人明確要求，追溯提醒不改成新的完成門檻。
