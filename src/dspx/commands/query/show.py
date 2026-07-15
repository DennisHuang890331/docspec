"""docspec show <id> — payload 下鑽（正向內容）＋反向關係查詢（改動影響預覽）。

- 無旗標＝正向下鑽：回某 id/section 的內容，讓 agent 免開原始檔（省 token）。
  - decision → statement / rationale / rejected / status / supersede 連結
  - concept  → concept 一句話 / brief / must_cover / sources
  - history  → 結構（statement / retired-in / superseded-by）；散文 rationale 目前在 history.md
- 反向關係查詢（把既有跨文件真相圖反向 surface，`crossref.build_reverse_indices`）：
  - `show <section> --impact`＝改這節之前，跨全部文件誰會髒（stale-upstream / -inherited / -norm
    ／跨參考三類）。
  - `show <decision-id> --realized-by`＝跨全部文章、誰 realize 這條決策。
  - `show <section> --referenced-by`＝誰的散文錨指向這節（未 render 誠實回報、不假空集）。
"""

from __future__ import annotations

import argparse
import json
import sys

from dspx.commands._shared import BootstrapError, bootstrap, load_model
from dspx.engine.glossary import load_glossary

NAME = "show"
HELP = ("Drill down an id's payload (decision/concept/history) or query REVERSE relations "
        "(--impact / --realized-by / --referenced-by) — preview a change's cross-document blast radius")


def _read_history_md(section_dir, the_id: str) -> str | None:
    """撈 history.md 的 `## <id>` 段散文（乾淨 id：標題第一個 token＝id；讀到下個 ## 為止）。"""
    path = section_dir / "history.md"
    if not path.is_file():
        return None
    out: list[str] = []
    capturing = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            parts = line[3:].split()
            capturing = bool(parts) and parts[0] == the_id
            continue
        if capturing:
            out.append(line)
    text = "\n".join(out).strip()
    return text or None


def _find(leaves: list, the_id: str, layout=None) -> dict | None:
    # glossary term 下鑽：精瘦索引只投 canonical/bucket/code/aliases_forbidden；
    # 完整 record（含 definition/english）只在這裡按需回。
    if layout is not None:
        for t in load_glossary(layout):
            if str(t.get("id")) == the_id:
                return {"kind": "glossary", "canonical": t.get("canonical"),
                        "bucket": t.get("bucket"), "code": t.get("code"),
                        "english": t.get("english"),
                        "aliases_forbidden": t.get("aliases_forbidden"),
                        "definition": t.get("definition")}
    for leaf in leaves:
        c = leaf.concept or {}
        if str(c.get("id")) == the_id:
            return {"kind": "concept", "section": leaf.section, "title": c.get("title"),
                    "status": c.get("status"), "concept": c.get("concept"),
                    "brief": c.get("brief"), "must_cover": c.get("must_cover"),
                    "sources": c.get("sources"), "realizes": c.get("realizes"),
                    "governedBy": c.get("governed-by")}
        for e in leaf.decisions:
            if str(e.get("id")) == the_id:
                return {"kind": "decision", "section": leaf.section,
                        "decisionKind": e.get("kind"), "status": e.get("status"),
                        "statement": e.get("statement"), "rationale": e.get("rationale"),
                        "rejected": e.get("rejected"), "supersedes": e.get("supersedes"),
                        "supersededBy": e.get("superseded-by"), "decidedIn": e.get("decided-in"),
                        "trace": e.get("trace")}
        for e in leaf.history:
            if str(e.get("id")) == the_id:
                out = {"kind": "history", "section": leaf.section,
                       "historyKind": e.get("kind"), "status": e.get("status"),
                       "statement": e.get("statement"), "retiredIn": e.get("retired-in"),
                       "supersededBy": e.get("superseded-by")}
                if e.get("kind") == "section":
                    out["archive"] = e.get("archive")          # 整節退場：細節＝封存資料夾
                else:
                    out["rationale"] = _read_history_md(leaf.dir, the_id)  # 決策退場：撈 md 散文
                return out
    return None


def _find_section(leaves: list, layout, arg: str) -> dict | None:
    """section 路徑模式（id 查找 miss 後的第二種地址形狀）：回該節身份 payload。

    命中條件＝引數含 `/`，或指到既有非封存 corpus 節資料夾。leaf → conceptId/title/status
    （＝concept.status，非 sync 狀態）/order＋決策 id（statement 截 80 字）＋history id。"""
    section = arg.strip("/")
    if not section:
        return None
    section_dir = layout.section_dir(section)
    dir_hit = section_dir.is_dir() and not layout.is_archived_path(section_dir)
    if "/" not in arg and not dir_hit:
        return None
    for leaf in leaves:
        if leaf.section != section:
            continue
        c = leaf.concept or {}
        return {"kind": "section", "section": section,
                "conceptId": c.get("id"), "title": c.get("title"),
                "status": c.get("status"), "order": c.get("order"),
                "decisions": [{"id": e.get("id"), "status": e.get("status"),
                               "statement": (str(e.get("statement") or ""))[:80]}
                              for e in leaf.decisions],
                "history": [{"id": e.get("id"), "kind": e.get("kind"),
                             "status": e.get("status")} for e in leaf.history]}
    return None


# ── 定址統一（id 與節路徑自動判別；四個查詢一律兩種都吃、錯定址指路另一種）────────────

def _resolve_to_section(leaves: list, arg: str) -> str | None:
    """arg（節路徑 或 concept/decision/history id）→ 所屬 leaf section 路徑；找不到 → None。

    id 形式（`sec-`/`dec-`/`rm-` 前綴或匹配某 id）與節路徑形式（含 `/` 或匹配 leaf.section）皆吃：
    任一 id 皆唯一對應一個 leaf，故 `--impact`/`--referenced-by` 不再只認完整節路徑。"""
    a = arg.strip("/")
    if not a:
        return None
    for lf in leaves:                       # id 形式：concept / decision / history id
        c = lf.concept or {}
        if str(c.get("id")) == a:
            return lf.section
        if any(str(e.get("id")) == a for e in lf.decisions):
            return lf.section
        if any(str(e.get("id")) == a for e in lf.history):
            return lf.section
    for lf in leaves:                       # 節路徑形式：直接匹配 leaf.section
        if lf.section == a:
            return lf.section
    return None


def _addr_hint(leaves: list, arg: str) -> str:
    """錯定址時的指路訊息（指向另一種定址形式）。"""
    a = arg.strip("/")
    for lf in leaves:
        c = lf.concept or {}
        if str(c.get("id")) == a:
            return (f"\"{a}\" is the concept id of section {lf.section} — pass either form.")
        if any(str(e.get("id")) == a for e in lf.decisions):
            return (f"\"{a}\" is a decision id owned by {lf.section} — try "
                    f"`docspec show {a} --realized-by`, or address the section \"{lf.section}\".")
    return ("give a leaf section path (has '/', e.g. guide/intro) or a concept id "
            "(docspec status shows sections; docspec show <id> shows an id's payload).")


# ── 分類視圖（整篇/子樹橫看某一分類）──────────────────────────────────────────

def _scope_leaves(leaves: list, arg: str) -> list | None:
    """arg → 該 article 或該子樹的 leaves（依 section 排序）；無命中 → None。
    arg 是 article 名（== lf.article）或 section 子樹前綴（== lf.section 或其前綴）皆吃。"""
    a = arg.strip("/")
    if not a:
        return None
    scoped = [lf for lf in leaves
              if lf.article == a or lf.section == a or lf.section.startswith(a + "/")]
    if not scoped:
        return None
    return sorted(scoped, key=lambda lf: lf.section)


def _statement_head(text: object, width: int = 80) -> str:
    """裁決/歷史 statement 截行（單行、去換行、截 width 字）。"""
    s = " ".join(str(text or "").split())
    return s[:width]


def _decisions_view(leaves: list, all_status: bool) -> dict:
    """整篇每節裁決（path/id/kind/status/statement）。預設只 active；--all-status 含死決策
    （superseded/deprecated，就地留在 decisions.yaml）＝取代已刪的 retire 報告。"""
    from dspx.engine.model import ACTIVE_DECISION_STATUSES
    sections: list[dict] = []
    total = 0
    dead = 0
    for lf in leaves:
        rulings: list[dict] = []
        for e in lf.decisions:
            if not e.get("id"):
                continue
            status = str(e.get("status"))
            is_dead = status not in ACTIVE_DECISION_STATUSES
            if is_dead and not all_status:
                continue
            rulings.append({"id": e.get("id"), "kind": e.get("kind"), "status": status,
                            "statement": _statement_head(e.get("statement")),
                            "dead": is_dead})
            total += 1
            if is_dead:
                dead += 1
        if rulings:
            sections.append({"section": lf.section, "decisions": rulings})
    return {"kind": "decisions", "allStatus": all_status, "sections": sections,
            "total": total, "dead": dead}


def _print_decisions_view(payload: dict) -> None:
    tag = " (all statuses, incl. dead)" if payload["allStatus"] else " (active only)"
    print(f"decisions across {len(payload['sections'])} section(s){tag} — "
          f"{payload['total']} ruling(s), {payload['dead']} dead:")
    if not payload["sections"]:
        print("  (no rulings)")
    for s in payload["sections"]:
        print(f"\n  {s['section']}:")
        for d in s["decisions"]:
            mark = " ⚰ DEAD" if d["dead"] else ""
            print(f"    [{d['id']}] {d.get('kind') or '—'} · {d['status']}{mark}  {d['statement']}")


def _brief_differential(concept: dict) -> dict:
    """該節自己填的 brief 欄（差異制：只列本節寫出的欄，省略＝繼承）。非 dict → {}。"""
    brief = (concept or {}).get("brief")
    if not isinstance(brief, dict):
        return {}
    return {k: v for k, v in brief.items() if v not in (None, "", [], {})}


def _concepts_view(leaves: list) -> dict:
    sections: list[dict] = []
    for lf in leaves:
        c = lf.concept or {}
        sections.append({
            "section": lf.section, "id": c.get("id"), "title": c.get("title"),
            "concept": c.get("concept"),
            "briefDifferential": _brief_differential(c)})
    return {"kind": "concepts", "sections": sections}


def _print_concepts_view(payload: dict) -> None:
    print(f"concepts across {len(payload['sections'])} section(s) "
          "(one-liner + differential brief — only fields this section overrides):")
    for s in payload["sections"]:
        title = f" — {s['title']}" if s.get("title") else ""
        print(f"\n  {s['section']}{title}  [{s.get('id') or '—'}]")
        print(f"    concept: {s.get('concept') or '—'}")
        bd = s.get("briefDifferential") or {}
        if bd:
            fields = "  ".join(f"{k}={v}" for k, v in bd.items())
            print(f"    brief (differential): {fields}")
        else:
            print("    brief (differential): — (fully inherited)")


_MATERIAL_HEADING_RE = None


def _material_headings(material: str | None) -> list[dict]:
    """material.md 的標題索引：`## <類型>: <標題> {#m-<錨>}`（錨可選）。"""
    import re
    global _MATERIAL_HEADING_RE
    if _MATERIAL_HEADING_RE is None:
        _MATERIAL_HEADING_RE = re.compile(
            r"^##\s+(?P<type>[^:：]+)[:：]\s*(?P<title>.*?)"
            r"(?:\s*\{#(?P<anchor>[^}]+)\})?\s*$")
    out: list[dict] = []
    for line in (material or "").splitlines():
        m = _MATERIAL_HEADING_RE.match(line)
        if m:
            out.append({"type": m.group("type").strip(),
                        "title": m.group("title").strip(),
                        "anchor": m.group("anchor")})
    return out


def _material_view(leaves: list) -> dict:
    sections: list[dict] = []
    for lf in leaves:
        if not lf.has_material:
            continue
        sections.append({"section": lf.section,
                         "headings": _material_headings(lf.material)})
    return {"kind": "material", "sections": sections}


def _print_material_view(payload: dict) -> None:
    print(f"material across {len(payload['sections'])} section(s) with material:")
    if not payload["sections"]:
        print("  (no section carries material)")
    for s in payload["sections"]:
        print(f"\n  {s['section']}:")
        if not s["headings"]:
            print("    (material present, but no `## <type>: <title>` headings)")
        for h in s["headings"]:
            anchor = f"  {{#{h['anchor']}}}" if h.get("anchor") else ""
            print(f"    · {h['type']}: {h['title']}{anchor}")


# ── 反向關係查詢（改動影響預覽；反向索引＝既有正向邊的反向鄰接表，同源不漂）──────────

def _active_decisions(leaf) -> list[dict]:
    """本節 active（proposed/accepted）決策條目。"""
    from dspx.engine.model import ACTIVE_DECISION_STATUSES
    return [e for e in leaf.decisions
            if str(e.get("status")) in ACTIVE_DECISION_STATUSES and e.get("id")]


def _unrendered_note(unrendered: list[str], what: str) -> str | None:
    """未 render 文章的誠實提示（跨參考類算不出＝明確回報、非空集假裝無引用）。"""
    if not unrendered:
        return None
    return (f"note: {len(unrendered)} article(s) not yet rendered "
            f"({', '.join(unrendered)}) — {what} from them cannot be determined; "
            "run docspec render <article>")


def _impact_payload(leaves, layout, section: str) -> dict | None:
    """`show <section> --impact`：改這節之前跨全部文件的受影響節（反向 staleness 邊）。"""
    from dspx.engine.crossref import build_reverse_indices

    by_section = {lf.section: lf for lf in leaves}
    leaf = by_section.get(section)
    if leaf is None:
        return None
    ri = build_reverse_indices(leaves, layout)

    active = _active_decisions(leaf)
    active_ids = [str(e.get("id")) for e in active]
    has_active_norm = any(e.get("kind") == "normative" for e in active)

    # ① reverse_realizes[本節 active 決策] → stale-upstream（realizer 們，跨全部文章）
    upstream: list[dict] = []
    seen_up: set = set()
    for did in active_ids:
        for lf in ri.reverse_realizes.get(did, []):
            key = (lf.section, did)
            if key in seen_up:
                continue
            seen_up.add(key)
            upstream.append({"section": lf.section, "viaDecision": did})

    # ② descendants(本節) → stale-inherited（brief 繼承）；有 active normative → 同集另標 stale-norm
    desc = [lf.section for lf in ri.descendants.get(section, [])]
    inherited = sorted(desc)
    norm = sorted(desc) if has_active_norm else []

    # ③ reverse_anchor[本節 concept.id ∪ 本節 active 決策 id] → 跨參考（§N 會變）
    cid = leaf.concept.get("id") if leaf.concept else None
    ref_ids = ([str(cid)] if cid else []) + active_ids
    xref: list[dict] = []
    seen_x: set = set()
    for tid in ref_ids:
        for (art, sec) in ri.reverse_anchor.get(tid, []):
            key = (art, sec, tid)
            if key in seen_x:
                continue
            seen_x.add(key)
            xref.append({"article": art, "section": sec, "viaId": tid})

    return {"kind": "impact", "section": section,
            "staleUpstream": upstream, "staleInherited": inherited,
            "staleNorm": norm, "crossReference": xref,
            "unrenderedArticles": ri.unrendered_articles}


def _print_impact(payload: dict) -> None:
    up, inh, norm, xref = (payload["staleUpstream"], payload["staleInherited"],
                           payload["staleNorm"], payload["crossReference"])
    empty = not (up or inh or norm or xref)
    print(f"impact of {payload['section']} "
          "(cross-document blast radius BEFORE you change it):")
    if empty:
        print("  no cross-section impact — nothing realizes its decisions, it has no descendants, "
              "and no prose anchor points at it.")
    else:
        if up:
            print("\n  stale-upstream (sections realizing this section's active decisions):")
            for r in up:
                print(f"    {r['section']}  (realizes {r['viaDecision']})")
        if inh:
            print("\n  stale-inherited (descendants inheriting its brief/concept):")
            for s in inh:
                print(f"    {s}")
        if norm:
            print("\n  stale-norm (descendants bound by its active normative rulings):")
            for s in norm:
                print(f"    {s}")
        if xref:
            print("\n  cross-reference (prose anchors pointing here — their §N shifts):")
            for r in xref:
                print(f"    docs/{r['article']}/_latest.md § {r['section']}  (→ {r['viaId']})")
    note = _unrendered_note(payload["unrenderedArticles"], "prose-anchor impact")
    if note:
        print(f"\n  {note}")
    print("\n  (a change to a GLOBAL style carrier — writing-guide / glossary / purpose — is not "
          "listed per-section; it restyles every section.)")


def _realized_by_payload(leaves, decision_id: str) -> dict:
    """`show <decision-id> --realized-by`：跨全部文章、誰 realize 這條決策。"""
    from dspx.engine.crossref import build_reverse_indices
    from dspx.engine.model import decision_index

    ri = build_reverse_indices(leaves)
    realizers = sorted(lf.section for lf in ri.reverse_realizes.get(decision_id, []))
    dindex = decision_index(leaves)
    rec = dindex.get(decision_id)
    defined_at = rec["section"] if rec else None
    # 定址統一：decision id miss 時，看是不是 concept id（concept 也可被 realize）
    if defined_at is None:
        for lf in leaves:
            if lf.concept and str(lf.concept.get("id")) == decision_id:
                defined_at = lf.section
                break
    return {"kind": "realized-by", "decision": decision_id,
            "definedAt": defined_at,
            "realizedBy": realizers}


def _print_realized_by(payload: dict) -> None:
    realizers = payload["realizedBy"]
    where = f" (defined at {payload['definedAt']})" if payload["definedAt"] else ""
    if realizers:
        print(f"{payload['decision']}{where} is realized by {len(realizers)} section(s) "
              "across all articles:")
        for s in realizers:
            print(f"  {s}")
    elif payload["definedAt"]:
        print(f"{payload['decision']}{where}: no section realizes it yet "
              "(not-yet-consumed — no inbound realizes edge, not unused).")
    else:
        print(f"{payload['decision']}: not a known decision id, and no section realizes it.")


def _referenced_by_payload(leaves, layout, section: str) -> dict | None:
    """`show <section> --referenced-by`：誰的散文錨指向這節（concept.id ∪ 本節決策 id）。"""
    from dspx.engine.crossref import build_reverse_indices

    by_section = {lf.section: lf for lf in leaves}
    leaf = by_section.get(section)
    if leaf is None:
        return None
    ri = build_reverse_indices(leaves, layout)
    cid = leaf.concept.get("id") if leaf.concept else None
    ref_ids = ([str(cid)] if cid else []) + [str(e.get("id")) for e in leaf.decisions if e.get("id")]
    refs: list[dict] = []
    seen: set = set()
    for tid in ref_ids:
        for (art, sec) in ri.reverse_anchor.get(tid, []):
            key = (art, sec, tid)
            if key in seen:
                continue
            seen.add(key)
            refs.append({"article": art, "section": sec, "viaId": tid})
    return {"kind": "referenced-by", "section": section, "referencedBy": refs,
            "unrenderedArticles": ri.unrendered_articles}


def _print_referenced_by(payload: dict) -> None:
    refs = payload["referencedBy"]
    note = _unrendered_note(payload["unrenderedArticles"], "references")
    if refs:
        print(f"{payload['section']} is referenced by {len(refs)} prose cross-reference(s):")
        for r in refs:
            print(f"  docs/{r['article']}/_latest.md § {r['section']}  (→ {r['viaId']})")
        if note:
            print(f"  {note}")
    elif note:
        # 未 render＝算不出跨參考：明確回報「需先 render」，MUST NOT 以空集假裝無引用
        print(f"{payload['section']}: {note}")
    else:
        print(f"{payload['section']}: no prose cross-reference points at it.")


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec show", description=HELP)
    parser.add_argument("id", help="a section path OR an id (concept/decision/retirement) — "
                                   "every view auto-detects which and accepts both forms")
    parser.add_argument("--json", action="store_true", dest="as_json", help="output as JSON")
    view = parser.add_mutually_exclusive_group()
    view.add_argument("--impact", action="store_true",
                      help="reverse view: every section across ALL documents a change to the "
                           "section (given by path or its concept id) would make stale "
                           "(upstream/inherited/norm/cross-reference)")
    view.add_argument("--realized-by", action="store_true", dest="realized_by",
                      help="reverse view: every section, across all articles, whose realizes "
                           "includes the decision id (or the section given by path)")
    view.add_argument("--referenced-by", action="store_true", dest="referenced_by",
                      help="reverse view: every section whose prose anchor points at the section "
                           "(given by path or its concept id)")
    view.add_argument("--decisions", action="store_true",
                      help="classification view: every section's rulings across an article (or a "
                           "section subtree) — path/id/kind/status/statement")
    view.add_argument("--concepts", action="store_true",
                      help="classification view: every section's one-line concept + differential brief")
    view.add_argument("--material", action="store_true",
                      help="classification view: which sections carry material + each material's title index")
    parser.add_argument("--all-status", action="store_true", dest="all_status",
                        help="with --decisions: also include dead rulings (superseded/deprecated) "
                             "— the in-place index that replaces the old retire report")
    args = parser.parse_args(argv)

    try:
        layout, _config = bootstrap()
        leaves = load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code

    # ── 分類視圖（整篇/子樹橫看某一分類；crossdoc 的反向視圖的正向補集）────────────────
    if args.decisions or args.concepts or args.material:
        scoped = _scope_leaves(leaves, args.id)
        if scoped is None:
            sys.stderr.write(
                f"docspec: no sections found for \"{args.id}\" (give an article name or a section "
                "subtree path; docspec status lists articles/sections).\n")
            return 1
        if args.decisions:
            payload = _decisions_view(scoped, args.all_status)
            printer = _print_decisions_view
        elif args.concepts:
            payload = _concepts_view(scoped)
            printer = _print_concepts_view
        else:
            payload = _material_view(scoped)
            printer = _print_material_view
        if args.as_json:
            print(json.dumps({"id": args.id, **payload}, ensure_ascii=False, indent=2))
        else:
            printer(payload)
        return 0

    # ── 反向關係查詢（定址統一：id 與節路徑自動判別、兩種都吃）────────────────────
    if args.impact:
        section = _resolve_to_section(leaves, args.id)
        payload = _impact_payload(leaves, layout, section) if section else None
        if payload is None:
            sys.stderr.write(f"docspec: --impact could not resolve \"{args.id}\" to a leaf section. "
                             + _addr_hint(leaves, args.id) + "\n")
            return 1
        if args.as_json:
            print(json.dumps({"id": args.id, **payload}, ensure_ascii=False, indent=2))
        else:
            _print_impact(payload)
        return 0
    if args.realized_by:
        # decision/concept id 直查；節路徑形式 → 解析成該節 concept.id 當查詢鍵
        query = args.id.strip("/")
        if "/" in args.id:
            section = _resolve_to_section(leaves, args.id)
            if section is None:
                sys.stderr.write(f"docspec: --realized-by could not resolve \"{args.id}\". "
                                 + _addr_hint(leaves, args.id) + "\n")
                return 1
            lf = next((l for l in leaves if l.section == section), None)
            cid = str(lf.concept.get("id")) if lf and lf.concept and lf.concept.get("id") else None
            if cid is None:
                sys.stderr.write(f"docspec: section \"{section}\" has no concept id to query "
                                 "realizers for (crystallize its concept first).\n")
                return 1
            query = cid
        payload = _realized_by_payload(leaves, query)
        if args.as_json:
            print(json.dumps({"id": args.id, **payload}, ensure_ascii=False, indent=2))
        else:
            _print_realized_by(payload)
        return 0
    if args.referenced_by:
        section = _resolve_to_section(leaves, args.id)
        payload = _referenced_by_payload(leaves, layout, section) if section else None
        if payload is None:
            sys.stderr.write(f"docspec: --referenced-by could not resolve \"{args.id}\" to a leaf "
                             "section. " + _addr_hint(leaves, args.id) + "\n")
            return 1
        if args.as_json:
            print(json.dumps({"id": args.id, **payload}, ensure_ascii=False, indent=2))
        else:
            _print_referenced_by(payload)
        return 0

    # ── 正向下鑽（無旗標）─────────────────────────────────────────────────
    found = _find(leaves, args.id, layout)
    if found is None:
        found = _find_section(leaves, layout, args.id)
    if found is None:
        sys.stderr.write(
            f"docspec: id or section \"{args.id}\" not found (use docspec status to see sections; "
            "docspec show <id> --realized-by / <section> --referenced-by / --impact for "
            "back-references)\n")
        return 1

    payload = {"id": args.id, **found}
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    where = f" @ {found['section']}" if found.get("section") else ""
    print(f"id: {args.id} ({found['kind']}{where})")
    for k, v in payload.items():
        if k in ("id", "kind", "section") or v in (None, [], {}):
            continue
        print(f"  {k}: {v}")
    return 0
