"""docspec export <article> — 把已凍結的定稿快照確定性轉成 PDF（Typst 預設）或發射期刊 .tex。

★薄引擎鐵律：export 只做確定性編排（subprocess pandoc → typst/LaTeX），不碰 PDF 二進位。
內容 byte-lock：一個字不改、只動呈現。

管線（兩軌）：
  Typst 軌（預設）：取快照 → pandoc -t typst → typst compile（受控字型）→ PDF。
  Journal 軌（emit-only）：取快照 → pandoc --template=<journal> → .tex（不編譯；交 Overleaf）。

soft-dep：pandoc/typst 缺了 → 印安裝指引、不 crash。
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
    pandoc_highlight_style,
    validate_format_config,
)
from dspx.layout import Layout, parse_semver

NAME = "export"
HELP = "Deterministically render a frozen snapshot to PDF (bundled template pack; content byte-locked, only presentation changes) → docs/exports/"

_INSTALL_HINT = (
    "For pandoc, install the export dependency: uv pip install 'docspec[export]' (or a system pandoc). "
    "For fonts / typst, run `docspec setup` (one-time)."
)

# 缺排版引擎/字型的統一提示。
_SETUP_HINT = (
    "Run `docspec setup` to install the controlled typst binary + OFL fonts (one-time, ~30 MB)."
)

# pandoc 輸入格式：標準 markdown 但關掉兩個擴充：
#   -citations         : @token（MPE @import、@提及）不被當成引用文獻。
#   -yaml_metadata_block: 文件中段的 --- ... --- 不被當 mid-doc YAML block（台中港風格
#                          用 --- 當 section divider，夾在兩個 --- 間的散文被 pandoc
#                          嘗試解析為 YAML 而失敗）；關掉後 --- 一律轉 thematic break。
_PANDOC_FROM = "markdown-citations-yaml_metadata_block"


# ── 相依 probe（soft dependency）────────────────────────────────────

def _pandoc_path() -> str | None:
    """找得到的 pandoc（委派 dspx.paths；優先 pypandoc 自帶 binary、退回系統 PATH）。"""
    return paths.resolve_pandoc()


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
        if "format" in data and isinstance(data["format"], dict):
            data = data["format"]
        raw = _section_merge(raw, data)
    return validate_format_config(raw)


# ── 快照預處理（剝 frontmatter、抽標題）─────────────────────────────

_H1_RE = re.compile(r"^#\s+(.+?)\s*$")
# pandoc 的 raw-LaTeX fenced 區塊（```{=latex} … ```），typst 軌不渲染（pandoc 丟棄）→
# fidelity 比對時要從源端剔除，否則 TikZ 標籤裡的 CJK 被誤判成「PDF 缺字」。
_RAW_LATEX_BLOCK_RE = re.compile(r"`{3,}\s*\{=(?:latex|tex)\}.*?`{3,}", re.DOTALL)


def _strip_raw_latex(md: str) -> str:
    """剔除 raw-LaTeX fenced 區塊（typst 不渲染它們）；供 typst 軌的 fidelity 源端使用。"""
    return _RAW_LATEX_BLOCK_RE.sub("", md)


def _collect_referenced_assets(layout: Layout, article: str, body_md: str) -> dict[str, Path]:
    """收集正文引用、且實際存在的圖片資產：{`assets/<file>` → corpus 源檔路徑}。

    交付物以扁平 `assets/<file>` 引用圖片（backend-neutral，Stage A）；實體檔住各節
    `corpus/<section>/assets/`。export 必須把被引用的圖檔 copy 進 build dir 的 `assets/`，
    typst/xelatex 才找得到（否則嵌圖渲不出）。引用了但 corpus 找不到的，交給 `docspec check`
    ⑨ 完整性閘擋（這裡只 copy 找得到的、不重複報錯）。
    """
    from dspx.render import find_image_refs
    refs = [r for r in find_image_refs(body_md) if r.startswith("assets/")]
    if not refs:
        return {}
    try:
        from dspx.commands._shared import load_model
        leaves = load_model(layout)
    except Exception:  # noqa: BLE001 — 載入失敗就不 copy（check 仍會擋斷引用）
        return {}
    name_to_path: dict[str, Path] = {}
    for lf in leaves:
        if getattr(lf, "article", None) != article:
            continue
        for p in lf.asset_files():
            name_to_path[f"assets/{p.name}"] = p
    return {r: name_to_path[r] for r in dict.fromkeys(refs) if r in name_to_path}


def _copy_assets_into(build: Path, assets: dict[str, Path]) -> None:
    """把收集到的圖片資產 copy 進 build/assets/（保留扁平檔名，對應正文的 `assets/<file>`）。"""
    if not assets:
        return
    adir = build / "assets"
    adir.mkdir(exist_ok=True)
    for ref, src in assets.items():
        if src.is_file():
            shutil.copy2(src, adir / Path(ref).name)


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




# ── PDF build（docspec-typst + typst；預設 render 軌，輕量、原生 CJK）──────────

def _build_pdf_typst(pandoc: str, typst: str, typst_template: Path, fonts_src: Path,
                     title: str, body_md: str, out: Path,
                     highlight_style: str = "tango", format_vars: list[str] | None = None,
                     assets: dict[str, Path] | None = None) -> None:
    """Typst 軌：pandoc -t typst（套 docspec-typst 模板）→ typst compile（受控字型）→ PDF。

    比 xelatex 軌輕：單一 typst binary、原生 CJK（--font-path 受控字型夾、--ignore-system-fonts
    確定性）、無 TinyTeX。docspec 不碰 PDF 二進位，只編排 subprocess。
    format_vars＝已驗證旋鈕編出的 pandoc -V 變數（fontsize/leading；compile_typst_vars）。
    """
    with tempfile.TemporaryDirectory(prefix="dspx_typst_") as td:
        build = Path(td)
        shutil.copy2(typst_template, build / "template.typ")
        (build / "doc.md").write_text(body_md, encoding="utf-8")
        # 圖片資產：被引用的 `assets/<file>` copy 進 build/assets/（typst image("assets/…") 解析；SVG 原生）
        _copy_assets_into(build, assets or {})

        # pandoc markdown → doc.typ（套自帶 typst 模板；標題經 -V 注入、節標題降一級＝root H1 已抽走；
        # 語法高亮＋格式旋鈕變數一併帶入）
        subprocess.run(
            [pandoc, "doc.md", "-f", _PANDOC_FROM, "-t", "typst",
             "--template=template.typ",
             "--shift-heading-level-by=-1",
             f"--syntax-highlighting={highlight_style}",
             "-V", f"title={title}",
             *(format_vars or []),
             "-o", "doc.typ"],
            cwd=str(build), check=True,
        )

        # typst compile（受控字型夾、忽略系統字型＝確定性）。
        proc = subprocess.run(
            [typst, "compile", "--font-path", str(fonts_src),
             "--ignore-system-fonts", "doc.typ", "doc.pdf"],
            cwd=str(build), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
        )
        if proc.returncode != 0:
            tail = "\n".join((proc.stdout or "").strip().splitlines()[-12:])
            raise RuntimeError(f"typst compilation failed:\n{tail}" if tail
                               else "typst compilation failed (no output)")
        produced = build / "doc.pdf"
        if not produced.is_file():
            raise RuntimeError("typst did not produce doc.pdf")
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(produced, out)


# ── journal 軌（BYO LaTeX，emit-only：pandoc --template=<journal> → .tex，不自編譯）──────

def _resolve_journal_template(journal: str | None, template_override: str | None) -> Path | None:
    """解析 journal 軌的 pandoc 模板（template.tex）：
      - --template <dir>＝使用者自有 journal pack（須含 template.tex）→ 用它。
      - --journal <name>＝隨包 adapter（ieee/elsevier）。
    回 template.tex 路徑；找不到/缺檔→None（呼叫端報錯）。
    """
    if template_override is not None:
        d = Path(template_override)
        cand = d / "template.tex" if d.is_dir() else d
        return cand if cand.is_file() else None
    if journal is not None:
        return paths.bundled_journal_template(journal)
    return None


def _emit_journal(pandoc: str, template: Path, title: str, body_md: str,
                  extra_slots: dict, out: Path) -> None:
    """journal 軌：把 slot contract 餵過 journal pandoc 模板 → emit `.tex`（不編譯、不驗 fidelity）。

    render-time slot 驗證：模板引用了 contract 沒有的變數＝印「unknown slot」（契約待 flex）；
    文件給了模板沒用到的 slot＝印「unused」（informational）。壞 slot 值在 build_slots 就拋。
    """
    from dspx import slots as slots_mod

    built = slots_mod.build_slots(title, body_md, extra_slots)
    template_text = template.read_text(encoding="utf-8")
    unknown, unused = slots_mod.validate_against_template(built, template_text)
    if unknown:
        sys.stderr.write(
            "docspec: ⚠ this journal template references variable(s) not in the slot contract "
            f"(the contract may need to flex): {', '.join(unknown)}\n")
    if unused:
        sys.stderr.write(
            f"docspec: (info) slots provided but unused by this template: {', '.join(unused)}\n")

    with tempfile.TemporaryDirectory(prefix="dspx_journal_") as td:
        build = Path(td)
        shutil.copy2(template, build / "template.tex")
        (build / "doc.md").write_text(body_md, encoding="utf-8")
        # slot metadata（除 body 外）寫成 YAML metadata file 餵 pandoc（list/people 才表達得了）。
        meta = {k: v for k, v in built.items() if k != "body"}
        (build / "meta.yaml").write_text(
            yaml.safe_dump(meta, allow_unicode=True, sort_keys=False), encoding="utf-8")
        # 兩欄期刊 class 拒 longtable → 用共用 Lua filter 把表格改寫成 tabular（table* 跨欄）。
        lua = paths.bundled_journal_filter()
        lua_args: list[str] = []
        if lua is not None:
            shutil.copy2(lua, build / "journal-tables.lua")
            lua_args = ["--lua-filter=journal-tables.lua"]
        subprocess.run(
            [pandoc, "doc.md", "-f", _PANDOC_FROM, "-t", "latex",
             "--template=template.tex", "--metadata-file=meta.yaml",
             *lua_args,
             "--number-sections", "--shift-heading-level-by=-1",
             "-o", "doc.tex"],
            cwd=str(build), check=True,
        )
        produced = build / "doc.tex"
        if not produced.is_file():
            raise RuntimeError("pandoc did not produce doc.tex")
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
                        help="output format (pdf only)")
    parser.add_argument("--engine", choices=["latex", "typst", "journal"], default=None,
                        help="render engine: typst (DEFAULT; docspec-typst owned template + lightweight typst binary, native CJK), "
                             "or journal (BYO LaTeX, EMIT-ONLY: emits a .tex through a journal pandoc template via the slot contract, "
                             "does NOT compile). latex is RETIRED (errors with guidance). "
                             "Overrides the project's export.engine config; default is typst. (--journal implies journal.)")
    parser.add_argument("--journal", default=None, metavar="NAME",
                        help="journal adapter for the emit-only journal track (bundled: ieee, elsevier; or use --template <dir> "
                             "with a template.tex for a BYO journal). Selecting it implies --engine journal.")
    parser.add_argument("--slots", default=None, metavar="FILE",
                        help="a YAML file of slot values (authors/abstract/keywords/…) for the journal/slot contract; "
                             "merged over the project export.slots config")
    parser.add_argument("--version", default=None, help="specific published version (semver X.Y.Z; default latest)")
    parser.add_argument("--latest", action="store_true",
                        help="export the working copy _latest (preview, not a final draft) instead of a frozen snapshot")
    parser.add_argument("--template", default=None, metavar="DIR",
                        help="BYO journal template directory (for --engine journal): a directory containing template.tex "
                             "(a pandoc LaTeX template honoring the slot contract). Selects journal track automatically.")
    parser.add_argument("--fonts", default=None, metavar="DIR",
                        help="a user font directory (e.g. a locally licensed real Kai font) to replace data_dir/fonts; "
                             "missing dir / missing required font files are rejected (no PDF produced)")
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
    # render 引擎：--engine 旗標 >（--journal/--template 隱含 journal）> 專案 export.engine config > 預設 typst。
    engine = args.engine or ("journal" if (args.journal or args.template) else None) or econf.get("engine") or "typst"

    # latex 軌已退場（docspec-cas LPPL 包已移除）。
    if engine == "latex":
        sys.stderr.write(
            "docspec: the LaTeX/xelatex track has been retired — "
            "use --engine typst (default) or --engine journal for journal submission (.tex emit-only).\n")
        return 1

    if engine == "typst" and args.format_config:
        from dspx.format_config import _TYPST_KNOB_FOLLOWUPS
        sys.stderr.write(
            "docspec: ⚠ Typst track applies the font-size / leading / code-highlight knobs; "
            f"these are NOT yet mapped (house defaults used): {', '.join(_TYPST_KNOB_FOLLOWUPS)}.\n")

    # 格式旋鈕：合成（專案 export.format ＋ --format-config 檔）並**驗證**。
    try:
        knobs = _resolve_format(econf, args.format_config)
    except FormatConfigError as exc:
        sys.stderr.write(f"docspec: invalid format knob — {exc} (no PDF produced)\n")
        return 1
    highlight_style = pandoc_highlight_style(knobs)

    resolved = _resolve_input(layout, args.article, args.version, args.latest)
    if resolved is None:
        return 1
    snapshot, label = resolved

    pandoc = _pandoc_path()
    if pandoc is None:
        sys.stderr.write(f"docspec: pandoc not found — export needs it. {_INSTALL_HINT}\n")
        return 1

    title, body_md = _split_title_body(
        snapshot.read_text(encoding="utf-8"), fallback_title=args.article)

    # ── journal 軌（BYO LaTeX、emit-only）：與兩條編譯軌分開，產 .tex、**不需字型**/不驗 fidelity ──
    if engine == "journal":
        template = _resolve_journal_template(args.journal, args.template)
        if template is None:
            sys.stderr.write(
                "docspec: journal template not found — use --journal {ieee,elsevier} or "
                "--template <dir> containing a template.tex.\n")
            return 1
        # slot 值：專案 export.slots config ＋ --slots 檔覆寫。
        extra_slots = dict(econf.get("slots") or {})
        if args.slots:
            sp = Path(args.slots)
            if not sp.is_file():
                sys.stderr.write(f"docspec: --slots file does not exist: {sp}\n")
                return 1
            try:
                data = yaml.safe_load(sp.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError as exc:
                sys.stderr.write(f"docspec: failed to parse --slots file ({sp}): {exc}\n")
                return 1
            if not isinstance(data, dict):
                sys.stderr.write(f"docspec: the --slots file's top level must be a mapping: {sp}\n")
                return 1
            extra_slots.update(data)
        out = layout.docs_export(args.article, label, "tex")
        from dspx.slots import SlotError
        try:
            _emit_journal(pandoc, template, title, body_md, extra_slots, out)
        except SlotError as exc:
            sys.stderr.write(f"docspec: invalid slot value — {exc} (no .tex produced)\n")
            return 1
        except subprocess.CalledProcessError as exc:
            sys.stderr.write(f"docspec: journal emit failed ({exc}).\n")
            return 1
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write(f"docspec: journal emit failed ({exc}).\n")
            return 1
        print(f"Emitted (journal track, not compiled): {out}")
        print("  Compile it with the journal's toolchain (Overleaf / its real .cls). docspec does not compile the journal track.")
        return 0

    # 字型（Typst 軌用）：--fonts 覆寫 > DOCSPEC_FONTS_SRC > data_dir/fonts（setup 落地）。
    # --fonts 缺夾/缺字型 → AssetError 清楚報錯、非零。
    try:
        fonts_src = paths.resolve_fonts_dir(args.fonts)
    except paths.AssetError as exc:
        sys.stderr.write(f"docspec: {exc}\n")
        return 1
    if fonts_src is None:
        sys.stderr.write(
            f"docspec: controlled fonts not found (data_dir/fonts) — PDF export needs them. {_SETUP_HINT}\n")
        return 1

    out = layout.docs_export(args.article, label, "pdf")
    # 被引用的圖片資產（兩條編譯軌共用）：copy 進 build dir 才渲得出嵌圖。
    assets = _collect_referenced_assets(layout, args.article, body_md)

    try:
        if engine == "typst":
            # ── Typst 軌（docspec-typst 自帶模板 + 受控 typst binary）──
            typst = paths.resolve_typst()
            if typst is None:
                sys.stderr.write(
                    "docspec: typst not found — the Typst track needs it. Install the controlled typst "
                    "(`docspec setup --with-typst`), or point DOCSPEC_TYPST at a typst binary.\n")
                return 1
            typst_template = paths.bundled_typst_template_dir()
            if typst_template is None or not (typst_template / "template.typ").is_file():
                sys.stderr.write("docspec: bundled Typst template not found (assets/templates/docspec-typst/) — the install may be incomplete.\n")
                return 1
            if _check_pack_integrity(typst_template, is_bundled=True, allow=args.allow) != 0:
                return 1
            from dspx.format_config import compile_typst_vars
            _build_pdf_typst(pandoc, typst, typst_template / "template.typ", fonts_src,
                             title, body_md, out,
                             highlight_style=highlight_style,
                             format_vars=compile_typst_vars(knobs), assets=assets)
        else:
            sys.stderr.write(f"docspec: unknown engine '{engine}' — valid engines: typst, journal.\n")
            return 1
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
    # typst 軌不渲染 raw-LaTeX 區塊（TikZ 等），故 fidelity 源端剔除它們、避免誤報缺字。
    verify_body = _strip_raw_latex(body_md) if engine == "typst" else body_md
    if not args.no_verify:
        if _verify_byte_lock(out, f"{title}\n{verify_body}", args.article, ack=args.ack) != 0:
            return 1

    print(f"Exported: {out}")
    return 0
