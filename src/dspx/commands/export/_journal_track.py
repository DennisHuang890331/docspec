"""journal 軌（BYO LaTeX，emit-only：pandoc --template=<journal> → .tex，不自編譯）。"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

from dspx.engine import paths

from ._config import _PANDOC_FROM


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


# journal 軌：作者/摘要/關鍵字進了 slot（→期刊 class 的 \author/\affiliation/abstract 巨集）後，
# body 仍是整份快照、開頭重複作者列＋Abstract/Keywords 節 → 期刊範本從不重複這些。砍掉 body 開頭
# 到「第一個真正內容標題（如 Introduction）」之間的前置內容，讓 .tex 匹配期刊示範。
_ATX_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FRONTMATTER_HEADINGS = {
    "abstract", "keywords", "key words", "index terms",
    "摘要", "關鍵詞", "关键词", "關鍵字", "关键字",
}


def _strip_journal_frontmatter(body_md: str) -> str:
    """砍掉 body 開頭重複 slot 的前置內容（作者列＋摘要/關鍵字節），保留至第一個內容標題起。
    找不到內容標題＝整份無 heading → 保守不動。"""
    def _norm(t: str) -> str:
        t = re.sub(r"^[\dⅠ-ⅩivxIVX一二三四五六七八九十]+[.、)）]?\s*", "", t)
        return t.strip().lower()
    lines = body_md.splitlines()
    for i, line in enumerate(lines):
        m = _ATX_RE.match(line)
        if m and _norm(m.group(2)) not in _FRONTMATTER_HEADINGS:
            return "\n".join(lines[i:])   # 第一個非前置標題＝正文起點
    return body_md


def _emit_journal(pandoc: str, template: Path, title: str, body_md: str,
                  extra_slots: dict, out: Path) -> None:
    """journal 軌：把 slot contract 餵過 journal pandoc 模板 → emit `.tex`（不編譯、不驗 fidelity）。

    render-time slot 驗證：模板引用了 contract 沒有的變數＝印「unknown slot」（契約待 flex）；
    文件給了模板沒用到的 slot＝印「unused」（informational）。壞 slot 值在 build_slots 就拋。
    """
    from dspx.typeset import slots as slots_mod

    # 作者/摘要進了 slot → 砍掉 body 開頭重複的作者列＋摘要/關鍵字節（匹配期刊範本、不重複）。
    if extra_slots.get("abstract") or extra_slots.get("authors"):
        body_md = _strip_journal_frontmatter(body_md)

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
        (build / "doc.md").write_text(body_md, encoding="utf-8", newline="\n")
        # slot metadata（除 body 外）寫成 YAML metadata file 餵 pandoc（list/people 才表達得了）。
        meta = {k: v for k, v in built.items() if k != "body"}
        (build / "meta.yaml").write_text(
            yaml.safe_dump(meta, allow_unicode=True, sort_keys=False), encoding="utf-8",
            newline="\n")
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
