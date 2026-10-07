# 文件版本收納與版本產物驗證

日期：2026/10/01。分支：`claude/software-domain-redesign`。對應 OpenSpec change：`relocate-document-versions`。只使用隔離的合成資料；不提交、推送、開 PR 或修改 main，保留先前工作區成果與原始驗收紀錄。

本輪版本儲存、明確搬移與輸出隔離已完成實作、獨立 review、Windows／Linux 完整回歸與新 wheel 驗證。先前六案全新 agent 的未通過項目不由本報告補成通過。

## 1. 實作範圍

- 新版定版 Markdown 與當版引用圖片放 `docspec/changes/_versions/<article>/<version>/snapshot/`，來源與圖片共同登記；圖片使用原始 bytes 指紋，Markdown 保留既有換行正規化。工作圖片後續修改不改舊版，也不能因正文相同就把圖片變更判成沒有修改。
- `history.md` 放文章版本根；每版 `exports/`、`proof/` 可重生，工作稿預覽放 `_preview/`。只有最高定版版本更新 `docs/` 的最新交付輸出，舊版與預覽不得取代或刪除最新產物。這不搬動本 repo 的一般開發文件。
- `artispec versions [article] [--json]` 唯讀列出版本來源。新舊同版並存明確拒絕；查詢不搬移、不重算指紋洗白歷史。普通 change 的查詢、封存與搬移不把 `_versions` 當作 change。
- `artispec versions migrate [article] [--dry-run] [--json]` 是明確搬移；省略 article 處理全部。全批次先檢查原 hash、目標與父目錄、history 衝突、symlink／Windows junction；保留快照 bytes 與原已驗證 hash，只換 manifest 路徑 key，既有 sealed baselines 留原處且不改封條。中途搬移失敗回復已移動檔案，成功後重跑不寫入。
- `register-legacy` 的任意歷史檔收 `_versions/_legacy/<name>/snapshot/`，不假造版本。無版本身份的舊校樣保存在 `_legacy-proof/`，不推測為最新版本；缺歷史圖片明示 unknown，匯出不得拿 current 圖片替代。
- snapshot 根及祖先刪除受 guard 保護；可再生輸出仍可寫。選定來源或圖片被竄改時 export／journal export 拒絕。讀取與輸出 preflight 防止連結越出受管路徑，正常 Read 與 staging 編輯維持可用。
- handover 追蹤 snapshot／工作來源與圖片；PDF、版本 proof、未知來源 proof 與 preview 變動不會假報交接過時。新增五個行為案例並保留來源變動會過時的反例。
- history 的寫入目標在 render／capture 前檢查，拒絕 symlink、junction、不在專案內的路徑與既有非普通檔；不能藉 history 寫到另一個使用者檔案。

快照 capture 與 manifest 登記有局部回復；版本 migration 有批次回復。既有 freeze 的 render、latest 蓋版、history 與 baseline 仍依序執行，本輪未新增整條 freeze 的跨檔交易，也未宣稱所有作業系統故障都能回復整個定版。獨立 review 發現設計文字的過度承諾後已收窄說明，完成判定與 baseline 封條契約不變。

## 2. 獨立測試與 review

測試角色先建立行為案例，實作者按檔案分工。獨立新增 `tests/test_document_version_storage.py` 最終 101 案；另由 review 角色新增 `tests/test_document_history_safety.py` 11 案。來源與測試的負責人分開，review 不修改來源。

- 初始核心案例有 8 項失敗，保存修前結果。實作後 Windows 的 96 案版本測試通過；其後增加五個 handover 案，版本與三個實際 PDF 排版案共 104 passed。
- 真 PNG 顏色檢查確認 frozen 藍圖匯出仍是藍圖，即使 current 改紅；binary CRLF 竄改拒絕，而既有 Markdown 換行相容保留。原 baseline、manifest 與來源指紋分別核對。
- 獨立 review 實際重現六項流程缺陷：竄改圖片仍可 journal export、version junction 讓 proof 操作外部目錄、asset junction 讀外部檔、migration 乾跑漏父目錄是普通檔、圖片單獨修改誤判 no-op／baseline，以及 guard 漏祖先刪除。全部在同條件下獨立複驗修復，原失敗產物保留。
- 最後獨立重現 history file symlink：修前 Windows 8 failed、2 passed；修後加既有 directory 案共 11 passed、0 skipped。涵蓋 flat／per-article、首次／再次定版、專案內／外目標，拒絕後目標 bytes、manifest、baseline 不變，沒有新版快照。
- 新增的 Windows junction 案使用真正 NTFS junction；Linux 的相關 symbolic-link 案使用真正 symlink。不能把 Windows 專用案例在 Linux 的 skip 當作通過。
- 完整回歸首批有五項舊測試仍使用舊 archive 路徑或未登記手建快照，更新了測試路徑與合法 fixture 登記。原正文標記、錨點與 PDF 座標／縮排／空行斷言保留；不是放寬測試。更早實作期間的失敗 checkpoint 亦保留，不回填成通過。

review 證據在案外 `C:/Users/zxc22/AppData/Local/Temp/artispec-readme-review-20261001/`：`review-relocate-document-versions.json`、`review-document-history-safety.json`、`history-safety-windows-before.xml`、`history-safety-windows-after.xml`。review 本身沒有宣稱兩平台完整回歸；以下由實際執行的結果補齊。

## 3. 平台回歸與 PDF／proof

Windows 使用原生 Python 3.12.13：**1729 passed、1 skipped**，486.98 秒。Linux 為 Windows controller 經 WSL Ubuntu 24.04 執行真正 Linux Python 3.12.3：**1726 passed、4 skipped**，505.87 秒。退出碼均為 0；不宣稱 Linux 原生 agent/controller 驗收。

兩平台的 export／proof／程式區塊 PDF 座標共 **86 passed、0 skipped**。新版本與 history 防護共 112 案，Windows **112 passed、0 skipped**；Linux **109 passed、3 skipped**，三個略過都是明確 Windows-only 的真 NTFS junction 案例，Linux 的真 symlink 及 history 防護照常通過。兩平台另外各有一個既有退役 group.yaml render warning 路徑的 skip，不是 PDF 工具缺失，也不把 skip 算通過。

最終 JUnit 位置：

- Windows：`C:/Users/zxc22/AppData/Local/Temp/artispec-document-versions-windows-release.xml`。
- Linux：`/home/dennis/.cache/docspec-workflow-validation/document-versions-linux-release.xml`。

PDF／proof 沿用既有受控 Typst 0.15.0、pandoc 3.10 與釘版字型資產。實際工具版本檢查、PDF fidelity、校樣與程式區塊座標測試不因環境問題放寬。這輪沒有重新宣稱下載驗證，前輪線上字型校驗失敗與離線資產來源紀錄保留在原報告。

## 4. 新 wheel 與實際安裝入口

最終 wheel 在 repo 外建置：`C:/Users/zxc22/AppData/Local/Temp/artispec-document-versions-wheel-final/docspec-0.1.0-py3-none-any.whl`。SHA256：`0FFC4781204319F64A3DED648759034DF082F8D5EDD358DA6859FD60C441EA27`。安裝 distribution 仍叫 `docspec`，唯一 console script 為 `artispec`。

最後 history 防護與 skill 文字更新後重建上述 wheel；Windows／Linux 各自隔離新安裝與舊 wheel 升級，各 **64 checks、42 次實際子程序通過**。實際已安裝 `artispec` 的版本查詢／乾跑／搬移／重跑，各 **9 checks、7 次子程序通過**，驗證來源 bytes、原 manifest hash 與唯讀查詢。最終 wheel 中的 `dspx/` 檔案與當時 `src/dspx/` 逐檔比對零差異；前一 wheel 的紀錄另存，不代稱最後產物。

最終案外紀錄：

- Windows：`C:/Users/zxc22/AppData/Local/Temp/artispec-document-versions-windows-package-final/package-retirement.json`，`artispec-document-versions-windows-installed-smoke-final/installed-versions.json`。
- Linux：`/home/dennis/.cache/docspec-workflow-validation/document-versions-linux-package-final/package-retirement.json`，`document-versions-linux-installed-smoke-final/installed-versions.json`。

安裝檢查清除 PYTHONPATH，使用實際環境的 Scripts／bin 入口，涵蓋空白與中文路徑；不以來源碼入口代替安裝驗證，不移除使用者其他環境的套件。測試專案、原始 command／exit／output 與 wheel 均在 repo 外。

## 5. 文件、規範與未完成項目

README 維持英文短版 60 行，沒有 `docspec` 文字，八個本地連結目標皆存在，完整操作移至 [操作指南](../../user-guide.md)。已核定的存放方式、裁定取代關係、現況、CHANGELOG 與 release skill 3.3 同步更新；skill YAML、name、版本與 compatibility 手動檢查通過。既有 compatibility 欄位保留，不能把泛用 validator 不接受該欄位代稱本產品錯誤或已通過。

OpenSpec strict validation **11 passed、0 failed**，含版本儲存、history 防護及 handover 輸出排除的情境；`git diff --check` 通過。未推送、未執行遠端 CI，不以本機結果代稱 CI 通過。

本輪是版本目錄的獨立行為測試、機械回歸與實作 review，沒有重新執行先前六份全新 agent README 流程。前輪同 provider 的獨立 agent 身分辨識仍待負責人裁定，六案未整體通過的事實見 [README 流程驗證](readme-workflows-run.md)。本輪沒有擅改簽收身分、放寬完成門檻或新增並行寫入支援。

## 6. 後續 README 雙語修訂（同日）

使用者後續要求中英文版本與供其他 agent 繪圖的 logo 設計。上方第 5 節的 60 行是版本儲存交付時的 README checkpoint；目前 `README.md` 與新增 `README.zh-TW.md` 各 69 行，互設語言連結，以報表匯出與操作手冊為共同例子，分清新建／接手及 skills／CLI。兩版沒有舊名稱，指令除初始化語言旗標外一致，每版 12 個本地連結與圖片目標存在，指南 anchor 與語言切換檢查通過；完整指南仍為英文。

雙語 logo brief 在 `docs/assets/logo-design-brief.md`，屬未定稿提案，原圖未替換。OpenSpec strict validation 11 passed、0 failed，`git diff --check` 通過。此次只改文件，未重跑 pytest 或全新 agent 實測，不把上述來源／wheel 回歸代稱新的雙語 README 已通過接手實測。
