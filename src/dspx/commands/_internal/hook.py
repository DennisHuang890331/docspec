"""docspec hook guard — agent 工具的 PreToolUse 守門（跨平台，邏輯在 Python）。

各 agent 工具的 hook 設定成「動手前呼叫 `docspec hook guard`」即可，不必在設定檔裡寫
各平台 shell（win/mac/linux 通用）。guard 從 stdin 讀工具呼叫 JSON：
  - Edit/Write：看 `tool_input.file_path`，落在 archive/ → 擋。
  - Bash/PowerShell：看 `tool_input.command`，若會**改到 / 刪到** archive/ 內檔案 → 擋
    （單純從 archive 複製出來＝讀，不影響快照，放行；使用者拍板的規則）。
  - 擋＝exit 2＋stderr（Claude Code 約定）。解析失敗＝fail-closed 擋下（使用者拍板）。

判斷不可能 100%（變數/glob/繞道抓不到）——漏網的由引擎 lint V11（hash 抓包）兜底。

各家 agent 的呼叫格式都在這裡原生正規化（不需要專案自寫轉接程式）：
  - Claude / Codex / Gemini：`{tool_input: {file_path | path | command}}`。
  - Codex apply_patch：`tool_name: apply_patch`，補丁文字在 `tool_input.input|patch|command`；
    逐一檢查 `*** Add/Update/Delete File:`、`*** Move to:` 的路徑。
  - Antigravity：`{toolCall: {name, args}}`（run_command 的 CommandLine、write_to_file 等的
    TargetFile）；Antigravity 以 stdout JSON `{"decision": "allow"|"deny"}` 表達結果、離開碼 0。
只擋寫入與刪除；純讀取（ls、grep、cat、find 不帶 -delete/-exec 寫入）一律放行。
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
    "To update content, edit docs/<article>/_latest.md, then `docspec freeze` a new version."
)

_STORE_BLOCK_MSG = (
    "[docspec] Blocked: corpus/<article>.yaml is an engine-owned single-file store guarded by an "
    "integrity seal — a hand-edit corrupts it. Change a section through the engine: "
    "`docspec get/put <section> <category>`. "
    "(If you truly must edit externally, run `docspec store fsck --accept` afterwards.)"
)


_GOV_BLOCK_MSG = (
    "[docspec] Blocked: docspec/governance/ holds engine-owned, sealed governance records "
    "(questions, rulings, decisions, roadmap, suspect flags). Change them only through docspec "
    "commands (`docspec question|ruling|decision|roadmap|impact ...`).")

_SW_BLOCK_MSG = (
    "[docspec] Blocked: docspec/software/ holds engine-owned, sealed software records (capability "
    "specs, change folders, tasks, test plans, evidence). Change them only through `docspec code ...`; "
    "task completion is written by the engine from evidence. (software/config.yaml is hand-editable.)")

_VIEW_BLOCK_MSG = (
    "[docspec] Blocked: docs/project/*.md are generated views (status, design, pending). "
    "Regenerate them with `docspec brief --write` instead of editing by hand.")


def _clean(token: str):
    from pathlib import Path
    return Path(token.strip().strip("'\""))


def _is_governance_file(token: str) -> bool:
    """`docspec/governance/**.yaml`：治理層密封紀錄。"""
    p = _clean(token)
    parts = p.parts
    return p.suffix == ".yaml" and any(
        parts[i] == "docspec" and parts[i + 1] == "governance" for i in range(len(parts) - 1))


def _is_software_file(token: str) -> bool:
    """`docspec/software/**.yaml`（`software/config.yaml` 除外）與 `docspec/baselines/**.yaml`（專案基線）。"""
    p = _clean(token)
    parts = p.parts
    for i in range(len(parts) - 1):
        if parts[i] == "docspec" and parts[i + 1] == "software":
            return p.suffix == ".yaml" and parts[i + 2:] != ("config.yaml",)
        if parts[i] == "docspec" and parts[i + 1] == "baselines":
            return p.suffix == ".yaml"
    return False


def _is_generated_view(token: str) -> bool:
    """`docs/project/*.md`：`docspec brief --write` 產生的檢視。"""
    p = _clean(token)
    return p.suffix == ".md" and p.parent.name == "project" and p.parent.parent.name == "docs"


def _protected_message(token: str) -> str | None:
    """寫入這個路徑會破壞引擎擁有的檔案 → 回對應的擋下訊息；否則 None。"""
    if _is_archive(token):
        return _BLOCK_MSG
    if _is_store_file(token):
        return _STORE_BLOCK_MSG
    if _is_governance_file(token):
        return _GOV_BLOCK_MSG
    if _is_software_file(token):
        return _SW_BLOCK_MSG
    if _is_generated_view(token):
        return _VIEW_BLOCK_MSG
    return None


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


# agent 當下的工作目錄（Claude/Codex/Gemini 的 hook 輸入帶 `cwd`）。相對路徑依它解析，
# 才分得出 docs/g 裡的 `archive/v1.md`（凍結）與 openspec/changes 裡的 `archive/…`（不是）。
_CWD: str | None = None


def _is_archive(token: str) -> bool:
    import os
    from pathlib import Path
    p = Path(token.strip().strip("'\""))
    if not p.is_absolute():
        p = Path(_CWD or os.getcwd()) / p
    return is_frozen_path(p)


def _tokens(sub: str) -> list[str]:
    """shlex 切詞；引號不對稱（例如文字裡的 it's）時退回空白切詞，不再因「字串含 archive」
    就整段擋下——判斷仍看「動詞＋目標路徑」，純讀取指令不會被誤擋。"""
    try:
        return shlex.split(sub)
    except ValueError:
        return [t.strip("'\"") for t in sub.split()]


_WRITE_VERBS = ("rm", "rmdir", "unlink", "truncate", "shred", "tee", "mv")


def _find_writes(args: list[str], pred) -> bool:
    """find：起點路徑命中，且帶 -delete 或以 -exec/-execdir 執行寫入動詞 → 視為寫入。"""
    roots = []
    for a in args:
        if a.startswith("-") or a in ("(", "!"):
            break
        roots.append(a)
    if not any(pred(r) for r in roots):
        return False
    if "-delete" in args:
        return True
    for i, a in enumerate(args):
        if a in ("-exec", "-execdir", "-ok") and i + 1 < len(args):
            verb = args[i + 1].rsplit("/", 1)[-1]
            if verb in _WRITE_VERBS or (verb == "sed" and any(x.startswith("-i") for x in args[i + 2:])):
                return True
    return False


def _sub_writes(sub: str, pred) -> bool:
    """一段 bash 子指令是否會改／刪「pred 為真」的路徑。"""
    toks = _tokens(sub)
    if not toks:
        return False
    cmd = toks[0].rsplit("/", 1)[-1]
    args = toks[1:]
    paths = [t for t in args if not t.startswith("-")]
    if cmd in _WRITE_VERBS:
        return any(pred(p) for p in paths)
    if cmd == "sed" and any(a.startswith("-i") for a in args):
        return any(pred(p) for p in paths)
    if cmd == "dd":
        return any(a.startswith("of=") and pred(a[3:]) for a in args)
    if cmd in ("cp", "ln", "install"):
        return bool(paths) and pred(paths[-1])
    if cmd == "find":
        return _find_writes(args, pred)
    return False


def _bash_sub_modifies(sub: str) -> bool:
    """一段 bash 子指令是否會改/刪 archive 內檔案。"""
    toks = _tokens(sub)
    if not toks:
        return False
    cmd = toks[0].rsplit("/", 1)[-1]
    args = toks[1:]
    paths = [t for t in args if not t.startswith("-")]
    if cmd == "find":
        return _find_writes(args, _is_archive)
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
        re.search(r"docs[\\/](?:[^\\/\s]+[\\/])?archive[\\/]", sub, re.IGNORECASE))


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


_PATCH_PATH = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", re.MULTILINE)
_MOVE_PATH = re.compile(r"^\*\*\* Move to: (.+)$", re.MULTILINE)
_AG_FILE_TOOLS = ("write_to_file", "replace_file_content", "multi_replace_file_content")


class _Unparseable(Exception):
    pass


def _patch_paths(patch: str) -> list[str]:
    paths = [x.strip() for x in _PATCH_PATH.findall(patch) + _MOVE_PATH.findall(patch)]
    if not paths or any(not x for x in paths):
        raise _Unparseable("apply_patch input has no file paths")
    return paths


def _normalize(data: object) -> tuple[list[dict], bool]:
    """各家 agent 的呼叫 → (要檢查的 tool_input 清單, 是否 Antigravity)。無法解析 → _Unparseable。"""
    if not isinstance(data, dict):
        raise _Unparseable("tool-call input is not a JSON object")
    call = data.get("toolCall")
    if isinstance(call, dict):                                   # Antigravity
        name, args = call.get("name"), call.get("args") or {}
        if not isinstance(args, dict):
            raise _Unparseable("malformed Antigravity tool call")
        if name == "run_command":
            return [{"command": str(args.get("CommandLine") or "")}], True
        if name in _AG_FILE_TOOLS:
            return [{"file_path": str(args.get("TargetFile") or "")}], True
        return [], True                                          # 非寫入工具：放行
    tool_input = data.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        raise _Unparseable("tool_input is not an object")
    name = data.get("tool_name") or data.get("name")
    patch = None
    if name == "apply_patch":
        patch = tool_input.get("input") or tool_input.get("patch") or tool_input.get("command")
        if not isinstance(patch, str):
            raise _Unparseable("malformed apply_patch input")
    elif isinstance(tool_input.get("command"), str) and "*** Begin Patch" in tool_input["command"]:
        patch = tool_input["command"]                            # 透過 shell 呼叫的 apply_patch
    if patch is not None:
        return [{"file_path": x} for x in _patch_paths(patch)], False
    return [tool_input], False


def _guard_one(tool_input: dict) -> str | None:
    """單一 tool_input → 擋下訊息或 None（放行）。"""
    path = tool_input.get("file_path") or tool_input.get("path") or ""
    if path:
        msg = _protected_message(str(path))
        if msg:
            return msg
    command = tool_input.get("command") or ""
    if not isinstance(command, str) or not command:
        return None
    if _command_modifies_archive(command):
        return _BLOCK_MSG
    for sub in _SUBCMD_SPLIT.split(command):
        sub = sub.strip()
        if not sub:
            continue
        for pred, msg in ((_is_store_file, _STORE_BLOCK_MSG), (_is_governance_file, _GOV_BLOCK_MSG),
                          (_is_software_file, _SW_BLOCK_MSG), (_is_generated_view, _VIEW_BLOCK_MSG)):
            if any(pred(m.group(1)) for m in _REDIRECT.finditer(sub)) or _sub_writes(sub, pred) \
                    or (_PWSH_MUTATE.search(sub) and any(pred(t) for t in sub.split())):
                return msg
    return None


def _guard(data: object) -> int:
    """PreToolUse：擋改凍結區、引擎擁有的檔案、使用者專用指令（exit 2 = 擋）。無法解析＝fail-closed。"""
    global _CWD
    antigravity = isinstance(data, dict) and "toolCall" in data
    _CWD = data.get("cwd") if isinstance(data, dict) and isinstance(data.get("cwd"), str) else None
    try:
        if data is None:
            raise _Unparseable("could not parse the tool-call input")
        inputs, antigravity = _normalize(data)
        msg = next((m for m in (_guard_one(ti) for ti in inputs) if m), None)
    except _Unparseable as exc:
        msg = f"[docspec] Could not parse the tool-call input ({exc}) — blocking to be safe (fail-closed)."
    if antigravity:
        print(json.dumps({"decision": "deny", "reason": msg} if msg else {"decision": "allow"},
                         ensure_ascii=False))
        if msg:
            sys.stderr.write(msg + "\n")
        return 0
    if msg:
        sys.stderr.write(msg + "\n")
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
        toks = _tokens(sub)
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
    antigravity = isinstance(data, dict) and "toolCall" in data
    try:
        rc = 0
        inputs, antigravity = _normalize(data)
        for ti in inputs:
            rc = max(rc, _postcheck_one(ti))
        if antigravity:
            print("{}")
            return 0
        return rc
    except Exception:
        if antigravity:
            print("{}")
        return 0


def _postcheck_one(tool_input: dict) -> int:
    try:
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
