"""markdown YAML frontmatter 讀寫（共用工具）。"""

from __future__ import annotations

from pathlib import Path

import yaml


class FrontmatterError(Exception):
    """frontmatter 缺損或無法解析。"""


def parse_frontmatter(text: str, *, source: object = "<text>") -> tuple[dict, str]:
    """回傳 (frontmatter dict, body)。無 frontmatter → ({}, 原文)。"""
    if not text.startswith("---"):
        return {}, text
    lines = text.split("\n")
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        raise FrontmatterError(f"frontmatter not closed: {source}")
    block = "\n".join(lines[1:end])
    try:
        data = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        raise FrontmatterError(f"frontmatter parse failed: {source} ({exc})") from exc
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise FrontmatterError(f"frontmatter must be a key-value mapping: {source}")
    body = "\n".join(lines[end + 1 :])
    return data, body


def read_frontmatter(path: Path) -> tuple[dict, str]:
    return parse_frontmatter(path.read_text(encoding="utf-8"), source=path)


def render_frontmatter(data: dict, body: str) -> str:
    block = yaml.safe_dump(data, allow_unicode=True, sort_keys=False).strip()
    if body and not body.startswith("\n"):
        body = "\n" + body
    return f"---\n{block}\n---{body}"


def write_frontmatter(path: Path, data: dict, body: str) -> None:
    path.write_text(render_frontmatter(data, body), encoding="utf-8", newline="\n")
