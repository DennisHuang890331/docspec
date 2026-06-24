"""glossary：專案術語權威（token 一致性的硬保證層）。

定位＝專案參考設定（像 writing-guide.md，編輯＋check 驗，非命令化）。
- realizes 給共享決策的正名字 → glossary＋lint 督促照用 → token 雙保險。
- lint 只做低誤判的「提醒」（Vg1 同物異名 / Vg2 縮寫裸奔，皆 WARN）；
  精確的同物異名「判定」要看上下文 → 交 audit（語義），不在 lint 硬擋。
照台中港 glossary.md 三桶實證：module(桶1自創縮寫→中文)/standard(桶2標準→編號保英)/protocol(桶3欄位→原樣)。
"""

from __future__ import annotations

from pathlib import Path

import yaml

from dspx.layout import Layout

BUCKETS = ("module", "standard", "protocol")


def glossary_path(layout: Layout) -> Path:
    return layout.planning_home / "glossary.yaml"


def load_glossary(layout: Layout) -> list[dict]:
    """載入 glossary.yaml 的 terms；缺席→[]。"""
    path = glossary_path(layout)
    if not path.is_file():
        return []
    from dspx.model import ModelError, keyed_list
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return keyed_list(raw, path, "terms", error=ModelError)  # 誤名頂層 key fail-loud


def validate_glossary(terms: list[dict]) -> list[str]:
    """check 用：每條 id 唯一、canonical 必填、bucket 合法。

    definition/english 是 optional 下鑽欄（`docspec show <id>` 才回）——不加硬 invariant。
    """
    errs: list[str] = []
    seen: set[str] = set()
    for t in terms:
        tid = t.get("id")
        if not tid:
            errs.append(f"glossary term missing id: {t!r}")
        elif tid in seen:
            errs.append(f"duplicate glossary id: {tid}")
        else:
            seen.add(str(tid))
        if not t.get("canonical"):
            errs.append(f"glossary term \"{tid}\" missing canonical (canonical name)")
        if t.get("bucket") not in BUCKETS:
            errs.append(f"glossary term \"{tid}\" bucket \"{t.get('bucket')}\" not in {BUCKETS}")
    return errs
