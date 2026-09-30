"""docspec handover — 交接單：一份、每次整份重寫（2026/09/30 裁定，取代 `docspec brief`）。

- `docspec handover`：印出目前的交接單，並指向現況（`docspec roadmap`）與待裁定的問題。
- `docspec handover write`：整份重寫交接單。舊的內容不保留——做完的事不需要留。

現況由 roadmap 與各項紀錄推導，不寫進交接單；交接單只記系統推導不出來的事。
"""

from __future__ import annotations

import argparse
import sys

import yaml

from dspx.commands.governance._gov_common import emit_json, fail, open_layout
from dspx.engine import governance as gv
from dspx.engine import handover as ho
from dspx.engine.config import lang_subtag

NAME = "handover"
HELP = ("governance: the handover note — one note, rewritten in full at every handover (what was "
        "done, what is in progress, promises to the owner, cautions, next); current status is "
        "`docspec roadmap`")

_TITLES = {
    "zh": {"title": "交接單", "none": "（還沒有交接單。結束一段工作、上下文快滿或換 agent 之前，用 "
           "`docspec handover write` 寫一份。）",
           "done": "這段做了什麼", "in-progress": "進行中（派了誰、在等誰）",
           "promises": "答應使用者的事", "cautions": "要注意的事", "next": "下一步",
           "status": "現況看 `docspec roadmap`", "pending": "待使用者裁定的問題：{n} 個（`docspec question list`）"},
    "en": {"title": "Handover note", "none": "(No handover note yet. Before you end a stretch of work, run "
           "out of context or hand over, write one with `docspec handover write`.)",
           "done": "Done in this stretch", "in-progress": "In progress (who was assigned what, waiting on whom)",
           "promises": "Promised to the owner", "cautions": "Watch out for", "next": "Next",
           "status": "Current status: `docspec roadmap`", "pending": "Questions awaiting the owner: {n} (`docspec question list`)"},
}


def _lang(layout) -> str:
    try:
        cfg = yaml.safe_load((layout.planning_home / "config.yaml").read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        cfg = {}
    return "zh" if lang_subtag(cfg.get("language")) == "zh" else "en"


def run(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="docspec handover", description=HELP)
    sub = p.add_subparsers(dest="op")
    w = sub.add_parser("write", help="rewrite the whole handover note (the old note is replaced)")
    for flag, hlp in (("done", "what was done in this stretch"),
                      ("in-progress", "work in progress: who was assigned what, waiting on whom"),
                      ("promise", "something promised to the owner"),
                      ("caution", "a trap, an environment fact, a reason to be careful"),
                      ("next", "the next step")):
        w.add_argument(f"--{flag}", action="append", default=[], help=f"{hlp} (repeatable)")
    w.add_argument("--from", dest="from_file", default=None,
                   help="YAML file with keys done / in-progress / promises / cautions / next (lists)")
    w.add_argument("--by", default=None, help="tool prefix: claude|gpt|gemini (auto-detected)")
    p.add_argument("--json", dest="as_json", action="store_true")
    args = p.parse_args(argv)
    layout = open_layout()
    if layout is None:
        return 1
    try:
        if args.op == "write":
            if args.from_file:
                try:
                    data = yaml.safe_load(open(args.from_file, encoding="utf-8")) or {}
                except (OSError, yaml.YAMLError) as exc:
                    return fail(f"cannot read {args.from_file}: {exc}")
                if not isinstance(data, dict):
                    return fail(f"{args.from_file}: expected a mapping with keys {', '.join(ho.FIELDS)}")
                note = {k: data.get(k) if isinstance(data.get(k), list) else
                        ([data[k]] if data.get(k) else []) for k in ho.FIELDS}
            else:
                note = {"done": args.done, "in-progress": args.in_progress, "promises": args.promise,
                        "cautions": args.caution, "next": args.next}
            path = ho.write(layout, note, tool=gv.detect_tool(args.by))
            print(f"handover note rewritten: {path.relative_to(layout.project_root)}")
            return 0
        note = ho.load(layout)
        pending = 0
        if gv.has_governance(layout):
            gov = gv.load_governance(layout)
            pending = sum(1 for q in gov.questions
                          if gv.question_effective_status(q, gov) in ("open", "needs-explanation"))
        if args.as_json:
            emit_json({"note": note, "pending-questions": pending})
            return 0
        t = _TITLES[_lang(layout)]
        if note is None:
            print(t["none"])
        else:
            print(f"# {t['title']}（{note.get('written-at')}，{note.get('written-by')}）")
            for key in ho.FIELDS:
                items = note.get(key) or []
                if items:
                    print(f"\n## {t[key]}")
                    for it in items:
                        print(f"- {it}")
        print(f"\n{t['status']}")
        if pending:
            print(t["pending"].format(n=pending))
        _print_outdated(layout.project_root)
        return 0
    except gv.GovernanceError as exc:
        return fail(str(exc))


def _print_outdated(project_root) -> None:
    """專案裡的 skill 或 AGENTS.md 協作區塊比這個 docspec 舊時提醒（不擋）。"""
    try:
        from dspx.commands.maintenance._skills import outdated_installs
        stale = outdated_installs(project_root)
    except Exception:  # noqa: BLE001
        return
    if stale:
        shown = ", ".join(stale[:4]) + (f" (+{len(stale) - 4} more)" if len(stale) > 4 else "")
        sys.stderr.write(f"\nnote: this project's skills / rules are older than the installed docspec "
                         f"({shown}). Run `docspec init --agents-md` to refresh them "
                         f"(project settings and content are kept).\n")
