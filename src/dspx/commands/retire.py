"""docspec retire <section> — 死決策就地報告（非破壞、不搬檔）。

contract-slimming D3：死決策（`status: superseded`/`deprecated`）**留在原 decisions.yaml**，
不搬進 live 樹 history.yaml。原檔可定址正是三套承重接線的前提——supersede 鏈解析、
deps 指紋二跳、check 的 repoint-to-live-successor 指引全都直接讀 decisions.yaml。

本指令因此改為**純報告、零寫入**：偵測該節 decisions.yaml 內的 superseded/deprecated 條目，
指出「就地即終態、無物可搬」。整節退場（`docspec retire-section`）在 `_archive/` 生成封存包的
行為不受本案影響。舊指令「把死決策搬 live 樹 history.yaml」的路徑已撤除。
"""

from __future__ import annotations

import argparse

import yaml

from dspx.commands._shared import BootstrapError, bootstrap

NAME = "retire"
HELP = "report dead decisions (superseded/deprecated) that stay in place in decisions.yaml (non-mutating)"

_RETIRE_STATUS = ("superseded", "deprecated")


def _load_entries(path) -> list[dict]:
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = data.get("entries") or []
    return [e for e in entries if isinstance(e, dict)]


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec retire", description=HELP)
    parser.add_argument("section", help="leaf section path (relative to corpus/)")
    parser.add_argument("--in", dest="retired_in", default=None,
                        help="(deprecated no-op) formerly the change/session tag; retire no longer writes")
    args = parser.parse_args(argv)

    try:
        layout, _config = bootstrap()
    except BootstrapError as exc:
        return exc.exit_code

    leaf_dir = layout.section_dir(args.section)
    decisions_path = leaf_dir / "decisions.yaml"
    if not decisions_path.is_file():
        # 缺檔＝合法空（該節無自有決策）＝零死決策可報。不當錯誤，直接回報。
        print(f"retire: {args.section} has no decisions.yaml (a section with no rulings of its "
              "own) — nothing to report.")
        return 0

    decisions = _load_entries(decisions_path)
    dead = [e for e in decisions if str(e.get("status")) in _RETIRE_STATUS]
    if not dead:
        print(f"retire: {args.section} has no superseded/deprecated decisions.")
        return 0

    print(f"retire: {args.section} has {len(dead)} dead decision(s) — they STAY IN PLACE in "
          "decisions.yaml (status: superseded/deprecated). Nothing to relocate: the supersede "
          "chain resolver, the deps-fingerprint two-hop signal, and check's repoint-to-live-"
          "successor guidance all read them in decisions.yaml.")
    for e in dead:
        print(f"  · {e.get('id')} ({e.get('status')})"
              + (f" -> superseded-by {e.get('superseded-by')}" if e.get("superseded-by") else ""))
    print("  (docspec retire is now non-mutating; it writes no files. Use `docspec show <id>` / "
          "`docspec impact <id>` to inspect a dead decision.)")
    return 0
