"""docspec get <section> <category> — 讀取 corpus 真相的引擎讀出面（配對 put 的寫入門）。

把某節某分類（concept | decisions | material）的內容吐到 stdout 或 `--out FILE`，供 agent 編輯後
再 `docspec put` 寫回。缺檔＝回一份**依 schema 的空骨架**（agent 從骨架填起，取代盲寫）。

get/put 是「全走引擎」的最小讀寫對：agent 改文章細節走指令、引擎驗證後才收，而不是手改散檔。
本 change 不動儲存拓撲（仍讀現行散檔）、不改任何指令名——只補「讀出＋（put 的）驗證寫入」這道門。
"""

from __future__ import annotations

import argparse
import sys

from dspx import change as chg
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
    from dspx.schema import yaml_skeleton
    art = schema.by_id(artifact_id)
    if art is None:
        return ""
    skel = yaml_skeleton(art)
    if skel:
        return skel + "\n"
    if art.template is not None and art.template.is_file():
        return art.template.read_text(encoding="utf-8")
    return ""


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

    filename, artifact_id = _CATEGORIES[args.category]
    if change is not None:
        sec_dir = chg.staging_target(change.dir, layout, layout.section_dir(section))
        # staging 未鏡像此檔（該節此分類尚無暫存副本）→ 回退正式檔，維持 union「補底」語義
        if not (sec_dir / filename).is_file():
            sec_dir = layout.section_dir(section)
    else:
        sec_dir = layout.section_dir(section)
    path = sec_dir / filename
    if path.is_file():
        content = path.read_text(encoding="utf-8")
    else:
        content = _skeleton(schema, artifact_id)

    origin = f" (change \"{change.id}\" staging)" if change is not None else ""
    if args.out:
        from pathlib import Path
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8", newline="\n")
        src = "file" if path.is_file() else "empty schema skeleton (no file yet)"
        print(f"get: {args.section} {args.category} -> {out_path} ({src}){origin}")
    else:
        sys.stdout.write(content)
        if content and not content.endswith("\n"):
            sys.stdout.write("\n")
    return 0
