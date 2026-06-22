"""dspx — docspec 指令列入口。

子指令採 registry 模式：每個子指令一個模組（dspx.commands.*），
模組提供 NAME、HELP、run(argv) -> int，並於 dspx.commands 註冊。
新增子指令＝新增一個模組＋一行註冊，主入口不需改動。
"""

from __future__ import annotations

import sys

from dspx.commands import HUMAN_COMMANDS, REGISTRY

_PROG = "docspec"


def _ensure_utf8_output() -> None:
    """Windows 主控台編碼防護：盡力切到 UTF-8，失敗不致命。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except Exception:  # pragma: no cover - 測試替身串流無 reconfigure
            pass


def _help_text(show_all: bool = False) -> str:
    lines = [
        f"{_PROG} — document SDD tool",
        "",
        f"Usage: {_PROG} <command> [args]",
        f"       {_PROG} --version | --help | --help-all",
        "",
        "Commands:",
    ]
    names = sorted(REGISTRY) if show_all else sorted(n for n in REGISTRY if n in HUMAN_COMMANDS)
    for name in names:
        lines.append(f"  {name:<12}{REGISTRY[name].HELP}")
    if not show_all:
        lines += [
            "",
            "The rest are agent commands (driven by skills via `docspec guide` / "
            "`docspec instructions`,",
            f"normally not run by hand). List them all: {_PROG} --help-all",
        ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    _ensure_utf8_output()

    if not args or args[0] in ("-h", "--help"):
        print(_help_text())
        return 0
    if args[0] == "--help-all":
        print(_help_text(show_all=True))
        return 0
    if args[0] in ("-V", "--version"):
        from dspx.commands import version as version_cmd
        print(version_cmd.report())
        return 0

    name, rest = args[0], args[1:]
    command = REGISTRY.get(name)
    if command is None:
        available = ", ".join(sorted(REGISTRY)) or "(none)"
        sys.stderr.write(f"{_PROG}: unknown command '{name}'. Available commands: {available}\n")
        return 2
    return command.run(rest)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
