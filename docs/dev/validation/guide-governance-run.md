# guide 治理來源指引修正

日期：2026/10/03。OpenSpec change：`fix-guide-governance-contract`。修正負責人已核定的來源分工，補齊先前未同步的 guide；新文件風格、F2 與 check 輸出設計仍未實作。

## 1. 缺陷與變更

最新已安裝版本的 `artispec guide develop` 仍把 notes.md 說成 human-decision record，要求保存裁定原話；現行 develop skill／生成規範與負責人裁定則要求治理紀錄保存原話、notes 引用。原查詢 exit 0，合成案例前後全檔指紋一致，確認是輸出規則矛盾。

產品只修改 `src/dspx/schemas/section-driven/schema.yaml` 的 develop workflow 兩段文字。ruling 保存裁定、info 保存事實的原話；notes 留變更理由與原紀錄引用。保留明確內容直接引用、不清楚才釐清、section decisions 與原紀錄分工，以及無法機械證明對話真實性的界線。不改模型必填、記錄格式、完成算法或 archive 程式，也不要求第二份裁定。

## 2. 獨立案例

測試角色單獨新增 `tests/test_governance_guide_contract.py` 四案：透過真正 CLI 函數測完整、develop、JSON guide，讀回真實合成 ruling／info 原話並比對查詢前後全案 bytes；另驗證不清楚內容的 read-back／confirmed 成對條件。notes 成功與阻擋直接沿用既有七案，沒有重複造另一套完成測試。

真正 RED 為 **3 failed／8 passed**，三種 guide 投影都沒有把原話分派到治理命令；修正後 GREEN 為 **11 passed**。測試 SHA256 前後同為 `824d6c3c6760778b44a908806d3fb2b5c59eec8d26c4c49400ee990cdccd2cd4`。首次 runner 漏帶 source 路徑的收集失敗另存，沒有算作行為 RED。

## 3. 本批實際結果

- Windows／Python 3.12.13：七個相關測試檔 **111 passed／0 skipped**，21.34 秒，退出碼 0。
- Windows controller 操作的實際 WSL Ubuntu-24.04 Linux／Python 3.12.3：相同 **111 passed／0 skipped**，59.21 秒，退出碼 0。兩平台相關回歸前後產品來源指紋一致。
- 新 wheel SHA256 `0ba38882173736dc67c0115ea9170fd0a71b50b63ac222871a9e1ca9da351452`，173 個套件檔與來源逐位元一致，唯一 console script 是 artispec。
- 兩平台各在新隔離環境離線安裝該 wheel，清除 PYTHONPATH，確認 dspx 來自 site-packages。每案 **8 次真正已安裝 CLI**：初始化、兩筆治理新增、三種 guide、兩筆原話讀回，均 exit 0。
- 五次唯讀查詢前後全案 manifest 相同；原話、notes 狀態與生成資料未被查詢改寫。中文與空白的案例路徑實際可用。
- 測試角色獨立核對 schema 解析差異只在 workflow 的兩個 steps，保留原治理與完成界線。
- 獨立收尾核對兩份 JUnit、八次 CLI 原始退出碼／三種投影／治理原話、每案 21 檔 manifest，並逐檔比對 wheel／來源／兩份實際 site-packages 的 173 檔，全部一致；沒有以主實作者的自報代稱安裝核對。
- OpenSpec strict validation 為 **17 passed／0 failed**，差異空白檢查退出碼 0。指定分支與既有 dirty 成果保留，不提交、推送或開 PR。

原始資料位於 repo 外 `artispec-guide-governance-fix-20261003-c8d8a6f9`，包含 398 檔基準、schema 原文、RED／GREEN／原收集失敗、JUnit、安裝程序、CLI 命令與輸出、manifest 及來源核對。只用合成資料。

本批未重跑完整 pytest、PDF／proof、考場實驗或原 README 六案。這些窄幅通過不等於新的預設風格已實作，也不代表同題比較已完成；後續順序見[重跑方案](../proposals/repeat-exam-workflow.md)。
