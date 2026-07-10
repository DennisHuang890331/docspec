"""dspx 子指令 registry。

子指令模組介面：NAME: str、HELP: str、run(argv: list[str]) -> int。
新增子指令＝新增模組＋下方一行註冊。
"""

from __future__ import annotations

from types import ModuleType

REGISTRY: dict[str, ModuleType] = {}

# Human-facing CLI surface: the only commands a person runs directly (bootstrap +
# maintenance). Everything else is agent-facing — driven by skills via `docspec guide` /
# `docspec instructions` — and hidden from the default `--help` (still runnable; listed by
# `docspec --help-all`). This is a discoverability split, not access control.
HUMAN_COMMANDS = frozenset({"init", "setup", "skills", "doctor", "upgrade", "version"})


def _register(module: ModuleType) -> None:
    REGISTRY[module.NAME] = module


from dspx.commands import audit as _audit  # noqa: E402
from dspx.commands import check as _check  # noqa: E402
from dspx.commands import diff as _diff  # noqa: E402
from dspx.commands import doctor as _doctor  # noqa: E402
from dspx.commands import export as _export  # noqa: E402
from dspx.commands import freeze_cmd as _freeze_cmd  # noqa: E402
from dspx.commands import guide as _guide  # noqa: E402
from dspx.commands import hook as _hook  # noqa: E402
from dspx.commands import impact as _impact  # noqa: E402
from dspx.commands import init as _init  # noqa: E402
from dspx.commands import instructions as _instructions  # noqa: E402
from dspx.commands import lint as _lint  # noqa: E402
from dspx.commands import list_cmd as _list_cmd  # noqa: E402
from dspx.commands import measure_fonts as _measure_fonts  # noqa: E402
from dspx.commands import new as _new  # noqa: E402
from dspx.commands import proof as _proof  # noqa: E402
from dspx.commands import reference as _reference  # noqa: E402
from dspx.commands import publish as _publish  # noqa: E402
from dspx.commands import ready as _ready  # noqa: E402
from dspx.commands import redraft as _redraft  # noqa: E402
from dspx.commands import render as _render  # noqa: E402
from dspx.commands import retire as _retire  # noqa: E402
from dspx.commands import stale as _stale  # noqa: E402
from dspx.commands import roadmap as _roadmap  # noqa: E402
from dspx.commands import retire_section as _retire_section  # noqa: E402
from dspx.commands import retired as _retired  # noqa: E402
from dspx.commands import setup as _setup  # noqa: E402
from dspx.commands import show as _show  # noqa: E402
from dspx.commands import skills_cmd as _skills  # noqa: E402
from dspx.commands import status as _status  # noqa: E402
from dspx.commands import upgrade as _upgrade  # noqa: E402
from dspx.commands import version as _version  # noqa: E402

_register(_init)
_register(_new)
_register(_status)
_register(_check)
_register(_instructions)
_register(_lint)
_register(_retire)
_register(_roadmap)
_register(_retire_section)
_register(_retired)
_register(_setup)
_register(_doctor)
_register(_upgrade)
_register(_version)
_register(_render)
_register(_stale)
_register(_redraft)
_register(_export)
_register(_proof)
_register(_measure_fonts)
_register(_reference)
_register(_diff)
_register(_impact)
_register(_hook)
_register(_freeze_cmd)
_register(_audit)
_register(_publish)
_register(_guide)
_register(_ready)
_register(_show)
_register(_list_cmd)
_register(_skills)
