"""docspec rename-term <old> <new> [--article A] [--dry-run] — 全庫術語代換（prose-span 限定）。

確定性批次代換，**只在散文 span 內**（復用 spans.py `classify_deliverable`／`PROSE_KINDS`）：
code fence／inline code／URL／圖 path／裸識別碼一律 byte-exact 不動。額外守門：即便落在散文
span 內，若命中處與 ASCII 識別碼相鄰（前後為 `[A-Za-z0-9_]`）＝屬更大的識別碼 token（台中港
`OCC_LIMIT_WEATHER_API_*` 案），跳過不代換。`--dry-run` 列全部命中（檔＋前後文）零寫入；實跑
後維護各觸及節 prose 指紋（比照 normalize，不產假 ✎drift）並印收尾 render 指引。

定位（spec：rename-term）：真語料災難類——22 個一次性 replace script、自傷式重複、`OCC_LIMIT_*`
參數碼腐化——全源自無守門的手／regex 代換；守門邏輯引擎已有，代換一律走這條唯一正道。
"""

from __future__ import annotations

import argparse
import string
import sys
from dataclasses import dataclass

from dspx.commands._shared import BootstrapError, bootstrap, load_engine_schema, load_model
from dspx.commands.deliverable._normalize import _update_ledger_prose
from dspx.engine.spans import PROSE_KINDS, classify_deliverable

NAME = "rename-term"
HELP = ("deterministic batch term substitution inside prose spans only (code/URLs/image paths and "
        "bare identifiers like OCC_LIMIT_* stay byte-exact); supports --dry-run")

# ASCII 識別碼字元集：命中處緊鄰任一者＝屬更大的識別碼 token（OCC_LIMIT_*），跳過。
# 刻意只認 ASCII——CJK 的 str.isalnum() 為 True，用它會誤把「OCC系統」的中文鄰居當識別碼。
_ASCII_IDENT = frozenset(string.ascii_letters + string.digits + "_")


@dataclass(frozen=True)
class _Hit:
    offset: int
    section: str | None
    before: str
    after: str


def _is_ident_char(ch: str) -> bool:
    return ch in _ASCII_IDENT


def _find_prose_hits(text: str, old: str) -> list[_Hit]:
    """枚舉散文 span 內 `old` 的每一處命中；識別碼邊界（前/後為 ASCII 識別碼字元）跳過。"""
    out: list[_Hit] = []
    n = len(text)
    length = len(old)
    if length == 0:
        return out
    for sp in classify_deliverable(text):
        if sp.kind not in PROSE_KINDS:
            continue
        i = sp.start
        while True:
            idx = text.find(old, i, sp.end)   # 整段 old 須落在 [sp.start, sp.end) 內
            if idx == -1:
                break
            end = idx + length
            before_ch = text[idx - 1] if idx > 0 else ""
            after_ch = text[end] if end < n else ""
            if not (_is_ident_char(before_ch) or _is_ident_char(after_ch)):
                out.append(_Hit(
                    offset=idx, section=sp.section,
                    before=text[max(sp.start, idx - 12):idx],
                    after=text[end:min(sp.end, end + 12)]))
            i = end                            # 非重疊、往後掃
    return out


def _apply(text: str, hits: list[_Hit], old: str, new: str) -> str:
    """把命中處的 old 換成 new；由右而左 splice 使 offset 穩定。"""
    length = len(old)
    buf = text
    for h in sorted(hits, key=lambda h: h.offset, reverse=True):
        buf = buf[:h.offset] + new + buf[h.offset + length:]
    return buf


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec rename-term", description=HELP)
    parser.add_argument("old", help="term to replace (prose occurrences only)")
    parser.add_argument("new", help="replacement term")
    parser.add_argument("--article", default=None,
                        help="limit to one article (default: every article's deliverable)")
    parser.add_argument(
        "--dry-run", action="store_true", dest="dry_run",
        help="list every hit (file + before/after context) without writing anything")
    args = parser.parse_args(argv)

    if not args.old:
        sys.stderr.write("docspec: <old> term must be non-empty\n")
        return 2
    if args.old == args.new:
        sys.stderr.write("docspec: <old> and <new> are identical (nothing to rename)\n")
        return 2

    try:
        layout, config = bootstrap()
        load_engine_schema(config)
        leaves = load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code

    all_articles = layout.articles()
    if args.article is not None:
        if args.article not in all_articles:
            sys.stderr.write(f"docspec: no leaf sections found for article \"{args.article}\"\n")
            return 1
        articles = [args.article]
    else:
        articles = all_articles

    # 先掃全部命中（供 dry-run 一次列清）。
    per_article: list[tuple[str, str, list[_Hit]]] = []   # (article, text, hits)
    total_hits = 0
    for art in articles:
        latest = layout.docs_latest(art)
        if not latest.is_file():
            continue
        text = latest.read_text(encoding="utf-8")
        hits = _find_prose_hits(text, args.old)
        if hits:
            per_article.append((art, text, hits))
            total_hits += len(hits)

    if total_hits == 0:
        print(f"rename-term: \"{args.old}\" -> \"{args.new}\" — 0 prose hit(s); nothing to do.")
        return 0

    if args.dry_run:
        n_sections = len({(a, h.section) for a, _t, hs in per_article for h in hs})
        print(f"rename-term --dry-run: \"{args.old}\" -> \"{args.new}\" — {total_hits} hit(s) "
              f"across {len(per_article)} article(s)/{n_sections} section(s) (nothing written):")
        for art, _text, hits in per_article:
            for h in hits:
                loc = h.section or "(preamble)"
                print(f"  § {loc} [{art}]: …{h.before}[{args.old} -> {args.new}]{h.after}…")
        return 0

    # 實跑：逐 article 代換、寫檔、維護 prose 指紋（比照 normalize，避免假 drift）。
    touched_sections_report: list[str] = []
    for art, text, hits in per_article:
        new_text = _apply(text, hits, args.old, args.new)
        layout.docs_latest(art).write_text(new_text, encoding="utf-8", newline="\n")
        touched = {h.section for h in hits if h.section}
        _update_ledger_prose(layout, art, touched, new_text)
        named = sorted(touched)
        print(f"rename-term: \"{art}\" — {len(hits)} hit(s) across {len(touched)} section(s) "
              f"-> {layout.docs_latest(art)}")
        if named:
            print(f"  sections touched: {', '.join(named)}")
            touched_sections_report.extend(f"{art}:{s}" for s in named)

    # 收尾指引（散文變＝合法重寫路徑，不靜默；prose 指紋已自持，指引導向覆檢與 stale 遷移）。
    arts = ", ".join(a for a, _t, _h in per_article)
    print(f"  prose changed in: {arts}. Prose fingerprints were updated in-place (no false drift). "
          "Re-review the touched sections for term coherence; if any ledger is fingerprint-v1 "
          "run `docspec render <article> --rebaseline`.")
    return 0
