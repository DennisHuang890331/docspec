# history.yaml（退場精瘦索引）

退場記錄的**精瘦索引**（機器查、每次都載故保持小）。由 `docspec retire` / `docspec retire-section`
機械寫入，**不手寫**。一種 `entries`、**id 為鍵**；散文細節不放這裡——決策的「為什麼」放成對的
**history.md**（同 id），整節退場的細節＝它被封存的資料夾。

每筆 entry 兩種：
- **死決策**（`docspec retire` 把 decisions.yaml 標 `superseded`/`deprecated`/`rejected` 的搬入）：
  `id`（不變、穩定身份；指向 history 不算死引用）、`kind`(`normative`/`rationale`)、
  `status`(`superseded`/`deprecated`/`rejected`)、`statement`(一句 WHAT)、`retired-in`、`superseded-by`、`decided-in`。
- **整節退場**（`docspec retire-section` 寫）：`id` ＝**該節的 `concept.id`（不是路徑！）**、
  `kind: section`、`status: retired`、`statement`(一句)、`archive`(→封存資料夾的 link)、`retired-in`。

對應與查詢：
- 決策的散文 rationale 在 history.md 的**乾淨 `## <id>` 段**（純 id，不帶標題、不夾破折號）；`docspec show <id>` 撈。
- **非硬綁**：靠同一個 id 對應、不存指向字串；孤兒散文段最多 lint 提醒，**不是 check 硬閘**
  （舊的「`## <id> — …` 破折號雙向綁定 check」已移除）。
- 整節退場**不寫 history.md**（細節＝archive 資料夾本身）。
- 查詢：`docspec retired`（摘要清單，含 archive link 是否解析得到）、`docspec show <id>`（單筆下鑽）。

draft 不讀；develop（re-open 回顧「為何丟」）、factcheck（判脈絡）讀。
