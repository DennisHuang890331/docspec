"""docspec init 開場畫面（仿 OpenSpec welcome-screen）。

左側「文件」像素 logo **持續迴圈浮現＋重置**（＝會閃／脈動），右側 welcome 文字。
動畫在背景執行緒跑、主執行緒等使用者按 Enter（仿 OpenSpec：邊閃邊等）。
只在真終端機（TTY）跑；非 TTY（agent/CI/測試）→ 安靜不輸出。
顏色用 colorama（跨 Windows legacy console）；NO_COLOR / 非 TTY 自動降級。
配色照 OpenSpec：logo＝cyan、標題＝white bold、副標/說明＝dim、slash 指令＝yellow、Enter 提示＝cyan。
"""

from __future__ import annotations

import os
import sys
import threading

try:
    import colorama
    colorama.just_fix_windows_console()
except Exception:  # pragma: no cover
    pass

# ---- ANSI 配色（對齊 OpenSpec chalk 用色）-----------------------------------
RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
CYAN = "\x1b[36m"
YELLOW = "\x1b[33m"
WHITE = "\x1b[37m"

# ---- 字元集（Windows legacy console 無 unicode → ASCII 降級）-----------------
_UNICODE = os.name != "nt" or bool(os.environ.get("WT_SESSION") or os.environ.get("TERM_PROGRAM"))
BULLET = "•" if _UNICODE else "-"

INTERVAL = 0.15        # 每格秒數
ART_COLUMN_WIDTH = 16  # logo 欄寬（右側文字起點）

# 疊頁文件 logo（線條風，使用者偏好）。動畫＝整體明暗脈動＋一拍熄滅（blink）＝「閃」。
_LOGO_U = [
    "   ┌───────┐",
    "  ┌┴──────┐│",
    " ┌┴──────┐││",
    " │ ▤▤▤   │├┘",
    " │ ▤▤    │┘ ",
    " └───────┘  ",
]
_LOGO_A = [
    "   +-------+",
    "  ++------+|",
    " ++------+||",
    " | ###   |++",
    " | ##    |+ ",
    " +-------+  ",
]
_LOGO = _LOGO_U if _UNICODE else _LOGO_A

# 脈動序列：熄滅(blink) → 漸亮 → hold 最亮 → 漸暗 → 迴圈。blank 那一拍就是「閃」。
_SEQ = ["blank", "dim", "normal", "bold", "bold", "normal", "dim"]

_TEXT = [
    f"{BOLD}{WHITE}Welcome to docspec{RESET}",
    f"{DIM}Spec-driven development, for writing documents.{RESET}",
    "",
    f"{WHITE}This setup will configure:{RESET}",
    f"{DIM}  {BULLET} Agent skills for your AI tool{RESET}",
    f"{DIM}  {BULLET} /dspx:* slash commands{RESET}",
    "",
    f"{WHITE}Quick start after setup:{RESET}",
    f"  {YELLOW}/dspx:develop{RESET} {DIM} shape the outline & decisions{RESET}",
    f"  {YELLOW}/dspx:draft  {RESET} {DIM} render the prose{RESET}",
    f"  {YELLOW}/dspx:publish{RESET} {DIM} freeze a version{RESET}",
    f"  {YELLOW}/dspx:release{RESET} {DIM} typeset the PDF{RESET}",
    "",
    f"{CYAN}Press Enter to select tools...{RESET}",
]

_HEIGHT = max(len(_LOGO), len(_TEXT))
_INTENSITY = {"dim": DIM + CYAN, "normal": CYAN, "bold": BOLD + CYAN}


def _color() -> bool:
    return sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def _compose(intensity: str) -> str:
    """logo（左，依 intensity 上 cyan 明暗；blank＝熄滅）＋ welcome（右）並排。"""
    lines = []
    for i in range(_HEIGHT):
        base = "" if intensity == "blank" else (_LOGO[i] if i < len(_LOGO) else "")
        raw = base.ljust(ART_COLUMN_WIDTH)
        if _color() and intensity != "blank":
            left = f"{_INTENSITY[intensity]}{raw}{RESET}"
        else:
            left = raw
        right = _TEXT[i] if i < len(_TEXT) else ""
        lines.append(f"\x1b[2K  {left}  {right}")
    return "\n".join(lines)


def _animate(stop: threading.Event) -> None:
    idx = 0
    first = True
    while not stop.is_set():
        intensity = _SEQ[idx % len(_SEQ)]
        if not first:
            sys.stdout.write(f"\x1b[{_HEIGHT}A")   # 游標上移、覆蓋重畫
        first = False
        sys.stdout.write(_compose(intensity) + "\n")
        sys.stdout.flush()
        idx += 1
        stop.wait(INTERVAL)


def _read_enter() -> None:
    """無回顯讀單鍵直到 Enter（讓動畫獨佔游標、不被 input 回顯干擾）。Ctrl+C → KeyboardInterrupt。"""
    if os.name == "nt":
        import msvcrt
        while True:
            ch = msvcrt.getwch()
            if ch in ("\r", "\n"):
                return
            if ch == "\x03":
                raise KeyboardInterrupt
    else:
        import termios
        import tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while True:
                ch = sys.stdin.read(1)
                if ch in ("\r", "\n"):
                    return
                if ch == "\x03":
                    raise KeyboardInterrupt
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


def show_welcome() -> None:
    """跑開場（迴圈閃動畫＋文字），按 Enter 後清畫面交給選單。非 TTY 直接 return。"""
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return

    stop = threading.Event()
    thread = threading.Thread(target=_animate, args=(stop,), daemon=True)
    thread.start()
    try:
        _read_enter()
    except KeyboardInterrupt:
        stop.set()
        thread.join(timeout=1)
        sys.stdout.write("\n")
        raise SystemExit(0)
    stop.set()
    thread.join(timeout=1)

    # 清掉整個 welcome 區塊、游標移回頂端，讓選單原地接手（仿 OpenSpec）
    sys.stdout.write(f"\x1b[{_HEIGHT}A")
    for _ in range(_HEIGHT):
        sys.stdout.write("\x1b[2K\n")
    sys.stdout.write(f"\x1b[{_HEIGHT}A")
    sys.stdout.flush()
