r"""typst 安裝 — 釘版受控 binary（Typst 軌＝預設 render 引擎）。

來源＝typst/typst release 的 standalone binary（單一靜態執行檔、無系統依賴、~22MB，
比 TinyTeX 輕一個量級）。Windows＝.zip、Linux/macOS＝.tar.xz，內含 typst-<target>/typst[.exe]。
平台 key 複用 _pandoc_platform_key（同樣 windows/linux-*/darwin-* 五鍵）。
升級＝改 tag＋抓新 asset 的 sha256。
"""

from __future__ import annotations

import hashlib
import platform
import sys

from dspx import paths

from ._pandoc import _extract_pandoc_binary

_TYPST_REPO = "typst/typst"
_TYPST_MANIFEST = {
    "tag": "v0.15.0",
    "assets": {
        "windows":       ("typst-x86_64-pc-windows-msvc.zip",      "66ae7f0907b4b9afed5c7d6cb9b21e07f0f3c3d4e293ba3e0026a54d88202fe9"),
        "linux-x86_64":  ("typst-x86_64-unknown-linux-musl.tar.xz", "59b207df01be2dab9f13e80f73d04d7ff8273ffd46b3dd1b9eef5c60f3eeabea"),
        "linux-arm64":   ("typst-aarch64-unknown-linux-musl.tar.xz", "cdf50ffc7b8ba759ed02200632eda3d78eb8b99aacb6611f4f75684990647620"),
        "darwin-x86_64": ("typst-x86_64-apple-darwin.tar.xz",       "30210c7c539c7954db94c063cd98b43fd0a0cad285d656dbbce2a40aee2e79be"),
        "darwin-arm64":  ("typst-aarch64-apple-darwin.tar.xz",      "fe53838737abf93a774495952a1a797b4686e9c4a21c2d99b9fdf77f46cc3572"),
    },
}


def _ensure_typst(*, force: bool, no_download: bool) -> bool:
    """把釘版 typst binary 放進 data_dir/typst（預設 render 引擎）。冪等：已在就跳過。"""
    # 透過套件頂層取得可被 monkeypatch 的名字（同 _pandoc.py 的理由）。
    from dspx.commands import setup as _pkg
    pkey = _pkg._pandoc_platform_key()
    manifest = _pkg._TYPST_MANIFEST
    if pkey is None or pkey not in manifest["assets"]:
        sys.stderr.write(
            f"docspec: the typst manifest does not cover this platform ({platform.system()}/{platform.machine()}).\n")
        return False

    exe_name = paths.typst_exe_name()
    target = paths.typst_dir() / exe_name
    if not force and target.is_file():
        print(f"  typst already at {target} (skipping download)")
        return True

    if no_download:
        sys.stderr.write("docspec: --no-download given and no typst in data_dir — aborting.\n")
        return False

    asset_name, sha = manifest["assets"][pkey]
    url = f"https://github.com/{_TYPST_REPO}/releases/download/{manifest['tag']}/{asset_name}"
    cache = paths.cache_dir()
    pkg = cache / asset_name
    if pkg.is_file() and hashlib.sha256(pkg.read_bytes()).hexdigest() != sha:
        pkg.unlink(missing_ok=True)
    if not pkg.is_file():
        print(f"  Downloading typst: {asset_name} ({manifest['tag']}) …")
        if not _pkg._download(url, pkg, sha):
            return False
    # 解出 typst 執行檔（reuse pandoc 的通用 by-basename 解壓；tar.xz 由 tarfile 自動偵測）。
    if not _extract_pandoc_binary(pkg, exe_name, target):
        return False
    print(f"  typst ready in {target}")
    return True
