"""docspec new <section> — 純機械建末節（從 schema templates 渲染空骨架）。"""

from __future__ import annotations

import argparse
import hashlib
import sys

import yaml

from dspx.commands._shared import BootstrapError, bootstrap, load_engine_schema
from dspx.layout import Layout

NAME = "new"
HELP = "create section folder + develop.md (concept/decisions are produced when develop crystallizes)"

# develop 階段只有 develop.md；concept/decisions 由 develop agent 在「結晶」時產出、
# material 可選、history 由 retire 建。（不預建空 stub——否則 status 會把未結晶的空節誤報 ready。）
_SCAFFOLD = ("develop",)


def _stable_id(section: str) -> str:
    """與位置脫鉤的穩定 id（內容＝路徑指紋，存進檔後即定身份）。"""
    return "sec-" + hashlib.sha1(section.encode("utf-8")).hexdigest()[:8]


def _next_order(layout: Layout, section: str) -> int:
    """同層自動接龍（建議值；develop 階段 order 還沒存進檔，結晶時才寫進 concept）。
    數同層既有「章節資料夾」（含 develop.md 或 concept.yaml）＋1。"""
    parent = layout.section_dir(section).parent
    n = 0
    if parent.is_dir():
        for sib in parent.iterdir():
            if sib.is_dir() and ((sib / "develop.md").is_file() or (sib / "concept.yaml").is_file()):
                n += 1
    return n + 1


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec new", description=HELP)
    parser.add_argument("section", help="leaf section path (relative to corpus/, e.g. myarticle/intro)")
    parser.add_argument("--title", default=None, help="title (defaults to the last path segment)")
    args = parser.parse_args(argv)

    section = args.section.strip("/")
    if not section:
        sys.stderr.write("docspec: section path must not be empty\n")
        return 2

    try:
        layout, config = bootstrap()
        schema = load_engine_schema(config)
    except BootstrapError as exc:
        return exc.exit_code

    target = layout.section_dir(section)
    if (target / "develop.md").exists() or (target / "concept.yaml").exists():
        sys.stderr.write(f"docspec: section \"{section}\" already exists: {target} (not overwritten)\n")
        return 2

    title = args.title or section.rsplit("/", 1)[-1]
    fills = {
        "id": _stable_id(section),
        "title": title,
        "order": str(_next_order(layout, section)),
    }

    target.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    for artifact_id in _SCAFFOLD:
        artifact = schema.by_id(artifact_id)
        if artifact is None or artifact.template is None:
            continue
        body = artifact.template.read_text(encoding="utf-8")
        for key, val in fills.items():
            body = body.replace("{" + key + "}", val)
        (target / artifact.generates).write_text(body, encoding="utf-8")
        created.append(artifact.generates)

    print(f"created section \"{section}\" (develop stage): {target}")
    print(f"  id: {fills['id']}  order: {fills['order']}")
    for item in created:
        print(f"  + {item}")
    print("  next: think in develop.md; once clear, crystallize into concept.yaml + decisions.yaml.")
    print("  ('develop stage' = the workflow phase; concept.status is a separate enum: draft|stable|deprecated)")
    from dspx.schema import field_contract, required_field_names, yaml_skeleton
    for aid in ("concept", "decisions"):
        art = schema.by_id(aid)
        if not (art and art.schema):
            continue
        req = ", ".join(required_field_names(art.schema)) or "(none)"
        print(f"\n  after crystallizing, {aid} requires: {req}")
        if art.entries:
            print("    container: file top level MUST be { entries: [ … ] }")
        for f in field_contract(art.schema):
            req_s = "required" if f.get("required") else "optional"
            vals = f" = {' | '.join(map(str, f['values']))}" if f.get("values") else ""
            rel = f" → {f['relation']}" if f.get("relation") else ""
            print(f"      {f['name']:<14} {f['type']:<9} {req_s}{vals}{rel}")
            for sub in f.get("fields", []):
                sv = f" = {' | '.join(map(str, sub['values']))}" if sub.get("values") else ""
                sreq = "required" if sub.get("required") else "optional"
                print(f"        {sub['name']:<12} {sub['type']:<9} {sreq}{sv}")
        skel = yaml_skeleton(art)
        if skel:
            print("    skeleton:")
            for ln in skel.splitlines():
                print(f"      {ln}")
    return 0
