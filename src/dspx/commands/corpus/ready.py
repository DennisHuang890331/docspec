"""docspec ready <section|article> — 畢業交易（一手包）。

檢兩件：①目的地 yaml 完整（run_file_check：必填非空/型別/enum）②develop.md 榨乾
（剝 heading＋HTML 註解＋空白後無實質殘留；fenced 內容算實質）。
雙綠 → 刪 develop.md（畢業的唯一持久動作，status 重算為 ready）；
任一紅 → 拒、列原因、develop.md 留著。agent 無「跳過 check 直接刪」「帶內容畢業」的縫。

批次模式：引數是單段名且命中已知 article（任一 leaf 的 article 或 develop-only 節首段）
→ 對該文章全部節逐一跑**同一個**畢業交易（每節獨立、失敗跳過不回滾、全過才 exit 0）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys

from dspx.check import run_file_check
from dspx.commands._shared import BootstrapError, bootstrap, load_engine_schema, load_model
from dspx.engine.layout import Layout
from dspx.engine.model import load_leaf
from dspx.engine.schema import Schema

NAME = "ready"
HELP = "graduation transaction: verify completeness + develop.md drained -> delete develop.md, section turns ready"

_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_HEADING_RE = re.compile(r"^#+(\s|$)")


def drain_remainder(text: str) -> str:
    """剝 HTML 註解＋ATX 標題行＋空白行後的實質殘留。
    fenced code 內容算實質（不剝）→ 有 keeper 沒分流就擋得到。"""
    t = _COMMENT_RE.sub("", text)
    kept: list[str] = []
    for line in t.splitlines():
        s = line.strip()
        if not s or _HEADING_RE.match(s):
            continue
        kept.append(s)
    return "\n".join(kept).strip()


def _graduate(layout: Layout, schema: Schema, section: str) -> tuple[bool, list[str], bool, str]:
    """單節畢業交易本體（single 與 batch 共用同一條 code path）。

    回傳 (ok, reasons, deleted, remainder)——remainder＝develop.md 未榨乾文字（乾淨＝""），
    single 模式在外面照舊印節錄；batch 模式只取第一個 reason。

    **backend 路由**：store 篇 leaf 由記錄餵、develop.md 住 work/（結晶前工作台），畢業＝刪 work/
    的 develop.md；散檔篇照舊（concept.yaml 存在性＋節夾內 develop.md）。
    """
    from dspx.engine import store as _store
    reasons: list[str] = []
    is_store = _store.article_has_store(layout, layout.article_of(section))

    if is_store:
        art = _store.cached_article(layout, layout.article_of(section))
        rec = art.record_by_path(section) if art is not None else None
        if rec is None or rec.kind != "leaf" or rec.concept is None:
            return False, ["not crystallized yet: no store record with a concept"], False, ""
        leaf = _store.leaf_from_record(layout, rec)
        develop_path = _store.work_develop(layout, section)
    else:
        section_dir = layout.section_dir(section)
        leaf = load_leaf(layout, section_dir)
        # ① 目的地存在（結晶過）。concept 無合法空形狀＝必備；decisions.yaml 缺席＝合法空
        # （該節無自有裁決），不再是拒絕理由（contract-slimming D2；空殼反模式已撤）。
        if not (section_dir / "concept.yaml").is_file():
            reasons.append("not crystallized yet: missing concept.yaml")
        develop_path = section_dir / "develop.md"

    # ② 完整性（per-section 欄位級）
    reasons.extend(run_file_check(leaf, schema))

    # ③ develop.md 榨乾
    remainder = ""
    if develop_path.is_file():
        remainder = drain_remainder(develop_path.read_text(encoding="utf-8"))
        if remainder:
            reasons.append(
                "develop.md still has unrouted substantive content -- route it into "
                "concept/decisions/material/history first, or delete the throwaway thinking")

    if reasons:
        return False, reasons, False, remainder

    # 雙綠 → 刪 develop.md（畢業＝這一個確定性動作；status 重算 ready）
    deleted = develop_path.is_file()
    if deleted:
        develop_path.unlink()
    return True, [], deleted, remainder


def _run_batch(layout: Layout, schema: Schema, article: str,
               targets: list[str], as_json: bool) -> int:
    """批次畢業：每節獨立交易（同 _graduate 路徑）、失敗跳過不回滾、全過才 exit 0。"""
    results: list[dict] = []
    all_ready = True
    for section in targets:
        ok, reasons, deleted, _remainder = _graduate(layout, schema, section)
        if ok:
            entry: dict = {"section": section, "ready": True, "developDeleted": deleted}
        else:
            entry = {"section": section, "ready": False, "reasons": reasons}
            all_ready = False
        results.append(entry)

    if as_json:
        print(json.dumps({"article": article, "sections": results, "allReady": all_ready},
                         ensure_ascii=False, indent=2))
        return 0 if all_ready else 1

    for entry in results:
        if entry["ready"]:
            tail = "graduated (develop.md deleted)" if entry["developDeleted"] \
                else "already ready (no develop.md)"
            print(f"  ✓ {entry['section']} — {tail}")
        else:
            print(f"  ✗ {entry['section']} — {entry['reasons'][0]}")
    n_ok = sum(1 for e in results if e["ready"])
    print(f"article \"{article}\": {n_ok}/{len(results)} section(s) ready"
          + ("" if all_ready else " (failing sections skipped; nothing rolled back)"))
    return 0 if all_ready else 1


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec ready", description=HELP)
    parser.add_argument("section",
                        help="leaf section path (relative to corpus/), or an article name "
                             "to batch-graduate every section of that article")
    parser.add_argument("--json", action="store_true", dest="as_json", help="output as JSON")
    args = parser.parse_args(argv)

    try:
        layout, config = bootstrap()
        schema = load_engine_schema(config)
    except BootstrapError as exc:
        return exc.exit_code

    section = args.section.strip("/")

    # 批次模式偵測：單段名＋命中已知 article（leaf 的 article 或 develop-only 節首段）。
    if "/" not in section:
        try:
            leaves = load_model(layout)
        except BootstrapError as exc:
            return exc.exit_code
        from dspx.commands.query.status import develop_only_sections
        dev_only = develop_only_sections(layout, {lf.section for lf in leaves})
        art_leaf_sections = sorted(lf.section for lf in leaves if lf.article == section)
        art_dev_only = sorted(s for s in dev_only if s.split("/", 1)[0] == section)
        if art_leaf_sections or art_dev_only:
            targets = sorted(set(art_leaf_sections) | set(art_dev_only))
            return _run_batch(layout, schema, section, targets, args.as_json)

    from dspx.engine import store as _store
    if _store.article_has_store(layout, layout.article_of(section)):
        art = _store.cached_article(layout, layout.article_of(section))
        if art is None or art.record_by_path(section) is None:
            sys.stderr.write(f"docspec: section \"{section}\" not found in store "
                             f"corpus/{layout.article_of(section)}.yaml\n")
            return 2
    else:
        section_dir = layout.section_dir(section)
        if not section_dir.is_dir():
            sys.stderr.write(f"docspec: section \"{section}\" not found: {section_dir}\n")
            return 2

    ok, reasons, deleted, remainder = _graduate(layout, schema, section)

    if not ok:
        if args.as_json:
            print(json.dumps({"section": section, "ready": False, "reasons": reasons},
                             ensure_ascii=False, indent=2))
        else:
            sys.stderr.write(f"docspec: section \"{section}\" cannot graduate yet:\n")
            for r in reasons:
                sys.stderr.write(f"  ✗ {r}\n")
            if remainder:
                sys.stderr.write("  -- develop.md remainder (excerpt) --\n  "
                                 + remainder[:200].replace("\n", "\n  ") + "\n")
        return 1

    if args.as_json:
        print(json.dumps({"section": section, "ready": True, "developDeleted": deleted},
                         ensure_ascii=False, indent=2))
    else:
        tail = " + deleted" if deleted else " (no develop.md)"
        print(f"✓ section \"{section}\" graduated: completeness green, develop.md drained{tail}, now ready.")
    return 0
