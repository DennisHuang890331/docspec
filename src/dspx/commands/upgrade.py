r"""docspec upgrade — 對齊資產層（TinyTeX/字型/tlmgr 套件）到當前 tex.lock 期望。

兩軌更新心智：
  - 程式（dspx wheel）→ 用 uv 換 wheel：`uv tool install … --reinstall --no-cache`。
  - 資產（TinyTeX/字型/套件）→ docspec 自管，本指令對齊隨包期望（_MANIFEST/_TEX_PACKAGES/
    REQUIRED_FONT_FILES）。

本質＝「補齊 setup 缺的部分」：大量重用 setup 的冪等安裝邏輯（已裝跳過、只補缺），
故 upgrade 對健康環境是 no-op、對缺件環境補齊、改版（程式帶新 _MANIFEST tag）後重抓。

★只碰資產層、不更新程式碼。最後印一行：程式請用 uv 重裝。
"""

from __future__ import annotations

import argparse
import platform
import sys

from dspx import paths
from dspx.commands import setup as setup_cmd

NAME = "upgrade"
HELP = "Align typesetting assets (TinyTeX/fonts/tlmgr packages) to the bundled expectations (idempotent; does not update program code)"

_PROGRAM_UPDATE_HINT = (
    "Program code (the dspx wheel) is not updated by upgrade — use: "
    "uv tool install --from <docspec path or PyPI> docspec --reinstall --no-cache"
)


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec upgrade", description=HELP)
    parser.add_argument("--force", action="store_true",
                        help="ignore idempotency, re-fetch TinyTeX and re-copy fonts")
    parser.add_argument("--no-download", action="store_true",
                        help="do not download TinyTeX (use existing data_dir or dev shortcut only)")
    parser.add_argument("--no-dev-shortcut", action="store_true",
                        help="do not copy from dev /tmp/ttx (force the real download path)")
    args = parser.parse_args(argv)

    pkey = setup_cmd._platform_key()
    if pkey is None:
        sys.stderr.write(
            f"docspec: unsupported platform ({platform.system()}/{platform.machine()})"
            " — not covered by the TinyTeX manifest.\n")
        return 1

    try:
        dd = paths.data_dir()
    except Exception as exc:  # noqa: BLE001 — platformdirs 缺席等
        sys.stderr.write(f"docspec: cannot resolve data_dir ({exc}) — make sure platformdirs is installed.\n")
        return 1

    print(f"docspec upgrade (platform={pkey}) → aligning the asset layer in data_dir: {dd}")

    # 1+2. TinyTeX（冪等：已裝齊跳過；程式帶新 _MANIFEST tag → 由 setup 邏輯判定重抓）
    if not setup_cmd._ensure_tinytex(
        pkey, force=args.force, no_download=args.no_download,
        use_dev_shortcut=not args.no_dev_shortcut,
    ):
        sys.stderr.write("docspec: TinyTeX alignment did not complete — upgrade aborted.\n")
        return 1
    tlmgr = paths.tlmgr_path(paths.tinytex_root())
    if tlmgr is None:
        sys.stderr.write("docspec: TinyTeX is in place but tlmgr was not found — the install may be incomplete.\n")
        return 1

    # 3. tlmgr 套件（補當前 _TEX_PACKAGES 缺的）
    ok, packages = setup_cmd._ensure_packages(tlmgr)
    if not ok:
        sys.stderr.write("docspec: tlmgr package alignment did not complete (possibly offline/mirror issue) — upgrade aborted.\n")
        return 1

    # 4. 字型（補當前 REQUIRED_FONT_FILES 缺的）
    if not setup_cmd._ensure_fonts(force=args.force):
        return 1

    # 5. pandoc（補當前 _PANDOC_MANIFEST 期望；程式帶新 tag → 重抓）
    if not setup_cmd._ensure_pandoc(force=args.force, no_download=args.no_download):
        sys.stderr.write("docspec: pandoc alignment did not complete — upgrade aborted.\n")
        return 1

    # 6. 重寫 tex.lock 指紋（資產層對齊後更新；doctor 之後比對的就是這份）
    xelatex = paths.resolve_xelatex()
    pandoc = paths.resolve_pandoc()
    setup_cmd._write_lock(tlmgr, xelatex, packages, pandoc)

    print(f"\n✓ upgrade complete (asset layer aligned). tex.lock: {paths.tex_lock_path()}")
    print(f"  xelatex: {xelatex}")
    print(f"  pandoc: {pandoc}")
    print(f"\n{_PROGRAM_UPDATE_HINT}")
    return 0
