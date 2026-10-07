"""artispec get <section> <category> — 讀取 corpus 真相的引擎讀出面（配對 put 的寫入門）。

把某節某分類（concept | decisions | material）的內容吐到 stdout 或 `--out FILE`，供 agent 編輯後
再 `artispec put` 寫回。缺檔＝回一份**依 schema 的空骨架**（agent 從骨架填起，取代盲寫）。

get/put 是「全走引擎」的最小讀寫對：agent 改文章細節走指令、引擎驗證後才收，而不是手改真相。
讀寫皆落在一篇一檔 store（`corpus/<article>.yaml`，引擎擁有＋封條）——get 從 store 記錄取出、
put 驗證後寫回；agent 不手改 store 檔。
"""

from __future__ import annotations

import argparse
import sys

from dspx.commands._shared import BootstrapError, bootstrap, load_engine_schema
from dspx.engine.document_context import add_context_arguments, load_context
from dspx.engine.model import ModelError

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


def _get_store(layout, schema, args, section: str, context) -> int:
    """store 篇 get：從記錄（change staging 優先、正式 store 補底）吐某分類；缺＝schema 空骨架。"""
    import yaml

    _filename, artifact_id = _CATEGORIES[args.category]
    rec = context.record(section)
    source = context.record_source(section)
    context.print_context(stream=sys.stderr)
    sys.stderr.write(f"source: {source['kind']} {source['path'] or '(no record; schema skeleton)'}\n")
    origin = f" ({source['kind']})"

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
    parser = argparse.ArgumentParser(prog="artispec get", description=HELP)
    parser.add_argument("section", help="leaf section path (relative to corpus/)")
    parser.add_argument("category", choices=sorted(_CATEGORIES),
                        help="which artifact to read: concept | decisions | material")
    parser.add_argument("--out", default=None, help="write to this FILE instead of stdout")
    add_context_arguments(parser)
    args = parser.parse_args(argv)

    try:
        layout, config = bootstrap()
        context = load_context(layout, config, args.change)
        layout = context.layout
        schema = load_engine_schema(context.config)
    except BootstrapError as exc:
        return exc.exit_code
    except (ModelError, OSError, ValueError) as exc:
        sys.stderr.write(f"artispec get: {exc}\n")
        return 1

    section = args.section.strip("/")

    from dspx.commands.corpus.put import validate_section_path
    if reason := validate_section_path(section):
        sys.stderr.write(f"artispec get: {reason}\n")
        return 2
    if context.change is not None:
        try:
            context.require_section(section, allow_pending=True)
        except ModelError as exc:
            sys.stderr.write(f"artispec get: {exc}\n")
            return 1

    # ★store-only：由 store 記錄吐內容（staging 優先、正式補底），缺＝schema 空骨架。
    return _get_store(layout, schema, args, section, context)
