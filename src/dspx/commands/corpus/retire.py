"""docspec retire <section> — 整節退場（含子節）到 corpus/_archive/。

（消滅三胞胎：舊的「retire＝死決策純報告」已刪——死決策就地留在 decisions.yaml 標
superseded/deprecated，用 `docspec show <article> --decisions --all-status` 檢視；退場整節＝
本指令的交易；查詢已退場＝`docspec retired`。）

設計（per-section 獨立、適合長期文件管理）：
  1. 退場結構記錄 append 進該節「自己的」history.yaml 的 entries（kind:section＝原路徑、
     archive＝封存實體位置＝link、note、in）；
  2. 退場散文（為何整節退場）開進該節 history.md 的 `## <原路徑>` 段；
  3. 整包搬進扁平封存區 corpus/_archive/<攤平路徑>/——兩份記錄隨節一起走、自我包含、可回復；
  4. 引擎忽略 `_` 開頭目錄，封存後對 status/check/render/draft 全隱形。

兩個 backend 都真正退場：
  - **tree 篇**（散檔 leaf 夾樹）＝把整個節資料夾搬進 _archive/。
  - **store 篇**（一篇一檔 corpus/<article>.yaml）＝把該子樹的記錄從活 store 抽出、dump 成
    _archive/ 封存包（可回復的散檔形態）、活 store 移除記錄、revision+1、原子重寫。

查詢用 `docspec retired`。
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys

import yaml

from dspx.commands._shared import BootstrapError, bootstrap, load_engine_schema

NAME = "retire"
HELP = "retire an entire section (including children) to corpus/_archive/; recorded as a kind:section entry in the section's history.yaml"


def _concept_field(section_dir, field: str) -> str | None:
    path = section_dir / "concept.yaml"
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return None
    if isinstance(data, dict) and data.get(field):
        return str(data[field])
    return None


def _section_id_for_path(section: str) -> str:
    """develop-only 節退場用路徑指紋（同 new 規則）；leaf 有 concept.id 時優先用它（見呼叫端）。"""
    return "sec-" + hashlib.sha1(section.encode("utf-8")).hexdigest()[:8]


def _section_id(section_dir, section: str) -> str:
    """整節退場用該節穩定 concept.id（非路徑！）；develop-only 節退場則用路徑指紋（同 new 規則）。"""
    return _concept_field(section_dir, "id") or _section_id_for_path(section)


def _archived_retired_ids(layout) -> dict[str, str]:
    """封存區既有的整節退場 id → 封存位置（_archive/*/history.yaml 的 kind:section entry）。

    撞號拒絕（D5）用：「已退役」與「活著」對同一 id 不能同真——同 id 再退＝兩筆退場記錄
    指同一 id、`docspec retired` 與回復流程無從分辨。"""
    out: dict[str, str] = {}
    root = layout.corpus_archive_dir
    if not root.is_dir():
        return out
    for hist in sorted(root.rglob("history.yaml")):
        try:
            data = yaml.safe_load(hist.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        entries = (data.get("entries") or []) if isinstance(data, dict) else []
        for e in entries:
            if isinstance(e, dict) and e.get("kind") == "section" and e.get("id"):
                out.setdefault(str(e["id"]),
                               str(e.get("archive")
                                   or hist.parent.relative_to(layout.planning_home).as_posix()))
    return out


def _subtree_concept_ids(src) -> set[str]:
    """待退子樹內全部 concept.id（含子節），供反向引用比對（target 可能是 id 而非路徑）。"""
    ids: set[str] = set()
    for cy in src.rglob("concept.yaml"):
        cid = _concept_field(cy.parent, "id")
        if cid:
            ids.add(cid)
    return ids


def _warn_back_references(layout, section: str, sub_ids: set[str]) -> None:
    """退役前反向引用警告（D5：警告不擋）：掃 audit findings 的 targets/sot-owner 與
    roadmap entries 的 target，指向待退子樹者逐條列出（退役後 check 將報 target 死引用），
    然後照常執行——退役常是正當操作、記錄本該跟著改。sub_ids＝待退子樹的 concept.id 集
    （tree 由 rglob、store 由記錄收；target 可能是 id 而非路徑）。"""
    from dspx.reports.audit import load_doc_audit, load_forest_audit
    from dspx.reports.roadmap import load_doc_roadmap, load_forest_roadmap

    def _refers(target: object) -> bool:
        t = str(target).split("#", 1)[0]
        return t == section or t.startswith(section + "/") or t in sub_ids

    hits: list[str] = []
    articles = layout.articles()
    audit_stores = [load_forest_audit(layout)] + [
        load_doc_audit(layout.section_dir(a), a) for a in articles]
    for store in audit_stores:
        for f in store.findings:
            fid = f.get("id")
            refs = [str(t) for t in (f.get("targets") or []) if _refers(t)]
            if f.get("sot-owner") and _refers(f["sot-owner"]):
                refs.append(f"sot-owner {f['sot-owner']}")
            for ref in refs:
                hits.append(f"audit finding {fid} ({store.store or store.path.name}) -> \"{ref}\"")
    entries = list(load_forest_roadmap(layout))
    for a in articles:
        entries.extend(load_doc_roadmap(layout.section_dir(a), a))
    for e in entries:
        if _refers(e.get("target")):
            hits.append(f"roadmap entry {e.get('id')} ({e.get('_store')}) -> \"{e.get('target')}\"")

    if hits:
        sys.stderr.write(
            f"docspec: ⚠ {len(hits)} audit/roadmap reference(s) point into \"{section}\" and "
            "will become dead references after retirement (docspec check will flag them):\n")
        for h in hits:
            sys.stderr.write(f"    {h}\n")
        sys.stderr.write("  retiring anyway; update or close these records afterwards.\n")


def _migrate_orphan_deliverable(layout, article: str, dest) -> list[str]:
    """整篇文章退役（活樹已無該文章任何節）→ 把 `docs/<article>_latest.md` 與
    `.ledger/<article>.sections.yaml` 一併搬進封存包（D6：散文與帳隨封存自我包含，
    「content is recoverable」才成立）。回傳搬了什麼（相對名）。docs 端凍結快照與
    圖檔不搬（archive/ 不可變；圖可能被其他文件共用）。"""
    moved: list[str] = []
    for f in (layout.docs_latest(article),
              layout.docs_ledger(article),
              layout.docs_ledger_legacy(article)):
        if f.is_file():
            target = dest / f.name
            shutil.move(str(f), str(target))
            moved.append(f.name)
    return moved


def _article_has_live_sections(layout, article: str) -> bool:
    """該文章在活樹是否還有任何節（concept/develop；`_` 隱形區不算）。"""
    art_dir = layout.section_dir(article)
    if not art_dir.is_dir():
        return False
    for name in ("concept.yaml", "develop.md"):
        for f in art_dir.rglob(name):
            if not layout.is_archived_path(f.parent):
                return True
    return False


def _write_history_yaml(history_path, entries: list) -> None:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(
        "# 本節歷史 entries：死決策（kind normative/rationale，散文在 history.md）"
        "＋整節退場（kind section，細節在 archive 資料夾）。\n"
        + yaml.safe_dump({"entries": entries}, allow_unicode=True, sort_keys=False),
        encoding="utf-8", newline="\n")


def _section_entry(sec_id: str, note: str, archive_link: str, retired_in: str | None) -> dict:
    return {
        "id": sec_id,              # ★該節穩定 concept.id（非路徑）
        "kind": "section",
        "status": "retired",
        "statement": note,
        "archive": archive_link,   # 指向封存資料夾的 link（細節在那）
        **({"retired-in": retired_in} if retired_in else {}),
    }


# ── store 篇退場：抽記錄→ dump 封存包（散檔形態）→活 store 移除、revision+1 ────────────

def _retire_store(layout, schema, section: str, args) -> int:
    from dspx.engine import store as _store

    article = layout.article_of(section)
    store_file = _store.store_path(layout, article)
    art = _store.load_article(store_file, verify=True)

    subtree = [r for r in art.records
               if r.path == section or r.path.startswith(section + "/")]
    if not subtree:
        sys.stderr.write(
            f"docspec: section \"{section}\" not found in store corpus/{article}.yaml. "
            "Use docspec status to get the correct path.\n")
        return 1

    own = art.record_by_path(section)
    own_concept = own.concept if (own is not None and own.kind == "leaf" and own.concept) else None
    note = (args.note
            or (str(own_concept.get("concept")) if own_concept and own_concept.get("concept") else None)
            or section)
    sec_id = (str(own_concept["id"]) if own_concept and own_concept.get("id")
              else _section_id_for_path(section))

    # 撞號拒絕（D5）：同一 id 不能同時「已退役」與「活著」。
    archived_ids = _archived_retired_ids(layout)
    if sec_id in archived_ids:
        sys.stderr.write(
            f"docspec: refusing to retire \"{section}\": its id \"{sec_id}\" is already recorded "
            f"as retired in the archive at {archived_ids[sec_id]}.\n"
            "  a retired and a live section cannot share the same id — give this section a new "
            "concept id, or resolve the archived entry first, then retire again.\n")
        return 1

    archive_root = layout.corpus_archive_dir
    dest = archive_root / section.replace("/", "__")
    if dest.exists():
        sys.stderr.write(f"docspec: archive destination already exists: {dest}. Resolve it before retiring.\n")
        return 1
    archive_link = dest.relative_to(layout.planning_home).as_posix()

    # 反向引用警告（子樹 concept.id 由記錄收集）。
    sub_ids = {str(r.concept["id"]) for r in subtree
               if r.kind == "leaf" and r.concept and r.concept.get("id")}
    _warn_back_references(layout, section, sub_ids)

    # ── dump 封存包（可回復的散檔形態；子樹相對位置保留）＋history.yaml（kind:section entry）──
    from pathlib import Path
    dest.mkdir(parents=True, exist_ok=True)
    dest_history: list = []
    for r in subtree:
        rel = r.path[len(section):].lstrip("/")
        rdir = dest / Path(*[p for p in rel.split("/") if p]) if rel else dest
        rdir.mkdir(parents=True, exist_ok=True)
        if r.kind == "group":
            meta = {k: v for k, v in (r.group or {}).items() if v is not None}
            (rdir / "group.yaml").write_text(
                yaml.safe_dump(meta, allow_unicode=True, sort_keys=False),
                encoding="utf-8", newline="\n")
            continue
        if r.concept is not None:
            (rdir / "concept.yaml").write_text(
                yaml.safe_dump(r.concept, allow_unicode=True, sort_keys=False),
                encoding="utf-8", newline="\n")
        if r.decisions:
            (rdir / "decisions.yaml").write_text(
                yaml.safe_dump({"entries": list(r.decisions)}, allow_unicode=True, sort_keys=False),
                encoding="utf-8", newline="\n")
        if r.material is not None:
            (rdir / "material.md").write_text(r.material, encoding="utf-8", newline="\n")
        # 該節自己既有的 history（退場記錄）併進退場根的 history.yaml（子節罕見有）
        if r.path == section:
            dest_history.extend(e for e in (r.history or []) if isinstance(e, dict))

    dest_history.append(_section_entry(sec_id, note, archive_link, args.retired_in))
    _write_history_yaml(dest / "history.yaml", dest_history)

    # ── 活 store 移除記錄、revision+1、原子重寫（或整篇退役→刪 store 檔＋搬交付物）──
    keep = [r for r in art.records
            if not (r.path == section or r.path.startswith(section + "/"))]
    art.records = keep
    art.revision += 1

    moved_deliverables: list[str] = []
    if any(r.kind == "leaf" for r in keep):
        _store.save_article(layout, art, schema)
    else:
        # 整篇退役：活 store 已無任何 leaf → 刪 store 檔（文章從活樹消失，對稱 tree 版），
        # 交付檔＋帳本搬進封存包（D6：content is recoverable）。
        store_file.unlink()
        moved_deliverables = _migrate_orphan_deliverable(layout, article, dest)

    print(f"retire: \"{section}\" retired -> {dest.relative_to(layout.project_root)} "
          f"(store corpus/{article}.yaml: {len(subtree)} record(s) extracted, revision {art.revision})")
    print(f"  one-liner: {note}")
    print(f"  link (archive): {archive_link}")
    if moved_deliverables:
        print(f"  whole article \"{article}\" retired: store file removed; moved its deliverable + "
              f"ledger into the archive package ({', '.join(moved_deliverables)}).")
    print("  content is recoverable; query with docspec retired, the engine already ignores the archive.")
    return 0


# ── tree 篇退場：整包搬進 _archive/ ──────────────────────────────────────────────

def _retire_tree(layout, section: str, args) -> int:
    src = layout.section_dir(section)
    if not src.is_dir() or not (
        (src / "concept.yaml").is_file() or (src / "develop.md").is_file()
    ):
        sys.stderr.write(
            f"docspec: section \"{section}\" not found (needs concept.yaml or develop.md). "
            f"Use docspec status to get the correct path.\n")
        return 1
    if layout.is_archived_path(src):
        sys.stderr.write(f"docspec: \"{section}\" is already in the archive.\n")
        return 1

    note = args.note or _concept_field(src, "concept") or section
    sec_id = _section_id(src, section)
    archive_root = layout.corpus_archive_dir
    dest = archive_root / section.replace("/", "__")
    # 撞號拒絕（D5）：先於 dest-exists 檢查（同路徑重退時 id 撞號訊息更對症）。
    archived_ids = _archived_retired_ids(layout)
    if sec_id in archived_ids:
        sys.stderr.write(
            f"docspec: refusing to retire \"{section}\": its id \"{sec_id}\" is already recorded "
            f"as retired in the archive at {archived_ids[sec_id]}.\n"
            "  a retired and a live section cannot share the same id — give this section a new "
            "concept id, or resolve the archived entry first, then retire again.\n")
        return 1

    if dest.exists():
        sys.stderr.write(f"docspec: archive destination already exists: {dest}. Resolve it before retiring.\n")
        return 1
    archive_link = dest.relative_to(layout.planning_home).as_posix()

    # 反向引用警告（D5：警告、不擋）。
    _warn_back_references(layout, section, _subtree_concept_ids(src))

    # 整節退場＝該節 history.yaml entries 多一筆 kind:section（id=concept.id、附 archive link）。
    history_path = src / "history.yaml"
    entries: list = []
    if history_path.is_file():
        try:
            loaded = yaml.safe_load(history_path.read_text(encoding="utf-8")) or {}
            if isinstance(loaded, dict):
                entries = [e for e in (loaded.get("entries") or []) if isinstance(e, dict)]
        except yaml.YAMLError:
            entries = []
    entries.append(_section_entry(sec_id, note, archive_link, args.retired_in))
    _write_history_yaml(history_path, entries)

    # 整包搬進扁平封存區（可回復、引擎隱形）
    archive_root.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    if src.exists() or not (dest / "history.yaml").is_file():
        sys.stderr.write(f"docspec: retire move anomaly (src={src.exists()} dest_ok={dest.is_dir()})\n")
        return 1

    article = layout.article_of(section)
    moved_deliverables: list[str] = []
    if article and not _article_has_live_sections(layout, article):
        moved_deliverables = _migrate_orphan_deliverable(layout, article, dest)

    print(f"retire: \"{section}\" retired -> {dest.relative_to(layout.project_root)}")
    print(f"  one-liner: {note}")
    print(f"  link (archive): {archive_link}")
    if moved_deliverables:
        print(f"  whole article \"{article}\" retired: moved its deliverable + ledger into the "
              f"archive package ({', '.join(moved_deliverables)}) — docs/.ledger keep no orphans.")
    print("  content is recoverable; query with docspec retired, the engine already ignores the archive.")
    return 0


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec retire", description=HELP)
    parser.add_argument("section", help="path of the section to retire (relative to corpus/)")
    parser.add_argument("--in", dest="retired_in", default=None,
                        help="which change/session this is retired in (written to retired.in)")
    parser.add_argument("--note", default=None,
                        help="one-line description (defaults to the section's concept.concept)")
    args = parser.parse_args(argv)

    try:
        layout, config = bootstrap()
        schema = load_engine_schema(config)
    except BootstrapError as exc:
        return exc.exit_code

    section = args.section.strip("/")

    # backend 路由：store 篇走結構化記錄退場、tree 篇搬資料夾。
    from dspx.engine import store as _store
    if _store.article_has_store(layout, layout.article_of(section)):
        return _retire_store(layout, schema, section, args)
    return _retire_tree(layout, section, args)
