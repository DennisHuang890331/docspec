## Purpose

向查核者說明一次 check 實際執行的機械檢查、引用來源可讀性與尚未執行的審查，讓結構通過不被誤解為正文同步、語意正確或交付完成；保留原完成條件及非阻擋診斷。

## ADDED Requirements

### Requirement: 範圍說明與判定一致
文字與 JSON SHALL 使用同一份版本化 coverage，分清全專案結構、機械引用、正文準備狀態、軟體問題、語意及交付審查。

#### Scenario: 過時預覽仍被掃描
- **WHEN** 選定 change 的預覽存在但過時
- **THEN** 引用掃描標為 performed，正文標為 deferred 並列既有原因，不改原 ok 或退出碼。

#### Scenario: 缺正文或未評估同步
- **WHEN** 正文不存在或正式正文同步未評估
- **THEN** 缺正文標為未掃描與 deferred，存在的正式正文同步標為 not-assessed；語意與交付均 not-performed。

### Requirement: 查詢保持唯讀與完成邊界
範圍輸出 MUST NOT 改寫來源或執行測試，article 只縮小 index；軟體問題仍獨立列出，缺必要證據不得解讀成完成。

#### Scenario: 指定單篇但另一篇有錯
- **WHEN** 查某篇而另一篇有死引用
- **THEN** 全專案結構仍失敗，coverage 包含所有受檢文章。

#### Scenario: 文件與軟體獨立
- **WHEN** 文件結構通過而軟體有問題
- **THEN** 保留文件通過、software issues 與既有非零退出碼；不新增文件定版阻擋。
