"""docspec put <section> <category> <FILE|-> — corpus 真相的**唯一驗證寫入門**。

concept/decisions/material 的寫入本該只有一道驗證門，不是 agent 各自寫再事後 lint/check 抓錯。put 把
「寫入」變成一道引擎交易：收 agent 編輯後的內容 → 先過 `run_file_check`（既有欄位驗證）＋結構
驗證（重複 id、entries 形狀、enum、relation 目標存在）→ 通過才**原子寫**（tmp + os.replace）回 store；
任一驗證失敗＝拒收、報錯、**原檔一個 byte 不動**（不寫半套）。首寫 concept（該節原無 concept 記錄）
時帶入 id/order，取代「agent 手寫真相」。

刻意**不**在寫入當下擋「完整性」（必填未齊）：completeness 閘在晉升（ready/publish），不在寫入
（schema boundaries 明文）——put 只擋結構壞掉（壞 enum／重複 id／斷 relation／壞形狀），半成品
concept 照收（該節停在 developing）。寫入落在一篇一檔 store（`corpus/<article>.yaml`），這道門是唯一寫入口。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from dspx.engine import change as chg
from dspx.check import run_file_check
from dspx.commands._shared import BootstrapError, bootstrap, load_engine_schema
from dspx.commands.corpus.new import _next_order, _stable_id, validate_section_path
from dspx.engine.model import Leaf, ModelError, _DupCheckLoader, _entries

NAME = "put"
HELP = "the single validated write gate: validate then atomically write a section's concept/decisions/material"

# category → get/put 匯出檔名慣例（store block 的暫存檔名；store-only 後不再是磁碟散檔）。
_CATEGORIES = {
    "concept": "concept.yaml",
    "decisions": "decisions.yaml",
    "material": "material.md",
}

# run_file_check 的「完整性」訊息（必填未齊／佔位字）＝寫入當下合法（developing）、put 不擋。
_COMPLETENESS_MARKERS = ("missing or empty", "is a placeholder")


def _parse_yaml_text(text: str, where: str):
    """解析 YAML 文字，重複 mapping key fail-loud（同 model._load_yaml 的 loader，同源）。"""
    from dspx.engine.model import _DuplicateKeyError
    try:
        return yaml.load(text, Loader=_DupCheckLoader)
    except _DuplicateKeyError as exc:
        raise ModelError(f"{where}: YAML duplicate key: {exc}") from exc
    except yaml.YAMLError as exc:
        position = ""
        mark = getattr(exc, "problem_mark", None)
        if mark is not None:
            position = f" (line {mark.line + 1})"
        raise ModelError(f"{where}: YAML parse failed{position}") from exc


def _leaf_ids_with_section(leaf: Leaf) -> list[tuple[str, str]]:
    """一節宣告的全部 id（concept ∪ decisions ∪ history）配上它的 section。"""
    out: list[tuple[str, str]] = []
    if leaf.concept and leaf.concept.get("id"):
        out.append((str(leaf.concept["id"]), leaf.section))
    for e in leaf.decisions:
        if e.get("id"):
            out.append((str(e["id"]), leaf.section))
    for e in leaf.history:
        if e.get("id"):
            out.append((str(e["id"]), leaf.section))
    return out


def _candidate_ids_ordered(leaf: Leaf) -> list[str]:
    return [iid for iid, _sec in _leaf_ids_with_section(leaf)]


def _structural_errors(schema, section: str, category: str,
                       candidate: Leaf, others: list[Leaf]) -> list[str]:
    """結構驗證（拒收判準）：欄位（enum/型別/未知鍵，非完整性）＋重複 id＋relation 目標存在。"""
    errs: list[str] = []

    # ① 欄位級（run_file_check）；濾掉「完整性」訊息（寫入當下合法）
    for e in run_file_check(candidate, schema):
        if any(m in e for m in _COMPLETENESS_MARKERS):
            continue
        errs.append(e)

    # ② 重複 id：candidate 內部重複 ＋ 撞別節既有 id
    other_ids: dict[str, str] = {}
    for lf in others:
        for iid, sec in _leaf_ids_with_section(lf):
            other_ids.setdefault(iid, sec)
    seen_local: set = set()
    for iid in _candidate_ids_ordered(candidate):
        if iid in seen_local:
            errs.append(f'{section}: duplicate id "{iid}" within this section')
        seen_local.add(iid)
        if iid in other_ids:
            errs.append(f'{section}: id "{iid}" is already claimed by {other_ids[iid]}')

    # ③ relation 目標存在（只驗**送進來的內容**自己的 realizes/governed-by/supersedes/trace）
    universe = set(other_ids) | set(_candidate_ids_ordered(candidate))

    def _check(target, where):
        if target is None:
            return
        for t in (target if isinstance(target, list) else [target]):
            if str(t) not in universe:
                errs.append(f'{section}: {where} points to nonexistent id "{t}"')

    if category == "concept" and isinstance(candidate.concept, dict):
        _check(candidate.concept.get("realizes"), "concept.realizes")
        _check(candidate.concept.get("governed-by"), "concept.governed-by")
    if category == "decisions":
        for e in candidate.decisions:
            eid = e.get("id", "?")
            _check(e.get("supersedes"), f"decisions[{eid}].supersedes")
            _check(e.get("superseded-by"), f"decisions[{eid}].superseded-by")
            trace = e.get("trace") or {}
            if isinstance(trace, dict):
                _check(trace.get("governs"), f"decisions[{eid}].trace.governs")
                _check(trace.get("refs"), f"decisions[{eid}].trace.refs")
    return errs


def _read_source(source: str) -> str:
    if source == "-":
        return sys.stdin.read()
    p = Path(source)
    if not p.is_file():
        raise FileNotFoundError(source)
    return p.read_text(encoding="utf-8")


def _put_store(layout, schema, args, section: str, text: str, change) -> int:
    """store 篇 put：把分類寫進正式 store 記錄（無 --change）或 change 的 partial store staging 記錄
    （有 --change，official byte 凍結）。同一驗證管線（欄位 check＋重複 id＋relation 目標＋enum）；
    通過才 canonical dump 原子寫。first-write concept 帶入 id/order（取代 agent 手寫）。"""
    from dspx.engine import store as _store
    category = args.category
    article = layout.article_of(section)

    # 取目標 Article（staging 或正式）＋ id 唯一/relation 宇宙（others）
    if change is not None:
        chg.stage_section(change, layout, section)   # 確保 partial store 有此記錄（深拷貝／pending）
        art_obj = chg._load_staging_article(change.dir, article)
        others = [lf for lf in chg.load_union(layout, change) if lf.section != section]
    else:
        from dspx.engine.model import load_project
        # first-write：該篇尚無 store 檔（首個 crystallize 的節）→ 起一份空 Article、寫入後即生檔。
        if _store.article_has_store(layout, article):
            art_obj = _store.load_article(_store.store_path(layout, article), verify=True)
        else:
            art_obj = _store.Article(name=article, revision=0, records=[])
        others = [lf for lf in load_project(layout) if lf.section != section]
    rec = art_obj.record_by_path(section)
    if rec is None:
        rec = _store.SectionRecord(path=section, kind="leaf")
        art_obj.records.append(rec)

    had = (bool(rec.concept) if category == "concept"
           else bool(rec.decisions) if category == "decisions"
           else rec.material is not None)
    stamp_first = category == "concept" and not (rec.concept and rec.concept.get("id"))

    # ── 解析 + 形狀（壞 YAML／壞形狀 fail-loud、記錄不動）──
    parsed: object
    stamped = False
    try:
        if category == "concept":
            raw = _parse_yaml_text(text, section)
            if raw is not None and not isinstance(raw, dict):
                raise ModelError(f"{section}: concept top level must be a mapping")
            parsed = raw if isinstance(raw, dict) else {}
            if stamp_first:
                if not parsed.get("id"):
                    parsed["id"] = _stable_id(section)
                    stamped = True
                if parsed.get("order") is None:
                    parsed["order"] = _next_order(layout, section)
                    stamped = True
        elif category == "decisions":
            raw = _parse_yaml_text(text, section)
            parsed = _entries(raw, Path(section))
        else:  # material（存原文；序列化時正規化換行）
            parsed = text
    except ModelError as exc:
        sys.stderr.write(f"docspec: put rejected (no write): {exc}\n")
        return 1

    # ── 建 candidate leaf（目標分類換新內容，其餘沿用記錄現值）→ 結構驗證 ──
    concept, decisions, material = rec.concept, list(rec.decisions), rec.material
    has_material = rec.material is not None
    if category == "concept":
        concept = parsed
    elif category == "decisions":
        decisions = parsed
    else:
        material, has_material = parsed, True
    candidate = Leaf(section=section, dir=layout.section_dir(section), concept=concept,
                     decisions=decisions, history=list(rec.history), has_material=has_material,
                     has_develop=_store.work_develop(layout, section).is_file(),
                     has_history=bool(rec.history), material=material)
    errs = _structural_errors(schema, section, category, candidate, others)
    if errs:
        sys.stderr.write(f"docspec: put rejected — {len(errs)} structural error(s), the store record "
                         f"for {section}/{category} is left unchanged (no partial write):\n")
        for e in errs:
            sys.stderr.write(f"    ✗ {e}\n")
        return 1

    # ── 通過 → 套用到記錄、canonical dump 原子寫（staging 或正式）──
    if category == "concept":
        rec.concept = parsed
    elif category == "decisions":
        rec.decisions = parsed
    else:
        rec.material = parsed
    rec.kind = "leaf"

    if change is not None:
        chg._save_staging_article(change.dir, art_obj, schema)
    else:
        art_obj.revision += 1
        _store.save_article(layout, art_obj, schema)

    verb = "created" if not had else "updated"
    where = f" into change \"{change.id}\" staging" if change is not None else ""
    print(f"put: {verb} {section}/{category} in store{where} (validated: field check + "
          "duplicate-id + relation-target + enum)")
    if stamped:
        print(f"  stamped id: {parsed['id']}  order: {parsed['order']} (first write of concept)")
    if change is not None:
        print("  official store is byte-frozen (changes land at archive); "
              f"next: docspec render --change {change.id}  then  docspec change status {change.id}.")
    else:
        print("  next: docspec status / docspec check picks up staleness; render to project prose.")
    return 0


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec put", description=HELP)
    parser.add_argument("section", help="leaf section path (relative to corpus/)")
    parser.add_argument("category", choices=sorted(_CATEGORIES),
                        help="which artifact to write: concept | decisions | material")
    parser.add_argument("source", help="FILE with the new content, or - for stdin")
    parser.add_argument("--change", default=None, metavar="ID",
                        help="route the write into this active change's staging (required to "
                             "disambiguate when >1 active change targets the section)")
    args = parser.parse_args(argv)

    section = args.section.strip("/")
    if not section:
        sys.stderr.write("docspec: section path must not be empty\n")
        return 2
    problem = validate_section_path(section)
    if problem:
        sys.stderr.write(f'docspec: refusing to write "{section}": {problem}\n')
        return 2

    try:
        layout, config = bootstrap()
        schema = load_engine_schema(config)
    except BootstrapError as exc:
        return exc.exit_code

    try:
        text = _read_source(args.source)
    except FileNotFoundError:
        sys.stderr.write(f"docspec: source file not found: {args.source}\n")
        return 2

    # ── change-aware 路由（★P0）：target 節在某 active change → 寫進該單 staging、official 凍結 ──
    try:
        change = chg.routing_change_for(layout, section, explicit_id=args.change)
    except chg.RoutingAmbiguous as amb:
        sys.stderr.write(
            f"docspec: section \"{section}\" is targeted by {len(amb.candidates)} active changes "
            f"({', '.join(c.id for c in amb.candidates)}) — put refuses to guess. "
            "Re-run with --change <id> to name which staging to write into.\n")
        return 2
    except chg.ChangeError as exc:
        sys.stderr.write(f"docspec: {exc}\n")
        return 2

    # ★store-only：寫進 store 記錄（正式或 change 的 partial store staging），非散檔。
    return _put_store(layout, schema, args, section, text, change)
