"""docspec mv — 引擎交易原語：改名/搬移 + 同步重寫 path-keyed 引用（原子、失敗零半套）。

兩種模式（由引數形態自動判定）：
  1. **節模式** `docspec mv <old-section> <new-section>`：改名/搬移一個 leaf 或 group 資料夾，
     確定性重寫①`docs/<article>_latest.md` 受影響的 section/group marker 行（不重寫則下次 render
     把舊路徑散文當無主丟棄＝毀稿）②森林級與 per-article `audit.yaml`/`roadmap.yaml` 的路徑型
     targets/sot-owner/target；自跑 `check` 驗引用完整；任一步失敗即回滾、零半套。
     v1 範圍限 leaf/group、同一 article：article root（無 `/`）與跨 article 明確排除
     （root 牽動交付檔名/publish 凍結/journal，屬後續擴充）。身份（concept.id）不動、
     指紋帳本不手改——收尾提示 `render --rebaseline` 以新 key 重生。
     **store 篇**（`corpus/<article>.yaml`）走結構化記錄搬移：改記錄的 path 前綴（不搬資料夾）、
     revision+1、canonical 原子重寫，其餘（引用重寫、check 自驗、回滾）與 tree 版一致。
  2. **資產模式** `docspec mv docs/assets/old.png new.png`：改圖檔名＋以 basename 比對重寫所有
     `docs/*_latest.md` 與 corpus `material.md` 的 `![](…old.png)` 引用；同樣原子/回滾。
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import yaml

from dspx.commands._shared import BootstrapError, bootstrap, load_engine_schema
from dspx.commands.corpus.new import validate_section_path

NAME = "mv"
HELP = ("engine transaction: rename/relocate a leaf/group folder (or a docs/assets image) and "
        "deterministically rewrite every path-keyed reference; self-verifies with check, aborts "
        "with zero partial effect on failure")

# 資產模式判定：任一引數帶圖檔副檔名（含 drawio 源）＝資產改名，否則走節模式。
_IMAGE_EXTS = frozenset({
    ".png", ".svg", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".drawio"})

_AUDIT_HEADER = ("# audit findings (maintained by the docspec audit command; do not edit by "
                 "hand). append-only adversarial log.\n")


class _MvAbort(Exception):
    """交易中止（已備妥回滾）。"""


# ── path 重映射（舊→新，subtree 前綴；#anchor 保留）──────────────────────────

def _remap_section(path: str, old: str, new: str) -> str | None:
    """節路徑重映射：== old → new；old/ 前綴 → new/ 前綴；否則 None（不受影響）。"""
    if path == old:
        return new
    if path.startswith(old + "/"):
        return new + path[len(old):]
    return None


def _remap_target(target: object, old: str, new: str) -> str | None:
    """audit/roadmap target 重映射：只動 `#` 前的節路徑部分，anchor 原樣保留。"""
    s = str(target)
    sec, sep, anchor = s.partition("#")
    remapped = _remap_section(sec, old, new)
    if remapped is None:
        return None
    return remapped + sep + anchor


# ── 檔案級重寫 ────────────────────────────────────────────────────────────

def _rewrite_latest_markers(latest: Path, old: str, new: str) -> list[str]:
    """重寫 `_latest.md` 受影響的 section/group marker 行（只動 marker 行、散文 body 逐字保留）。"""
    from dspx.render import GROUP_MARKER_RE, MARKER_RE, group_marker, section_marker

    if not latest.is_file():
        return []
    text = latest.read_text(encoding="utf-8")
    out: list[str] = []
    changes: list[str] = []
    for line in text.split("\n"):
        m = MARKER_RE.match(line)
        if m:
            remapped = _remap_section(m.group(1), old, new)
            if remapped is not None:
                out.append(section_marker(remapped))
                changes.append(f"{latest.name} section marker: {m.group(1)} -> {remapped}")
                continue
        gm = GROUP_MARKER_RE.match(line)
        if gm:
            remapped = _remap_section(gm.group(1), old, new)
            if remapped is not None:
                out.append(group_marker(remapped))
                changes.append(f"{latest.name} group marker: {gm.group(1)} -> {remapped}")
                continue
        out.append(line)
    if changes:
        latest.write_text("\n".join(out), encoding="utf-8", newline="\n")
    return changes


def _dump_with_header(path: Path, data: dict, original_text: str) -> None:
    """把 data 寫回 path，保留原檔開頭的註解列（audit/roadmap 的 machine-maintained header）。"""
    header = []
    for line in original_text.splitlines(keepends=True):
        if line.lstrip().startswith("#"):
            header.append(line)
        else:
            break
    body = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=10000)
    path.write_text("".join(header) + body, encoding="utf-8", newline="\n")


def _rewrite_audit_file(path: Path, old: str, new: str) -> list[str]:
    """重寫某 audit.yaml 內 findings 的路徑型 targets/sot-owner；壞檔略過（check 會抓）。"""
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return []
    if not isinstance(data, dict) or not isinstance(data.get("findings"), list):
        return []
    changes: list[str] = []
    for f in data["findings"]:
        if not isinstance(f, dict):
            continue
        fid = f.get("id")
        targets = f.get("targets")
        if isinstance(targets, list):
            for i, t in enumerate(targets):
                r = _remap_target(t, old, new)
                if r is not None:
                    changes.append(f"{path.name} finding {fid} target: {t} -> {r}")
                    targets[i] = r
        so = f.get("sot-owner")
        if so is not None:
            r = _remap_target(so, old, new)
            if r is not None:
                changes.append(f"{path.name} finding {fid} sot-owner: {so} -> {r}")
                f["sot-owner"] = r
    if changes:
        _dump_with_header(path, data, text)
    return changes


def _rewrite_roadmap_file(path: Path, old: str, new: str) -> list[str]:
    """重寫某 roadmap.yaml 內 entries 的路徑型 target；壞檔略過（check 會抓）。"""
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return []
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        return []
    changes: list[str] = []
    for e in data["entries"]:
        if not isinstance(e, dict):
            continue
        r = _remap_target(e.get("target"), old, new)
        if r is not None:
            changes.append(f"{path.name} roadmap {e.get('id')} target: {e.get('target')} -> {r}")
            e["target"] = r
    if changes:
        _dump_with_header(path, data, text)
    return changes


# ── 交易骨架（快照 → 變更 → check；失敗回滾）──────────────────────────────

def _snapshot(paths: list[Path]) -> dict[Path, bytes | None]:
    """快照每個檔的原始 bytes（不存在＝None），供回滾。"""
    return {p: (p.read_bytes() if p.is_file() else None) for p in paths}


def _restore(snapshots: dict[Path, bytes | None]) -> None:
    for p, original in snapshots.items():
        if original is None:
            if p.is_file():
                p.unlink()
        else:
            p.write_bytes(original)


def _ensure_parent(dst: Path) -> list[Path]:
    """建 dst 的缺失父層，回傳實際新建的目錄（供回滾清除）。"""
    missing: list[Path] = []
    p = dst.parent
    while not p.exists():
        missing.append(p)
        p = p.parent
    created: list[Path] = []
    for d in reversed(missing):
        d.mkdir()
        created.append(d)
    return created


def _remove_created_dirs(created: list[Path]) -> None:
    for d in reversed(created):
        try:
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
        except OSError:
            pass


def _check_result(layout, schema):
    """載入現行模型跑 check，回傳 CheckResult。"""
    from dspx.check import run_check
    from dspx.model import load_project
    leaves = load_project(layout)
    return run_check(leaves, schema, layout)


# ── 節模式 ────────────────────────────────────────────────────────────────

def _is_section_folder(layout, src: Path) -> bool:
    """src 是 leaf（含 concept.yaml/develop.md）或 group（子樹含節）＝可搬移的節資料夾。"""
    if not src.is_dir():
        return False
    if (src / "concept.yaml").is_file() or (src / "develop.md").is_file():
        return True
    for name in ("concept.yaml", "develop.md"):
        for f in src.rglob(name):
            if not layout.is_archived_path(f.parent):
                return True
    return False


def _run_section_mode(layout, schema, old_arg: str, new_arg: str) -> int:
    old = old_arg.strip("/")
    new = new_arg.strip("/")
    if not old or not new:
        sys.stderr.write("docspec: both <old-section> and <new-section> must be non-empty\n")
        return 2
    if old == new:
        sys.stderr.write("docspec: source and destination are identical (nothing to move)\n")
        return 2

    # ── backend 路由：store 篇改的是記錄的 path 前綴（不搬資料夾），走結構化記錄搬移。 ──
    from dspx import store as _store
    if (_store.article_has_store(layout, layout.article_of(old))
            or _store.article_has_store(layout, layout.article_of(new))):
        return _run_store_section_mode(layout, schema, old, new)

    src = layout.section_dir(old)
    dst = layout.section_dir(new)

    if layout.is_archived_path(src):
        sys.stderr.write(f"docspec: \"{old}\" is in the archive; mv operates on the live tree only.\n")
        return 1
    if not _is_section_folder(layout, src):
        sys.stderr.write(
            f"docspec: section \"{old}\" not found (needs a leaf with concept.yaml/develop.md or a "
            "group folder containing sections). Use docspec status for paths.\n")
        return 1

    # v1 範圍：article root（無 `/`）不搬——交付檔名/publish 凍結/verdicts journal 綁 article 名。
    if "/" not in old:
        sys.stderr.write(
            f"docspec: refusing to move article root \"{old}\" — deliverable filename, publish "
            "freeze ledger and verdicts journal are keyed by the article name; root moves are a "
            "later mv extension (designed together with freeze linkage). v1 scope is leaf/group.\n")
        return 1
    if "/" not in new:
        sys.stderr.write(
            f"docspec: destination \"{new}\" would be an article root (no parent segment); v1 mv "
            "cannot promote a section to an article root.\n")
        return 1
    # v1 範圍：同一 article（跨 article 牽動 audit/roadmap/ledger 的 article 歸屬，屬後續擴充）。
    if old.split("/", 1)[0] != new.split("/", 1)[0]:
        sys.stderr.write(
            f"docspec: refusing cross-article move (\"{old.split('/', 1)[0]}\" -> "
            f"\"{new.split('/', 1)[0]}\") — v1 mv is same-article only (cross-article changes the "
            "deliverable/ledger/audit article ownership; that is a later extension).\n")
        return 1

    problem = validate_section_path(new)
    if problem:
        sys.stderr.write(f"docspec: refusing to move to \"{new}\": {problem}\n")
        return 2
    if dst.exists():
        sys.stderr.write(
            f"docspec: destination \"{new}\" already exists ({dst}); resolve it before moving.\n")
        return 1

    # mv 以 check 自驗——若專案已非綠，無法分辨「本次搬移」是否破壞引用；先要求綠。
    pre = _check_result(layout, schema)
    if not pre.ok:
        sys.stderr.write(
            "docspec: refusing to mv — docspec check is not green; mv self-verifies with check and "
            "cannot tell a pre-existing error from one it caused. Fix these first:\n")
        for err in pre.errors[:20]:
            sys.stderr.write(f"    ✗ {err}\n")
        return 1

    article = old.split("/", 1)[0]
    touched = [
        layout.docs_latest(article),
        forest_audit_path(layout), doc_audit_path(layout, article),
        forest_roadmap_path(layout), doc_roadmap_path(layout, article),
    ]
    snapshots = _snapshot(touched)
    created_dirs = _ensure_parent(dst)
    moved = False
    report: list[str] = []
    try:
        shutil.move(str(src), str(dst))
        moved = True
        report += _rewrite_latest_markers(layout.docs_latest(article), old, new)
        report += _rewrite_audit_file(forest_audit_path(layout), old, new)
        report += _rewrite_audit_file(doc_audit_path(layout, article), old, new)
        report += _rewrite_roadmap_file(forest_roadmap_path(layout), old, new)
        report += _rewrite_roadmap_file(doc_roadmap_path(layout, article), old, new)
        result = _check_result(layout, schema)
        if not result.ok:
            raise _MvAbort("check went red after the move:\n    "
                           + "\n    ".join(f"✗ {e}" for e in result.errors[:20]))
    except (_MvAbort, Exception) as exc:  # noqa: BLE001 — 任何失敗都要回滾
        if moved and dst.exists() and not src.exists():
            shutil.move(str(dst), str(src))
        _restore(snapshots)
        _remove_created_dirs(created_dirs)
        sys.stderr.write(f"docspec: mv aborted (no partial effect): {exc}\n")
        return 1

    print(f"mv: \"{old}\" -> \"{new}\" (folder moved; references rewritten; check green)")
    if report:
        for c in report:
            print(f"  {c}")
    else:
        print("  (no path-keyed references pointed at the moved subtree)")
    print(f"  reminder: run `docspec render {article} --rebaseline` — the fingerprint ledger is "
          "keyed by section path and is NOT hand-edited; rebaseline regenerates it for the new "
          "paths (prose is preserved). Identity (concept.id) is unchanged.")
    return 0


# ── 節模式（store backend）────────────────────────────────────────────────

def _run_store_section_mode(layout, schema, old: str, new: str) -> int:
    """store 篇改名/搬移：改記錄的 path 前綴（不搬資料夾）＋同步重寫 docs marker/audit/roadmap
    路徑引用；revision+1、canonical dump、原子寫；自跑 check 驗引用完整，失敗回滾零半套。"""
    from dspx import store as _store

    old_art, new_art = layout.article_of(old), layout.article_of(new)
    # v1 範圍：article root 不搬、跨 article 不搬（同 tree 版；store 天生 per-article）。
    if "/" not in old:
        sys.stderr.write(
            f"docspec: refusing to move article root \"{old}\" — the store file is keyed by the "
            "article name (corpus/<article>.yaml); root moves are a later mv extension. v1 scope "
            "is leaf/group.\n")
        return 1
    if "/" not in new:
        sys.stderr.write(
            f"docspec: destination \"{new}\" would be an article root (no parent segment); v1 mv "
            "cannot promote a section to an article root.\n")
        return 1
    if old_art != new_art:
        sys.stderr.write(
            f"docspec: refusing cross-article move (\"{old_art}\" -> \"{new_art}\") — v1 mv is "
            "same-article only.\n")
        return 1

    problem = validate_section_path(new)
    if problem:
        sys.stderr.write(f"docspec: refusing to move to \"{new}\": {problem}\n")
        return 2

    store_file = _store.store_path(layout, old_art)
    art = _store.load_article(store_file, verify=True)
    subtree = [r for r in art.records if r.path == old or r.path.startswith(old + "/")]
    if not subtree:
        sys.stderr.write(
            f"docspec: section \"{old}\" not found in store corpus/{old_art}.yaml. "
            "Use docspec status for paths.\n")
        return 1
    if any(r.path == new or r.path.startswith(new + "/") for r in art.records):
        sys.stderr.write(
            f"docspec: destination \"{new}\" already exists in the store; resolve it before moving.\n")
        return 1

    # mv 以 check 自驗——先要求綠（無法分辨既有錯與本次搬移造成的錯）。
    pre = _check_result(layout, schema)
    if not pre.ok:
        sys.stderr.write(
            "docspec: refusing to mv — docspec check is not green; mv self-verifies with check and "
            "cannot tell a pre-existing error from one it caused. Fix these first:\n")
        for err in pre.errors[:20]:
            sys.stderr.write(f"    ✗ {err}\n")
        return 1

    touched = [
        layout.docs_latest(old_art),
        forest_audit_path(layout), doc_audit_path(layout, old_art),
        forest_roadmap_path(layout), doc_roadmap_path(layout, old_art),
    ]
    snapshots = _snapshot([store_file] + touched)
    report: list[str] = []
    try:
        for r in subtree:
            remapped = _remap_section(r.path, old, new)
            if remapped is not None:
                report.append(f"corpus/{old_art}.yaml record path: {r.path} -> {remapped}")
                r.path = remapped
        art.revision += 1
        _store.save_article(layout, art, schema)
        report += _rewrite_latest_markers(layout.docs_latest(old_art), old, new)
        report += _rewrite_audit_file(forest_audit_path(layout), old, new)
        report += _rewrite_audit_file(doc_audit_path(layout, old_art), old, new)
        report += _rewrite_roadmap_file(forest_roadmap_path(layout), old, new)
        report += _rewrite_roadmap_file(doc_roadmap_path(layout, old_art), old, new)
        result = _check_result(layout, schema)
        if not result.ok:
            raise _MvAbort("check went red after the move:\n    "
                           + "\n    ".join(f"✗ {e}" for e in result.errors[:20]))
    except (_MvAbort, Exception) as exc:  # noqa: BLE001 — 任何失敗都要回滾
        _restore(snapshots)
        sys.stderr.write(f"docspec: mv aborted (no partial effect): {exc}\n")
        return 1

    print(f"mv: \"{old}\" -> \"{new}\" (store records repointed; references rewritten; check green)")
    for c in report:
        print(f"  {c}")
    print(f"  reminder: run `docspec render {old_art} --rebaseline` — the fingerprint ledger is "
          "keyed by section path and is NOT hand-edited; rebaseline regenerates it for the new "
          "paths (prose is preserved). Identity (concept.id) is unchanged.")
    return 0


# ── 資產模式 ──────────────────────────────────────────────────────────────

def _is_asset_arg(arg: str) -> bool:
    return Path(arg).suffix.lower() in _IMAGE_EXTS


def _resolve_asset(layout, arg: str) -> Path | None:
    p = Path(arg)
    candidates: list[Path] = []
    if p.is_absolute():
        candidates.append(p)
    else:
        candidates.append(layout.project_root / p)
        candidates.append(Path.cwd() / p)
        candidates.append(layout.docs_assets_dir() / p.name)
    for c in candidates:
        if c.is_file():
            return c
    return None


def _rewrite_image_refs_file(path: Path, old_base: str, new_base: str) -> list[str]:
    """以 basename 比對重寫某檔的 `![](…old_base)` 圖引用（單一權威 IMAGE_REF_RE）。"""
    from dspx.render import IMAGE_REF_RE

    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    changes: list[str] = []

    def repl(m):
        ref = m.group(1)
        if Path(ref).name != old_base:
            return m.group(0)
        newref = ref[: len(ref) - len(old_base)] + new_base
        full = m.group(0)
        idx = full.rfind(ref)
        changes.append((ref, newref))
        return full[:idx] + newref + full[idx + len(ref):]

    new_text = IMAGE_REF_RE.sub(repl, text)
    if changes:
        path.write_text(new_text, encoding="utf-8", newline="\n")
        return [f"{path.name}: {a} -> {b}" for a, b in changes]
    return []


def _run_asset_mode(layout, schema, old_arg: str, new_arg: str) -> int:
    old_file = _resolve_asset(layout, old_arg)
    if old_file is None:
        sys.stderr.write(
            f"docspec: asset \"{old_arg}\" not found (looked under docs/assets/ and the given "
            "path). Nothing moved.\n")
        return 1
    old_base = old_file.name

    new_p = Path(new_arg)
    if new_p.is_absolute():
        dst = new_p
    elif "/" in new_arg or "\\" in new_arg:
        dst = layout.project_root / new_p
    else:
        dst = old_file.parent / new_arg
    new_base = dst.name
    if dst.exists():
        sys.stderr.write(f"docspec: destination asset already exists: {dst}. Resolve it first.\n")
        return 1

    pre = _check_result(layout, schema)
    if not pre.ok:
        sys.stderr.write(
            "docspec: refusing to mv — docspec check is not green; fix structural errors first "
            "(mv self-verifies with check).\n")
        for err in pre.errors[:20]:
            sys.stderr.write(f"    ✗ {err}\n")
        return 1

    # 掃描面：所有 docs `_latest.md` ＋ corpus 活樹的 material.md（散文圖引用）。
    ref_files: list[Path] = []
    for art in layout.articles():
        latest = layout.docs_latest(art)
        if latest.is_file():
            ref_files.append(latest)
    if layout.corpus_dir.is_dir():
        for mat in sorted(layout.corpus_dir.rglob("material.md")):
            if not layout.is_archived_path(mat.parent):
                ref_files.append(mat)

    snapshots = _snapshot(ref_files)
    created_dirs = _ensure_parent(dst)
    moved = False
    report: list[str] = []
    touched_articles: set[str] = set()
    try:
        shutil.move(str(old_file), str(dst))
        moved = True
        for p in ref_files:
            file_changes = _rewrite_image_refs_file(p, old_base, new_base)
            if file_changes and p.name.endswith("_latest.md"):
                # per-article layout: docs/<article>/_latest.md ；flat: docs/<article>_latest.md
                touched_articles.add(_article_of_latest(layout, p))
            report += file_changes
        result = _check_result(layout, schema)
        if not result.ok:
            raise _MvAbort("check went red after the asset rename:\n    "
                           + "\n    ".join(f"✗ {e}" for e in result.errors[:20]))
    except (_MvAbort, Exception) as exc:  # noqa: BLE001 — 任何失敗都要回滾
        if moved and dst.exists() and not old_file.exists():
            shutil.move(str(dst), str(old_file))
        _restore(snapshots)
        _remove_created_dirs(created_dirs)
        sys.stderr.write(f"docspec: mv aborted (no partial effect): {exc}\n")
        return 1

    try:
        rel_old = old_file.relative_to(layout.project_root)
        rel_new = dst.relative_to(layout.project_root)
    except ValueError:
        rel_old, rel_new = old_file, dst
    print(f"mv (asset): {rel_old} -> {rel_new} (renamed; refs rewritten; check green)")
    if report:
        for c in report:
            print(f"  {c}")
    else:
        print("  (no image references pointed at this asset)")
    arts = sorted(a for a in touched_articles if a)
    if arts:
        print(f"  reminder: image refs changed prose in {', '.join(arts)}; run "
              f"`docspec render <article> --rebaseline` so the ledger prose fingerprints follow.")
    return 0


def _article_of_latest(layout, latest: Path) -> str:
    """從 `_latest.md` 路徑反推 article 名（flat: <article>_latest.md；per-article: <article>/_latest.md）。"""
    if latest.name == "_latest.md":
        return latest.parent.name
    if latest.name.endswith("_latest.md"):
        return latest.name[: -len("_latest.md")]
    return ""


# ── audit/roadmap 路徑 helper（延後匯入避免循環）──────────────────────────

def forest_audit_path(layout):
    from dspx.audit import forest_audit_path as _f
    return _f(layout)


def doc_audit_path(layout, article: str):
    from dspx.audit import doc_audit_path as _f
    return _f(layout, article)


def forest_roadmap_path(layout):
    from dspx.roadmap import forest_roadmap_path as _f
    return _f(layout)


def doc_roadmap_path(layout, article: str):
    from dspx.roadmap import doc_roadmap_path as _f
    return _f(layout, article)


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec mv", description=HELP)
    parser.add_argument(
        "old",
        help="old section path (relative to corpus/) OR an image asset path (docs/assets/x.png)")
    parser.add_argument(
        "new",
        help="new section path OR the new asset filename/path")
    args = parser.parse_args(argv)

    try:
        layout, config = bootstrap()
        schema = load_engine_schema(config)
    except BootstrapError as exc:
        return exc.exit_code

    if _is_asset_arg(args.old) or _is_asset_arg(args.new):
        return _run_asset_mode(layout, schema, args.old, args.new)
    return _run_section_mode(layout, schema, args.old, args.new)
