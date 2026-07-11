# 寫 concept.yaml（末節的治理與結構契約）

concept 是這一末節的**身份與寫作信封**——draft 之後只在這個信封裡寫散文。它是**覆寫型**：改 scope 就地更新、不留史（要留史的判斷請走 decisions.yaml）。

填寫要點：
- `concept`：一句話講清「這節到底在說什麼」。這是 aperture 核心——draft 靠它定錨。
- `brief`：寫作世界邊界（**鍵固定英文、值用專案語言**）：`audience`（寫給誰）、`depth`（多深入）、`breadth`（涵蓋多廣）、`forbidden`（不准寫什麼，list）、`layout`（prose / table / list…）、`kind`（可選，Diátaxis 章節型別：`explain` 論述／`how-to` 任務步驟／`reference` 查表終端／`tutorial` 教學）。`kind` 只當 **draft 提示＋audit 訊號**（型混由 factcheck 軟提示，不進 render、不是硬閘）；隨樹繼承（子省略＝沿用父）。**brief 全可選、差異制**：只填與祖先鏈不同的欄，省略＝繼承；逐字複製祖先值＝灌水（lint WARN）。root 節例外——須填滿 audience/depth/breadth。
- `must_cover`：本節非提不可的點，draft 的 checklist。
- `sources`：**只放外部出處指標**（用了哪份標準/論文/資料集，或 "Author's design"），不要把內容貼進來——內容是 material.md 的事。**⚠ 不要把「引用別節的決策」寫進這裡**：那是內部依賴、要用 `realizes:`/`governed-by:`。寫進 `sources` 的內部依賴對 staleness 隱形（上游決策被推翻時，本節不會轉 stale、散文繼續講死決策且過所有閘）——大型文件最致命的無聲漂移。`check` 偵測到 `sources` 出現專案內部 decision id 會直接擋（ERROR），逼你改用結構邊。
- `realizes`：本節散文實現了哪些決策（指向 decisions/history 的 id）＝**內部跨節依賴的家**，餵 staleness 指紋（上游決策動了→本節 stale-upstream→重渲）。
- `governed-by`：跨樹延伸——本概念延伸（治於）哪個父 concept（單向、子→父；父不存子，反向由 `docspec impact` 算出）。必須指向**活的 concept id**（kind=concept、非決策、非退場），祖先集會把父的 brief＋normative 繼承進來。

`id` / `order` 由 `docspec instructions develop <section>` 給的模板填好（結晶時連同 concept.yaml 一起寫出）；別手改 id（它是 diff 判存廢的穩定身份）。`title` 設成純章節名（會成為文件章節標題）——**不含章號前綴**（`6.`／`11、`）：章號由 render 從 order＋樹位置確定性推導注入，title 只存名稱。附錄或慣例不編號的節設 `numbering: appendix`／`none`（沿樹繼承）。
