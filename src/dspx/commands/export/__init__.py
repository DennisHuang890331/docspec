"""docspec export <article> — 把已凍結的定稿快照確定性轉成 PDF（Typst 預設）或發射期刊 .tex。

★薄引擎鐵律：export 只做確定性編排（subprocess pandoc → typst/LaTeX），不碰 PDF 二進位。
內容 byte-lock：一個字不改、只動呈現。

管線（兩軌）：
  Typst 軌（預設）：取快照 → pandoc -t typst → typst compile（受控字型）→ PDF。
  Journal 軌（emit-only）：取快照 → pandoc --template=<journal> → .tex（不編譯；交 Overleaf）。

soft-dep：pandoc/typst 缺了 → 印安裝指引、不 crash。

此檔案為 export 子套件的入口＋CLI 主流程；各主題模組（設定合成/預處理/資產/typst 軌/
journal 軌/忠實度驗證/pack 完整性 gate/housekeeping）分在同夾的 `_config`/`_preprocess`/
`_assets`/`_typst_track`/`_journal_track`/`_fidelity`/`_pack_gate`/`_housekeeping`（純內部
拆分、零行為改變）。以下 re-export 讓 `dspx.commands.export.<name>` 對外行為與拆分前的
單一 `export.py` 完全相同（含測試的 `monkeypatch.setattr(export_cmd, "_pandoc_path", …)`
等 module-attribute patch 仍然生效——被 monkeypatch 的名字只在本檔的 `run()` 內被呼叫，
故 patch 落在本模組全域即生效，無需跨模組延遲查找）。
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

from dspx import paths
from dspx.commands._shared import BootstrapError, bootstrap
from dspx.format_config import (
    FormatConfigError,
    pandoc_highlight_style,
    validate_format_config,
)
from dspx.layout import Layout, parse_semver

from ._assets import (
    _collect_referenced_assets,
    _copy_assets_into,
    _figure_health_warnings,
)
from ._config import (
    _PANDOC_FROM,
    _export_config,
    _pandoc_path,
    _resolve_format,
    _section_merge,
)
from ._fidelity import (
    _is_cjk,
    _nfc,
    _pdf_paged_stream,
    _sample,
    _source_anchored_stream,
    _verify_byte_lock,
    _window,
)
from ._housekeeping import _prune_old_pdfs, _resolve_input
from ._journal_track import (
    _ATX_RE,
    _FRONTMATTER_HEADINGS,
    _emit_journal,
    _resolve_journal_template,
    _strip_journal_frontmatter,
)
from ._pack_gate import _check_pack_integrity
from ._preprocess import (
    _RAW_LATEX_BLOCK_RE,
    _TYPST_COLS_RE,
    _TYPST_MATH_RE,
    _TYPST_MATH_SYMBOL_FIXES,
    _balance_table_columns,
    _denumber_manual_headings,
    _fix_typst_math,
    _strip_raw_latex,
)
from ._typst_track import _H1_RE, _build_pdf_typst, _split_title_body

NAME = "export"
HELP = "Deterministically render a frozen snapshot to PDF (bundled template pack; content byte-locked, only presentation changes) → docs/exports/"

_INSTALL_HINT = (
    "For pandoc, install the export dependency: uv pip install 'docspec[export]' (or a system pandoc). "
    "For fonts / typst, run `docspec setup` (one-time)."
)

# 缺排版引擎/字型的統一提示。
_SETUP_HINT = (
    "Run `docspec setup` to install the controlled typst binary + OFL fonts (one-time, ~30 MB)."
)


# ── --template 內容物路由 / ejected 包 provenance ─────────────────

def _route_by_template(d: Path) -> str | None:
    """依 `--template <dir>` 內容物推斷引擎軌：template.typ→typst、template.tex→journal。

    兩者皆有→需明確 --engine（報錯、回 None）；皆無/夾不存在→指名報缺（回 None）。
    明確 --engine 由呼叫端優先處理、不進此函式。
    """
    if not d.is_dir():
        sys.stderr.write(f"docspec: --template directory does not exist: {d}\n")
        return None
    has_typ = (d / "template.typ").is_file()
    has_tex = (d / "template.tex").is_file()
    if has_typ and has_tex:
        sys.stderr.write(
            f"docspec: --template {d} contains BOTH template.typ and template.tex — "
            "pass --engine typst or --engine journal to choose the track.\n")
        return None
    if has_typ:
        return "typst"
    if has_tex:
        return "journal"
    sys.stderr.write(
        f"docspec: --template {d} contains neither template.typ (Typst track) nor "
        "template.tex (journal track) — nothing to route to.\n")
    return None


def _eject_provenance_notice(pack_dir: Path) -> str | None:
    """ejected 包的 provenance 版本 ≠ 現行 dspx 版本 → 回一行落後提示（不擋）；無 provenance/相同→None。"""
    prov = pack_dir / ".ejected-from.json"
    if not prov.is_file():
        return None
    try:
        data = json.loads(prov.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    old = data.get("version")
    from dspx import __version__
    if old and str(old) != __version__:
        return (f"docspec: ℹ template-pack was ejected from docspec {old}; current is {__version__} "
                "— re-eject (`docspec template eject --force`) to pick up template fixes.")
    return None


# ── 主流程 ────────────────────────────────────────────────────────

def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec export", description=HELP)
    parser.add_argument("article", help="name of the article to export")
    parser.add_argument("--format", choices=["pdf"], default="pdf",
                        help="output format (pdf only)")
    parser.add_argument("--engine", choices=["latex", "typst", "journal"], default=None,
                        help="render engine: typst (DEFAULT; docspec-typst owned template + lightweight typst binary, native CJK), "
                             "or journal (BYO LaTeX, EMIT-ONLY: emits a .tex through a journal pandoc template via the slot contract, "
                             "does NOT compile). latex is RETIRED (errors with guidance). "
                             "Overrides the project's export.engine config; default is typst. (--journal implies journal.)")
    parser.add_argument("--journal", default=None, metavar="NAME",
                        help="journal adapter for the emit-only journal track (bundled: ieee, elsevier; or use --template <dir> "
                             "with a template.tex for a BYO journal). Selecting it implies --engine journal.")
    parser.add_argument("--slots", default=None, metavar="FILE",
                        help="a YAML file of slot values (authors/abstract/keywords/…) for the journal/slot contract; "
                             "merged over the project export.slots config")
    parser.add_argument("--version", default=None, help="specific published version (semver X.Y.Z; default latest)")
    parser.add_argument("--latest", action="store_true",
                        help="export the working copy _latest (preview, not a final draft) instead of a frozen snapshot")
    parser.add_argument("--template", default=None, metavar="DIR",
                        help="BYO template pack directory, routed by CONTENT: a template.typ selects the Typst track "
                             "(BYO replacement for the bundled pack, integrity gate skipped — see `docspec template eject`); "
                             "a template.tex selects the journal track (pandoc LaTeX template honoring the slot contract); "
                             "both present requires an explicit --engine. Overrides the project's export.template config.")
    parser.add_argument("--fonts", default=None, metavar="DIR",
                        help="a user font directory (e.g. a locally licensed real Kai font) to replace data_dir/fonts; "
                             "missing dir / missing required font files are rejected (no PDF produced)")
    parser.add_argument("--format-config", default=None, metavar="FILE",
                        help="a per-article format-knob override file (YAML; overrides the project export.format knobs of the same name). "
                             "Knobs = validated values (font enum / font-size range / table style…); bad values are rejected before "
                             "compiling to LaTeX and no PDF is produced")
    parser.add_argument("--profile", default=None,
                        choices=["default", "academic", "paper", "manual", "essay", "novel"],
                        help="Typst document-type layout profile (overrides project export.profile): "
                             "default | academic (single-column serif body + sans headings, indented paragraphs) | "
                             "paper (two-column academic; title/abstract span both columns, 10pt body — IEEE/journal style) | "
                             "manual (sans body, code/admonition-friendly) | essay (quiet unnumbered headings) | "
                             "novel (first-line indent, * * * scene breaks, sunk chapter openers)")
    parser.add_argument("--allow", action="store_true",
                        help="escape hatch: explicitly allow exporting with a hand-edited bundled template pack (by default any detected change is rejected, "
                             "forcing you through knobs or your own --template pack)")
    parser.add_argument("--ack", action="store_true",
                        help="render fidelity: run the check and print the diff locations, but return 0 (you've already re-checked that page with docspec proof "
                             "= render is faithful / extraction misfire, not real character loss)")
    parser.add_argument("--no-verify", action="store_true",
                        help="skip the post-export render-fidelity verification entirely (for debugging; --ack is the proper \"re-checked, allowed\")")
    parser.add_argument("--keep", action="store_true",
                        help="keep this article's previously-generated PDFs (by default a successful export removes the article's other "
                             "PDFs in docs/exports/ — older versions + the _vlatest preview — so only the latest deliverable remains)")
    args = parser.parse_args(argv)

    try:
        layout, config = bootstrap()
    except BootstrapError as exc:
        return exc.exit_code

    econf = _export_config(config)
    # 文類版面 profile：--profile 旗標 > 專案 export.profile config > default。
    from dspx.config import EXPORT_PROFILES
    profile = args.profile or econf.get("profile") or "default"
    if profile not in EXPORT_PROFILES:
        sys.stderr.write(f"docspec: unknown export profile '{profile}' — valid: {', '.join(EXPORT_PROFILES)}.\n")
        return 1
    # 模板夾：--template 旗標 > 專案 export.template config（非空、相對專案根解析）。
    template_dir: Path | None = None
    if args.template:
        template_dir = Path(args.template)
    elif econf.get("template"):
        template_dir = layout.project_root / str(econf["template"])
    template_override = str(template_dir) if template_dir is not None else None

    # render 引擎：--engine 旗標 > --journal 隱含 journal > 依模板夾內容物路由（template.typ→typst BYO、
    #   template.tex→journal）> 專案 export.engine config > 預設 typst。明確 --engine 恆優先於內容推斷。
    engine = args.engine
    if engine is None and args.journal:
        engine = "journal"
    if engine is None and template_dir is not None:
        engine = _route_by_template(template_dir)
        if engine is None:
            return 1   # 內容物路由失敗（不存在/兩者皆有需 --engine/皆無）已報錯。
    if engine is None:
        engine = econf.get("engine") or "typst"

    # latex 軌已退場（docspec-cas LPPL 包已移除）。
    if engine == "latex":
        sys.stderr.write(
            "docspec: the LaTeX/xelatex track has been retired — "
            "use --engine typst (default) or --engine journal for journal submission (.tex emit-only).\n")
        return 1

    if engine == "typst" and args.format_config:
        from dspx.format_config import _TYPST_KNOB_FOLLOWUPS
        sys.stderr.write(
            "docspec: ⚠ Typst track applies the font-size / leading / margin / first-line-indent / "
            "code-highlight knobs; still NOT mapped (house defaults used): "
            f"{', '.join(_TYPST_KNOB_FOLLOWUPS)}.\n")

    # 格式旋鈕：合成（專案 export.format ＋ --format-config 檔）並**驗證**。
    try:
        knobs = _resolve_format(econf, args.format_config)
    except FormatConfigError as exc:
        sys.stderr.write(f"docspec: invalid format knob — {exc} (no PDF produced)\n")
        return 1
    highlight_style = pandoc_highlight_style(knobs)

    resolved = _resolve_input(layout, args.article, args.version, args.latest)
    if resolved is None:
        return 1
    snapshot, label = resolved

    pandoc = _pandoc_path()
    if pandoc is None:
        sys.stderr.write(f"docspec: pandoc not found — export needs it. {_INSTALL_HINT}\n")
        return 1

    title, body_md = _split_title_body(
        snapshot.read_text(encoding="utf-8"), fallback_title=args.article)

    # ── journal 軌（BYO LaTeX、emit-only）：與兩條編譯軌分開，產 .tex、**不需字型**/不驗 fidelity ──
    if engine == "journal":
        template = _resolve_journal_template(args.journal, template_override)
        if template is None:
            sys.stderr.write(
                "docspec: journal template not found — use --journal {ieee,elsevier} or "
                "--template <dir> containing a template.tex.\n")
            return 1
        # slot 值：專案 export.slots config ＋ --slots 檔覆寫。
        extra_slots = dict(econf.get("slots") or {})
        if args.slots:
            sp = Path(args.slots)
            if not sp.is_file():
                sys.stderr.write(f"docspec: --slots file does not exist: {sp}\n")
                return 1
            try:
                data = yaml.safe_load(sp.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError as exc:
                sys.stderr.write(f"docspec: failed to parse --slots file ({sp}): {exc}\n")
                return 1
            if not isinstance(data, dict):
                sys.stderr.write(f"docspec: the --slots file's top level must be a mapping: {sp}\n")
                return 1
            extra_slots.update(data)
        # journal 軌產物落 per-journal 子夾（不與 latest PDF 混、雙 adapter 不互蓋）。
        journal_id = args.journal or (template_dir.name if template_dir is not None else "journal")
        out = layout.docs_journal_export(args.article, label, journal_id, "tex")
        from dspx.slots import SlotError
        try:
            _emit_journal(pandoc, template, title, body_md, extra_slots, out)
        except SlotError as exc:
            sys.stderr.write(f"docspec: invalid slot value — {exc} (no .tex produced)\n")
            return 1
        except subprocess.CalledProcessError as exc:
            sys.stderr.write(f"docspec: journal emit failed ({exc}).\n")
            return 1
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write(f"docspec: journal emit failed ({exc}).\n")
            return 1
        print(f"Emitted (journal track, not compiled): {out}")
        # 把 .tex 引用的圖 copy 到它旁邊（`docs/exports/assets/`），否則使用者拿 .tex 去 Overleaf
        # 會缺圖編不出（圖原本只住 corpus/<section>/assets/）。
        j_assets = _collect_referenced_assets(layout, args.article, body_md)
        if j_assets:
            adir = out.parent / "assets"
            adir.mkdir(parents=True, exist_ok=True)
            for ref, src in j_assets.items():
                if src.is_file():
                    shutil.copy2(src, adir / Path(ref).name)
            print(f"  Copied {len(j_assets)} referenced image asset(s) next to the .tex → {adir}")
        print("  Compile it with the journal's toolchain (Overleaf / its real .cls). docspec does not compile the journal track.")
        return 0

    # 字型（Typst 軌用）：--fonts 覆寫 > DOCSPEC_FONTS_SRC > data_dir/fonts（setup 落地）。
    # --fonts 缺夾/缺字型 → AssetError 清楚報錯、非零。
    try:
        fonts_src = paths.resolve_fonts_dir(args.fonts)
    except paths.AssetError as exc:
        sys.stderr.write(f"docspec: {exc}\n")
        return 1
    if fonts_src is None:
        sys.stderr.write(
            f"docspec: controlled fonts not found (data_dir/fonts) — PDF export needs them. {_SETUP_HINT}\n")
        return 1

    out = layout.docs_export(args.article, label, "pdf")
    # 被引用的圖片資產（兩條編譯軌共用）：copy 進 build dir 才渲得出嵌圖。
    assets = _collect_referenced_assets(layout, args.article, body_md)
    for w in _figure_health_warnings(body_md, assets):
        sys.stderr.write(f"docspec: ⚠ {w}\n")

    try:
        if engine == "typst":
            # ── Typst 軌（docspec-typst 自帶模板 + 受控 typst binary）──
            typst = paths.resolve_typst()
            if typst is None:
                sys.stderr.write(
                    "docspec: typst not found — the Typst track needs it. Install the controlled typst "
                    "(`docspec setup --with-typst`), or point DOCSPEC_TYPST at a typst binary.\n")
                return 1
            # BYO Typst 包（--template 或 config export.template 含 template.typ）＝合法替換、跳 hash 閘；
            # 否則用 bundled docspec-typst 包（走 hash 閘）。
            if template_dir is not None:
                if not (template_dir / "template.typ").is_file():
                    sys.stderr.write(
                        f"docspec: --template {template_dir} has no template.typ (Typst track).\n")
                    return 1
                typst_template = template_dir
                is_bundled = False
                notice = _eject_provenance_notice(template_dir)
                if notice is not None:
                    print(notice)
            else:
                typst_template = paths.bundled_typst_template_dir()
                is_bundled = True
                if typst_template is None or not (typst_template / "template.typ").is_file():
                    sys.stderr.write("docspec: bundled Typst template not found (assets/templates/docspec-typst/) — the install may be incomplete.\n")
                    return 1
            if _check_pack_integrity(typst_template, is_bundled=is_bundled, allow=args.allow) != 0:
                return 1
            from dspx.format_config import compile_typst_vars
            from dspx.config import detect_language, region_for
            # 文件語言＝從定稿內容偵測（非綁專案 config.language；agent 常忘了改）。
            # title＋body 一起判（標題已被抽出，但仍是文件文字）。config.language 為 fallback。
            _lang = detect_language(f"{title}\n{body_md}", config.get("language"))
            _region = region_for(_lang, config.get("language"))
            _build_pdf_typst(pandoc, typst, typst_template / "template.typ", fonts_src,
                             title, body_md, out,
                             highlight_style=highlight_style,
                             format_vars=compile_typst_vars(knobs), assets=assets,
                             lang=_lang, region=_region, profile=profile)
        else:
            sys.stderr.write(f"docspec: unknown engine '{engine}' — valid engines: typst, journal.\n")
            return 1
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(f"docspec: PDF conversion failed ({exc}) — skipped. {_INSTALL_HINT}\n")
        return 1
    except Exception as exc:  # noqa: BLE001 — 任何轉檔例外都降級、不 crash
        sys.stderr.write(f"docspec: PDF conversion failed ({exc}) — skipped. {_INSTALL_HINT}\n")
        return 1

    # runtime 渲染忠實度：產出 PDF 後抽文字、與源「定稿全文」位置化精確 diff。
    # 參照＝title＋body（標題行被移出正文注入 \title，但仍渲進 PDF，故要併回比對）。
    # CJK 淨缺失＝渲染吃字（嚴重）→ 非零；--ack＝已 proof 複判放行；--no-verify 全跳；
    # pdfplumber 缺＝soft-dep 跳。
    # typst 軌不渲染 raw-LaTeX 區塊（TikZ 等），故 fidelity 源端剔除它們、避免誤報缺字。
    verify_body = _strip_raw_latex(body_md) if engine == "typst" else body_md
    if not args.no_verify:
        if _verify_byte_lock(out, f"{title}\n{verify_body}", args.article, ack=args.ack) != 0:
            return 1

    # 預設只留 latest：成功 export+verify 後清同篇舊版 PDF（`--keep` 保留；`--latest` 預覽不清，
    # 預覽不該抹掉已發行匯出；失敗已在上方 early-return、到不了這裡）。
    if not args.keep and not args.latest:
        pruned = _prune_old_pdfs(layout, args.article, out)
        if pruned:
            print(f"  Pruned {len(pruned)} older PDF export(s) (use --keep to retain): "
                  f"{', '.join(p.name for p in pruned)}")

    print(f"Exported: {out}")
    return 0
