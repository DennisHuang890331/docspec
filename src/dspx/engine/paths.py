"""docspec 受控執行期資產的 data_dir 解析。

四目錄規範（CLAUDE.md＋已定決策）：
- data_dir＝platformdirs.user_data_dir("docspec")：
    Win   %LOCALAPPDATA%\\docspec
    Linux ~/.local/share/docspec
    macOS ~/Library/Application Support/docspec
- 結構：typst/（受控 Typst binary）、pandoc/（受控 pandoc binary）、
        fonts/（CJK＋拉丁字型；`docspec setup` 落地）、
        tex.lock（setup 寫的版本指紋，供 doctor 比對）、
        cache/（下載暫存）。

此模組是「解析器」：知道資產該在哪、怎麼找；不負責下載/安裝（那是 commands/setup.py）。
export 與 setup 共用這裡的解析邏輯，避免路徑常數散落漂移。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import unicodedata
from collections import Counter
from pathlib import Path


# ── data_dir 與其子路徑 ────────────────────────────────────────────

def data_dir() -> Path:
    """docspec 的每平台 user data dir（受控 TinyTeX＋字型的家）。"""
    import platformdirs  # 延後 import：缺相依時錯誤訊息更聚焦在實際用到的指令
    return Path(platformdirs.user_data_dir("docspec"))


def tinytex_root() -> Path:
    """受控 TinyTeX 安裝根（data_dir/tinytex；其下含 bin/<plat>/、texmf-*）。

    ★TinyTeX 是通用 LaTeX 引擎（xelatex），與已退場的 docspec-cas class 是兩回事：
    它仍是日後編譯期刊 .tex（IEEE/Elsevier/IET）所需的引擎，故保留（setup 仍裝、doctor 仍查）。
    """
    return data_dir() / "tinytex"


def fonts_dir() -> Path:
    """受控字型夾（data_dir/fonts；Source Serif / Source Code Pro / 思源宋體）。"""
    return data_dir() / "fonts"


def tex_lock_path() -> Path:
    """setup 落地的指紋檔（TinyTeX 版本＋tlmgr 套件清單＋探測到的 bin 路徑）。"""
    return data_dir() / "tex.lock"


def cache_dir() -> Path:
    """下載暫存夾（TinyTeX 安裝包等可重生中介物）。"""
    return data_dir() / "cache"


def pandoc_dir() -> Path:
    """受控 pandoc 夾（data_dir/pandoc；setup 釘版下載的 pandoc binary 落地處）。"""
    return data_dir() / "pandoc"


def pandoc_exe_name() -> str:
    return "pandoc.exe" if os.name == "nt" else "pandoc"


def typst_dir() -> Path:
    """受控 typst 夾（data_dir/typst；`docspec setup` 釘版下載的 typst binary 落地處）。"""
    return data_dir() / "typst"


def typst_exe_name() -> str:
    return "typst.exe" if os.name == "nt" else "typst"


def drawio_dir() -> Path:
    """受控 draw.io 夾（data_dir/drawio；`docspec setup --with-drawio` 釘版下載的 drawio-desktop
    可攜版落地處）。draw.io 是**選用**資產（核心 setup 不裝），供 dspx-diagram 的委派 subagent
    把 `.drawio` 渲成 SVG 用。"""
    return data_dir() / "drawio"


def drawio_managed_binary(plat: str | None = None) -> Path:
    """受控 draw.io 可攜版的執行檔路徑（每平台不同的可攜結構）：
      - Windows ＝ drawio/draw.io.exe（portable zip 解出的整包 Electron app）
      - macOS   ＝ drawio/draw.io.app/Contents/MacOS/draw.io（.app bundle）
      - Linux   ＝ drawio/drawio.AppImage（單檔 AppImage，需 X/FUSE 或 --appimage-extract）
    plat 預設用本機；指定時供解析/測試跨平台路徑。
    """
    base = drawio_dir()
    plat = plat or _os_family()
    if plat == "windows":
        return base / "draw.io.exe"
    if plat == "darwin":
        return base / "draw.io.app" / "Contents" / "MacOS" / "draw.io"
    return base / "drawio.AppImage"


def _os_family() -> str:
    if os.name == "nt":
        return "windows"
    import platform as _platform
    return "darwin" if _platform.system() == "Darwin" else "linux"


def resolve_drawio() -> str | None:
    """找得到的 draw.io CLI（選用；dspx-diagram subagent 渲圖用）。優先序同其他資產：
      1. DOCSPEC_DRAWIO 環境變數覆寫（指向 draw.io 執行檔／AppImage）。
      2. data_dir/drawio 的受控可攜版（`docspec setup --with-drawio` 落地）。
      3. 系統 PATH 後備（`drawio` 或舊式 `draw.io`）。
    找不到 → None（呼叫端降級＝瀏覽器後備或只給 .drawio XML）。
    """
    env = os.environ.get("DOCSPEC_DRAWIO")
    if env and Path(env).is_file():
        return env
    try:
        managed = drawio_managed_binary()
        if managed.is_file():
            return str(managed)
    except Exception:
        pass
    return shutil.which("drawio") or shutil.which("draw.io")


def resolve_typst() -> str | None:
    """找得到的 typst（預設 render 引擎；優先序同 resolve_pandoc＝受控資產優先）：
      1. DOCSPEC_TYPST 環境變數覆寫（指向 typst 執行檔）。
      2. data_dir/typst/typst(.exe)＝`docspec setup --with-... ` 釘版下載的受控 typst。
      3. 系統 PATH 後備（dev）。
    找不到 → None。
    """
    env = os.environ.get("DOCSPEC_TYPST")
    if env and Path(env).is_file():
        return env
    try:
        managed = typst_dir() / typst_exe_name()
        if managed.is_file():
            return str(managed)
    except Exception:
        pass  # platformdirs 缺席等 → 落到後備
    return shutil.which("typst")


# ── xelatex 解析（export/proof 共用）──────────────────────────────

def _xelatex_exe_name() -> str:
    return "xelatex.exe" if os.name == "nt" else "xelatex"


def _xelatex_from_root(root: Path) -> Path | None:
    """從一個「根」解析出 xelatex 執行檔：可能是檔本身／bin 夾／TinyTeX 安裝根。"""
    exe = _xelatex_exe_name()
    if root.is_file():
        return root
    cand = root / exe
    if cand.is_file():
        return cand
    for p in root.glob(f"**/bin/*/{exe}"):
        if p.is_file():
            return p
    return None


def dev_tinytex_roots() -> list[Path]:
    """dev 後備：手動裝在暫存區的 TinyTeX（/tmp/ttx、Windows Git-Bash /tmp＝%TEMP%）。"""
    return [
        Path("/tmp/ttx/TinyTeX"),
        Path(tempfile.gettempdir()) / "ttx" / "TinyTeX",
    ]


def resolve_xelatex() -> Path | None:
    """解析受控 TinyTeX 的 xelatex 執行檔（不污染系統 PATH）。

    優先序（任務規範）：
      1. 環境變數 DOCSPEC_TINYTEX（覆寫；可指 bin 夾或 xelatex 檔本身）。
      2. data_dir/tinytex/bin/<plat>/xelatex（Phase B `docspec setup` 落地處）。
      3. dev 後備：/tmp/ttx 或 %TEMP%/ttx 的 TinyTeX。
    找不到 → None（呼叫端降級報錯、叫跑 `docspec setup`）。
    """
    env = os.environ.get("DOCSPEC_TINYTEX")
    if env:
        hit = _xelatex_from_root(Path(env))
        if hit is not None:
            return hit

    try:
        hit = _xelatex_from_root(tinytex_root())
        if hit is not None:
            return hit
    except Exception:
        pass  # platformdirs 缺席等 → 落到 dev 後備

    for dev in dev_tinytex_roots():
        if dev.is_dir():
            hit = _xelatex_from_root(dev)
            if hit is not None:
                return hit
    return None


def tlmgr_path(tinytex_root_dir: Path) -> Path | None:
    """TinyTeX 安裝根下的 tlmgr 執行檔（Windows＝tlmgr.bat，POSIX＝tlmgr）。"""
    name = "tlmgr.bat" if os.name == "nt" else "tlmgr"
    for p in tinytex_root_dir.glob(f"**/bin/*/{name}"):
        if p.is_file():
            return p
    return None


# ── 字型解析（export build 從這裡 copy 進 build dir 的 fonts/）──────

# export build 需要的字型檔名（缺任一 → setup 報；export 從 data_dir/fonts copy 進 build）。
REQUIRED_FONT_FILES: tuple[str, ...] = (
    "TW-Kai-98_1.ttf",
    "SourceSerif4-Regular.otf", "SourceSerif4-Bold.otf",
    "SourceSerif4-It.otf", "SourceSerif4-BoldIt.otf",
    "SourceSans3-Regular.otf", "SourceSans3-Bold.otf",
    "SourceSans3-It.otf", "SourceSans3-BoldIt.otf",
    "SourceCodePro-Regular.otf", "SourceCodePro-Bold.otf",
    "SourceCodePro-It.otf", "SourceCodePro-BoldIt.otf",
    "SourceHanSansTC-Regular.otf", "SourceHanSansTC-Bold.otf",
    "SourceHanSerifTC-Regular.otf", "SourceHanSerifTC-SemiBold.otf",  # SemiBold＝CJK emphasis 粗體 fallback
    "LXGWWenKaiTC-Regular.ttf",      # 霞鶩文楷 TC（cjk_body 候選）
    "TW-Sung-98_1.ttf",             # 全字庫正宋體（內文預設）
)


class AssetError(Exception):
    """使用者指定的 --fonts / --template 夾找不到或缺必要檔（清楚報錯、非零、不 crash）。"""


def resolve_fonts_dir(override: str | Path | None = None) -> Path | None:
    """解析 export build 要 copy 的字型來源夾。

    優先序：
      0. override（`--fonts <dir>`）：使用者指定的字型夾。給了就**只用它**——夾不存在或
         缺必要字型 → 拋 AssetError（不靜默退回 data_dir）。
      1. 環境變數 DOCSPEC_FONTS_SRC（dev / CI：指向含字型的夾）。
      2. data_dir/fonts（`docspec setup` 落地處）——只要存在就用。
    找不到 → None（呼叫端提示執行 docspec setup）。
    """
    if override is not None:
        d = Path(override)
        if not d.is_dir():
            raise AssetError(f"--fonts directory does not exist: {d}")
        missing = [f for f in REQUIRED_FONT_FILES if not (d / f).is_file()]
        if missing:
            raise AssetError(
                f"--fonts directory {d} is missing required font files: "
                f"{', '.join(missing[:6])}{' …' if len(missing) > 6 else ''}")
        return d
    env_src = os.environ.get("DOCSPEC_FONTS_SRC")
    if env_src:
        d = Path(env_src)
        if d.is_dir() and any((d / f).is_file() for f in REQUIRED_FONT_FILES):
            return d
    try:
        d = fonts_dir()
        if d.is_dir() and any((d / f).is_file() for f in REQUIRED_FONT_FILES):
            return d
    except Exception:
        pass
    return None


def _bundled_fonts_dir() -> Path | None:
    """setup 的字型「快路/離線後備」本地來源夾（免下載時 copy 用）。

    唯一來源＝環境變數 DOCSPEC_FONTS_SRC 指定的夾（dev / CI：指向已備齊字型的夾）。
    （舊的套件隨包字型夾已隨 docspec-cas 模板包一併移除——prod 字型本就排除出 wheel、
    走 `docspec setup` 下載；本快路只在使用者明確設了 DOCSPEC_FONTS_SRC 時生效。）
    沒設或夾不含字型 → None（setup 退回 pinned URL 下載）。
    """
    env_src = os.environ.get("DOCSPEC_FONTS_SRC")
    if env_src:
        d = Path(env_src)
        if d.is_dir() and any((d / f).is_file() for f in REQUIRED_FONT_FILES):
            return d
    return None


# ── tex.lock 讀取（doctor/upgrade/version 共用；setup 寫、這裡讀）────────

def read_tex_lock() -> dict | None:
    """讀 setup 落地的 tex.lock 指紋；不存在/壞 JSON → None（離線、不拋）。"""
    try:
        p = tex_lock_path()
    except Exception:
        return None
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


# ── 模板包解析 ────────────────────────────────────────────────────────────────

BUNDLED_JOURNALS: tuple[str, ...] = ("ieee", "elsevier", "iet")


def bundled_journal_template(name: str) -> Path | None:
    """套件隨包的期刊 adapter pandoc 模板（assets/templates/journals/<name>/template.tex）。

    journal 軌＝BYO emit-only：把 slot contract 餵過此 pandoc 模板產 `.tex`、不自編譯。
    回 template.tex 路徑；不存在 → None。
    """
    try:
        from importlib.resources import files
        p = Path(str(files("dspx").joinpath("assets", "templates", "journals", name, "template.tex")))
        return p if p.is_file() else None
    except Exception:
        return None


def bundled_journal_filter() -> Path | None:
    """journal 軌共用的 pandoc Lua filter（assets/templates/journals/journal-tables.lua）：
    把 pandoc 的 longtable 改寫成兩欄期刊 class 吃得下的 tabular（IEEEtran/cas-dc/cta-author
    都拒 longtable）。回 .lua 路徑；不存在 → None。"""
    try:
        from importlib.resources import files
        p = Path(str(files("dspx").joinpath("assets", "templates", "journals", "journal-tables.lua")))
        return p if p.is_file() else None
    except Exception:
        return None


def bundled_typst_template_dir() -> Path | None:
    """套件隨包的 docspec-typst 模板包（src/dspx/assets/templates/docspec-typst/；含 template.typ）。"""
    try:
        from importlib.resources import files
        p = Path(str(files("dspx").joinpath("assets", "templates", "docspec-typst")))
        return p if p.is_dir() else None
    except Exception:
        return None


def bundled_reference_dir() -> Path | None:
    """套件隨包、與模板包無關的通用參考資料夾（src/dspx/assets/reference/）。
    現存 `writing.md`（中/英文寫作道地化參考索引，`docspec reference writing-{zh,en}`）；
    非模板包 escape-hatch gate 範圍（該 gate 只掃 assets/templates/ 下）。"""
    try:
        from importlib.resources import files
        p = Path(str(files("dspx").joinpath("assets", "reference")))
        return p if p.is_dir() else None
    except Exception:
        return None


PACK_HASHES_FILE = ".pack-hashes.json"


def pack_content_hashes(pack_dir: Path) -> dict[str, str]:
    """模板包內容指紋：{相對路徑(POSIX): sha256}。

    用於 export 的逃生口 gate（偵測 bundled pack 被手改）。納入所有檔，**排除** fonts/
    （不進 wheel、各機器自裝、會異）與基線檔 `.pack-hashes.json` 本身。相對路徑正規成
    POSIX（跨平台基線一致）。build-time（無 git）由 `tools/gen_pack_hashes.py` 落地進 pack。
    """
    import hashlib
    out: dict[str, str] = {}
    for fp in sorted(pack_dir.rglob("*")):
        if not fp.is_file():
            continue
        rel = fp.relative_to(pack_dir).as_posix()
        if rel == PACK_HASHES_FILE or rel.startswith("fonts/"):
            continue
        out[rel] = hashlib.sha256(fp.read_bytes()).hexdigest()
    return out


def read_pack_baseline(pack_dir: Path) -> dict[str, str] | None:
    """讀 pack 內 `.pack-hashes.json` 基線；缺/壞 → None（呼叫端決定是否放行）。"""
    p = pack_dir / PACK_HASHES_FILE
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


# ── 內容 token 多重集（export runtime byte-lock；test 與 export 共用）─────

_LATEX_CMD_RE = re.compile(r"\\[A-Za-z]+")


def content_token_multiset(text: str) -> Counter:
    """NFC 正規化後，抽「個別 CJK 字 / 個別拉丁字母 / 個別數字」為內容字元多重集。

    忽略空白、標點、表格格線——這些是呈現。刻意逐「字元」而非逐「詞」比對：
    xelatex+actualtext 的 PDF 文字層雖完整可搜尋，但詞間空白並非總能由抽取器
    （pdfplumber/pypdf）依字符座標還原（"MUST NOT"→可能變 "MUSTNOT"、純英文行
    整段無空白）。詞邊界＝抽取器重建的呈現，非內容；字元多重集相等才是真 byte-lock
    （任何 CJK 豆腐＝某字消失、任何內容增刪＝某字元計數變動，皆抓得到）。

    比對前先剝掉源裡的裸 LaTeX 控制序列（如 `\\newpage`）：它們是排版指令、被 pandoc
    消化成版面（換頁等），不渲成可見字，否則會誤判為「PDF 缺字」。
    """
    norm = unicodedata.normalize("NFC", text)
    norm = _LATEX_CMD_RE.sub(" ", norm)
    return Counter(re.findall(r"[0-9A-Za-z]|[一-鿿]", norm))


_CONTENT_CHAR_RE = re.compile(r"[0-9A-Za-z]|[一-鿿]")


def content_char_stream(text: str) -> list[str]:
    """同 content_token_multiset 的字元集，但回**有序清單**（保留出現順序）。

    給 export 的 byte-lock 位置化精確 diff 用（difflib.SequenceMatcher 比源端與 PDF 端
    的有序字元流，雙向報「源有 PDF 缺」/「PDF 多」並定位）。multiset（無序）仍保留給
    pass/fail 決策（不受版面重排影響、表格頁不誤報），有序流只用來**定位與報告**。
    """
    norm = unicodedata.normalize("NFC", text)
    norm = _LATEX_CMD_RE.sub(" ", norm)
    return _CONTENT_CHAR_RE.findall(norm)


# ── pandoc 解析（export 端的 soft-dep；doctor/version 共用）─────────────

def resolve_pandoc() -> str | None:
    """找得到的 pandoc，優先序（與 resolve_xelatex 同調＝受控資產優先、確定性輸出）：
      1. DOCSPEC_PANDOC 環境變數覆寫（指向 pandoc 執行檔）。
      2. data_dir/pandoc/pandoc(.exe)＝`docspec setup` 釘版下載的受控 pandoc。
      3. dev/系統後備：pypandoc 自帶 binary → 系統 PATH。
    找不到 → None。
    """
    env = os.environ.get("DOCSPEC_PANDOC")
    if env and Path(env).is_file():
        return env
    try:
        managed = pandoc_dir() / pandoc_exe_name()
        if managed.is_file():
            return str(managed)
    except Exception:
        pass  # platformdirs 缺席等 → 落到後備
    try:
        import pypandoc  # type: ignore
        return pypandoc.get_pandoc_path()
    except Exception:
        return shutil.which("pandoc")
