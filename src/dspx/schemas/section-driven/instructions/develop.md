# 寫 develop.md（思考工作台）

這是你**自由亂想**的地方——草稿、半成形的論證、待查的疑點、代號都行。**draft 永遠不讀這個檔**（aperture 防漏的關鍵），所以這裡的亂不會污染交付物。

想清楚後**結晶**（develop → 乾淨層）：
- 範圍 / 受眾 / 深淺 / 禁區 / 版面 → 寫進 `concept.yaml`
- 拍板的決定（含 why、被否決的選項）→ 寫進 `decisions.yaml`（**按需**：本節有自己的裁決才建檔；
  沒有裁決＝不建＝合法空，別造空殼 `entries: []`）
- 消化好的素材 → 寫進 `material.md`（按需）
- 被推翻 / 否決的決策 → 在 decisions.yaml **就地**標 `superseded`/`deprecated`（留在原檔可定址；
  supersede 鏈、deps 指紋、repoint 指引都讀它——**不搬** live 樹 history.yaml）

沒結晶的就留在這。乾淨靠「萃取」達成，不靠「保持 develop 乾淨」。
