r"""docspec doctor — 唯一排版環境診斷入口（唯讀、離線、不改任何東西）。

★鐵律：doctor 只「看」、絕不「動」（不下載、不安裝、不寫 tex.lock）。每項一行
  OK / WARN / FAIL ＋（非 OK 時）一行可複製的修復指令。有任一 FAIL → exit 非零（給 CI）。

檢查項（全離線、不連網）：
  1. 程式版本 dspx.__version__。
  2. typst（預設 render 引擎）：paths.resolve_typst() 命中否（否 → FAIL：`docspec setup`）。
  3. pandoc：受控 pandoc 命中否（缺 → FAIL：`docspec setup`）。
  4. 字型：paths.REQUIRED_FONT_FILES 在 resolve_fonts_dir() 齊否（缺 → FAIL：`docspec upgrade`）。
     （字型兩軌共用：Typst --font-path 與期刊 xelatex 都要。）
  5. TinyTeX（xelatex，OPTIONAL）：預設 Typst 軌不用、期刊軌 emit-only 不自編；只有想本機編
     emit 出的期刊 `.tex` 才需要 → 缺 = WARN（`docspec setup --with-latex`），非 FAIL。
  6. tlmgr 套件（optional）：僅在 LaTeX 軌已裝時比對；未裝 → WARN「LaTeX 軌未裝（可選）」。

選配：
  --deep         實編一頁中文最小檔（預設 Typst 軌），驗文字層乾淨（抓 cid:0/壞字型）。
  --check-latest 才連網查新版（GitHub TinyTeX release）；結果寫 update-cache.json（TTL 7 天）；
                 離線/查無 → 靜默零噪音、不開背景執行緒。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from dspx import __version__, paths
from dspx.commands import setup as setup_cmd

NAME = "doctor"
HELP = "Diagnose the typesetting environment (read-only, offline; each item OK/WARN/FAIL + a fix command; any FAIL → non-zero exit code)"

_OK, _WARN, _FAIL = "OK", "WARN", "FAIL"
_MARK = {_OK: "[ OK ]", _WARN: "[WARN]", _FAIL: "[FAIL]"}

# --check-latest 結果快取 TTL（秒）：7 天。
_UPDATE_CACHE_TTL = 7 * 24 * 3600


class _Check:
    """單項結果：狀態、標題、明細、（非 OK 時）一行可複製修復指令。"""

    def __init__(self, status: str, title: str, detail: str, fix: str | None = None):
        self.status = status
        self.title = title
        self.detail = detail
        self.fix = fix


# ── 個別檢查（皆唯讀、離線）────────────────────────────────────────

def _check_version() -> _Check:
    return _Check(_OK, "docspec version", __version__)


def _check_typst() -> _Check:
    """typst＝預設 render 引擎；缺＝預設 export 出不了 PDF → FAIL。"""
    try:
        typst = paths.resolve_typst()
    except Exception as exc:  # noqa: BLE001 — platformdirs 缺席等
        return _Check(_FAIL, "typst (default engine)", f"resolution failed: {exc}", "docspec setup")
    if typst is None:
        return _Check(_FAIL, "typst (default engine)", "controlled typst not found", "docspec setup")
    return _Check(_OK, "typst (default engine)", str(typst))


def _check_tinytex() -> _Check:
    """TinyTeX/xelatex 為 OPTIONAL：預設 Typst 軌不用它，期刊軌是 emit-only（docspec 不自編）。
    只有想在本機用受控 toolchain 自行編譯 emit 出的期刊 `.tex` 才需要 → 缺＝WARN 非 FAIL。"""
    try:
        xelatex = paths.resolve_xelatex()
    except Exception as exc:  # noqa: BLE001 — platformdirs 缺席等
        return _Check(_WARN, "TinyTeX (xelatex, optional)", f"resolution failed: {exc}",
                      "docspec setup --with-latex")
    if xelatex is None:
        return _Check(_WARN, "TinyTeX (xelatex, optional)",
                      "not installed — only needed to locally compile an emitted journal .tex",
                      "docspec setup --with-latex")
    return _Check(_OK, "TinyTeX (xelatex, optional)", str(xelatex))


def _check_packages() -> _Check:
    """tex.lock 宣告的 tlmgr 套件 vs setup 當前期望（_TEX_PACKAGES）。"""
    lock = paths.read_tex_lock()
    if lock is None:
        return _Check(_WARN, "tlmgr packages", "tex.lock does not exist (not set up yet)", "docspec setup")
    declared = set(lock.get("tlmgr_packages") or [])
    if not declared:
        # 受控 LaTeX 軌（TinyTeX）未安裝＝可選、預設 Typst 軌不需要 → 非缺陷
        return _Check(_WARN, "tlmgr packages (optional)",
                      "LaTeX track not installed — optional, only for locally compiling a journal .tex",
                      "docspec setup --with-latex")
    expected = set(setup_cmd._TEX_PACKAGES)
    missing = sorted(expected - declared)
    if missing:
        return _Check(
            _WARN, "tlmgr packages",
            f"tex.lock is missing {len(missing)} expected package(s): {' '.join(missing)}",
            "docspec upgrade")
    return _Check(_OK, "tlmgr packages", f"tex.lock declares {len(declared)}, covering all expected")


def _check_fonts() -> _Check:
    try:
        fdir = paths.resolve_fonts_dir()
    except Exception as exc:  # noqa: BLE001
        return _Check(_FAIL, "fonts", f"resolution failed: {exc}", "docspec upgrade")
    if fdir is None:
        return _Check(_FAIL, "fonts", "controlled fonts directory not found", "docspec upgrade")
    missing = [f for f in paths.REQUIRED_FONT_FILES if not (fdir / f).is_file()]
    if missing:
        return _Check(
            _FAIL, "fonts",
            f"{fdir} is missing {len(missing)} file(s): {', '.join(missing)}", "docspec upgrade")
    return _Check(_OK, "fonts", f"{len(paths.REQUIRED_FONT_FILES)} files present in {fdir}")


def _check_pandoc() -> _Check:
    pandoc = paths.resolve_pandoc()
    if pandoc is None:
        return _Check(
            _FAIL, "pandoc", "controlled pandoc not found",
            "docspec setup")
    return _Check(_OK, "pandoc", str(pandoc))


# ── --deep：實編一頁中文最小檔（只有實編才現形的問題）─────────────────

# 中英混排、含 code（mono 字型）的最小驗證文：typst 編得過＝字型/渲染鏈真的可用。
_DEEP_DOC = (
    "# 排版環境健檢\n\n"
    "這是一頁中文最小驗證檔，混排英文 English 與行內 `code`，"
    "用來確認 typst＋CJK 字型鏈在實編下沒有缺字或壞字型。\n\n"
    "- 正體中文：臺中港、車隊、協定。\n"
    "- 數字與標點：123,456。（全形）\n"
)


def _check_deep() -> _Check:
    """實編一頁中文最小檔（預設 Typst 軌），檢查文字層乾淨（無 cid: 缺字標記）。"""
    pandoc = paths.resolve_pandoc()
    if pandoc is None:
        return _Check(_WARN, "deep test (real compile)", "pandoc missing, skipping real compile",
                      "docspec setup")
    typst = paths.resolve_typst()
    if typst is None:
        return _Check(_WARN, "deep test (real compile)", "typst missing, skipping real compile", "docspec setup")
    typst_template = paths.bundled_typst_template_dir()
    if typst_template is None or not (typst_template / "template.typ").is_file():
        return _Check(_WARN, "deep test (real compile)", "bundled Typst template not found, skipping real compile", None)
    try:
        fonts_src = paths.resolve_fonts_dir()
    except Exception:
        fonts_src = None
    if fonts_src is None:
        return _Check(_WARN, "deep test (real compile)", "fonts missing, skipping real compile", "docspec setup")

    try:
        from dspx.commands.export import _build_pdf_typst
        import tempfile
        with tempfile.TemporaryDirectory(prefix="dspx_doctor_") as td:
            out = Path(td) / "probe.pdf"
            _build_pdf_typst(pandoc, typst, typst_template / "template.typ", fonts_src,
                             "排版環境健檢", _DEEP_DOC, out)
            bad = _pdf_text_layer_problem(out)
    except Exception as exc:  # noqa: BLE001 — 實編失敗＝環境壞，FAIL 但不 crash
        return _Check(_FAIL, "deep test (real compile)", f"single-page Chinese minimal file failed to compile: {exc}",
                      "docspec doctor (fix the FAILs above first)")
    if bad:
        return _Check(_FAIL, "deep test (real compile)",
                      f"PDF text layer has broken/missing-glyph markers: {bad}", "docspec upgrade")
    return _Check(_OK, "deep test (real compile)", "single-page Chinese minimal file compiled, text layer clean")


def _pdf_text_layer_problem(pdf: Path) -> str | None:
    """掃 PDF 找壞字型徵兆（cid:0、無法對映字元）。乾淨 → None；否則回一段描述。

    用 pypdfium2 抽文字層（與 proof 同相依）；抽不出時退化成不報（避免誤殺）。
    """
    try:
        import pypdfium2 as pdfium  # type: ignore
    except Exception:
        return None  # 無 pypdfium2 → 無法檢文字層，不誤報（編得過已是強訊號）
    try:
        doc = pdfium.PdfDocument(str(pdf))
        try:
            text = "".join(doc[i].get_textpage().get_text_range() for i in range(len(doc)))
        finally:
            doc.close()
    except Exception:
        return None
    for marker in ("cid:", "�", "\x00"):
        if marker in text:
            return repr(marker)
    return None


# ── --check-latest：唯一連網路徑（同步、無背景執行緒、TTL 快取）─────────

def _update_cache_path() -> Path | None:
    try:
        return paths.data_dir() / "update-cache.json"
    except Exception:
        return None


def _read_update_cache() -> dict | None:
    p = _update_cache_path()
    if p is None or not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if time.time() - float(data.get("fetched_at", 0)) > _UPDATE_CACHE_TTL:
        return None  # 過期
    return data


def _fetch_latest_tinytex_tag() -> str | None:
    """連網查 TinyTeX 最新 release tag；任何失敗 → None（靜默、零噪音）。"""
    api = f"https://api.github.com/repos/{setup_cmd._TINYTEX_REPO}/releases/latest"
    try:
        req = urllib.request.Request(
            api, headers={"Accept": "application/vnd.github+json",
                          "User-Agent": "docspec-doctor"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.load(resp)
        tag = data.get("tag_name")
        return tag if isinstance(tag, str) and tag else None
    except (urllib.error.URLError, OSError, ValueError):
        return None


def _check_latest() -> _Check | None:
    """連網查新版（先讀 TTL 快取，過期才連網；查無/離線 → 靜默回 None）。"""
    cached = _read_update_cache()
    if cached is not None:
        latest = cached.get("latest_tinytex_tag")
    else:
        latest = _fetch_latest_tinytex_tag()
        if latest is not None:
            p = _update_cache_path()
            if p is not None:
                try:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(json.dumps(
                        {"fetched_at": time.time(), "latest_tinytex_tag": latest},
                        ensure_ascii=False, indent=2), encoding="utf-8")
                except OSError:
                    pass
    if not latest:
        return None  # 離線/查無：靜默零噪音
    current = setup_cmd._MANIFEST["tag"]
    if latest != current:
        return _Check(
            _WARN, "update check",
            f"docspec pins TinyTeX={current}, upstream latest={latest}",
            "upgrade the docspec program (uv tool install … --reinstall --no-cache), then `docspec upgrade`")
    return _Check(_OK, "update check", f"already at the upstream latest TinyTeX ({latest})")


# ── 主流程 ────────────────────────────────────────────────────────

def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec doctor", description=HELP)
    parser.add_argument("--deep", action="store_true",
                        help="really compile a single-page Chinese minimal file to verify the text layer (catches font problems that only surface on a real compile)")
    parser.add_argument("--check-latest", action="store_true",
                        help="go online to check for an upstream update (offline by default; result cached 7 days)")
    args = parser.parse_args(argv)

    checks: list[_Check] = [
        _check_version(),
        _check_typst(),
        _check_pandoc(),
        _check_fonts(),
        _check_tinytex(),
        _check_packages(),
    ]
    if args.deep:
        checks.append(_check_deep())
    if args.check_latest:
        latest = _check_latest()
        if latest is not None:
            checks.append(latest)

    print("docspec doctor — typesetting environment diagnosis\n")
    fixes: list[str] = []
    for c in checks:
        print(f"  {_MARK[c.status]} {c.title}: {c.detail}")
        if c.status != _OK and c.fix:
            print(f"         → fix: {c.fix}")
            fixes.append(c.fix)

    has_fail = any(c.status == _FAIL for c in checks)
    has_warn = any(c.status == _WARN for c in checks)
    print()
    if has_fail:
        print("✗ FAIL present — the typesetting environment is unusable. Follow the fix commands above.")
        return 1
    if has_warn:
        print("⚠ WARN present — usable, but worth addressing (see the fix commands above).")
        return 0
    print("✓ Typesetting environment healthy.")
    return 0
