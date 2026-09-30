"""交接單（2026/09/30 裁定）：一份、每次整份重寫。

現況（進度、失敗、缺漏）由 roadmap 與各項紀錄推導，不寫在這裡；交接單只記系統推導不出來的事：
這段做了什麼、進行中的事（派了誰、在等誰）、答應使用者的事、要注意的事、下一步。
做完的事不需要留，所以每次交接都整份重寫，不追加、不會越寫越長。
存在 `docspec/governance/handover.yaml`，封條保護，只能用 `docspec handover write` 改。
"""

from __future__ import annotations

from pathlib import Path

from dspx.engine import governance as gv
from dspx.engine.layout import Layout
from dspx.engine.store import atomic_write_store

FIELDS = ("done", "in-progress", "promises", "cautions", "next")
_KIND = "handover"


def path(layout: Layout) -> Path:
    return gv.gov_dir(layout) / "handover.yaml"


def load(layout: Layout) -> dict | None:
    p = path(layout)
    if not p.is_file():
        return None
    return gv.load_record(p, _KIND)


def write(layout: Layout, note: dict, *, tool: str) -> Path:
    body = {k: [str(x).strip() for x in note.get(k) or [] if str(x).strip()] for k in FIELDS}
    if not any(body.values()):
        raise gv.GovernanceError("the handover note is empty — write at least what is in progress "
                                 "or what comes next")
    record = {"written-by": tool, "written-at": gv.today(), **{k: v for k, v in body.items() if v}}
    p = path(layout)
    p.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_store(p, gv.dump_record(_KIND, record))
    return p
