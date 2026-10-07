"""Prepare a synthetic exam workflow; never run the product or claim acceptance.

Only README, an ambiguous opening task and synthetic CSV enter the project.
The controller retains the owner answers, later event and oracle outside it.
Record actual participant launch inputs before starting a fresh conversation.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import uuid


def case_contract() -> dict:
    """Return the same agreed facts on both platforms, without filesystem work."""
    return {
        "task": (
            "# 合成專案任務\n\n"
            "我們學校段考排考場座位每次都很麻煩，幫我做個系統。\n\n"
            "先閱讀提供的 README；使用已安裝的 artispec。students.csv 是合成輸入。\n"
            "README 引用的完整操作指南有唯讀副本：../reference/docs/user-guide.md。\n"
            "對影響設計而尚未說明的需求向負責人提問；已有明確資料直接引用。\n"
            "依工具流程登記工作、記錄依據並完成交付。測試由獨立測試會話撰寫與簽收，"
            "實作者不能修改它的測試。使用真實身分，不冒用其他工具或負責人。\n"
            "先回報你需要釐清的內容，等待負責人的回答再完成相關設計。\n"
        ),
        "owner_persona": (
            "# 控制器專用：合成負責人\n\n"
            "所有學生、學校與需求均為合成；不使用真實資料。只回答接手者實際提出的問題，"
            "不要主動告知解法、紀錄編號或評分答案；原始問答另存案外。\n\n"
            "persona 未涵蓋的要求答覆尚未裁定，不臨時創造隱藏需求。實作者可提出普通"
            "實作選擇，但不能記為負責人已裁定；影響既有範圍或限制者才回到真實負責人。\n\n"
            "- 規模：兩班各八人，總共 16 人。兩間教室 R1、R2，各 4×4 個座位。\n"
            "- 功能：匯入 CSV、安排座位、輸出各考場座位表。CSV 欄位 class、number、name "
            "分別為班級、座號、姓名；以班級加座號識別學生。\n"
            "- 規則：每位學生恰好排一次、不漏人、不重複、不超過教室容量；同班學生不能"
            "前後左右相鄰。斜角不算相鄰；未要求隨機、公平報表或固定使用每間教室。\n"
            "- 操作：老師使用 Windows，離線、雙擊啟動，不接受要求老師安裝 Python 或"
            "開發工具。開發環境可安裝工具；先釐清交付方式，再提出符合限制的方案。"
            "Linux 是另一個實際驗證環境；它的測試不能代替 Windows 雙擊交付的驗證。\n"
            "- 文件：一份簡短操作手冊，涵蓋輸入、步驟、規則、限制；含一張座位表示意圖，"
            "必須與實際輸出一致。需要 PDF 與 proof。\n"
            "- 明確授權：本案例的合成操作手冊在檢查通過後可以定版、輸出 PDF 及 proof；"
            "修改後仍須依工具流程產生新版。此授權只適用本合成案例。\n"
            "- 不做特殊考生、手動指定座位、學生查詢、帳號、補考與公平報表。\n"
            "- 初版交付前不提供後續變更；若身分判定或環境阻擋，記錄實際原因，不偽造完成。\n"
        ),
        "change_event": (
            "# 初版驗收後才注入的一次變更\n\n"
            "初版交付已核對後，負責人只追加一次要求：每間教室的座位表也要顯示"
            "教室容量與剩餘座位數，剩餘數為容量減去實際已安排人數。\n"
            "操作手冊同步說明這兩個欄位，其餘已裁定需求不變。\n"
            "先記錄變更、登記或連結既有工作並寫交接；在這次變更尚未完成時換全新會話接手。"
            "不得先完成變更再將接手偽裝為未完成案例。\n"
        ),
        "handover_task": (
            "# 全新會話接手任務\n\n"
            "你沒有前一段對話。請閱讀專案的 README 與生成規範，使用已安裝的 artispec "
            "盤點交接、roadmap 及相關工作摘要，必要時查原始紀錄。\n"
            "先指出目前有效依據、仍有效的原引用、測試簽收、最新證據及文件定版狀態，"
            "提供實際來源並沿用既有工作；盤點後才重寫交接。\n"
            "接續尚未完成的工作至第二次交付；測試仍由獨立測試會話處理，"
            "不得修改它的測試、冒用身分或宣稱未實際驗證的結果。\n"
        ),
        "students_csv": "class,number,name\n" + "".join(
            f"{class_name},{number},Synthetic-{class_name}-{number:02d}\n"
            for class_name in ("A", "B") for number in range(1, 9)
        ),
        "oracle": {
            "students": {"count": 16, "classes": 2, "per_class": 8,
                         "csv_columns": ["class", "number", "name"]},
            "rooms": [{"id": name, "rows": 4, "columns": 4} for name in ("R1", "R2")],
            "adjacency": {"orthogonal": True, "diagonal": False},
            "initial_output_fields": ["class", "number", "name"],
            "change_output_fields": ["capacity", "remaining"],
            "document": {"manual_count": 1, "seating_diagram_count": 1,
                         "pdf_proof_required": True, "synthetic_freeze_authorized": True},
            "acceptance": [
                "Questions elicit operation, platform, installation and offline restrictions.",
                "Recorded work and sources reflect actual owner answers, not hidden oracle guesses.",
                "Independent author signs tests before implementation; implementer preserves tests.",
                "Engine obtains valid passing evidence; software change is archived.",
                "Seat output contains each input identity once, within capacity and adjacency rules.",
                "Windows offline double-click delivery is actually tested on Windows.",
                "Manual is frozen; PDF and proof exist and depict the actual seating output.",
                "Exactly one change follows verified first delivery; fresh handover occurs while unfinished.",
                "Fresh participant cites sources, reuses work and updates handover after inspection.",
                "Second delivery verifies capacity/remaining and updates the manual version.",
            ],
        },
    }


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cli", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--platform", choices=("windows", "linux"), required=True)
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[2]
    cli, wheel = (p.resolve() for p in (args.cli, args.wheel))
    # Resolving a venv's interpreter symlink loses that venv's pyvenv.cfg context.
    python = args.python.absolute()
    for path in (cli, python, wheel, repo / "README.md", repo / "README.zh-TW.md",
                 repo / "docs/user-guide.md",
                 Path(__file__).with_name("record_installed_command.py")):
        if not path.is_file():
            parser.error(f"required input is not a file: {path}")
    contract = case_contract()
    canonical = json.dumps(contract, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":")).encode("utf-8")
    created = datetime.now(timezone.utc)
    run = args.output_dir.resolve() / (
        "run-" + created.strftime("%Y%m%d-%H%M%S-%f") + "-" + uuid.uuid4().hex[:8])
    run.mkdir(parents=True, exist_ok=False)
    project = run / "project"
    project.mkdir()
    reference = run / "reference/docs"
    reference.mkdir(parents=True)
    shutil.copyfile(repo / "docs/user-guide.md", reference / "user-guide.md")
    for name in ("README.md", "README.zh-TW.md"):
        shutil.copyfile(repo / name, project / name)
    (project / "TASK.md").write_text(contract["task"], encoding="utf-8", newline="\n")
    (project / "students.csv").write_text(contract["students_csv"], encoding="utf-8", newline="\n")
    for name, key in (("owner-persona.md", "owner_persona"), ("change-event.md", "change_event"),
                      ("handover-task.md", "handover_task")):
        (run / name).write_text(contract[key], encoding="utf-8", newline="\n")
    _write_json(run / "oracle.json", contract["oracle"])
    _write_json(run / "recorder-config.json", {
        "executable": str(cli), "project": str(project), "log": str(run / "commands.jsonl"),
    })
    shutil.copyfile(Path(__file__).with_name("record_installed_command.py"),
                    run / "record_installed_command.py")
    shutil.copyfile(Path(__file__).with_name("workflow_runtime.py"), run / "workflow_runtime.py")
    _write_json(run / "manifest.json", {
        "contract_version": 1, "case_id": "exam-seating-small",
        "created_at": created.isoformat(), "platform": args.platform, "project": str(project),
        "cli": str(cli), "python": str(python), "wheel": str(wheel),
        "wheel_sha256": _hash(wheel.read_bytes()), "contract_sha256": _hash(canonical),
        "participant_launches": [], "agent_workflow_executed": False,
        "before_files": {p.relative_to(project).as_posix(): _hash(p.read_bytes())
                         for p in sorted(project.iterdir())},
        "reference_files": {"reference/docs/user-guide.md": _hash((reference / "user-guide.md").read_bytes())},
        "preparation_only": True,
        "note": "No product process launched. Paths and hashes do not prove installation or acceptance.",
    })
    print(json.dumps({"run": str(run), "project": str(project), "prepared_only": True},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
