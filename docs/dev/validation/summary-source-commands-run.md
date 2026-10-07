# 工作摘要的來源查詢修正

日期：2026/10/04。OpenSpec change：`fix-summary-source-commands`。狀態：最小修正、獨立 GREEN、新 wheel 安裝及兩平台完整回歸已完成；未更新兩個實際考場案例的安裝版本，不代表完整考場實測已通過。

此項已按 OpenSpec 結案，原提案、設計、固定行為需求及全部勾選任務保存於 `openspec/changes/archive/2026-10-04-fix-summary-source-commands/`，現行來源查詢需求同步至 `openspec/specs/work-summary-source-commands/spec.md`。其餘五項本輪 changes 仍依各自未完成的驗收保留，不批量結案或遷移。

歸檔後將工具產生的 TBD Purpose 改為實際用途，第一次說明不足其 50 字最低長度，strict 真實返回 1（22 passed、1 failed）。已補清楚的用途說明，最終 strict 為 23 passed、0 failed；原失敗及新版結果分別保存於 `question-command-regression/openspec-archive-and-strict.json` 與 `openspec-purpose-corrected-final-strict.json`，沒有降低檢查器或改產品。

## 缺陷與實際變更

Windows 停止點的官方 `roadmap show --json` 提供 `artispec question show Q-gpt-2`，實際已安裝 console 返回 2。原完整 JSON、兩層命令紀錄及查詢前後不變的指紋保存在本輪案外資料。這是工具產生的無效提示；先前控制器自己猜錯命令另列操作錯誤，不混為同一證據。

獨立合成案例另確認明確引用 `gov:W`／`gov:M` 會產生不存在的 `work show`／`milestone show`。只更正摘要中這三類來源的命令：

- 問題：`artispec question list --all --json`，能讀回已回答及撤回的原題。
- 工作：`artispec roadmap show <W>`，沿用現有目標及推導狀態。
- 里程碑：`artispec roadmap --milestone <M> --json`，沿用相關工作及統計。

文字及 JSON 共用原摘要結果。裁定、資訊、決策、原引用、來源、封條、簽收、完成判定及角色邊界不改。不新增 CLI 子命令，也不實作待裁定的 unlink。

## 獨立 RED 與固定來源

原七案在 Windows／實際 WSL Linux 各為 4 failed、3 passed：四種問題狀態均因建議命令退出 2 失敗，三類其他治理紀錄的既有入口成功。原測試全文及兩平台 RED 紀錄保留。

加入 W／M 後，固定九案在兩平台各為 **6 failed、3 passed**。測試核對來源內容、既有狀態／統計、文字與 JSON 提示、原樣執行命令及全專案前後內容指紋；不是只斷言修正版命令字串。Windows 28.45 秒；Linux 為 Windows controller 啟動的實際 WSL runtime，144.68 秒，不稱原生 Linux agent。

- 固定九案 SHA-256：`f4b6105d5310ff51244ae4d224abf2320b39ff9b1552896fc693e9817d8e8824`。
- 修正前來源 SHA-256：`a86d96739dcd1a25a5c0ab664c70c46c498af15f60ed8edb21ded51398616ad1`。
- 修正後來源 SHA-256：`d50524b0921842eda9549fb71f5932024ee66e788b3d2c7d2aeb709fcef47bbd`。
- 新候選 wheel SHA-256：`002c1420b4326dc413b4a6afd8e2eb3d52ba2df1ea9f3e5758946dd30b3b0ae7`。

所有 RED 的測試及來源前後相同，舊七案是九案檔案的完整位元組前綴。修正前來源另保存原文；原 wheel `d88cd4…bdad` 與兩個實測案例保持原樣。此候選包尚不能代稱完整驗收通過。

固定九案及原 work-summary／v2／governance 相關回歸，Windows／實際 WSL Linux 各 **81 passed、0 skipped**，59.49／175.44 秒。兩平台測試與來源 SHA 前後相同。獨立來源差異核對確認只新增 Q／W／M 的現有查詢映射，沒有修改完成或 status 演算法。

## 新 wheel 的獨立安裝核對

Windows 原生與實際 WSL Linux 各建立全新候選環境，離線安裝並清除 PYTHONPATH。173 個套件成員的完整集合及位元組與來源／site-packages 相符；相對原 wheel 只有 work_summary.py 改變。新環境唯一入口為 artispec，自身指令目錄沒有 docspec，實際模組來源為 site-packages。原有 wheels 指紋未改，也沒有更新兩個實際考場案例。

每平台六個新合成案例、53 次真實已安裝 console 命令、24 次唯讀查詢，最終退出碼全為 0；每次查詢的完整前後檔案指紋相同。問題四狀態能讀回原題與有效狀態；工作讀回原目標與真正 done；指定里程碑讀回 1/2、in-progress 及相關工作，文字與 JSON 使用同一份 installed renderer。

第一次案外驗證額外以整份 JSON 字串排除無關 W，兩平台均返回 1。實際里程碑紀錄、items 與計數沒有混入無關工作，但既有 children 索引保留 `W-gpt-3:[]`／`W-gpt-4:[]` 空 key。原失敗完整保存；第二版只修正案外紀錄邊界判定，以新案例及新收據核對，沒有改產品／repo 測試，也不聲稱 JSON 完全沒有無關字串。最終查詢與原 filtered query 完全相同。

完整成員、安裝命令、退出碼及原失敗見 `independent-summary-source-commands-final-receipt.json/md`。此安裝結果不授權考場案例定版、接受或封存。

## 證據與未完成項目

案外根目錄沿用 `artispec-workflow-comparison-20261003-71f369f6`。RED 總核對在 `question-command-regression/independent-red-nine-review.json`；實際案例證據在 `independent-exam-reviews/windows-fixture-objection/stopped-first-delivery-review/attempt-3/generated-question-query-defect.json`。

GREEN 總核對在 `question-command-regression/independent-green-nine-review.json`，完整說明為 `independent-final-review.md`。OpenSpec strict 全部 23 passed、0 failed。

最終完整回歸：Windows **2096 passed、1 skipped**（594.08 秒）；實際 WSL Linux **2093 passed、4 skipped**（767.61 秒），兩平台 exit 0、全部 src／tests 前後指紋相同。略過仍為既有退役警告路徑，Linux 另有三個只適用 Windows 的 junction；沒有 PDF／proof 略過或放寬條件。原始 stdout／stderr、JUnit 與前後來源在 `{windows,linux}-post-summary-source-commands-full.*`，先前完整結果保留。

獨立停止點核對另確認 Windows 2328 檔及實際 Linux native 134 檔，來源／副本／原停止點 manifest 全相同，前後新增、遺失及修改皆 0。Linux 沒有使用會漏深層檔案的 UNC 遍歷。新收據為 `independent-summary-source-commands-exam-preservation-final-20261004.json`；只證明此次實際取樣的停止點，不宣稱每個歷史時刻都已取樣。兩份 README 的 SHA 亦與本批起點相同。

若後續更新實測安裝，須保存停止作者的版本分界，不回填原錯誤命令或宣稱全程同一 wheel。尚待裁定的 unlink、實際 GUI、唯一事件及新會話接手仍是完整實測的未完成項目。

非阻擋後續觀察：治理來源列沿用紀錄的原始狀態，W／M 沒有保存 status，故該列可能是 unknown；正確的 roadmap 查詢可讀回完整推導狀態。是否在治理來源列投影同一判定，留待設計討論；本修正未新增或改寫狀態算法。
