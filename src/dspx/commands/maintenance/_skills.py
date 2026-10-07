"""docspec skills — 把內建 skill 安裝到各 agent 工具的技能系統。

照 OpenSpec 的 delivery='both' 模型：每個工具產**兩份**——
 (1) skill：自動載入 / Agent Skills 規格位置 <skillsDir>/skills/<name>/SKILL.md
 (2) command：使用者顯式叫用的原生 slash/workflow 位置

  | 工具        | skill（自動）                       | command（叫用）                            |
  |-------------|-------------------------------------|--------------------------------------------|
  | claude      | .claude/skills/<name>（見下）        | .claude/commands/dspx/<id>.md  /dspx:<id>  |
  | antigravity | .agents/skills/<name>/SKILL.md 共用 | .agents/workflows/<name>.md    原生 workflow|
  | codex       | .agents/skills/<name>/SKILL.md 共用 | （skills-only：skill 即 $dspx-<name> 叫用） |
  | gemini      | .agents/skills/<name>/SKILL.md 共用 | .gemini/commands/dspx/<id>.toml /dspx:<id> |

`.agents/skills/` 是跨工具的共用 skill 根（Codex／Antigravity／Gemini CLI 皆讀；OpenSpec
config.ts 亦已把 codex/antigravity 的 skillsDir 改為 `.agents`、舊 `.codex`／`.agent` 列 legacy）。
Claude Code 只讀 `.claude/skills/`：同時裝了共用根時，`.claude/skills/<name>` 做成指向
`.agents/skills/<name>` 的相對 symlink（單一來源）；建不了 symlink（Windows 無權限等）退回複製。
只裝 claude 時照舊寫實檔。
Codex 照 OpenSpec 改 skills-only：不再寫全域 $CODEX_HOME/prompts（舊版產的會在 --force 時收掉）。
舊位（`.agent/skills`、`.agent/workflows`、`.codex/skills`）裡 docspec 自己的 skill 在 --force 時
移除，避免新舊兩份同名 skill 同時被載入；未 --force 只提示。

`--tool`（預設 claude＝只裝你實際在用的那家）；`--tool all`＝全裝。已存在的檔預設「跳過、不覆寫」
（保護手改）；--force 覆寫。
"""

from __future__ import annotations

import argparse
import ntpath
import os
import re
import shutil
import sys
from pathlib import Path

from dspx.env.skills import Skill, SkillError, available_skills

NAME = "skills"
HELP = "install the built-in skills to Claude / Antigravity / Codex / Gemini"

_TOOLS = ("claude", "antigravity", "codex", "gemini")

# 跨工具共用 skill 根（Agent Skills 的 vendor-neutral 位置）與讀它的工具。
_SHARED_ROOT = ".agents"
_SHARED_TOOLS = ("antigravity", "codex", "gemini")
# 前一代 docspec 為各工具寫的 skill 根（遷移時收掉 docspec 自己的那幾份）。
_LEGACY_SKILLS_DIR = {"antigravity": ".agent", "codex": ".codex"}
# 舊版 codex 全域 prompt 的簽名（前一代 prompt body 的 frontmatter 行）——只收帶此簽名的檔。
_CODEX_PROMPT_SIGNATURE = "argument-hint: command arguments"


def _skill_dir(root: Path, base: str, skill: Skill) -> Path:
    return root / base / "skills" / skill.name


# ---- command（原生 slash/workflow 叫用位置）---------------------------------
# OpenSpec 預設 delivery='both'：每個工具除了 skill（自動上下文），還產一份 command
# （使用者顯式叫用的 slash/workflow）。OpenSpec 的 command 是獨立模板；docspec 只有
# 一份 skill body，故 command 直接用同一份 body（自給自足，叫用時不依賴 skill 是否載入）。
#   claude      : .claude/commands/dspx/<id>.md      → slash /dspx:<id>   (claude.ts)
#   antigravity : .agents/workflows/<name>.md        → 原生 workflow      (antigravity.ts)
#   gemini      : .gemini/commands/dspx/<id>.toml    → slash /dspx:<id>   (gemini.ts)
#   codex       : 無（skills-only，同 OpenSpec）
# <id> ＝ skill 名去掉 dspx- 前綴（develop/apply/factcheck/publish/release）。

def _command_id(skill: Skill) -> str:
    return skill.name[len("dspx-"):] if skill.name.startswith("dspx-") else skill.name


def _codex_home() -> Path:
    """codex 家目錄：honor CODEX_HOME，否則 ~/.codex（同 OpenSpec codex.ts）。"""
    env = os.environ.get("CODEX_HOME", "").strip()
    return Path(env) if env else Path.home() / ".codex"


def _claude_command_path(root: Path, skill: Skill) -> Path:
    return root / ".claude" / "commands" / "dspx" / f"{_command_id(skill)}.md"


def _claude_command_body(skill: Skill) -> str:
    return f"---\nname: dspx-{_command_id(skill)}\ndescription: {skill.description}\n---\n\n{skill.body}"


def _antigravity_workflow_path(root: Path, skill: Skill, base: str = _SHARED_ROOT) -> Path:
    return root / base / "workflows" / f"{skill.name}.md"


def _antigravity_workflow_body(skill: Skill) -> str:
    return f"---\ndescription: {skill.description}\n---\n\n{skill.body}"


def _gemini_command_path(root: Path, skill: Skill) -> Path:
    return root / ".gemini" / "commands" / "dspx" / f"{_command_id(skill)}.toml"


def _toml_basic(value: str, *, multiline: bool = False) -> str:
    """TOML basic string 跳脫（反斜線、引號、控制字元）；multiline 保留換行與 tab。"""
    out = []
    for ch in value:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif multiline and ch in "\n\t":
            out.append(ch)
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif ord(ch) < 0x20 or ord(ch) == 0x7f:
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    return "".join(out)


def _gemini_command_body(skill: Skill) -> str:
    return (f'description = "{_toml_basic(skill.description)}"\n'
            f'prompt = """\n{_toml_basic(skill.body, multiline=True)}\n"""\n')


def _codex_legacy_prompt_path(skill: Skill) -> Path:
    return _codex_home() / "prompts" / f"dspx-{_command_id(skill)}.md"


# ---- 寫檔（含 skip/force 政策） ----------------------------------------------

def _write(path: Path, content: str, *, force: bool, results: list[str]) -> None:
    rel = path
    if path.exists() and not force:
        results.append(f"  = exists, skipped: {rel} (use --force to overwrite)")
        return
    verb = "overwrote" if path.exists() else "created"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    results.append(f"  + {verb}: {rel}")


def _copy(src: Path, dst: Path, *, force: bool, results: list[str]) -> None:
    """Copy a vendored aux file (script / NOTICE) verbatim, honoring skip/force."""
    if dst.exists() and not force:
        results.append(f"  = exists, skipped: {dst} (use --force to overwrite)")
        return
    verb = "overwrote" if dst.exists() else "created"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    results.append(f"  + {verb}: {dst}")


def _write_skill(skill_dir: Path, s: Skill, *, force: bool, results: list[str]) -> None:
    """落一份完整 skill：SKILL.md ＋ support skill 的 scripts/ 等輔助檔（subagent 要能跑）。"""
    if skill_dir.is_symlink():
        # 前一次裝成指向共用根的 link；改寫實檔前先拆 link，免得穿過 link 寫進 .agents/。
        if not force:
            results.append(f"  = exists, skipped: {skill_dir} (use --force to overwrite)")
            return
        skill_dir.unlink()
    _write(skill_dir / "SKILL.md", s.text, force=force, results=results)
    for aux in s.aux_files:
        rel = aux.relative_to(s.source.parent)
        _copy(aux, skill_dir / rel, force=force, results=results)


def _remove_path(p: Path) -> None:
    if p.is_symlink() or p.is_file():
        p.unlink()
    elif p.is_dir():
        shutil.rmtree(p)


def _link_skill(link: Path, target: Path, *, force: bool, results: list[str]) -> None:
    """`link`（.claude/skills/<name>）→ 相對 symlink 到 `target`（.agents/skills/<name>）。
    已是正確 link＝不動；既有實體（舊實檔／錯 link）未 --force 跳過、--force 換掉。
    建不了 symlink（Windows 無開發者模式等）→ 退回整夾複製，照樣可用。"""
    rel_target = Path(os.path.relpath(target, link.parent))
    if link.is_symlink() and link.resolve() == target.resolve():
        results.append(f"  = linked: {link} -> {rel_target}")
        return
    if link.exists() or link.is_symlink():
        if not force:
            results.append(f"  = exists, skipped: {link} (use --force to replace it with a link)")
            return
        _remove_path(link)
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(rel_target, link, target_is_directory=True)
        results.append(f"  + linked: {link} -> {rel_target}")
    except (OSError, NotImplementedError):
        shutil.copytree(target, link)
        results.append(f"  + copied (symlink unavailable): {link}")


def _prune_empty(path: Path, stop: Path) -> None:
    """由 path 往上刪空資料夾，到 stop（不含）為止。"""
    while path != stop and path.is_dir() and not path.is_symlink() and not any(path.iterdir()):
        path.rmdir()
        path = path.parent


def _retire_legacy(root: Path, tool: str, skills: list[Skill], *, force: bool,
                   results: list[str]) -> None:
    """收掉前一代 docspec 在 `.agent/`／`.codex/` 與全域 codex prompts 留下的自家檔。
    只動 docspec 內建 skill 同名的項目；未 --force 只提示（保護手改）。"""
    stale: list[Path] = []
    legacy = _LEGACY_SKILLS_DIR.get(tool)
    if legacy:
        stale += [p for s in skills if (p := _skill_dir(root, legacy, s)).exists()]
    if tool == "antigravity":
        stale += [p for s in skills if s.is_workflow
                  and (p := _antigravity_workflow_path(root, s, base=".agent")).is_file()]
    if tool == "codex":
        for s in skills:
            p = _codex_legacy_prompt_path(s)
            try:
                if p.is_file() and _CODEX_PROMPT_SIGNATURE in p.read_text(encoding="utf-8"):
                    stale.append(p)
            except OSError:
                pass
    if not stale:
        return
    if not force:
        for p in stale:
            results.append(f"  ! legacy docspec file left in place: {p} "
                           "(re-run `artispec init` to retire it)")
        return
    for p in stale:
        _remove_path(p)
        results.append(f"  - retired legacy: {p}")
    if legacy:
        _prune_empty(root / legacy / "skills", root)
    if tool == "antigravity":
        _prune_empty(root / ".agent" / "workflows", root)


def _install(root: Path, tools: tuple[str, ...], force: bool) -> list[str]:
    skills = available_skills()
    if not skills:
        raise SkillError("no built-in skills found (package data missing?)")
    results: list[str] = []
    if shutil.which("artispec") is None:
        results.append(
            "  ! PATH: `artispec` was not found; generated hooks require it. "
            "Add the installation's command directory to PATH and re-run `artispec init` "
            "to pin its absolute path (for uv tools: `uv tool update-shell`, then restart the session).")
    # 只給 workflow skill 產 command——support skill 由 subagent 載入、非人顯式叫用的階段。
    workflow_skills = [s for s in skills if s.is_workflow]

    # 1) 共用 skill 根：任一讀 .agents 的工具被選到就寫一次（不各寫一份）。
    shared = [t for t in _SHARED_TOOLS if t in tools]
    if shared:
        results.append(f"[agents] skill → {_SHARED_ROOT}/skills/<name>/SKILL.md "
                       f"(shared by {', '.join(shared)})")
        for s in skills:
            _write_skill(_skill_dir(root, _SHARED_ROOT, s), s, force=force, results=results)

    for tool in _TOOLS:
        if tool not in tools:
            continue
        if tool == "claude":
            if shared:
                # Claude 不讀 .agents/：以相對 symlink 共用同一份（單一來源）。
                results.append(f"[claude] skill → .claude/skills/<name> "
                               f"(linked to {_SHARED_ROOT}/skills/<name>)")
                for s in skills:
                    _link_skill(_skill_dir(root, ".claude", s),
                                _skill_dir(root, _SHARED_ROOT, s), force=force, results=results)
            else:
                results.append("[claude] skill → .claude/skills/<name>/SKILL.md")
                for s in skills:
                    _write_skill(_skill_dir(root, ".claude", s), s, force=force, results=results)
            results.append("[claude] command → .claude/commands/dspx/<id>.md (slash /dspx:<id>)")
            for s in workflow_skills:
                _write(_claude_command_path(root, s),
                       _claude_command_body(s), force=force, results=results)
        elif tool == "antigravity":
            results.append(f"[antigravity] command → {_SHARED_ROOT}/workflows/<name>.md "
                           "(native invocation)")
            for s in workflow_skills:
                _write(_antigravity_workflow_path(root, s),
                       _antigravity_workflow_body(s), force=force, results=results)
        elif tool == "codex":
            results.append("[codex] command → none (skills-only: invoke as $dspx-<name>)")
        elif tool == "gemini":
            results.append("[gemini] command → .gemini/commands/dspx/<id>.toml (slash /dspx:<id>)")
            for s in workflow_skills:
                _write(_gemini_command_path(root, s),
                       _gemini_command_body(s), force=force, results=results)
        _retire_legacy(root, tool, skills, force=force, results=results)
        # hook（凍結區守門；擋改 archive/ 與手改密封檔）
        _install_hook(root, tool, results)

    return results


# ---- freeze 守門 hook（擋改 archive/）----------------------------------------
# 跨平台：hook 一律呼叫 `artispec hook ...`（邏輯在 Python），設定檔不寫各平台 shell。

def _docspec_invocation() -> str:
    """Pin the installed artispec path; unresolved PATH is reported by _install.

    The helper name stays internal and does not provide an executable alias.
    """
    resolved = shutil.which("artispec")
    if not resolved:
        return "artispec"
    # A relative PATH entry must not make hooks depend on the init shell's cwd.
    if not os.path.isabs(resolved) and not ntpath.isabs(resolved):
        resolved = str(Path(resolved).resolve())
    return f'"{resolved}"' if any(c.isspace() for c in resolved) else resolved


def _claude_guard_entry() -> dict:
    return {
        "matcher": "Edit|Write|Bash|PowerShell",   # 改檔工具 ＋ shell（bash/PS 寫檔也擋）
        "hooks": [{
            "type": "command",
            "command": f"{_docspec_invocation()} hook guard",
            "timeout": 10,
            "statusMessage": "artispec freeze guard (archive/)",
        }],
    }


def _claude_postcheck_entry() -> dict:
    return {
        "matcher": "Edit|Write",                   # 寫/改檔後做 corpus/*.yaml 完整性回饋
        "hooks": [{
            "type": "command",
            "command": f"{_docspec_invocation()} hook check",
            "timeout": 10,
            "statusMessage": "artispec completeness reminder (corpus/*.yaml)",
        }],
    }


def _codex_guard_entry() -> dict:
    # Codex 的 hook schema 與 Claude 同構（exit-2 + stderr 擋下，`artispec hook guard` 原樣可用）；
    # 檔案編輯工具叫 apply_patch（加進 matcher），shell 仍是 Bash。
    return {
        "matcher": "Edit|Write|Bash|apply_patch",
        "hooks": [{
            "type": "command",
            "command": f"{_docspec_invocation()} hook guard",
            "timeout": 10,
            "statusMessage": "artispec freeze guard (archive/)",
        }],
    }


def _codex_postcheck_entry() -> dict:
    return {
        "matcher": "Edit|Write|apply_patch",
        "hooks": [{
            "type": "command",
            "command": f"{_docspec_invocation()} hook check",
            "timeout": 10,
            "statusMessage": "artispec completeness reminder (corpus/*.yaml)",
        }],
    }


def _gemini_guard_entry() -> dict:
    # Gemini CLI hook 協定與 Claude 相容處：stdin 帶 tool_name/tool_input、exit 2＋stderr 擋下；
    # 內建工具參數同名（write_file/replace 的 file_path、run_shell_command 的 command），故
    # `artispec hook guard` 原樣可用。差異：事件叫 BeforeTool、timeout 單位是毫秒。
    return {
        "matcher": "write_file|replace|run_shell_command",
        "hooks": [{
            "name": "docspec-guard",
            "type": "command",
            "command": f"{_docspec_invocation()} hook guard",
            "timeout": 10000,
        }],
    }


def _owned_hook(hook: dict, action: str) -> bool:
    """Match exact old/new executable invocations, not another tool's substring.

    Host-shell tokenization is inappropriate for migrated Windows/POSIX paths.
    """
    if hook.get("type", "command") != "command":
        return False
    command = hook.get("command")
    if not isinstance(command, str):
        return False
    match = re.fullmatch(r'''\s*(?:"([^"\r\n]+)"|'([^'\r\n]+)'|([^\s"']+))\s+hook\s+(guard|check)\s*''', command)
    if match is None or match.group(4) != action:
        return False
    executable = next(part for part in match.groups()[:3] if part is not None)
    basename = executable.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return basename in {"docspec", "docspec.exe", "docspec.cmd", "artispec", "artispec.exe", "artispec.cmd"}


def _is_docspec_guard(entry: dict) -> bool:
    return any(_owned_hook(h, "guard") for h in (entry or {}).get("hooks", []))


def _is_docspec_postcheck(entry: dict) -> bool:
    return any(_owned_hook(h, "check") for h in (entry or {}).get("hooks", []))


def _validate_hook_settings(settings: object, path: Path) -> dict:
    """Reject unreadable structures before changing a user's settings."""
    def invalid(reason: str) -> None:
        raise SkillError(f"invalid hook settings in {path}: {reason}; repair the file and retry (not overwritten)")

    if not isinstance(settings, dict):
        invalid("top-level value must be an object")
    hooks = settings.get("hooks", {})
    if not isinstance(hooks, dict):
        invalid("hooks must be an object")
    for event, entries in hooks.items():
        # Older Gemini settings placed control fields alongside event arrays.
        # Preserve them; modern hooksConfig controls remain untouched outside hooks.
        if event in {"enabled", "notifications"}:
            if not isinstance(entries, bool):
                invalid(f"hooks.{event} must be a boolean")
            continue
        if event == "disabled":
            if not isinstance(entries, list) or not all(isinstance(name, str) for name in entries):
                invalid("hooks.disabled must be an array of names")
            continue
        if not isinstance(entries, list):
            invalid(f"hooks.{event} must be an array")
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("hooks"), list):
                invalid(f"hooks.{event} entries must be objects containing a hooks array")
            for hook in entry["hooks"]:
                if not isinstance(hook, dict):
                    invalid(f"hooks.{event} hook must be an object")
                if "command" in hook and not isinstance(hook["command"], str):
                    invalid(f"hooks.{event} hook command must be a string")
    return settings


def _without_owned_hooks(entries: list[dict], action: str) -> list[dict]:
    retained = []
    for entry in entries:
        remaining = [hook for hook in entry["hooks"] if not _owned_hook(hook, action)]
        if len(remaining) == len(entry["hooks"]):
            retained.append(entry)
        elif remaining:
            retained.append({**entry, "hooks": remaining})
    return retained


def _write_hook_settings(path: Path, guard_entry: dict, postcheck_entry: dict | None, *,
                         pre_event: str = "PreToolUse", post_event: str = "PostToolUse") -> None:
    """把 guard（工具執行前）＋postcheck（執行後，可省）冪等寫進一份 hooks 設定；事件名依工具
    （Claude/Codex＝PreToolUse/PostToolUse，Gemini＝BeforeTool）。既有非 docspec 條目保留。"""
    import json
    settings: dict = {}
    if path.exists():
        try:
            settings = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise SkillError(f"cannot read hook settings in {path}: {exc}; repair the file and retry (not overwritten)") from exc
    settings = _validate_hook_settings(settings, path)
    hooks = settings.setdefault("hooks", {})
    pre = _without_owned_hooks(hooks.get(pre_event, []), "guard")
    pre.append(guard_entry)
    hooks[pre_event] = pre
    if postcheck_entry is not None:
        post = _without_owned_hooks(hooks.get(post_event, []), "check")
        post.append(postcheck_entry)
        hooks[post_event] = post
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def _install_hook(root: Path, tool: str, results: list[str]) -> None:
    """裝 PreToolUse 守門 hook（擋改 archive/ 凍結區）＋PostToolUse 完整性回饋。

    Claude 與 Codex 的 hook schema 同構（command hook、exit-2 + stderr 擋下，`artispec hook
    guard` 原樣可用）：Claude→`.claude/settings.json`、Codex→`.codex/hooks.json`（Codex 檔案
    編輯工具 apply_patch 已納 matcher）；Gemini CLI→`.gemini/settings.json`（BeforeTool）。
    Antigravity 的 BLOCK 機制是 stdout deny-JSON（非 exit-2）且工具名/欄位拼法未經官方文件實證
    → 暫不產（避免吐壞設定），靠 engine gate（export 竄改偵測）＋lint V11 hash 抓包保護，各家通用。"""
    if tool == "claude":
        _write_hook_settings(root / ".claude" / "settings.json",
                             _claude_guard_entry(), _claude_postcheck_entry())
        results.append("[claude] hook → .claude/settings.json"
                       " (PreToolUse blocks edits to archive/; PostToolUse completeness feedback)")
    elif tool == "codex":
        _write_hook_settings(root / ".codex" / "hooks.json",
                             _codex_guard_entry(), _codex_postcheck_entry())
        results.append("[codex] hook → .codex/hooks.json"
                       " (PreToolUse blocks edits to archive/, incl. apply_patch; PostToolUse completeness feedback)")
    elif tool == "gemini":
        # 只裝 BeforeTool 守門：Gemini 的 AfterTool exit 2 會「隱藏工具結果」（非 Claude 的回饋提醒），
        # 對已寫入的檔會誤導模型以為寫入失敗——完整性回饋留給 check/publish 閘。
        _write_hook_settings(root / ".gemini" / "settings.json",
                             _gemini_guard_entry(), None, pre_event="BeforeTool")
        results.append("[gemini] hook → .gemini/settings.json"
                       " (BeforeTool blocks edits to archive/ and hand-edits of sealed stores)")
    else:  # antigravity
        results.append(
            f"[{tool}] hook not generated (BLOCK uses stdout deny-JSON, tool names not officially confirmed); "
            "freeze protection relies on the engine gate (export tamper detection) + lint V11 (hash detection).")


# ---- 子指令 -----------------------------------------------------------------

def _cmd_list(_args: argparse.Namespace) -> int:
    try:
        skills = available_skills()
    except SkillError as exc:
        sys.stderr.write(f"artispec: {exc}\n")
        return 1
    if not skills:
        print("(no built-in skills found)")
        return 0
    print(f"Built-in skills ({len(skills)}):")
    for s in skills:
        print(f"  {s.name}")
        print(f"    {s.description}")
    return 0


def _cmd_install(args: argparse.Namespace) -> int:
    tools = _TOOLS if args.tool == "all" else (args.tool,)
    root = Path(args.path).resolve()
    try:
        results = _install(root, tools, args.force)
    except SkillError as exc:
        sys.stderr.write(f"artispec: {exc}\n")
        return 1
    print(f"Installing skills to {root} (tools: {', '.join(tools)})")
    for line in results:
        print(line)
    return 0


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="artispec skills", description=HELP)
    sub = parser.add_subparsers(dest="action")

    p_list = sub.add_parser("list", help="list the built-in skills")
    p_list.set_defaults(func=_cmd_list)

    p_install = sub.add_parser("install", help="generate skills into the project")
    p_install.add_argument(
        "--tool", choices=("all", *_TOOLS), default="claude",
        help="target tool (default: claude; use the agent you actually run. "
             "`all` installs every tool — only sensible if they share memory)")
    p_install.add_argument("--path", default=".", help="project root (default: current directory)")
    p_install.add_argument(
        "--force", action="store_true", help="overwrite existing files (default: skip)")
    p_install.set_defaults(func=_cmd_install)

    args = parser.parse_args(argv)
    if not getattr(args, "action", None):
        parser.print_help()
        return 0
    return args.func(args)


def outdated_installs(root: Path) -> list[str]:
    """專案裡已安裝、但和這個 docspec 內建版本不同的 skill 與 AGENTS.md 協作區塊。

    docspec 套件更新後，專案裡的副本不會自己跟著變；重跑 `artispec init` 才會刷新。
    只比對存在的檔案（沒裝的工具不算）。"""
    out: list[str] = []
    try:
        skills = available_skills()
    except Exception:  # noqa: BLE001 — 內建資料讀不到時不擋 brief
        return out
    for base in (".claude", _SHARED_ROOT):
        for sk in skills:
            f = _skill_dir(root, base, sk) / "SKILL.md"
            if f.is_file() and not f.is_symlink() and f.read_text(encoding="utf-8") != sk.text:
                out.append(f"{f.relative_to(root)}")
    agents = root / "AGENTS.md"
    if agents.is_file():
        from dspx.commands.maintenance.init import _AGENTS_MD_BEGIN, _AGENTS_MD_END, agents_md_block, _project_lang
        text = agents.read_text(encoding="utf-8")
        b, e = text.find(_AGENTS_MD_BEGIN), text.find(_AGENTS_MD_END)
        if b >= 0 and e > b:
            current = text[b:e + len(_AGENTS_MD_END)] + "\n"
            lang = _project_lang(root / "docspec" / "config.yaml", "en")
            if current != agents_md_block(lang):
                out.append("AGENTS.md (docspec block)")
    return sorted(set(out))
