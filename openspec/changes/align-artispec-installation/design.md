## Context

見 proposal。現有 pyproject 名稱仍為 docspec；uv 因 distribution 名稱建立 tools/docspec。paths 使用舊 platformdirs 根，Windows 實際為 LOCALAPPDATA/docspec/docspec。新 LOCALAPPDATA/ArtiSpec 已含 installer wheel，因此遷移必須保留目的額外檔案。

## Goals / Non-Goals

Goals：安裝命名一致、明確遷移受控資產、來源與 dev 更新檢查正確，核對 Windows 與實際 WSL Linux，再提交推 dev。

Non-Goals：不改專案資料格式、Python import、環境變數、歷史封條；不修尚未核定的 roadmap unlink、不重寫 README、不移轉到 ArtiSpec 自用流程，不增加多人寫入支援。

## Decisions

- 根目錄採 user_data_dir("artispec", appauthor=False)，舊根另解析；平常查詢不自動搬移。
- setup --migrate-data 獨立且離線，只遷移 tinytex/fonts/pandoc/typst/drawio/cache 與 tex.lock/update-cache.json。未知根項目留原處並列未遷移項數。source 保留作回復來源。
- tex.lock 的 tinytex_root、fonts_dir、五種已知 *_path 若在舊根內才重指新根；其他欄位保留。壞 JSON 拒絕，不以空 lock 取代。
- 先預檢來源／目的、內容碰撞與連結，再到自有 staging 複製並驗 hash、複核來源。發布只建立缺少項目、不覆寫現存檔；失敗回復本次自建項目，目的 installers 等額外內容保留。來源內相對連結可保留，外部連結拒絕。
- 安裝來源讀新 distribution；Git 更新及 init 檢查使用 dev。套件 repo URL仍為 docspec，不能替換成不存在的 artispec repo。
- 新輪先在隔離 tool 環境驗安裝及舊包升級；本機停止執行本工具後才卸舊 uv tool 並裝新包，保留舊 wheel 供必要回復。不手工改 uv venv 名稱。

## Risks / Trade-offs

需要暫存空間 → 預檢並在發布前完成內容核對；舊來源保留，避免升級損失。目的有衝突 → 報錯、不覆寫。來源／目的可能是連結或互相包含 → 核對解析絕對路徑與內外連結，不複製外部資料。

本輪安裝／機械驗證不能替代前輪完整工作流驗收；報告持續分開原失敗、環境與 agent 表現。

## Migration Plan

建立新 wheel、兩平台隔離安裝／舊包升級與合成資產遷移；完整回歸及 strict 通過後更新本機工具、明確遷移資產、doctor/deep 核對。同步共享 wheel 與安裝說明。審查全部未提交成果不含真實資料，整理提交並推 dev；原歷史紀錄保持。
