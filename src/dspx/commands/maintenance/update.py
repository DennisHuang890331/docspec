r"""docspec update — 檢查安裝來源、印精確更新指令；`--run` 才以 detached 子行程真跑。

★預設（無旗標）＝唯讀：讀 PEP 610 安裝來源 → 印對應精確更新指令、exit 0，不碰任何東西
（已覆蓋 90% 需求、零風險）。
★`--run`＝以 **detached 子行程**啟動 uv 更新（Windows DETACHED_PROCESS＋新 process group；
POSIX 新 session），印「以 `docspec version` 事後驗」後**立即返回**、不等待、不回報成敗。

★Windows 檔案鎖限制（記載、勿試圖繞）：正在執行的 `docspec.exe` 住在 uv tool venv 裡，
同進程/等待式 upgrade 會撞「檔案使用中」大概率失敗——所以 `--run` 必須 detached、不等待；
成敗由使用者事後 `docspec version` 驗。help 明講這點。
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

NAME = "update"
HELP = "Check the install source and print the exact update command (--run launches it in a detached process)"

_WIN_LOCK_NOTE = (
    "On Windows the running docspec.exe lives inside the uv tool venv and holds a file lock, "
    "so --run launches a DETACHED process and does NOT wait for or report the outcome — "
    "verify afterwards with `docspec version`."
)


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="docspec update", description=HELP, epilog=_WIN_LOCK_NOTE)
    parser.add_argument("--run", action="store_true",
                        help="actually launch the update in a detached child process "
                             "(default: only print the command)")
    args = parser.parse_args(argv)

    from dspx.env import _install_source
    source = _install_source.read_install_source()
    cmd = _install_source.update_command(source)

    if not args.run:
        print(f"To update docspec, run:\n  {cmd}")
        return 0

    argv_cmd = _install_source.update_argv(source)
    kwargs: dict = {}
    if os.name == "nt":
        # DETACHED_PROCESS｜CREATE_NEW_PROCESS_GROUP＝子行程脫離本 console，不被本進程結束連累。
        kwargs["creationflags"] = (
            getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200))
    else:
        kwargs["start_new_session"] = True
    try:
        subprocess.Popen(argv_cmd, **kwargs)   # 不等待（見 Windows 檔案鎖限制）
    except OSError as exc:
        sys.stderr.write(f"docspec: could not launch the updater ({exc}) — run it yourself:\n  {cmd}\n")
        return 1
    print(f"Update launched in a detached process: {cmd}\n"
          "Verify afterwards with `docspec version`.")
    return 0
