# 封存提醒與交付指引修正

日期：2026/10/03。OpenSpec change：`align-delivery-guidance`。負責人要求「繼續修改」，接續原實測 O6 與 O1／O2／O3／A1 的指引；不新增完成算法、紀錄種類或來源語法。

## 1. 具體修正

- `commands/change/change.py`：保留原 notes 機械條件，只換提醒內容。seed-only／缺 notes 不再宣稱 human-decision record 空白或 Archiving anyway；改提供可選的變更理由與 ruling／info／decision 查詢入口，明示非阻擋，且目標完成與 fork drift 仍須通過。不查斷語意、不補造或抄錄裁定、不改原 notes。
- `dspx-propose` 1.6：分清操作者安裝需求、主機已有依賴與程序／整機網路限制；引用已記錄要求，只問真正缺漏且影響設計的區別，不自行加強條件。
- `dspx-verify` 1.6：核對實際平台、啟動、權限與完成後的交付包；headless 或另一平台測試不能證明尚未操作的 GUI。驗收文件的 latest 待驗／可用敘述須和當前證據核對，必要修正及新定版仍需負責人授權；舊快照不改，不新增跨域完成閘門。
- `commands/maintenance/init.py`：雙語生成規範提高至版本 3，補同樣的來源與交付界線。舊專案沿用 `artispec init --agents-md --tool <tool>` 刷新，不新增搬移或設定操作。
- 同步操作指南、CHANGELOG、現況、裁定與 roadmap；[F2 提案](../proposals/draft-requirement-links.md) 明示尚未核定，只討論身份、封存後映射與失效。沒有實作 `draft-req:`。

## 2. 獨立案例與原始失敗

測試角色單獨維護 `tests/test_archive_governance_reminder.py` 七案。以真實 ruling／info／decision、realizes、file-target staging 與 archive 建立合成資料，不 mock run_archive。驗證 seed-only／缺 notes 的成功與未完成拒絕、額外理由／治理引用不提醒、fork drift 拒絕及原 override 途徑。治理集合與 bytes、notes bytes 或缺失狀態均核對。

首次執行撞到主實作者先套暫稿的時段，7 passed，不能算原始 RED。只將本批 warning 還原到案外 baseline，未還原其他 dirty 工作；確認 source hash 相同後真正 RED 為 **5 failed／2 passed**。五案分別暴露缺非阻擋聲明與 Archiving anyway 假承諾。收到 RED 後套最終文案，獨立 GREEN 為 **7 passed（2.69 秒）**，測試與前後來源 hashes 不變。首次通過、原 RED、最終 GREEN 與各實際 fixture 都保留，不用成功覆蓋失敗。

兩平台 console harness 的第一次嘗試，錯以為生成的版本一定使用 YAML 雙引號；實際合法輸出是單引號。兩平台各三次 CLI 已成功，但控制器 assertion 失敗。改用已安裝的 frontmatter parser 讀取 metadata，另建新的最終合成案重查。此項是驗證腳本假設，不改產品或 wheel，原腳本、原案例及失敗日誌保留。

## 3. 本批驗證結果

- **Windows／Python 3.12.13**：10 個相關測試檔共 236 passed／0 skipped，85.65 秒，退出碼 0。
- **實際 WSL Ubuntu-24.04 Linux／Python 3.12.3**：相同 236 passed／0 skipped，103.95 秒，退出碼 0。Linux 由 Windows controller 經 WSL 執行。
- **新 wheel**：SHA256 `d598618cf1e3c2bf6f3cf4018ebbb6db41f8693714120de15c6418db4bb2c2ed`，173 個套件檔逐位元匹配來源，唯一入口 artispec。兩平台各自新建使用者層級隔離環境；移除 PYTHONPATH、確認 dspx 從 site-packages 載入，repo 外的七個新案例各 7 passed。
- **真正已安裝 console script**：每平台各 9 次呼叫，含 help／version、init、由舊生成版本與 skill metadata 刷新、ruling／change／target 建立、未完成拒絕與完成封存。中文含空白專案路徑實際可用；只有預期的未完成 archive 為 exit 1，其餘 exit 0。使用者 AGENTS 前文、原治理與 notes 保留，正常落地 staged bytes。
- **獨立收尾審查**：reviewer 唯讀核對兩平台 JUnit、真正 CLI 退出碼／產物、原 notes／治理及 wheel／兩份 site-packages／173 個來源檔。沒有實質缺陷，確認指引不新增定版權或硬閘、F2 仍是未核定方案；未改回答、fixture、測試或產品。
- **唯讀與來源界線**：兩平台相關回歸前後來源指紋一致；獨立七案測試 SHA256 為 `0f00f26f24d761c2413b749934df3638c2ba170f90151ee38d8d3fa2e3a0c632`，實作者未修改。安裝／CLI 案例在 repo 外；README、原實測與前批成果不因本輪回填。
- **交付檢查**：OpenSpec `validate --all --strict --no-interactive` 為 16 passed／0 failed，`git diff --check` 退出碼 0。對本批基準只變更四個產品檔及預期文件，原基準檔無刪除，兩份 README、套件設定與先前驗證報告 bytes 不變。分支仍為 `claude/software-domain-redesign`、HEAD `5a942b6`，未提交、推送或開 PR。

通用 skill-creator quick validator 仍不接受既有 compatibility 欄位，兩份原檔直接檢查均拒絕；暫存副本只移除此欄位後各通過。產品 skills／init 回歸及實際生成／升級則通過，不將暫存副本或格式檢查當作 agent 行為證據。

本批改的是提醒文字與窄幅指引，因此執行相關回歸及安裝驗證，**未重跑完整套件、PDF／proof、考場完整案例或六次全新 agent 實測**。上一批完整回歸與 PDF 結果仍見[第一批報告](workflow-review-gaps-run.md)，不當成本批重跑結果。新 skills 的機械／生成檢查不保證所有 agent 都會遵守。

原始紀錄在 repo 外 `artispec-delivery-followup-20261003-ac0016e0`，保存 374 檔本批基準、七案 RED／GREEN、JUnit、已安裝來源 probe、CLI 的命令／退出碼／輸出、初次失敗及最終 console 案例。只用合成資料，不收真實專案或完整 agent 對話。

## 4. 後續待辦

F2 新引用格式與封存後涵義須先由負責人確認；README 意見尚待討論。既有考場控制器的 UTF-8、完整 shell history、GUI 等待、評分與抽樣改進不因本批新 harness 通過而結案。原實測的功能、作者簽收、證據、接受及凍結資料均不改寫。
