"""docspec approve — 使用者專用：一次處理所有「待批准」事項。

待批准事項＝待確認的重大裁定（major ruling, pending）＋ agent 送出的申請（例如發布）。
三層防護（2026/09/29 裁定「乙＋丁」）：
  1. hook 攔截：各家 agent 的防護擋下 agent 呼叫本指令（`docspec hook guard`）。
  2. 只接受真人互動終端機：非互動、或任一家 agent 的執行環境記號在場 → 拒絕。
  3. 留紀錄：確認時間與 git 使用者名稱寫進紀錄。
誠實的限制：刻意偽造終端機的程式仍可能繞過；這套擋的是順手或誤會造成的越權。

`--list` 只列出待批准事項（任何人都能執行，agent 可以用它告訴使用者還有什麼要批）。
"""

from __future__ import annotations

import argparse
import sys

from dspx.commands.governance._gov_common import emit_json, fail, label, open_layout, public
from dspx.engine import governance as gv

NAME = "approve"
HELP = ("owner only: review and approve pending items (major rulings, publish requests) in an "
        "interactive terminal; --list shows what is pending")


def pending_items(gov: gv.Governance) -> list[tuple[str, dict]]:
    items = [("ruling", r) for r in gov.rulings if r.get("status") == "pending"]
    items += [("request", q) for q in gov.requests if q.get("status") == "pending"]
    return items


def _question_titles(gov: gv.Governance, ids: list[str]) -> str:
    by = {str(q.get("id")): q for q in gov.questions}
    return "、".join(label(by[i]) if i in by else i for i in ids)


def _show(kind: str, rec: dict, gov: gv.Governance, n: int, total: int) -> None:
    print(f"\n[{n}/{total}] ", end="")
    if kind == "ruling":
        print(f"裁定（{rec['id']}，{rec.get('recorded-by')} 轉記，{rec.get('date')}）")
        print(f"  原話：「{rec.get('quote')}」")
        if rec.get("interpretation"):
            print(f"  agent 的解讀：{rec['interpretation']}")
        if rec.get("answers"):
            print(f"  回答的問題：{_question_titles(gov, gv._as_list(rec.get('answers')))}")
        if rec.get("supersedes"):
            print(f"  取代先前的裁定：{'、'.join(gv._as_list(rec.get('supersedes')))}")
        if rec.get("provisional"):
            print("  （這是暫定）")
    else:
        print(f"申請（{rec['id']}，{rec.get('requested-by')} 送出，{rec.get('requested-at')}）")
        print(f"  {rec.get('summary')}")


def _ask(prompt: str) -> str:
    while True:
        try:
            ans = input(prompt).strip().lower()
        except EOFError:
            return "s"
        if ans in ("y", "n", "s", "q"):
            return ans
        print("  請輸入 y（同意）、n（不同意）、s（略過）或 q（結束）")


def _decide_ruling(layout, rec: dict, ans: str, who: str) -> None:
    if ans == "y":
        rec["status"] = "confirmed"
        rec["confirmed-at"] = gv.today()
        rec["confirmed-by"] = who
    else:
        rec["status"] = "rejected"
        try:
            reason = input("  不同意的原因（可留空）：").strip()
        except EOFError:
            reason = ""
        if reason:
            rec["rejected-reason"] = reason
    gv.write_record(layout, "ruling", rec)
    from dspx.engine.impact import flag_after_change
    flagged = flag_after_change(layout, str(rec["id"]), tool="user")
    word = "已確認" if ans == "y" else "已駁回"
    extra = f"；{len(flagged)} 個受影響項目標為可疑" if flagged else ""
    print(f"  → {word}{extra}")


def _decide_request(layout, rec: dict, ans: str, who: str) -> None:
    rec["decided-by"] = who
    rec["decided-at"] = gv.today()
    if ans == "n":
        rec["status"] = "rejected"
        gv.write_record(layout, "request", rec)
        print("  → 已駁回")
        return
    rec["status"] = "approved"
    gv.write_record(layout, "request", rec)
    rc = execute_request(rec)
    if rc == 0:
        rec["status"] = "done"
        gv.write_record(layout, "request", rec)
        print("  → 已批准並完成")
    else:
        rec["status"] = "pending"
        rec["reason"] = f"execution failed (exit {rc}); fix and approve again"
        gv.write_record(layout, "request", rec)
        print(f"  → 已批准，但執行失敗（離開碼 {rc}），申請保留為待批准")


def execute_request(rec: dict) -> int:
    """執行已批准的申請。目前只有 publish。"""
    if rec.get("action") == "publish":
        from dspx.commands.deliverable import publish as publish_cmd
        payload = rec.get("payload") or {}
        argv = [str(payload["article"]), "--level", str(payload.get("level", "patch"))]
        if payload.get("note"):
            argv += ["--note", str(payload["note"])]
        if payload.get("set_version"):
            argv += ["--set-version", str(payload["set_version"])]
        if payload.get("allow_noop"):
            argv.append("--allow-noop")
        return publish_cmd.run(argv)
    sys.stderr.write(f"docspec: unknown request action \"{rec.get('action')}\"\n")
    return 1


def run(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="docspec approve", description=HELP)
    p.add_argument("--list", action="store_true", help="only list pending items (no decisions)")
    p.add_argument("--json", dest="as_json", action="store_true", help="with --list: JSON output")
    args = p.parse_args(argv)
    layout = open_layout()
    if layout is None:
        return 1
    try:
        gov = gv.load_governance(layout)
        items = pending_items(gov)
        if args.list:
            if args.as_json:
                emit_json({"pending": [{"kind": k, **public(r)} for k, r in items]})
            elif not items:
                print("（沒有待批准事項）")
            else:
                print(f"待批准事項：{len(items)} 項（請使用者在終端機執行 `docspec approve`）")
                for k, r in items:
                    print(f"- {'裁定' if k == 'ruling' else '申請'}：{label(r)}")
            return 0
        if gv.is_agent_environment() or not (sys.stdin.isatty() and sys.stdout.isatty()):
            return fail("`docspec approve` is for the project owner in an interactive terminal; "
                        "agents cannot run it. Agents: use `docspec approve --list` to tell the "
                        "owner what is pending.", 2)
        if not items:
            print("沒有待批准事項。")
            return 0
        who = gv.git_user(layout.project_root)
        print(f"待批准事項共 {len(items)} 項。y＝同意，n＝不同意，s＝略過，q＝結束。")
        for n, (kind, rec) in enumerate(items, 1):
            _show(kind, rec, gov, n, len(items))
            ans = _ask("  同意(y) / 不同意(n) / 略過(s) / 結束(q)：")
            if ans == "q":
                break
            if ans == "s":
                continue
            clean = public(rec)
            if kind == "ruling":
                _decide_ruling(layout, clean, ans, who)
            else:
                _decide_request(layout, clean, ans, who)
        return 0
    except gv.GovernanceError as exc:
        return fail(str(exc))
