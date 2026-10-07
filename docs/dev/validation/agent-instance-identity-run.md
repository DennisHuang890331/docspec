# 同工具不同會話的身分修正（2026/10/01）

不同 GPT 會話可分別實作與測試，已不再因同為 `gpt` 被拒絕簽收。同一會話仍不能簽收自己的實作測試。核心實作、57 項新案例、獨立審查、兩平台完整回歸與最後 wheel 檢查已完成；考場座位兩案已完成訪談、提案、真實測試簽收、引擎自動測試與文件輸出，完整交付仍未驗收。

## 1. 核定與實作

負責人原話與取代關係已記入 [設計裁定](../system-design.md)。使用 `distinguish-agent-instances` 管理，保留工具前綴、治理 ID、現有檔案及封條；未增加 store 或產品並行寫入。

[actors.py](../../../src/dspx/engine/actors.py) 共用偵測及比較：Codex 自動使用 CODEX_THREAD_ID，沒有可偵測碼才接受 DOCSPEC_ACTOR_ID；衝突或不合法碼報錯、不自行生成。新測試、任務、簽收與異議記 instance 欄位；不同已知會話可使用同 provider，已知作者的操作要求精確符合原會話。任一同 provider 紀錄缺碼時，不推論獨立。負責人例外保留，碼只供追查，不是身分認證。

CLI 的 add/set/remove/sign/object/respond、task add 與 evidence 的同作者提醒共用判定。remove 原本只檢查任務引用，現在也檢查作者。原測試作者或負責人才能回答異議，不能找第三個 agent 清除。生成中英文 AGENTS 規範與指南同步，test／implement skills 提高至 1.5；現有專案以 `artispec init --agents-md --tool <實際工具>` 刷新，既有使用者內容保留。

## 2. 獨立審查發現與修正

審查者唯讀、以記憶體資料重現：A 在尚無實作任務時先簽收，之後同 A 新增實作任務，原簽收仍為 current，通過證據可得到 done。這是合法命令順序的工具漏洞。新 instance-aware 簽收的有效性現在重用獨立性檢查，因此不重簽也不能繞過；新任務使簽收 needs-review，既有證據不能繼續算完成。

另修新 metadata 中作者／簽收者 provider 同時缺失造成 None 相等，以及非 mapping 的 signed 資料崩潰；都改成明確診斷。舊無 instance 簽收保留原讀取算法，不追溯將既有警告改成失效，歷史封條及證據 bytes 不變。actor 欄位沒有加入行為 scope，不代替測試內容或情境驗證。

獨立複查已確認：先簽後同會話實作受阻，不同已知 GPT 會話仍可簽收；同 provider 任務缺碼保守拒絕；損壞新 metadata 不誤判有效；舊格式、負責人例外、test／scenario 指紋保持。這是程式審查，不代稱完整產品流程。

## 3. 機械驗證

測試角色先建立 [test_agent_instance_identity.py](../../../tests/test_agent_instance_identity.py)，root 只修改 source／文件與包裝驗證腳本。修前 30 項的基線是 16 failed、13 setup errors、1 passed；失敗來自缺 helper、缺 instance 參數、同 provider 誤判與作者刪除漏洞。實作後 38 passed；審查缺口再補 19 項，最終 **57 passed，0 skipped**，7.46 秒。

兩平台相關回歸曾各 **159 passed**，包含既有軟體、作者權限、簽收列表、init 與 skills；這是審查修補前 checkpoint。之後同會話順序漏洞修正，root 的軟體相關 103 項通過。最終完整回歸另列實際完成結果；先前在修補前啟動的兩次 full 已中止，不採為通過證據。

修補前後的完整回歸都有保留：第一次完整跑完，各只有一處舊錯誤訊息引號格式失敗（Windows 1802 passed／1 failed／1 skipped，Linux 1799 passed／1 failed／4 skipped）。保留原格式後，相關 70 項通過，重建 wheel 並重跑完整回歸，最終結果如下：

- Windows：**1803 passed，1 skipped**，388.53 秒；JUnit `C:/Users/zxc22/AppData/Local/Temp/artispec-actor-windows-release.xml`。
- 實際 WSL Ubuntu-24.04 Linux runtime：**1800 passed，4 skipped**，467.71 秒；JUnit `/home/dennis/.cache/docspec-workflow-validation/actor-linux-release.xml`。
- 略過沿用既有已退役 group.yaml warning 案；Linux 另有三個 Windows-only NT junction 案。PDF／proof 相關測試群沒有略過，未放寬測試以消除 skip。

最終 wheel：`C:/Users/zxc22/AppData/Local/Temp/artispec-actor-wheel-release/docspec-0.1.0-py3-none-any.whl`，SHA256 `c5bc2a96ebc79b7b3a78b2d62e88d37b5c138afd7e46156921e234b86153f72c`。172 個 dspx 套件檔案與 source bytes 完全一致，入口只有 artispec。新建 Windows 與 Linux venv 安裝這個本機 wheel、export 依賴與 pytest；沒有改其他環境的套件。先前 quote 修正前的 wheel 與驗證產物保留，不拿舊 hash 代稱最後版本。

[check_agent_instances.py](../../../scripts/validation/check_agent_instances.py) 不 import source，實際呼叫已安裝入口，各平台 **34 checks／21 commands passed**。內容包括同 GPT 不同合成會話簽收、錯作者 set/remove/sign 拒絕且 bytes 不變、異議往返、引擎實際 pytest 成功得到 done、改測試後 needs-review、先簽後同會話新增實作與重簽拒絕。會話碼明示合成，這項不是全新 agent 工作流程。

- 最後 Windows 產物：`C:/Users/zxc22/AppData/Local/Temp/artispec-actor-installed-checks-windows/run-8656f62f717e4072aba7a19f3f23f5fd/`。
- 最後 WSL Linux 產物：`/home/dennis/.cache/docspec-workflow-validation/actor-installed-checks/run-d10e0c7a38e74b07860d2c7a8563dcf2/`。
- 較早兩個安裝檢查 run 保留為失敗：控制器誤用 `--added`（正確是 `--new`），是驗證腳本錯誤，不是產品失敗；修正指令後另建 run，未改需求或覆寫原紀錄。
- OpenSpec strict：**13 passed，0 failed**。

## 4. 真實 Codex 會話探測與後續實測

以本機 Codex CLI 實際各啟動一次無前文會話，只要求 shell 讀 CODEX_THREAD_ID，沒有執行產品流程。案外保存啟動命令、完整 JSONL、退出碼與答案；兩次均 exit 0，thread.started 與 shell 回報相符，分別為 `01a0f6a7-aef3-7d42-9a30-62e828ea7c99`、`01a0f6a7-e4e4-7812-8eb4-76ba9bac72df`，確實不同。這證明本機可取得真正不同的會話碼，不用冒用其他 provider。

探測紀錄：`C:/Users/zxc22/AppData/Local/Temp/artispec-actor-probe/`。不直接將這兩個已探測會話當考場案例的無前文參與者；正式案例另啟動新會話，逐項保存啟動資料。若子 agent 繼承相同 thread marker，仍不能直接當作獨立。

兩平台考場案例已另建新 run，使用 release wheel 及完整依賴 runtime；先前準備 run 保留。Windows 最新：`C:/Users/zxc22/AppData/Local/Temp/artispec-exam-workflow-windows/run-20261001-090921-373328-875cd5ee/`；Linux 最新：`/home/dennis/.cache/docspec-workflow-validation/exam-workflow-cases/run-20261001-090921-533921-178a3113/`。

兩個新的正式參與者已完成第一輪訪談（各 exit 0），接續提案階段；manifest 記為已啟動，不再是 preparation_only，但不表示通過。實際 thread IDs 為 Windows `01a0f6bb-25d7-7641-add9-64c13836784d`、Linux controller `01a0f6bb-268f-7dc1-b99e-b734313ca7f3`，各自只讀案例、公開指南與明示 recorder，沒有提供前文或 oracle。owner 的合成問答及逐次啟動資料保存在案外。尚未宣稱初版／變更／接手／第二次交付通過；Linux 仍明示 Windows controller 操作實際 WSL Linux runtime，不稱原生 Linux agent。

後續真實分工已通過簽收步驟：Windows 的獨立測試會話 `01a0f6d1-0f40-7f33-b56f-d25b491d440a` 建立並簽收 T1–T10；Linux 的獨立測試會話 `01a0f6d1-1955-7d33-847e-3beaaf240545` 建立並簽收 T1–T9。兩案原實作任務皆屬上述提案會話，工具名稱皆為 gpt，沒有冒用 claude、gemini 或 user。簽收列表全部有效，原作者／簽收者欄位與 thread.started 相符。獨立唯讀審查核對兩案 8 個測試／輔助快照檔案，當時 bytes 全部保持不變。

測試角色保留尚無實作的紅色基線，沒有把它當成功證據。兩個原實作者後續已正常收尾，自動測試引擎證據為 Windows 17 passed、Linux 21 passed，測試與輔助檔案 bytes 仍全數不變；兩份手冊皆已定版、PDF／proof，軟體仍缺實際 Windows 交付示範與接受而未封存。考場整套流程結果續記於 [流程報告](exam-seating-workflow-run.md)，不能把身分修正的完成擴大為初版交付、接手或第二次交付通過。
