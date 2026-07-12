"""dspx 子指令 registry（領域子套件 ＋ 自動發現）。

子指令模組介面：NAME: str、HELP: str、run(argv: list[str]) -> int。
指令模組住領域子套件（corpus/ query/ deliverable/ export/ change/ governance/
projection/ maintenance/ _internal/）；**新增指令＝把模組丟進對應子套件即可**，registry
掃子套件自動發現有這三個屬性的模組——不需在此手寫 import。`_` 前綴模組（_shared、各
包的 helper）不被收。人面（`--help` 預設顯示）＝maintenance/ 子套件的成員；其餘 agent 面
（靠 `docspec guide`/`instructions` 投影發現、`--help-all` 才列）。
"""

from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType

REGISTRY: dict[str, ModuleType] = {}
_HUMAN: set[str] = set()


def _register(module: ModuleType) -> None:
    REGISTRY[module.NAME] = module


def _discover() -> None:
    """掃 dspx.commands.* 子套件，收有 NAME/HELP/run 的模組進 REGISTRY。"""
    import dspx.commands as _pkg
    for info in pkgutil.walk_packages(_pkg.__path__, _pkg.__name__ + "."):
        leaf = info.name.rsplit(".", 1)[-1]
        if leaf.startswith("_"):
            continue                       # _shared、各包 helper 不是指令
        mod = importlib.import_module(info.name)
        if all(hasattr(mod, a) for a in ("NAME", "HELP", "run")):
            _register(mod)
            # 人面＝住 maintenance/ 子套件的指令（bootstrap＋維護）
            if ".maintenance." in info.name + ".":
                _HUMAN.add(mod.NAME)


_discover()

# Human-facing CLI surface: the only commands a person runs directly (bootstrap +
# maintenance). Everything else is agent-facing — driven by skills via `docspec guide` /
# `docspec instructions` — and hidden from the default `--help` (still runnable; listed by
# `docspec --help-all`). This is a discoverability split, not access control.
HUMAN_COMMANDS = frozenset(_HUMAN)
