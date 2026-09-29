# 第二期現行設計：軟體領域（取代 OpenSpec）

- 這是第二期的**現行版**，整合了 `phase2-design.md`（架構）、`phase2-detail.md`（細部設計與歷次裁定）、`phase2-review.md`（review 與修正）。三份舊檔保留作討論過程；內容有出入時以本檔為準。
- 更新：2026/09/30（review 修正後）。

## 1. 定位

專案分三層：
- 最外層是治理層：問題、裁定、決策、唯一的 roadmap、可疑標記。
- 底下兩個平級的領域：文件樹（原本的 docspec）與軟體領域（本期）。
- 兩個領域各自管理自己的 change，共用治理層、追溯與影響分析、一頁現況。

軟體領域的檔案全部放在 `docspec/software/`，是引擎擁有、各自封條的 YAML，只能透過 `docspec code …` 寫入。唯一例外是 `config.yaml`，由人手寫。

## 2. 目錄

```
docspec/software/
├─ config.yaml                  repo 登記、測試執行器、環境檢查、change 大小門檻（人手寫）
├─ specs/<能力>.yaml             正式規格：現在系統應該做到什麼
├─ changes/<change>/            進行中的修改
│   ├─ proposal.yaml              為什麼改、改什麼、影響哪些能力、前置 change
│   ├─ design.yaml                背景、目標、風險、遷移；決策以 gov:D-… 引用治理層
│   ├─ specs/<能力>.yaml          規格差異（只寫改到的需求或情境，含基準指紋）
│   ├─ tests.yaml                 測試規劃、簽收、測試異議（測試角色）
│   └─ tasks.yaml                 任務；status／completed-at／evidence 只由引擎寫
├─ changes/_archive/<日期>-<change>/   已完成的修改（歷史）
├─ evidence/E-<工具>-<n>.yaml   證據，一筆一檔
└─ baselines/<日期>-<change>.yaml     封存時的基線
```

## 3. 規格

- 每個能力一份規格。需求編號 R1、R2…，情境編號 S1、S2…，編號永不重用（退役的記在 `retired`）。
- 需求的規範句必須含 SHALL 或 MUST，至少一個情境（WHEN／THEN）。
- 每條需求標明驗證方法，可以是 test、demonstration、inspection、analysis 其中之一或幾種。
- 情境的 `verified-by` 列出驗證它的測試，在封存時由引擎寫入。
- 查詢一次只取需要的部分：`docspec code spec show <能力> --req R1 --json`。

## 4. 一次修改的流程與角色

1. **提案（dspx-propose）**：`code change new` → `code change design` → `code change delta`（一次一筆，例如只改 R1/S2 的 THEN）→ `code task add`（每條改到的需求都要有任務實作）。
2. **測試角色（dspx-test，必須和實作者不同的 agent）**：
   - 依 WHEN／THEN 從外部行為規劃測試（`code testplan add`），接著寫測試。
   - 寫好後簽收（`code testplan sign`）。
   - 回應實作者提出的測試異議（`code testplan respond`）。
3. **實作（dspx-implement）**：只改任務宣告的檔案，然後跑 `code evidence run <change> <任務>`。測試有問題時提出異議（`code testplan object`），不能自己改測試。
4. **驗證與封存（dspx-verify）**：
   - 執行 `code archive --dry-run`，看還有哪些問題擋著封存。
   - 審閱證據，並做語意審查：這個測試真的能證明 THEN 嗎？
   - 需要人看的需求，取得使用者驗收。
   - 最後執行 `docspec archive <change>`，並用 `code test` 跑回歸測試。

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
  - 測試檔和測試角色簽收時相同。
  - 跑的過程中檔案沒被改動。
  - 執行器產出了 JUnit 報告；沒有報告就一律不通過。
- **其他證據**：
  - 檢查、展示、分析紀錄：`code evidence add`。
  - 使用者驗收：`code evidence accept`，走對話中覆述確認。
  - 豁免：`code evidence waive`，引用一條有效裁定，並寫明什麼情況下重新打開；裁定原文會和被豁免的任務並排顯示。
- **新鮮度**：每筆證據記下任務宣告的檔案與測試檔當時的內容指紋。之後內容變了，任務退回「需重跑證據」。沒宣告檔案的任務會收到提醒，因為改程式不會觸發退回。
- **以最新為準**：同一類證據只看最新一筆。

## 6. 封存

- `code archive` 依序做這些事：
  1. 依證據刷新任務狀態。
  2. 嚴格檢查。
  3. 完整性檢查：任務都完成或豁免；檢查、展示類需求要有使用者驗收或豁免。
  4. 在副本上套用差異，併入 `verified-by`。
  5. 寫入規格、寫入基線、把資料夾搬進 `_archive/`。
- 寫到一半失敗會全部還原。
- 兩個 change 改到同一處：後封存的那個因基準指紋不符而停下，不會覆蓋。
- 被修改的情境，舊的 `verified-by` 會換成這次規劃的測試，被拿掉的舊測試列出來交給測試角色。

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
- **文件章節**可以 `realizes: [req:…]`。需求內容變了，章節會轉為需要更新。
- **`docspec brief`** 有「軟體開發」一段。

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

- **身分只靠工具名稱**（claude、gpt、gemini）：`--by` 可以冒充，程式只記錄和提醒。
- **驗收確認的真實性**：確認文字由 agent 寫入，程式無法證明出自使用者。和第一期「對話中覆述確認」相同。
- **封條只防不小心手改**：直接呼叫程式內部，可以寫出假紀錄。真正的防線是 CI 獨立重跑（`docspec code test`）。封存前不強制重跑。
- **改 `conftest.py` 或 pytest 設定作弊**：簽收只保護測試檔本身。
- **程式偵測「正在測試」而作弊**：只能靠驗證時的語意審查。

## 10. 文件與專案層級的配套（2026/09/30 裁定）

- **一個 `docspec archive <change>`**：文件 change 和軟體 change 共用一個入口，程式依名稱判斷是哪一種，兩邊的檢查各自保留。change 名稱跨領域不可重複，建立時就會擋下。舊的 `docspec change archive`、`docspec code archive` 仍然可以用。
- **定版改名 `docspec freeze`**（舊名 publish 保留為別名）：
  - 原本寫在 skill 裡要 agent 自己做的檢查，全部併進指令：每一節都寫好、沒有待更新；check 與 lint 無錯誤；快照不含殘留標記。
  - factcheck 沒跑過只提醒，不擋。
  - 沒給 `--level` 時自動建議：章節有增減用 minor，否則 patch。
  - 週報這類文件可用日期當版本：`--date-version`，或在 config 的 `date_versions` 列出文件；同一天只能定一版。
  - 只在使用者明確要求時執行。
  - dspx-publish skill 拿掉。
- **change 預覽標示草稿**：預覽檔的檔頭寫明「草稿，尚未定版」與對應的 change。
- **排版**：`docspec export <文件>` 一個指令產出 PDF，版型用專案設定。dspx-release 只在使用者說排版不對時使用，只處理被指出的問題。
- **專案基線**（系統設計 SR10）：
  - 甲：每次 `docspec freeze`，自動記下當下的軟體規格指紋、各程式 repo 的 commit、進行中的軟體 change、有效的專案決策（`docspec/baselines/documents/<文件>@<版本>.yaml`）。查詢：`docspec baseline doc <文件> <版本>`。
  - 乙：`docspec baseline <名稱>`，交付時把整個專案一次釘住：所有文件目前的定版版本（以及是否有尚未定版的修改）、軟體規格、各 repo 的 commit、有效決策、還開著的 change；有需要注意的地方會一併列出。名稱不可重複，寫了就不改。查詢：`docspec baseline list`、`docspec baseline show <名稱>`。
  - 基線檔封條保護，hook 擋手改。
- **派工規範**：`docspec init --agents-md` 在根目錄 AGENTS.md 寫入協作規範區塊，語言依專案 config 的主語言。dspx-govern skill 拿掉，它的固定行為寫進規範的「使用者的決定」一節。

目前的 skill：
- 文件：dspx-develop、dspx-apply、dspx-factcheck、dspx-release（只在排版不對時用）、dspx-diagram（輔助）。
- 軟體：dspx-propose、dspx-test、dspx-implement、dspx-verify。

## 11. 留給第三期

- 同一個 change 在兩個分支各加任務，`tasks.yaml` 合併時會衝突，而且是封條檔，不能手動合併。
- 證據編號在兩個分支會撞號（和治理層編號同一個問題）。
