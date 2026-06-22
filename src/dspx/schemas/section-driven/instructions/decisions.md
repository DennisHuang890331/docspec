# 寫 decisions.yaml（本節活著的決策）

決策記憶是**留史型**：append / supersede，不就地砍。判準＝**歷史重不重要**——重要走這裡，還在 churn 的留 develop.md。

每條決策：
- `kind`：`normative`（會投影成散文裡的規範句，用 必須/MUST 等關鍵字）或 `rationale`（背景判斷/理據）。
- `status`：`proposed` / `accepted`（兩者為 active，draft 會讀其 statement）/ `superseded` / `deprecated`（退場態，等 `docspec retire` 搬去 history）。
- `statement`：決策本身（what）。draft **只讀這句**。
- `rationale`：why（給 factcheck/audit agent 讀，draft 不讀）。
- `rejected`：考慮過但否決的選項（留給 audit 當禁區，draft 不讀）。
- `supersedes`：本決策取代了哪條（填對方 id；對方標 superseded 後 retire 搬走）。

別重用 id；id 是 supersede 鏈與 realizes 引用的靶點。

**EARS 慣例（可選、非結構化欄位）**：規範決策（kind=normative）若是「觸發式」規則，`statement` **建議**寫成 EARS 句式「WHEN <觸發> SHALL <回應>」——觸發條件＋必為回應分開寫，讓 factcheck/讀者一眼能驗。這是**機器契約英文**的慣例，draft 渲成交付散文時用 config.language 自然語言重述、**不逐字抄** WHEN/SHALL。普適規則（ubiquitous，無觸發）或 rationale 不逼這格式。模糊的觸發式 ruling 會被 factcheck 開成 `clarity` 軟提示、建議改寫成 EARS。
