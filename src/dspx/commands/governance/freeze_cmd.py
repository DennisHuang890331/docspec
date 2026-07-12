"""docspec freeze — 凍結區維運（agent-facing；子動詞制，仿 `hook guard|check` 前例）。

目前唯一子動詞 `register-legacy`：把 pre-docspec 歷版登記進凍結區的**第二張白名單**
（`.freeze.yaml` 頂層 `legacy:`，與 publish 鑄造的 `frozen:` 平行——出處可稽）。

- src 在 archive 外（常態）：引擎自己搬進 `docs/archive/legacy/<name>/` 再登記
  （引擎受控路徑＝hook 分層本意：hook 擋 agent 裸 mv 進 archive、引擎指令放行）。
- src 已在 archive 內（先前手動塞入、V11 全紅的救援場景）：原地登記、不搬動。
- 防洗白鐵則：任一檔相對路徑已在 frozen∪legacy → 整批拒絕、零寫入；**無 unregister**
  （凍結區隻進不出；撤銷＝人工操作 manifest，hook 不攔人）。
- 失敗原子性：先搬完檔案、最後才**一次**批次寫 manifest——manifest 沒寫＝全部未登記，
  V11 把已搬進 archive 的檔標紅並指路重跑（原地登記模式天然收尾）。

模組名 freeze_cmd.py 避開與 dspx/freeze.py（資料模組）同名混淆（仿 skills_cmd.py 前例）。
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from dspx import freeze
from dspx.commands._shared import BootstrapError, bootstrap

NAME = "freeze"
HELP = ("frozen-area operations: `freeze register-legacy <src-dir>` registers "
        "pre-docspec legacy versions into the tamper-detection hash net")

_USAGE = (
    "Usage: docspec freeze register-legacy <src-dir> [--into <name>]\n"
    "  register-legacy  register pre-docspec legacy versions into the frozen area:\n"
    "                   moves the files into docs/archive/legacy/<name>/ and records\n"
    "                   their hashes in .freeze.yaml (src-dir already inside an\n"
    "                   archive/ folder -> registered in place, nothing is moved).\n"
    "                   Paths already registered are refused as a whole batch;\n"
    "                   there is no unregister.\n"
)


def run(argv: list[str]) -> int:
    sub = argv[0] if argv else ""
    if sub in ("-h", "--help"):
        print(_USAGE, end="")
        return 0
    if sub != "register-legacy":
        sys.stderr.write(_USAGE)
        return 2
    return _register_legacy(argv[1:])


def _register_legacy(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="docspec freeze register-legacy",
        description="register pre-docspec legacy versions into the frozen-area hash net")
    parser.add_argument("src_dir", help="folder holding the pre-docspec legacy version files")
    parser.add_argument("--into", default=None, metavar="NAME",
                        help="destination folder name under docs/archive/legacy/ "
                             "(default: the last segment of src-dir)")
    args = parser.parse_args(argv)

    try:
        layout, _config = bootstrap()
    except BootstrapError as exc:
        return exc.exit_code

    src = Path(args.src_dir)
    if not src.is_dir():
        sys.stderr.write(f"docspec: freeze register-legacy: not a directory: {src}\n")
        return 1
    files = sorted(p for p in src.rglob("*") if p.is_file() and not freeze.is_sync_junk(p.name))
    if not files:
        sys.stderr.write(f"docspec: freeze register-legacy: no files to register under {src}\n")
        return 1

    root = layout.project_root.resolve()
    try:
        src_rel = src.resolve().relative_to(root)
    except ValueError:
        src_rel = None
    in_archive = src_rel is not None and freeze.is_frozen_path(src_rel)

    # 雙模式：archive 外 → 搬進 docs/archive/legacy/<name>/；已在 archive 內 → 原地登記
    if in_archive:
        targets = {f: f for f in files}
        dest_note = src
    else:
        name = args.into or src.resolve().name
        dest_root = layout.docs_dir / "archive" / "legacy" / name
        targets = {f: dest_root / f.relative_to(src) for f in files}
        dest_note = dest_root

    # 防洗白：搬動/寫入前先整批查碰撞——任一 rel 已在 frozen∪legacy → 整批拒絕、零變動
    frozen = freeze.load_manifest(layout.planning_home)
    legacy = freeze.load_legacy(layout.planning_home)
    rels = {f: t.resolve().relative_to(root).as_posix() for f, t in targets.items()}
    collisions = sorted(r for r in rels.values() if r in frozen or r in legacy)
    if collisions:
        sys.stderr.write(
            "docspec: freeze register-legacy refused -- path(s) already registered in "
            ".freeze.yaml (the frozen area is append-only; re-registering would launder a "
            "tampered hash). Nothing was moved or written:\n")
        for c in collisions:
            sys.stderr.write(f"  ✗ {c}\n")
        return 1
    if not in_archive:
        clobber = sorted(str(t) for t in targets.values() if t.exists())
        if clobber:
            sys.stderr.write(
                "docspec: freeze register-legacy refused -- destination file(s) already exist "
                "(will not overwrite). Nothing was moved or written:\n")
            for c in clobber:
                sys.stderr.write(f"  ✗ {c}\n")
            return 1

    # 先搬完（失敗中斷＝manifest 未寫、V11 指路重跑）……
    if not in_archive:
        for f, t in targets.items():
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), str(t))
        # 搬空的來源子夾 best-effort 清掉（殘留空夾無害）
        for d in sorted((p for p in src.rglob("*") if p.is_dir()), reverse=True):
            try:
                d.rmdir()
            except OSError:
                pass
        try:
            src.rmdir()
        except OSError:
            pass

    # ……最後一步才批次**單次**寫 manifest（失敗原子性邊界；record_legacy 內再查一次碰撞兜底）
    try:
        registered = freeze.record_legacy(
            layout.planning_home, layout.project_root, list(targets.values()))
    except freeze.LegacyCollisionError as exc:
        sys.stderr.write(
            "docspec: freeze register-legacy refused -- path(s) already registered:\n")
        for c in exc.collisions:
            sys.stderr.write(f"  ✗ {c}\n")
        return 1
    print(f"registered {len(registered)} legacy file(s) under {dest_note}")
    print("  recorded in .freeze.yaml `legacy:` table (tamper/deletion now caught by lint)")
    return 0
