"""docspec init — 一鍵建 docspec 專案骨架（在 CWD 下建 docspec/ planning home）。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dspx.config import CONFIG_FILE_NAME
from dspx.layout import CORPUS_DIR_NAME, PLANNING_DIR_NAME

NAME = "init"
HELP = "create a docspec project skeleton in the current directory (config.yaml + corpus/)"

_CONFIG_TEMPLATE = """\
# docspec project config. Missing keys fall back to defaults.
schema: section-driven        # built-in data model (section five-file)
language: {lang}              # interaction / deliverable language (e.g. zh-TW, en)
purpose:                      # overall goal of the whole forest/project, a sentence or two (shown as develop kickoff context)
# docs_layout: flat           # flat (<article>_latest.md + archive/) | per-article (one folder per article)
# audit:                      # audit red-team core attack faces + regulatory packs
#   core: [logic, completeness, clarity, discipline, consistency]
#   packs: {}
# autonomy:                   # publish locked to human (irreversible trigger stays with the human)
#   publish: human
"""

# 寫作守則：全文件共用一份「風格」（盲渲染下唯一的跨節連貫載體）。draft/edit 由 instructions 注入。
# 語言（套 concept.brief 慣例「鍵英文/值專案語言」）：通用骨架＝英文一份（語言中性 doctrine，
# 英文寫照樣產任何語言交付）；語言特定的東西（禁開場語、需求關鍵字字典、交付語言）留到 develop
# 時用「交付語言」填進「Project conventions」區——故交付語言是 develop 決策、不在 init 定。
_WRITING_GUIDE = """\
# Writing guide

> Shared by the whole document. `draft` blind-renders each section against THIS file; `edit`
> checks the whole document against it. Coherence comes from these rules, not from peeking at
> sibling sections.
>
> **SCOPE FENCE — writing doctrine only.** Term identity → `glossary.yaml`. Versioning / file
> layout / project ops → `config.yaml` & the publish workflow. If a rule isn't about how the
> prose reads, it's in the wrong file. If this file passes ~1 screen, the rule is probably
> section-specific and belongs in that section's `concept.brief`, not here.
>
> The backbone below is **canonical English** (language-neutral doctrine). Fill **Project
> conventions** in your **deliverable language** during `develop`. (Expository defaults; a
> narrative profile may override a backbone rule — strike/replace in place, don't stack.)

## General discipline (backbone — keep)
1. **Constrained generation**: use only the projected aperture content. Never invent facts/
   numbers/rationale; mark anything missing as `[TBD]`.
2. **Render independently, no cross-section references**: you cannot see other sections. Ban
   "as above", "the next section", "in summary", "below we will".
3. **Inverted pyramid**: each section's first sentence is its conclusion; detail descends.
4. **No filler**: ban throat-clearing openers (keep the deliverable-language list below).
5. **Structure first**: rules / multi-dimensional data / state → table or list, not prose;
   obey the section's `brief.layout`.
6. **Honor the brief**: don't exceed `breadth`, don't go below `depth`, never touch `forbidden`.
7. **Normative force uses keywords** (see the deliverable-language dictionary below).
8. **Clean**: the deliverable carries no id / internal code / anchors (`{#…}`) / draft markers.
9. **Density**: one idea per paragraph, 4–5 sentences max.
10. **No metaphors / nicknames** → state responsibilities plainly.
11. **No first-person colloquialism** → formal sentences with explicit subjects.
12. **Read like a native** → write as a fluent native writer of the deliverable language would
    phrase it: natural idiom, varied sentence openings and length. NEVER calque English structure
    word-for-word — formal register is not stiff translationese. This matters most when the
    deliverable language is not English; the rules above are expository defaults, not a license to
    write translated-sounding prose.

## Project conventions (fill during `develop`, in the deliverable language)
<!-- The only zone that grows. One concrete imperative per bullet; refine in place —
     supersede, don't stack near-duplicates. Machine-checkable term identity goes to
     glossary.yaml, not here. -->
- **Deliverable language**: (e.g. zh-TW / English; which terms keep their original language)
- **Deliverable-language naturalness**: (when the language is not English, name the translationese
  phrasings to avoid and their natural replacements; note sentence-rhythm habits — this is the
  concrete face of backbone rule 12)
- **Requirement keyword dictionary**: (deliverable-language tokens for MUST / MUST NOT / SHOULD / SHOULD NOT / MAY)
- **Banned openers / filler**: (deliverable-language list for rule 4)
- **Global intro ownership**: (which section frames the whole document; others write no intro)
- **Other banned words / required phrasing**: (project-specific)
"""


# 術語權威（token 一致性）。realizes 給正名、glossary＋lint Vg 督促照用、aperture 注入寫作 agent。
# 桶＝待遇：module(自創詞/縮寫→用正名、展開、首次可附 english) /
#          standard(外部標準名→官方寫法逐字、不翻) / protocol(協定 token→位元組逐字、code 格式、不翻)。
_GLOSSARY_TEMPLATE = """\
# Project term authority (token consistency). Bucket = how draft must treat the term.
#   - id: <unique>
#     canonical: <the name prose must use>       # required
#     bucket: module | standard | protocol       # required; selects the treatment
#     code: <abbreviation, e.g. RMM>             # optional; module bucket → lint Vg2 (no bare code)
#     english: <English original>                # optional; drill-down only — gloss on first use / map to EN sources
#     definition: <one canonical sentence of what the term IS>  # optional; drill-down only (`docspec show <id>`), NOT injected
#     aliases_forbidden: [<other names>]         # optional; lint Vg1 nudges to canonical
terms: []
"""


# 可整合的 agent 工具（chatgpt＝codex 別名）
_AGENTS = ("claude", "antigravity", "codex")
_ALIASES = {"chatgpt": "codex", "openai": "codex", "gpt": "codex"}


def _resolve_tools(raw: str | None) -> tuple[str, ...] | None:
    """解析 --tool；'all'/空＝全部。回傳 None＝有非法值。"""
    if not raw or raw.strip().lower() == "all":
        return _AGENTS
    picked = []
    for tok in raw.replace(" ", "").split(","):
        if not tok:
            continue
        name = _ALIASES.get(tok.lower(), tok.lower())
        if name not in _AGENTS:
            return None
        if name not in picked:
            picked.append(name)
    return tuple(picked) or _AGENTS


def _select_tools_interactive(project_root: Path) -> tuple[str, ...] | None:
    """questionary 勾選 agent（箭頭鍵/Space/Enter）；偵測已裝者預勾。"""
    import questionary
    # 偵測＝該工具的代表 skill 檔**真的裝好**（不只資料夾存在；資料夾可能是別的工具留的空殼）
    _marker = {
        "claude": project_root / ".claude" / "skills" / "dspx-develop" / "SKILL.md",
        "antigravity": project_root / ".agent" / "skills" / "dspx-develop" / "SKILL.md",
        "codex": project_root / ".codex" / "skills" / "dspx-develop" / "SKILL.md",
    }
    detected = {tool for tool, marker in _marker.items() if marker.is_file()}
    labels = {"claude": "Claude", "antigravity": "Antigravity", "codex": "Codex (ChatGPT)"}
    choices = [
        questionary.Choice(
            labels[a] + ("  (detected)" if a in detected else ""),
            value=a, checked=(a in detected))
        for a in _AGENTS
    ]
    picked = questionary.checkbox(
        "Select AI tools to configure (↑↓ move · Space toggle · Enter confirm)",
        choices=choices).ask()
    return tuple(picked) if picked else None


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec init", description=HELP)
    parser.add_argument("--path", default=".", help="project root (default: current directory)")
    parser.add_argument("--tool", default=None,
                        help="agents to integrate (comma-separated): claude,antigravity,codex(chatgpt); default all")
    parser.add_argument("--lang", default="zh-TW",
                        help="default hint for config.language (zh-TW or en); the deliverable language is ultimately decided in develop")
    parser.add_argument("--no-tex-hint", action="store_true",
                        help="turn off the typesetting-environment hint (suggests docspec doctor when tex.lock is missing/mismatched)")
    args = parser.parse_args(argv)
    lang = args.lang.strip()

    project_root = Path(args.path).resolve()
    home = project_root / PLANNING_DIR_NAME
    config_path = home / CONFIG_FILE_NAME

    is_reinit = config_path.is_file()   # 既有專案＝重新設定（照跑介面、不毀既有檔、刷新 skill）

    # 選 agent：--tool 優先；沒給且是真人終端→動畫＋questionary 勾選；否則預設 all（不卡自動化）
    if args.tool is not None:
        tools = _resolve_tools(args.tool)
        if tools is None:
            sys.stderr.write(f"docspec: unknown agent '{args.tool}'. Choices: {', '.join(_AGENTS)} (or all)\n")
            return 2
    elif sys.stdin.isatty() and sys.stdout.isatty():
        from dspx.welcome import show_welcome
        show_welcome()             # 迴圈閃動畫＋按 Enter 才進選單（仿 OpenSpec，不直接跳）
        tools = _select_tools_interactive(project_root)
        if not tools:
            sys.stderr.write("docspec: no tool selected, cancelled.\n")
            return 2
    else:
        tools = _AGENTS   # 非 TTY（agent/CI/測試）：預設全部

    home.mkdir(parents=True, exist_ok=True)
    (home / CORPUS_DIR_NAME).mkdir(exist_ok=True)
    # scaffold：既有檔不覆寫（保留使用者客製的 config/writing-guide/glossary），只補缺
    # config/glossary/writing-guide 骨架一律英文（語言中性 doctrine）；交付語言由 develop 填進
    # writing-guide 的 Project conventions 區，config.language 先放 --lang 預設提示。
    for fname, body in (
        (CONFIG_FILE_NAME, _CONFIG_TEMPLATE.replace("{lang}", lang)),
        ("writing-guide.md", _WRITING_GUIDE),
        ("glossary.yaml", _GLOSSARY_TEMPLATE),
    ):
        p = home / fname
        if not p.is_file():
            p.write_text(body, encoding="utf-8")

    # 載入/刷新 skill 到選定 agent（重 init＝刷新，force 覆寫舊 skill 檔）
    from dspx.commands.skills_cmd import _install
    from dspx.skills import SkillError
    try:
        _install(project_root, tools, force=True)
    except SkillError as exc:
        sys.stderr.write(
            f"docspec: project scaffold created, but skill install failed — {exc}\n"
            "The packaged skill data may be incomplete; reinstall docspec, then run "
            "`docspec skills install`.\n")
        return 1

    print(f"{'Settings updated' if is_reinit else 'docspec project initialized'}: {project_root}")
    if is_reinit:
        print("  (existing config/writing-guide/glossary kept, not overwritten)")
    print(f"  docspec/: {CONFIG_FILE_NAME}  {CORPUS_DIR_NAME}/  writing-guide.md  glossary.yaml")
    print("  skills installed to (per tool = skill auto-load + command explicit invocation):")
    _dest = {
        "claude": ".claude/skills/<name>/SKILL.md + .claude/commands/dspx/<id>.md (/dspx:<id>)",
        "antigravity": ".agent/skills/<name>/SKILL.md + .agent/workflows/<name>.md (native invocation)",
        "codex": ".codex/skills/<name>/SKILL.md + $CODEX_HOME/prompts/dspx-<id>.md (⚠️ global)",
    }
    for t in tools:
        print(f"    - {t:<11} → {_dest[t]}")
    print("\nNext: docspec new <article> to create the article root section (develop will ask you about audience/scope).")

    # 被動、離線、可關的排版環境提示：tex.lock 缺或與隨包期望錯位 → 叫跑 doctor。
    # 不連網、不下載；只讀本機 tex.lock。
    if not args.no_tex_hint:
        why = _tex_env_hint_reason()
        if why is not None:
            print(f"\nTypesetting-environment hint ({why}): run `docspec doctor` to check the export/PDF environment.")
    return 0


def _tex_env_hint_reason() -> str | None:
    """被動偵測：tex.lock 不存在或與隨包期望不一致 → 回一句原因；一致/無法判 → None。

    純讀本機 tex.lock（離線、不下載）。判準＝隨包 _MANIFEST tag 與 tex.lock 記的 tag。
    """
    from dspx import paths
    lock = paths.read_tex_lock()
    if lock is None:
        return "typesetting environment not set up yet"
    try:
        from dspx.commands.setup import _MANIFEST
    except Exception:  # noqa: BLE001
        return None
    declared_tag = lock.get("tinytex_tag")
    if declared_tag != _MANIFEST["tag"]:
        return f"tex.lock's TinyTeX version ({declared_tag}) does not match the bundled expectation ({_MANIFEST['tag']})"
    return None
