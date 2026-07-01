r"""setup 子套件共用工具：平台偵測、release asset 解析、下載、tex.lock 寫入。

供 _tinytex/_fonts/_pandoc/_typst/_drawio 各模組共用。
"""

from __future__ import annotations

import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.error
import urllib.request
from pathlib import Path

from dspx import paths


# ── 平台偵測 ──────────────────────────────────────────────────────

def _platform_key() -> str | None:
    """回 _MANIFEST.assets 的鍵，未支援 → None。"""
    sysname = platform.system()
    mach = platform.machine().lower()
    if sysname == "Windows":
        return "windows"
    if sysname == "Darwin":
        return "darwin"  # TinyTeX darwin 是 universal
    if sysname == "Linux":
        if mach in ("x86_64", "amd64"):
            return "linux-x86_64"
        if mach in ("aarch64", "arm64"):
            return "linux-arm64"
    return None


def _pandoc_platform_key() -> str | None:
    """回 _PANDOC_MANIFEST.assets 的鍵；macOS 須分 arm64/x86_64。未支援 → None。"""
    sysname = platform.system()
    mach = platform.machine().lower()
    if sysname == "Windows":
        return "windows"  # pandoc Windows 只出 x86_64（ARM 走模擬）
    if sysname == "Darwin":
        return "darwin-arm64" if mach in ("arm64", "aarch64") else "darwin-x86_64"
    if sysname == "Linux":
        if mach in ("x86_64", "amd64"):
            return "linux-x86_64"
        if mach in ("aarch64", "arm64"):
            return "linux-arm64"
    return None


# ── release asset 解析（不寫死檔名）────────────────────────────────

def _resolve_asset(tag: str, name_substr: str) -> tuple[str, str] | None:
    """從 GitHub release API 按 tag 找 asset；回 (download_url, asset_name)。

    名稱靠 substr＋tag 命中（不寫死完整檔名）。網路/解析失敗 → None。
    """
    from ._tinytex import _TINYTEX_REPO
    api = f"https://api.github.com/repos/{_TINYTEX_REPO}/releases/tags/{tag}"
    try:
        req = urllib.request.Request(api, headers={"Accept": "application/vnd.github+json",
                                                   "User-Agent": "docspec-setup"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        sys.stderr.write(f"docspec: cannot query TinyTeX release ({api}): {exc}\n")
        return None
    for asset in data.get("assets", []):
        nm = asset.get("name", "")
        if nm.startswith(name_substr) and tag in nm:
            return asset.get("browser_download_url", ""), nm
    sys.stderr.write(f"docspec: release {tag} has no asset matching \"{name_substr}*{tag}*\".\n")
    return None


def _download(url: str, dest: Path, expect_sha256: str) -> bool:
    """下載 url → dest，驗 sha256。失敗（含驗證不符）→ 清掉半成品、回 False。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "docspec-setup"})
        with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, "wb") as fh:
            shutil.copyfileobj(resp, fh)
    except (urllib.error.URLError, OSError) as exc:
        sys.stderr.write(f"docspec: download failed ({url}): {exc}\n")
        tmp.unlink(missing_ok=True)
        return False
    h = hashlib.sha256()
    with open(tmp, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    if h.hexdigest() != expect_sha256:
        sys.stderr.write(
            f"docspec: sha256 verification failed ({dest.name}): got {h.hexdigest()}, expected {expect_sha256}.\n")
        tmp.unlink(missing_ok=True)
        return False
    tmp.replace(dest)
    return True


def _normalize_extracted_root(target_root: Path) -> bool:
    """把剛解出的 TinyTeX 安裝層正規化成 target_root（data_dir/tinytex）。

    平台差異：Windows SFX 解出 `TinyTeX/`，但 Linux/mac 官方 tar 解出**隱藏的
    `.TinyTeX/`**（前綴點）。兩種名字都要認，否則 rename 被跳過、tlmgr 找不到。
    回 True＝target_root 下找得到 tlmgr（安裝完整）。
    """
    if paths.tlmgr_path(target_root) is not None:
        return True  # 已經就位（如直接解到 target_root）
    for name in ("TinyTeX", ".TinyTeX"):
        extracted = target_root.parent / name
        if extracted.is_dir() and extracted != target_root \
                and paths.tlmgr_path(extracted) is not None:
            if target_root.exists():
                shutil.rmtree(target_root)
            extracted.rename(target_root)
            break
    return paths.tlmgr_path(target_root) is not None


def _extract_windows_exe(installer: Path, target_root: Path) -> bool:
    """Windows TinyTeX-1 是 7-zip 自解壓 .exe；用其 -y 旗標解到 target_root。

    自解壓檔解出一層 TinyTeX/。解壓後把該層內容搬成 target_root（data_dir/tinytex）本身。
    """
    target_root.parent.mkdir(parents=True, exist_ok=True)
    # 自解壓 exe：`installer.exe -y -o<dir>`（7-zip SFX 慣例）。
    try:
        subprocess.run([str(installer), "-y", f"-o{target_root.parent}"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, OSError) as exc:
        sys.stderr.write(f"docspec: failed to extract the TinyTeX installer: {exc}\n")
        return False
    return _normalize_extracted_root(target_root)


def _extract_tar(archive: Path, target_root: Path) -> bool:
    """Linux/mac TinyTeX-1 是 .tar.xz/.tar.gz，內含一層 .TinyTeX/，解到 data_dir/tinytex。"""
    target_root.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(archive) as tf:
            tf.extractall(target_root.parent, filter="data")  # noqa: S202 — 官方 release、已驗 sha256
    except (tarfile.TarError, OSError) as exc:
        sys.stderr.write(f"docspec: failed to extract the TinyTeX tar: {exc}\n")
        return False
    return _normalize_extracted_root(target_root)


def _version_tuple(ver: str | None) -> tuple[int, ...] | None:
    """把 "30.2.4" 解析成 (30, 2, 4) 供門檻比較；None/非法 → None。"""
    if not ver:
        return None
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", ver)   # search＝容忍開頭的 "v" 等前綴
    return tuple(int(g) for g in m.groups()) if m else None


# ── tex.lock（指紋；供 doctor 比對）────────────────────────────────

def _write_lock(tlmgr: Path | None, xelatex: Path | None, packages: list[str],
                pandoc: str | None = None, typst: str | None = None,
                drawio: str | None = None) -> None:
    # 透過套件頂層取得可被 monkeypatch 的名字（各 manifest／_drawio_version／
    # _platform_key）——確保測試對 `setup_cmd.X` 的 patch 對這裡的呼叫生效。
    from dspx.commands import setup as _pkg
    lock = {
        "tinytex_tag": _pkg._MANIFEST["tag"],
        "pandoc_tag": _pkg._PANDOC_MANIFEST["tag"],
        "typst_tag": _pkg._TYPST_MANIFEST["tag"],
        "drawio_tag": _pkg._DRAWIO_MANIFEST["tag"],
        "platform": _pkg._platform_key(),
        "tinytex_root": str(paths.tinytex_root()) if tlmgr else None,  # None＝未裝（--with-latex 才裝）
        "tlmgr_path": str(tlmgr) if tlmgr else None,
        "xelatex_path": str(xelatex) if xelatex else None,
        "pandoc_path": str(pandoc) if pandoc else None,
        "typst_path": str(typst) if typst else None,
        "drawio_path": str(drawio) if drawio else None,  # None＝未裝（--with-drawio 才裝）
        "drawio_installed_version": _pkg._drawio_version(drawio) if drawio else None,  # binary 自報；供 doctor 比對漂移
        "fonts_dir": str(paths.fonts_dir()),
        "fonts": list(paths.REQUIRED_FONT_FILES),
        "tlmgr_packages": packages,
    }
    paths.tex_lock_path().write_text(
        json.dumps(lock, ensure_ascii=False, indent=2), encoding="utf-8")
