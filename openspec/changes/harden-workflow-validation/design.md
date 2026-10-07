## Context

前輪 recorder 本身已有 UTF-8，問題還出在外層控制器、取樣與評分。負責人已授權補強；產品資料不增加第二份狀態。

## Goals / Non-Goals

stdlib 共用 helper 可由新控制器直接使用。不要重寫舊結果、讀不到的 history、採樣中的包，或改產品完成條件。

## Decisions

- scripts/validation/workflow_runtime.py 定義 record_command(argv,*,cwd,log,phase,session,env=None,input=None)，回實際事件並追加 UTF-8 JSONL，啟動失敗 exit127。parse_codex_events(path) 回 acquisition、session、events、diagnostics；同 id 取 completed，未知或未完成列診斷。
- resolve_source(location,*,case_root,cwd=None,mappings=None) 只在已宣告根／cwd／prefix 映射下找唯一實檔，拒絕逃逸與歧義，不全樹猜 basename。
- build_manifest(root) 回 version1/files SHA/categories。分類順序：changes/archive 快照、history/journal YAML 追加歷史、tests 作者來源、docs 或 test-handover 公開投影、其他；分類不改 fingerprint。
- checkpoint_artifacts(source,destination,*,expected_manifest,manifest_path=None) 核對 before=expected=copied=after，destination 存在拒絕；新失敗取樣清除新建的不完整目標，保留來源與舊包。wait_for_condition(predicate,*,timeout,interval=.1) 等實際條件。
- 控制器保存 argv/cwd/提示 hash/真實會話與原 JSONL，核對 resume session。新紀錄器重用 helper；GUI 既有控制項探測改等條件。
- 真實重跑發現同一階段的唯讀查詢可能同時追加外部命令紀錄；追加時以各平台的跨程序檔案鎖保護完整 UTF-8 記錄，等待有期限。鎖只涵蓋紀錄寫入，不序列化產品命令或增加產品並行寫入支援。既有損壞行保留，原取得範圍仍列不完整。

## Risks / Trade-offs

雙重取樣不能保證檔案在中間改後又完全復原 → 作者先停止寫入，前後 hash 為可核對證據，不宣稱並行快照保證。JSONL 不含全部 shell → 明示取得程度，統計以實際 recorder 與可取得事件為準。

## Migration Plan

新案使用共用 helper；舊私有控制器與原失敗不改。評分、manifest、會話原檔留 repo 外，報告只記合成驗收結果。
