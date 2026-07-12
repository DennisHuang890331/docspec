r"""pandoc 安裝 — 釘版受控 binary（確定性輸出，不靠系統 pandoc）。

為什麼 pandoc 也釘版進 data_dir（而非靠系統 apt/brew）：pandoc 版本影響輸出
（lua filter、--shift-heading-level、pandoc-data 模板跨大版本會壞），系統 pandoc
各發行版版本不一，會打臉「釘死工具鏈→確定性 + byte-lock」的整套設計。故與 TinyTeX
/字型同級：釘版、sha256 驗證、解出 binary 進 data_dir/pandoc。
"""

from __future__ import annotations

import hashlib
import os
import platform
import sys
import tarfile
import zipfile
from pathlib import Path

from dspx.engine import paths

# 來源＝jgm/pandoc release 的 standalone binary（靜態、無系統依賴）。直接組 release
# 下載 URL（不查 API；釘了完整 asset 名＋sha256，URL pattern 穩定）。
# macOS 分 arm64/x86_64（TinyTeX universal 不分、pandoc 要分）→ key 比 _platform_key 細。
# 升級＝改 tag＋抓新 asset 名與 sha256（Phase F upgrade）。
_PANDOC_REPO = "jgm/pandoc"
_PANDOC_MANIFEST = {
    "tag": "3.10",
    # pandoc-platform-key → (release-asset 完整檔名, sha256)。
    "assets": {
        "windows":       ("pandoc-3.10-windows-x86_64.zip", "bb808d00fd58762299d64582a9b4c3e4b106cd929e62c5f19bcdcb496f1e54ae"),
        "linux-x86_64":  ("pandoc-3.10-linux-amd64.tar.gz", "e0f8af62d0f267d22baa5bcefe6d5dda3a097ccc60de794b759fe03159923244"),
        "linux-arm64":   ("pandoc-3.10-linux-arm64.tar.gz", "55413dfb0c1aec861641fe858f1f73e84848f3db497b1c0c02e62887ea76f4a4"),
        "darwin-arm64":  ("pandoc-3.10-arm64-macOS.zip",    "d9cad01d96ae774a0dc8c8c45bb1ad3e4c5ff2cc2e24f45958f5f9b7974aee34"),
        "darwin-x86_64": ("pandoc-3.10-x86_64-macOS.zip",   "6334f4d9af7c9e37e761dfad56fa5507685f6d29724ebf31c4be6d5c654a3161"),
    },
}


# ── pandoc（釘版受控 binary；解出單一執行檔進 data_dir/pandoc）──────────

def _extract_pandoc_binary(archive: Path, exe_name: str, target: Path) -> bool:
    """從已驗 sha256 的 release 壓縮檔解出 pandoc 執行檔到 target（.zip / .tar.gz 兩路）。

    壓縮檔內含 `pandoc-<ver>[/bin]/pandoc[.exe]` ＋ pandoc-lua/pandoc-server——只取
    basename 等於 exe_name 的那一個（不要 lua/server）。
    """
    import shutil
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        if archive.name.endswith(".zip"):
            with zipfile.ZipFile(archive) as zf:
                member = next((n for n in zf.namelist()
                               if not n.endswith("/") and Path(n).name == exe_name), None)
                if member is None:
                    sys.stderr.write(f"docspec: {exe_name} not found in {archive.name}.\n")
                    return False
                with zf.open(member) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out)
        else:
            with tarfile.open(archive) as tf:
                member = next((m for m in tf.getmembers()
                               if m.isfile() and Path(m.name).name == exe_name), None)
                if member is None:
                    sys.stderr.write(f"docspec: {exe_name} not found in {archive.name}.\n")
                    return False
                src = tf.extractfile(member)
                if src is None:
                    return False
                with src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out)
    except (zipfile.BadZipFile, tarfile.TarError, OSError) as exc:
        sys.stderr.write(f"docspec: failed to extract pandoc ({archive.name}): {exc}\n")
        return False
    if os.name != "nt":
        target.chmod(0o755)  # tar/zip extractfile 不保留執行位元
    return True


def _ensure_pandoc(*, force: bool, no_download: bool) -> bool:
    """把釘版 pandoc binary 放進 data_dir/pandoc。冪等：已在就跳過。"""
    # 透過套件頂層取得可被 monkeypatch 的名字（_pandoc_platform_key/_PANDOC_MANIFEST/
    # _download），確保測試對 `setup_cmd.X` 的 patch 對這裡的呼叫生效。
    from dspx.commands.maintenance import setup as _pkg
    pkey = _pkg._pandoc_platform_key()
    if pkey is None:
        sys.stderr.write(
            f"docspec: the pandoc manifest does not cover this platform ({platform.system()}/{platform.machine()}).\n")
        return False

    exe_name = paths.pandoc_exe_name()
    target = paths.pandoc_dir() / exe_name
    if not force and target.is_file():
        print(f"  pandoc already at {target} (skipping download)")
        return True

    if no_download:
        sys.stderr.write("docspec: --no-download given and no pandoc in data_dir — aborting.\n")
        return False

    manifest = _pkg._PANDOC_MANIFEST
    asset_name, sha = manifest["assets"][pkey]
    url = f"https://github.com/{_PANDOC_REPO}/releases/download/{manifest['tag']}/{asset_name}"
    cache = paths.cache_dir()
    pkg = cache / asset_name
    if pkg.is_file():
        if hashlib.sha256(pkg.read_bytes()).hexdigest() != sha:
            pkg.unlink(missing_ok=True)
    if not pkg.is_file():
        print(f"  Downloading pandoc: {asset_name} ({manifest['tag']}) …")
        if not _pkg._download(url, pkg, sha):
            return False
    if not _extract_pandoc_binary(pkg, exe_name, target):
        return False
    print(f"  pandoc ready in {target}")
    return True
