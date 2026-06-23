r"""docspec setup — 把受控 TinyTeX(xelatex)＋字型裝進 data_dir（Phase B、冪等）。

讓 `docspec export`/`proof` 不再依賴 dev 的 /tmp/ttx，且字型移出 wheel。

做四件事（冪等：已齊就跳過、只補缺）：
  1. 偵測平台/arch → 下載受控 TinyTeX（版本+sha256 釘在下方 _MANIFEST；release asset 名
     不寫死、靠 GitHub release API 按平台 pattern 解析）→ 解到 data_dir/tinytex。
     dev 捷徑：偵測到既有 /tmp/ttx 的 TinyTeX 可 copy 進 data_dir 免重抓。
  2. tlmgr update --self → tlmgr install <_TEX_PACKAGES>（docspec-cas.cls \RequirePackage
     ＋本專案 preamble ＋ session 實裝推導；缺的補、已裝的跳）。
  3. 字型放 data_dir/fonts：主路＝從 _FONT_MANIFEST 的 pinned OFL URL 下載 zip→驗
     sha256→解出需要的字型檔；快路/離線後備＝偵測到 dev 源樹/DOCSPEC_FONTS_SRC 就 copy。
  4. 寫 tex.lock（TinyTeX 版本＋tlmgr 套件清單＋探測到的 bin 路徑），供日後 doctor 比對。

soft-dep/網路失敗 → 清楚報錯、回 1、不 crash。不需要 docspec 專案（全域工具設定）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from dspx import paths

NAME = "setup"
HELP = "Install controlled TinyTeX (xelatex) + fonts into data_dir so export/proof don't depend on a dev environment (idempotent)"

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


# ── pandoc manifest（釘版受控 binary；與 TinyTeX 同哲學＝確定性輸出）──────────
#
# 為什麼 pandoc 也釘版進 data_dir（而非靠系統 apt/brew）：pandoc 版本影響輸出
# （lua filter、--shift-heading-level、pandoc-data 模板跨大版本會壞），系統 pandoc
# 各發行版版本不一，會打臉「釘死工具鏈→確定性 + byte-lock」的整套設計。故與 TinyTeX
# /字型同級：釘版、sha256 驗證、解出 binary 進 data_dir/pandoc。
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


# ── typst manifest（釘版受控 binary；Typst 軌＝預設 render 引擎）──────────────
# 來源＝typst/typst release 的 standalone binary（單一靜態執行檔、無系統依賴、~22MB，
# 比 TinyTeX 輕一個量級）。Windows＝.zip、Linux/macOS＝.tar.xz，內含 typst-<target>/typst[.exe]。
# 平台 key 複用 _pandoc_platform_key（同樣 windows/linux-*/darwin-* 五鍵）。
# 升級＝改 tag＋抓新 asset 的 sha256。
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


# ── drawio manifest（選用受控可攜版；D8：核心 setup 不裝、`--with-drawio` 才裝）──────
# 來源＝jgraph/drawio-desktop release 的**可攜**資產（非安裝程式）：
#   windows       ＝ draw.io-<tag>-windows.zip（解出整包 Electron app，draw.io.exe 直接跑）
#   darwin-*      ＝ draw.io-{x64,arm64}-<tag>.zip（.app bundle，binary 在 .app/Contents/MacOS/draw.io）
#   linux-*       ＝ drawio-{x86_64,arm64}-<tag>.AppImage（單檔，chmod +x 直接跑；需 X/FUSE）
# 平台 key 複用 _pandoc_platform_key（windows/linux-*/darwin-* 五鍵）。tag 不含 'v' 前綴。
# sha256 取自 GitHub release API 的 asset digest（已驗）。升級＝改 tag＋抓新 asset digest。
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


# tlmgr 要補裝的套件（docspec-cas.cls \RequirePackage ＋ preamble \usepackage ＋ session
# 實裝推導）。TinyTeX-1 medium scheme 多半已含，install 對已裝者 no-op。缺的才裝。
_TEX_PACKAGES = [
    "xecjk", "fontspec", "framed", "fvextra", "tabularx", "xltabular",
    "ltablex",  # xltabular 的依賴（提供 ltablex.sty）；TinyTeX medium scheme 含 xltabular
                # 卻不含 ltablex，tlmgr 裝 xltabular 時又因「已存在」沒拉依賴 → Linux 實編
                # 撞 `ltablex.sty not found`（Windows medium scheme 剛好含故未爆，Linux 真測抓到）。
    "seqsplit", "etoolbox", "enumitem", "tcolorbox", "environ", "trimspaces",
    "pgf",  # TikZ 原生繪圖（preamble \usepackage{tikz}＋positioning/arrows.meta/fit/backgrounds/calc）：agent 把 mermaid 翻成等價 TikZ。tikz.sty 與各 tikzlibrary 都在 pgf bundle 內
    "lastpage",  # 頁尾「Page X of N」總頁數：preamble 用 \pageref{LastPage} 取代 cas 的 off-by-one \lastpage

    "booktabs", "colortbl", "makecell", "multirow", "stix", "inconsolata",
    "dcolumn", "footmisc", "xstring", "xspace", "needspace",
    # docspec-cas.cls 進一步 \RequirePackage 推導：
    "natbib", "elsarticle", "moreverb", "wrapfig", "setspace",
    "sttools",  # 提供 stfloats.sty（upstream cas-sc \RequirePackage{stfloats}）；TL 套件名＝sttools，
                # 非 stfloats（後者只是 .sty 檔名）。誤用 stfloats 會「not present in repository」
                # 讓整批 tlmgr install 回非零、setup 中止（Linux 真測抓到，Windows medium scheme 已含故未爆）。
    "l3packages", "l3kernel", "amsmath", "amsfonts",
]
# 註：upstream cas-sc.cls 原本 \RequirePackage{charis}/{stix}/{inconsolata}，但我們的 preamble
# 用 fontspec \setmainfont/\setCJKmainfont 整組覆蓋掉這些字型設定（見 preamble.tex），
# 故 charis 不在清單（實測純-data_dir export 不需它即正確產出）。stix/inconsolata 仍留
# （數學符號 fallback 可能用到）。


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


# ── TinyTeX 安裝（解壓到 data_dir/tinytex）─────────────────────────

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
            tf.extractall(target_root.parent)  # noqa: S202 — 官方 release、已驗 sha256
    except (tarfile.TarError, OSError) as exc:
        sys.stderr.write(f"docspec: failed to extract the TinyTeX tar: {exc}\n")
        return False
    return _normalize_extracted_root(target_root)


def _dev_tinytex_shortcut() -> Path | None:
    """偵測既有 dev TinyTeX（/tmp/ttx、%TEMP%/ttx）可 copy 進 data_dir 免重抓。"""
    for root in paths.dev_tinytex_roots():
        if root.is_dir() and paths.tlmgr_path(root) is not None:
            return root
    return None


def _ensure_tinytex(pkey: str, *, force: bool, no_download: bool,
                    use_dev_shortcut: bool) -> bool:
    """確保 data_dir/tinytex 有可用 TinyTeX（含 tlmgr）。冪等：已裝齊跳過。"""
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
    version, url, sha, members = _FONT_MANIFEST[key]
    cache = paths.cache_dir()
    pkg = cache / f"{key}-{version}.zip"
    if pkg.is_file():
        h = hashlib.sha256(pkg.read_bytes()).hexdigest()
        if h != sha:
            pkg.unlink(missing_ok=True)
    if not pkg.is_file():
        print(f"  Downloading font source: {key} {version} …")
        if not _download(url, pkg, sha):
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

    need_keys: list[str] = []
    for f in still:
        k = _FONT_FILE_SOURCE.get(f)
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


# ── pandoc（釘版受控 binary；解出單一執行檔進 data_dir/pandoc）──────────

def _extract_pandoc_binary(archive: Path, exe_name: str, target: Path) -> bool:
    """從已驗 sha256 的 release 壓縮檔解出 pandoc 執行檔到 target（.zip / .tar.gz 兩路）。

    壓縮檔內含 `pandoc-<ver>[/bin]/pandoc[.exe]` ＋ pandoc-lua/pandoc-server——只取
    basename 等於 exe_name 的那一個（不要 lua/server）。
    """
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
    pkey = _pandoc_platform_key()
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

    asset_name, sha = _PANDOC_MANIFEST["assets"][pkey]
    url = f"https://github.com/{_PANDOC_REPO}/releases/download/{_PANDOC_MANIFEST['tag']}/{asset_name}"
    cache = paths.cache_dir()
    pkg = cache / asset_name
    if pkg.is_file():
        if hashlib.sha256(pkg.read_bytes()).hexdigest() != sha:
            pkg.unlink(missing_ok=True)
    if not pkg.is_file():
        print(f"  Downloading pandoc: {asset_name} ({_PANDOC_MANIFEST['tag']}) …")
        if not _download(url, pkg, sha):
            return False
    if not _extract_pandoc_binary(pkg, exe_name, target):
        return False
    print(f"  pandoc ready in {target}")
    return True


def _ensure_typst(*, force: bool, no_download: bool) -> bool:
    """把釘版 typst binary 放進 data_dir/typst（預設 render 引擎）。冪等：已在就跳過。"""
    pkey = _pandoc_platform_key()
    if pkey is None or pkey not in _TYPST_MANIFEST["assets"]:
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

    asset_name, sha = _TYPST_MANIFEST["assets"][pkey]
    url = f"https://github.com/{_TYPST_REPO}/releases/download/{_TYPST_MANIFEST['tag']}/{asset_name}"
    cache = paths.cache_dir()
    pkg = cache / asset_name
    if pkg.is_file() and hashlib.sha256(pkg.read_bytes()).hexdigest() != sha:
        pkg.unlink(missing_ok=True)
    if not pkg.is_file():
        print(f"  Downloading typst: {asset_name} ({_TYPST_MANIFEST['tag']}) …")
        if not _download(url, pkg, sha):
            return False
    # 解出 typst 執行檔（reuse pandoc 的通用 by-basename 解壓；tar.xz 由 tarfile 自動偵測）。
    if not _extract_pandoc_binary(pkg, exe_name, target):
        return False
    print(f"  typst ready in {target}")
    return True


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


def _ensure_drawio(*, force: bool, no_download: bool, interactive: bool = False) -> bool:
    """選用：把釘版 draw.io 可攜版放進 data_dir/drawio。冪等：已在就跳過。"""
    pkey = _pandoc_platform_key()
    if pkey is None or pkey not in _DRAWIO_MANIFEST["assets"]:
        sys.stderr.write(
            f"docspec: the draw.io manifest does not cover this platform ({platform.system()}/{platform.machine()}).\n")
        return False

    plat = "windows" if pkey == "windows" else ("darwin" if pkey.startswith("darwin") else "linux")
    target = paths.drawio_managed_binary(plat)
    if not force and target.is_file():
        print(f"  draw.io already at {target} (skipping download)")
        _check_linux_drawio_runtime(interactive=interactive)
        return True

    if no_download:
        sys.stderr.write("docspec: --no-download given and no draw.io in data_dir — aborting.\n")
        return False

    asset_name, sha = _DRAWIO_MANIFEST["assets"][pkey]
    url = f"https://github.com/{_DRAWIO_REPO}/releases/download/v{_DRAWIO_MANIFEST['tag']}/{asset_name}"
    cache = paths.cache_dir()
    pkg = cache / asset_name
    if pkg.is_file() and hashlib.sha256(pkg.read_bytes()).hexdigest() != sha:
        pkg.unlink(missing_ok=True)
    if not pkg.is_file():
        print(f"  Downloading draw.io: {asset_name} (v{_DRAWIO_MANIFEST['tag']}) …")
        if not _download(url, pkg, sha):
            return False
    print(f"  Extracting draw.io → {paths.drawio_dir()}")
    if not _extract_drawio(pkg, pkey):
        sys.stderr.write("docspec: draw.io extraction did not yield a runnable binary.\n")
        return False
    print(f"  draw.io ready ({target})")
    _check_linux_drawio_runtime(interactive=interactive)
    return True


# ── tex.lock（指紋；供 doctor 比對）────────────────────────────────

def _write_lock(tlmgr: Path, xelatex: Path | None, packages: list[str],
                pandoc: str | None = None, typst: str | None = None,
                drawio: str | None = None) -> None:
    lock = {
        "tinytex_tag": _MANIFEST["tag"],
        "pandoc_tag": _PANDOC_MANIFEST["tag"],
        "typst_tag": _TYPST_MANIFEST["tag"],
        "drawio_tag": _DRAWIO_MANIFEST["tag"],
        "platform": _platform_key(),
        "tinytex_root": str(paths.tinytex_root()),
        "tlmgr_path": str(tlmgr),
        "xelatex_path": str(xelatex) if xelatex else None,
        "pandoc_path": str(pandoc) if pandoc else None,
        "typst_path": str(typst) if typst else None,
        "drawio_path": str(drawio) if drawio else None,  # None＝未裝（--with-drawio 才裝）
        "fonts_dir": str(paths.fonts_dir()),
        "fonts": list(paths.REQUIRED_FONT_FILES),
        "tlmgr_packages": packages,
    }
    paths.tex_lock_path().write_text(
        json.dumps(lock, ensure_ascii=False, indent=2), encoding="utf-8")


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
    args = parser.parse_args(argv)

    pkey = _platform_key()
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

    print(f"docspec setup (platform={pkey}) → data_dir: {dd}")

    # 1+2. TinyTeX
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

    # 3. 字型
    if not _ensure_fonts(force=args.force, no_download=args.no_download):
        return 1

    # 4. pandoc（受控 binary；與 TinyTeX 同級＝確定性輸出，不靠系統 pandoc）
    if not _ensure_pandoc(force=args.force, no_download=args.no_download):
        sys.stderr.write("docspec: pandoc install did not complete — setup aborted.\n")
        return 1

    # 4.5 typst（受控 binary；Typst 軌＝預設 render 引擎，輕量、原生 CJK）
    if not _ensure_typst(force=args.force, no_download=args.no_download):
        sys.stderr.write("docspec: typst install did not complete — setup aborted.\n")
        return 1

    # 4.6 draw.io（選用、D8：核心不裝、--with-drawio 才裝；供 dspx-diagram subagent 渲圖）
    if args.with_drawio:
        if not _ensure_drawio(force=args.force, no_download=args.no_download, interactive=True):
            sys.stderr.write("docspec: draw.io install did not complete — setup aborted.\n")
            return 1

    # 5. tex.lock
    xelatex = paths.resolve_xelatex()
    pandoc = paths.resolve_pandoc()
    typst = paths.resolve_typst()
    drawio = paths.resolve_drawio()
    _write_lock(tlmgr, xelatex, packages, pandoc, typst, drawio)

    print(f"\n✓ setup complete. tex.lock: {paths.tex_lock_path()}")
    print(f"  typst: {typst}  (default render engine)")
    print(f"  xelatex: {xelatex}  (LaTeX track)")
    print(f"  pandoc: {pandoc}")
    if drawio:
        print(f"  draw.io: {drawio}  (optional; diagram rendering)")
    else:
        print("  draw.io: not installed (run `docspec setup --with-drawio` to add diagram rendering)")
    print("  From now on `docspec export <article>` / `docspec proof <article>` run purely off data_dir.")
    return 0
