"""docspec store — 一篇一檔儲存的維修/遷移門（dump / load / fsck / migrate / tidy）。

「全走引擎」的鎖入風險（設計 §4.4）由三層維修門緩解：
- `store dump <article>`  ：store → 散檔唯讀匯出（除錯/災難救援）。
- `store load <article> <DIR>`：散檔 → store，過全驗證才收。
- `store fsck [<article>] [--accept]`：驗 integrity 封條；--accept 顯式吸收外部變更（重封、留痕）。
- `store migrate <article>|--all`：tree → store 一次性，**平價閘**（雙 backend 深等值＋
  anc/deps/norm 三軸值逐節相等才收，否則回滾刪 store 檔）。dump + 刪 store 檔＝回散檔世界（可逆）。
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import yaml

from dspx.engine import store as st
from dspx.commands._shared import BootstrapError, bootstrap, load_engine_schema
from dspx.engine.layout import Layout
from dspx.engine.model import (ancestor_brief_fingerprint, ancestor_normative_fingerprint,
                        deps_fingerprint, decision_index, leaf_from_dir, load_leaf)

NAME = "store"
HELP = "one-file-per-article store maintenance: dump / load / fsck / migrate (parity-gated) / tidy"

# migrate/dump 認得的每節檔（其餘檔一律 fail-loud，永不靜默刪資料）。
_FOLD_FILES = ("concept.yaml", "decisions.yaml", "material.md", "history.yaml", "group.yaml")
_MOVE_TO_WORK = ("develop.md", "history.md")
# doc-root 治理檔（散檔世界的 audit/roadmap）：migrate 收編成 sibling 密封檔、非拒絕。
_GOVERNANCE_FILES = ("audit.yaml", "roadmap.yaml", "roadmap-archive.yaml")


# ── article leaf-set 建構（migrate 平價閘用）────────────────────────────

def _tree_leaves_of(layout: Layout, article: str):
    """散檔該篇的 leaves（依 section 排序）。"""
    out = []
    for d in layout.leaf_dirs():
        sec = layout.section_id(d)
        if layout.article_of(sec) == article:
            out.append(load_leaf(layout, d))
    return out


def _fingerprints(leaves) -> dict[str, tuple]:
    """每節 (anc, deps, norm) 三軸值（平價閘只比這三軸——own 軸 v5 蓄意會變）。"""
    by_section = {lf.section: lf for lf in leaves}
    concept_by_id = {lf.concept["id"]: lf for lf in leaves
                     if lf.concept and lf.concept.get("id")}
    dindex = decision_index(leaves)
    out: dict[str, tuple] = {}
    for lf in leaves:
        out[lf.section] = (
            ancestor_brief_fingerprint(lf.section, by_section, concept_by_id),
            deps_fingerprint(lf, dindex),
            ancestor_normative_fingerprint(lf.section, by_section, concept_by_id),
        )
    return out


def _leaf_truth(lf) -> tuple:
    """平價閘的深等值鍵：概念/決策/歷史/材料（store 承載的真相；has_* 檔存在旗標不入比對）。"""
    return (lf.concept, lf.decisions, lf.history, lf.material)


def _parity_check(layout: Layout, article: str, schema) -> tuple[st.Article, list[str]]:
    """建 store Article、對散檔跑平價閘。回 (article_obj, mismatches)；mismatches 空＝過關。

    ★store-only：散檔讀取集中在 `st.load_tree_leaves`（遷移橋），其它篇已是 store（load_project）。"""
    from dspx.engine.model import load_project
    tree_x = st.load_tree_leaves(layout, article)   # 該篇散檔（遷移橋唯讀路徑）
    if not tree_x:
        raise st.StoreError(f"no scattered sections found for article {article!r}")
    others = load_project(layout)                   # 其它篇（已 store；不含本散檔篇）

    groups = st.group_records_from_tree(layout, article)
    article_obj = st.article_from_leaves(article, tree_x, groups, revision=1)
    store_x = st.leaves_from_article(layout, article_obj)

    # ① 逐節深等值（concept/decisions/history/material）
    mism: list[str] = []
    tree_by = {lf.section: lf for lf in tree_x}
    store_by = {lf.section: lf for lf in store_x}
    if set(tree_by) != set(store_by):
        only_tree = sorted(set(tree_by) - set(store_by))
        only_store = sorted(set(store_by) - set(tree_by))
        if only_tree:
            mism.append(f"sections only in scattered: {only_tree}")
        if only_store:
            mism.append(f"sections only in store: {only_store}")
    for sec in sorted(set(tree_by) & set(store_by)):
        if _leaf_truth(tree_by[sec]) != _leaf_truth(store_by[sec]):
            mism.append(f"{sec}: leaf truth differs (concept/decisions/history/material)")

    # ② anc/deps/norm 三軸逐節相等（全 leaf-set：其它篇 store 不變、X 篇 tree vs store 讀）
    fp_tree = _fingerprints(others + tree_x)
    fp_store = _fingerprints(others + store_x)
    for sec in sorted(set(tree_by) & set(store_by)):
        if fp_tree.get(sec) != fp_store.get(sec):
            mism.append(f"{sec}: anc/deps/norm fingerprint differs "
                        f"(tree={fp_tree.get(sec)} store={fp_store.get(sec)})")
    return article_obj, mism


# ── migrate ───────────────────────────────────────────────────────────

def _guard_scatter_files(layout: Layout, article: str) -> list[str]:
    """掃該篇散檔樹，回「非預期檔」清單（migrate 遇任一非預期檔 fail-loud，永不靜默刪資料）。"""
    art_dir = layout.section_dir(article)
    unexpected: list[str] = []
    if not art_dir.is_dir():
        return unexpected
    allowed = set(_FOLD_FILES) | set(_MOVE_TO_WORK)
    for p in sorted(art_dir.rglob("*")):
        if layout.is_archived_path(p):
            continue
        if p.is_dir():
            if p.name == "assets" and any(f.is_file() for f in p.rglob("*")):
                unexpected.append(f"{p.relative_to(layout.corpus_dir).as_posix()}/ (corpus-side "
                                  "assets — relocate to docs/assets/ before migrating)")
            continue
        # 治理檔（audit/roadmap/roadmap-archive.yaml）只在文章**根層**放行（fold 只收根層那份）；
        # 巢狀誤放＝unexpected fail-loud，永不靜默刪（#9：guard 的唯一職責就是不靜默刪資料）。
        if p.name in _GOVERNANCE_FILES and p.parent == art_dir:
            continue
        if p.name not in allowed:
            unexpected.append(p.relative_to(layout.corpus_dir).as_posix())
    return unexpected


def _migrate_one(layout: Layout, article: str, schema) -> int:
    backend = st.backend_of(layout, article)
    if backend == "store":
        print(f"store migrate: {article} already a store (nothing to do)")
        return 0
    if backend == "none":
        sys.stderr.write(f"docspec: store migrate: no such article {article!r} in corpus/\n")
        return 1

    unexpected = _guard_scatter_files(layout, article)
    if unexpected:
        sys.stderr.write(
            f"docspec: store migrate {article}: refusing — the scattered tree has files the store "
            "does not model yet (migration would lose them):\n")
        for u in unexpected:
            sys.stderr.write(f"    ✗ {u}\n")
        return 1

    try:
        article_obj, mism = _parity_check(layout, article, schema)
    except st.StoreError as exc:
        sys.stderr.write(f"docspec: store migrate {article}: {exc}\n")
        return 1
    if mism:
        sys.stderr.write(
            f"docspec: store migrate {article}: PARITY GATE FAILED — not written (scattered files "
            "left intact):\n")
        for m in mism:
            sys.stderr.write(f"    ✗ {m}\n")
        return 1

    # 平價閘過關 → 寫 store 檔、搬 develop/history 散文出 store、刪散檔樹。
    st.save_article(layout, article_obj, schema)
    moved = _relocate_workfiles(layout, article)
    folded_gov = _fold_governance(layout, article)
    _delete_scatter_tree(layout, article)
    print(f"store migrate: {article} -> corpus/{article}.yaml "
          f"({len(article_obj.leaf_records())} leaves, {len(article_obj.group_records())} groups; "
          f"parity gate passed).")
    if moved:
        print(f"  moved {moved} workbench/prose file(s) to docspec/work/{article}/…")
    print(f"  reverse anytime: docspec store dump {article} <DIR>  then delete corpus/{article}.yaml")
    return 0


def _relocate_workfiles(layout: Layout, article: str) -> int:
    """把 develop.md / history.md（非 store 承載）搬到 work/ 鏡像樹，保全不刪。"""
    art_dir = layout.section_dir(article)
    moved = 0
    for name in _MOVE_TO_WORK:
        for p in sorted(art_dir.rglob(name)):
            if layout.is_archived_path(p):
                continue
            section = layout.section_id(p.parent)
            dst = st.work_dir(layout, section) / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), str(dst))
            moved += 1
    return moved


def _fold_governance(layout: Layout, article: str) -> int:
    """migrate 收編：散檔 `<article>/{audit,roadmap}.yaml` → sibling 密封檔；
    `roadmap-archive.yaml` → 單一 forest archive。回傳收編的檔數。"""
    from dspx.engine.sealed import load_sealed
    from dspx.reports.audit import AuditError, AuditStore, doc_audit_path
    from dspx.reports.roadmap import (RoadmapError, _append_archive, _write_entries,
                                      doc_roadmap_path, forest_roadmap_archive_path)
    art_dir = layout.section_dir(article)
    folded = 0
    old_audit = art_dir / "audit.yaml"
    if old_audit.is_file():
        _rev, findings = load_sealed(old_audit, list_key="findings", error_cls=AuditError)
        AuditStore(path=doc_audit_path(layout, article), findings=findings,
                   store=f"doc:{article}").save()
        folded += 1
    old_roadmap = art_dir / "roadmap.yaml"
    if old_roadmap.is_file():
        _rev, entries = load_sealed(old_roadmap, list_key="entries", error_cls=RoadmapError)
        _write_entries(doc_roadmap_path(layout, article), entries)
        folded += 1
    old_archive = art_dir / "roadmap-archive.yaml"
    if old_archive.is_file():
        _rev, arch = load_sealed(old_archive, list_key="entries", error_cls=RoadmapError)
        for rec in arch:
            _append_archive(forest_roadmap_archive_path(layout), rec)
        folded += 1
    return folded


def _delete_scatter_tree(layout: Layout, article: str) -> None:
    art_dir = layout.section_dir(article)
    if art_dir.is_dir():
        shutil.rmtree(art_dir)


# ── dump（store → 散檔）────────────────────────────────────────────────

def _dump_one(layout: Layout, article: str, out_dir: Path, schema) -> int:
    if not st.article_has_store(layout, article):
        sys.stderr.write(f"docspec: store dump: no store file corpus/{article}.yaml\n")
        return 1
    article_obj = st.load_article(st.store_path(layout, article))
    out_dir.mkdir(parents=True, exist_ok=True)
    for rec in article_obj.sorted_records():
        sec_dir = out_dir.joinpath(*rec.path.split("/"))
        sec_dir.mkdir(parents=True, exist_ok=True)
        if rec.kind == "group":
            meta = {k: v for k, v in (rec.group or {}).items() if v is not None}
            if meta:
                (sec_dir / "group.yaml").write_text(
                    yaml.safe_dump(meta, allow_unicode=True, sort_keys=False),
                    encoding="utf-8", newline="\n")
            continue
        if rec.concept is not None:
            (sec_dir / "concept.yaml").write_text(
                yaml.safe_dump(rec.concept, allow_unicode=True, sort_keys=False),
                encoding="utf-8", newline="\n")
        if rec.decisions:
            (sec_dir / "decisions.yaml").write_text(
                yaml.safe_dump({"entries": rec.decisions}, allow_unicode=True, sort_keys=False),
                encoding="utf-8", newline="\n")
        if rec.history:
            (sec_dir / "history.yaml").write_text(
                yaml.safe_dump({"entries": rec.history}, allow_unicode=True, sort_keys=False),
                encoding="utf-8", newline="\n")
        if rec.material is not None:
            (sec_dir / "material.md").write_text(rec.material, encoding="utf-8", newline="\n")
    print(f"store dump: corpus/{article}.yaml -> {out_dir} (read-only export; "
          f"{len(article_obj.leaf_records())} leaves)")
    return 0


# ── load（散檔 DIR → store，過全驗證）──────────────────────────────────

def _load_one(layout: Layout, article: str, src_dir: Path, schema) -> int:
    if not src_dir.is_dir():
        sys.stderr.write(f"docspec: store load: no such directory {src_dir}\n")
        return 1
    if st.article_has_store(layout, article):
        sys.stderr.write(f"docspec: store load: corpus/{article}.yaml already exists "
                         "(delete it first, or use fsck)\n")
        return 1
    leaves = []
    groups: list[dict] = []
    for cp in sorted(src_dir.rglob("concept.yaml")):
        section = cp.parent.relative_to(src_dir).as_posix()
        leaves.append(leaf_from_dir(f"{article}/{section}" if section != "." else article, cp.parent))
    for gy in sorted(src_dir.rglob("group.yaml")):
        if (gy.parent / "concept.yaml").is_file():
            continue
        rel = gy.parent.relative_to(src_dir).as_posix()
        try:
            meta = yaml.safe_load(gy.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            sys.stderr.write(f"docspec: store load: malformed {gy} ({exc})\n")
            return 1
        rec = {"path": f"{article}/{rel}" if rel != "." else article}
        for k in ("title", "order", "numbering"):
            if isinstance(meta, dict) and meta.get(k) is not None:
                rec[k] = meta[k]
        groups.append(rec)
    if not leaves:
        sys.stderr.write(f"docspec: store load: no concept.yaml under {src_dir}\n")
        return 1
    article_obj = st.article_from_leaves(article, leaves, groups, revision=1)
    # 過封條驗證的往返（dump→parse verify）確保寫出即合法。
    text = st.dump_article(article_obj, schema)
    st.article_from_dict(yaml.safe_load(text), st.store_path(layout, article))  # verify
    st.atomic_write_store(st.store_path(layout, article), text)
    print(f"store load: {src_dir} -> corpus/{article}.yaml ({len(leaves)} leaves, validated)")
    return 0


# ── fsck（驗封條）──────────────────────────────────────────────────────

def _fsck_governance(layout: Layout, articles: list[str], accept: bool) -> int:
    """驗（並在 --accept 時重封）封條治理檔＝doc audit/roadmap sibling＋forest（#1：這些以前
    完全不在 fsck 掃描面，fail-loud 指路 fsck 卻修不了它們＝死路）。"""
    from dspx.engine.sealed import load_sealed, write_sealed
    from dspx.reports.audit import doc_audit_path, forest_audit_path
    from dspx.reports.roadmap import doc_roadmap_path, forest_roadmap_path
    checks: list = []
    for a in articles:
        checks.append((doc_audit_path(layout, a), "audit", f"doc:{a}", "findings"))
        checks.append((doc_roadmap_path(layout, a), "roadmap", f"doc:{a}", "entries"))
    checks.append((forest_audit_path(layout), "audit", "forest", "findings"))
    checks.append((forest_roadmap_path(layout), "roadmap", "forest", "entries"))
    rc = 0
    for path, kind, scope, key in checks:
        if not path.is_file():
            continue
        try:
            load_sealed(path, list_key=key, error_cls=st.StoreError, verify=True)
            print(f"store fsck: {path.name} OK (integrity seal valid)")
        except st.StoreError as exc:
            if accept:
                rev, items = load_sealed(path, list_key=key, error_cls=st.StoreError, verify=False)
                write_sealed(path, kind=kind, scope=scope, revision=rev, list_key=key, items=items)
                print(f"store fsck: {path.name} RESEALED (external change adopted)")
            else:
                sys.stderr.write(f"docspec: store fsck: {path.name}: {exc}\n")
                rc = 1
    return rc


def _fsck(layout: Layout, articles: list[str], accept: bool, schema) -> int:
    rc = 0
    for article in articles:
        path = st.store_path(layout, article)
        try:
            st.load_article(path, verify=True)
            print(f"store fsck: {article} OK (integrity seal valid)")
        except st.StoreError as exc:
            if accept:
                article_obj = st.load_article(path, verify=False)
                st.save_article(layout, article_obj, schema)
                print(f"store fsck: {article} RESEALED (external change adopted)")
            else:
                sys.stderr.write(f"docspec: store fsck: {article}: {exc}\n")
                rc = 1
    return _fsck_governance(layout, articles, accept) or rc


# ── CLI ───────────────────────────────────────────────────────────────

def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec store", description=HELP)
    sub = parser.add_subparsers(dest="sub", required=True)

    p_mig = sub.add_parser("migrate", help="convert a scattered article to a store file (parity-gated)")
    p_mig.add_argument("article", nargs="?", help="article name (or use --all)")
    p_mig.add_argument("--all", action="store_true", help="migrate every scattered article")

    p_dump = sub.add_parser("dump", help="export a store back to scattered files (read-only)")
    p_dump.add_argument("article")
    p_dump.add_argument("out", help="output directory")

    p_load = sub.add_parser("load", help="import scattered files into a store (full validation)")
    p_load.add_argument("article")
    p_load.add_argument("src", help="source directory of scattered files")

    p_fsck = sub.add_parser("fsck", help="verify integrity seals; --accept re-seals external edits")
    p_fsck.add_argument("article", nargs="?", help="article name (default: all store articles)")
    p_fsck.add_argument("--accept", action="store_true", help="adopt external changes and re-seal")

    p_tidy = sub.add_parser("tidy", help="deterministic idempotent corpus cleanup: strip verbatim-"
                            "duplicate brief fields / chapter-number title prefixes, rename folders "
                            "to delivery-language slugs")
    p_tidy.add_argument("--dry-run", action="store_true", dest="dry_run",
                        help="print the complete action list without touching any store file")

    args = parser.parse_args(argv)

    try:
        layout, config = bootstrap()
        schema = load_engine_schema(config)
    except BootstrapError as exc:
        return exc.exit_code

    if args.sub == "migrate":
        if args.all:
            # 掃全散檔文章（有 leaf 夾樹者；store 篇已遷、跳過）——遷移橋 tree_articles。
            arts = st.tree_articles(layout)
            rc = 0
            for a in arts:
                rc = _migrate_one(layout, a, schema) or rc
            if not arts:
                print("store migrate --all: no scattered articles to migrate")
            return rc
        if not args.article:
            sys.stderr.write("docspec: store migrate: give an <article> or --all\n")
            return 2
        return _migrate_one(layout, args.article, schema)

    if args.sub == "dump":
        return _dump_one(layout, args.article, Path(args.out), schema)
    if args.sub == "load":
        return _load_one(layout, args.article, Path(args.src), schema)
    if args.sub == "fsck":
        arts = [args.article] if args.article else st.store_articles(layout)
        if not arts:
            print("store fsck: no store articles")
            return 0
        return _fsck(layout, arts, args.accept, schema)
    if args.sub == "tidy":
        from dspx.commands.corpus import _tidy
        return _tidy.run(["--dry-run"] if args.dry_run else [])
    return 2
