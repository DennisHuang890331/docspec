r"""docspec template — 管理 export 模板包。

子指令：
  eject  把 bundled `docspec-typst` 包複製到專案 `docspec/template-pack/`（可編輯的 BYO 包），
         寫 provenance（`.ejected-from.json` 記 dspx 版本）、把 `export.template` 寫回 config.yaml，
         此後 export 自動用此包走 Typst 軌**且跳過 hash 閘**（使用者自有包合法可改）。
         排除 `.pack-hashes.json`（ejected 包不受閘管、留著徒增困惑）；`fonts/` 本就不在包內。
         目標夾已存在→拒（非零、不動任何檔），`--force` 才覆蓋。

eject 是**專案設定操作**（非 export 旗標——它不吃 article）：正當客製走這裡，bundled 包的
hash 閘因此不必降級。
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import yaml

from dspx.engine import paths
from dspx.commands._shared import BootstrapError, bootstrap
from dspx.engine.config import CONFIG_FILE_NAME

NAME = "template"
HELP = "Manage the export template pack (eject: copy the bundled docspec-typst pack into the project for editing)"

# 專案內 ejected 包的相對位置（相對專案根；planning home 是 `docspec/`）。
_EJECT_REL = "docspec/template-pack"
_PROVENANCE_FILE = ".ejected-from.json"


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec template", description=HELP)
    sub = parser.add_subparsers(dest="subcommand")
    ej = sub.add_parser(
        "eject", help="copy the bundled docspec-typst pack into docspec/template-pack/ for editing")
    ej.add_argument("--force", action="store_true",
                    help="overwrite an existing docspec/template-pack/")
    args = parser.parse_args(argv)

    if args.subcommand == "eject":
        return _eject(force=args.force)
    parser.print_help()
    return 2


def _eject(force: bool) -> int:
    try:
        layout, _config = bootstrap()
    except BootstrapError as exc:
        return exc.exit_code

    src = paths.bundled_typst_template_dir()
    if src is None or not (src / "template.typ").is_file():
        sys.stderr.write(
            "docspec: bundled Typst template pack not found (assets/templates/docspec-typst/) — "
            "the install may be incomplete.\n")
        return 1

    dest = layout.planning_home / "template-pack"
    if dest.exists() and not force:
        sys.stderr.write(
            f"docspec: {dest} already exists — nothing overwritten. Use --force to overwrite "
            "(you will lose local edits to that pack).\n")
        return 1
    if dest.exists():
        shutil.rmtree(dest)

    # 複製整包，排除 `.pack-hashes.json`（ejected 包不受閘管）。fonts/ 本就不在包內。
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns(paths.PACK_HASHES_FILE))

    # provenance：記 eject 當下的 dspx 版本（export 據此印落後提示）。
    from dspx import __version__
    (dest / _PROVENANCE_FILE).write_text(
        json.dumps({"version": __version__, "pack": "docspec-typst"},
                   ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")

    # config.yaml 記 export.template（相對專案根；export 無 --template 時作為預設模板夾）。
    _record_export_template(layout.planning_home / CONFIG_FILE_NAME, _EJECT_REL)

    print(f"Ejected the bundled docspec-typst pack → {dest}")
    print(f"  Recorded export.template: {_EJECT_REL} in {CONFIG_FILE_NAME} "
          "(exports now use this editable pack on the Typst track, skipping the integrity gate).")
    print("  Edit template.typ to change the layout; after upgrading docspec, re-eject with "
          "`docspec template eject --force` to pick up template fixes.")
    return 0


def _record_export_template(config_path: Path, rel: str) -> None:
    """把 `export.template: <rel>` 寫回專案 config.yaml（保留其他鍵；壞/缺檔則新建最小 mapping）。"""
    data: object = {}
    if config_path.is_file():
        try:
            data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            data = {}
    if not isinstance(data, dict):
        data = {}
    export = data.get("export")
    if not isinstance(export, dict):
        export = {}
    export["template"] = rel
    data["export"] = export
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8", newline="\n")
