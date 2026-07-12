r"""docspec setup — 把受控 render 工具鏈裝進 data_dir（冪等）。

讓 `docspec export`/`proof` 不依賴 dev 環境，且字型移出 wheel。

**核心（永遠裝）＝字型 + pandoc + typst（預設 render 引擎）**：
  1. 字型放 data_dir/fonts：主路＝從 _FONT_MANIFEST 的 pinned OFL URL 下載 zip→驗 sha256
     →解出需要的字型檔；快路/離線後備＝偵測到 dev 源樹/DOCSPEC_FONTS_SRC 就 copy。
     （兩軌共用：Typst --font-path ＋ 期刊 xelatex。）
  2. pandoc：釘版受控 binary（版本+sha256 釘在 _PANDOC_MANIFEST）→ data_dir/pandoc。
  3. typst：釘版受控 binary（_TYPST_MANIFEST）→ data_dir/typst。輕量(~22MB)、原生 CJK。

**選用（旗標才裝）**：
  - `--with-latex`：受控 TinyTeX(xelatex) + tlmgr 套件 → data_dir/tinytex。**只給想在本機用
    受控 toolchain 自行編譯 emit 出的期刊 `.tex` 的人**；預設 Typst 軌與 emit-only 期刊軌都
    不自編 LaTeX，故核心不再硬塞數百 MB 的 TinyTeX。
  - `--with-drawio`：受控 draw.io 可攜版 → data_dir/drawio（供 dspx-diagram subagent 渲圖）。

最後寫 tex.lock（各工具版本＋路徑＋tlmgr 套件清單），供 doctor 比對。
soft-dep/網路失敗 → 清楚報錯、回 1、不 crash。不需要 docspec 專案（全域工具設定）。

此檔案為 setup 子套件的入口＋CLI 主流程；各受控依賴的安裝邏輯分在同夾的
`_shared`/`_tinytex`/`_fonts`/`_pandoc`/`_typst`/`_drawio` 模組（純內部拆分、
零行為改變）。以下 re-export 讓 `dspx.commands.maintenance.setup.<name>` 對外行為與拆分前
的單一 `setup.py` 完全相同（含測試的 `monkeypatch.setattr(setup_cmd.urllib.request, …)`
等 module-level stdlib attribute patch 仍然生效）。
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from dspx import paths

from ._drawio import (
    _DRAWIO_MANIFEST,
    _DRAWIO_MIN_VERSION,
    _DRAWIO_REPO,
    _check_linux_drawio_runtime,
    _drawio_version,
    _ensure_drawio,
    _extract_drawio,
)
from ._fonts import (
    _FONT_FILE_SOURCE,
    _FONT_MANIFEST,
    _copy_from_local_source,
    _download_font_source,
    _ensure_fonts,
    _extract_fonts_from_zip,
)
from ._pandoc import (
    _PANDOC_MANIFEST,
    _PANDOC_REPO,
    _ensure_pandoc,
    _extract_pandoc_binary,
)
from ._shared import (
    _download,
    _extract_tar,
    _extract_windows_exe,
    _normalize_extracted_root,
    _pandoc_platform_key,
    _platform_key,
    _resolve_asset,
    _version_tuple,
    _write_lock,
)
from ._tinytex import (
    _MANIFEST,
    _TEX_PACKAGES,
    _TINYTEX_REPO,
    _dev_tinytex_shortcut,
    _ensure_packages,
    _ensure_tinytex,
    _file_resolvable,
    _installed_packages,
    _kpsewhich,
    _missing_packages,
    _run_tlmgr,
)
from ._typst import _TYPST_MANIFEST, _TYPST_REPO, _ensure_typst

NAME = "setup"
HELP = "Install the controlled render toolchain (fonts + pandoc + typst) into data_dir; TinyTeX is optional via --with-latex (idempotent)"


# ── 主流程 ────────────────────────────────────────────────────────

def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec setup", description=HELP)
    parser.add_argument("--force", action="store_true",
                        help="ignore idempotency, reinstall TinyTeX and re-copy fonts")
    parser.add_argument("--no-download", action="store_true",
                        help="do not download TinyTeX (use existing data_dir or dev shortcut only)")
    parser.add_argument("--no-dev-shortcut", action="store_true",
                        help="do not copy from dev /tmp/ttx (force the real download path)")
    parser.add_argument("--with-drawio", action="store_true",
                        help="also install the optional managed draw.io desktop binary (for diagram rendering)")
    parser.add_argument("--with-latex", action="store_true",
                        help="also install the optional managed TinyTeX (xelatex) + tlmgr packages — "
                             "only needed to locally compile an emitted journal .tex (the default Typst track does not use it)")
    args = parser.parse_args(argv)

    pkey = _platform_key()
    if pkey is None:
        sys.stderr.write(
            f"docspec: unsupported platform ({platform.system()}/{platform.machine()})"
            " — not covered by the TinyTeX manifest.\n")
        return 1

    if platform.system() == "Darwin":
        # macOS 的下載/解壓/字型路徑在程式碼裡是齊的（manifest + 平台 key），但尚未在真實
        # Mac 硬體上跑過一輪端到端驗證（只在 Windows/Linux 實測過）——先誠實提醒，不擋。
        sys.stderr.write(
            "docspec: note — macOS is not yet verified on real hardware "
            "(only Windows and Linux are tested); setup will proceed but may hit "
            "untested edge cases. Reports welcome.\n")

    try:
        dd = paths.data_dir()
    except Exception as exc:  # noqa: BLE001 — platformdirs 缺席等
        sys.stderr.write(f"docspec: cannot resolve data_dir ({exc}) — make sure platformdirs is installed.\n")
        return 1

    print(f"docspec setup (platform={pkey}) → data_dir: {dd}")

    # 核心受控工具鏈（永遠裝）＝ fonts + pandoc + typst（預設 render 引擎）。
    # TinyTeX（LaTeX 軌）是 OPTIONAL、只在 `--with-latex` 才裝——預設 Typst 軌與 emit-only
    # 期刊軌都不自編 LaTeX，故核心 setup 不再硬塞數百 MB 的 TinyTeX。

    # 1. 字型（兩軌共用：Typst --font-path ＋ 期刊 xelatex）
    if not _ensure_fonts(force=args.force, no_download=args.no_download):
        return 1

    # 2. pandoc（受控 binary；確定性輸出，不靠系統 pandoc）
    if not _ensure_pandoc(force=args.force, no_download=args.no_download):
        sys.stderr.write("docspec: pandoc install did not complete — setup aborted.\n")
        return 1

    # 3. typst（受控 binary；Typst 軌＝預設 render 引擎，輕量、原生 CJK）
    if not _ensure_typst(force=args.force, no_download=args.no_download):
        sys.stderr.write("docspec: typst install did not complete — setup aborted.\n")
        return 1

    # 4. TinyTeX + tlmgr packages — OPTIONAL（--with-latex；只給想本機編期刊 .tex 的人）
    tlmgr: Path | None = None
    xelatex = None
    packages: list[str] = []
    if args.with_latex:
        if not _ensure_tinytex(pkey, force=args.force, no_download=args.no_download,
                               use_dev_shortcut=not args.no_dev_shortcut):
            sys.stderr.write("docspec: TinyTeX install did not complete — setup aborted.\n")
            return 1
        tlmgr = paths.tlmgr_path(paths.tinytex_root())
        if tlmgr is None:
            sys.stderr.write("docspec: TinyTeX is in place but tlmgr was not found — the install may be incomplete.\n")
            return 1
        ok, packages = _ensure_packages(tlmgr)
        if not ok:
            sys.stderr.write("docspec: tlmgr package install did not complete (possibly offline/mirror issue) — setup aborted.\n")
            return 1
        xelatex = paths.resolve_xelatex()

    # 5. draw.io（選用、D8：核心不裝、--with-drawio 才裝；供 dspx-diagram subagent 渲圖）
    if args.with_drawio:
        if not _ensure_drawio(force=args.force, no_download=args.no_download, interactive=True):
            sys.stderr.write("docspec: draw.io install did not complete — setup aborted.\n")
            return 1

    # 6. tex.lock
    pandoc = paths.resolve_pandoc()
    typst = paths.resolve_typst()
    drawio = paths.resolve_drawio()
    _write_lock(tlmgr, xelatex, packages, pandoc, typst, drawio)

    print(f"\n✓ setup complete. tex.lock: {paths.tex_lock_path()}")
    print(f"  typst: {typst}  (default render engine)")
    print(f"  pandoc: {pandoc}")
    if xelatex:
        print(f"  xelatex: {xelatex}  (optional LaTeX track)")
    else:
        print("  xelatex: not installed (run `docspec setup --with-latex` to compile journal .tex locally)")
    if drawio:
        print(f"  draw.io: {drawio}  (optional; diagram rendering)")
    else:
        print("  draw.io: not installed (run `docspec setup --with-drawio` to add diagram rendering)")
    print("  From now on `docspec export <article>` / `docspec proof <article>` run purely off data_dir.")
    return 0
