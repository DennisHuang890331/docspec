"""治理層指令（question / ruling / decision / roadmap / impact / trace / brief）的共用小工具。"""

from __future__ import annotations

import json
import sys

from dspx.commands._shared import BootstrapError, bootstrap
from dspx.engine import governance as gv


def split_csv(raw: str | None) -> list[str]:
    return [gv.strip_ns(x.strip()) for x in (raw or "").split(",") if x.strip()]


def open_layout():
    """bootstrap；失敗回 None（訊息已寫 stderr）。"""
    try:
        layout, _config = bootstrap()
    except BootstrapError:
        return None
    return layout


def fail(msg: str, code: int = 1) -> int:
    sys.stderr.write(f"docspec: {msg}\n")
    return code


def emit_json(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def public(rec: dict) -> dict:
    return {k: v for k, v in rec.items() if not k.startswith("_")}


def label(rec: dict) -> str:
    """給人看的標示：標題在前、編號在括號（SR17）。"""
    title = rec.get("title") or rec.get("quote") or rec.get("summary") or ""
    title = " ".join(str(title).split())
    if len(title) > 60:
        title = title[:59] + "…"
    return f"{title}（{rec.get('id')}）"
