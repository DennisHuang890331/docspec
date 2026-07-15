# history.md（退場散文細節，可選；主要服務舊 corpus）

history.yaml 的**散文半**：yaml 管精瘦索引（id/狀態/連結）；**md 管「為什麼」的散文細節**——
讀者是 **develop（回顧）與 factcheck（判脈絡）兩個 agent**，draft 永不讀、publish 不投影。
可有可無（沒散文就只留 yaml 摘要）。
注意（contract-slimming 後）：死決策**就地留在 decisions.yaml**（rationale/rejected 原欄保留、
不再被剝離搬移），所以新流程不再生成本檔——它服務舊 corpus 既有段落與 `_archive/` 封存包內的記錄，
`docspec show <id>` 照讀。

## 格式（乾淨 `## <id>`，純 id）
對某筆退場「決策」開一段，標題＝**純 id**（不帶標題、不夾破折號）：
```markdown
## dec-xxxx
（一句話摘要）**退場於** <change>。**輸給** <勝出選項>。
<為何丟的散文：理由、證據、行號…>
```
段內要分小節用 `###`／粗體，**別再用 `## `**（`## ` 開頭會被當成新的退場 id）。

## 對應＝同一個 id（非硬綁）
`docspec show <id>` 撈本檔 `## <id>` 段當該決策的 rationale；對應靠**同一個 id**（標題第一個 token），
不存指向字串、不解析散文。找得到就給、找不到就只回 yaml 摘要；**孤兒段最多 lint 提醒，不是 check 硬閘**。

## 整節退場不寫這裡
整節退場的「細節」＝它被封存的資料夾本身（history.yaml 那筆 kind:section 的 `archive` 連結）。
所以**整節退場不開 history.md 段**；本檔只給「決策退場」的散文。
