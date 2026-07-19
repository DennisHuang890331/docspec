"""docspec hook guard — agent 工具的 PreToolUse 守門（跨平台，邏輯在 Python）。

各 agent 工具的 hook 設定成「動手前呼叫 `docspec hook guard`」即可，不必在設定檔裡寫
各平台 shell（win/mac/linux 通用）。guard 從 stdin 讀工具呼叫 JSON：
  - Edit/Write：看 `tool_input.file_path`，落在 archive/ → 擋。
  - Bash/PowerShell：看 `tool_input.command`，若會**改到 / 刪到** archive/ 內檔案 → 擋
    （單純從 archive 複製出來＝讀，不影響快照，放行；使用者拍板的規則）。
  - 擋＝exit 2＋stderr（Claude Code 約定）。解析失敗＝fail-closed 擋下（使用者拍板）。

判斷不可能 100%（變數/glob/繞道抓不到）——漏網的由引擎 lint V11（hash 抓包）兜底。
"""

from __future__ import annotations

import json
import re
import shlex
import sys

from dspx.reports.freeze import is_frozen_path

NAME = "hook"
HELP = "agent-tool gatekeeper (internal; PreToolUse calls `docspec hook guard`)"

_BLOCK_MSG = (
    "[docspec] Blocked: archive/ holds published frozen versions, never to be modified. "
    "To update content, edit docs/<article>/_latest.md, then `docspec publish` a new version."
)

_STORE_BLOCK_MSG = (
    "[docspec] Blocked: corpus/<article>.yaml is an engine-owned single-file store guarded by an "
    "integrity seal — a hand-edit corrupts it. Change a section through the engine: "
    "`docspec get/put <section> <category>`. "
    "(If you truly must edit externally, run `docspec store fsck --accept` afterwards.)"
)


def _is_store_file(token: str) -> bool:
    """path 是否為 corpus store 檔（`.../corpus/<article>.yaml`、非 `_` 前綴、直接在 corpus 下）。

    不尋根（保守、跨平台、快）：只認「父目錄名＝corpus、副檔名 .yaml、檔名非 `_` 開頭」的形。
    corpus 底下唯一的頂層 .yaml 就是 store 檔（散檔的 concept/decisions 住更深的節夾裡）。"""
    from pathlib import Path
    p = Path(token.strip().strip("'\""))
    # forest 級治理密封檔（`<home>/audit.yaml` / `roadmap.yaml`）——依名顯式守（不在 corpus/ 下、
    # 但同為封條保護，手改必壞；doc 級 sibling `<a>.audit.yaml` 走下面 corpus-parent 規則）。
    if p.name in ("audit.yaml", "roadmap.yaml"):
        return True
    # dossier-layout：案卷內定名檔 `corpus/<夾>/{article,ledger,verdicts}.yaml`（活案卷）
    # 與 `corpus/_archive/<夾>/…`（退場案卷）——一條形狀規則守全案卷。
    if p.name in ("article.yaml", "ledger.yaml", "verdicts.yaml"):
        gp = p.parent.parent
        if gp.name == "corpus" or (gp.name == "_archive" and gp.parent.name == "corpus"):
            return True
    # 前一代扁平形（fallback 期）：corpus 直下 *.yaml
    return (p.suffix == ".yaml" and p.parent.name == "corpus"
            and not p.name.startswith("_"))

# 子指令切分（; && || | 換行）與重導目標擷取
_SUBCMD_SPLIT = re.compile(r"&&|\|\||[;|\n]")
_REDIRECT = re.compile(r"(?:\d*>>?|&>)\s*('[^']*'|\"[^\"]*\"|[^\s;|&]+)")
# PowerShell 會改內容的 cmdlet（含常見別名）；Copy-Item 不列（複製＝讀、放行）
_PWSH_MUTATE = re.compile(
    r"\b(Remove-Item|ri|del|erase|Move-Item|mi|move|Set-Content|sc|Add-Content|ac|"
    r"Out-File|Clear-Content|clc|New-Item|ni)\b", re.IGNORECASE)


def _is_archive(token: str) -> bool:
    return is_frozen_path(token.strip().strip("'\""))


def _bash_sub_modifies(sub: str) -> bool:
    """一段 bash 子指令是否會改/刪 archive 內檔案。"""
    try:
        toks = shlex.split(sub)
    except ValueError:
        return "archive" in sub          # 引號不對稱 → fail-closed
    if not toks:
        return False
    cmd = toks[0].rsplit("/", 1)[-1]
    args = toks[1:]
    paths = [t for t in args if not t.startswith("-")]
    # 破壞/改內容：碰 archive 就擋（mv 搬出去＝毀快照，故任一邊都擋）
    if cmd in ("rm", "rmdir", "unlink", "truncate", "shred", "tee", "mv"):
        return any(_is_archive(p) for p in paths)
    if cmd == "sed" and any(a.startswith("-i") for a in args):
        return any(_is_archive(p) for p in paths)
    if cmd == "dd":
        return any(a.startswith("of=") and _is_archive(a[3:]) for a in args)
    # cp/ln/install：只有「目的地」（最後位置參數）是 archive 才擋；從 archive 複製出來放行
    if cmd in ("cp", "ln", "install"):
        return bool(paths) and _is_archive(paths[-1])
    return False


def _pwsh_sub_modifies(sub: str) -> bool:
    """一段 PowerShell 子指令是否會改/刪 archive（保守：改內容 cmdlet＋提到 archive 即擋）。"""
    if not _PWSH_MUTATE.search(sub):
        return False
    return any(_is_archive(t) for t in sub.split()) or bool(
        re.search(r"archive[\\/]", sub, re.IGNORECASE))


def _command_modifies_archive(command: str) -> bool:
    """bash / powershell 指令是否會改到 archive/ 內容（會→True 擋下）。"""
    for sub in _SUBCMD_SPLIT.split(command):
        sub = sub.strip()
        if not sub:
            continue
        if any(_is_archive(m.group(1)) for m in _REDIRECT.finditer(sub)):  # 重導寫入
            return True
        if _bash_sub_modifies(sub) or _pwsh_sub_modifies(sub):
            return True
    return False


def _guard(data: object) -> int:
    """PreToolUse：擋改 archive/ 凍結區（exit 2 = 擋）。fail-closed。"""
    if data is None:
        sys.stderr.write("[docspec] Could not parse the tool-call input — blocking to be safe (fail-closed).\n")
        return 2
    tool_input = data.get("tool_input") or {}
    path = tool_input.get("file_path") or tool_input.get("path") or ""
    if path and is_frozen_path(path):
        sys.stderr.write(_BLOCK_MSG + "\n")
        return 2
    if path and _is_store_file(path):
        sys.stderr.write(_STORE_BLOCK_MSG + "\n")
        return 2
    command = tool_input.get("command") or ""
    if command and _command_modifies_archive(command):
        sys.stderr.write(_BLOCK_MSG + "\n")
        return 2
    if command and _command_writes_store(command):
        sys.stderr.write(_STORE_BLOCK_MSG + "\n")
        return 2
    return 0


def _command_writes_store(command: str) -> bool:
    """bash/pwsh 指令是否會寫/改到 corpus store 檔（重導 or mutate cmdlet 目標）。"""
    for sub in _SUBCMD_SPLIT.split(command):
        sub = sub.strip()
        if not sub:
            continue
        if any(_is_store_file(m.group(1)) for m in _REDIRECT.finditer(sub)):
            return True
        try:
            toks = shlex.split(sub)
        except ValueError:
            if "corpus" in sub and ".yaml" in sub:
                return True
            toks = []
        if toks:
            cmd = toks[0].rsplit("/", 1)[-1]
            paths = [t for t in toks[1:] if not t.startswith("-")]
            if cmd in ("rm", "mv", "cp", "tee", "truncate", "sed", "dd", "unlink") \
                    and any(_is_store_file(p) for p in paths):
                return True
        if _PWSH_MUTATE.search(sub) and any(_is_store_file(t) for t in sub.split()):
            return True
    return False


def _postcheck(data: object) -> int:
    """PostToolUse：編輯**散檔形態**的 concept/decisions/history（`store dump`／migrate 源／
    `_archive` 快照）後的「檔案級完整性」提醒。活 store（`corpus/<article>.yaml`）由 guard 擋手改、
    走 put，不經此路。
    **best-effort、非阻擋**（PostToolUse 在寫入後觸發、擋不住寫入；真正的閘＝check/publish）。
    絕不因自身錯誤干擾 agent（任何例外 → 放行 exit 0）。exit 2 僅把提醒餵回 agent。"""
    if data is None:
        return 0
    try:
        tool_input = data.get("tool_input") or {}
        path = tool_input.get("file_path") or tool_input.get("path") or ""
        if not path:
            return 0
        from pathlib import Path
        p = Path(path)
        if p.name not in ("concept.yaml", "decisions.yaml", "history.yaml"):
            return 0
        from dspx.check import run_file_check
        from dspx.engine.config import load_config
        from dspx.engine.layout import Layout, find_planning_home
        from dspx.engine.model import load_leaf
        from dspx.engine.schema import load_schema
        home = find_planning_home()
        config = load_config(home)
        layout = Layout(home, config.get("docs_layout", "flat"))
        section_dir = p.parent
        try:                                  # 必須在 corpus 內
            section_dir.resolve().relative_to(layout.corpus_dir.resolve())
        except (ValueError, OSError):
            return 0
        if layout.is_archived_path(section_dir):   # _archive 引擎隱形
            return 0
        errs = run_file_check(load_leaf(layout, section_dir), load_schema(config.get("schema")))
        if not errs:
            return 0
        sys.stderr.write("[docspec] Reminder (non-blocking, file already written): the file just "
                         "written has unfilled required fields; fill them (status shows the section as developing until complete):\n")
        for e in errs[:8]:
            sys.stderr.write(f"  · {e}\n")
        return 2
    except Exception:
        return 0


_USAGE = ("Usage: docspec hook guard|check (reads tool JSON from stdin)\n"
          "  guard  PreToolUse freeze guard — blocks edits under archive/ (exit 2 = block)\n"
          "  check  PostToolUse completeness reminder for corpus/*.yaml (best-effort)\n")


def run(argv: list[str]) -> int:
    sub = argv[0] if argv else ""
    if sub in ("-h", "--help"):
        print(_USAGE, end="")
        return 0
    if sub not in ("guard", "check"):
        sys.stderr.write(_USAGE)
        return 2
    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    try:
        data = json.loads(raw) if raw.strip() else None
    except json.JSONDecodeError:
        data = None
    return _guard(data) if sub == "guard" else _postcheck(data)
