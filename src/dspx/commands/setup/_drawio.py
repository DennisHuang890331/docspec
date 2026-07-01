r"""draw.io 安裝 — 選用受控可攜版（D8：核心 setup 不裝、`--with-drawio` 才裝）。

來源＝jgraph/drawio-desktop release 的**可攜**資產（非安裝程式）：
  windows       ＝ draw.io-<tag>-windows.zip（解出整包 Electron app，draw.io.exe 直接跑）
  darwin-*      ＝ draw.io-{x64,arm64}-<tag>.zip（.app bundle，binary 在 .app/Contents/MacOS/draw.io）
  linux-*       ＝ drawio-{x86_64,arm64}-<tag>.AppImage（單檔，chmod +x 直接跑；需 X/FUSE）
平台 key 複用 _pandoc_platform_key（windows/linux-*/darwin-* 五鍵）。tag 不含 'v' 前綴。
sha256 取自 GitHub release API 的 asset digest（已驗）。升級＝改 tag＋抓新 asset digest。
"""

from __future__ import annotations

import hashlib
import os
import platform
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from dspx import paths

_DRAWIO_REPO = "jgraph/drawio-desktop"
_DRAWIO_MANIFEST = {
    "tag": "30.2.4",
    "assets": {
        "windows":       ("draw.io-30.2.4-windows.zip",       "53633acf3c24927ae99e32c85bc838131719148a40487d3dfacf19042a4f240c"),
        "linux-x86_64":  ("drawio-x86_64-30.2.4.AppImage",    "a936ff56fe92e3251b1353f42ace564abc8bcf81bc146631fab477fc4a3b6881"),
        "linux-arm64":   ("drawio-arm64-30.2.4.AppImage",     "4d20819afb01bb3c7694da7344b5f4c742ed4d9ca77e4f7695ce9d1e69b75c42"),
        "darwin-x86_64": ("draw.io-x64-30.2.4.zip",           "bf31463d3d37e7c6739ee9199363421ca024fdeab2c6a228c43233bfcb50c6f0"),
        "darwin-arm64":  ("draw.io-arm64-30.2.4.zip",         "2e40b7c5b5034379a88998236fe6050224a5a5232e213c1a0393a86e8f65e5b3"),
    },
}
# 既有 binary 的版本檢查＝**最小門檻**（非精確匹配釘版）。理由：`-x -f png` 匯出旗標跨很廣的
# draw.io 版本都能用（壓測在 v24.16.0 實證；當初「舊版拒旗標」其實是 ELECTRON_RUN_AS_NODE 在作怪、
# 非版本）。故只要 ≥ 此下限就留著用、不重抓也不把更新版降級回 pinned；低於才重抓 pinned。
# 保守值＝有硬證據可用的最低版本；單一常數、要放寬只改這行。下載端仍精確 pinned（見 _DRAWIO_MANIFEST）。
_DRAWIO_MIN_VERSION = (24, 0, 0)


# ── drawio（選用受控可攜版；解整包/AppImage 進 data_dir/drawio）─────────────

def _extract_drawio(archive: Path, pkey: str) -> bool:
    """把 draw.io 可攜資產解到 data_dir/drawio，並回傳是否解出可用的 CLI binary。

    - windows/.zip ＝ 整包 Electron app（draw.io.exe + resources/…）→ 全解進 drawio_dir。
    - darwin/.zip  ＝ draw.io.app bundle → 全解進 drawio_dir，binary 在 .app/Contents/MacOS/draw.io。
    - linux/.AppImage ＝ 單檔 → 複製成 drawio_dir/drawio.AppImage 並 chmod +x。
    """
    dest = paths.drawio_dir()
    dest.mkdir(parents=True, exist_ok=True)
    plat = "windows" if pkey == "windows" else ("darwin" if pkey.startswith("darwin") else "linux")
    try:
        if plat == "linux":
            target = paths.drawio_managed_binary(plat)
            shutil.copyfile(archive, target)
            target.chmod(0o755)
        else:
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(dest)  # noqa: S202 — 官方 release、已驗 sha256
            if plat == "darwin":
                binary = paths.drawio_managed_binary(plat)
                if binary.is_file():
                    binary.chmod(0o755)  # zip 不保留執行位元
    except (zipfile.BadZipFile, OSError) as exc:
        sys.stderr.write(f"docspec: failed to extract draw.io ({archive.name}): {exc}\n")
        return False
    return paths.drawio_managed_binary(plat).is_file()


def _check_linux_drawio_runtime(*, interactive: bool) -> None:
    """Linux：draw.io（Electron）渲圖需 X/Electron 共享庫 ＋ headless 的 xvfb。
    這些是系統套件，docspec 不能塞進 data_dir。偵測缺漏 → 依 D8 詢問是否安裝（互動時），
    否則只印清楚指引（含 Docker 後備）。永不強制、不阻擋 binary 落地。"""
    if platform.system() != "Linux":
        return
    have_xvfb = shutil.which("xvfb-run") is not None
    libs_ok = True
    try:
        out = subprocess.run(["ldconfig", "-p"], capture_output=True, text=True, check=False)
        cat = out.stdout
        libs_ok = all(lib in cat for lib in ("libgtk-3", "libnss3", "libgbm"))
    except OSError:
        libs_ok = False  # ldconfig 不在 → 無法確認，當作可能缺
    if have_xvfb and libs_ok:
        print("  draw.io Linux runtime looks present (xvfb + GTK/NSS/GBM).")
        return
    apt = ("sudo apt-get install -y xvfb libgtk-3-0 libnss3 libgbm1 "
           "libasound2t64 libnotify4")
    print("  ⚠ draw.io on Linux needs X/Electron libraries + xvfb for headless rendering.")
    print(f"    Missing or unconfirmed: {'xvfb ' if not have_xvfb else ''}"
          f"{'GTK/NSS/GBM libs' if not libs_ok else ''}".strip())
    print(f"    Install (Debian/Ubuntu):  {apt}")
    print("    Alternative: the tomkludy/drawio-renderer Docker image (headless export REST API).")
    if interactive and sys.stdin.isatty():
        try:
            import questionary
            if questionary.confirm(
                    "Install the X/Electron libraries now via apt-get? (needs sudo)",
                    default=False).ask():
                rc = subprocess.run(["sh", "-c", apt], check=False).returncode
                if rc != 0:
                    print("  apt-get returned non-zero — install the packages manually (above).")
        except Exception:  # noqa: BLE001 — questionary 缺/非 TTY → 留指引即可
            pass


def _drawio_version(binary: str | Path) -> str | None:
    """跑 `<binary> --version` 取 draw.io 自報版本（如 "30.2.4"）。
    先剝掉繼承的 `ELECTRON_RUN_AS_NODE`——它會讓 Electron app 當 node 跑、拒 `-x -f`/版本旗標。
    探不到（逾時/非零/無版本字串/headless 起不來）→ None：呼叫端不阻擋，只是無法擔保版本。"""
    env = {k: v for k, v in os.environ.items() if k != "ELECTRON_RUN_AS_NODE"}
    try:
        out = subprocess.run([str(binary), "--version"], capture_output=True,
                             text=True, timeout=30, env=env, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"\b(\d+\.\d+\.\d+)\b", f"{out.stdout}\n{out.stderr}")
    return m.group(1) if m else None


def _ensure_drawio(*, force: bool, no_download: bool, interactive: bool = False) -> bool:
    """選用：把釘版 draw.io 可攜版放進 data_dir/drawio。冪等：已在**且版本對得上釘版**才跳過
    （舊版殘檔的 CLI 會拒 `-x -f`，故不只信檔案存在——驗 `--version`，不符就重抓）。"""
    # 透過套件頂層取得可被 monkeypatch 的名字（_pandoc_platform_key/_DRAWIO_MANIFEST/
    # _drawio_version/_check_linux_drawio_runtime/_download/_version_tuple）——確保測試
    # 對 `setup_cmd.X` 的 patch（含自身模組定義的 _drawio_version 等）對這裡的呼叫生效。
    from dspx.commands import setup as _pkg
    pkey = _pkg._pandoc_platform_key()
    manifest = _pkg._DRAWIO_MANIFEST
    if pkey is None or pkey not in manifest["assets"]:
        sys.stderr.write(
            f"docspec: the draw.io manifest does not cover this platform ({platform.system()}/{platform.machine()}).\n")
        return False

    plat = "windows" if pkey == "windows" else ("darwin" if pkey.startswith("darwin") else "linux")
    target = paths.drawio_managed_binary(plat)
    pinned = manifest["tag"]
    floor = ".".join(map(str, _DRAWIO_MIN_VERSION))
    if not force and target.is_file():
        ver = _pkg._drawio_version(target)
        vt = _pkg._version_tuple(ver)
        # 只有「確實探到版本且低於門檻」才重抓。夠新（≥門檻）即留、不降級；版本探不到也留——
        # 探測失敗（逾時/headless 起不來）不是「壞 binary」的證據，硬重抓只會 churn 又修不了。
        too_old = vt is not None and vt < _DRAWIO_MIN_VERSION
        if not too_old:
            note = (f"v{ver}, ≥ min v{floor}" if vt is not None
                    else "version unprobed (keeping — a probe failure is not a bad binary)")
            print(f"  draw.io already at {target} ({note}, skipping download)")
            _pkg._check_linux_drawio_runtime(interactive=interactive)
            return True
        # 確實低於門檻 → 重抓 pinned。
        if no_download:
            sys.stderr.write(
                f"docspec: draw.io at {target}: v{ver} is below the v{floor} floor; "
                f"--no-download given, keeping it (its CLI may reject -x -f export flags).\n")
            _pkg._check_linux_drawio_runtime(interactive=interactive)
            return True
        print(f"  draw.io at {target}: v{ver} below v{floor} floor — re-downloading pinned v{pinned}")
        # 落到下面重抓

    if no_download:
        sys.stderr.write("docspec: --no-download given and no draw.io in data_dir — aborting.\n")
        return False

    asset_name, sha = manifest["assets"][pkey]
    url = f"https://github.com/{_DRAWIO_REPO}/releases/download/v{manifest['tag']}/{asset_name}"
    cache = paths.cache_dir()
    pkg = cache / asset_name
    if pkg.is_file() and hashlib.sha256(pkg.read_bytes()).hexdigest() != sha:
        pkg.unlink(missing_ok=True)
    if not pkg.is_file():
        print(f"  Downloading draw.io: {asset_name} (v{manifest['tag']}) …")
        if not _pkg._download(url, pkg, sha):
            return False
    print(f"  Extracting draw.io → {paths.drawio_dir()}")
    if not _extract_drawio(pkg, pkey):
        sys.stderr.write("docspec: draw.io extraction did not yield a runnable binary.\n")
        return False
    print(f"  draw.io ready ({target})")
    ver = _pkg._drawio_version(target)
    if ver is not None and ver != pinned:
        sys.stderr.write(
            f"docspec: warning — installed draw.io self-reports v{ver} but pinned v{pinned} "
            f"(the export flags it accepts may differ).\n")
    elif ver:
        print(f"  draw.io version {ver} (matches pinned v{pinned})")
    _pkg._check_linux_drawio_runtime(interactive=interactive)
    return True
