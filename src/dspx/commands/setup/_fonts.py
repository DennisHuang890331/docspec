r"""字型安裝 — 主路＝從 pinned OFL URL 下載 zip 驗 sha256；快路＝dev 源樹 copy。

兩軌共用：Typst --font-path ＋ 期刊 xelatex。
"""

from __future__ import annotations

import hashlib
import shutil
import sys
import zipfile
from pathlib import Path

from dspx import paths

# ── 字型 manifest（OFL 來源；每來源釘 version＋URL＋zip sha256）─────────────
#
# 主路＝從這些 pinned URL 下載 zip → 驗 zip 的 sha256 → 從 zip 解出需要的字型檔
# （member 為 zip 內完整路徑，basename → REQUIRED_FONT_FILES 之一）。全部 OFL：
#   - Source Serif 4 / Source Sans 3 / Source Code Pro：Adobe 官方 GitHub release
#     的 Desktop/OTF zip（Apache→OFL 1.1，見各 zip 內 LICENSE）。
#   - Source Han Sans TC / Source Han Serif TC（思源黑/宋，↔ CJK fallback）：
#     adobe-fonts/source-han-* release 的 *TC*.zip，取 OTF/TraditionalChinese/。
#   - TW-Kai 全字庫正楷體：政府 cns11643 Open Data 的 Fonts_Kai.zip（GODL 1.0 或
#     OFL 1.1 任選；canonical 來源，URL 穩定）。
# 升級＝改 ver＋url＋抓新 sha256（仿 TinyTeX 的釘法）。下載後 byte 級驗證 zip 整體
# sha256，再解 member——故不需逐檔 hash（zip 驗證即覆蓋其內容）。
#
# 每筆：(version, url, zip_sha256, {zip 內 member 路徑 → 落地檔名}).
_FONT_MANIFEST = {
    "source-serif": (
        "4.005R",
        "https://github.com/adobe-fonts/source-serif/releases/download/4.005R/source-serif-4.005_Desktop.zip",
        "549fdb8f9a682bd06944298621404969f6de77c2e422ff3b8244a1dcd6a0c425",
        {
            "source-serif-4.005_Desktop/OTF/SourceSerif4-Regular.otf": "SourceSerif4-Regular.otf",
            "source-serif-4.005_Desktop/OTF/SourceSerif4-Bold.otf":    "SourceSerif4-Bold.otf",
            "source-serif-4.005_Desktop/OTF/SourceSerif4-It.otf":      "SourceSerif4-It.otf",
            "source-serif-4.005_Desktop/OTF/SourceSerif4-BoldIt.otf":  "SourceSerif4-BoldIt.otf",
        },
    ),
    "source-sans": (
        "3.052R",
        "https://github.com/adobe-fonts/source-sans/releases/download/3.052R/OTF-source-sans-3.052R.zip",
        "a4ebbdea20b08ccbd7bf3665a9462454eefdd01d9a6307129d3b3d4672981074",
        {
            "OTF/SourceSans3-Regular.otf": "SourceSans3-Regular.otf",
            "OTF/SourceSans3-Bold.otf":    "SourceSans3-Bold.otf",
            "OTF/SourceSans3-It.otf":      "SourceSans3-It.otf",
            "OTF/SourceSans3-BoldIt.otf":  "SourceSans3-BoldIt.otf",
        },
    ),
    "source-code-pro": (
        "2.042R-u",
        "https://github.com/adobe-fonts/source-code-pro/releases/download/2.042R-u/1.062R-i/1.026R-vf/OTF-source-code-pro-2.042R-u_1.062R-i.zip",
        "754a2e3ebb945ae905d720ac5896b3b34acc9546dd6551ef9536869788629dae",
        {
            "OTF/SourceCodePro-Regular.otf": "SourceCodePro-Regular.otf",
            "OTF/SourceCodePro-Bold.otf":    "SourceCodePro-Bold.otf",
            "OTF/SourceCodePro-It.otf":      "SourceCodePro-It.otf",
            "OTF/SourceCodePro-BoldIt.otf":  "SourceCodePro-BoldIt.otf",
        },
    ),
    "source-han-sans-tc": (
        "2.005R",
        "https://github.com/adobe-fonts/source-han-sans/releases/download/2.005R/10_SourceHanSansTC.zip",
        "28058dc7d729560c5fa5c850e7298905cac8de55c1e33cfd5cb13e3d7408989e",
        {
            "OTF/TraditionalChinese/SourceHanSansTC-Regular.otf": "SourceHanSansTC-Regular.otf",
            "OTF/TraditionalChinese/SourceHanSansTC-Bold.otf":    "SourceHanSansTC-Bold.otf",
        },
    ),
    "source-han-serif-tc": (
        "2.003R",
        "https://github.com/adobe-fonts/source-han-serif/releases/download/2.003R/10_SourceHanSerifTC.zip",
        "c3f741e2da0d553ef729404a7be2febb3679245a918a6f47994cd863ddb268b3",
        {
            "OTF/TraditionalChinese/SourceHanSerifTC-Regular.otf": "SourceHanSerifTC-Regular.otf",
            # SemiBold＝CJK 內文粗體（**emphasis**）fallback：宋體 body 的粗體用思源宋 SemiBold
            # （同族、比 Bold 輕、優雅；Bold 過黑故不用）。
            "OTF/TraditionalChinese/SourceHanSerifTC-SemiBold.otf": "SourceHanSerifTC-SemiBold.otf",
        },
    ),
    "tw-kai": (
        "98.1",
        "https://www.cns11643.gov.tw/opendata/Fonts_Kai.zip",
        "d03cc7960f5204b50da1a33a4537242f45bd96370ef169f2c9010d79353e9228",
        {
            "TW-Kai-98_1.ttf": "TW-Kai-98_1.ttf",
        },
    ),
    # 霞鶩文楷 TC（LXGW WenKai TC）：手寫楷風、OFL 1.1。內文 cjk_body 候選。
    "lxgw-wenkai-tc": (
        "1.522",
        "https://github.com/lxgw/LxgwWenkaiTC/releases/download/v1.522/lxgw-wenkai-tc-v1.522.zip",
        "1c3021d72c2000fdbad219bbf093a7a20fe1f8de7699ca4b4017192afe2b542f",
        {
            "lxgw-wenkai-tc-v1.522/LXGWWenKaiTC-Regular.ttf": "LXGWWenKaiTC-Regular.ttf",
        },
    ),
    # 全字庫正宋體（TW-Sung）：宋體、政府開放資料/OFL。內文 cjk_body 候選。
    # ⚠ 來源是「不帶版本的 latest」gov URL → 政府改檔時 zip_sha256 會漂；不符時 setup 會擋，
    #   屆時重新下載一次、更新此 hash（與 tw-kai 同情況）。
    "tw-sung": (
        "98.1",
        "https://www.cns11643.gov.tw/opendata/Fonts_Sung.zip",
        "25cb90ddf7c98bfeebd9e88a79c63dcde7eaaf81409a15b323ace744bade7867",
        {
            "TW-Sung-98_1.ttf": "TW-Sung-98_1.ttf",
        },
    ),
}

# 落地檔名 → 來源 key，反查供「只補缺檔」時挑要下載哪些 zip。
_FONT_FILE_SOURCE = {
    target: key
    for key, (_v, _u, _s, members) in _FONT_MANIFEST.items()
    for target in members.values()
}


# ── 字型（主路＝OFL pinned URL 下載；快路＝dev/源樹 copy）──────────────

def _copy_from_local_source(dest: Path, wanted: list[str], *, force: bool) -> int:
    """快路/離線後備：偵測到 dev 源樹/DOCSPEC_FONTS_SRC 字型夾就 copy（免下載）。

    回 copy 的檔數（0＝沒有本地來源、或無可補檔）。
    """
    src = paths._bundled_fonts_dir()
    if src is None or not src.is_dir():
        return 0
    copied = 0
    for fname in wanted:
        sp = src / fname
        if sp.is_file() and (force or not (dest / fname).is_file()):
            shutil.copy2(sp, dest / fname)
            copied += 1
    return copied


def _extract_fonts_from_zip(archive: Path, members: dict[str, str], dest: Path) -> int:
    """從已驗證 sha256 的 zip 解出 members（{zip 內路徑 → 落地檔名}）到 dest。

    回實際寫出的檔數。member 不在 zip 內 → 報該檔、略過（不致命，留給上層判缺）。
    """
    written = 0
    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())
        for inner, target in members.items():
            if inner not in names:
                sys.stderr.write(f"docspec: {inner} not found in zip {archive.name} (skipping).\n")
                continue
            with zf.open(inner) as fh, open(dest / target, "wb") as out:
                shutil.copyfileobj(fh, out)
            written += 1
    return written


def _download_font_source(key: str, dest: Path, *, force: bool) -> bool:
    """下載 _FONT_MANIFEST[key] 的 zip → 驗 sha256 → 解出其 members 到 dest。

    zip 快取在 cache_dir（已快取且 sha 符就重用）。冪等：只在 force 或目標缺時寫出。
    """
    # 透過套件頂層取得 _FONT_MANIFEST/_download（延遲 import 避免循環、且讓
    # `monkeypatch.setattr(setup_cmd, "_FONT_MANIFEST"/"_download", …)` 對呼叫端生效）。
    from dspx.commands import setup as _pkg
    version, url, sha, members = _pkg._FONT_MANIFEST[key]
    cache = paths.cache_dir()
    pkg = cache / f"{key}-{version}.zip"
    if pkg.is_file():
        h = hashlib.sha256(pkg.read_bytes()).hexdigest()
        if h != sha:
            pkg.unlink(missing_ok=True)
    if not pkg.is_file():
        print(f"  Downloading font source: {key} {version} …")
        if not _pkg._download(url, pkg, sha):
            return False
    # 只解尚缺（或 force）的 member
    todo = {inner: target for inner, target in members.items()
            if force or not (dest / target).is_file()}
    if not todo:
        return True
    return _extract_fonts_from_zip(pkg, todo, dest) == len(todo)


def _ensure_fonts(*, force: bool, no_download: bool = False) -> bool:
    """把所需字型放進 data_dir/fonts。

    主路＝從 _FONT_MANIFEST 的 pinned OFL URL 下載 zip→驗 sha256→解出需要的檔。
    快路/離線後備＝偵測到 dev 源樹/DOCSPEC_FONTS_SRC 字型夾就直接 copy（免下載）。
    冪等：齊了跳過、只補缺檔。缺檔/網路失敗→清楚報錯回 False。
    """
    dest = paths.fonts_dir()
    dest.mkdir(parents=True, exist_ok=True)

    have = {f for f in paths.REQUIRED_FONT_FILES if (dest / f).is_file()}
    if not force and len(have) == len(paths.REQUIRED_FONT_FILES):
        print(f"  Fonts already complete ({len(have)} files) in {dest} (skipping)")
        return True

    wanted = [f for f in paths.REQUIRED_FONT_FILES if force or f not in have]

    # 快路/離線後備：偵測到本地字型夾就先 copy（免下載）。
    copied = _copy_from_local_source(dest, wanted, force=force)
    if copied:
        print(f"  Font fast path: copied {copied} files from a local source → {dest}")

    still = [f for f in paths.REQUIRED_FONT_FILES if not (dest / f).is_file()]
    if not still:
        print(f"  Fonts ready in {dest}")
        return True

    # 主路：從 pinned OFL 來源下載（只抓還缺的檔所屬的來源）。
    if no_download:
        sys.stderr.write(
            "docspec: --no-download given, no local font source, and fonts incomplete — aborting.\n"
            "  Missing: " + ", ".join(still) + "\n")
        return False

    from dspx.commands import setup as _pkg
    need_keys: list[str] = []
    for f in still:
        k = _pkg._FONT_FILE_SOURCE.get(f)
        if k is None:
            sys.stderr.write(f"docspec: font {f} is not in the download manifest — cannot fetch automatically.\n")
            return False
        if k not in need_keys:
            need_keys.append(k)

    for k in need_keys:
        if not _download_font_source(k, dest, force=force):
            sys.stderr.write(
                f"docspec: font source \"{k}\" download/extraction did not complete — setup aborted.\n")
            return False

    still_missing = [f for f in paths.REQUIRED_FONT_FILES if not (dest / f).is_file()]
    if still_missing:
        sys.stderr.write(
            "docspec: fonts still missing (incomplete after download): " + ", ".join(still_missing) + "\n")
        return False
    print(f"  Fonts ready (including downloads) in {dest}")
    return True
