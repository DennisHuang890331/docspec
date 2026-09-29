"""docspec brief — 一頁現況（接手的 agent 與使用者先讀這一頁）。

- `docspec brief`：印出一頁現況（上限 2000 字，白話、編號在括號）。
- `--design`：目前有效設計；`--pending`：待你裁定的問題。
- `--write`：三份檢視寫到 `docs/project/`（status.md、design.md、pending.md），整份覆寫；
  這些檔是產生物，防護會擋手改。
"""

from __future__ import annotations

import argparse

from dspx.commands._shared import BootstrapError, bootstrap, load_model
from dspx.commands.governance._gov_common import fail
from dspx.engine import governance as gv
from dspx.engine import views

NAME = "brief"
HELP = ("governance: one-page project status for handover (--design: current effective design; "
        "--pending: questions awaiting the owner; --write: regenerate docs/project/*.md)")

VIEW_FILES = {"status": "status.md", "design": "design.md", "pending": "pending.md"}


def view_dir(layout):
    return layout.docs_dir / "project"


def run(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="docspec brief", description=HELP)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--design", action="store_true", help="current effective design")
    g.add_argument("--pending", action="store_true", help="questions awaiting the owner's ruling")
    p.add_argument("--write", action="store_true", help="regenerate all views under docs/project/")
    args = p.parse_args(argv)
    try:
        layout, config = bootstrap()
        leaves = load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code
    try:
        texts = {"status": lambda: views.brief(layout, leaves, config),
                 "design": lambda: views.effective_design(layout, config),
                 "pending": lambda: views.pending_list(layout, config)}
        if args.write:
            out = view_dir(layout)
            out.mkdir(parents=True, exist_ok=True)
            for key, fname in VIEW_FILES.items():
                (out / fname).write_text(texts[key](), encoding="utf-8", newline="\n")
            print(f"views regenerated under {out.relative_to(layout.project_root)}/: "
                  f"{', '.join(VIEW_FILES.values())}")
            return 0
        key = "design" if args.design else "pending" if args.pending else "status"
        print(texts[key](), end="")
        return 0
    except gv.GovernanceError as exc:
        return fail(str(exc))
