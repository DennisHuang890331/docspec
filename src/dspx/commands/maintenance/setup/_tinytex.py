r"""TinyTeX（xelatex）+ tlmgr 套件安裝 — optional，只在 `--with-latex` 才裝。

只給想在本機用受控 toolchain 自行編譯 emit 出的期刊 `.tex` 的人；預設 Typst 軌
與 emit-only 期刊軌都不自編 LaTeX。
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

from dspx import paths

from ._shared import (
    _download,
    _extract_tar,
    _extract_windows_exe,
    _resolve_asset,
)

# ── 釘版 manifest（版本＋每平台 sha256；asset 名不寫死、靠 release API 解析）────
#
# 來源＝rstudio/tinytex-releases 官方 release（TinyTeX-1＝medium scheme，含 xelatex
# ＋一批常用套件，再用 tlmgr 補齊 docspec-cas 依賴）。sha256 為官方 release 公布之 digest，
# 下載後 byte 級驗證。要升級＝改 _MANIFEST 的 tag＋抓新 digest（Phase F doctor/upgrade）。
_TINYTEX_REPO = "rstudio/tinytex-releases"
_MANIFEST = {
    "tag": "v2026.06",
    # platform-key → (release-asset-檔名-pattern 子串, sha256)。
    # 解析時以「子串 + tag」命中 release asset，不寫死完整檔名（避免 release 改名炸）。
    "assets": {
        "windows":         ("TinyTeX-1-windows-",        "9e8b35509374af7160c5b2f681005c4730b73fa037d97bcbea6aa274fd3350fa"),
        "linux-x86_64":    ("TinyTeX-1-linux-x86_64-",   "8928c620301fe959ec41e8cdd0e1c6113d739c0207c5851807213d5336898fca"),
        "linux-arm64":     ("TinyTeX-1-linux-arm64-",    "1392e1e90b971ca604686643da2f9dacc8836e007a7550a522bc8d184cd9464e"),
        "darwin":          ("TinyTeX-1-darwin-",         "b73fa9202fc3f80e634290464b98bc0251ebbe87a47bea8c9b3983e754f3605d"),
    },
}

# tlmgr 要補裝的 TeX 套件集——僅供 optional `--with-latex` 本機編譯期刊軌 emit 出的 `.tex`
# 使用（Typst 預設軌不需要 TinyTeX）。涵蓋期刊模板/xelatex/xeCJK 鏈常用依賴。
# TinyTeX-1 medium scheme 多半已含，install 對已裝者 no-op。缺的才裝。
_TEX_PACKAGES = [
    "xecjk", "fontspec", "framed", "fvextra", "tabularx", "xltabular",
    "ltablex",  # xltabular 的依賴（提供 ltablex.sty）；TinyTeX medium scheme 含 xltabular
                # 卻不含 ltablex，tlmgr 裝 xltabular 時又因「已存在」沒拉依賴 → Linux 實編
                # 撞 `ltablex.sty not found`（Windows medium scheme 剛好含故未爆，Linux 真測抓到）。
    "seqsplit", "etoolbox", "enumitem", "tcolorbox", "environ", "trimspaces",
    "pgf",  # TikZ 繪圖支援（tikz.sty 與各 tikzlibrary 都在 pgf bundle 內），供期刊軌 .tex 本機編譯時用得到
    "lastpage",  # 頁尾「Page X of N」總頁數所需的 \pageref{LastPage} 支援

    "booktabs", "colortbl", "makecell", "multirow", "stix", "inconsolata",
    "dcolumn", "footmisc", "xstring", "xspace", "needspace",
    # 期刊軌常見的 elsarticle/citation 鏈依賴：
    "natbib", "elsarticle", "moreverb", "wrapfig", "setspace",
    "sttools",  # 提供 stfloats.sty；TL 套件名＝sttools，非 stfloats（後者只是 .sty 檔名）。
                # 誤用 stfloats 會「not present in repository」讓整批 tlmgr install 回非零、setup
                # 中止（Linux 真測抓到，Windows medium scheme 已含故未爆）。
    "l3packages", "l3kernel", "amsmath", "amsfonts",
]
# 註：stix/inconsolata 留作數學符號／等寬字型的 fallback；其餘為期刊軌 .tex 本機編譯的常用依賴。


# ── TinyTeX 安裝（解壓到 data_dir/tinytex）─────────────────────────

def _dev_tinytex_shortcut() -> Path | None:
    """偵測既有 dev TinyTeX（/tmp/ttx、%TEMP%/ttx）可 copy 進 data_dir 免重抓。"""
    for root in paths.dev_tinytex_roots():
        if root.is_dir() and paths.tlmgr_path(root) is not None:
            return root
    return None


def _ensure_tinytex(pkey: str, *, force: bool, no_download: bool,
                    use_dev_shortcut: bool) -> bool:
    """確保 data_dir/tinytex 有可用 TinyTeX（含 tlmgr）。冪等：已裝齊跳過。"""
    import shutil
    root = paths.tinytex_root()
    if not force and paths.tlmgr_path(root) is not None:
        print(f"  TinyTeX already at {root} (skipping download)")
        return True

    # dev 捷徑：copy 既有 /tmp/ttx 進 data_dir（避免重抓大檔）
    if use_dev_shortcut:
        dev = _dev_tinytex_shortcut()
        if dev is not None:
            print(f"  Detected dev TinyTeX ({dev}) → copying into {root}")
            if root.exists():
                shutil.rmtree(root)
            shutil.copytree(dev, root)
            return paths.tlmgr_path(root) is not None

    if no_download:
        sys.stderr.write("docspec: --no-download given, no TinyTeX in data_dir, and no dev shortcut — aborting.\n")
        return False

    substr, sha = _MANIFEST["assets"][pkey]
    resolved = _resolve_asset(_MANIFEST["tag"], substr)
    if resolved is None:
        return False
    url, asset_name = resolved
    cache = paths.cache_dir()
    pkg = cache / asset_name
    if pkg.is_file():
        # 已快取：驗 sha，符就用、不符就重抓
        h = hashlib.sha256(pkg.read_bytes()).hexdigest()
        if h != sha:
            pkg.unlink(missing_ok=True)
    if not pkg.is_file():
        print(f"  Downloading TinyTeX: {asset_name} …")
        if not _download(url, pkg, sha):
            return False
    print(f"  Extracting → {root}")
    if pkey == "windows":
        return _extract_windows_exe(pkg, root)
    return _extract_tar(pkg, root)


# ── tlmgr 套件 ────────────────────────────────────────────────────

def _run_tlmgr(tlmgr: Path, args: list[str], *, check: bool = True) -> bool:
    """跑 tlmgr；失敗（且 check）時把 tlmgr 自己的輸出尾段透出來（不再黑箱）。"""
    env = dict(os.environ)
    env["PATH"] = str(tlmgr.parent) + os.pathsep + env.get("PATH", "")
    try:
        proc = subprocess.run([str(tlmgr), *args], check=False, env=env,
                              capture_output=True, text=True)
    except OSError as exc:
        sys.stderr.write(f"docspec: tlmgr {' '.join(args)} could not run: {exc}\n")
        return False
    if proc.returncode != 0:
        if check:
            tail = "\n".join(
                ((proc.stderr or "") + (proc.stdout or "")).strip().splitlines()[-15:])
            sys.stderr.write(
                f"docspec: tlmgr {' '.join(args)} returned non-zero (rc={proc.returncode}):\n{tail}\n")
        return False
    return True


def _installed_packages(tlmgr: Path) -> set[str]:
    env = dict(os.environ)
    env["PATH"] = str(tlmgr.parent) + os.pathsep + env.get("PATH", "")
    try:
        out = subprocess.run([str(tlmgr), "info", "--only-installed", "--data", "name"],
                             check=True, env=env, capture_output=True, text=True)
    except (subprocess.CalledProcessError, OSError):
        return set()
    return {ln.strip() for ln in out.stdout.splitlines() if ln.strip()}


def _kpsewhich(tlmgr: Path) -> Path | None:
    """TinyTeX 的 kpsewhich（與 tlmgr 同 bin 夾）。"""
    name = "kpsewhich.exe" if os.name == "nt" else "kpsewhich"
    cand = tlmgr.parent / name
    return cand if cand.is_file() else None


def _file_resolvable(kpse: Path, fname: str) -> bool:
    """kpsewhich 找得到該 TeX 檔（=已可用，不論裝在哪個 collection）。"""
    env = dict(os.environ)
    env["PATH"] = str(kpse.parent) + os.pathsep + env.get("PATH", "")
    try:
        out = subprocess.run([str(kpse), fname], env=env,
                             capture_output=True, text=True)
        return bool(out.stdout.strip())
    except OSError:
        return False


def _missing_packages(tlmgr: Path) -> list[str]:
    """回 _TEX_PACKAGES 中尚未可用者。

    判準雙軌：tlmgr 已裝清單（按 package 名）∪ kpsewhich 找得到 <pkg>.sty/.cls
    （許多套件＝某 collection/bundle 的一員，tlmgr name 列不到，但檔案早已可用；
    用 kpsewhich 補判才不會每次都誤報「缺」、達成真冪等）。
    """
    installed = _installed_packages(tlmgr)
    kpse = _kpsewhich(tlmgr)
    missing: list[str] = []
    for p in _TEX_PACKAGES:
        if p in installed:
            continue
        if kpse is not None and (
            _file_resolvable(kpse, f"{p}.sty") or _file_resolvable(kpse, f"{p}.cls")
        ):
            continue
        missing.append(p)
    return missing


def _ensure_packages(tlmgr: Path) -> tuple[bool, list[str]]:
    """tlmgr update --self → install 缺的套件。回 (ok, 最終可用清單交集 _TEX_PACKAGES)。"""
    print("  tlmgr update --self …")
    _run_tlmgr(tlmgr, ["update", "--self"], check=False)  # 失敗（如離線鏡像）不致命

    missing = _missing_packages(tlmgr)
    if missing:
        print(f"  tlmgr install ({len(missing)} missing): {' '.join(missing)}")
        if not _run_tlmgr(tlmgr, ["install", *missing], check=True):
            return False, []
    else:
        print("  tlmgr packages already present (skipping install)")
    # 回最終可用清單（裝後再判一次）供 tex.lock 記錄
    still = set(_missing_packages(tlmgr))
    have = sorted(p for p in _TEX_PACKAGES if p not in still)
    return True, have
