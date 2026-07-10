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

# ── 路徑段安全驗證（確定性黑名單；corpus 跨機同步，任何平台一律驗）──
# Windows 保留裝置名（不分大小寫；「保留名.副檔名」形式的目錄名同樣中招）
_WINDOWS_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)})
# Windows 非法字元＋反斜線（Windows pathlib 視 `\` 為分隔符，跨平台一致拒收）
_ILLEGAL_CHARS = frozenset('<>:"|?*\\')


def _segment_error(segment: str) -> str | None:
    """單一路徑段的確定性安全檢查；壞 → 英文原因（給 CLI 訊息），好 → None。"""
    if segment in ("", ".", ".."):
        return 'empty, "." and ".." segments are not allowed'
    if segment.startswith("_"):
        return ('"_"-prefixed folders are engine-invisible (like _archive/); '
                "sections created there are never seen by status/check/render")
    bad = sorted({c for c in segment if c in _ILLEGAL_CHARS or ord(c) < 32})
    if bad:
        return "illegal character(s) " + ", ".join(map(repr, bad)) + " (unportable path)"
    if segment != segment.strip() or segment.endswith("."):
        # 結尾點/空格 Windows 會靜默剝除→路徑不一致；頭尾空白也破 render 標記 round-trip
        return "leading/trailing whitespace or a trailing dot is not allowed"
    if segment.split(".", 1)[0].upper() in _WINDOWS_RESERVED:
        return (f'"{segment.split(".", 1)[0]}" is a Windows reserved device name '
                "(the folder would be unusable on Windows)")
    return None


def validate_section_path(section: str) -> str | None:
    """逐段驗證 section 路徑；回傳第一個壞段的錯誤訊息（指明段與原因），全部合法 → None。"""
    for segment in section.split("/"):
        reason = _segment_error(segment)
        if reason:
            return f'invalid path segment "{segment}": {reason}'
    return None


def _render_scaffold(schema, target, fills: dict[str, str]) -> list[str]:
    """從 schema template 渲染 _SCAFFOLD 骨架（填入 fills）；回傳建立的檔名清單。
    new（新建）與 --reopen（重建）共用同一模板來源與替換規則。"""
    target.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    for artifact_id in _SCAFFOLD:
        artifact = schema.by_id(artifact_id)
        if artifact is None or artifact.template is None:
            continue
        body = artifact.template.read_text(encoding="utf-8")
        for key, val in fills.items():
            body = body.replace("{" + key + "}", val)
        (target / artifact.generates).write_text(body, encoding="utf-8", newline="\n")
        created.append(artifact.generates)
    return created


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
    parser.add_argument(
        "section",
        help="leaf section path relative to corpus/, segments named in the deliverable "
             "language (en: guide/intro; zh: 指南/簡介); no chapter-number prefixes")
    parser.add_argument("--title", default=None, help="title (defaults to the last path segment)")
    parser.add_argument(
        "--reopen", action="store_true",
        help="rebuild develop.md for an already-crystallized section (has concept.yaml, no "
             "develop.md); id/title/order are read from concept.yaml, never recomputed")
    args = parser.parse_args(argv)

    section = args.section.strip("/")
    if not section:
        sys.stderr.write("docspec: section path must not be empty\n")
        return 2

    # 路徑安全驗證：mkdir 之前 fail-loud——命中任一黑名單即拒建、不建任何目錄
    problem = validate_section_path(section)
    if problem:
        sys.stderr.write(f'docspec: refusing to create "{section}": {problem}\n')
        return 2

    try:
        layout, config = bootstrap()
        schema = load_engine_schema(config)
    except BootstrapError as exc:
        return exc.exit_code

    target = layout.section_dir(section)
    has_concept = (target / "concept.yaml").exists()
    has_develop = (target / "develop.md").exists()

    # ── --reopen：為已結晶節（有 concept.yaml、無 develop.md）從 schema template 重建 develop.md ──
    # fills 的 id/title/order 一律從現有 concept.yaml 讀出（入帳身份／同層位置皆已定案，重算會脫鉤/漂移）。
    if args.reopen:
        if has_develop:
            sys.stderr.write(
                f"docspec: section \"{section}\" is already open (develop.md present): {target} "
                "(reopen has nothing to do; not overwritten)\n")
            return 2
        if not has_concept:
            sys.stderr.write(
                f"docspec: section \"{section}\" is not crystallized (no concept.yaml); "
                f"use `docspec new {section}` to scaffold a new section\n")
            return 2
        concept = yaml.safe_load((target / "concept.yaml").read_text(encoding="utf-8")) or {}
        fills = {
            "id": str(concept.get("id", _stable_id(section))),
            "title": str(concept.get("title") or section.rsplit("/", 1)[-1]),
            "order": str(concept.get("order", "")),
        }
        created = _render_scaffold(schema, target, fills)
        print(f"reopened section \"{section}\" (develop stage): {target}")
        print(f"  id: {fills['id']}  order: {fills['order']}  (read from concept.yaml, not recomputed)")
        for item in created:
            print(f"  + {item}")
        print("  next: think from where the section already stands (read its concept/decisions/history "
              "first); crystallize the new thinking, then docspec ready <section> to re-graduate.")
        return 0

    if has_develop or has_concept:
        if has_concept and not has_develop:
            # 已結晶但 develop.md 已被 ready 榨乾刪除 → 指路 --reopen（重開推理的正道）
            sys.stderr.write(
                f"docspec: section \"{section}\" is crystallized and has no develop.md: {target} "
                f"(not overwritten); to reopen it for more thinking run "
                f"`docspec new {section} --reopen`\n")
        else:
            sys.stderr.write(
                f"docspec: section \"{section}\" already exists: {target} (not overwritten)\n")
        return 2

    title = args.title or section.rsplit("/", 1)[-1]
    fills = {
        "id": _stable_id(section),
        "title": title,
        "order": str(_next_order(layout, section)),
    }

    created = _render_scaffold(schema, target, fills)

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
