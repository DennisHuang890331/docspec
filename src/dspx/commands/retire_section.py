"""docspec retire-section <section> — 整節退場。

跟 `docspec retire`（搬決策）不同層級：這裡退場「整個章節（含子節）」。
設計（per-section 獨立、適合長期文件管理）：
  1. 退場結構記錄 append 進該節「自己的」history.yaml 的 `retired:` 區塊
     （section=原路徑、archive=封存實體位置＝link、note、in）；
  2. 退場散文（為何整節退場）開進該節 history.md 的 `## <原路徑>` 段；
  3. 整包搬進扁平封存區 corpus/_archive/<攤平路徑>/——兩份記錄隨節一起走、自我包含、可回復；
  4. 引擎忽略 `_` 開頭目錄，封存後對 status/check/render/draft 全隱形。
查詢用 `docspec retired`。
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys

import yaml

from dspx.commands._shared import BootstrapError, bootstrap

NAME = "retire-section"
HELP = "retire an entire section (including children) to corpus/_archive/; recorded as a kind:section entry in the section's history.yaml"


def _concept_field(section_dir, field: str) -> str | None:
    path = section_dir / "concept.yaml"
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return None
    if isinstance(data, dict) and data.get(field):
        return str(data[field])
    return None


def _section_id(section_dir, section: str) -> str:
    """整節退場用該節穩定 concept.id（非路徑！）；develop-only 節退場則用路徑指紋（同 new 規則）。"""
    return _concept_field(section_dir, "id") or (
        "sec-" + hashlib.sha1(section.encode("utf-8")).hexdigest()[:8])


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec retire-section", description=HELP)
    parser.add_argument("section", help="path of the section to retire (relative to corpus/)")
    parser.add_argument("--in", dest="retired_in", default=None,
                        help="which change/session this is retired in (written to retired.in)")
    parser.add_argument("--note", default=None,
                        help="one-line description (defaults to the section's concept.concept)")
    args = parser.parse_args(argv)

    try:
        layout, _config = bootstrap()
    except BootstrapError as exc:
        return exc.exit_code

    section = args.section.strip("/")
    src = layout.section_dir(section)
    if not src.is_dir() or not (
        (src / "concept.yaml").is_file() or (src / "develop.md").is_file()
    ):
        sys.stderr.write(
            f"docspec: section \"{section}\" not found (needs concept.yaml or develop.md). "
            f"Use docspec status / docspec list to get the correct path.\n")
        return 1
    if layout.is_archived_path(src):
        sys.stderr.write(f"docspec: \"{section}\" is already in the archive.\n")
        return 1

    note = args.note or _concept_field(src, "concept") or section
    sec_id = _section_id(src, section)
    # 封存實體位置（＝link），存進記錄；相對 planning home（corpus/_archive/...）
    archive_root = layout.corpus_archive_dir
    dest = archive_root / section.replace("/", "__")
    if dest.exists():
        sys.stderr.write(f"docspec: archive destination already exists: {dest}. Resolve it before retiring.\n")
        return 1
    archive_link = dest.relative_to(layout.planning_home).as_posix()

    # 整節退場＝該節 history.yaml entries 多一筆 kind:section（id=concept.id、附 archive link）。
    # 細節＝archive 資料夾本身（不寫 history.md；history.md 只給決策退場的散文）。隨節進 archive。
    history_path = src / "history.yaml"
    entries: list = []
    if history_path.is_file():
        try:
            loaded = yaml.safe_load(history_path.read_text(encoding="utf-8")) or {}
            if isinstance(loaded, dict):
                entries = [e for e in (loaded.get("entries") or []) if isinstance(e, dict)]
        except yaml.YAMLError:
            entries = []
    entries.append({
        "id": sec_id,              # ★該節穩定 concept.id（非路徑）
        "kind": "section",
        "status": "retired",
        "statement": note,
        "archive": archive_link,   # 指向封存資料夾的 link（細節在那）
        **({"retired-in": args.retired_in} if args.retired_in else {}),
    })
    history_path.write_text(
        "# 本節歷史 entries：死決策（kind normative/rationale，散文在 history.md）"
        "＋整節退場（kind section，細節在 archive 資料夾）。\n"
        + yaml.safe_dump({"entries": entries}, allow_unicode=True, sort_keys=False),
        encoding="utf-8")

    # 整包搬進扁平封存區（可回復、引擎隱形）
    archive_root.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    # 搬移後完整性驗證（Drive 同步/權限可能半搬）
    if src.exists() or not (dest / "history.yaml").is_file():
        sys.stderr.write(f"docspec: retire move anomaly (src={src.exists()} dest_ok={dest.is_dir()})\n")
        return 1

    print(f"retire-section: \"{section}\" retired -> {dest.relative_to(layout.project_root)}")
    print(f"  one-liner: {note}")
    print(f"  link (archive): {archive_link}")
    print("  content is recoverable; query with docspec retired, the engine already ignores the archive.")
    return 0
