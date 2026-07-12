"""指令共用的 bootstrap：尋根→佈局→config→schema→model。"""

from __future__ import annotations

import sys

from dspx.engine.config import ConfigError, load_config
from dspx.engine.layout import Layout, LayoutError, find_planning_home
from dspx.engine.model import Leaf, ModelError, load_project
from dspx.engine.schema import Schema, SchemaError, load_schema


class BootstrapError(Exception):
    """已向 stderr 回報的啟動失敗（攜帶離開碼）。"""

    def __init__(self, exit_code: int):
        super().__init__(exit_code)
        self.exit_code = exit_code


def bootstrap() -> tuple[Layout, dict]:
    """解析專案；失敗時輸出訊息並拋 BootstrapError。"""
    try:
        home = find_planning_home()
    except LayoutError as exc:
        sys.stderr.write(
            f"docspec: no docspec project found — {exc}\n"
            "Run `docspec init` in the target directory to create one "
            "(config.yaml + corpus/ + skills).\n"
        )
        raise BootstrapError(1) from exc
    try:
        config = load_config(home)
    except ConfigError as exc:
        sys.stderr.write(f"docspec: {exc}\n")
        raise BootstrapError(1) from exc
    layout = Layout(home, config.get("docs_layout", "flat"))
    return layout, config


def load_engine_schema(config: dict) -> Schema:
    """載入專案 config 指定的 schema（預設 section-driven）。"""
    try:
        return load_schema(config.get("schema"))
    except SchemaError as exc:
        sys.stderr.write(f"docspec: {exc}\n")
        raise BootstrapError(1) from exc


def load_model(layout: Layout) -> list[Leaf]:
    """載入全 corpus 末節；解析失敗時回報並拋 BootstrapError。"""
    try:
        return load_project(layout)
    except ModelError as exc:
        sys.stderr.write(f"docspec: {exc}\n")
        raise BootstrapError(1) from exc
