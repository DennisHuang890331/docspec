"""docspec reference [topic] — print the active template pack's craft reference.

Craft knowledge (TikZ idioms, known LaTeX traps) is not a *rule* the engine can
enforce — it ships with the template pack as a per-pack reference member and is
surfaced on demand. The release skill points here when the agent hits a mermaid
box or a LaTeX trap, instead of carrying a stale copy in its prose.

Pack-agnostic: reads `reference.md` from the active pack (the bundled `docspec-cas`,
or a `--template <dir>` pack), splits it into topic sections by
`<!-- topic: NAME -->` markers, and prints one. No topic → an index of the
topics the active pack ships. A pack with no `reference.md` is fine (advisory,
not a gate): it just has no craft reference. Read-only, offline; no project
required — mirrors `version`/`measure-fonts` (no bootstrap).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from dspx import paths

NAME = "reference"
HELP = "Print the active template pack's craft reference (TikZ idioms / LaTeX traps; consult during release when you hit a box)"

_REFERENCE_FILE = "reference.md"
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


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec reference", description=HELP)
    parser.add_argument("topic", nargs="?", default=None,
                        help="the craft topic to print (omit = list this pack's available topics)")
    parser.add_argument("--template", default=None, metavar="DIR",
                        help="read the reference file from the given template pack instead (same as export --template)")
    args = parser.parse_args(argv)

    try:
        pack = paths.resolve_template_dir(args.template)
    except paths.AssetError as exc:
        sys.stderr.write(f"docspec: {exc}\n")
        return 1
    if pack is None:
        sys.stderr.write(
            "docspec: template pack not found — the install may be incomplete or the --template path is wrong.\n")
        return 1

    ref = pack / _REFERENCE_FILE
    if not ref.is_file():
        # advisory, not a gate: a pack may legitimately ship no craft reference.
        print(f"Template pack \"{pack.name}\" ships no craft reference (no {_REFERENCE_FILE}).")
        return 0

    text = ref.read_text(encoding="utf-8")
    topics = _split_topics(text)
    if not topics:
        print(f"The {_REFERENCE_FILE} of template pack \"{pack.name}\" marks no topics.")
        return 0

    if args.topic is None:
        print(f"Craft reference topics for template pack \"{pack.name}\":")
        for tid, body in topics.items():
            print(f"  {tid:16}  {_topic_title(body)}")
        print(f"\nUsage: docspec reference <topic> (e.g. docspec reference {next(iter(topics))})")
        return 0

    if args.topic not in topics:
        sys.stderr.write(
            f"docspec: template pack \"{pack.name}\" has no topic \"{args.topic}\". "
            f"Available: {', '.join(topics)}\n")
        return 2

    print(topics[args.topic])
    return 0
