## Decisions
兩個 console scripts 指向同一 Python main。生成 AGENTS 保留舊管理標記以便冪等更新，skills 名稱不改，版本提高。主要操作說明使用 artispec，歷史範例與相容入口保留。

## Risks / Trade-offs
改名不等於已取得名稱權利或修改套件索引名稱。部分既有子指令提示可保留可用的 docspec 別名，避免無關資料改寫。
