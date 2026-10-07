## 核定與既有限制

2026/10/01 負責人原話：「兩者都被記成 `gpt`，工具就認為是同一個人，拒絕 B 簽收測試。 都是GPTagent沒有關係不應該被拒絕 你可以解決一下嗎?」。核定前文所提工具與會話分開的修法。不同會話可用同一家工具；測試角色仍須獨立於實作者。不支援產品並行寫入或多人編輯，角色順序操作。

## 會話碼與共同 helper

工具偵測沿用 governance.detect_tool。新 actors helper 偵測／驗證可選會話碼：gpt 用 CODEX_THREAD_ID，沒有實際碼才使用 DOCSPEC_ACTOR_ID；兩者衝突拒絕，不生成隨機碼。碼必須是有長度限制的非空安全文字。user 沿用既有負責人例外，不宣稱驗證真人。

tests 記 written-by-instance、tasks 記 created-by-instance；signed 記 by-instance，異議記 by-instance／responded-by-instance。既有 provider 欄位保留。測試寫入與刪除採精確作者判定：新紀錄已知會話碼時，呼叫者缺碼也拒絕；舊紀錄沒碼保留原作者 provider 規則。独立性採保守判定：同 provider 必須雙方都有碼且不同才認定為不同會話，任一缺碼不推論獨立。不同 provider 維持原行為。

任務登記者仍沿用現行 created-by 作為實作角色的紀錄，不新增實際程式編輯監控。新 helper 用於 testplan set/remove/sign、異議回應與 evidence 同作者提醒；remove 原本未檢查作者，補齊同一規則。異議回應须由該測試作者或負責人處理，不能僅找第三個 agent 清除異議。

## 簽收與證據

簽收仍須存在的測試、正確函式名稱、test fingerprint 及 scenario fingerprint。已知作者會話碼的新簽收也記碼，證據檢視驗證簽收者是否為作者或既有負責人例外。測試內容改變照舊需重新簽收，actor 欄位不加入行為 scope、不讓身分變更代替測試驗證。查詢不寫入。

## 相容性与風險

不回填舊紀錄、不重新封條、不覆寫舊證據；舊資料不足以區分同 provider 會話時，給出缺碼原因與處理提示。不同 agent 若繼承同一 CODEX_THREAD_ID，仍不能宣稱獨立，須真正另啟動會話。會話碼是流程標記，使用者仍可刻意偽造環境變數；本修正不提供身分認證或安全隔離。

## 驗證

測試角色先建案例，實作者單獨修改 source。涵蓋同 gpt 雙會話成功、同會話拒絕、錯作者與缺碼拒絕、衝突碼／損壞資料、remove 防護、異議往返、舊格式、內容變更過時、CLI／JSON 與診斷一致。兩平台相關及完整回歸、OpenSpec strict、新 wheel 入口與实际簽收檢查分别記錄，不把合成碼的機械驗證稱為全新 agent 流程通過。
