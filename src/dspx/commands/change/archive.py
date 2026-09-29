"""docspec archive <change> — 一次修改做完：套用並收進歷史（文件與軟體共用的入口）。

程式依 change 名稱判斷它屬於哪個領域，兩邊的檢查各自保留：
- 文件 change（`docspec/changes/<id>/`）→ 等同 `docspec change archive`：每個 target 都完成、
  草稿套用回正式內容、搬進 `changes/_archive/`；`--abandon --reason` 放棄。
- 軟體 change（`docspec/software/changes/<id>/`）→ 等同 `docspec code archive`：任務都有證據、
  該有的驗收都有、規格沒有衝突，差異併回正式規格、寫基線、搬進 `_archive/`；`--dry-run` 只檢查。
change 名稱跨領域不可重複（建立時就擋），所以不會判斷錯。
"""

from __future__ import annotations

import sys

NAME = "archive"
HELP = ("finish a change — document or software, detected by name: apply it and move it into "
        "history (--dry-run for software checks, --abandon --reason for document changes)")


def domain_of(layout, cid: str) -> str | None:
    """'doc' / 'software' / 'both'（舊專案可能同名）/ None。只看進行中的 change。"""
    from dspx.engine import change as doc_chg
    from dspx.engine.software import changes as sw_chg
    doc = doc_chg.change_state(layout, cid) == doc_chg.STATE_ACTIVE
    sw = sw_chg.change_state(layout, cid) == "active"
    if doc and sw:
        return "both"
    return "doc" if doc else "software" if sw else None


def name_taken_elsewhere(layout, cid: str, domain: str) -> str | None:
    """建立 change 時用：名稱在另一個領域已被使用（任何狀態）→ 回說明，否則 None。"""
    from dspx.engine import change as doc_chg
    from dspx.engine.software import changes as sw_chg
    if domain == "software" and doc_chg.change_state(layout, cid) is not None:
        return f"a document change named \"{cid}\" already exists ({doc_chg.change_state(layout, cid)})"
    if domain == "doc" and sw_chg.change_state(layout, cid) is not None:
        return f"a software change named \"{cid}\" already exists ({sw_chg.change_state(layout, cid)})"
    return None


def run(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: docspec archive <change> [--dry-run] [--abandon --reason R] [--override-drift]\n")
        print(HELP)
        return 0
    from dspx.commands._shared import BootstrapError, bootstrap
    try:
        layout, _config = bootstrap()
    except BootstrapError as exc:
        return exc.exit_code
    cid = argv[0]
    domain = domain_of(layout, cid)
    if domain is None:
        sys.stderr.write(f"docspec: no active change \"{cid}\" (document or software); "
                         f"see `docspec change status` and `docspec code change list`.\n")
        return 1
    if domain == "both":
        sys.stderr.write(f"docspec: both a document change and a software change are named \"{cid}\"; "
                         f"use `docspec change archive {cid}` or `docspec code archive {cid}`.\n")
        return 2
    if domain == "doc":
        if "--dry-run" in argv:
            sys.stderr.write("docspec: --dry-run applies to software changes; for a document change "
                             f"see `docspec change status {cid}`.\n")
            return 2
        from dspx.commands.change.change import _cmd_archive
        return _cmd_archive(argv)
    if any(a in argv for a in ("--abandon", "--override-drift")):
        sys.stderr.write("docspec: --abandon / --override-drift apply to document changes only.\n")
        return 2
    from dspx.commands.code import code as code_cmd
    return code_cmd.run(["archive", *argv])
