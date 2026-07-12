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
_WRITING_GUIDE_BACKBONE = """\
# Writing guide

> Shared by the whole document. `apply` (rewrite mode) blind-renders each section against THIS file;
> `apply` (align mode) checks the whole document against it. Coherence comes from these rules, not from peeking at
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
4. **No filler, no scaffolding-narration**: ban throat-clearing openers (keep the deliverable-language
   list below); and NEVER narrate this section's own `brief` — don't announce its scope ("this section
   specifies…"), exclusions ("not covered here"), verifiability ("verifiability:…"), or downstream /
   governance constraints. The brief is a constraint you obey, not content you recite; open on the
   payload (rule 3), and the section's role shows through the content, never declared. This applies to
   the OVERVIEW / root section at the *document* level too: it orients by SUBJECT and key idea, NEVER
   by narrating the document's own layout — no prose table of contents ("first… then… finally…",
   「先以…再以…最後…」, 「各章環環相扣」) and no self-reference to the document as an artifact
   ("this spec splits the work into…", 「本規範把這項工作拆成…／把…整合成一份…文件」). The chapter
   order reveals itself as the reader proceeds; it is never announced.
5. **Structure first**: rules / multi-dimensional data / state → table or list, not prose;
   obey the section's `brief.layout`.
6. **Honor the brief**: don't exceed `breadth`, don't go below `depth`, never touch `forbidden`.
7. **Normative force uses keywords** (see the deliverable-language dictionary below).
8. **Clean**: the deliverable carries no id / internal code / anchors (`{#…}`) / draft markers,
   **and no authoring-tool / governance vocabulary** — it is for domain readers, not for operators
   of this tool. Never surface backstage words (forest / governed-by / governance parent /
   Tier-1·2·3 / L2a / diamond fan-in / module-section / factcheck / raise a finding).
   Express document relationships in domain language instead: name the document (《…》), write "per
   the principles in 《…》" or "see 《…》", and "the sections of this spec" — not "module-sections".
   For a cross-reference to another SECTION (same document or internal cross-document), write the
   stable cross-reference **anchor** where the number belongs — `<!--@<target-concept-id>--><!--@-->`
   — and let `render` inject the live `§N` between the two invisible comments (re-derived every
   render, so it never dangles). The **anchor-injected `§N` IS the sanctioned form**; what is banned
   is a **hand-typed** chapter number / literal `§N` / 第 N 章 (a hand-typed number drifts on any
   reorder — the real corpus lost 94–107 cross-refs to exactly this). So write 「（詳見<錨>）」/
   "see §N (via the anchor)", never a number you typed yourself. External-standard clause citations
   (ISO 13849-1 §4.2) stay literal — the anchor is for internal references only.
9. **Density**: one idea per paragraph, 4–5 sentences max.
10. **No metaphors / nicknames** → state responsibilities plainly.
11. **No first-person colloquialism** → formal sentences with explicit subjects.
12. **Read like a native** → write as a fluent native writer of the deliverable language would
    phrase it: natural idiom, varied sentence openings and length. NEVER calque English structure
    word-for-word — formal register is not stiff translationese. This matters most when the
    deliverable language is not English; the rules above are expository defaults, not a license to
    write translated-sounding prose. Chinese-translationese and AI-sounding-English are two
    different diseases with two different fixes, not the same rule in two languages — the naturalness
    bullet below is pre-seeded for zh-TW/en from `docspec reference writing-<lang>`; for any other
    language run that command yourself (or `docspec reference` for the index) and write the
    language's own defect list here — don't guess at what "sounds native" from this rule's name alone.

"""

# 自然度 bullet 種子＝docspec reference writing-{zh,en} 的濃縮版（動作句、非長篇論證+出處；論證/出處
# 留給 reference 指令查）。只有「語言本身」的通用規則（不分文類都成立）才進這裡；文類特有的東西
# （附錄A 規範詞/EARS、特定領域禁詞）留給 develop 依實際文類另外補——這條線是「通用 vs 文類特化」，
# 不是舊版「10 檔 genre×language profile」那種整份預寫文案（設計理由見
# openspec/changes/2026-06-30-chinese-writing-profiles/design.md「被否決的路」）。
_ZH_NATURALNESS_SEED = """\
- **Deliverable-language naturalness** (seeded from `docspec reference writing-zh`; re-run it for
  the full reasoning/citations, or if this is a normative/spec document also pull in the 規範詞
  與需求句紀律 table):
  - 動詞當家：把「進行/作出/予以/加以＋名詞」還原成動詞（「進行查核」→「查核」）；同類弱動詞
    （施加/執行/實施/造成/受到）逐個判斷，別無腦改。
  - 被字句只用在真正不如意的事：中性/正面的事不加「被」（「他被升為營長」→「他升為營長」）。
  - 「的」不連三層以上：定語堆疊三層以上拆成後置短句。
  - 連接詞只留扛邏輯的：純裝飾的「和／由於…所以／當…的時候」能省則省，因果/條件接榫
    （因為…所以、若…則）留著。
  - 冗詞與空範疇詞直接刪：「有很多問題存在」→「問題很多」；「作為一個…」通常是英文直譯可刪。
  - 結構性內容交給版面：規則/介面/狀態機用表格條列，不用散文扛三層條件。
  - 段落用內容銜接：指前文用「上述兩道措施」，不要「如前所述」這種報幕式連結。
  - 禁報幕：不寫「本節規範…／本節說明…／可驗證性:／設計依據:」這類元敘述，直接給結論/規定/事實。
  - 語域一以貫之：選定正式度後不中途轉口語/行銷腔。
"""

_EN_NATURALNESS_SEED = """\
- **Deliverable-language naturalness** (seeded from `docspec reference writing-en`; re-run it for
  the full reasoning/citations, or for the RFC 2119 requirement-keyword table on a normative
  document):
  - Verb-centric: turn nominalizations back into verbs ("make a decision" → "decide"); scan
    `-tion`/`-ment`/`-ity` stacked with a weak verb (*is, has, undergoes*).
  - Active voice by default: "the system validates the request", not "the request is validated by
    the system"; use the passive only when the actor is unknown or irrelevant.
  - Cut the hedge-and-inflate pattern: say the claim directly, or mark it `[TBD]` — don't
    manufacture false modesty around a claim you're actually making.
  - Avoid the AI-ism word list: delve, tapestry, realm, leverage (as a verb), utilize, seamless,
    robust, boasts, testament to — prefer the plain, shorter word.
  - Em-dash / "not just X — it's Y" only for a genuine interruption or emphasis, never as default
    connective tissue between clauses.
  - No throat-clearing openers or closers: cut "In today's fast-paced world" and generic
    "In conclusion, X is a multifaceted topic" restatements.
  - No self-narration of the document's own structure: state the content directly, don't announce
    "this section will discuss X" or "first... then... finally...".
  - Default to prose for explanation; reserve lists for genuinely enumerable, parallel items
    (avoid bullet-itis).
"""

_GENERIC_NATURALNESS_PLACEHOLDER = """\
- **Deliverable-language naturalness**: (fill-in guidance — this is the concrete face of backbone
  rule 12: docspec ships no bundled reference for this language yet. (1) run `docspec reference`
  to confirm, and check `writing-zh`/`writing-en` for the shape a reference doc takes; (2) draft
  concrete bad→good pairs for THIS project's language and genre, citing a real, checkable source
  — never invent an example or an equivalence a source doesn't actually make; (3) ask the human to
  confirm or adjust before treating this bullet as final — writing-guide.md is shared, load-bearing
  doctrine, not something to silently auto-fill)
"""


def _naturalness_seed(lang: str) -> str:
    """語言已知（zh-TW/zh-CN 等 zh 系、en）→ 種通用規則濃縮版；其他語言→維持填寫指引佔位。"""
    norm = lang.strip().lower()
    if norm.startswith("zh"):
        return _ZH_NATURALNESS_SEED
    if norm == "en" or norm.startswith("en-") or norm.startswith("en_"):
        return _EN_NATURALNESS_SEED
    return _GENERIC_NATURALNESS_PLACEHOLDER


def build_writing_guide(lang: str) -> str:
    """組出完整 writing-guide.md：語言中性 backbone（不變）＋ Project Conventions（自然度 bullet
    依 `--lang` 種對應語言的通用規則濃縮版；其餘 bullet 維持文類特化的填寫佔位，因為文類要 develop
    才決定）。"""
    deliverable_language_hint = (
        f"{lang} (confirm/adjust during develop; which terms keep their original language)"
        if lang.strip() else "(e.g. zh-TW / English; which terms keep their original language)"
    )
    return _WRITING_GUIDE_BACKBONE + f"""\
## Project conventions (fill during `develop`, in the deliverable language)
<!-- The only zone that grows. One concrete imperative per bullet; refine in place —
     supersede, don't stack near-duplicates. Machine-checkable term identity goes to
     glossary.yaml, not here. -->
- **Deliverable language**: {deliverable_language_hint}
{_naturalness_seed(lang)}\
- **Requirement keyword dictionary**: (deliverable-language tokens for MUST / MUST NOT / SHOULD / SHOULD NOT / MAY)
- **Banned openers / filler**: (deliverable-language list for rule 4)
- **No report-style section metadiscourse**: (deliverable-language ban for rule 4 — e.g. 不寫
  「本節規範…／本節不寫…／可檢核性:…／本節約束下游…／設計依據:…」這類報幕句;每節直接從主旨切入,角色由內容浮現、不宣告)
- **Global intro ownership**: (which section frames the whole document; others write no intro)
- **No backstage vocabulary**: (deliverable-language replacements for any authoring-tool / governance
  term — e.g. don't write 森林/治理父/governed-by/Tier-N/L2a/fan-in/factcheck/§<section>; name the
  document and say "依據《…》" / "詳見《…》" instead)
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


# .gitattributes 腳手架（fingerprint v2 D2 防禦縱深第三層）：repo 端把 docspec 管的文字檔
# 釘 eol=lf——引擎讀端已正規化（D1）、寫端已釘 LF（D2），這層讓 git autocrlf 也不再翻譯換行
# ＝三層任一失守其餘仍保住。建議性、非閘門；既有專案自行補上（`docspec guide` 有提示）。
_GITATTRIBUTES_TEMPLATE = """\
# docspec: pin LF for the text files the engine fingerprints/writes, so fingerprints
# and the freeze hash net stay byte-identical across OS / git autocrlf / worktrees.
*.md text eol=lf
*.yaml text eol=lf
*.yml text eol=lf
"""


# 可整合的 agent 工具（chatgpt＝codex 別名）
_AGENTS = ("claude", "antigravity", "codex")
DEFAULT_AGENT = "claude"   # 非互動預設只裝這一家（要全裝＝ `--tool all`）
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
    parser.add_argument("--no-update-check", action="store_true",
                        help="skip the non-blocking update check (git install: compares against GitHub HEAD with a ≤2s timeout, silent on any failure; directory install: offline snapshot reminder)")
    args = parser.parse_args(argv)
    lang = args.lang.strip()

    project_root = Path(args.path).resolve()
    home = project_root / PLANNING_DIR_NAME
    config_path = home / CONFIG_FILE_NAME

    is_reinit = config_path.is_file()   # 既有專案＝重新設定（照跑介面、不毀既有檔、刷新 skill）

    # 選 agent：--tool 優先；沒給且是真人終端→動畫＋questionary 勾選；否則預設**單一 claude**
    # （別灑三家＝避免 .claude/.agent/.codex 三份污染專案；三家 skill 各自獨立、不共享 memory，
    #  故只該裝使用者實際在用的那家。要全裝＝明確 `--tool all`。）
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
        tools = (DEFAULT_AGENT,)   # 非 TTY（agent/CI/測試）：預設單一 agent，不灑三家

    home.mkdir(parents=True, exist_ok=True)
    (home / CORPUS_DIR_NAME).mkdir(exist_ok=True)
    # scaffold：既有檔不覆寫（保留使用者客製的 config/writing-guide/glossary），只補缺
    # config/glossary/writing-guide 骨架一律英文（語言中性 doctrine）；交付語言由 develop 填進
    # writing-guide 的 Project conventions 區，config.language 先放 --lang 預設提示。
    for fname, body in (
        (CONFIG_FILE_NAME, _CONFIG_TEMPLATE.replace("{lang}", lang)),
        ("writing-guide.md", build_writing_guide(lang)),
        ("glossary.yaml", _GLOSSARY_TEMPLATE),
    ):
        p = home / fname
        if not p.is_file():
            p.write_text(body, encoding="utf-8", newline="\n")

    # .gitattributes（專案根）：釘 LF、跨 OS 指紋位元一致；既有檔不覆寫（保留使用者客製）。
    gitattributes = project_root / ".gitattributes"
    if not gitattributes.is_file():
        gitattributes.write_text(_GITATTRIBUTES_TEMPLATE, encoding="utf-8", newline="\n")

    # 載入/刷新 skill 到選定 agent（重 init＝刷新，force 覆寫舊 skill 檔）
    from dspx.commands.maintenance.skills_cmd import _install
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
    print("  .gitattributes: pins eol=lf for the fingerprinted text files (keeps fingerprints "
          "byte-identical across OS/worktrees)")
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

    # 非阻塞更新檢查（有界超時、失敗全靜默；絕不擋 init、絕不改離開碼）。
    if not args.no_update_check:
        _print_update_check()
    return 0


def _github_head_sha(timeout: float = 2.0) -> str | None:
    """GitHub 上 docspec repo 的 HEAD commit sha。任何失敗由呼叫端吞掉。

    ★8.6 硬牆時鐘：socket `timeout` 不涵蓋 DNS 解析（getaddrinfo 可 hang 數十秒——dogfood
    實測 init 卡 2 分鐘的根因）。故整個抓取跑在 daemon thread、以 `join(deadline)` 硬上限收斂；
    逾時＝放棄該執行緒（daemon、不阻塞 init）、回 None。"""
    import threading
    result: dict = {}

    def _fetch() -> None:
        try:
            import json
            import urllib.request
            from dspx import _install_source
            api = f"https://api.github.com/repos/{_install_source.GIT_REPO}/commits/HEAD"
            req = urllib.request.Request(
                api, headers={"Accept": "application/vnd.github+json", "User-Agent": "docspec-init"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.load(resp)
            sha = data.get("sha")
            if isinstance(sha, str) and sha:
                result["sha"] = sha
        except Exception:  # noqa: BLE001 — 任何失敗＝靜默、無更新資訊
            pass

    th = threading.Thread(target=_fetch, daemon=True)
    th.start()
    th.join(timeout + 1.5)   # 硬牆：socket 逾時 + DNS/解析餘裕；逾此即放棄（daemon 續跑不阻塞）
    return result.get("sha")


def _print_update_check() -> None:
    """非阻塞更新提醒：git 裝比對 GitHub HEAD（落後印一行）；目錄裝離線印快照提醒。

    ★鐵律：任何例外（無網/DNS/HTTP/429/schema 意外/direct_url 缺/超時）一律**靜默跳過**——
    不印錯誤、不改離開碼、不阻塞 init。離線環境的 git 裝路徑＝完全無輸出（零煩擾）。
    """
    try:
        from dspx import _install_source
        src = _install_source.read_install_source()
        if src is None:
            return
        if src["kind"] == "dir":
            # 目錄安裝：**不連網**，直接印快照可能落後提醒＋更新指令。
            print(f"\nUpdate: this is a local build snapshot ({src['path']}) and may lag the source. "
                  f"To update: {_install_source.update_command(src)}")
            return
        if src["kind"] == "git":
            head = _github_head_sha()
            commit = src["commit"]
            if not head:
                return
            same = head.startswith(commit) or commit.startswith(head)
            if not same:
                print(f"\nUpdate available: your git install ({commit[:12]}) is behind the latest on GitHub. "
                      f"To update: {_install_source.update_command(src)}")
    except Exception:  # noqa: BLE001 — 更新檢查永不擋 init、永不改離開碼
        return


def _tex_env_hint_reason() -> str | None:
    """被動偵測：tex.lock 不存在或與隨包期望不一致 → 回一句原因；一致/無法判 → None。

    純讀本機 tex.lock（離線、不下載）。判準＝隨包 _MANIFEST tag 與 tex.lock 記的 tag。
    """
    from dspx import paths
    lock = paths.read_tex_lock()
    if lock is None:
        return "typesetting environment not set up yet"
    try:
        from dspx.commands.maintenance.setup import _MANIFEST
    except Exception:  # noqa: BLE001
        return None
    declared_tag = lock.get("tinytex_tag")
    if declared_tag != _MANIFEST["tag"]:
        return f"tex.lock's TinyTeX version ({declared_tag}) does not match the bundled expectation ({_MANIFEST['tag']})"
    return None
