<div align="center">

<img src="docs/assets/logo.png" alt="ArtiSpec 標誌" width="160">

# ArtiSpec

**用規格驅動文件與軟體的系統工程。**

[English](README.md) · 繁體中文

![Python](https://img.shields.io/badge/python-%E2%89%A53.11-blue) ![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey)

</div>

ArtiSpec 為 AI agent 提供從決策、需求到文件、軟體與驗證證據的工作流程。它把負責人的決定、工作規劃、修改與交付紀錄連在一起，讓接手的 agent 看得出做過什麼，以及還有哪些事情需要處理。

## 一個專案，兩條工作流程

例如你需要**新增報表匯出功能，同時更新操作手冊**：

- 記錄負責人的決定與限制，讓軟體需求及文件章節連到各自的依據。
- 用同一份 roadmap 追蹤工作。文件與軟體 change 共用目錄及查詢入口，各自保留原有流程。
- 由獨立測試角色撰寫及簽收測試，引擎實際執行驗證，保存判定軟體完成的證據。
- 審查操作手冊，只有負責人明確要求才定版。每版保存正文與當版引用的圖片，PDF 和頁面校樣可重新產生。

文件與軟體各自判定完成。缺追溯連結只提醒；缺必要軟體測試或有效證據就不能完成。軟體問題會記錄，但不阻擋文件定版。

## 開始使用

支援 Windows、Linux，需 Python 3.11 以上。安裝套件名稱為 `artispec`，請[從本機 `dev` 原始碼或自行建置的 wheel 安裝](docs/user-guide.md#install-and-initialize)，這不表示已公開發布到 PyPI。既有使用者請依[升級流程](docs/user-guide.md#upgrade-an-existing-project)更換舊工具安裝，並明確遷移受管工具與字型。

在專案目錄內，依使用的 agent 工具初始化：

```text
artispec init --agents-md --tool codex --lang zh-TW
```

Claude Code 使用 `--tool claude`；英文專案使用 `--lang en`。初始化會安裝專案規範、skills 與支援的 hooks。PDF 工具和字型的安裝方式見[環境設定](docs/user-guide.md#install-and-initialize)。

**新建專案：**請 agent 先界定範圍、記錄已知決定與需求，再登記工作。例如：

> 新增報表匯出功能並更新操作手冊，請安排獨立測試角色，完成後提供驗證結果。

接著依[文件流程](docs/user-guide.md#document-workflow)或[軟體流程](docs/user-guide.md#software-workflow)工作。Skills 指導 agent 規劃、寫作、實作與審查；CLI 負責讀取及更新受管紀錄。文件的 `develop`、`apply` 是 skill 階段，不是頂層 CLI 指令。

**接手專案：**先讀交接單、找到既有工作，再查目前狀態：

```text
artispec handover
artispec roadmap
artispec roadmap show <work-id>
```

用 `artispec change` 找相關修改，再用 `artispec change show <change-id>` 看細節。這些查詢不會寫入。沿用既有工作、驗證結果，交棒時整份重寫 handover。Agent 透過交接協作；受管紀錄不支援同時寫入。

## 更多說明

- [操作指南：安裝、兩條流程與升級](docs/user-guide.md)
- [文件範例與 PDF](docs/showcase/)
- [文件版本及跨平台驗證](docs/dev/validation/document-version-storage-run.md)
- [Agent 流程實測與目前限制](docs/dev/validation/readme-workflows-run.md)

用 `artispec --help` 查看指令，或用 `artispec guide` 查看紀錄格式。完整操作指南目前為英文。

## 授權與致謝

原始碼採 [PolyForm Noncommercial 1.0.0](LICENSE)，商業使用需另行取得授權；內附元件見 [NOTICE.md](NOTICE.md)。

維護者為 Yao-Jiun Huang。設計參考 [OpenSpec](https://github.com/Fission-AI/OpenSpec)，ArtiSpec 可獨立運作；開發與驗證曾使用 Claude Code、Codex 與 Gemini agents。
