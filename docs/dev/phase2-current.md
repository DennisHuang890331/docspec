# 第二期現行設計：軟體領域（取代 OpenSpec）

- 這是第二期的**現行版**，整合了 `phase2-design.md`（架構）、`phase2-detail.md`（細部設計與歷次裁定）、`phase2-review.md`（review 與修正）。三份舊檔保留作討論過程；內容有出入時以本檔為準。
- 更新：2026/10/07（最新核定使用 `dev` 開發、安裝套件及使用者工具資料改為 `artispec`，安全升級後整理提交／推送；同題完整流程仍未完成）。第二期已驗收，歷史文件中的等待驗收與並行規劃不代表現行待辦；同日條目的先後須依明確取代關係判斷，不按排列位置猜測。
- 本次命名與升級依[最新裁定](system-design.md#開發分支安裝套件與工具資料升級20261007)，取代安裝名保留 `docspec`、舊分支及不提交／不推送限制；不動 main、不開 PR。README 只修此次安裝／升級資訊，定稿及自用開發切換仍待後續處理；兩個同題案例尚未初版接受／封存、容量變更或新會話接手，roadmap unlink 仍待裁定，個別 change 驗證完成也不算整體 workflow passed。
- 本批最終回歸（2026/10/07）：Windows **2135 passed／1 skipped**、實際 WSL Linux **2132 passed／4 skipped**，各收集 2136 項、0 failed／0 error；已核原退出碼及 XML，276 個 src／tests／pyproject／lock 檔前後 bytes 相同。Windows Python 3.12.13、Linux Python 3.12.3；skip 為既有退役 warning 案，Linux 另三個 Windows junction 案，PDF／proof 無 skip。四個新 wheel 乾淨／升級情境合計 50 命令、88 項核對及 696 次套件檔案比對通過；Windows 23,620／Linux 20,751 個受管工具檔明確遷移且舊來源保留。本機全域 uv tool 已更換為 `artispec v0.1.0`、只提供 `artispec` 入口，原 `docspec` tool 環境已移除；實際全域 doctor／deep 中文一頁實編與 16 個套件的 pip check 均 exit0，舊工具資料及 2026/10/06 wheel 備份保留。執行期依賴使用 repo lock 匯出的 constraints，與回歸環境一致。共用新 wheel、提交與遠端 `dev` 推送仍待完成。完整流程驗收仍保留上述未完成項目，實際收據與限制見[本批報告](validation/installation-upgrade-run.md)。
- 前輪現況（2026/10/04）：補正工作摘要來源提示後，Windows 2096 passed／1 skipped、實際 WSL Linux 2093 passed／4 skipped，新候選 wheel 兩平台已獨立安裝核對，見[提示修正](validation/summary-source-commands-run.md)。兩個同題案例仍未完成初版交付、唯一變更或新會話接手；Windows 定版被錯誤工作引用阻擋，合法恢復方案待裁定。Windows 成品已真雙擊、匯入 16 人、安排 R1、輸出兩房 HTML，並原生列印兩份一頁橫式 PDF，root 與另一角色均親閱，53 項獨立核對及直接讀 PDF 通過。Linux 原包已在 Windows 私有 Chrome154 真匯入、排座、下載 HTML 與另存兩頁橫式 PDF，通過獨立審查；新版手冊 1.0.1 及 ZIP 已完成，停止點／包／歷史的獨立核對已通過，新包 GUI 不直接算通過。Explorer 預設關聯兩次停在控制器守衛，正式交付仍待核。下列 2026/10/03 所述 F2／文件預設尚待核定與未實作，是當時狀態，已被 2026/10/04 明確授權及上述實作取代；詳見[本輪紀錄](validation/workflow-alignment-run.md)。README 與自用開發遷移在該輪未動。
- 本次規則整理、過時原因與 E11 的驗證紀錄見 `validation/workflow-handover-run.md`；Windows／Linux 的實際覆蓋分開列出。
- 2026/10/01：ArtiSpec 對外命名與共用 change 已實作；兩平台最終完整回歸各 1521 passed、1 skipped，PDF／proof 各 83 passed。四份全新接手核心核對通過，Linux 為 Windows controller／WSL runtime；詳細相容性、失敗紀錄與限制見 [共用 change 驗證](validation/change-navigation-run.md)。
- 2026/10/01 後續明確裁定：本輪移除 `docspec` 相容入口，僅提供 `artispec`；README 補齊本機來源／wheel 安裝、共同查詢、文件與軟體流程、舊專案刷新與獨立搬移說明。以 `retire-docspec-command`、`validate-readme-workflows` 管理。先前四案及 1521 項回歸是前輪結果；本輪六案與兩平台驗證另行記錄，未執行前不宣稱通過。
- 移除相容入口那輪的最終完整回歸 Windows／Linux 各 1617 passed、1 skipped，PDF／proof 加程式區塊座標各 86 passed、0 skipped；最終 wheel 乾淨／升級與 hook 各 64 項機械檢查通過。六案已執行但未整體驗收；當時同工具獨立 agent 身分辨識缺口待裁定，後續已核定修正。原失敗與 oracle 衝突保留，見 [該輪驗證](validation/readme-workflows-run.md)。
- 2026/10/01 後續版本目錄 `relocate-document-versions` 已完成實作、獨立測試與 review；Windows 最終完整回歸 1729 passed、1 skipped，Linux 實際 WSL runtime 1726 passed、4 skipped（三個 Windows-only junction 加一個既有退役路徑）。兩平台 PDF／proof／程式區塊座標各 86 passed、0 skipped，最終 wheel 安裝／升級各 64 checks，實際已安裝 versions 查詢／搬移各 9 checks 通過。詳見 [版本儲存驗證](validation/document-version-storage-run.md)；不回填前輪六案全新 agent 未通過項目。
- 同工具不同會話修正已完成：Windows 完整回歸 1803 passed、1 skipped；實際 WSL Linux 1800 passed、4 skipped。兩平台各 34 項已安裝 CLI 檢查通過，真正獨立 Codex 測試會話也已完成考場案例簽收。這些結果不代稱考場初版、接手或第二次交付通過；詳見[身分修正報告](validation/agent-instance-identity-run.md)與[流程進度](validation/exam-seating-workflow-run.md)。
- 完整流程續測（2026/10/02）：兩案初版及一次容量變更均有獨立測試、引擎證據、實際 Windows GUI／Explorer 雙擊、指定 EXE 網路隔離、合成負責人接受與正式封存；兩份手冊各有 1.0.0／1.1.0、三頁 PDF／proof。無前文接手盤點與最終交接均已獨立核對，交接新鮮度 current，測試與歷史資料未改寫。inline delta 校驗修正完整回歸為 Windows 1874 passed、1 skipped，實際 WSL Linux 1871 passed、4 skipped，OpenSpec strict 14 passed。資訊引用造成 roadmap 狀態不準、preview 查核上下文等缺口先記錄後續處理，未判整體無缺陷通過；限制、失敗及來源見[完整流程報告](validation/exam-seating-workflow-run.md#11-第二次交付與最終核對20261002)。

## 1. 定位

2026/10/02 負責人已核定實測缺口第一批修正（`fix-workflow-review-gaps`）：roadmap 的 D／I 是背景依據，只有背景的工作不自動完成；相關失聯來源與取代循環由列表和摘要共用檢查。`get`／`instructions`／`find`／`check`／`diff` 預設正式內容，以明確 `--change <id>` 讀同一份正式加草稿來源，缺失或過時 preview 不改查正式舊文。摘要預設 JSON v2，原 v1 用 `--schema-version 1`，精簡的是重複簽收全文，不縮減有效決策或診斷。skills 與生成規範同步補明來源、歷史與驗收界線；實作與本輪驗證結果見[具體修正報告](validation/workflow-review-gaps-run.md)。尚未封存需求的文件引用 namespace（F2）保留為下一批提案，本輪不實作；先前實測歷史不回填。

第一批最終完整回歸：Windows 1976 passed／1 skipped，實際 WSL Linux 1973 passed／4 skipped；兩平台 PDF／proof／程式區塊座標各 86 passed／0 skipped，最終已安裝 wheel 的 102 個新行為案例各自通過。兩名無前文 agent 的合成 factcheck 核對達標；Linux 有一項路徑 substring 機械誤判保留原結果，由獨立來源核對說明，Windows 完整 shell history 不可取得。這些結果不代稱原考場或前輪六案重跑通過。

2026/10/03 的 `align-delivery-guidance` 修正文件封存 notes 提醒，提供可選理由及既有治理查詢，不再聲稱裁定空白或 Archiving anyway；原目標／漂移檢查與資料不變。propose／verify 1.6、生成規範 3 補齊實際交付包、平台／限制覆蓋及文件 latest 核對。兩平台相關回歸各 236 passed／0 skipped，安裝後各七個新案與九次 CLI 核對通過；完整套件、PDF 與 agent 完整流程未在這批重跑。限制及原始失敗另見[後續驗證](validation/delivery-guidance-run.md)，F2 仍是[未核定提案](proposals/draft-requirement-links.md)。

同日另以 `fix-guide-governance-contract` 補齊 schema 投影的治理來源舊指引：ruling／info 保存原話，notes 引用，不新增完成條件。兩平台相關回歸各 111 passed，新 wheel 已安裝入口各八次核對通過，見[guide 驗證](validation/guide-governance-run.md)。工程團隊定位已明確，具體[文件預設提案](proposals/engineering-document-style.md) 尚未實作；[修正後同題比較](proposals/repeat-exam-workflow.md) 保留原契約與歷史，尚未啟動。

產品支援 Windows 與 Linux（2026/09/30 使用者釐清）。本次 Windows E11 使用的啟動器只是實驗工具；Windows 的接手結果不代稱 Linux 驗收。完整測試與接手實測按實際平台分開報告，未執行的平台不宣稱通過。

對外工具名稱是 **ArtiSpec**，唯一可執行指令及安裝套件是 `artispec`；後續明確裁定取代前輪保留 `docspec` 相容入口與安裝名稱的安排。使用者工具 root 為 `platformdirs.user_data_dir('artispec', appauthor=False)`，Windows `%LOCALAPPDATA%\artispec`、Linux 通常 `~/.local/share/artispec`。Python 套件 `dspx`、專案內受管根目錄 `docspec/`、`corpus`、`DOCSPEC_*` 環境變數與既有管理標記名稱不改。下列現行操作範例使用新指令；第 10.1 節的實測歷史保留原拼法，歷史封條與證據不重寫。

安裝與驗收先使用目前來源或新 wheel，在隔離環境驗證後才更換既有 uv tool；repo 仍名為 `docspec`，`dev` 遠端來源只在推送後可用，不宣稱已公開發布 PyPI。`uv tool uninstall docspec` 只移除舊 tool 環境，以 direct wheel `[export]` 安裝 `artispec`。舊工具與字型由 `artispec setup --migrate-data` 明確離線複製，只含受管六目錄及 `tex.lock`／`update-cache.json`；未知 root 內容留舊處、來源作備份、目的衝突全批預檢拒絕、既有目的 `installers/` 保留，僅重指 `tex.lock` 已知根路徑。其餘 bytes 不變，也不移專案資料；相同內容重跑不修改。接著 doctor／deep，再在舊專案執行 `artispec init --agents-md --tool <實際工具>` 更新規範、skills 與本工具 hook；保留使用者設定與其他工具 hook，損壞設定須報錯。hook 解析 `artispec` 的絕對路徑，找不到時提示修正 PATH，不回退舊指令。新環境使用一般 setup。規範刷新與資料搬移是不同操作，詳細命令見 [操作指南](../user-guide.md)；本次 `align-artispec-installation` 實際驗證另見[安裝升級報告](validation/installation-upgrade-run.md)。

2026/10/01 後續 README 裁定：首頁改為短版入口，不出現舊名稱；完整安裝、兩域流程與升級說明移到操作指南。此次只驗證文字與連結，先前 wheel／六案紀錄保留，不宣稱短版 README 已重新通過 agent 實測。文件版本收 `changes/_versions/` 的具體方案已由使用者確認「可以你開始實作了嗎?」；此條取代先前尚待架構確認的狀態，設計與實作驗證狀態分開。

同工具不同 agent 的身分修正已核定（2026/10/01）：新測試／任務另記穩定會話碼，兩個不同 Codex 會話可以分工，不再僅因同為 gpt 而拒絕簽收。同會話不能自行簽收；作者修改、刪除、簽收與異議共用判定。舊缺碼紀錄保守處理，不回填歷史；此修正的回歸及完整考場流程分開驗收，未通過項目不可提前宣稱完成。

專案分三層：
- 最外層是治理層：問題、裁定、資訊、決策、唯一的 roadmap、可疑標記。
- 底下兩個平級的領域：文件樹（原本的 docspec）與軟體領域（本期）。
- 兩個領域保留自己的 change 格式、建立時機與完成判定，共用 change 目錄、唯讀總覽、治理層、追溯與影響分析。

軟體規格、設定、證據與基線放在 `docspec/software/`；新 change 放在共用的 `docspec/changes/`。受管紀錄是引擎擁有、各自封條的 YAML，只能透過領域指令寫入。唯一設定例外是 `docspec/software/config.yaml`，由人手寫，或用 `artispec code repo add <名稱> <路徑> [--test-command …]` 登記程式 repo（`code repo list` 顯示引擎實際會執行的指令）。`test-command` 只寫執行器，開頭可以帶環境變數（例如 `PYTHONPATH=src python -m pytest -q`）；測試位置由引擎接在最後，不接受 `{tests}` 這類佔位符。

Windows 路徑保留反斜線，含空白的執行器路徑須加雙引號；既有 POSIX 引號格式仍可使用。YAML 範例：`test-command: 'PYTHONPATH=src "C:\Tools\Python Env\python.exe" -m pytest -q'`。環境變數由引擎傳給子程序，不透過 shell 展開；沒有引號的含空白路徑會提示修正設定。

## 2. 目錄

```
docspec/
├─ corpus/                      文件來源，名稱不改
├─ changes/                     新文件與軟體 change 共用根目錄
│  ├─ <文件-change>/            change.yaml、notes.md、staging/、preview/，targets 不變
│  ├─ <軟體-change>/
│  │  ├─ proposal.yaml         為什麼改、改什麼、能力與前置 change
│  │  ├─ design.yaml           背景、目標、風險；以 gov:D-… 引用決策
│  │  ├─ specs/<能力>.yaml     差異與基準指紋
│  │  ├─ tests.yaml            測試規劃、簽收、異議（測試角色）
│  │  └─ tasks.yaml            任務與引擎判定的完成證據
│  ├─ _archive/                已封存 change，保留各領域原格式
│  ├─ _abandoned/              既有文件 change 放棄紀錄
│  └─ _versions/<article>/    文件版本專區，不是普通 change
│     ├─ history.md            此文章歷史唯一的新寫入位置
│     ├─ <version>/
│     │  ├─ snapshot/document.md
│     │  ├─ snapshot/assets/   當版受管圖資產，snapshot 整夾凍結
│     │  ├─ exports/           可再生，<article>_v<version>.<format>
│     │  └─ proof/             可再生，page_<N>.png
│     └─ _preview/             未定版的 exports/、proof/
│                              舊無版號 proof 另放文章根 _legacy-proof/
│                              register-legacy 放 _versions/_legacy/<name>/snapshot/
└─ software/
   ├─ config.yaml              repo／執行器等設定
   ├─ specs/<能力>.yaml        正式軟體規格
   ├─ evidence/E-<工具>-<n>.yaml
   ├─ baselines/<日期>-<change>.yaml
   └─ changes/                 舊位置相容（含 _archive），不自動搬移
```

先用 `artispec change` 看兩個領域進行中的變更，`--all` 包含歷史，再用 `artispec change show <id>` 看類型、來源與現況。共用查詢唯讀，不刷新任務、不執行測試、不改寫交接，也不搬檔。舊軟體 change 可留在原位置繼續操作；需搬移時先看 `artispec change migrate --dry-run`，再明確執行 `artispec change migrate`。搬移先檢查衝突、保持紀錄內容，只處理舊軟體 change 容器與歷史，不搬其他軟體資料。

列表與 show 都支援 `--json`，摘要使用 `schema-version: 1`，依 domain 區分 document／software，再保留各領域的 details。未完成是正常查詢結果；不存在、紀錄損壞或同編號出現多份容器則報錯，不挑其中一份。編號跨領域及活動／封存／放棄歷史保留；歷史 show 讀取封存內容，不依目前狀態重算歷史驗收。

建立入口仍分領域：文件 `artispec change new`、軟體 `artispec code change new`。文件的既有建立時機不變，targets 不改成 tasks，也不增加必填 proposal／design；軟體仍依需求、測試及任務證據完成。

### 文件版本：已實作並完成當輪驗證

- docs 留工作 latest、工作資產與既有 latest 匯出輸出；定版 Markdown 與當版實際引用的受管圖資產寫上述 snapshot。各版 exports/proof 可重生，不能改 snapshot；preview 不建立凍結版本。初次 freeze 不須新建 change。
- 本裁定明確取代 `docs/archive/`／`docs/revision_history/` 的新寫入位置；舊讀取 fallback 與舊防護仍有效。`docs_snapshot` 讀新或舊；同版兩份報錯，不選副本。`version_snapshot` 只寫新，`docs_changelog` 只寫文章根 history；freeze 遇尚未搬的舊 history 拒絕並提示 explicit migrate。
- `artispec versions [article] [--json]` 唯讀列版本與來源；`artispec versions migrate [article] --dry-run`／實跑明確搬移，all 預設。全批次先檢舊 `.freeze.yaml`／原 hash、目標與 history 碰撞、解析後路徑；乾跑不寫，失敗回復。只 rekey verified 原 manifest hash，快照 bytes／sealed baseline 原文、位置、封條均不改，不洗白。
- snapshot 整夾 hash/hook保護，新增、刪除、替換資產不合法；freeze只保存管理圖引用。新 snapshot 缺圖不 fallback current；舊圖來源缺漏列 unknown provenance／缺圖，不複製 current 造歷史。舊版及 preview export/proof 隔離，不能 prune 其他版本或 latest。
- 舊 Markdown 可原文搬移並保留缺歷史asset警告，export無當版圖資產就拒絕。舊無版號proof僅存文章根 `_legacy-proof/`，不猜版號。register-legacy任意歷史檔存 `_versions/_legacy/<name>/snapshot/`，不假成semver、不列文章版本號；舊 `docs/archive/legacy/` 仍讀，all明確搬移包含它。原hash verified rekey，不新增治理型別；`_legacy`／`_preview`／`_legacy-proof` 在各自位置保留，碰撞先拒絕。
- 普通 change與 `_archive`格式不變；版本樹不混入普通 change 查詢／封存。現有 sealed document／project baseline 留原處，唯讀查詢使用版本路徑解析，不改基線去追新路徑。

## 3. 規格

- 每個能力一份規格。需求編號 R1、R2…，情境編號 S1、S2…，編號永不重用（退役的記在 `retired`）。
- 需求的規範句必須含 SHALL 或 MUST，至少一個情境（WHEN／THEN）。
- 每條需求標明驗證方法，可以是 test、demonstration、inspection、analysis 其中之一或幾種。
- 情境的 `verified-by` 只列有效證據中真正通過的測試，在封存時由引擎寫入；豁免保留於任務及基線，不冒充測試通過。
- 查詢一次只取需要的部分：`artispec code spec show <能力> --req R1 --json`。

## 4. 一次修改的流程與角色

1. **提案（dspx-propose）**：`code change new` → `code change design` → `code change delta`（一次一筆，例如只改 R1/S2 的 THEN）→ `code task add`（每條改到的需求都要有任務實作）。
   - 先查現有資訊、裁定與需求，確認誰操作、平台、啟動方式、安裝限制、連線限制與交付方式；已有紀錄直接引用，只有缺漏且影響設計時才詢問。沿用資訊、裁定與需求，不另設必填表單。需求改動時說明哪些既有限制保留、哪些依裁定取代；工具不能自動保證語意完整。
   - 開工先查 roadmap，同範圍沿用，缺少才 `roadmap add --title "…" --ref swc:<change>`；使用實際回傳的工作編號，不虛構編號或重複登記。文件工作連 `change:` 或 `doc:`。這是流程規範，不新增無連結封存門檻。
   - `--verify test` 的任務可暫無 tests，顯示未開始、待測試規劃；非嚴格查詢將此列待辦，其他結構及死引用仍是錯誤。交給測試角色補計畫與連結，不能虛構 T-id 或暫改驗證方法繞過。執行證據及嚴格封存仍要求完整。
   - 改這個 change 自己新增的需求或情境：直接對它的編號用 modify-requirement／modify-scenario，原地修改、編號不變，測試連結不斷。
   - design 的清單欄位寫錯：`code change design --remove-goal <文字或序號>`（其他清單欄位同）。
2. **測試角色（dspx-test，必須和實作者不同的 agent）**：
   - 依 WHEN／THEN 從外部行為規劃測試（`code testplan add`），接著寫測試。
   - 寫好後簽收（`code testplan sign`）。
   - 回應實作者提出的測試異議（`code testplan respond`）。
3. **實作（dspx-implement）**：只改任務宣告的檔案，然後跑 `code evidence run <change> <任務>`。測試有問題時提出異議（`code testplan object`），不能自己改測試。
4. **驗證與封存（dspx-verify）**：
   - 執行 `code archive --dry-run`，看還有哪些問題擋著封存。
   - 審閱證據，並做語意審查：這個測試真的能證明 THEN 嗎？
   - 需要人看的需求，取得使用者驗收。
   - 最後執行 `artispec archive <change>`，並用 `code test` 跑回歸測試。

## 5. 證據與任務完成

- 任務沒有「打勾」指令。完成與否由引擎依證據判定，並寫回 `tasks.yaml` 的 `status`。狀態有五種：未開始、進行中、完成、完成（含豁免）、需重跑證據。
- **測試證據**：`code evidence run` 由引擎自己組指令，不接受自訂指令。指令內容是：
  - repo 設定的 `test-command`（預設 `python -m pytest`）；
  - 固定以 repo 根目錄為基準；
  - 輸出 JUnit 報告；
  - 規劃測試的完整位置。
- **測試證據要全部符合下列條件，才算通過**：
  - 每個規劃的測試都真的有跑到，名稱完整相符。
  - 沒有失敗。
  - 沒有未事先聲明的略過（聲明方式：`--allow-skips`）。
  - 測試和測試角色簽收時相同。比對的是「這個測試＋檔案裡共用的部分（import、輔助函式、fixture）」，同一檔案新增或修改別的測試不影響它的簽收。簽收另綁當時 covers 的情境行為及位置；情境、covers 或位置改變需重新審閱簽收。進行中舊簽收缺情境指紋時提示補簽，不自動升級。
  - 跑的過程中檔案沒被改動。
  - 執行器產出了 JUnit 報告；沒有報告就一律不通過。
- **其他證據**：
  - 檢查、展示、分析紀錄：`code evidence add`。
  - 使用者驗收：`code evidence accept`，保留驗收內容及使用者回覆；另綁目前需求與相關實作任務的範圍、宣告檔案。A 版驗收後改成 B 版，即使 agent 為 B 寫 inspection 通過，也不替代 B 的使用者驗收。
  - 豁免：`code evidence waive`，引用目前有效裁定，並寫明什麼情況下重新打開；裁定原文和被豁免任務並排顯示。查詢及封存時重新檢查裁定與當時任務範圍：裁定被駁回／取代或範圍變動就失效；如已有其他有效驗證則可依它完成。重啟條件的語意仍由負責人判斷。
- **新鮮度**：每筆新證據保存版本化的局部驗證範圍（相關需求規範句、情境、驗證方法、直接依據、task 方法、測試 id／位置／covers、略過政策、宣告檔案與執行器設定），加上宣告檔案及測試檔內容指紋。相關內容變更需補驗證；不相關需求或純標題修改不使其他任務全部失效。未宣告的外部檔案不受監看，工具仍提醒宣告檔案。
- **以最新為準**：先取同一任務及驗證方法的最新嘗試，再檢查成功、完整收集、簽收與新鮮度。零收集、部分收集、逾時、執行器失敗或無 JUnit 都保留為失敗，不能回頭用舊成功完成任務；有效重跑後才恢復。
- **升級／回退**：舊活動證據缺範圍資料時保留原文並提示補簽、補驗證，不用目前規格回填舊證據。已封存 change 不重開、不改寫。新欄位放在可擴充紀錄中；程式版本回退時保留所有紀錄及封條，不刪新證據或批次重新封條。舊版的完成判準仍有本次已修缺口，回退不代表同等保證。

## 6. 封存

- `code archive` 依序做這些事：
  1. 依既有證據推導任務狀態；dry-run 只在記憶體計算，實際封存才寫入。
  2. 嚴格檢查。
  3. 完整性檢查：任務都完成或有適用的有效豁免；必要情境的每個規劃測試都連到實作其需求的任務，且有有效測試證據或該任務有效豁免。需求規範句改變時納入其既有情境，純改標題不強制全部重跑；共享測試可覆蓋多個情境。inspection／imported-done 不代替測試型需求的證據。檢查、展示類需求另需目前範圍的使用者驗收或豁免。即使只有程式修正、沒有規格 delta，任務實作的既有需求仍須遵守驗證方法與目前版本的使用者驗收條件。
  4. 在副本上套用差異，併入 `verified-by`。
  5. 寫入規格、寫入基線、把資料夾搬進 `_archive/`。
- 寫到一半失敗會全部還原。
- 兩個 change 改到同一處：後封存的那個因基準指紋不符而停下，不會覆蓋。
- 被修改的情境，舊的 `verified-by` 會換成這次有效通過的測試，被拿掉的舊測試列出來交給測試角色；只有規劃卻沒執行的測試不會寫入。

## 7. 與治理層、文件樹的連結

- 參照方式：`swc:<change>` 指軟體 change，`req:<能力>/R1` 指需求。
- **決策被取代或撤回時**，程式會把下列項目標為可疑，每個都要附理由清除：
  - 依據它的進行中 change 與需求；
  - 再往下：驗證那條需求的測試、實作它的任務（已封存的只標記需重看，不重開）、引用那條需求的文件章節。
- **roadmap 工作項目**可以連到 `swc:<change>`，進度自動算：
  - change 進行中 → 進行中；
  - change 被標記 → 卡住，並寫明原因；
  - 封存 → 完成；
  - 封存時有豁免任務 → 完成（含豁免 N 項）。
- **文件章節**可以 `realizes: [req:…]`。需求內容變了，章節轉為 stale-software：照樣提醒更新，但**不擋文件定版**；定版時把這些章節記進該版紀錄（`software-divergence`）。
- 尚未封存的變動需求可引用 `draft-req:<change>/<capability>/R<n>`；只取指定 change 實際變動需求，base 衝突不冒當有效來源。封存後以唯一 sealed baseline 與既有 renames 解析正式入口，原字串不改。缺證明、損壞、撤回或退役列來源診斷，不能猜同編號需求；診斷列 software_errors，不阻擋文件自身定版。來源供投影、追溯、摘要與指紋共用，標題、mtime 及純 verified-by 封存註記不誤觸草稿語意過時。
- `check --json` 新增 coverage.version=1，文字同源：全專案結構、正文引用掃描、預覽準備狀態、軟體問題分開；過時但存在的預覽仍 performed 引用掃描，正文 deferred；正式正文同步 not-assessed，語意及交付審查 not-performed。原 ok/errors/退出碼與 article 索引範圍不變，查詢不寫入或執行測試。
- 文件預設以任務、交付讀者與既有 kind 組織，保留實際操作、結果與限制；既有專案 writing-guide 優先且刷新不覆寫。develop/apply 2.6、factcheck 2.4、生成規範 4；不新增必填表單、語意判定或完成閘門。
- **兩個領域互不阻擋**（2026/09/30 裁定「文件管文件、軟體管軟體」）：`artispec check` 把軟體錯誤另列，不讓文件的狀態與定版變紅（整體結束碼仍反映軟體問題）；文件引用已退役的需求只提醒；軟體封存不看文件。差異由系統記錄，不強制對齊。
- 現況看 `artispec roadmap`；交接看 `artispec handover`（`artispec brief` 已拿掉，見第 10 節後的實測後修訂）。
- 本次核定工作摘要：先以 `artispec roadmap` 找工作，再用 `artispec roadmap show <W> [--json]`，必要時查摘要引用的原始紀錄。版本化 JSON 分為 work、dependencies、governance、software、documents、actions、diagnostics；只整理明確 refs、子項、前置項及必要來源，正常項目概述數量，問題保留識別碼與原因，有效決策保留內容。缺資料明示而不推定無限制；被取代的引用仍保留，不能自動當成本工作已獲授權採用新版。
- 摘要不執行測試、不刷新或寫入受管紀錄、不重寫 handover，也不縮小完整驗證範圍。動作建議遵守既有角色與授權：未簽收由測試角色處理，文件未定版仍須使用者明確要求才定版；文件與軟體差異維持互不阻擋。
- 裁定駁回沿既有依據連結傳到決策、需求、change、任務與測試。軟體封存直接驗證相關決策的依據，清除 suspect 不等於恢復失效依據；不以無關治理錯誤阻擋全部 change。歷史裁定被取代仍沿既有審閱流程；waiver 需要目前有效裁定。
- `roadmap done` 只結案無可推導完成連結、無子項目的小工作；純 `gov:D` 約束不算完成條件。舊 closed 之後新增連結或子項目，以新條件推導。章節可已寫好，整份文件要目前內容與定版快照一致才算交付完成；單獨 stale-software 只提醒。文字和 JSON 共用原因，含前置阻擋、軟體失敗／缺證據／缺計畫、尚未定版及子項目原因；查詢不代跑測試。

## 8. OpenSpec 匯入

- 指令：`code import-openspec`。
  - 現行規格 → 正式規格。
  - 進行中的 change → 可以接著做的 change，差異一律經過引擎，自動補基準指紋。
  - 已封存的 change → 歷史。
  - 已打勾的任務 → 「匯入時已完成（無證據）」。
- 名稱對不上的差異只列在報告裡，不猜；`openspec/` 原檔不動。
- **驗證方法**：OpenSpec 沒有這個欄位，匯入時一律先設為 test。報告會列出內容提到畫面、版面的需求，請人判斷要不要改。
- **設計決策**：用「以後者為準」局部取代的，列為待合併。
- **補連結**：匯入的 change 缺「任務→需求」「測試→情境」連結，平常 check 只合併成一則提醒，封存時才逐條擋下。補連結的方式：
  1. 執行 `code change gaps --template`，產生一份缺口草稿。
  2. 實作者填好任務的部分，執行 `code task set --from`。
  3. 測試角色填好測試的部分，執行 `code testplan add --from`。

## 9. 已接受的風險

- **身分不是認證**：新紀錄以工具名稱與穩定會話碼區分作者，舊缺碼紀錄保守處理。Codex 已偵測的真實碼不能被衝突的手填碼覆蓋，但程式無法防止人刻意偽造整個呼叫環境或冒用負責人；這些欄位供流程追查，不是安全隔離。
- **驗收確認的真實性**：確認文字由 agent 寫入，程式無法證明出自使用者。治理裁定同樣保存原話但不驗證身分；清楚就直接記，不清楚才覆述確認。
- **封條只防不小心手改**：直接呼叫程式內部，可以寫出假紀錄。真正的防線是 CI 獨立重跑（`artispec code test`）。封存前不強制重跑。
- **改 `conftest.py` 或 pytest 設定作弊**：簽收只保護測試檔本身。
- **程式偵測「正在測試」而作弊**：只能靠驗證時的語意審查。

## 10. 文件與專案層級的配套（2026/09/30 裁定）

- **一個 `artispec archive <change>`**：文件 change 和軟體 change 共用一個入口，程式依名稱判斷是哪一種，兩邊的檢查各自保留。change 名稱跨領域不可重複，建立時就會擋下。舊的 `artispec change archive`、`artispec code archive` 仍然可以用。
- **定版改名 `artispec freeze`**（舊名 publish 保留為別名）：
  - 原本寫在 skill 裡要 agent 自己做的檢查，全部併進指令：每一節都寫好、沒有待更新；check 與 lint 無錯誤；快照不含殘留標記。
  - factcheck 沒跑過只提醒，不擋。
  - 沒給 `--level` 時自動建議：章節有增減用 minor，否則 patch。
  - 週報這類文件可用日期當版本：`--date-version`，或在 config 的 `date_versions` 列出文件；同一天只能定一版。
  - 只在使用者明確要求時執行。
  - dspx-publish skill 拿掉。
- **change 預覽標示草稿**：預覽檔的檔頭寫明「草稿，尚未定版」與對應的 change。
- **排版**：`artispec export <文件>` 一個指令產出 PDF，版型用專案設定。dspx-release 只在使用者說排版不對時使用，只處理被指出的問題。
- **專案基線**（系統設計 SR10）：
  - 甲：每次 `artispec freeze`，自動記下當下的軟體規格指紋、各程式 repo 的 commit、進行中的軟體 change、有效的專案決策（`docspec/baselines/documents/<文件>@<版本>.yaml`）。查詢：`artispec baseline doc <文件> <版本>`。
  - 乙：`artispec baseline <名稱>`，交付時把整個專案一次釘住：所有文件目前的定版版本（以及是否有尚未定版的修改）、軟體規格、各 repo 的 commit、有效決策、還開著的 change；有需要注意的地方會一併列出。名稱不可重複，寫了就不改。查詢：`artispec baseline list`、`artispec baseline show <名稱>`。
  - 基線檔封條保護，hook 擋手改。
- **派工規範**：`artispec init --agents-md` 在根目錄 AGENTS.md 寫入協作規範區塊，語言依專案 config 的主語言。dspx-govern skill 拿掉，它的固定行為寫進規範的「使用者的決定」一節。

## 10.1 實測後修訂（2026/09/30，考場座位實測）

- **使用者的話分兩種紀錄**：決定用 `docspec ruling add`，使用者提供的現況資訊用 `docspec info add`（補回原本文件樹「決定／資訊」的另一半）。兩者都保存原話；講得清楚就直接記，講得不清楚才覆述、等確認。文件可以 `realizes: [gov:I-…]`，事實查核把資訊紀錄當第一手來源；較新的資訊 `--supersedes` 舊的，引用舊資訊的章節會轉為需要更新。
- **現況看 roadmap，交接看交接單**：`docspec brief` 拿掉。`docspec handover` 顯示交接單並指向 `docspec roadmap` 與待裁定問題；`docspec handover write` 每次整份重寫（這段做了什麼、進行中、答應使用者的事、要注意的事、下一步），舊內容不留。
- **文件管文件、軟體管軟體**：見第 7 節。
- **追溯連結提醒（都不擋）**：`ruling add` 列出有效的專案決策，提醒改變了哪一條就寫新版取代；新需求沒標 based-on 時 `change status` 提醒；轉述決定、資訊或需求的章節要 realizes；定版時把沒有任何連結的章節記進版本紀錄（`unlinked-sections`）。這不豁免第 6 節必要情境、規劃測試、實作任務與有效證據的完成條件，也不容許不存在的引用或結構錯誤。
- **流程卡點修正**：`code spec show／list` 找得到只存在於進行中 change 的能力（`--change` 看套用後版本）；`code testplan set` 原地修正測試的對應情境（編號不變）；`code testplan sign` 不帶編號只簽「還沒簽或簽後改過」的，`--all` 才全部重簽；審查者把文件查核的發現用 `docspec audit raise` 記下（不算修改）。
- **交接新鮮度**：交接單保存帶時區時間與受管紀錄的內容指紋，讀取比較治理、roadmap、軟體規格／活動 change／證據、文件來源／工作文字／ledger／定版資訊／文件 change。同日變動也提醒可能過時並指向 roadmap；PDF、快取、預覽及單純 mtime 不計。舊交接單缺指紋或紀錄不可讀時明示無法確認，不宣稱最新；原內容仍可讀。讀取不刷新紀錄、重寫才更新交接狀態；不監控整個外部程式 repo。
- **過時原因明細**：新交接單由同次讀取保存相對路徑／指紋清單（`state-manifest`），文字與 JSON 的 `freshness.changes` 列出新增、修改、刪除；`changes-available` 明示能否列出。舊單有整體指紋仍可判定 current／stale，缺少有效清單只影響明細，不臆測歷史變動。軟體證據透過既有 `why` 與 roadmap `details` 指出需求、情境、依據、測試、驗證方法、runner 或檔案宣告的範圍差異；診斷不自動重簽或執行驗證。
- **測試計畫的簽收檢視**：E11 發現原文字列表分不清已簽收與未簽收；`code testplan list` 現在逐測試顯示 unsigned／current／needs-review／unknown 與原因，JSON 保留原紀錄並附加 `signoffs`。使用現行簽收判定，不因列出資料而簽收、執行測試或改寫紀錄。

目前的 skill：
- 文件：dspx-develop、dspx-apply、dspx-factcheck、dspx-release（只在排版不對時用）、dspx-diagram（輔助）。
- 軟體：dspx-propose、dspx-test、dspx-implement、dspx-verify。

## 11. 第三期範圍與已知限制

- 依「第三期縮小範圍」裁定，產品不支援多 agent 並行修改受管理紀錄或多人編輯；原寫入權、測試埠協調與 S6 取消。協作以 roadmap 與每次整份重寫的 handover 交棒，不保存追加式交接歷史。
- 已知限制：同一 change 在兩分支各加任務會使封條檔 `tasks.yaml` 衝突，證據與治理編號也可能撞號。這些是未支援用法的限制，不是第三期待實作項目；不得手動合併後重新封條冒充原紀錄。
- 保留 base fingerprint 防止舊 change 覆蓋新基準，與產品並行支援分開。docspec 原始碼開發可以依難度分派 agent，明訂檔案負責人，測試與實作角色分開。
- 既有專案遷移細節仍待第三期架構關卡。前批 E11 的查詢成本已形成新核定的 `add-work-summary`；摘要沿用既有紀錄，不新增 stores、workset、語意推定或並行寫入支援。
- `complete-cross-platform-validation` 已完成本輪驗證：Windows／Linux 最終完整回歸各 1433 passed、1 skipped，PDF／proof 各 83 passed、0 skipped；各兩份全新 agent 正常／過時案例通過獨立核對。Linux 接手採全新 Windows controller 經 WSL 操作 Linux 專案與 CLI，不代表 Linux 原生 controller 通過；線上字型 ZIP 校驗不符後使用既有受控字型離線安裝，原始失敗保留。平台、證據、查詢成本與限制見 [工作摘要驗證報告](validation/work-summary-run.md)。全新 agent 在流程修改或發布前由人啟動，CI 只跑機械回歸。
