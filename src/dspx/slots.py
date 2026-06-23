"""Slot contract — the named, validated variable set both export emitters honor.

A *slot* is a backend-neutral document-metadata field (title / authors / abstract /
keywords / …). The Typst-default template consumes it, and each BYO journal pandoc
template (IEEE, Elsevier, …) declares which slots it consumes; `export` validates the
provided slots against the template's referenced variables at render time:

  - a template references a variable the slot contract does NOT define   → "unknown slot"
    (the contract must flex — the empirical signal the IEEE/Elsevier spike exists to surface)
  - the document provides a slot the template never references            → "unused slot"
    (informational; pandoc simply ignores it)

Slot VALUES come from the article's frozen H1 (title), its prose (body), and an optional
project/article `export.slots` mapping (or a `--slots` YAML file). Values are validated by
kind (text / list / people) before any emit — a malformed slot is refused before pandoc runs,
mirroring the format-config "bad value never reaches the engine" discipline.

This is deliberately a SMALL, fixed contract: the IEEE/Elsevier adapter spike (Stage D) is
what defines where it must flex; flex points are recorded in the change's design.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# Semver for the slot-contract surface (independent of the package version): a breaking
# slot rename/removal = major bump, an added optional slot = minor bump. BYO journal
# templates depend on this surface, so it carries its own version. See CHANGELOG.md.
CONTRACT_VERSION = "0.1.0"


class SlotError(Exception):
    """A provided slot value has the wrong shape, or an unknown slot key was given."""


@dataclass(frozen=True)
class Slot:
    name: str
    kind: str          # "text" | "list" | "people"
    required: bool
    derived: bool      # True = engine fills it (title from H1, body from prose); not user-set
    desc: str


# The contract. `body` and `title` are derived from the snapshot; the rest are optional
# metadata a project/article may supply. Keep this list the single source of slot names.
SLOTS: tuple[Slot, ...] = (
    Slot("title",        "text",   True,  True,  "document title (derived from the snapshot's first H1)"),
    Slot("subtitle",     "text",   False, False, "optional subtitle"),
    Slot("authors",      "people", False, False, "list of authors: each a mapping with at least `name` (optional `affiliation`, `email`, `orcid`)"),
    Slot("date",         "text",   False, False, "publication / preparation date"),
    Slot("version",      "text",   False, False, "document version label"),
    Slot("abstract",     "text",   False, False, "abstract paragraph"),
    Slot("keywords",     "list",   False, False, "list of keyword strings"),
    Slot("shorttitle",   "text",   False, False, "running short title (journal headers)"),
    Slot("shortauthors", "text",   False, False, "running short author line (journal headers)"),
    Slot("body",         "text",   True,  True,  "the document prose (derived from the snapshot body)"),
)

_BY_NAME = {s.name: s for s in SLOTS}
USER_SETTABLE = {s.name for s in SLOTS if not s.derived}


def _validate_value(slot: Slot, value) -> object:
    """Validate one slot value by kind; return the normalized value or raise SlotError."""
    if slot.kind == "text":
        if not isinstance(value, str):
            raise SlotError(f"slot \"{slot.name}\" must be text (got {type(value).__name__})")
        return value
    if slot.kind == "list":
        if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
            raise SlotError(f"slot \"{slot.name}\" must be a list of strings")
        return value
    if slot.kind == "people":
        if not isinstance(value, list):
            raise SlotError(f"slot \"{slot.name}\" must be a list of author mappings")
        out = []
        for i, person in enumerate(value):
            if not isinstance(person, dict) or not str(person.get("name", "")).strip():
                raise SlotError(f"slot \"{slot.name}\"[{i}] must be a mapping with a non-empty `name`")
            out.append(person)
        return out
    raise SlotError(f"slot \"{slot.name}\" has an unknown kind {slot.kind!r}")  # pragma: no cover


def build_slots(title: str, body: str, extra: dict | None = None) -> dict:
    """Assemble + validate the slot set: derived (title/body) + optional user-supplied `extra`.

    Unknown keys in `extra` raise SlotError (the contract is closed — a typo or an
    out-of-contract field fails loud rather than silently vanishing).
    """
    extra = dict(extra or {})
    slots: dict[str, object] = {"title": title, "body": body}
    unknown = [k for k in extra if k not in USER_SETTABLE]
    if unknown:
        raise SlotError(
            f"unknown slot(s): {', '.join(sorted(unknown))} "
            f"(settable slots: {', '.join(sorted(USER_SETTABLE))})")
    for name, value in extra.items():
        if value is None:
            continue
        slots[name] = _validate_value(_BY_NAME[name], value)
    return slots


# ── render-time validation against a pandoc template ──────────────────────────

# pandoc template variable references: $var$, $var.field$, $for(var)$, $if(var)$, $sep$, etc.
_TEMPLATE_VAR_RE = re.compile(r"\$(?:for|if|ifelse|elseif)\(([\w.]+)\)|\$([\w.]+)\$")
# pandoc template control keywords that are NOT slots.
_CONTROL = {"for", "if", "ifelse", "elseif", "else", "endfor", "endif", "sep", "it",
            "body", "$"}


def template_referenced_slots(template_text: str) -> set[str]:
    """The set of slot names a pandoc template references (root token before any `.`)."""
    found: set[str] = set()
    for m in _TEMPLATE_VAR_RE.finditer(template_text):
        token = m.group(1) or m.group(2) or ""
        root = token.split(".", 1)[0]
        if root and root not in _CONTROL:
            found.add(root)
    return found


def validate_against_template(provided: dict, template_text: str) -> tuple[list[str], list[str]]:
    """Compare provided slots to a template's referenced variables.

    Returns (unknown_wanted, unused_provided):
      - unknown_wanted = variables the template references that are NOT in the slot contract
        (these define where the contract must flex — surfaced to the user).
      - unused_provided = slots the document provides that the template never references
        (informational; pandoc ignores them).
    Derived slots (title/body) and pandoc built-ins are never reported as unused.
    """
    referenced = template_referenced_slots(template_text)
    contract = {s.name for s in SLOTS}
    unknown_wanted = sorted(referenced - contract)
    unused_provided = sorted(
        name for name in provided
        if name not in referenced and name in USER_SETTABLE)
    return unknown_wanted, unused_provided
