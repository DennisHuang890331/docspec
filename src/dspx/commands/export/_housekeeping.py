"""輸出清理（預設只留 latest）＋選輸入快照。"""

from __future__ import annotations

import sys
from pathlib import Path

from dspx.engine.layout import Layout, parse_semver


def _prune_old_pdfs(layout: Layout, article: str, keep: Path) -> list[Path]:
    """預設只留 latest：刪同篇其他已產 PDF（舊版號 + `_vlatest` 預覽），只留剛產出的 `keep`。

    scope 嚴格：只掃 docs/exports/ **頂層**、檔名前綴 `<article>_v`（`_v` 分隔符保證不誤傷
    `<article>-x` 等他篇）；非遞迴（不碰 journals/ 子夾）、不碰 archive/。回刪除清單。"""
    pruned: list[Path] = []
    exports = layout.docs_exports_dir
    if not exports.is_dir():
        return pruned
    keep = keep.resolve()
    for p in exports.glob(f"{article}_v*.pdf"):
        if not p.is_file():
            continue
        if p.resolve() == keep:
            continue
        try:
            p.unlink()
            pruned.append(p)
        except OSError:
            pass   # 刪不掉不致命（鎖定/權限）；export 本身已成功
    return pruned


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
