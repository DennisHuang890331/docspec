"""docspec instructions <skill> <section> — aperture projection (feed the right files to the right skill)."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys

from dspx.engine.aperture import ApertureError, project
from dspx.commands._shared import BootstrapError, bootstrap, load_engine_schema, load_model


def _fill_template(template: str | None, section: str, layout) -> str | None:
    """Fill in {id}/{title}/{order} in the concept/decisions template — used directly by the agent at crystallization."""
    if not template:
        return template
    sid = "sec-" + hashlib.sha1(section.encode("utf-8")).hexdigest()[:8]
    title = section.rsplit("/", 1)[-1]
    parent = layout.section_dir(section).parent
    order = 1
    if parent.is_dir():
        order = 1 + sum(
            1 for s in parent.iterdir()
            if s.is_dir() and s != layout.section_dir(section)
            and ((s / "develop.md").is_file() or (s / "concept.yaml").is_file())
        )
    for k, v in {"id": sid, "title": title, "order": str(order)}.items():
        template = template.replace("{" + k + "}", v)
    return template

NAME = "instructions"
HELP = "aperture projection: the readable files + writing guidance for <skill> at <section>"


def _contract_lines(f: dict, indent: str = "  ") -> list[str]:
    """一欄一行的契約投影：name type required/optional [= enum 值] [→ relation]；巢狀遞迴。"""
    req = "required" if f.get("required") else "optional"
    bits = [f"{indent}{f['name']:<14} {f['type']:<9} {req}"]
    if f.get("values"):
        bits.append(f"= {' | '.join(map(str, f['values']))}")
    if f.get("relation"):
        bits.append(f"→ {f['relation']}")
    if f.get("type") == "object":
        bits.append("(closed)" if f.get("closed") else "(open)")
    lines = ["  ".join(bits)]
    for sub in f.get("fields", []):
        lines.extend(_contract_lines(sub, indent + "  "))
    return lines


def _realized_mark(r: dict) -> str:
    """前景化一個 realized 決策的退場狀態＋接替（FG-1 語義半）。活決策回空字串。
    退場（kind=history／status superseded|deprecated|retired）時提示重指活接替，避免
    draft/factcheck 只看 aperture 就把散文錨回死真相。"""
    status = r.get("status")
    retired = r.get("kind") == "history"
    if not retired and status not in ("superseded", "deprecated", "retired"):
        return ""
    label = "RETIRED (now in history)" if retired else str(status).upper()
    succ = r.get("superseded_by")   # terminal LIVE successor (chain-resolved) or None
    if succ:
        ss = r.get("successor_statement")
        return f"  ⚠ {label} → superseded by {succ}" + (f": {ss}" if ss else "")
    return f"  ⚠ {label} (no live successor in the supersede chain — repoint realizes to the live truth or drop the edge)"


# per-action 驗收判準的一行摘要（instructions active-change 投影用）
_ACTION_CRITERION = {
    "create": "ready + synced (crystallized + prose written)",
    "revise": "synced (prose rewritten against the changed source)",
    "redraft": "synced (prose fully rewritten)",
    "align": "stale-inherited/style cleared, or render --ack",
    "review": "acked with a reason",
    "retire": "retirement transaction completed in staging",
    "move": "mv executed at archive + check green",
}

# change target action → apply 模式（change 內驅動；move/retire 是交易、不走 apply prose）
_ACTION_MODE = {
    "create": "rewrite", "revise": "rewrite", "redraft": "rewrite",
    "align": "align", "review": "align",
}


def _sync_mode_verb(sync: str) -> tuple[str, str] | None:
    """一節的 staleness 型別 → apply 模式 + 對應 render/ack verb（change 外驅動）。
    synced / uncrystallized 等無工作態回 None。"""
    if sync in ("unwritten", "stale-own", "stale-upstream"):
        return "rewrite", "docspec render <article>  (blind-render the section from its aperture)"
    if sync == "stale-norm":
        return "align", ("docspec render <article>  (a sentence violated the changed ruling) — else "
                         "docspec render <article> --ack <section>  (re-checked; prose conforms)")
    if sync in ("stale-inherited", "stale-style"):
        return "align", ("docspec render <article>  (you re-tuned the prose) — else "
                         "docspec render <article> --ack <section>  (reviewed; no change needed)")
    if sync == "drifted":
        return "align", "reconcile the hand-edit, then docspec render <article>"
    return None


def _apply_mode(layout, schema, leaves, section: str) -> dict | None:
    """instructions apply <section> 的模式投影：change 內由 target action 選、change 外由
    staleness 型別選（同一套路由住 apply 內部，不外漏尾表）。回 {mode, verb, reason} 或 None。"""
    from dspx.engine import change as chg
    from dspx.commands.query.status import compute_sync

    by_section = {lf.section: lf for lf in leaves}
    leaf = by_section.get(section)

    # change 內：target action 定模式（多單命中取第一個有 apply 模式的 action）
    concept_id = str(leaf.concept_id) if leaf is not None and leaf.concept_id else None
    for change, t in chg.changes_hitting_section(layout, section, concept_id, leaves):
        mode = _ACTION_MODE.get(t.action)
        if mode:
            verb = (_sync_mode_verb("stale-own") if mode == "rewrite"
                    else _sync_mode_verb("stale-inherited"))
            return {"mode": mode, "verb": verb[1] if verb else "",
                    "reason": f"change {change.id} action={t.action}"}

    # change 外：staleness 型別定模式
    if leaf is None:
        return None
    from dspx.engine.model import decision_index
    from dspx.engine.render import ledger_needs_migration, read_ledger
    ledger = read_ledger(layout, leaf.article)
    recorded = ledger.get(section)
    deliverable_missing = bool(ledger) and not layout.docs_latest(leaf.article).is_file()
    needs_migration = ledger_needs_migration(layout, leaf.article)
    dindex = decision_index(leaves)
    sync, _ = compute_sync(layout, leaf, recorded, by_section, dindex,
                           deliverable_missing=deliverable_missing,
                           needs_migration=needs_migration)
    mv = _sync_mode_verb(sync)
    if mv is None:
        return {"mode": "—", "verb": "", "reason": f"{sync} (no apply work needed)"}
    return {"mode": mv[0], "verb": mv[1], "reason": sync}


def _load_authoring(schema) -> dict:
    """讀 schema.yaml 的 authoring 權威塊（頂層鍵、非 artifact 契約，故不進 Schema dataclass；
    apply 投影它＝規則住 schema、被投影，skill 只錨不重抄）。讀不到＝回空 dict（不炸）。"""
    import yaml
    try:
        data = yaml.safe_load((schema.root / "schema.yaml").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — 投影永不因權威塊缺損而爆
        return {}
    auth = data.get("authoring") if isinstance(data, dict) else None
    return auth if isinstance(auth, dict) else {}


def _print_authoring(auth: dict) -> None:
    """apply 投影三區塊：寫作原則（含 zero-inference 雙載）／── Verdict verbs ──／── Dispatch
    exclusions ──。skill body 不再重抄這些長文；照這裡逐字，別憑記憶重推。"""
    principles = auth.get("principles") or []
    zero = auth.get("zero_inference")
    if principles or zero:
        print("── Writing principles ── (fold into every leaf; TECHNICAL/EXPOSITORY defaults — the "
              "active writing-guide profile OVERRIDES per genre, follow it, never apply these blindly)")
        for p in principles:
            print(f"  • {p}")
        if zero:
            print(f"  IMPORTANT — zero-inference: {str(zero).strip()}")
        print()

    vv = auth.get("verdict_verbs") or {}
    if vv:
        print("── Verdict verbs ── (clear a staleness verdict with the MATCHING verb; give a real "
              "--reason — never fabricate an edit or a perturb-render-revert dance)")
        if vv.get("intro"):
            print("  " + str(vv["intro"]).strip().replace("\n", "\n  "))
        for w in vv.get("whitelist") or []:
            print(f"  • {w}")
        env = vv.get("brief_envelope") or []
        if env:
            print("  Brief-envelope handling (which brief field moved decides ack-or-rewrite):")
            for e in env:
                print(f"    • {e}")
        print()

    de = auth.get("dispatch_exclusions") or {}
    if de:
        print("── Dispatch exclusions ── (copy VERBATIM into every semantic subagent brief; never "
              "re-derive which work is mechanical from memory)")
        if de.get("intro"):
            print("  " + str(de["intro"]).strip().replace("\n", "\n  "))
        for item in de.get("items") or []:
            print(f"  • {item}")
        print()


def _change_context(layout, leaves, section: str) -> list[dict]:
    """本節命中的 active change context（多單全列；workflow-introspection 5.1）。"""
    from dspx.engine import change as chg
    concept_id = None
    for lf in leaves:
        if lf.section == section and lf.concept_id:
            concept_id = str(lf.concept_id)
            break
    out: list[dict] = []
    for change, t in chg.changes_hitting_section(layout, section, concept_id, leaves):
        out.append({"id": change.id, "why": change.why, "action": t.action,
                    "acceptance": _ACTION_CRITERION.get(t.action, t.action)})
    return out


def _print_change_context(layout, leaves, section: str) -> None:
    ctx = _change_context(layout, leaves, section)
    if not ctx:
        return
    print("── Active change context (this section is enlisted; obey the action, acceptance is DERIVED) ──")
    for c in ctx:
        why = f"｜why: {c['why']}" if c["why"] else ""
        print(f"  {c['id']}{why}｜action={c['action']}｜acceptance＝{c['acceptance']}")
    print()


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec instructions", description=HELP)
    parser.add_argument("skill", help="develop / apply / factcheck / publish / release")
    parser.add_argument("section", help="leaf-section path (relative to corpus/)")
    parser.add_argument("--json", action="store_true", dest="as_json", help="output as JSON")
    args = parser.parse_args(argv)

    try:
        layout, config = bootstrap()
        schema = load_engine_schema(config)
        leaves = load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code

    # develop-only (not-yet-crystallized) sections must also project — develop needs the concept/decisions
    # templates at crystallization. ★store-only：develop.md 住 work/、尚無 store 記錄 → 建 concept=None 樁 Leaf。
    if not any(lf.section == args.section for lf in leaves):
        from dspx.engine import store as _store
        if _store.work_develop(layout, args.section).is_file():
            from dspx.engine.model import Leaf
            leaves = leaves + [Leaf(section=args.section,
                                    dir=layout.section_dir(args.section),
                                    concept=None, has_develop=True)]

    try:
        proj = project(layout, schema, args.skill, args.section, leaves, config)
    except ApertureError as exc:
        sys.stderr.write(f"docspec: {exc}\n")
        return 1

    # Fill in {id}/{title}/{order} in the writes templates (at crystallization the agent just fills in the content)
    # + attach the "required-fields list" so the agent knows the full definition (2.4)
    from dspx.engine.schema import field_contract, required_field_names, yaml_skeleton
    for w in proj.writes:
        w["template"] = _fill_template(w.get("template"), args.section, layout)
        art = schema.by_id(w.get("id", ""))
        w["requiredFields"] = required_field_names(art.schema) if art and art.schema else []
        w["fieldContract"] = field_contract(art.schema) if art and art.schema else []
        w["entriesContainer"] = bool(art.entries) if art else False
        w["closed"] = bool(art.closed) if art else False
        w["yamlSkeleton"] = yaml_skeleton(art) if art else None

    apply_mode = (_apply_mode(layout, schema, leaves, args.section)
                  if args.skill == "apply" else None)
    apply_authoring = _load_authoring(schema) if args.skill == "apply" else None

    if args.as_json:
        print(json.dumps({
            "skill": proj.skill,
            "section": proj.section,
            "applyMode": apply_mode,
            "authoring": apply_authoring,
            "activeChanges": _change_context(layout, leaves, args.section),
            "reads": proj.reads,
            "writes": proj.writes,
            "parentBriefs": proj.parent_briefs,
            "ancestorNormative": proj.ancestor_normative,
            "realized": proj.realized,
            "writingGuide": proj.writing_guide,
            "glossary": proj.glossary,
            "forest": proj.forest,
            "roadmap": proj.roadmap,
            "projectPurpose": proj.project_purpose,
            "imageAssets": proj.image_assets,
            "documentMap": proj.document_map,
            "coverageContract": proj.coverage_contract,
            "coherenceContract": proj.coherence_contract,
        }, ensure_ascii=False, indent=2))
        return 0

    print(f"aperture projection: skill={proj.skill}  section={proj.section}\n")

    if apply_mode is not None:
        print(f"── apply mode: {apply_mode['mode']}  ({apply_mode['reason']}) ──")
        if apply_mode["verb"]:
            print(f"   clear-with: {apply_mode['verb']}")
        print()

    if apply_authoring:
        _print_authoring(apply_authoring)

    _print_change_context(layout, leaves, args.section)

    if proj.project_purpose:
        print(f"Project goal: {proj.project_purpose}\n")

    # 風格權威（writing guide）印在大宗逐節內容之前：edit 級投影可達 ~100KB、消費端可能截尾——
    # 印在最後會讓 naive editor 根本沒看到它。刻意只調順序、不做任何截斷/預算機制（非目標）。
    if proj.writing_guide:
        print("── Writing guide (one shared copy for the whole document; coherence comes from it, not from reading other sections) ──")
        print(proj.writing_guide)
        print()

    if proj.forest is not None:
        f = proj.forest
        print("── Forest map (this document's place in the forest / who governs it / who it parallels; set governed-by against this) ──")
        print("   (backstage — wire structure with these, but NEVER write forest/governed-by/Tier-N/L2a/fan-in into the deliverable; name the document in domain language)")
        for d in f.get("documents", []):
            note = "" if d.get("rootCrystallized", True) else "  (root not yet crystallized)"
            print(f"  [{d['article']}] {d.get('oneLiner') or ''}{note}")
            for a in d.get("anchors", []):
                print(f"    anchor: {a['id']} — {a.get('title') or ''}  ({a['section']})")
        for h in f.get("hierarchy", []):
            warn = "  ⚠ governs cycle — `docspec check` will fail" if h.get("cycle") else ""
            print(f"  {h['childDoc']} → {h['parentDoc']}{warn}")
        for pair in f.get("parallel", []):
            print(f"  {pair[0]} ∥ {pair[1]}")
        print("  (full concept catalogue of a document: docspec show <article> --concepts --json)")
        print()

    if proj.roadmap is not None:
        print("── Backlog (roadmap): planned-but-not-done work for this document + the forest (check before starting) ──")
        if not proj.roadmap:
            print("  (no backlog)")
        else:
            unblocked = [e for e in proj.roadmap if e.get("unblocked")]
            blocked = [e for e in proj.roadmap if e.get("blocked")]
            accounted = {id(e) for e in unblocked} | {id(e) for e in blocked}
            other = [e for e in proj.roadmap if id(e) not in accounted]

            def _r(e: dict, suffix: str = "") -> None:
                print(f"  [{e.get('kind')}] {e.get('id')}  {e.get('title') or ''}{suffix}")

            if unblocked:
                print("  Unblocked:")
                for e in unblocked:
                    _r(e)
            if blocked:
                print("  Blocked-by:")
                for e in blocked:
                    _r(e, f"  ← waiting on: {', '.join(e.get('blocking-deps') or [])}")
            if other:
                print("  Other backlog:")
                for e in other:
                    _r(e)
        print()

    if proj.document_map:
        print("── Document map (the whole article's sections in order — frame THIS section's role in the whole; do NOT read/name siblings' prose) ──")
        for n in proj.document_map:
            if n.get("kind") == "group":
                # 分組節點：印 group.yaml 標題（同 render 交付物的章標題）、無 role、
                # 不印 "◀ you are here"（group 不可能是本節）。
                print(f"  [{n.get('order')}] {n.get('section')}/  —  [group] {n.get('title') or ''}")
                continue
            marker = " ◀ you are here" if n.get("section") == proj.section else ""
            print(f"  [{n.get('order')}] {n.get('section')}  —  {n.get('role') or ''}{marker}")
        print()

    if proj.image_assets:
        print("── Image assets (place ONLY these; reference as ![caption](<ref>) — never invent a path) ──")
        for ref in proj.image_assets:
            print(f"  {ref}")
        print()

    if proj.parent_briefs:
        print("── Parent-chain brief ──")
        print("   (backstage — obey these inherited constraints; NEVER narrate them as prose"
              " e.g. 「本節約束下游…」)")
        for pb in proj.parent_briefs:
            print(f"  [{pb['section']}] {pb.get('concept') or ''}")
            if pb.get("brief"):
                print(f"    brief: {pb['brief']}")
        print()

    print("── Readable (within the aperture; this is all you can see) ──")
    print("   (the concept's `brief` — breadth/depth/forbidden — and `sources` are constraints/"
          "provenance you OBEY, NOT content to recite: never write 「本節規範…／本節不寫…」 or a rote"
          " per-section 「設計依據:…」 tag; open on the payload and cite a standard inline only where the"
          " substance needs it. material.md / decisions here ARE your source content.)")
    if not proj.reads:
        print("  (none — this section has no readable content yet)")
    for art_id, content in proj.reads.items():
        print(f"\n[{art_id}]\n{content}")
    print()

    if proj.coverage_contract:
        cc = proj.coverage_contract
        print("── Coverage contract (this section's completeness + form contract — rule each item entailed/unsupported; flag a rendered form that fights the declared layout) ──")
        print("   (backstage completeness check — satisfy each item in the substance; do NOT write a"
              " 「可檢核性:…」 / verification section into the deliverable)")
        if cc.get("layout") or cc.get("kind"):
            print(f"  form: layout={cc.get('layout') or '—'}  kind={cc.get('kind') or '—'}")
        for item in cc.get("must_cover", []):
            print(f"  must cover: {item}")
        print()

    if proj.coherence_contract:
        ch = proj.coherence_contract
        print("── Coherence contract (pairs that MUST stay semantically consistent — rule each coherent/contradictory vs the rendered prose, and own-brief vs the ancestor briefs above; the hash ledger CANNOT see a field that should have changed but didn't, so raise a non-blocking `audit` finding on any contradiction) ──")
        print("   (backstage consistency check — these pairs are checked, not written: never narrate"
              " them as 「本節規範…／本節約束下游…」 prose)")
        if ch.get("title"):
            print(f"  title ↔ prose: \"{ch['title']}\"")
        if ch.get("framing"):
            print(f"  concept framing ↔ prose: {ch['framing']}")
        if ch.get("own_brief"):
            bd = ch["own_brief"]
            print(f"  this section's brief ↔ ancestor briefs (above): "
                  f"audience={bd.get('audience') or '—'} depth={bd.get('depth') or '—'}")
        for d in ch.get("decisions", []):
            extra = f" — rationale: {d['rationale']}" if d.get("rationale") else ""
            print(f"  decision framing ↔ prose: [{d.get('id')}] {d.get('statement') or ''}{extra}")
        for fig in ch.get("figures", []):
            print(f"  figure framing ↔ prose: {fig} (is the diagram still drawn in the current framing?)")
        for r in ch.get("realized", []):
            src = f" [{r['from_section']}]" if r.get("from_section") else ""
            print(f"  realized shared truth ↔ prose: [{r.get('id')}]{src} {r.get('statement') or ''}{_realized_mark(r)} "
                  f"(does this section's prose still implement this upstream truth, or did it move?)")
        print()

    if proj.ancestor_normative:
        print("── Ancestor-chain normative decisions (check inheritance consistency: this section must not contradict / overstep; non-blocking finding) ──")
        print("   (backstage governance you OBEY; NEVER narrate as 「本節約束下游…／設計依據…」 prose)")
        for a in proj.ancestor_normative:
            for d in a["decisions"]:
                print(f"  • [{a['section']} · {d['id']}] {d.get('statement') or ''}")
        print()

    if proj.realized:
        print("── Shared truth this section realizes (cross-document; must be realized / must not be violated) ──")
        for r in proj.realized:
            print(f"  • [{r['id']} ← {r['from_section']}] {r['statement']}{_realized_mark(r)}")
        print()

    if proj.writes:
        print("── The artifact you are to write ──")
        for w in proj.writes:
            print(f"\n● {w['id']} → {w['generates']}")
            if w.get("requiredFields"):
                print(f"  Required: {', '.join(w['requiredFields'])}")
            if w.get("entriesContainer"):
                print("  Container: file top level MUST be { entries: [ … ] } (not a bare list / other key)")
            for f in w.get("fieldContract") or []:
                for line in _contract_lines(f):
                    print(line)
            if w.get("yamlSkeleton"):
                print("  Skeleton (paste, then fill):")
                for ln in str(w["yamlSkeleton"]).splitlines():
                    print(f"    {ln}")
            if w.get("instruction"):
                print(w["instruction"])

    if proj.glossary:
        print("\n── Terminology authority (lean index; apply the bucket treatment before writing; canonical is mandatory, aliases_forbidden is banned) ──")
        print("  Drill down for definition/english via `docspec show <id>`; write per the definition in your own words (write-per, don't clone).")
        _treat = {
            "module":   "use the canonical name · expand abbreviations · may attach the English original on first use",
            "standard": "official spelling verbatim · do not translate",
            "protocol": "token byte-exact · code formatting · do not translate",
        }
        for bucket in ("module", "standard", "protocol"):
            terms = [t for t in proj.glossary if t.get("bucket") == bucket]
            if not terms:
                continue
            print(f"  {bucket} ({_treat[bucket]}):")
            for t in terms:
                tid = t.get("id")
                bans = []
                if bucket == "module" and t.get("code"):
                    bans.append(f"do not use bare {t['code']}")
                if t.get("aliases_forbidden"):
                    bans.append("banned: " + ", ".join(map(str, t["aliases_forbidden"])))
                tail = f" ({'; '.join(bans)})" if bans else ""
                canon = t.get("canonical")
                disp = f"`{canon}`" if bucket == "protocol" else canon  # protocol uses code formatting to demonstrate the treatment
                ref = f" [{tid}]" if tid else ""
                print(f"    • {disp}{ref}{tail}")

    if proj.writing_guide:
        # 尾端回指：巨量/被截尾的投影從尾巴讀起也找得到風格權威（正文在上方、header 之後）。
        print("\n(style authority: the writing guide is projected near the TOP of this output, right after the header — read it before touching any prose)")
    return 0
