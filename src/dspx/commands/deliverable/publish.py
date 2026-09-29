"""docspec publish — `docspec freeze` 的舊名（2026/09/30 改名），保留作相容別名。"""

from __future__ import annotations

from dspx.commands.deliverable import freeze as _freeze

NAME = "publish"
HELP = "old name of `docspec freeze` (freeze a document version); kept as an alias"


def run(argv: list[str]) -> int:
    return _freeze.run(argv)
