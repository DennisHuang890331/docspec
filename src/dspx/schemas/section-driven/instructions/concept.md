# 寫 concept.yaml（末節的治理與結構契約）

concept 是這一末節的**身份與寫作信封**——draft 之後只在這個信封裡寫散文。它是**覆寫型**：改 scope 就地更新、不留史（要留史的判斷請走 decisions.yaml）。

填寫要點：
- `concept`：一句話講清「這節到底在說什麼」。這是 aperture 核心——draft 靠它定錨。
- `brief`：寫作世界邊界（**鍵固定英文、值用專案語言**）：`audience`（寫給誰）、`depth`（多深入）、`breadth`（涵蓋多廣）、`forbidden`（不准寫什麼，list）、`layout`（prose / table / list…）、`kind`（可選，Diátaxis 章節型別：`explain` 論述／`how-to` 任務步驟／`reference` 查表終端／`tutorial` 教學）。`kind` 只當 **draft 提示＋audit 訊號**（型混由 factcheck 軟提示，不進 render、不是硬閘）；隨樹繼承（子省略＝沿用父）。
- `must_cover`：本節非提不可的點，draft 的 checklist。
- `sources`：**只放指標**（用了哪份標準/文件），不要把內容貼進來——內容是 material.md 的事。
- `realizes`：本節散文實現了哪些決策（指向 decisions/history 的 id）。
- `governed-by`：跨樹延伸——本概念延伸（治於）哪個父 concept（單向、子→父；父不存子，反向由 `docspec impact` 算出）。必須指向**活的 concept id**（kind=concept、非決策、非退場），祖先集會把父的 brief＋normative 繼承進來。

`id` / `order` 由 `docspec instructions develop <section>` 給的模板填好（結晶時連同 concept.yaml 一起寫出）；別手改 id（它是 diff 判存廢的穩定身份）。`title` 設成人類可讀標題（會成為文件章節標題）。
