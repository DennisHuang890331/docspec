"""docspec get <section> <category> — 讀取 corpus 真相的引擎讀出面（配對 put 的寫入門）。

把某節某分類（concept | decisions | material）的內容吐到 stdout 或 `--out FILE`，供 agent 編輯後
再 `docspec put` 寫回。缺檔＝回一份**依 schema 的空骨架**（agent 從骨架填起，取代盲寫）。

get/put 是「全走引擎」的最小讀寫對：agent 改文章細節走指令、引擎驗證後才收，而不是手改散檔。
本 change 不動儲存拓撲（仍讀現行散檔）、不改任何指令名——只補「讀出＋（put 的）驗證寫入」這道門。
"""

from __future__ import annotations

import argparse
import sys

from dspx.engine import change as chg
from dspx.commands._shared import BootstrapError, bootstrap, load_engine_schema

NAME = "get"
HELP = "read a section's concept/decisions/material to stdout or --out FILE (empty schema skeleton if absent)"

# category → (檔名, schema artifact id)
_CATEGORIES = {
    "concept": ("concept.yaml", "concept"),
    "decisions": ("decisions.yaml", "decisions"),
    "material": ("material.md", "material"),
}


def _skeleton(schema, artifact_id: str) -> str:
    """缺檔時回的空骨架：yaml 走 schema 導出的 `yaml_skeleton`；material（md）走其 template。"""
    from dspx.engine.schema import yaml_skeleton
    art = schema.by_id(artifact_id)
    if art is None:
        return ""
    skel = yaml_skeleton(art)
    if skel:
        return skel + "\n"
    if art.template is not None and art.template.is_file():
        return art.template.read_text(encoding="utf-8")
    return ""


def _get_store(layout, schema, args, section: str, change) -> int:
    """store 篇 get：從記錄（change staging 優先、正式 store 補底）吐某分類；缺＝schema 空骨架。"""
    import yaml

    from dspx.engine import store as _store
    _filename, artifact_id = _CATEGORIES[args.category]
    article = layout.article_of(section)
    rec = None
    origin = ""
    if change is not None:
        staging = chg._load_staging_article(change.dir, article)
        staged_rec = staging.record_by_path(section) if staging is not None else None
        if staged_rec is not None and staged_rec.kind == "leaf":
            rec = staged_rec
            origin = f" (change \"{change.id}\" staging)"
    if rec is None and _store.article_has_store(layout, article):
        art = _store.load_article(_store.store_path(layout, article), verify=True)
        rec = art.record_by_path(section)

    have = False
    if rec is not None and rec.kind == "leaf":
        if args.category == "concept" and rec.concept:
            content = yaml.safe_dump(rec.concept, allow_unicode=True, sort_keys=False)
            have = True
        elif args.category == "decisions" and rec.decisions:
            content = yaml.safe_dump({"entries": rec.decisions}, allow_unicode=True, sort_keys=False)
            have = True
        elif args.category == "material" and rec.material is not None:
            content = rec.material
            have = True
        else:
            content = _skeleton(schema, artifact_id)
    else:
        content = _skeleton(schema, artifact_id)

    if args.out:
        from pathlib import Path
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8", newline="\n")
        src = "store record" if have else "empty schema skeleton (no content yet)"
        print(f"get: {args.section} {args.category} -> {out_path} ({src}){origin}")
    else:
        sys.stdout.write(content)
        if content and not content.endswith("\n"):
            sys.stdout.write("\n")
    return 0


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec get", description=HELP)
    parser.add_argument("section", help="leaf section path (relative to corpus/)")
    parser.add_argument("category", choices=sorted(_CATEGORIES),
                        help="which artifact to read: concept | decisions | material")
    parser.add_argument("--out", default=None, help="write to this FILE instead of stdout")
    parser.add_argument("--official", action="store_true",
                        help="read the frozen official baseline even if an active change stages "
                             "this section (default: the staging version — what you edit is what you see)")
    parser.add_argument("--change", default=None, metavar="ID",
                        help="read this active change's staging (required to disambiguate when >1 "
                             "active change targets the section)")
    args = parser.parse_args(argv)

    try:
        layout, config = bootstrap()
        schema = load_engine_schema(config)
    except BootstrapError as exc:
        return exc.exit_code

    section = args.section.strip("/")

    # ── change-aware 讀（★P0 union 語義）：staged target 預設吐 staging；--official 看凍結基準 ──
    change = None
    if not args.official:
        try:
            change = chg.routing_change_for(layout, section, explicit_id=args.change)
        except chg.RoutingAmbiguous as amb:
            sys.stderr.write(
                f"docspec: section \"{section}\" is staged by {len(amb.candidates)} active changes "
                f"({', '.join(c.id for c in amb.candidates)}) — get refuses to guess which staging. "
                "Re-run with --change <id>, or --official for the frozen baseline.\n")
            return 2
        except chg.ChangeError as exc:
            sys.stderr.write(f"docspec: {exc}\n")
            return 2

    # ★store-only：由 store 記錄吐內容（staging 優先、正式補底），缺＝schema 空骨架。
    return _get_store(layout, schema, args, section, change)
