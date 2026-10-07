## Context

Windows 實測的原官方 JSON 與已安裝 console 證明 `artispec question show Q-gpt-2` 返回 2。獨立測試先對目前來源跑出兩平台各四個失敗；ruling、info、decision 的三個既有入口正例通過。同一個泛用命令模板也會對明確引用的 W／M 產生不存在的 `work show`／`milestone show`。

## Decisions

按紀錄種類投影到現有唯讀入口。問題使用包含已回答及撤回紀錄的完整列表；工作使用單一工作摘要；里程碑使用該里程碑的 roadmap 篩選。保持原 id、引用、來源、診斷與狀態推導，不將命令提示視為完成或授權。

這個修正不增加新查詢介面。錯誤連結的新增拒絕及移除操作屬另一份待裁定方案，不在此變更實作。

## Verification

測試角色先建立真 CLI 子程序的正反案例，將摘要提供的命令原樣執行，核對原紀錄與全專案前後指紋。擴充後保留原七案的 RED 來源與結果，固定測試後由實作者修提示，再跑兩平台相關及完整回歸、wheel 安裝與 OpenSpec strict。

原 wheel、案例、失敗紀錄及 checkpoint 保留。若後續更新實測安裝環境，須在作者停止的階段分界保存舊／新 wheel 指紋；不宣稱全程使用同一版本。
