"""docspec ready <section> — 畢業交易（一手包）。

檢兩件：①目的地 yaml 完整（run_file_check：必填非空/型別/enum）②develop.md 榨乾
（剝 heading＋HTML 註解＋空白後無實質殘留；fenced 內容算實質）。
雙綠 → 刪 develop.md（畢業的唯一持久動作，status 重算為 ready）；
任一紅 → 拒、列原因、develop.md 留著。agent 無「跳過 check 直接刪」「帶內容畢業」的縫。
"""

from __future__ import annotations

import argparse
import json
import re
import sys

from dspx.check import run_file_check
from dspx.commands._shared import BootstrapError, bootstrap, load_engine_schema
from dspx.model import load_leaf

NAME = "ready"
HELP = "graduation transaction: verify completeness + develop.md drained -> delete develop.md, section turns ready"

_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_HEADING_RE = re.compile(r"^#+(\s|$)")


def drain_remainder(text: str) -> str:
    """剝 HTML 註解＋ATX 標題行＋空白行後的實質殘留。
    fenced code 內容算實質（不剝）→ 有 keeper 沒分流就擋得到。"""
    t = _COMMENT_RE.sub("", text)
    kept: list[str] = []
    for line in t.splitlines():
        s = line.strip()
        if not s or _HEADING_RE.match(s):
            continue
        kept.append(s)
    return "\n".join(kept).strip()


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec ready", description=HELP)
    parser.add_argument("section", help="leaf section path (relative to corpus/)")
    parser.add_argument("--json", action="store_true", dest="as_json", help="output as JSON")
    args = parser.parse_args(argv)

    try:
        layout, config = bootstrap()
        schema = load_engine_schema(config)
    except BootstrapError as exc:
        return exc.exit_code

    section = args.section.strip("/")
    section_dir = layout.section_dir(section)
    if not section_dir.is_dir():
        sys.stderr.write(f"docspec: section \"{section}\" not found: {section_dir}\n")
        return 2

    leaf = load_leaf(layout, section_dir)
    reasons: list[str] = []

    # ① 目的地存在（結晶過）
    if not (section_dir / "concept.yaml").is_file():
        reasons.append("not crystallized yet: missing concept.yaml")
    if not (section_dir / "decisions.yaml").is_file():
        reasons.append("not crystallized yet: missing decisions.yaml")

    # ② 完整性（per-section 欄位級）
    reasons.extend(run_file_check(leaf, schema))

    # ③ develop.md 榨乾
    develop_path = section_dir / "develop.md"
    remainder = ""
    if develop_path.is_file():
        remainder = drain_remainder(develop_path.read_text(encoding="utf-8"))
        if remainder:
            reasons.append(
                "develop.md still has unrouted substantive content -- route it into "
                "concept/decisions/material/history first, or delete the throwaway thinking")

    if reasons:
        if args.as_json:
            print(json.dumps({"section": section, "ready": False, "reasons": reasons},
                             ensure_ascii=False, indent=2))
        else:
            sys.stderr.write(f"docspec: section \"{section}\" cannot graduate yet:\n")
            for r in reasons:
                sys.stderr.write(f"  ✗ {r}\n")
            if remainder:
                sys.stderr.write("  -- develop.md remainder (excerpt) --\n  "
                                 + remainder[:200].replace("\n", "\n  ") + "\n")
        return 1

    # 雙綠 → 刪 develop.md（畢業＝這一個確定性動作；status 重算 ready）
    deleted = develop_path.is_file()
    if deleted:
        develop_path.unlink()

    if args.as_json:
        print(json.dumps({"section": section, "ready": True, "developDeleted": deleted},
                         ensure_ascii=False, indent=2))
    else:
        tail = " + deleted" if deleted else " (no develop.md)"
        print(f"✓ section \"{section}\" graduated: completeness green, develop.md drained{tail}, now ready.")
    return 0
