# history.yaml（退場記錄——僅存在於 _archive/ 封存包）

**不屬於活樹 leaf 契約**：live 樹的節**不建**這個檔（實證：真語料 0 檔）。它只在
`docspec retire` 的退場交易中生成、隨整節封存包住進 `corpus/_archive/`。由指令機械寫入，
**不手寫**。一種 `entries`、**id 為鍵**；散文細節不放這裡。

- **死決策不住這裡**：被推翻/否決的決策**就地留在原 `decisions.yaml`** 標 `status: superseded`/
  `deprecated`（supersede 鏈解析、deps 指紋二跳、check 的 repoint 指引都要求它在原檔可定址）。
  舊的「死決策搬 live 樹 history.yaml」流程已撤除（死決策就地留在 decisions.yaml，查用 `docspec show <article> --decisions --all-status`）。
- **整節退場**（`docspec retire` 寫、住封存包內）：`id` ＝**該節的 `concept.id`（不是路徑！）**、
  `kind: section`、`status: retired`、`statement`(一句)、`archive`(→封存資料夾的 link)、`retired-in`。
- 舊專案若仍有 live 樹 history.yaml：引擎照讀不炸（向後相容）；`docspec tidy` 會報告它為可遷移項。

對應與查詢：
- 決策的散文 rationale 在 history.md 的**乾淨 `## <id>` 段**（純 id，不帶標題、不夾破折號）；`docspec show <id>` 撈。
- **非硬綁**：靠同一個 id 對應、不存指向字串；孤兒散文段最多 lint 提醒，**不是 check 硬閘**
  （舊的「`## <id> — …` 破折號雙向綁定 check」已移除）。
- 整節退場**不寫 history.md**（細節＝archive 資料夾本身）。
- 查詢：`docspec retired`（摘要清單，含 archive link 是否解析得到）、`docspec show <id>`（單筆下鑽）。

draft 不讀；develop（re-open 回顧「為何丟」）、factcheck（判脈絡）讀。
