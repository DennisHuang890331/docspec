# ArtiSpec 安裝命名與升級驗證

日期：2026/10/07。負責人已核定 distribution 與使用者工具目錄改名、本機分支改成 dev、整理提交並推遠端 dev；不動 main、不開 PR。本輪不是 PyPI 發布，也不將既有未完成的兩域工作流宣稱通過。

## 變更與保留範圍

- 安裝套件改為 artispec，唯一入口仍為 artispec；Python import dspx、專案 docspec/、corpus、DOCSPEC_* 與管理標記保留。
- 使用者工具根改為 platformdirs.user_data_dir("artispec", appauthor=False)：Windows LOCALAPPDATA/artispec、Linux ~/.local/share/artispec。
- setup --migrate-data 是明確離線遷移：白名單 tinytex/fonts/pandoc/typst/drawio/cache 與 tex.lock/update-cache.json。來源保留，未知舊根內容不操作，目的額外 installers 保留；先驗完整碰撞與內容，再發布缺少項目，失敗回復本次自建項目。
- tex.lock 已知七個路徑欄位只重指來源內路徑，資產 bytes、其他欄位與來源 lock 保留。version／doctor 查詢不搬移，doctor 可提示明確遷移。
- 新 metadata 來源使用 artispec，Git 更新指向原 repo 的 dev，init 更新檢查也查 dev。安裝指南使用直接 wheel extras，沒有自動搬移專案紀錄。

## 獨立正反案例

測試角色先取得本批完整 RED：34 failed／30 passed；相鄰原行為基線 91 passed。安裝名、預設 metadata、dev 更新、來源安全／碰撞／壞 lock／source 變動／rollback／唯讀查詢有獨立案例。

後續另保留三段原失敗：健康合成 fixture 未隔離真實 legacy root，1 failed／156 passed，測試角色只補一行 legacy 路徑隔離、不改產品診斷；白名單內 link 指向未知來源需拒絕，先 RED 再修；Windows 唯讀來源使 stage 清理 WinError5，已真實重現，包含發布後清理失敗及遮蔽原 OSError 的 rollback 反例。

唯讀修法只清本次自有 Windows 副本的屬性，不改來源、既有目的或 Unix executable mode。最終獨立七檔 **163 passed（8.51 秒）**。變更既有 tests/test_phase_f.py 僅新增健康 fixture 的 legacy 路徑隔離一行；其他未核定行為與歷史案例保持。

## 已安裝 wheel 與升級

新 wheel SHA-256：`4b61c1d088294ae5a2f1d4cc37ac085d83379b0e680d9135e0f0ef64c2e70dce`。
原安裝 wheel SHA-256：`002c1420b4326dc413b4a6afd8e2eb3d52ba2df1ea9f3e5758946dd30b3b0ae7`。

Windows／實際 WSL Ubuntu-24.04 各驗乾淨安裝與舊包移除後升級，共四情境、50 個成功命令、88 項核對。每個 scope 的 174 個 dspx 套件檔案與 wheel 逐檔相同，合計 696 次比對；實際 version/help、pip check、metadata、site-packages 來源及唯一入口均核過。合成 companion tool 與額外資料的 before／after 指紋相同。中文與空白路徑、README 的直接 wheel[export] 安裝形式均在兩平台真實執行。

錯誤 --from wheel 加 package[export] 形式兩平台 exit2、案外 Windows 路徑腳本 KeyError 的原收據保留，更正命令／腳本後另存成功，不算產品錯誤。Linux 由 Windows controller 經 WSL 操作真 Linux runtime，不代稱原生 Linux agent；macOS 未驗。

## 工具資料遷移與本機安裝

兩平台已真實執行明確遷移，來源保留、目的額外內容保留。Windows 23,620 個受控檔、Linux 20,751 個受控檔經核對；七個 lock 路徑指向新根。兩平台新根 doctor --deep 均真 exit0，一頁中英文實編與文字層檢查通過。

Windows 全域 uv tool 已由 docspec 取代為 artispec，實際 tools/artispec 環境存在、舊 tools/docspec 移除，唯一入口 artispec；全域 doctor/deep 及 16 套件的 pip check exit0。使用本輪新 wheel 與 repo lock 匯出的 runtime constraints，與完整回歸的相依版本一致。舊受控工具來源與舊 wheel 保留作備份，沒有改其他安裝環境。

負責人指定共用資料夾已更新新 wheel、Linux 安裝說明、校驗碼及 runtime constraints；舊 wheel 留作備份。沒有讀取或提交該資料夾的真實專案內容，也未宣稱已在另一個隔離 Linux agent 的環境完成安裝。

## 完整回歸與開發提交

Windows Python 3.12.13：**2135 passed／1 skipped**，pytest 597.78 秒，wrapper 600.75 秒。實際 WSL Linux Python 3.12.3：**2132 passed／4 skipped**，pytest 566.28 秒，wrapper 572.05 秒。兩平台各 2136 項、0 failure／error、真 exit0，276 個 src/tests/pyproject/lock 檔在測試前後 bytes 相同。略過僅一個既有退役警告案例，Linux 另三個 Windows junction 案例；沒有 PDF／proof 環境略過。

回歸結束後才整理暫存檢查列出的 17 個 EOF 多餘空白：16 個規劃／spec／script 只去末尾空白，Python script AST 不變；測試角色另整理 tests/test_workflow_integrity.py，AST 含位置資訊完全相同、單檔回歸 **48 passed（40.92 秒）**。整套回歸驗的是整理前 bytes，末尾空白與單檔驗證另存，沒有虛稱前後原檔完全未變。封條／歷史正文與產品套件程式未改。

本機分支已從 claude/software-domain-redesign 改為 dev。暫存成果經另一角色核對，349 個文字檔未見真實專案資料、binary、wheel、appdata、原始案例對話或常見金鑰格式。整理提交與遠端 dev 推送進行中；未完成事項仍包含 roadmap 錯誤連結恢復待裁定、新 Linux 包 GUI 與兩案初版接受／封存、容量變更及全新會話接手。中英文 README 仍待定稿；ArtiSpec 自用開發尚未遷移。

本批案外證據根：`C:/Users/zxc22/AppData/Local/Temp/artispec-installation-upgrade-20261007-4e6289/`。portable-receipts/summary.json 含全部命令、初始失敗與來源指紋；regression/ 保存完整回歸，Windows 原始唯讀失敗另保存於同使用者 Temp 的 artispec-runtime-readonly-red.json。真實專案內容與工具資料未複製進 repo。
