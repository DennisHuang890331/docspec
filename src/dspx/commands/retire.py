"""docspec retire <section> — 把 superseded/deprecated 決策機械搬進 history。

拆分：**結構**（id/kind/status/statement/retired-in/superseded-by/decided-in）留 history.yaml；
**散文 why**（rationale/rejected/why/reason）搬進成對的 history.md 的 `## <id>` 段（同 id 綁）。
純機械、不判語義。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from dspx.commands._shared import BootstrapError, bootstrap

NAME = "retire"
HELP = "move superseded/deprecated decisions into history (structure -> history.yaml, prose why -> history.md)"

_RETIRE_STATUS = ("superseded", "deprecated")
# 這些是「散文 why」，搬去 history.md，不留 history.yaml
_PROSE_FIELDS = ("rationale", "rejected", "why", "reason")
# history.yaml 結構帳只留這些（其餘結構欄如 supersedes/trace 若有也保留）
_STRUCT_DROP = set(_PROSE_FIELDS)

_HISTORY_MD_HEADER = (
    "# history（退場散文墳場）\n\n"
    "<!-- 每個 ## <id> 段對應 history.yaml 一列；寫「為什麼放棄」。draft 不讀此檔。 -->\n"
)


def _load_entries(path) -> list[dict]:
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = data.get("entries") or []
    return [e for e in entries if isinstance(e, dict)]


def _dump_entries(path, entries: list[dict], header: str) -> None:
    block = yaml.safe_dump({"entries": entries}, allow_unicode=True, sort_keys=False)
    path.write_text(header + block, encoding="utf-8")


def _md_has_section(existing: str, anchor_id: str) -> bool:
    # 乾淨 ## <id>：取標題第一個空白分隔 token（id 是 slug 無空白）＝穩、不解析散文
    for line in existing.splitlines():
        if line.startswith("## "):
            parts = line[3:].split()
            if parts and parts[0] == anchor_id:
                return True
    return False


def append_history_md(section_dir: Path, anchor_id: str, heading: str, body: str) -> None:
    """在該節 history.md append 一個 `## <heading>` 段（同 anchor_id 已存在則跳過）。"""
    path = section_dir / "history.md"
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    if _md_has_section(existing, anchor_id):
        return
    if not existing.strip():
        existing = _HISTORY_MD_HEADER
    block = f"\n## {heading}\n{body}\n" if body else f"\n## {heading}\n"
    path.write_text(existing.rstrip() + "\n" + block, encoding="utf-8")


def _prose_body(e: dict) -> str:
    """從決策條目組「為什麼」的散文（rationale/why/reason 段 + rejected 條列）。"""
    parts: list[str] = []
    for key in ("rationale", "why", "reason"):
        v = e.get(key)
        if isinstance(v, str) and v.strip():
            parts.append(v.strip())
    rejected = e.get("rejected")
    if isinstance(rejected, list) and rejected:
        parts.append("\n".join(f"- 否決：{r}" for r in rejected))
    elif isinstance(rejected, str) and rejected.strip():
        parts.append(f"- 否決：{rejected.strip()}")
    return "\n\n".join(parts)


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec retire", description=HELP)
    parser.add_argument("section", help="leaf section path (relative to corpus/)")
    parser.add_argument("--in", dest="retired_in", default=None,
                        help="which change/session this is retired in (written to retired-in)")
    args = parser.parse_args(argv)

    try:
        layout, _config = bootstrap()
    except BootstrapError as exc:
        return exc.exit_code

    leaf_dir = layout.section_dir(args.section)
    decisions_path = leaf_dir / "decisions.yaml"
    history_path = leaf_dir / "history.yaml"
    if not decisions_path.is_file():
        sys.stderr.write(f"docspec: {decisions_path} not found\n")
        return 1

    decisions = _load_entries(decisions_path)
    to_retire = [e for e in decisions if str(e.get("status")) in _RETIRE_STATUS]
    if not to_retire:
        print(f"retire: {args.section} has no superseded/deprecated decisions to move.")
        return 0

    history = _load_entries(history_path)
    keep = [e for e in decisions if str(e.get("status")) not in _RETIRE_STATUS]

    for e in to_retire:
        eid = str(e.get("id", ""))
        statement = str(e.get("statement", "")).strip()
        # 散文 why → history.md（同 id 綁；標題帶 {#<id>} 錨點供 link 對應）
        body = _prose_body(e)
        in_tag = f"\n**退場於** {args.retired_in}。" if args.retired_in else ""
        # 乾淨標題＝純 id（statement 摘要留 yaml；不把標題塞進 md 標題以免要解析）
        head_note = f"（{statement}）" if statement else ""
        append_history_md(leaf_dir, eid, eid,
                          (head_note + in_tag + ("\n" + body if body else "")).strip())
        # 結構 → history.yaml（去掉散文欄；綁定＝同一個 id ⟺ history.md `## <id>` 段，由 check 強制）
        lean = {k: v for k, v in e.items() if k not in _STRUCT_DROP}
        if args.retired_in and "retired-in" not in lean:
            lean["retired-in"] = args.retired_in
        history.append(lean)

    # 先寫 history（additive），再寫 decisions（removal）：中途失敗留重複而非遺失
    _dump_entries(history_path, history,
                  "# 退場決策結構帳（docspec retire 搬入；散文 why 在 history.md）。draft 不讀。\n")
    _dump_entries(decisions_path, keep,
                  "# 本節活著的決策。append / supersede，退場的搬去 history。\n")

    print(f"retire: {args.section} moved {len(to_retire)} decision(s) -> history.yaml (prose why -> history.md)")
    for e in to_retire:
        print(f"  -> {e.get('id')} ({e.get('status')})")
    print("  next: docspec check (verifies history.yaml <-> history.md correspondence)")
    return 0
