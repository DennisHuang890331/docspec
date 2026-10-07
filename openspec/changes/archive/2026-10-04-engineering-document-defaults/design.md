## Context

見 proposal 與 docs/dev/proposals/engineering-document-style.md。負責人已授權本批實作，README 除外；guide 的治理來源矛盾已另修。既有 kind/brief 與 writing-guide 足以承載用途。

## Goals / Non-Goals

統一模板、投影與 skills；不改 schema 欄位、既有手冊快照或完成算法，也不新增自動語意判斷。

## Decisions

- 調整 init 雙語模板、schema authoring 與 concept/develop/apply/factcheck；語言自然度、來源與規範效力仍保留。通用倒金字塔改按文類解釋，避免再加一份流程表。
- 專案 writing-guide 與明確 audience 優先；init 原本只在缺檔時產生 writing-guide，刷新不改為覆寫。提高有變 skills 與 AGENTS guidance 版本。
- 工程團隊是工具預設讀者，交付讀者仍取 brief；用途與事實品質由人審，不以固定關鍵字或章節當品質通過。

## Risks / Trade-offs

精簡可能隱藏限制 → 明定保留支援條件、失敗處理與未驗證範圍；既有專案尚未採用新風格 → 更新提示，不自動重寫正文。

## Migration Plan

新初始化取得新預設；既有專案 init --agents-md 刷新內建規範，writing-guide 保留。封存紀錄、證據、封條不改。
