"""check 衛生（WARN、非阻塞）：corpus 的同步衝突副本與死資料夾（corpus-fail-loud-batch D7）。

兩類都是「疑似」狀態（可能正在施工），WARN 提示人裁決、不當閘門：
  - 衝突副本：`* (N)` 檔/夾（Drive 衝突副本模式）與 `*.tmp.drive*` 暫存——引擎只讀固定
    檔名，副本內容不生效，人以為改了其實沒改。
  - 死資料夾：非 `_` 前綴、但不含 concept.yaml/group.yaml 且無有效後代——
    引擎全體對它隱形（status/list/check 均不列）。
"""

from __future__ import annotations

import re

# Drive 衝突副本檔名模式：`<stem> (N)` 或 `<stem> (N).<ext>`
_CONFLICT_COPY_RE = re.compile(r"^.* \(\d+\)(\.[^.]+)?$")
# 引擎的「活」標記檔：含任一＝該資料夾（或其祖先鏈）對引擎可見
_ALIVE_MARKERS = ("concept.yaml", "group.yaml")
# 慣例資料夾（非節點、不算死資料夾）：節的圖資產夾
_CONVENTION_DIRS = frozenset({"assets"})


def _hidden(rel_parts: tuple[str, ...]) -> bool:
    """路徑任一段 `_` 開頭＝引擎隱形區（_archive 等），衛生檢查跳過。"""
    return any(part.startswith("_") for part in rel_parts)


def _scan_hygiene(layout) -> list[str]:
    """回傳 WARN 字串清單（進 CheckResult.warnings，非阻塞）。"""
    warnings: list[str] = []
    corpus = layout.corpus_dir
    if not corpus.is_dir():
        return warnings

    entries = sorted(corpus.rglob("*"), key=lambda p: p.relative_to(corpus).as_posix())
    conflict_dirs: set = set()

    # ── 衝突副本（檔與資料夾）──────────────────────────────────
    for p in entries:
        rel = p.relative_to(corpus)
        if _hidden(rel.parts):
            continue
        name = p.name
        if _CONFLICT_COPY_RE.match(name) or ".tmp.drive" in name.lower():
            kind = "folder" if p.is_dir() else "file"
            warnings.append(
                f"corpus/{rel.as_posix()}: looks like a sync-conflict copy ({kind}) — "
                "the engine only reads fixed file names, so this copy's content has no "
                "effect; merge or delete it")
            if p.is_dir():
                conflict_dirs.add(p)

    # ── 死資料夾：無活標記、無有效後代 ─────────────────────────
    marker_dirs = {
        f.parent for marker in _ALIVE_MARKERS for f in corpus.rglob(marker)
        if not _hidden(f.parent.relative_to(corpus).parts)   # 隱形區的標記不算「有效後代」
    }

    def _alive(d) -> bool:
        return any(md == d or md.is_relative_to(d) for md in marker_dirs)

    dead: list = []
    for p in entries:
        if not p.is_dir():
            continue
        rel = p.relative_to(corpus)
        if _hidden(rel.parts) or p in conflict_dirs:
            continue
        if any(part in _CONVENTION_DIRS for part in rel.parts):
            continue
        if not _alive(p):
            dead.append(p)
    # 只報最頂層的死資料夾（父已死＝子必死，逐層報是噪音）
    for p in dead:
        if any(parent in dead for parent in p.parents):
            continue
        rel = p.relative_to(corpus)
        warnings.append(
            f"corpus/{rel.as_posix()}: dead folder — no concept.yaml/group.yaml "
            "here or below, so the engine cannot see it (status/list/check all skip it); "
            "add the missing file or clean it up")
    return warnings
