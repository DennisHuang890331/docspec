## Context

2026/10/01 使用者確認新版本目錄方案，原話「可以你開始實作了嗎?」。本案明確取代文件定版寫入 `docs/archive/`、歷史寫入 `docs/revision_history/` 的儲存規則；舊路徑讀取與防護仍保留。既有基線、封條、版本識別、文件與軟體各自完成條件不改寫。本案實作與驗證結果見 `docs/dev/validation/document-version-storage-run.md`，不回填先前六案驗收。

## Goals / Non-Goals

讓 docs 留工作中的最新內容，把版本的不可變輸入與可再生輸出收在同一版本目錄。支援可讀舊專案、明確且保留原文的搬移，以及缺歷史圖來源時的真實診斷。不改普通 change 格式、不強迫初次 freeze 開新 change、不搬 sealed baseline、不從現在圖檔臆造歷史、不新增多人或多 agent 同時寫受管資料的支援。

## Decisions

1. **版本樹與普通 change 分開。**

   ```text
   docspec/changes/
     <document-change>/          change.yaml、notes.md、staging/、preview/
     <software-change>/          proposal／design／specs／tests／tasks
     _archive/                  保留兩域原封存格式
     _versions/
       <article>/
         history.md
         <version>/
           snapshot/
             document.md
             assets/            當版實際引用的受管圖資產
           exports/<article>_v<version>.<format>
           proof/page_<N>.png
         _preview/
           exports/
           proof/
         _legacy-proof/         舊無版號 proof，版本來源未知
       _legacy/
         <name>/snapshot/       register-legacy 原檔，非版本號
   docs/
     <article>_latest.md         實際位置仍依既有 layout
     assets/                    工作資產
     exports/                   沿用既有 latest 輸出命名
   ```

   `_versions`、`_preview`、`_legacy-proof` 與頂層 `_legacy` 是保留目錄，不能被普通 change 的列表、同名辨識、封存或搬移當作 change。`_legacy` 不是文章名，`_legacy-proof`／`_preview` 不是版本號；碰到既有識別與保留名稱衝突時報錯，不用新規則覆蓋原檔。版本目錄不是 change ID，不因此新增 proposal/design/tasks。文章與版本路徑沿用既有識別規則，所有解析後路徑必須留在指定根目錄內。

2. **讀取有 fallback，寫入只有新位置。** `docs_snapshot` 解析新 snapshot 或舊 archive；同文章同版同時存在兩處時明確報錯，內容相同也不選副本。`version_snapshot` 永遠提供新寫入位置，`docs_changelog` 永遠指向新 `history.md`。`artispec versions [article] [--json]` 唯讀顯示版本與新／舊來源，讓搬移入口可發現；不自動修復、refresh 或搬移。freeze 遇仍未搬移的舊歷史先拒絕並提示 explicit migrate，避免把歷史改寫成兩份。

3. **freeze 保存不可變輸入。** 每版 snapshot 的 Markdown 與所引用、可解析的受管圖資產同次保存；工作圖後續改動不能改掉舊版。snapshot 整個資料夾受 hash 與 write guard 保護，檔案被新增、刪除或替換都不能被視為原版本。snapshot 與 manifest 登記失敗時回復該次 snapshot；history 寫入路徑須在 render／capture 前拒絕 symlink、junction、外部路徑及非普通檔。既有 freeze 的 render、latest 蓋版、history 與 baseline 仍是依序寫入，本輪不承諾整條 freeze 流程的跨檔案交易。格式調整只能再生 exports/proof；不得改 snapshot 或重算 hash 把已變動內容當合法。只有受管的圖引用可以被保存，不因此複製任意外部路徑。

4. **輸出依所選版本分開。** 指定版及預設最新定版 export 讀該版 snapshot/assets，寫該版 exports；proof 從該版實際輸出讀取並寫該版 proof。未定版 `--latest` 預覽在 `_preview` 再生，不佯裝已有版本。既有 docs/exports 的 latest 輸出保留；匯出舊版或 preview 不得清掉、替換其他版與 latest。新 snapshot 缺圖或被改動時報錯，不 fallback 到目前圖檔。

5. **搬移是單獨且可預檢的交易。** `artispec versions migrate [article] --dry-run` 唯讀列出來源、目標與缺漏；省略文章以全專案為批次。實跑先驗證所有選取項目的舊 `.freeze.yaml` 與快照原 hash、目標不存在、history 衝突、路徑與可辨識資產來源，再搬移 Markdown／既有可辨識歷史產物／history。未通過任何前置檢查不得改一個原檔；中途失敗回復已完成的搬移與 manifest 更新。無待搬內容時可安全重跑。

6. **搬移不能洗白歷史。** 原 Markdown bytes/hash不變；`.freeze.yaml` 只對已核對的原 hash 換成新相對路徑 key。現有 sealed document/project baseline 保持原位置、原 bytes、原封條；不得重新 seal 或回填目前內容。舊 Markdown 沒有當版圖資產時，搬移原 Markdown 可成功，但報告 `unknown provenance`／缺圖，不複製 current assets 或宣稱圖歷史已 verified。讀舊版時保留來源不明提醒；匯出找不到版本資產時明確拒絕，不以 current 圖補洞。

7. **舊產物不能被猜成一版。** 舊無版號的 proof 只保存在文章根 `_legacy-proof/`，明示版本來源未知，不能當作最新或某版 proof。既有 register-legacy 接受的任意歷史檔收在 `_versions/_legacy/<name>/snapshot/`，保留原格式、bytes與原hash，不假造semver或插入文章版本序列；舊 `docs/archive/legacy/` 讀取仍有效。省略 article 的 all explicit migrate 包含這個 collection，遵守相同預檢／原hash換key／回復；這是舊API儲存相容，不新增治理紀錄型別。

## Risks / Trade-offs

- 只驗證 Markdown 原 hash 不能證明舊圖資產來源。原快照可原文搬移，圖的缺漏仍須保留，可能使該版匯出無法完成。
- 新舊副本並存不能用「新位置優先」掩蓋不一致；使用者需處置重複，再搬移或繼續。
- baseline 本來保存軟體／治理狀態，不隨實體路徑整理重寫。任何需要讀舊版路徑的查詢都須沿用解析 fallback，而不是更新 sealed 紀錄。
- 任意檔案操作失敗不能留下半完成的批次。乾跑與實跑各以原檔 bytes、manifest及輸出路徑的可觀察行為驗證。

## Verification

獨立測試角色先建立新／舊路徑、同版碰撞、snapshot/assets 不變、缺圖、不洗白、全批次預檢及回復、版本／preview 輸出隔離、hook Read／Write、baseline保留與普通 change不被誤掃的行為案例。實作者只改負責範圍，測試角色維護測試；review 檢查本案結果，不回填以前驗收。Windows／Linux實際機械與PDF/proof覆蓋另記，未執行不宣稱通過。
