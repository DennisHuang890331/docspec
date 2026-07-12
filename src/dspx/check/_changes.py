"""check：changes/ 容器結構驗證（task 1.4；結構查，語義不查）。

- change.yaml 欄位級（validate_change：id 安全/唯一、publish enum、target action/origin/kind enum、
  ref 非空/不重複）。
- id 唯一（同一 id 不得同時出現在 active / _archive / _abandoned）。
- target ref 死引用：section/revise/align/redraft/review/retire 的 ref 必須解析到現行正式 corpus
  的真實 section（concept.id 或 section 路徑）；create 的 ref＝尚未出生的路徑（不查存在）；
  file 的 ref＝project-root 相對檔路徑（不查存在——外部檔可在 apply 期才生）。
- change.yaml 被手改偵測交由「引擎獨占寫」慣例＋機器 header，這裡不做 byte net（v1）。
"""

from __future__ import annotations

from dspx.engine.model import Leaf


def _validate_changes(layout, leaves: list[Leaf], id_set: set[str],
                      concept_ids: set[str]) -> list[str]:
    from dspx.engine import change as chg

    errs: list[str] = []

    # ── id 唯一（跨狀態）：同 cid 不得出現在兩個狀態根 ──
    dup: dict[str, list[str]] = {}
    for state, root in (
            (chg.STATE_ACTIVE, chg.changes_root(layout)),
            (chg.STATE_ARCHIVED, chg.changes_root(layout) / chg.ARCHIVE_DIR),
            (chg.STATE_ABANDONED, chg.changes_root(layout) / chg.ABANDONED_DIR)):
        for cid in chg._iter_change_ids(root):
            dup.setdefault(cid, []).append(state)
    for cid, states in sorted(dup.items()):
        if len(states) > 1:
            errs.append(f"change[{cid}]: id appears in multiple states {states} "
                        "(a change id must live in exactly one of changes/ | _archive/ | _abandoned/)")

    section_paths = {leaf.section for leaf in leaves}

    # ── 逐個 active change 欄位級 + ref 死引用 ──
    for cid in chg.active_change_ids(layout):
        try:
            change = chg.load_change_at(chg.change_dir(layout, cid, chg.STATE_ACTIVE),
                                        chg.STATE_ACTIVE)
        except chg.ChangeError as exc:
            errs.append(f"change[{cid}]: {exc}")
            continue
        errs.extend(chg.validate_change(change))
        for t in change.targets:
            if t.kind in ("create", "file", "term"):
                continue   # create 路徑/外部檔/術語不查存在（apply 期才生/引擎視野外）
            if (t.ref not in id_set and t.ref not in section_paths
                    and t.ref not in concept_ids):
                errs.append(f"change[{cid}] target[{t.ref}]: ref points to nonexistent section "
                            f"id/path \"{t.ref}\" (use --action create for a new section, or "
                            "--kind file for an external file)")
    return errs
