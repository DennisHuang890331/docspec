r"""docspec version — 一併印 程式版 + tex.lock 記的 TinyTeX 版 + pandoc 版。

讓「程式↔TinyTeX↔pandoc」版本錯位一眼可見（離線、唯讀）。
`docspec --version` 與 `docspec version` 走同一份 report（cli.py 委派此處）。
"""

from __future__ import annotations

import subprocess

from dspx import __version__, paths

NAME = "version"
HELP = "Print program version + TinyTeX version (from tex.lock) + pandoc version (offline, read-only)"


def _tinytex_version() -> str:
    """tex.lock 記的 TinyTeX tag（setup/upgrade 落地）；無 → 提示尚未 setup。"""
    lock = paths.read_tex_lock()
    if lock is None:
        return "(not installed; run `docspec setup`)"
    tag = lock.get("tinytex_tag")
    return str(tag) if tag else "(no tag in tex.lock)"


def _pandoc_version() -> str:
    """pandoc 自報版本（離線、本機）；找不到/查不到 → 提示。"""
    pandoc = paths.resolve_pandoc()
    if pandoc is None:
        return "(not installed)"
    try:
        out = subprocess.run([pandoc, "--version"], capture_output=True,
                             text=True, timeout=10)
        first = (out.stdout or "").splitlines()
        if first:
            # 首行形如 "pandoc 3.1.11"
            parts = first[0].split()
            return parts[1] if len(parts) >= 2 else first[0].strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "(version unavailable)"


def report() -> str:
    """三版本對齊報告（cli.py --version 與 version 子指令共用）。"""
    return (
        f"docspec {__version__}\n"
        f"  TinyTeX (tex.lock)  {_tinytex_version()}\n"
        f"  pandoc              {_pandoc_version()}"
    )


def run(argv: list[str]) -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="docspec version", description=HELP)
    parser.parse_args(argv)  # no options; honors -h/--help (and rejects unknown args)
    print(report())
    return 0
