"""docspec tidy — 確定性、冪等的 corpus 遷移指令（contract-slimming）。

四個機械動作，依序執行（`--dry-run` 先看完整清單、零寫入）：
  1. **刪空殼 decisions.yaml**：`entries: []`／空 mapping／空檔＝契約層非法空殼 → 刪檔逐一列出。
     壞檔（頂層 list、誤名 key）不是空殼——loader 本就 fail-loud，tidy 不碰。
  2. **剝逐字重複 brief 欄**：與「最近提供該欄的祖先」strip 後 byte 等值的子欄 → 刪欄改繼承。
     判定原語＝`dspx.engine.lint.brief_dup_fields`（與 lint V19 單一權威，不另寫副本）；改寫過的
     特化（哪怕一字之差）永不觸發。article root 永不剝（hierarchy check 要求 root 信封完整；
     root 無祖先、本就不會命中——雙保險）。
  3. **剝 title 阿拉伯式章號前綴**：concept.yaml／group.yaml 的 title 以 `6.`／`6.1`／`6、`
     等阿拉伯式編號起頭（判定＝lint `_TITLE_ARABIC_PREFIX_RE`，與 V20 同源）→ 剝除**完整**
     層級前綴（`6.1 概觀`→`概觀`，不是 `1 概觀`）。附錄字母式（`A.`／`附錄 A`）v1 不動（D7：
     等 agent 補 `numbering: appendix`）。整值只是編號的 title 不動（剝了變空）、報告跳過。
  4. **資料夾改名為交付語言 title slug**（最後跑）：leaf／有 authored title 的 group，其資料夾
     名 ≠（剝章號後）title 的檔名安全 slug → **逐項呼叫 `docspec mv` 交易原語**（marker／
     audit／roadmap 同步重寫、自驗 check、失敗零半套——tidy 不土製改名邏輯）。article root
     明確排除（交付檔名/凍結/journal 綁 article 名）。同層 slug 撞名＝兩者都拒改、報告衝突。
     每做完一項即重載模型重算剩餘清單（父層改名不會失效子路徑）。

紅 check 政策：mv 以 check 自驗、要求起跑綠。check 紅時 tidy 照做動作 1–3（不經 mv），
**整批改名跳過**並列出本會執行的清單，提示先修 check 再重跑。

實跑有變更後收尾印「逐篇 `docspec render <article> --rebaseline`」提示（own 軸輸入檔集合變了；
rebaseline 吸收、散文保留）——tidy 自己**永不** render、永不寫帳本。冪等：跑第二次＝零動作。
"""

from __future__ import annotations

import argparse
import re
import sys

import yaml

from dspx.commands.corpus import mv as mv_cmd
from dspx.commands._shared import BootstrapError, bootstrap, load_engine_schema, load_model
from dspx.commands.corpus.new import _ILLEGAL_CHARS, _segment_error
from dspx.engine.lint import _TITLE_ARABIC_PREFIX_RE, brief_dup_fields

NAME = "tidy"
HELP = ("deterministic, idempotent corpus migration: delete empty-shell decisions.yaml, strip "
        "verbatim-duplicate brief fields, strip arabic outline-numbering prefixes from titles, "
        "and rename leaf/group folders to delivery-language title slugs (via the mv transaction)")

# 剝除用：**完整**層級阿拉伯前綴（`6.` `6.1` `6.1.2` `6、` `６．１` 含尾隨編號標點與空白）。
# 觸發與否由 lint 的 `_TITLE_ARABIC_PREFIX_RE`（單一權威）決定；此 regex 只負責剝乾淨——
# 只用第一段 `^[0-9]+[.、．。]` 剝 `6.1 概觀` 會剩 `1 概觀`（錯），故 dotted 段一併吃掉。
_ARABIC_STRIP_RE = re.compile(r"^\s*[0-9０-９]+(?:[.．][0-9０-９]+)*[.、．。]?\s*")

_SLUG_MAX_LEN = 80

_HISTORY_GUIDANCE = (
    "live-tree history.yaml is no longer part of the contract; dead decisions fold back into "
    "decisions.yaml marked status: superseded — not moved automatically. Migrate the entries by "
    "hand (or re-crystallize), then delete the file.")


# ── 動作 1：空殼 decisions.yaml 判定 ────────────────────────────────────────

def _is_shell_decisions(path) -> bool:
    """空殼＝空/純空白檔、空 mapping、或只有 falsy `entries`（`entries: []`/`entries:`）。
    壞檔（parse 失敗、頂層非 mapping、有其他 key）不是空殼——留給 loader fail-loud。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    if not text.strip():
        return True
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return False
    if data is None:                       # 只有註解＝無資料＝空殼
        return True
    if isinstance(data, dict):
        if not data:
            return True
        if set(data.keys()) == {"entries"} and not data["entries"]:
            return True
    return False


# ── 動作 2/3：concept.yaml / group.yaml 改寫（保留其餘 key，不排序）─────────

def _rewrite_yaml(path, data: dict) -> None:
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                    encoding="utf-8", newline="\n")


def _strip_brief_fields(concept_path, fields: list[str]) -> None:
    data = yaml.safe_load(concept_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return
    brief = data.get("brief")
    if not isinstance(brief, dict):
        return
    changed = False
    for f in fields:
        if f in brief:
            del brief[f]
            changed = True
    if changed:
        if not brief:                      # brief 空了＝整塊省略（＝繼承；schema brief 可選）
            del data["brief"]
        _rewrite_yaml(concept_path, data)


def _set_title(path, new_title: str) -> None:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data["title"] = new_title
        _rewrite_yaml(path, data)


def _strip_title(title: object) -> tuple[str | None, str | None]:
    """(剝乾淨的新 title, skip 原因)。不觸發＝(None, None)；只剩空＝(None, 原因)。"""
    if not isinstance(title, str) or not _TITLE_ARABIC_PREFIX_RE.match(title):
        return None, None
    stripped = _ARABIC_STRIP_RE.sub("", title, count=1).strip()
    if not stripped:
        return None, "title is only an outline number (stripping would leave it empty)"
    return stripped, None


# ── 動作 4：title → 檔名安全 slug（複用 new 的路徑段防呆做最終驗證）─────────

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


def _group_files(layout) -> list[tuple[object, str, dict]]:
    """活樹 group.yaml 清單：(path, section, parsed dict)。壞檔略過（check ⑩ fail-loud 管）。"""
    out: list[tuple[object, str, dict]] = []
    if not layout.corpus_dir.is_dir():
        return out
    for gy in sorted(layout.corpus_dir.rglob("group.yaml")):
        if layout.is_archived_path(gy.parent):
            continue
        try:
            data = yaml.safe_load(gy.read_text(encoding="utf-8"))
        except (yaml.YAMLError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        out.append((gy, layout.section_id(gy.parent), data))
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
    """從現行磁碟狀態算改名清單：(valid, conflicts, skips)。
    valid=(old, new)；conflicts=([olds], new, 原因)；skips=(section, 原因)。
    article root（section 無 `/`）一律排除。slug 以「剝章號後的 title」為基準
    （dry-run 時動作 3 尚未落盤、實跑時已剝＝再剝是 no-op，兩態一致）。"""
    from dspx.engine.model import load_project
    leaves = load_project(layout)
    raw: list[tuple[str, str]] = []
    skips: list[tuple[str, str]] = []

    for leaf in leaves:
        if "/" not in leaf.section:
            continue                       # article root 排除（v1 mv 範圍）
        _cand_from_title(leaf.section, (leaf.concept or {}).get("title"), raw, skips)

    for gy, section, data in _group_files(layout):
        if (gy.parent / "concept.yaml").is_file():
            continue                       # leaf 的 title 以 concept.yaml 為準
        if "/" not in section:
            continue                       # article root group.yaml 排除
        _cand_from_title(section, data.get("title"), raw, skips)

    by_target: dict[str, list[str]] = {}
    for old, new in raw:
        by_target.setdefault(new, []).append(old)

    valid: list[tuple[str, str]] = []
    conflicts: list[tuple[list[str], str, str]] = []
    for new, olds in sorted(by_target.items()):
        if len(olds) > 1:                  # 同層撞名：兩者都拒、交人改 title
            conflicts.append((sorted(olds), new,
                              "multiple sections slug to the same folder name"))
            continue
        old = olds[0]
        dst = layout.section_dir(new)
        if dst.exists():
            src = layout.section_dir(old)
            same = False
            try:
                same = src.exists() and dst.samefile(src)
            except OSError:
                same = False
            if same:                       # 大小寫不敏感 FS：只差大小寫＝同資料夾，跳過
                skips.append((old, f'rename to "{new}" differs only by letter case from the '
                                   "current folder name; skipped"))
            else:
                conflicts.append(([old], new, "target folder already exists"))
            continue
        valid.append((old, new))
    valid.sort()
    return valid, conflicts, skips


# ── 主流程 ──────────────────────────────────────────────────────────────────

def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec tidy", description=HELP)
    parser.add_argument(
        "--dry-run", action="store_true", dest="dry_run",
        help="print the complete action list (deletes / field strips / prefix strips / renames, "
             "plus conflicts and skips) without touching any file")
    args = parser.parse_args(argv)

    try:
        layout, config = bootstrap()
        schema = load_engine_schema(config)
        leaves = load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code

    dry = args.dry_run
    tag = "tidy --dry-run" if dry else "tidy"
    actions = 0
    articles: set[str] = set()
    hard_fail = False

    # ── 1. 刪空殼 decisions.yaml ──────────────────────────────────────────
    for leaf in leaves:
        p = leaf.dir / "decisions.yaml"
        if p.is_file() and _is_shell_decisions(p):
            print(f"{tag}: delete empty-shell decisions.yaml: {leaf.section}/decisions.yaml")
            if not dry:
                p.unlink()
            actions += 1
            articles.add(leaf.article)

    # ── 2. 剝逐字重複 brief 欄（判定＝lint brief_dup_fields，單一權威）────
    from dspx.engine.model import _concept_by_id
    by_section = {lf.section: lf for lf in leaves}
    concept_by_id = _concept_by_id(by_section)
    for leaf in leaves:
        if "/" not in leaf.section:
            continue                       # article root 信封永不剝（hierarchy 要求 root 完整）
        fields = brief_dup_fields(leaf, by_section, concept_by_id)
        if not fields:
            continue
        for f in fields:
            print(f"{tag}: strip verbatim-duplicate brief field: {leaf.section}/concept.yaml "
                  f"brief.{f} (byte-identical to the nearest ancestor supplying it; "
                  "deleting = inherit)")
        if not dry:
            _strip_brief_fields(leaf.dir / "concept.yaml", fields)
        actions += len(fields)
        articles.add(leaf.article)

    # ── 3. 剝 title 阿拉伯式章號前綴（concept.yaml ＋ 活樹 group.yaml）────
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
        if not dry:
            _set_title(leaf.dir / "concept.yaml", new_title)
        actions += 1
        articles.add(leaf.article)

    for gy, section, data in _group_files(layout):
        title = data.get("title")
        new_title, skip = _strip_title(title)
        if skip:
            print(f"{tag}: skip title strip: {section}/group.yaml title {title!r} — {skip}")
            continue
        if new_title is None:
            continue
        print(f'{tag}: strip numbering prefix: {section}/group.yaml title '
              f'"{title}" -> "{new_title}"')
        if not dry:
            _set_title(gy, new_title)
        actions += 1
        articles.add(section.split("/", 1)[0])

    # ── 4. live 樹 history.yaml 偵測（只報告、不動檔、不計入動作）─────────
    for leaf in leaves:
        if (leaf.dir / "history.yaml").is_file():
            print(f"{tag}: NOTE {leaf.section}/history.yaml — {_HISTORY_GUIDANCE}")

    # ── 5. 資料夾改名（最後跑；逐項呼叫 mv 交易原語，做一項重算一次）──────
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
            # mv 以 check 自驗、要求起跑綠：紅 check ＝ 整批改名跳過（動作 1–3 已照做）。
            pre = mv_cmd._check_result(layout, schema)
            if not pre.ok:
                print(f"{tag}: SKIPPED all folder renames — `docspec check` is not green, and "
                      "renames run through the mv transaction which self-verifies with check. "
                      "Fix the check errors, then re-run `docspec tidy`. Would have renamed:")
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
            # 重載重算：父層改名後子路徑全變，剩餘清單以磁碟現況為準。
            valid, conflicts, skips = _compute_renames(layout)
            valid = [c for c in valid if c not in failed]

    for olds, new, reason in conflicts:
        print(f"{tag}: rename conflict (kept original): {', '.join(olds)} -> {new} — {reason}; "
              "fix the title(s), then re-run `docspec tidy`")
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
                  "set of its sections changed; rebaseline absorbs it (prose preserved). "
                  "tidy never renders or writes ledgers itself.")
    return 1 if hard_fail else 0
