"""freeze：凍結區（archive/）完整性。

設計（使用者拍板）：
  - 規則＝**資料夾級**：任何 `archive/` 資料夾內的檔案＝已發行凍結歷史，**禁改**。
  - 引擎**不上鎖**（OS 唯讀在 Google Drive 失效過）→ 改用**內容 hash 事後抓包**：
    publish 寫快照時把 hash 記進 `docspec/.freeze.yaml`；lint（V11）/ publish 閘重算比對，
    被竄改/刪除/未登記 → 報錯。純看內容、與同步工具無關（Drive/OneDrive/本機皆有效）。
  - 三層防護：① skill 規則（告訴 agent 別改）② 本模組 hash 抓包（引擎保證、跨工具）
    ③ PreToolUse hook（動手前就擋；見 dspx.commands.hook）。
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

MANIFEST_NAME = ".freeze.yaml"

# 凍結區驗證的同步/系統垃圾白名單：同步工具/OS 自動生成、清了會長回來、非人為放置——
# 不觸發「not registered」ERROR（曾實測 desktop.ini 布滿真專案、第一次 publish 後必然全紅）。
# 真正的未登記內容檔（如 .md）行為不變。
_SYNC_JUNK_NAMES = frozenset({"desktop.ini", "thumbs.db", ".ds_store"})


class FreezeError(Exception):
    """freeze manifest 無法解析（壞 YAML）。"""


def is_sync_junk(name: str) -> bool:
    """同步/系統垃圾檔名（大小寫不敏感）：desktop.ini/Thumbs.db/.DS_Store/~$*（Office 鎖檔）/
    *.tmp.drive*（Drive 暫存）。"""
    low = name.lower()
    return (low in _SYNC_JUNK_NAMES
            or low.startswith("~$")
            or ".tmp.drive" in low)


def is_frozen_path(path: str | Path) -> bool:
    """路徑落在某個 `archive/` 資料夾內＝凍結（資料夾級規則）。"""
    return "archive" in Path(path).parts


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest_path(home: Path) -> Path:
    return home / MANIFEST_NAME


def load_manifest(home: Path) -> dict[str, str]:
    p = _manifest_path(home)
    if not p.is_file():
        return {}
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        # 壞檔（Drive 衝突截斷）→ domain error 帶路徑（cli 包成友善一行），不裸 traceback。
        mark = getattr(exc, "problem_mark", None)
        position = f" (line {mark.line + 1})" if mark is not None else ""
        raise FreezeError(f"YAML parse failed: {p}{position}") from exc
    frozen = data.get("frozen") if isinstance(data, dict) else None
    return frozen if isinstance(frozen, dict) else {}


def record(home: Path, project_root: Path, snapshot: Path) -> None:
    """publish 產出快照後登記其 hash（key＝相對 project_root 的 posix 路徑）。"""
    frozen = load_manifest(home)
    key = snapshot.resolve().relative_to(project_root.resolve()).as_posix()
    frozen[key] = _hash(snapshot)
    _manifest_path(home).write_text(
        yaml.safe_dump({"frozen": frozen}, allow_unicode=True, sort_keys=True),
        encoding="utf-8",
    )


def verify(home: Path, project_root: Path, docs_dir: Path) -> list[tuple[str, str]]:
    """抽查凍結區完整性。回傳 (相對路徑, 問題) 清單；空＝全部完好。"""
    frozen = load_manifest(home)
    root = project_root.resolve()
    problems: list[tuple[str, str]] = []
    # 1) manifest 每一筆：被刪 or hash 不符
    for rel, want in frozen.items():
        f = root / rel
        if not f.is_file():
            problems.append((rel, "was deleted"))
        elif _hash(f) != want:
            problems.append((rel, "content was tampered with"))
    # 2) 磁碟上 archive/ 內、卻沒登記的檔（手動塞進凍結區）；同步垃圾（desktop.ini 類）
    #    白名單排除——它們由同步工具自動生成、非人為放置，不該鎖發布。
    if docs_dir.is_dir():
        for f in docs_dir.rglob("*"):
            if f.is_file() and is_frozen_path(f) and not is_sync_junk(f.name):
                rel = f.resolve().relative_to(root).as_posix()
                if rel not in frozen:
                    problems.append((rel, "not registered (not produced by publish)"))
    return problems
