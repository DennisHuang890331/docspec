"""docspec skills — 把內建 skill 安裝到三工具的技能系統。

照 OpenSpec 的 delivery='both' 模型：每個工具產**兩份**——
 (1) skill：自動載入 / Agent Skills 規格位置 <skillsDir>/skills/<name>/SKILL.md
 (2) command：使用者顯式叫用的原生 slash/workflow 位置

  | 工具        | skill（自動）                    | command（叫用）                          |
  |-------------|----------------------------------|------------------------------------------|
  | claude      | .claude/skills/<name>/SKILL.md   | .claude/commands/dspx/<id>.md  /dspx:<id>|
  | antigravity | .agent/skills/<name>/SKILL.md    | .agent/workflows/<name>.md     原生 workflow|
  | codex       | .codex/skills/<name>/SKILL.md    | $CODEX_HOME/prompts/dspx-<id>.md（全域） |

佐證：OpenSpec config.ts（各工具 skillsDir）＋ command-generation/adapters/{claude,antigravity,codex}.ts。
不產單檔 AGENTS.md——那是先前自創的設計，OpenSpec 已棄用 AGENTS.md 生成
（changelog：「Tool-specific instruction files (… AGENTS.md …) are no longer generated」）。
⚠️ codex 的 slash prompt 設計就是放 home（無專案內位置），故 command 寫到全域 $CODEX_HOME。

`--tool`（預設 claude＝只裝你實際在用的那家）；`--tool all`＝三家都裝（僅當三家共享 memory 才合理）。已存在的檔預設「跳過、不覆寫」（保護手改）；--force 覆寫。
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

from dspx.skills import Skill, SkillError, available_skills

NAME = "skills"
HELP = "install the built-in skills to Claude / Antigravity / Codex"

_TOOLS = ("claude", "antigravity", "codex")


# ---- 各工具的 skill 目錄（照 OpenSpec：每個 agent 一個資料夾、同一套 SKILL.md）----
# OpenSpec 的 skills 一律落 <skillsDir>/skills/<name>/SKILL.md（claude=.claude、
# codex=.codex、antigravity=.agent），內容是同一份完整 SKILL.md（含 frontmatter）。
# docspec 對齊此模型：三工具結構一致，不再用單檔 AGENTS.md（OpenSpec 已棄用該檔）。
_SKILLS_DIR = {"claude": ".claude", "antigravity": ".agent", "codex": ".codex"}


def _skill_path(root: Path, tool: str, skill: Skill) -> Path:
    return root / _SKILLS_DIR[tool] / "skills" / skill.name / "SKILL.md"


# ---- command（原生 slash/workflow 叫用位置）---------------------------------
# OpenSpec 預設 delivery='both'：每個工具除了 skill（自動上下文），還產一份 command
# （使用者顯式叫用的 slash/workflow）。OpenSpec 的 command 是獨立模板；docspec 只有
# 一份 skill body，故 command 直接用同一份 body（自給自足，叫用時不依賴 skill 是否載入）。
#   claude      : .claude/commands/dspx/<id>.md      → slash /dspx:<id>   (claude.ts)
#   antigravity : .agent/workflows/<name>.md         → 原生 workflow      (antigravity.ts)
#   codex       : $CODEX_HOME/prompts/dspx-<id>.md   → 全域 prompt        (codex.ts)
# <id> ＝ skill 名去掉 dspx- 前綴（develop/draft/edit/factcheck/publish/release）。

def _command_id(skill: Skill) -> str:
    return skill.name[len("dspx-"):] if skill.name.startswith("dspx-") else skill.name


def _codex_home() -> Path:
    """codex prompt 家目錄：honor CODEX_HOME，否則 ~/.codex（同 OpenSpec codex.ts）。"""
    env = os.environ.get("CODEX_HOME", "").strip()
    return Path(env) if env else Path.home() / ".codex"


def _claude_command_path(root: Path, skill: Skill) -> Path:
    return root / ".claude" / "commands" / "dspx" / f"{_command_id(skill)}.md"


def _claude_command_body(skill: Skill) -> str:
    return f"---\nname: dspx-{_command_id(skill)}\ndescription: {skill.description}\n---\n\n{skill.body}"


def _antigravity_workflow_path(root: Path, skill: Skill) -> Path:
    return root / ".agent" / "workflows" / f"{skill.name}.md"


def _antigravity_workflow_body(skill: Skill) -> str:
    return f"---\ndescription: {skill.description}\n---\n\n{skill.body}"


def _codex_prompt_path(skill: Skill) -> Path:
    return _codex_home() / "prompts" / f"dspx-{_command_id(skill)}.md"


def _codex_prompt_body(skill: Skill) -> str:
    return f"---\ndescription: {skill.description}\nargument-hint: command arguments\n---\n\n{skill.body}"


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
    import shutil
    if dst.exists() and not force:
        results.append(f"  = exists, skipped: {dst} (use --force to overwrite)")
        return
    verb = "overwrote" if dst.exists() else "created"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    results.append(f"  + {verb}: {dst}")


def _install(root: Path, tools: tuple[str, ...], force: bool) -> list[str]:
    skills = available_skills()
    if not skills:
        raise SkillError("no built-in skills found (package data missing?)")
    results: list[str] = []

    for tool in _TOOLS:
        if tool not in tools:
            continue
        # 1) skill（自動載入 / Agent Skills 規格位置）。support skill（如 dspx-diagram）
        #    隨帶其 scripts/ 等輔助檔一起落地——subagent 載入後要能跑 vendored scripts。
        results.append(f"[{tool}] skill → {_SKILLS_DIR[tool]}/skills/<name>/SKILL.md")
        for s in skills:
            skill_md = _skill_path(root, tool, s)
            _write(skill_md, s.text, force=force, results=results)
            for aux in s.aux_files:
                rel = aux.relative_to(s.source.parent)
                _copy(aux, skill_md.parent / rel, force=force, results=results)
        # 2) command（原生 slash/workflow 叫用位置；照 OpenSpec delivery='both'）。
        #    只給 workflow skill 產 command——support skill 由 subagent 載入、非人顯式叫用的階段。
        workflow_skills = [s for s in skills if s.is_workflow]
        if tool == "claude":
            results.append("[claude] command → .claude/commands/dspx/<id>.md (slash /dspx:<id>)")
            for s in workflow_skills:
                _write(_claude_command_path(root, s),
                       _claude_command_body(s), force=force, results=results)
        elif tool == "antigravity":
            results.append("[antigravity] command → .agent/workflows/<name>.md (native invocation)")
            for s in workflow_skills:
                _write(_antigravity_workflow_path(root, s),
                       _antigravity_workflow_body(s), force=force, results=results)
        elif tool == "codex":
            results.append(
                f"[codex] command → {_codex_home()}/prompts/dspx-<id>.md (⚠️ global; slash /dspx-<id>)")
            for s in workflow_skills:
                _write(_codex_prompt_path(s),
                       _codex_prompt_body(s), force=force, results=results)
        # 3) hook（凍結區守門；擋改 archive/。Claude 已驗證格式，其餘見 README/說明）
        _install_hook(root, tool, results)

    return results


# ---- freeze 守門 hook（擋改 archive/）----------------------------------------
# 跨平台：hook 一律呼叫 `docspec hook ...`（邏輯在 Python），設定檔不寫各平台 shell。

def _docspec_invocation() -> str:
    """hook 指令叫用 docspec 的方式：安裝時解析**絕對路徑**（`shutil.which`），避免 hook 在
    PATH 尚未更新／被沙箱清過的 shell 裡找不到 docspec 而靜默不守門（凍結保護失效）；
    含空白則加引號（cmd/sh 皆可）；解不到才退回裸 `docspec`。"""
    resolved = shutil.which("docspec")
    if not resolved:
        return "docspec"
    return f'"{resolved}"' if " " in resolved else resolved


def _claude_guard_entry() -> dict:
    return {
        "matcher": "Edit|Write|Bash|PowerShell",   # 改檔工具 ＋ shell（bash/PS 寫檔也擋）
        "hooks": [{
            "type": "command",
            "command": f"{_docspec_invocation()} hook guard",
            "timeout": 10,
            "statusMessage": "docspec freeze guard (archive/)",
        }],
    }


def _claude_postcheck_entry() -> dict:
    return {
        "matcher": "Edit|Write",                   # 寫/改檔後做 corpus/*.yaml 完整性回饋
        "hooks": [{
            "type": "command",
            "command": f"{_docspec_invocation()} hook check",
            "timeout": 10,
            "statusMessage": "docspec completeness reminder (corpus/*.yaml)",
        }],
    }


def _codex_guard_entry() -> dict:
    # Codex 的 hook schema 與 Claude 同構（exit-2 + stderr 擋下，`docspec hook guard` 原樣可用）；
    # 檔案編輯工具叫 apply_patch（加進 matcher），shell 仍是 Bash。
    return {
        "matcher": "Edit|Write|Bash|apply_patch",
        "hooks": [{
            "type": "command",
            "command": f"{_docspec_invocation()} hook guard",
            "timeout": 10,
            "statusMessage": "docspec freeze guard (archive/)",
        }],
    }


def _codex_postcheck_entry() -> dict:
    return {
        "matcher": "Edit|Write|apply_patch",
        "hooks": [{
            "type": "command",
            "command": f"{_docspec_invocation()} hook check",
            "timeout": 10,
            "statusMessage": "docspec completeness reminder (corpus/*.yaml)",
        }],
    }


def _is_docspec_guard(entry: dict) -> bool:
    # 比對 `hook guard` 子命令（容忍 docspec 被寫成絕對路徑＝C4 portability 修法）。
    for h in (entry or {}).get("hooks", []):
        if "hook guard" in str(h.get("command", "")):
            return True
    return False


def _is_docspec_postcheck(entry: dict) -> bool:
    for h in (entry or {}).get("hooks", []):
        if "hook check" in str(h.get("command", "")):
            return True
    return False


def _write_hook_settings(path: Path, guard_entry: dict, postcheck_entry: dict) -> None:
    """把 guard(PreToolUse)＋postcheck(PostToolUse) 冪等寫進一份 hooks 設定（Claude/Codex 同構）。"""
    import json
    settings: dict = {}
    if path.is_file():
        try:
            settings = json.loads(path.read_text(encoding="utf-8")) or {}
        except json.JSONDecodeError:
            settings = {}
    hooks = settings.setdefault("hooks", {})
    pre = [e for e in hooks.get("PreToolUse", []) if not _is_docspec_guard(e)]
    pre.append(guard_entry)
    hooks["PreToolUse"] = pre
    post = [e for e in hooks.get("PostToolUse", []) if not _is_docspec_postcheck(e)]
    post.append(postcheck_entry)
    hooks["PostToolUse"] = post
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def _install_hook(root: Path, tool: str, results: list[str]) -> None:
    """裝 PreToolUse 守門 hook（擋改 archive/ 凍結區）＋PostToolUse 完整性回饋。

    Claude 與 Codex 的 hook schema 同構（command hook、exit-2 + stderr 擋下，`docspec hook
    guard` 原樣可用）：Claude→`.claude/settings.json`、Codex→`.codex/hooks.json`（Codex 檔案
    編輯工具 apply_patch 已納 matcher）。Antigravity 的 BLOCK 機制是 stdout deny-JSON（非
    exit-2）且工具名/欄位拼法未經官方文件實證 → 暫不產（避免吐壞設定），靠 engine gate
    （export 竄改偵測）＋lint V11 hash 抓包保護，三家通用。"""
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
    else:  # antigravity
        results.append(
            f"[{tool}] hook not generated (BLOCK uses stdout deny-JSON, tool names not officially confirmed); "
            "freeze protection relies on the engine gate (export tamper detection) + lint V11 (hash detection).")


# ---- 子指令 -----------------------------------------------------------------

def _cmd_list(_args: argparse.Namespace) -> int:
    try:
        skills = available_skills()
    except SkillError as exc:
        sys.stderr.write(f"docspec: {exc}\n")
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
        sys.stderr.write(f"docspec: {exc}\n")
        return 1
    print(f"Installing skills to {root} (tools: {', '.join(tools)})")
    for line in results:
        print(line)
    if shutil.which("docspec") is None:
        print("\n⚠ `docspec` is not on this shell's PATH — your agent tools (Codex/Antigravity/Claude)")
        print("  will hit \"docspec: command not recognized\". Add the uv tools bin dir to PATH:")
        print("    uv tool update-shell    # then fully restart the agent tool's terminal/session")
        print("  (the binary lives in `uv tool dir --bin`, normally ~/.local/bin).")
    return 0


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec skills", description=HELP)
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
