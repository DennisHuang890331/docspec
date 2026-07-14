"""docspec find <QUERY> [SCOPE] [--in FACE,…] [--regex] [--limit N] [--numbers] [--json]
   — agent 快速查找：回「哪一節、哪個面、哪一行/位置、片段」，讓 agent 定位後只讀相關段、省 token。

搜面（資料已在記憶體、零新讀取路徑）：prose（`docs/<a>_latest.md` 過 `mask_non_prose`，code/URL 不算）／
concept／decisions（statement＋rationale）／material／glossary（canonical＋aliases＋definition）／audit。
純確定性子字串／regex（recall 導向、不做語義——消費者是 LLM，語義它自己判）。

`--numbers`＝值層呈現器（V10 重生）：森林級聚合「同指涉底下出現哪些值＋出處」，**只攤不判**
（永不印 drift/reconcile；>1 distinct value 的組交 agent 讀了判、人裁）。延伸引擎既有
`coherence_contract`「只列不判」模式到值層。
"""

from __future__ import annotations

import argparse
import json
import re
import sys

from dspx.commands._shared import BootstrapError, bootstrap, load_model
from dspx.commands.query.show import _scope_leaves
from dspx.engine.glossary import load_glossary

NAME = "find"
HELP = ("locate a keyword/term across all faces (prose/concept/decisions/material/glossary/audit) — "
        "returns section + face + line/position + snippet so an agent jumps straight there; "
        "--numbers aggregates number+unit values by referent (present-only, for the agent to judge)")

_ALL_FACES = ("prose", "concept", "decisions", "material", "glossary", "audit")
# 值層呈現器：數字＋單位（放寬 V10 的封閉集，含常見中文量詞）。單位後不得緊接英文字母
# （#12：擋「5 steps」→「5 s」這類垃圾組）；長單位在前，避免 m 先吃掉 mm/ms。
_NUM_UNIT_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*"
    r"(km/h|kHz|MHz|kW|ms|Hz|mm|cm|km|kg|°C|s|m|g|V|A|W|%|次|毫秒|秒|公尺|公里|公分)"
    r"(?![A-Za-z])")


def _snippet(text: str, start: int, end: int, pad: int = 40) -> str:
    lo = max(0, start - pad)
    hi = min(len(text), end + pad)
    s = text[lo:hi].replace("\n", " ")
    return ("…" if lo > 0 else "") + s + ("…" if hi < len(text) else "")


def _match_positions(hay: str, needle: str, regex: bool):
    if regex:
        try:
            rx = re.compile(needle, re.IGNORECASE)
        except re.error as exc:
            raise ValueError(f"bad --regex: {exc}") from exc
        for m in rx.finditer(hay):
            yield m.start(), m.end()
    else:
        low = hay.lower()
        n = needle.lower()
        if not n:
            return
        i = low.find(n)
        while i != -1:
            yield i, i + len(needle)
            i = low.find(n, i + len(needle))


def _prose_section_at(spans, pos: int) -> str | None:
    for sp in spans:
        if sp.start <= pos < sp.end:
            return sp.section
    return None


def _search_prose(layout, articles, query, regex, hits, scope_sections=None):
    from dspx.engine.spans import (FENCE, HTML_COMMENT, INLINE_CODE, MARKER,
                                    classify_deliverable, mask_non_prose)
    for art in articles:
        path = layout.docs_latest(art)
        if not path.is_file():
            hits.append({"section": art, "face": "prose", "loc": "(not rendered)",
                         "snippet": f"run `docspec render {art}` first", "id": None})
            continue
        text = path.read_text(encoding="utf-8")
        masked = mask_non_prose(text, kinds={HTML_COMMENT, FENCE, INLINE_CODE, MARKER})
        spans = classify_deliverable(text)
        for start, end in _match_positions(masked, query, regex):
            sec = _prose_section_at(spans, start) or art
            if scope_sections is not None and sec not in scope_sections:
                continue   # #12：scope 限定時，別回報 scope 外同篇節的 prose 命中
            line = text.count("\n", 0, start) + 1
            hits.append({"section": sec, "face": "prose",
                         "loc": f"docs/{art}/_latest.md L{line} (snapshot)",
                         "snippet": _snippet(text, start, end), "id": None})


def _search_source(leaves, query, regex, faces, hits):
    for lf in leaves:
        if "concept" in faces and isinstance(lf.concept, dict):
            for key in ("title", "concept"):
                val = lf.concept.get(key)
                if isinstance(val, str):
                    for s, e in _match_positions(val, query, regex):
                        hits.append({"section": lf.section, "face": f"concept.{key}",
                                     "loc": f"concept.{key}", "snippet": _snippet(val, s, e),
                                     "id": lf.concept.get("id")})
        if "decisions" in faces:
            for i, d in enumerate(lf.decisions or []):
                for key in ("statement", "rationale"):
                    val = d.get(key)
                    if isinstance(val, str):
                        for s, e in _match_positions(val, query, regex):
                            hits.append({"section": lf.section, "face": f"decisions[{i}].{key}",
                                         "loc": f"decisions[{i}].{key}",
                                         "snippet": _snippet(val, s, e), "id": d.get("id")})
        if "material" in faces and isinstance(lf.material, str):
            for s, e in _match_positions(lf.material, query, regex):
                line = lf.material.count("\n", 0, s) + 1
                hits.append({"section": lf.section, "face": "material",
                             "loc": f"material L{line}", "snippet": _snippet(lf.material, s, e),
                             "id": None})


def _search_glossary(layout, query, regex, hits):
    for term in load_glossary(layout):
        parts = [str(term.get("canonical", ""))] + [str(a) for a in (term.get("aliases") or [])] \
            + [str(term.get("definition", ""))]
        blob = " ┃ ".join(parts)
        for s, e in _match_positions(blob, query, regex):
            hits.append({"section": "(glossary)", "face": "glossary", "loc": f"term {term.get('id')}",
                         "snippet": _snippet(blob, s, e), "id": term.get("id")})
            break


def _search_audit(layout, leaves, query, regex, hits):
    from dspx.reports.audit import all_findings
    for f in all_findings(layout, leaves):
        for key in ("finding", "suggestion"):
            val = f.get(key)
            if isinstance(val, str):
                for s, e in _match_positions(val, query, regex):
                    hits.append({"section": ", ".join(f.get("targets") or []) or f.get("_store", ""),
                                 "face": "audit", "loc": f"finding {f.get('id')}",
                                 "snippet": _snippet(val, s, e), "id": f.get("id")})


def _referent_of(text: str, pos: int, glossary_terms: list[tuple[str, str]], lf, sec: str) -> str:
    """值層呈現器的分組鍵（#3）：數字前 60 字內**最靠近**的 glossary 詞（canonical **或別名**、
    case-insensitive）→ 回其 canonical → concept.title → section。用 glossary 當鍵才能讓跨文件
    同一個量（標題不同、稱呼含別名）聚成一組、「>1 distinct value」旗標才亮得起來。"""
    window = text[max(0, pos - 60):pos].lower()
    best_canon, best_i = None, -1
    for name_lower, canonical in glossary_terms:
        i = window.rfind(name_lower)
        if i > best_i:
            best_canon, best_i = canonical, i
    if best_canon is not None:
        return best_canon
    if lf is not None and isinstance(lf.concept, dict):
        title = lf.concept.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
    return sec


def _run_numbers(layout, leaves, articles, as_json, scope_sections=None) -> int:
    """`find --numbers`：森林級聚合 number+unit → 依指涉分組攤出所有值＋出處。只攤不判。"""
    from dspx.engine.spans import (FENCE, HTML_COMMENT, INLINE_CODE, MARKER,
                                    classify_deliverable, mask_non_prose)
    glossary_terms: list[tuple[str, str]] = []          # (name_lower, canonical)；含 canonical＋別名
    for t in load_glossary(layout):
        canon = str(t.get("canonical", ""))
        if not canon:
            continue
        glossary_terms.append((canon.lower(), canon))
        for a in (t.get("aliases") or []):
            if str(a).strip():
                glossary_terms.append((str(a).lower(), canon))
    by_section = {lf.section: lf for lf in leaves}
    groups: dict[str, list[dict]] = {}
    for art in articles:
        path = layout.docs_latest(art)
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        masked = mask_non_prose(text, kinds={HTML_COMMENT, FENCE, INLINE_CODE, MARKER})
        spans = classify_deliverable(text)
        for m in _NUM_UNIT_RE.finditer(masked):
            value, unit = m.group(1), m.group(2)
            sec = _prose_section_at(spans, m.start()) or art
            if scope_sections is not None and sec not in scope_sections:
                continue   # #12：scope 限定時，別列 scope 外同篇節的數字（與 prose 搜同一過濾）
            ref = _referent_of(text, m.start(), glossary_terms, by_section.get(sec), sec)
            key = f"{ref} · {unit}"
            line = text.count("\n", 0, m.start()) + 1
            groups.setdefault(key, []).append(
                {"value": value, "unit": unit, "section": sec, "line": line,
                 "snippet": _snippet(text, m.start(), m.end(), 24)})
    # 只攤：>1 distinct value 的組排前面（agent 優先看這些），但不下任何判決字眼。
    ordered = sorted(groups.items(),
                     key=lambda kv: (-len({h["value"] for h in kv[1]}), kv[0]))
    if as_json:
        print(json.dumps({"groups": [{"referent": k, "values": v} for k, v in ordered]},
                         ensure_ascii=False, indent=2))
        return 0
    if not ordered:
        print("find --numbers: no number+unit tokens found in the rendered prose.")
        return 0
    print("find --numbers — number+unit values grouped by referent "
          "(present-only; a group with >1 distinct value is for you to judge, not a verdict):\n")
    for key, occ in ordered:
        distinct = sorted({h["value"] for h in occ})
        flag = "  ← multiple values" if len(distinct) > 1 else ""
        print(f"  {key}: {{{', '.join(distinct)}}}{flag}")
        for h in occ[:6]:
            print(f"      {h['value']}{h['unit']}  @ {h['section']} L{h['line']}  …{h['snippet']}…")
    return 0


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec find", description=HELP)
    parser.add_argument("query", nargs="?", default=None, help="keyword / regex to locate")
    parser.add_argument("scope", nargs="?", default=None, help="limit to a section/subtree/article")
    parser.add_argument("--in", dest="faces", default=None,
                        help="comma-separated faces to search (default: all): " + ",".join(_ALL_FACES))
    parser.add_argument("--regex", action="store_true", help="treat QUERY as a regular expression")
    parser.add_argument("--numbers", action="store_true",
                        help="value presenter: aggregate number+unit by referent (present-only)")
    parser.add_argument("--limit", type=int, default=200, help="max hits to print (default 200)")
    parser.add_argument("--json", action="store_true", dest="as_json", help="JSON output")
    args = parser.parse_args(argv)

    try:
        layout, _config = bootstrap()
        leaves = load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code

    if args.scope:
        scoped = _scope_leaves(leaves, args.scope)
        if scoped is None:
            sys.stderr.write(f"docspec find: scope \"{args.scope}\" matched no section\n")
            return 1
        leaves = scoped
    articles = []
    for lf in leaves:
        if lf.article and lf.article not in articles:
            articles.append(lf.article)
    scope_sections = {lf.section for lf in leaves} if args.scope else None

    if args.numbers:
        return _run_numbers(layout, leaves, articles, args.as_json, scope_sections)

    if not args.query:
        sys.stderr.write("docspec find: give a QUERY (or use --numbers)\n")
        return 2

    faces = set(_ALL_FACES) if not args.faces else {f.strip() for f in args.faces.split(",")}
    unknown = faces - set(_ALL_FACES)
    if unknown:   # #6：未知面名 fail-loud（別靜默給假「不存在」）
        sys.stderr.write(f"docspec find: unknown --in face(s) {sorted(unknown)}; "
                         f"valid: {', '.join(_ALL_FACES)}\n")
        return 2
    hits: list[dict] = []
    try:
        if "prose" in faces:
            _search_prose(layout, articles, args.query, args.regex, hits, scope_sections)
        _search_source(leaves, args.query, args.regex, faces, hits)
        if "glossary" in faces:
            _search_glossary(layout, args.query, args.regex, hits)
        if "audit" in faces:
            _search_audit(layout, leaves, args.query, args.regex, hits)
    except ValueError as exc:
        sys.stderr.write(f"docspec find: {exc}\n")
        return 2

    if args.as_json:
        print(json.dumps({"query": args.query, "hits": hits[:args.limit]},
                         ensure_ascii=False, indent=2))
        return 0
    if not hits:
        print(f"find: \"{args.query}\" — no hits.")
        return 0
    print(f"find: \"{args.query}\" — {len(hits)} hit(s)"
          + (f" (showing {args.limit})" if len(hits) > args.limit else "") + ":\n")
    for h in hits[:args.limit]:
        idtag = f"  [{h['id']}]" if h.get("id") else ""
        print(f"  § {h['section']}  ({h['face']}, {h['loc']}){idtag}")
        print(f"      …{h['snippet']}…")
    print("\n  → drill down: docspec show <id> / get <section> <category>")
    return 0
