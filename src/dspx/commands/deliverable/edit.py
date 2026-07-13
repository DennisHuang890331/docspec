"""docspec edit <target> (--punct | --term OLD NEW | --replace OLD NEW) [--dry-run]
   — 交付散文的機械精準修改原語（吸收 normalize + rename-term，並加節定位 literal 替換）。

三個互斥模式：
- `--punct`：把某篇散文的半形標點確定性轉全形（＝舊 `normalize`）。
- `--term OLD NEW`：整篇/全庫術語代換（＝舊 `rename-term`；prose span 限定、識別碼 byte-exact）。
- `--replace OLD NEW`：某「節」內的 literal 替換（新；只動該節散文 span、code/URL/marker 不碰）。

三者共用 spans 遮罩（構造性排除 code/URL/marker）＋帳本 prose 指紋自持（不產假 drift）。
語義忠實無法機械強制（源料摘要進散文本就會變形）——本原語只保證「不動 code/URL/marker、
不越節、回報命中數」；改得對不對＝人／factcheck 的事（見設計 fact-integrity）。
"""

from __future__ import annotations

import argparse
import sys

from dspx.commands._shared import BootstrapError, bootstrap, load_engine_schema, load_model

NAME = "edit"
HELP = ("mechanical prose edit primitive: --punct (normalize half->full-width), "
        "--term OLD NEW (project term substitution), --replace OLD NEW (one section's prose, "
        "literal) -- prose spans only, code/URLs/markers byte-exact")


def _run_replace(target: str, old: str, new: str, dry_run: bool) -> int:
    """`edit <section> --replace OLD NEW`：某節散文內 literal 替換（復用 rename-term 的散文
    span 遮罩＋識別碼守門，但限定該節、literal）。0 命中＝exit 1（指定要換的東西不在＝多半是錯）。"""
    from dspx.commands.deliverable._rename_term import _apply, _find_prose_hits
    from dspx.commands.deliverable._normalize import _update_ledger_prose

    if not old:
        sys.stderr.write("docspec: edit --replace: OLD must be non-empty\n")
        return 2
    if old == new:
        sys.stderr.write("docspec: edit --replace: OLD and NEW are identical (nothing to do)\n")
        return 2

    try:
        layout, config = bootstrap()
        load_engine_schema(config)
        leaves = load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code

    section = target.strip("/")
    if section not in {lf.section for lf in leaves}:
        sys.stderr.write(f"docspec: edit --replace: no such section \"{section}\"\n")
        return 1
    article = layout.article_of(section)
    latest = layout.docs_latest(article)
    if not latest.is_file():
        sys.stderr.write(
            f"docspec: deliverable {latest} does not exist -- run `docspec render {article}` first.\n")
        return 1

    text = latest.read_text(encoding="utf-8")
    hits = [h for h in _find_prose_hits(text, old) if h.section == section]
    if not hits:
        sys.stderr.write(
            f"docspec: edit --replace: \"{old}\" -- 0 prose hit(s) in section \"{section}\"; "
            "nothing changed.\n")
        return 1

    if dry_run:
        print(f"edit --replace --dry-run: \"{old}\" -> \"{new}\" in § {section} "
              f"-- {len(hits)} hit(s) (nothing written):")
        for h in hits:
            print(f"  …{h.before}[{old} -> {new}]{h.after}…")
        return 0

    new_text = _apply(text, hits, old, new)
    latest.write_text(new_text, encoding="utf-8", newline="\n")
    _update_ledger_prose(layout, article, {section}, new_text)
    print(f"edit --replace: \"{old}\" -> \"{new}\" in § {section} -- {len(hits)} hit(s) -> {latest}")
    print("  prose fingerprint updated in-place (no false drift); re-review the section for coherence.")
    return 0


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec edit", description=HELP)
    parser.add_argument("target", nargs="?", default=None,
                        help="article (for --punct/--term) or section path (for --replace)")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--punct", action="store_true",
                      help="normalize half->full-width punctuation in the article's prose (= old `normalize`)")
    mode.add_argument("--term", nargs=2, metavar=("OLD", "NEW"),
                      help="project-wide term substitution in prose spans (= old `rename-term`)")
    mode.add_argument("--replace", nargs=2, metavar=("OLD", "NEW"),
                      help="literal replace within ONE section's prose (target = section path)")
    parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                        help="preview without writing anything")
    args = parser.parse_args(argv)
    dry = ["--dry-run"] if args.dry_run else []

    if args.punct:
        if not args.target:
            sys.stderr.write("docspec: edit --punct needs an <article>\n")
            return 2
        from dspx.commands.deliverable import _normalize
        return _normalize.run([args.target] + dry)

    if args.term:
        old, new = args.term
        from dspx.commands.deliverable import _rename_term
        extra = ["--article", args.target] if args.target else []
        return _rename_term.run([old, new] + extra + dry)

    # --replace
    old, new = args.replace
    if not args.target:
        sys.stderr.write("docspec: edit --replace needs a <section>\n")
        return 2
    return _run_replace(args.target, old, new, args.dry_run)
