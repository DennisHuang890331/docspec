"""docspec export <article> — 把已凍結的定稿快照確定性轉成 docspec-cas 風格 PDF。

★薄引擎鐵律：export 只做確定性編排（subprocess pandoc → LaTeX、subprocess xelatex），
docspec 自己不碰 PDF 二進位結構。內容 byte-lock：一個字不改、只動呈現。

管線（Phase C 定版＝docspec-cas 單欄 class（改自 Elsevier cas-sc）+ xelatex；typst/docx 路已退場）：
  1. 取凍結快照 docs/.../archive/v<N>.md（定稿、已剝標記）；--latest 才碰 _latest（預覽）。
  2. 剝 YAML frontmatter、抽首個 H1 當文件標題（注入 before.tex）、其餘為正文。
  3. 建 ASCII 暫存 build dir（避中文路徑炸 xelatex/fontspec）；copy 模板包＋隨包字型。
  4. pandoc <body>.md -t latex -V documentclass=docspec-cas --number-sections
       --shift-heading-level-by=-1 --syntax-highlighting=tango --lua-filter=docspec-tables.lua
       --data-dir=<pandoc-data> -H preamble.tex -B before.tex -s -o doc.tex
  5. xelatex ×2（解析到的受控 TinyTeX；env 隔離：PATH 前置 bin、cwd=build dir）。
  6. PDF copy 回 docs/exports/<article>_v<N>.pdf（絕不寫 archive/）。

soft-dep：pandoc 或 TinyTeX(xelatex) 缺了→印清楚安裝指引、跳過、不 crash。
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

from dspx import paths
from dspx.commands._shared import BootstrapError, bootstrap
from dspx.config import DEFAULTS
from dspx.format_config import (
    FormatConfigError,
    compile_format_config,
    compile_postmaketitle_fonts,
    pandoc_highlight_style,
    pandoc_table_metavars,
    validate_format_config,
)
from dspx.layout import Layout, parse_semver

NAME = "export"
HELP = "Deterministically render a frozen snapshot to PDF (bundled template pack; content byte-locked, only presentation changes) → docs/exports/"

_INSTALL_HINT = (
    "First run `docspec setup` (installs controlled TinyTeX + OFL fonts into data_dir; "
    "the first run downloads a few hundred MB, one-time); "
    "for pandoc, install the export dependency: uv pip install 'docspec[export]' (or a system pandoc). "
    "Override the TinyTeX path with the DOCSPEC_TINYTEX environment variable."
)

# 缺排版引擎/字型的統一提示（模型 A：uv install → docspec setup）。
_SETUP_HINT = (
    "The typesetting engine/fonts are not installed. Run `docspec setup` "
    "(installs controlled TinyTeX + OFL fonts into data_dir; the first run downloads a few hundred MB, one-time). "
    "Override the TinyTeX path with the DOCSPEC_TINYTEX environment variable."
)

# pandoc 輸入格式：標準 markdown 但關掉兩個擴充：
#   -citations         : @token（MPE @import、@提及）不被當成引用文獻。
#   -yaml_metadata_block: 文件中段的 --- ... --- 不被當 mid-doc YAML block（台中港風格
#                          用 --- 當 section divider，夾在兩個 --- 間的散文被 pandoc
#                          嘗試解析為 YAML 而失敗）；關掉後 --- 一律轉 thematic break。
_PANDOC_FROM = "markdown-citations-yaml_metadata_block"

# before.tex 內待注入的標題佔位字串。
_TITLE_PLACEHOLDER = "__DOCSPEC_TITLE__"
_FONTSIZE_PLACEHOLDER = "__DOCSPEC_FONTSIZES__"


# ── 相依 probe（soft dependency）────────────────────────────────────

def _pandoc_path() -> str | None:
    """找得到的 pandoc（委派 dspx.paths；優先 pypandoc 自帶 binary、退回系統 PATH）。"""
    return paths.resolve_pandoc()


def _xelatex_path() -> Path | None:
    """解析受控 TinyTeX 的 xelatex（委派 dspx.paths；env > data_dir > dev 後備）。"""
    return paths.resolve_xelatex()


def _template_dir() -> Path | None:
    """套件隨包的 docspec-cas 模板包（委派 dspx.paths；test/proof 仍用此名。）"""
    return paths.bundled_template_dir()


# ── 設定合併（缺鍵給預設）────────────────────────────────────────

def _export_config(config: dict) -> dict:
    """export 設定：頂層整塊可被 config 覆寫，故在此 merge 回預設、確保子鍵齊全。"""
    base = DEFAULTS["export"]
    econf = {**base, **(config.get("export") or {})}
    return econf


def _section_merge(base: dict, over: dict) -> dict:
    """旋鈕表逐區塊淺合併（over 同名區塊鍵覆蓋 base，其餘區塊保留 base）。"""
    out = {k: dict(v) if isinstance(v, dict) else v for k, v in base.items()}
    for section, body in over.items():
        if isinstance(body, dict) and isinstance(out.get(section), dict):
            out[section] = {**out[section], **body}
        else:
            out[section] = body
    return out


def _resolve_format(econf: dict, format_config_file: str | None) -> dict:
    """合成最終旋鈕表並驗證：專案 config 的 export.format（預設）＋ --format-config 檔覆寫。

    回**已驗證**的完整旋鈕表（可直接 compile）。任一層含不合法值 → 拋 FormatConfigError
    （由 run() 攔成清楚錯誤、export 非零、不產 LaTeX——壞值/幻覺永不進 xelatex）。
    """
    raw = dict(econf.get("format") or {})
    if format_config_file is not None:
        path = Path(format_config_file)
        if not path.is_file():
            raise FormatConfigError(f"the file given to --format-config does not exist: {path}")
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise FormatConfigError(f"failed to parse the --format-config file ({path}): {exc}") from exc
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise FormatConfigError(f"the --format-config file's top level must be a key-value mapping: {path}")
        # 檔可整塊是旋鈕表，或包在 format: 鍵下；兩種都收。
        if "format" in data and isinstance(data["format"], dict):
            data = data["format"]
        raw = _section_merge(raw, data)
    return validate_format_config(raw)


# ── 快照預處理（剝 frontmatter、抽標題）─────────────────────────────

_H1_RE = re.compile(r"^#\s+(.+?)\s*$")


def _split_title_body(text: str, fallback_title: str) -> tuple[str, str]:
    """剝 YAML frontmatter、抽首個 H1 當標題；回 (title, body)。

    凍結快照本就無 frontmatter（publish 已剝），但 --latest 工作副本有；一律防禦性剝除。
    首個 H1 移出正文（標題改由 before.tex `\\title` 注入、避免重複），其餘為正文。
    無 H1 → 用 fallback（文章名），正文原樣。
    """
    from dspx.frontmatter import parse_frontmatter
    _, body = parse_frontmatter(text)
    lines = body.split("\n")
    title = fallback_title
    out: list[str] = []
    taken = False
    for line in lines:
        if not taken:
            m = _H1_RE.match(line)
            if m:
                title = m.group(1).strip()
                taken = True
                continue  # 吃掉這一行，不進正文
        out.append(line)
    return title, "\n".join(out).lstrip("\n")


def _tex_escape_title(title: str) -> str:
    """標題注入 LaTeX before.tex 前的最小跳脫（標題多為散文，僅處理常見特殊字）。"""
    repl = {
        "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
        "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
        "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
    }
    return "".join(repl.get(c, c) for c in title)


# ── PDF build（docspec-cas + xelatex）──────────────────────────────────

def _xelatex_failure_detail(build: Path, captured: str) -> str:
    """xelatex 失敗時萃取可讀錯誤：優先 doc.log 內 '!' 起的 LaTeX 錯誤行（含脈絡），
    退回 stdout 尾段。讓 export/doctor 不再只回一句 exit code（黑箱）。"""
    detail: list[str] = []
    log = build / "doc.log"
    if log.is_file():
        try:
            loglines = log.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            loglines = []
        for i, ln in enumerate(loglines):
            if ln.startswith("!"):  # LaTeX 錯誤行
                detail = loglines[i:i + 5]
                break
        if not detail:
            detail = loglines[-12:]
    if not detail and captured:
        detail = captured.strip().splitlines()[-12:]
    body = "\n".join(detail).strip()
    return f"xelatex compilation failed:\n{body}" if body else "xelatex compilation failed (no log available)"


def _build_pdf(pandoc: str, xelatex: Path, template_dir: Path, fonts_src: Path,
               title: str, body_md: str, out: Path,
               format_override: str = "", highlight_style: str = "tango",
               postmaketitle_fonts: str = "", table_metavars: list[str] | None = None) -> None:
    """在 ASCII 暫存區組裝 docspec-cas build、跑 pandoc→xelatex×2、產物 copy 到 out。

    字型不再隨 wheel：從 data_dir/fonts（setup 落地處；dev 後備＝舊套件內字型夾）
    copy 進 build dir 的 fonts/（preamble 的 Path=./fonts/ 不變）。

    format_override＝已驗證旋鈕編出的 LaTeX 覆寫片段（空＝不覆寫、純用 bundled preamble）；
    以 `-H format.tex` 在 bundled `preamble.tex` **之後**注入，故覆寫生效。
    highlight_style＝旋鈕 code.highlight（已在 enum 內），帶進 pandoc --syntax-highlighting。
    """
    plat_exe_dir = xelatex.parent  # TinyTeX 的 bin/<plat>/
    with tempfile.TemporaryDirectory(prefix="dspx_cassc_") as td:
        build = Path(td)
        # 模板包：cls/sty/preamble/before/lua 平鋪；pandoc-data 保子夾結構。
        for name in ("docspec-cas.cls", "docspec-cas-common.sty", "preamble.tex",
                     "before.tex", "docspec-tables.lua"):
            shutil.copy2(template_dir / name, build / name)
        shutil.copytree(template_dir / "pandoc-data", build / "pdata")
        # 字型：從受控字型夾 copy 進 build/fonts（preamble Path=./fonts/ 對應）
        (build / "fonts").mkdir()
        for fp in fonts_src.iterdir():
            if fp.is_file():
                shutil.copy2(fp, build / "fonts" / fp.name)

        # before.tex 注入標題＋post-\maketitle 字級階梯（C4：base_size 旋鈕在 maketitle 後生效）。
        before = build / "before.tex"
        before_text = before.read_text(encoding="utf-8").replace(
            _TITLE_PLACEHOLDER, _tex_escape_title(title))
        before_text = before_text.replace(_FONTSIZE_PLACEHOLDER, postmaketitle_fonts)
        before.write_text(before_text, encoding="utf-8")

        # 正文寫進 build（ASCII 路徑，xelatex/fontspec 安全）
        (build / "doc.md").write_text(body_md, encoding="utf-8")

        # format-config 覆寫片段：以 -H 在 bundled preamble.tex **之後**注入（覆寫生效）。
        # 空＝不覆寫（純用 bundled preamble，行為＝現狀）。
        header_includes = ["-H", "preamble.tex"]
        if format_override:
            (build / "format.tex").write_text(format_override, encoding="utf-8")
            header_includes += ["-H", "format.tex"]

        # pandoc → doc.tex（驗證過的 recipe；--syntax-highlighting 由旋鈕 code.highlight 帶；
        # 表格旋鈕 size/column_rules 走 -M 餵 docspec-tables.lua）
        subprocess.run(
            [pandoc, "doc.md", "-f", _PANDOC_FROM, "-t", "latex",
             "-V", "documentclass=docspec-cas",
             "--number-sections", "--shift-heading-level-by=-1",
             f"--syntax-highlighting={highlight_style}",
             "--lua-filter=docspec-tables.lua",
             *(table_metavars or []),
             "--data-dir=pdata",
             *header_includes, "-B", "before.tex",
             "-s", "-o", "doc.tex"],
            cwd=str(build), check=True,
        )

        # xelatex ×2：env 隔離（PATH 前置 TinyTeX bin、cwd=build），交叉引用/頁碼收斂。
        env = dict(os.environ)
        env["PATH"] = str(plat_exe_dir) + os.pathsep + env.get("PATH", "")
        for _ in range(2):
            proc = subprocess.run(
                [str(xelatex), "-interaction=nonstopmode", "-halt-on-error", "doc.tex"],
                cwd=str(build), env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                # ★別用系統 locale 解（Windows cp950 會炸在 xelatex 輸出的非-cp950 位元）；
                # 固定 utf-8 + replace，確定性且不 crash。
                text=True, encoding="utf-8", errors="replace",
            )
            if proc.returncode != 0:
                # 失敗時透出 doc.log 的真錯誤（不再只回 exit code）。
                raise RuntimeError(_xelatex_failure_detail(build, proc.stdout or ""))

        produced = build / "doc.pdf"
        if not produced.is_file():
            raise RuntimeError("xelatex did not produce doc.pdf")
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(produced, out)


# ── runtime byte-lock 驗證（產出 PDF 後抽文字、與源做 content-token 比對）────

def _sample(counter, n: int = 12) -> str:
    """把多重集差（Counter）格式成可讀樣本字串：`字×3, A×1 …`。"""
    items = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    shown = ", ".join(f"{tok!r}×{cnt}" for tok, cnt in items[:n])
    more = " …" if len(items) > n else ""
    return shown + more


def _is_cjk(ch: str) -> bool:
    return "一" <= ch <= "鿿"


def _source_anchored_stream(body_md: str) -> tuple[list[str], list[str]]:
    """源端有序內容字元流＋每字「最近 markdown 標題」錨（供差異定位、源端為準）。"""
    import re as _re
    chars: list[str] = []
    anchors: list[str] = []
    heading = "(preamble)"
    for line in _nfc(body_md).splitlines():
        s = line.strip()
        if s.startswith("#"):
            heading = s.lstrip("#").strip() or heading
            continue
        clean = paths._LATEX_CMD_RE.sub(" ", line)
        for ch in paths._CONTENT_CHAR_RE.findall(clean):
            chars.append(ch)
            anchors.append(heading)
    return chars, anchors


def _pdf_paged_stream(pdf) -> tuple[list[str], list[int]]:
    """PDF 端有序內容字元流＋每字所在頁碼（1-indexed；用 page.chars 帶座標的逐字）。"""
    chars: list[str] = []
    pages: list[int] = []
    for i, page in enumerate(pdf.pages, start=1):
        raw = "".join(c.get("text", "") for c in page.chars)
        clean = paths._LATEX_CMD_RE.sub(" ", _nfc(raw))
        for ch in paths._CONTENT_CHAR_RE.findall(clean):
            chars.append(ch)
            pages.append(i)
    return chars, pages


def _nfc(text: str) -> str:
    """NFC 正規化（與 paths.content_* 同一套，供 byte-lock 有序流前處理）。"""
    import unicodedata
    return unicodedata.normalize("NFC", text)


def _window(seq: list[str], lo: int, hi: int, pad: int = 12) -> str:
    """源端字元窗（差異前後文，給人/agent 對位）。"""
    a = max(0, lo - pad)
    b = min(len(seq), hi + pad)
    return ("…" if a > 0 else "") + "".join(seq[a:b]) + ("…" if b < len(seq) else "")


def _verify_byte_lock(out: Path, body_md: str, article: str = "", *, ack: bool = False) -> int:
    """產出 PDF 後 runtime 驗**渲染忠實度**：源正文 vs PDF 抽回文字的位置化精確 diff。

    正名「渲染忠實度檢查」（防竄改改由結構 gate 擋）：這裡只問「凍結內容有沒有在轉檔中
    被吃掉/變形」。比對分兩層，刻意分離「決策」與「定位」（教訓＝機械 drift 才擋、版面
    重排不誤報；CLAUDE.md 操作鐵律 1）：

      ① **決策（pass/fail）走 multiset 淨損**：CJK 字元的淨缺失（src - got）＝豆腐/缺字型/
         丟段，是真內容事故 → 紅燈。multiset 不受 PDF 閱讀順序重排影響（表格/多欄頁不誤報）。
      ② **定位＋雙向報走有序 diff**：difflib.SequenceMatcher 比源端有序流 vs PDF 端有序流，
         報「源有 PDF 缺」（delete）含 page N＋源端最近標題＋前後文窗，並雙向附「PDF 多」
         （insert，多為連字/重複，informational）。

    拉丁/數字差異一律 **informational**（等寬字/語法高亮的字元級抽取本就有損）——印出但
    不致 fail（取代舊的 5% 硬容差）。

    回傳：0＝忠實/僅拉丁雜訊/pdfplumber 缺（soft-dep 跳過）/`--ack`（已 proof 複判）；
         1＝CJK 淨缺失（疑似豆腐/丟段）。
    """
    from collections import Counter

    try:
        import pdfplumber  # type: ignore
    except Exception:
        sys.stderr.write(
            "docspec: ⚠ pdfplumber not installed — skipping export render-fidelity verification (PDF was still produced). "
            "Install: uv pip install 'docspec[export]' (includes pdfplumber).\n")
        return 0

    try:
        pdf_cm = pdfplumber.open(str(out))
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(
            f"docspec: ⚠ pdfplumber failed to open the PDF ({exc}) — skipping verification (PDF was still produced).\n")
        return 0

    with pdf_cm as pdf:
        pdf_chars, pdf_pages = _pdf_paged_stream(pdf)
    src_chars, src_anchors = _source_anchored_stream(body_md)

    # ① 決策：CJK 淨缺失（multiset，順序無關、表格不誤報）。
    src_ms = Counter(src_chars)
    got_ms = Counter(pdf_chars)
    missing = src_ms - got_ms
    extra = got_ms - src_ms
    miss_cjk = Counter({k: v for k, v in missing.items() if _is_cjk(k)})
    miss_latin = Counter({k: v for k, v in missing.items() if not _is_cjk(k)})
    cjk_lost = bool(miss_cjk)

    # ② 定位＋雙向：有序 diff（只在有 CJK 缺失或要報拉丁雜訊時走，省成本）。
    import difflib
    sm = difflib.SequenceMatcher(None, src_chars, pdf_chars, autojunk=False)
    del_runs = []   # (src_lo, src_hi, page, anchor, window, n_cjk)
    ins_runs = []   # (pdf_lo, pdf_hi, page, text)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("delete", "replace") and i2 > i1:
            run = src_chars[i1:i2]
            n_cjk = sum(1 for c in run if _is_cjk(c))
            page = pdf_pages[min(j1, len(pdf_pages) - 1)] if pdf_pages else 0
            anchor = src_anchors[i1] if i1 < len(src_anchors) else ""
            del_runs.append((i1, i2, page, anchor, _window(src_chars, i1, i2), n_cjk))
        if tag in ("insert", "replace") and j2 > j1:
            page = pdf_pages[min(j1, len(pdf_pages) - 1)] if pdf_pages else 0
            ins_runs.append((j1, j2, page, "".join(pdf_chars[j1:j2])))

    if not cjk_lost:
        # 通過（或只有拉丁雜訊/PDF 連字）；有差異就 informational 印一行、不 fail。
        latin_lost = sum(miss_latin.values())
        if latin_lost or extra:
            sys.stderr.write(
                f"docspec: ✓ render fidelity passed (no CJK loss). informational: Latin/digit extraction differs by "
                f"{latin_lost} char(s), PDF side has {sum(extra.values())} extra char(s) (monospace/ligature extraction noise, not lost content).\n")
        return 0

    # CJK 缺失 → 高度可疑。--ack（已 proof 複判）仍印報告但回 0。
    tag = "⚠ (--ack: re-checked, allowed)" if ack else "✗"
    sys.stderr.write(
        f"docspec: {tag} render fidelity: detected a net CJK character loss of {sum(miss_cjk.values())} char(s) "
        f"(suspected missing-glyph boxes / missing font / dropped segment). In source but missing from PDF: {_sample(miss_cjk)}\n")
    cjk_del = [r for r in del_runs if r[5] > 0][:6]
    for _i1, _i2, page, anchor, win, n_cjk in cjk_del:
        proof_hint = f"page_{page:0{max(2, len(str(len(pdf_pages))))}d}.png" if page else "?"
        sys.stderr.write(
            f"    page {page} · source §{anchor or '(preamble)'} · {n_cjk} CJK missing · context \"{win}\""
            f"  → run docspec proof{f' {article}' if article else ''} and look at _proof/.../{proof_hint}\n")
    if ack:
        return 0
    sys.stderr.write(
        "  CJK here cannot be extracted back from the PDF = the render may be eating characters. Run `docspec proof` to that page to re-check:\n"
        "    · real missing-glyph boxes / dropped segment → fix the font/layout and re-export.\n"
        "    · proof shows the text and it's just an extraction misfire (e.g. text inside an image) → add --ack to allow it (or --no-verify to skip entirely).\n")
    return 1


# ── 逃生口 gate：偵測內建模板包被手改（規則 b＝只用旋鈕；例外 a＝手改要 --allow）────

def _check_pack_integrity(template_dir: Path, is_bundled: bool, allow: bool) -> int:
    """內建模板包完整性 gate（engine 後盾、三家通用）。

    docctrine：格式變動走**驗證過的旋鈕**（rule b）；真要手改內建包＝例外，要人明確 `--allow`
    （rule a）。`--template` 使用者自有包＝合法替換、**跳過此 gate**（is_bundled=False）。

    比 pack 內 `.pack-hashes.json` 基線：不符且無 --allow → 拒（非零、不 build）。基線缺（dev
    源樹未生成）→ 印提示、放行（不破開發流）。誠實：bundled pack 在 site-packages、agent 少在
    cwd，故 hook 只是 defense-in-depth、**此 engine gate 才是真擋**。
    回傳 0＝放行、1＝拒。
    """
    if not is_bundled:
        return 0  # 使用者 --template 包：合法替換，不設限
    baseline = paths.read_pack_baseline(template_dir)
    if baseline is None:
        sys.stderr.write(
            "docspec: ⚠ the bundled template pack has no integrity baseline (.pack-hashes.json) — skipping the tamper gate "
            "(normal in a dev source tree; a release wheel should include it).\n")
        return 0
    live = paths.pack_content_hashes(template_dir)
    changed = sorted(set(baseline) | set(live))
    diffs = [f for f in changed if baseline.get(f) != live.get(f)]
    if not diffs:
        return 0
    verb = "⚠ (--allow: hand-edited pack explicitly allowed)" if allow else "✗"
    sys.stderr.write(
        f"docspec: {verb} the bundled template pack was hand-edited ({len(diffs)} file(s) differ from the baseline): "
        f"{', '.join(diffs[:8])}{' …' if len(diffs) > 8 else ''}\n")
    if allow:
        return 0
    sys.stderr.write(
        "  Make format changes through validated knobs (--format-config; see docspec guide); "
        "to really change the layout, use your own template pack with --template <dir>. To use this hand-edited bundled pack, add --allow.\n")
    return 1


# ── 選輸入快照 ────────────────────────────────────────────────────

def _resolve_input(layout: Layout, article: str, version: str | None,
                   latest: bool) -> tuple[Path, str] | None:
    """回 (快照路徑, 版本標籤)；找不到→印錯誤回 None。"""
    if latest:
        path = layout.docs_latest(article)
        if not path.is_file():
            sys.stderr.write(f"docspec: _latest not found ({path}) — render/publish first.\n")
            return None
        sys.stderr.write("docspec: ⚠ --latest exports the working copy (not a final draft, no version number, may contain drift).\n")
        return path, "latest"
    if version is not None:
        if parse_semver(version) is None:
            sys.stderr.write(f"docspec: --version \"{version}\" is not valid semver (X.Y.Z).\n")
            return None
        path = layout.docs_snapshot(article, version)
        if not path.is_file():
            sys.stderr.write(f"docspec: snapshot for version v{version} not found ({path}).\n")
            return None
        return path, version
    versions = layout.existing_versions(article)
    if not versions:
        sys.stderr.write(
            f"docspec: article \"{article}\" has no published snapshot yet — first `docspec publish {article}`"
            f" (or --latest to export a preview of the working copy).\n")
        return None
    top = max(versions)
    label = f"{top[0]}.{top[1]}.{top[2]}"
    return layout.docs_snapshot(article, label), label


# ── 主流程 ────────────────────────────────────────────────────────

def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec export", description=HELP)
    parser.add_argument("article", help="name of the article to export")
    parser.add_argument("--format", choices=["pdf"], default="pdf",
                        help="output format (currently pdf only = bundled template pack/xelatex; the typst/docx paths are retired)")
    parser.add_argument("--version", default=None, help="specific published version (semver X.Y.Z; default latest)")
    parser.add_argument("--latest", action="store_true",
                        help="export the working copy _latest (preview, not a final draft) instead of a frozen snapshot")
    parser.add_argument("--template", default=None, metavar="DIR",
                        help="a user template pack directory (with the same cls/sty/preamble.tex/before.tex/lua/pandoc-data "
                             "structure) to replace the bundled pack; use it for a different layout/journal template without editing bundled files")
    parser.add_argument("--fonts", default=None, metavar="DIR",
                        help="a user font directory (e.g. a locally licensed real Kai font) to replace data_dir/fonts; "
                             "copied into the build at build time")
    parser.add_argument("--format-config", default=None, metavar="FILE",
                        help="a per-article format-knob override file (YAML; overrides the project export.format knobs of the same name). "
                             "Knobs = validated values (font enum / font-size range / table style…); bad values are rejected before "
                             "compiling to LaTeX and no PDF is produced")
    parser.add_argument("--allow", action="store_true",
                        help="escape hatch: explicitly allow exporting with a hand-edited bundled template pack (by default any detected change is rejected, "
                             "forcing you through knobs or your own --template pack)")
    parser.add_argument("--ack", action="store_true",
                        help="render fidelity: run the check and print the diff locations, but return 0 (you've already re-checked that page with docspec proof "
                             "= render is faithful / extraction misfire, not real character loss)")
    parser.add_argument("--no-verify", action="store_true",
                        help="skip the post-export render-fidelity verification entirely (for debugging; --ack is the proper \"re-checked, allowed\")")
    args = parser.parse_args(argv)

    try:
        layout, config = bootstrap()
    except BootstrapError as exc:
        return exc.exit_code

    econf = _export_config(config)

    # 格式旋鈕：合成（專案 export.format ＋ --format-config 檔）並**驗證**。
    # ★防幻覺閘門：任何不合法值（不在 enum / 超範圍）在此處就拋、export 非零、不產 LaTeX。
    try:
        knobs = _resolve_format(econf, args.format_config)
    except FormatConfigError as exc:
        sys.stderr.write(f"docspec: invalid format knob — {exc} (no LaTeX/PDF produced)\n")
        return 1
    format_override = compile_format_config(knobs)
    postmaketitle_fonts = compile_postmaketitle_fonts(knobs)
    highlight_style = pandoc_highlight_style(knobs)
    table_metavars = pandoc_table_metavars(knobs)

    resolved = _resolve_input(layout, args.article, args.version, args.latest)
    if resolved is None:
        return 1
    snapshot, label = resolved

    pandoc = _pandoc_path()
    if pandoc is None:
        sys.stderr.write(f"docspec: pandoc not found — export needs it. {_INSTALL_HINT}\n")
        return 1

    xelatex = _xelatex_path()
    if xelatex is None:
        sys.stderr.write(
            f"docspec: controlled TinyTeX (xelatex) not found — PDF export needs it. {_SETUP_HINT}\n")
        return 1

    # 模板包：--template 覆寫內建 docspec-cas（缺夾/缺檔 → AssetError 清楚報錯、非零）。
    try:
        template_dir = paths.resolve_template_dir(args.template)
    except paths.AssetError as exc:
        sys.stderr.write(f"docspec: {exc}\n")
        return 1
    if template_dir is None:
        sys.stderr.write("docspec: bundled template not found (assets/templates/docspec-cas/) — the install may be incomplete.\n")
        return 1

    # 逃生口 gate：用內建包時偵測手改（規則 b＝走旋鈕）；--template 自有包跳過。
    if _check_pack_integrity(template_dir, is_bundled=(args.template is None),
                             allow=args.allow) != 0:
        return 1

    # 字型：--fonts 覆寫 data_dir/fonts（缺夾/缺字型 → AssetError 清楚報錯、非零）。
    try:
        fonts_src = paths.resolve_fonts_dir(args.fonts)
    except paths.AssetError as exc:
        sys.stderr.write(f"docspec: {exc}\n")
        return 1
    if fonts_src is None:
        sys.stderr.write(
            f"docspec: controlled fonts not found (data_dir/fonts) — PDF export needs them. {_SETUP_HINT}\n")
        return 1

    title, body_md = _split_title_body(
        snapshot.read_text(encoding="utf-8"), fallback_title=args.article)

    out = layout.docs_export(args.article, label, "pdf")
    try:
        _build_pdf(pandoc, xelatex, template_dir, fonts_src, title, body_md, out,
                   format_override=format_override, highlight_style=highlight_style,
                   postmaketitle_fonts=postmaketitle_fonts, table_metavars=table_metavars)
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(f"docspec: PDF conversion failed ({exc}) — skipped. {_INSTALL_HINT}\n")
        return 1
    except Exception as exc:  # noqa: BLE001 — 任何轉檔例外都降級、不 crash
        sys.stderr.write(f"docspec: PDF conversion failed ({exc}) — skipped. {_INSTALL_HINT}\n")
        return 1

    # runtime 渲染忠實度：產出 PDF 後抽文字、與源「定稿全文」位置化精確 diff。
    # 參照＝title＋body（標題行被移出正文注入 \title，但仍渲進 PDF，故要併回比對）。
    # CJK 淨缺失＝渲染吃字（嚴重）→ 非零；--ack＝已 proof 複判放行；--no-verify 全跳；
    # pdfplumber 缺＝soft-dep 跳。
    if not args.no_verify:
        if _verify_byte_lock(out, f"{title}\n{body_md}", args.article, ack=args.ack) != 0:
            return 1

    print(f"Exported: {out}")
    return 0
