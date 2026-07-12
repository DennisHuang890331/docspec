"""docspec reference [topic] — print craft or writing-style reference material.

Two independent sources, merged into one topic index:
  1. **Template-pack craft reference** (engine-specific idioms, known traps) — not a *rule* the
     engine can enforce, so it ships with a template pack as a per-pack `reference.md` member and
     is surfaced on demand instead of carrying a stale copy in skill prose.
  2. **docspec-bundled writing reference** (`writing-zh` / `writing-en`) — curated, cited pointers
     to native-language writing-craft authorities (e.g. 余光中/思果 for zh, Orwell/Strunk & White
     for en) for `develop` to consult when drafting a project's `writing-guide.md` "Project
     conventions" section. Language-specific naturalness doctrine is NOT baked into docspec's own
     prose (that risks stale, invented-sounding advice); it lives here as citeable reference,
     always available regardless of which template pack or project is active.

Both sources use the same `<!-- topic: NAME -->` marker convention, split into topic sections and
printed one at a time. No topic → a combined index. A pack with no `reference.md` is fine
(advisory, not a gate). Read-only, offline; no project required — mirrors `version`/`measure-fonts`
(no bootstrap).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from dspx.engine import paths

NAME = "reference"
HELP = "Print craft or writing-style reference material (template-pack idioms + docspec's zh/en writing references)"

_REFERENCE_FILE = "reference.md"
_WRITING_REFERENCE_FILE = "writing.md"
_TOPIC_RE = re.compile(r"^<!--\s*topic:\s*([A-Za-z0-9_-]+)\s*-->\s*$", re.MULTILINE)


def _split_topics(text: str) -> dict[str, str]:
    """Split a reference.md into {topic-id: section-body} by `<!-- topic: id -->` markers.

    Order-preserving (dict keeps insertion order). Text before the first marker
    (the file preamble) is ignored — only marked sections are addressable.
    """
    sections: dict[str, str] = {}
    matches = list(_TOPIC_RE.finditer(text))
    for i, m in enumerate(matches):
        topic = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[topic] = text[start:end].strip()
    return sections


def _topic_title(body: str) -> str:
    """First heading/line of a section, for the index listing."""
    for line in body.splitlines():
        line = line.strip()
        if line:
            return line.lstrip("# ").strip()
    return ""


def _load_topics(ref_file: Path) -> dict[str, str]:
    if not ref_file.is_file():
        return {}
    return _split_topics(ref_file.read_text(encoding="utf-8"))


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec reference", description=HELP)
    parser.add_argument("topic", nargs="?", default=None,
                        help="the topic to print (omit = list all available topics)")
    parser.add_argument("--template", default=None, metavar="DIR",
                        help="read the craft reference from the given template pack directory instead of the bundled pack")
    args = parser.parse_args(argv)

    if args.template is not None:
        pack = Path(args.template)
        if not pack.is_dir():
            sys.stderr.write(f"docspec: --template directory does not exist: {pack}\n")
            return 1
    else:
        pack = paths.bundled_typst_template_dir()
        if pack is None:
            sys.stderr.write(
                "docspec: bundled template pack not found — the install may be incomplete.\n")
            return 1

    pack_topics = _load_topics(pack / _REFERENCE_FILE)

    writing_dir = paths.bundled_reference_dir()
    writing_topics = _load_topics(writing_dir / _WRITING_REFERENCE_FILE) if writing_dir else {}

    # docspec-bundled writing topics first (stable regardless of active pack), then pack craft topics.
    topics = {**writing_topics, **pack_topics}

    if not topics:
        print(f"No reference topics available (template pack \"{pack.name}\" ships no {_REFERENCE_FILE}; "
              f"no bundled writing reference found).")
        return 0

    if args.topic is None:
        print("Reference topics:")
        if writing_topics:
            print("  writing (docspec-bundled):")
            for tid, body in writing_topics.items():
                print(f"    {tid:16}  {_topic_title(body)}")
        if pack_topics:
            print(f"  craft (template pack \"{pack.name}\"):")
            for tid, body in pack_topics.items():
                print(f"    {tid:16}  {_topic_title(body)}")
        print(f"\nUsage: docspec reference <topic> (e.g. docspec reference {next(iter(topics))})")
        return 0

    if args.topic not in topics:
        sys.stderr.write(
            f"docspec: no reference topic \"{args.topic}\". Available: {', '.join(topics)}\n")
        return 2

    print(topics[args.topic])
    return 0
