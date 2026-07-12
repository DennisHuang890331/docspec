"""docspec retire-section <section> — 整節退場。

跟 `docspec retire`（搬決策）不同層級：這裡退場「整個章節（含子節）」。
設計（per-section 獨立、適合長期文件管理）：
  1. 退場結構記錄 append 進該節「自己的」history.yaml 的 `retired:` 區塊
     （section=原路徑、archive=封存實體位置＝link、note、in）；
  2. 退場散文（為何整節退場）開進該節 history.md 的 `## <原路徑>` 段；
  3. 整包搬進扁平封存區 corpus/_archive/<攤平路徑>/——兩份記錄隨節一起走、自我包含、可回復；
  4. 引擎忽略 `_` 開頭目錄，封存後對 status/check/render/draft 全隱形。
查詢用 `docspec retired`。
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys

import yaml

from dspx.commands._shared import BootstrapError, bootstrap

NAME = "retire-section"
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


def _section_id(section_dir, section: str) -> str:
    """整節退場用該節穩定 concept.id（非路徑！）；develop-only 節退場則用路徑指紋（同 new 規則）。"""
    return _concept_field(section_dir, "id") or (
        "sec-" + hashlib.sha1(section.encode("utf-8")).hexdigest()[:8])


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


def _warn_back_references(layout, section: str, src) -> None:
    """退役前反向引用警告（D5：警告不擋）：掃 audit findings 的 targets/sot-owner 與
    roadmap entries 的 target，指向待退子樹者逐條列出（退役後 check 將報 target 死引用），
    然後照常執行——退役常是正當操作、記錄本該跟著改。"""
    from dspx.audit import load_doc_audit, load_forest_audit
    from dspx.roadmap import load_doc_roadmap, load_forest_roadmap

    sub_ids = _subtree_concept_ids(src)

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


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec retire-section", description=HELP)
    parser.add_argument("section", help="path of the section to retire (relative to corpus/)")
    parser.add_argument("--in", dest="retired_in", default=None,
                        help="which change/session this is retired in (written to retired.in)")
    parser.add_argument("--note", default=None,
                        help="one-line description (defaults to the section's concept.concept)")
    args = parser.parse_args(argv)

    try:
        layout, _config = bootstrap()
    except BootstrapError as exc:
        return exc.exit_code

    section = args.section.strip("/")

    # ── 誠實邊界：store 篇的結構化退場（抽記錄→封存包）＝Phase-C 後續（未落地）。指路散檔逃生口。──
    from dspx import store as _store
    if _store.article_has_store(layout, layout.article_of(section)):
        sys.stderr.write(
            f"docspec: retire-section does not yet operate on store-backed article "
            f"\"{layout.article_of(section)}\" (corpus/{layout.article_of(section)}.yaml). Use "
            f"`docspec store dump {layout.article_of(section)} <DIR>`, retire in the scattered "
            "export, then `docspec store load` — the structured record-retire is a Phase-C "
            "follow-up.\n")
        return 1

    src = layout.section_dir(section)
    if not src.is_dir() or not (
        (src / "concept.yaml").is_file() or (src / "develop.md").is_file()
    ):
        sys.stderr.write(
            f"docspec: section \"{section}\" not found (needs concept.yaml or develop.md). "
            f"Use docspec status / docspec list to get the correct path.\n")
        return 1
    if layout.is_archived_path(src):
        sys.stderr.write(f"docspec: \"{section}\" is already in the archive.\n")
        return 1

    note = args.note or _concept_field(src, "concept") or section
    sec_id = _section_id(src, section)
    # 封存實體位置（＝link），存進記錄；相對 planning home（corpus/_archive/...）
    archive_root = layout.corpus_archive_dir
    dest = archive_root / section.replace("/", "__")
    # 撞號拒絕（D5）：待退節 id 已存在於封存區退場記錄＝「已退役」與「活著」對同一 id 同真
    # （台中港真實撞過 3 對：路徑重用、id 沿用）。拒絕＋指路，不靜默疊第二筆。
    # 先於 dest-exists 檢查：同路徑重退時，id 撞號訊息（含解法）比「資料夾已存在」更對症。
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

    # 反向引用警告（D5：警告、不擋）：audit/roadmap 指向待退子樹的記錄逐條預告。
    _warn_back_references(layout, section, src)

    # 整節退場＝該節 history.yaml entries 多一筆 kind:section（id=concept.id、附 archive link）。
    # 細節＝archive 資料夾本身（不寫 history.md；history.md 只給決策退場的散文）。隨節進 archive。
    history_path = src / "history.yaml"
    entries: list = []
    if history_path.is_file():
        try:
            loaded = yaml.safe_load(history_path.read_text(encoding="utf-8")) or {}
            if isinstance(loaded, dict):
                entries = [e for e in (loaded.get("entries") or []) if isinstance(e, dict)]
        except yaml.YAMLError:
            entries = []
    entries.append({
        "id": sec_id,              # ★該節穩定 concept.id（非路徑）
        "kind": "section",
        "status": "retired",
        "statement": note,
        "archive": archive_link,   # 指向封存資料夾的 link（細節在那）
        **({"retired-in": args.retired_in} if args.retired_in else {}),
    })
    history_path.write_text(
        "# 本節歷史 entries：死決策（kind normative/rationale，散文在 history.md）"
        "＋整節退場（kind section，細節在 archive 資料夾）。\n"
        + yaml.safe_dump({"entries": entries}, allow_unicode=True, sort_keys=False),
        encoding="utf-8", newline="\n")

    # 整包搬進扁平封存區（可回復、引擎隱形）
    archive_root.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    # 搬移後完整性驗證（Drive 同步/權限可能半搬）
    if src.exists() or not (dest / "history.yaml").is_file():
        sys.stderr.write(f"docspec: retire move anomaly (src={src.exists()} dest_ok={dest.is_dir()})\n")
        return 1

    # 整篇文章退役（D6）：活樹已無該文章任何節 → 交付檔＋帳本搬進封存包，
    # docs/.ledger 不留孤兒（散文只活在 _latest.md，不搬＝「recoverable」是假話）。
    article = layout.article_of(section)
    moved_deliverables: list[str] = []
    if article and not _article_has_live_sections(layout, article):
        moved_deliverables = _migrate_orphan_deliverable(layout, article, dest)

    print(f"retire-section: \"{section}\" retired -> {dest.relative_to(layout.project_root)}")
    print(f"  one-liner: {note}")
    print(f"  link (archive): {archive_link}")
    if moved_deliverables:
        print(f"  whole article \"{article}\" retired: moved its deliverable + ledger into the "
              f"archive package ({', '.join(moved_deliverables)}) — docs/.ledger keep no orphans.")
    print("  content is recoverable; query with docspec retired, the engine already ignores the archive.")
    return 0
