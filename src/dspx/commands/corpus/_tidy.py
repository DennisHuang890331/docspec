"""docspec store tidy — 確定性、冪等的 corpus 遷移指令（contract-slimming；★store-only）。

三個機械動作，依序執行（`--dry-run` 先看完整清單、零寫入）——全部對 `corpus/<article>.yaml`
store 記錄操作，不再碰散檔：
  1. **剝逐字重複 brief 欄**：與「最近提供該欄的祖先」strip 後 byte 等值的子欄 → 刪欄改繼承。
     判定原語＝`dspx.engine.lint.brief_dup_fields`（與 lint V19 單一權威，不另寫副本）；改寫過的
     特化（哪怕一字之差）永不觸發。article root 永不剝（hierarchy check 要求 root 信封完整）。
  2. **剝 title 阿拉伯式章號前綴**：concept／group 記錄的 title 以 `6.`／`6.1`／`6、` 等阿拉伯式
     編號起頭（判定＝lint `_TITLE_ARABIC_PREFIX_RE`，與 V20 同源）→ 剝除**完整**層級前綴
     （`6.1 概觀`→`概觀`）。附錄字母式（`A.`／`附錄 A`）v1 不動（D7）。整值只是編號的 title 不動。
  3. **記錄 path 改名為交付語言 title slug**（最後跑）：leaf／有 authored title 的 group，其路徑
     末段 ≠（剝章號後）title 的檔名安全 slug → **逐項呼叫 `docspec mv` 交易原語**（marker／
     audit／roadmap 同步重寫、自驗 check、失敗零半套）。article root 明確排除。同層 slug 撞名＝
     兩者都拒改、報告衝突。每做完一項即重載模型重算剩餘清單。

（舊的「刪空殼 decisions.yaml」動作已隨 store 化消滅：store canonical serializer 天然不落
`decisions: []` 空殼，無檔可刪。）

紅 check 政策：mv 以 check 自驗、要求起跑綠。check 紅時 tidy 照做動作 1–2（就地改 store），
**整批改名跳過**並列出本會執行的清單，提示先修 check 再重跑。

實跑有變更後收尾印「逐篇 `docspec render <article> --rebaseline`」提示（own 軸輸入變了；
rebaseline 吸收、散文保留）——tidy 自己**永不** render、永不寫帳本。冪等：跑第二次＝零動作。
"""

from __future__ import annotations

import argparse
import re
import sys

from dspx.commands.corpus import mv as mv_cmd
from dspx.commands._shared import BootstrapError, bootstrap, load_engine_schema, load_model
from dspx.commands.corpus.put import _ILLEGAL_CHARS, _segment_error
from dspx.engine.lint import _TITLE_ARABIC_PREFIX_RE, brief_dup_fields

NAME = "tidy"
HELP = ("deterministic, idempotent corpus migration (store-native): strip verbatim-duplicate "
        "brief fields, strip arabic outline-numbering prefixes from titles, and rename leaf/group "
        "record paths to delivery-language title slugs (via the mv transaction)")

# 剝除用：**完整**層級阿拉伯前綴（`6.` `6.1` `6.1.2` `6、` `６．１` 含尾隨編號標點與空白）。
_ARABIC_STRIP_RE = re.compile(r"^\s*[0-9０-９]+(?:[.．][0-9０-９]+)*[.、．。]?\s*")

_SLUG_MAX_LEN = 80


def _strip_title(title: object) -> tuple[str | None, str | None]:
    """(剝乾淨的新 title, skip 原因)。不觸發＝(None, None)；只剩空＝(None, 原因)。"""
    if not isinstance(title, str) or not _TITLE_ARABIC_PREFIX_RE.match(title):
        return None, None
    stripped = _ARABIC_STRIP_RE.sub("", title, count=1).strip()
    if not stripped:
        return None, "title is only an outline number (stripping would leave it empty)"
    return stripped, None


# ── 動作 3：title → 檔名安全 slug（複用 new 的路徑段防呆做最終驗證）─────────

def _slugify(title: str) -> tuple[str | None, str | None]:
    """title →（slug, None）或（None, 拒絕原因）。剝 `/` 與 path 非法字元/控制字元、
    收斂空白、去頭尾點空白、長度上限；最終段交 `_segment_error`（保留名等）把關。"""
    s = "".join(c for c in title if c != "/" and c not in _ILLEGAL_CHARS and ord(c) >= 32)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > _SLUG_MAX_LEN:
        s = s[:_SLUG_MAX_LEN]
    s = s.rstrip(" .")
    if not s:
        return None, "nothing left after removing path-illegal characters"
    reason = _segment_error(s)
    if reason:
        return None, reason
    return s, None


def _group_records(layout) -> list[tuple[str, str, dict]]:
    """全 store 篇的 group 記錄：(article, section, meta dict)。★store-only：由記錄枚舉。"""
    from dspx.engine import store as _store
    out: list[tuple[str, str, dict]] = []
    for art in _store.store_articles(layout):
        art_obj = _store.cached_article(layout, art)
        for rec in (art_obj.group_records() if art_obj is not None else []):
            out.append((art, rec.path, dict(rec.group or {})))
    return out


def _cand_from_title(section: str, title: object,
                     out: list[tuple[str, str]], skips: list[tuple[str, str]]) -> None:
    if not isinstance(title, str) or not title.strip():
        return                             # 無 authored title＝無改名依據
    stripped, skip_reason = _strip_title(title)
    if skip_reason:
        skips.append((section, f"title {title!r} is only an outline number; no rename basis"))
        return
    base = stripped if stripped is not None else title
    slug, reason = _slugify(base)
    if slug is None:
        skips.append((section,
                      f"cannot derive a safe folder name from title {title!r}: {reason}"))
        return
    parent, _, cur = section.rpartition("/")
    if slug == cur:
        return
    out.append((section, f"{parent}/{slug}"))


def _compute_renames(layout) -> tuple[list[tuple[str, str]],
                                      list[tuple[list[str], str, str]],
                                      list[tuple[str, str]]]:
    """從現行 store 狀態算改名清單：(valid, conflicts, skips)。
    valid=(old, new)；conflicts=([olds], new, 原因)；skips=(section, 原因)。
    article root（section 無 `/`）一律排除。slug 以「剝章號後的 title」為基準。"""
    from dspx.engine.model import load_project
    leaves = load_project(layout)
    raw: list[tuple[str, str]] = []
    skips: list[tuple[str, str]] = []

    for leaf in leaves:
        if "/" not in leaf.section:
            continue                       # article root 排除（v1 mv 範圍）
        _cand_from_title(leaf.section, (leaf.concept or {}).get("title"), raw, skips)

    leaf_sections = {leaf.section for leaf in leaves}
    for _art, section, meta in _group_records(layout):
        if section in leaf_sections:
            continue                       # leaf 的 title 以 concept 為準
        if "/" not in section:
            continue                       # article root group 排除
        _cand_from_title(section, meta.get("title"), raw, skips)

    by_target: dict[str, list[str]] = {}
    for old, new in raw:
        by_target.setdefault(new, []).append(old)

    valid: list[tuple[str, str]] = []
    conflicts: list[tuple[list[str], str, str]] = []
    existing = leaf_sections | {s for _a, s, _m in _group_records(layout)}
    for new, olds in sorted(by_target.items()):
        if len(olds) > 1:                  # 同層撞名：兩者都拒、交人改 title
            conflicts.append((sorted(olds), new,
                              "multiple sections slug to the same folder name"))
            continue
        old = olds[0]
        if new in existing:
            conflicts.append(([old], new, "target section already exists"))
            continue
        valid.append((old, new))
    valid.sort()
    return valid, conflicts, skips


# ── store 就地改寫（brief 剝欄 / title 剝前綴）：批次每篇一讀一寫 ──────────────

def _apply_inplace_edits(layout, leaves, dry: bool, tag: str) -> tuple[int, set[str]]:
    """動作 1（brief 剝欄）＋動作 2（title 剝前綴）：對 store 記錄就地改寫。
    每篇 Article 只 load 一次、改完 save 一次（Drive 檔案系統一讀一寫紀律）。回 (actions, articles)。"""
    from dspx.engine import store as _store
    from dspx.engine.model import _concept_by_id

    actions = 0
    touched_articles: set[str] = set()

    # 每篇載入可變 Article（非 cached，避免共享快取被改）
    arts: dict[str, object] = {}
    for art in _store.store_articles(layout):
        arts[art] = _store.load_article(_store.store_path(layout, art), verify=False)
    dirty: set[str] = set()

    by_section = {lf.section: lf for lf in leaves}
    concept_by_id = _concept_by_id(by_section)

    # 動作 1：剝逐字重複 brief 欄
    for leaf in leaves:
        if "/" not in leaf.section:
            continue                       # article root 信封永不剝
        fields = brief_dup_fields(leaf, by_section, concept_by_id)
        if not fields:
            continue
        for f in fields:
            print(f"{tag}: strip verbatim-duplicate brief field: {leaf.section}/concept.yaml "
                  f"brief.{f} (byte-identical to the nearest ancestor supplying it; "
                  "deleting = inherit)")
        actions += len(fields)
        touched_articles.add(leaf.article)
        if not dry:
            rec = arts[leaf.article].record_by_path(leaf.section)
            if rec is not None and isinstance(rec.concept, dict):
                brief = rec.concept.get("brief")
                if isinstance(brief, dict):
                    for f in fields:
                        brief.pop(f, None)
                    if not brief:
                        rec.concept.pop("brief", None)
                    dirty.add(leaf.article)

    # 動作 2：剝 title 阿拉伯式章號前綴（concept 記錄）
    for leaf in leaves:
        title = (leaf.concept or {}).get("title")
        new_title, skip = _strip_title(title)
        if skip:
            print(f"{tag}: skip title strip: {leaf.section}/concept.yaml title {title!r} — {skip}")
            continue
        if new_title is None:
            continue
        print(f'{tag}: strip numbering prefix: {leaf.section}/concept.yaml title '
              f'"{title}" -> "{new_title}"')
        actions += 1
        touched_articles.add(leaf.article)
        if not dry:
            rec = arts[leaf.article].record_by_path(leaf.section)
            if rec is not None and isinstance(rec.concept, dict):
                rec.concept["title"] = new_title
                dirty.add(leaf.article)

    # 動作 2：剝 title 阿拉伯式章號前綴（group 記錄）
    for art, section, meta in _group_records(layout):
        title = meta.get("title")
        new_title, skip = _strip_title(title)
        if skip:
            print(f"{tag}: skip title strip: {section}/group.yaml title {title!r} — {skip}")
            continue
        if new_title is None:
            continue
        print(f'{tag}: strip numbering prefix: {section}/group.yaml title '
              f'"{title}" -> "{new_title}"')
        actions += 1
        touched_articles.add(art)
        if not dry:
            rec = arts[art].record_by_path(section)
            if rec is not None and rec.kind == "group" and isinstance(rec.group, dict):
                rec.group["title"] = new_title
                dirty.add(art)

    # 每篇 save 一次
    if not dry:
        from dspx.engine.schema import load_schema
        sch = load_schema()
        for art in sorted(dirty):
            _store.save_article(layout, arts[art], sch)

    return actions, touched_articles


# ── 主流程 ──────────────────────────────────────────────────────────────────

def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec store tidy", description=HELP)
    parser.add_argument(
        "--dry-run", action="store_true", dest="dry_run",
        help="print the complete action list (field strips / prefix strips / renames, "
             "plus conflicts and skips) without touching any store file")
    args = parser.parse_args(argv)

    try:
        layout, config = bootstrap()
        schema = load_engine_schema(config)
        leaves = load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code

    dry = args.dry_run
    tag = "tidy --dry-run" if dry else "tidy"
    hard_fail = False

    # ── 1–2. brief 剝欄 ＋ title 剝前綴（store 就地改寫；批次每篇一讀一寫）──
    actions, articles = _apply_inplace_edits(layout, leaves, dry, tag)

    # ── 3. 記錄 path 改名（最後跑；逐項呼叫 mv 交易原語，做一項重算一次）──────
    conflicts: list[tuple[list[str], str, str]] = []
    skips: list[tuple[str, str]] = []
    if dry:
        valid, conflicts, skips = _compute_renames(layout)
        for old, new in valid:
            print(f"{tag}: rename: {old} -> {new} (via `docspec mv`; markers/audit/roadmap "
                  "rewritten in the same transaction)")
        actions += len(valid)
        articles.update(old.split("/", 1)[0] for old, _ in valid)
    else:
        failed: set[tuple[str, str]] = set()
        valid, conflicts, skips = _compute_renames(layout)
        valid = [c for c in valid if c not in failed]
        if valid:
            pre = mv_cmd._check_result(layout, schema)
            if not pre.ok:
                print(f"{tag}: SKIPPED all record renames — `docspec check` is not green, and "
                      "renames run through the mv transaction which self-verifies with check. "
                      "Fix the check errors, then re-run `docspec store tidy`. Would have renamed:")
                for old, new in valid:
                    print(f"{tag}:   {old} -> {new}")
                valid = []
        for _ in range(200):               # 防禦性上限（確定性 slug 必收斂）
            if not valid:
                break
            old, new = valid[0]
            print(f"{tag}: rename: {old} -> {new}")
            rc = mv_cmd._run_section_mode(layout, schema, old, new)
            if rc == 0:
                actions += 1
                articles.add(old.split("/", 1)[0])
            else:
                sys.stderr.write(f"docspec: tidy — rename {old} -> {new} failed (mv aborted "
                                 "with no partial effect); continuing with the rest.\n")
                failed.add((old, new))
                hard_fail = True
            valid, conflicts, skips = _compute_renames(layout)
            valid = [c for c in valid if c not in failed]

    for olds, new, reason in conflicts:
        print(f"{tag}: rename conflict (kept original): {', '.join(olds)} -> {new} — {reason}; "
              "fix the title(s), then re-run `docspec store tidy`")
    for section, reason in skips:
        print(f"{tag}: rename skipped: {section} — {reason}")

    # ── 收尾 ──────────────────────────────────────────────────────────────
    if actions == 0:
        print(f"{tag}: nothing to do — corpus already conforms (0 actions).")
    elif dry:
        print(f"{tag}: {actions} action(s) would be applied (nothing written).")
    else:
        print(f"{tag}: {actions} action(s) applied.")
        for art in sorted(articles):
            print(f"  reminder: run `docspec render {art} --rebaseline` — the own-axis input "
                  "of its sections changed; rebaseline absorbs it (prose preserved). "
                  "tidy never renders or writes ledgers itself.")
    return 1 if hard_fail else 0
