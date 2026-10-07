"""Provider labels plus optional stable session ids; not identity authentication."""
from __future__ import annotations

import os
import re

from dspx.engine.governance import TOOLS
from dspx.engine.software.io import SoftwareError

_INSTANCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")


def validate_instance(instance: str | None) -> str | None:
    if instance is not None and (not isinstance(instance, str) or not _INSTANCE.fullmatch(instance)):
        raise SoftwareError("invalid agent instance id: use 1-128 ASCII letters, digits, '.', '_', ':' or '-'")
    return instance


def detect_instance(tool: str) -> str | None:
    """Never mint a per-command identity or override a detected Codex thread."""
    if tool == "user":
        return None
    explicit = validate_instance(os.environ.get("DOCSPEC_ACTOR_ID"))
    detected = validate_instance(os.environ.get("CODEX_THREAD_ID")) if tool == "gpt" else None
    if detected is not None and explicit is not None and detected != explicit:
        raise SoftwareError("DOCSPEC_ACTOR_ID conflicts with CODEX_THREAD_ID; use the actual session id, "
                            "not a different role label")
    return detected if detected is not None else explicit


def same_actor(tool1: str | None, instance1: str | None,
               tool2: str | None, instance2: str | None) -> bool:
    """Unknown same-provider independence is conservative; ownership is stricter."""
    validate_instance(instance1)
    validate_instance(instance2)
    return tool1 == tool2 and (instance1 is None or instance2 is None or instance1 == instance2)


def label(tool: str | None, instance: str | None) -> str:
    return f"{tool} (session {instance})" if instance is not None else str(tool)


def require_author(record: dict, tool: str, instance: str | None, *,
                   field: str = "written-by", instance_field: str = "written-by-instance") -> None:
    author, author_instance = record.get(field), validate_instance(record.get(instance_field))
    validate_instance(instance)
    if tool not in TOOLS or author not in TOOLS:
        raise SoftwareError("invalid test author or signer provider; record a valid tool label before signing")
    if tool == "user":
        return
    if tool != author or (author_instance is not None and instance != author_instance):
        raise SoftwareError(f"only its author (the test role) or the owner may change, remove, sign or "
                            f"answer for this test; author is {label(author, author_instance)}, "
                            f"you are \"{label(tool, instance)}\". Preserve the original session id; "
                            "do not impersonate another agent or the owner")


def require_independent(ch: dict, tool: str, instance: str | None) -> None:
    """Keep the existing change-wide test/implementation separation guard."""
    if tool == "user":
        return
    for task in ch["tasks"].get("tasks") or []:
        author = task.get("created-by")
        if task.get("created-by-instance") is not None and author not in TOOLS:
            raise SoftwareError("invalid implementation author provider for a recorded session id")
        if author not in (None, "user") and same_actor(
                tool, instance, author, task.get("created-by-instance")):
            reason = ("same-provider records lack a session id; independence cannot be determined"
                      if instance is None or task.get("created-by-instance") is None
                      else "the same session created implementation tasks in this change")
            raise SoftwareError(f"{label(tool, instance)} created implementation tasks or cannot be "
                                f"distinguished from their author: {reason}; the test role must be a "
                                "different agent session. Use an independently launched session with "
                                "its stable id; legacy records are not automatically reassigned")
