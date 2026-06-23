"""docspec instructions <skill> <section> — aperture projection (feed the right files to the right skill)."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys

from dspx.aperture import ApertureError, project
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


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec instructions", description=HELP)
    parser.add_argument("skill", help="develop / draft / edit / factcheck / publish / release")
    parser.add_argument("section", help="leaf-section path (relative to corpus/)")
    parser.add_argument("--json", action="store_true", dest="as_json", help="output as JSON")
    args = parser.parse_args(argv)

    try:
        layout, config = bootstrap()
        schema = load_engine_schema(config)
        leaves = load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code

    # develop-only (not-yet-crystallized) sections must also project — develop needs the concept/decisions templates at crystallization.
    if not any(lf.section == args.section for lf in leaves):
        folder = layout.section_dir(args.section)
        if (folder / "develop.md").is_file() or (folder / "concept.yaml").is_file():
            from dspx.model import load_leaf
            leaves = leaves + [load_leaf(layout, folder)]

    try:
        proj = project(layout, schema, args.skill, args.section, leaves, config)
    except ApertureError as exc:
        sys.stderr.write(f"docspec: {exc}\n")
        return 1

    # Fill in {id}/{title}/{order} in the writes templates (at crystallization the agent just fills in the content)
    # + attach the "required-fields list" so the agent knows the full definition (2.4)
    from dspx.schema import required_field_names
    for w in proj.writes:
        w["template"] = _fill_template(w.get("template"), args.section, layout)
        art = schema.by_id(w.get("id", ""))
        w["requiredFields"] = required_field_names(art.schema) if art and art.schema else []

    if args.as_json:
        print(json.dumps({
            "skill": proj.skill,
            "section": proj.section,
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
        }, ensure_ascii=False, indent=2))
        return 0

    print(f"aperture projection: skill={proj.skill}  section={proj.section}\n")

    if proj.project_purpose:
        print(f"Project goal: {proj.project_purpose}\n")

    if proj.forest is not None:
        f = proj.forest
        print("── Forest map (this document's place in the forest / who governs it / who it parallels; set governed-by against this) ──")
        for d in f.get("documents", []):
            print(f"  [{d['article']}] {d.get('oneLiner') or ''}")
        for h in f.get("hierarchy", []):
            print(f"  {h['childDoc']} → {h['parentDoc']}")
        for pair in f.get("parallel", []):
            print(f"  {pair[0]} ∥ {pair[1]}")
        print()

    if proj.roadmap is not None:
        print("── Backlog (roadmap): planned-but-not-done work for this document + the forest (check before starting) ──")
        if not proj.roadmap:
            print("  (no backlog)")
        else:
            unblocked = [e for e in proj.roadmap if e.get("unblocked")]
            doing = [e for e in proj.roadmap if e.get("status") == "doing"]
            blocked = [e for e in proj.roadmap
                       if e.get("blocked") and e.get("status") != "doing"]
            accounted = ({id(e) for e in unblocked} | {id(e) for e in doing}
                         | {id(e) for e in blocked})
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
            if doing:
                print("  Doing:")
                for e in doing:
                    _r(e)
            if other:
                print("  Other backlog:")
                for e in other:
                    _r(e, f"  ({e.get('status')})")
        print()

    if proj.document_map:
        print("── Document map (the whole article's sections in order — frame THIS section's role in the whole; do NOT read/name siblings' prose) ──")
        for n in proj.document_map:
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
        for pb in proj.parent_briefs:
            print(f"  [{pb['section']}] {pb.get('concept') or ''}")
            if pb.get("brief"):
                print(f"    brief: {pb['brief']}")
        print()

    print("── Readable (within the aperture; this is all you can see) ──")
    if not proj.reads:
        print("  (none — this section has no readable content yet)")
    for art_id, content in proj.reads.items():
        print(f"\n[{art_id}]\n{content}")
    print()

    if proj.ancestor_normative:
        print("── Ancestor-chain normative decisions (check inheritance consistency: this section must not contradict / overstep; non-blocking finding) ──")
        for a in proj.ancestor_normative:
            for d in a["decisions"]:
                print(f"  • [{a['section']} · {d['id']}] {d.get('statement') or ''}")
        print()

    if proj.realized:
        print("── Shared truth this section realizes (cross-document; must be realized / must not be violated) ──")
        for r in proj.realized:
            print(f"  • [{r['id']} ← {r['from_section']}] {r['statement']}")
        print()

    if proj.writes:
        print("── The artifact you are to write ──")
        for w in proj.writes:
            print(f"\n● {w['id']} → {w['generates']}")
            if w.get("requiredFields"):
                print(f"  Required: {', '.join(w['requiredFields'])}")
            if w.get("instruction"):
                print(w["instruction"])

    if proj.writing_guide:
        print("\n── Writing guide (one shared copy for the whole document; coherence comes from it, not from reading other sections) ──")
        print(proj.writing_guide)

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
    return 0
