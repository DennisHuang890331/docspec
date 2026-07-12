r"""docspec version — 一併印 程式版 + 安裝來源 + typst/pandoc 版 + 選配 TinyTeX 版。

讓「程式↔引擎」版本與安裝來源錯位一眼可見（離線、唯讀）。
`docspec --version` 與 `docspec version` 走同一份 report（cli.py 委派此處）。
安裝來源＝讀自身 dist 的 PEP 610 `direct_url.json`（git@commit／directory build snapshot）；
typst＝現行預設 render 引擎（取代已退場為選配的 TinyTeX 主位）。
"""

from __future__ import annotations

import subprocess

from dspx import __version__
from dspx.engine import paths

NAME = "version"
HELP = "Print program version + install source + typst / pandoc versions + optional TinyTeX (offline, read-only)"


def _tinytex_version() -> str:
    """tex.lock 記的 TinyTeX tag（setup 落地）；無 → 提示尚未 setup。"""
    lock = paths.read_tex_lock()
    if lock is None:
        return "(not installed; run `docspec setup`)"
    tag = lock.get("tinytex_tag")
    return str(tag) if tag else "(no tag in tex.lock)"


def _tool_version(exe: str | None) -> str:
    """一個 CLI 工具（typst/pandoc）自報版本首行的版本號（離線、本機）；缺/查不到 → 提示。"""
    if exe is None:
        return "(not installed; run `docspec setup`)"
    try:
        out = subprocess.run([exe, "--version"], capture_output=True,
                             text=True, timeout=10)
        first = (out.stdout or "").splitlines()
        if first:
            # 首行形如 "pandoc 3.1.11" / "typst 0.13.1 (...)"
            parts = first[0].split()
            return parts[1] if len(parts) >= 2 else first[0].strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "(version unavailable)"


def _pandoc_version() -> str:
    return _tool_version(paths.resolve_pandoc())


def _typst_version() -> str:
    return _tool_version(paths.resolve_typst())


def _install_source_line() -> str | None:
    """安裝來源行（PEP 610 direct_url.json）；來源不明 → None（靜默省略）。"""
    from dspx.env import _install_source
    src = _install_source.read_install_source()
    if src is None:
        return None
    if src["kind"] == "git":
        return f"installed from git@{src['commit'][:12]} ({src['url']})"
    if src["kind"] == "dir":
        return (f"installed from directory {src['path']} "
                f"(build snapshot — may lag the source; update: {_install_source.update_command(src)})")
    return None


def report() -> str:
    """版本對齊＋安裝來源報告（cli.py --version 與 version 子指令共用）。"""
    lines = [f"docspec {__version__}"]
    src = _install_source_line()
    if src is not None:
        lines.append(f"  {src}")
    lines += [
        f"  typst               {_typst_version()}  (default render engine)",
        f"  pandoc              {_pandoc_version()}",
        f"  TinyTeX (tex.lock)  {_tinytex_version()}  (optional LaTeX track)",
    ]
    return "\n".join(lines)


def run(argv: list[str]) -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="docspec version", description=HELP)
    parser.parse_args(argv)  # no options; honors -h/--help (and rejects unknown args)
    print(report())
    return 0
