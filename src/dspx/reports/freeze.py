"""freeze：凍結區（archive/）完整性。

設計（使用者拍板）：
  - 規則＝**資料夾級**：任何 `archive/` 資料夾內的檔案＝已發行凍結歷史，**禁改**。
  - 引擎**不上鎖**（OS 唯讀在 Google Drive 失效過）→ 改用**內容 hash 事後抓包**：
    publish 寫快照時把 hash 記進 `docspec/.freeze.yaml`；lint（V11）/ publish 閘重算比對，
    被竄改/刪除/未登記 → 報錯。純看內容、與同步工具無關（Drive/OneDrive/本機皆有效）。
  - 三層防護：① skill 規則（告訴 agent 別改）② 本模組 hash 抓包（引擎保證、跨工具）
    ③ PreToolUse hook（動手前就擋；見 dspx.commands._internal.hook）。
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


class LegacyCollisionError(Exception):
    """register-legacy 碰撞：任一相對路徑已在 frozen/legacy 任一表上（防洗白，整批拒絕）。"""

    def __init__(self, collisions: list[str]):
        super().__init__("already registered: " + ", ".join(collisions))
        self.collisions = collisions


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
    """凍結 hash（v2）：換行正規化（`\\r\\n`→`\\n`）後 sha256。

    換行符是 git autocrlf／checkout／同步工具的產物、非內容——同一份凍結快照在 LF worktree
    檢出不得被報竄改、鎖死 publish。「只改換行符」自此不構成竄改（接受此縮小：語義內容位元不變）。"""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _hash_legacy_algo(path: Path) -> str:
    """舊算法（v2 前）＝raw bytes 不正規化。只供 verify 的自動遷移 fallback：mismatch 時以
    舊算法重比、命中＝內容與登記時位元一致、僅算法升級 → 改寫 manifest（零洗白窗口）。"""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest_path(home: Path) -> Path:
    return home / MANIFEST_NAME


def _load_raw(home: Path) -> dict:
    """讀整份 manifest（頂層 dict）；壞 YAML → FreezeError（cli 包成友善一行）。"""
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
    return data if isinstance(data, dict) else {}


def _table(data: dict, key: str) -> dict[str, str]:
    t = data.get(key)
    return t if isinstance(t, dict) else {}


def load_manifest(home: Path) -> dict[str, str]:
    """`frozen:` 表（publish 鑄造的快照登記）。"""
    return _table(_load_raw(home), "frozen")


def load_legacy(home: Path) -> dict[str, str]:
    """`legacy:` 表（register-legacy 遷入的 pre-docspec 歷版）；缺鍵＝空表（舊 manifest 相容）。"""
    return _table(_load_raw(home), "legacy")


def _write_manifest(home: Path, frozen: dict[str, str], legacy: dict[str, str]) -> None:
    """兩表一次寫回；legacy 空表不落鍵（與現行單表 manifest 位元相容）。"""
    data: dict = {"frozen": frozen}
    if legacy:
        data["legacy"] = legacy
    _manifest_path(home).write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=True),
        encoding="utf-8", newline="\n",
    )


def record(home: Path, project_root: Path, snapshot: Path) -> None:
    """publish 產出快照後登記其 hash（key＝相對 project_root 的 posix 路徑）。"""
    raw = _load_raw(home)
    frozen = _table(raw, "frozen")
    key = snapshot.resolve().relative_to(project_root.resolve()).as_posix()
    frozen[key] = _hash(snapshot)
    _write_manifest(home, frozen, _table(raw, "legacy"))


def record_legacy(home: Path, project_root: Path, files: list[Path]) -> list[str]:
    """pre-docspec 歷版整批登記進 `legacy:` 表（key 規則同 frozen：相對 project_root 的 posix 路徑）。

    防洗白：任一 rel 已在 frozen **或** legacy 任一表 → LegacyCollisionError、零寫入
    （允許重登記＝「竄改後 re-register 洗白 hash」一條指令繞過整個 hash net）。
    批次單寫：整批算完 hash 才一次寫回 manifest（非逐檔全檔重寫；Drive 同步環境的 I/O／衝突面）。
    回傳已登記的 rel 清單（排序）。"""
    raw = _load_raw(home)
    frozen, legacy = _table(raw, "frozen"), _table(raw, "legacy")
    root = project_root.resolve()
    entries: dict[str, str] = {}
    for f in files:
        rel = f.resolve().relative_to(root).as_posix()
        entries[rel] = _hash(f)
    collisions = sorted(r for r in entries if r in frozen or r in legacy)
    if collisions:
        raise LegacyCollisionError(collisions)
    legacy.update(entries)
    _write_manifest(home, frozen, legacy)
    return sorted(entries)


def verify(home: Path, project_root: Path, docs_dir: Path) -> list[tuple[str, str]]:
    """抽查凍結區完整性。回傳 (相對路徑, 問題) 清單；空＝全部完好。

    舊 manifest 自動遷移（fingerprint v2 D6）：條目為舊算法（未正規化）hash 時，新算法必
    mismatch——先以舊算法重比一次，命中＝檔案內容從未變、只是算法升級 → 自動把該條目改寫成
    新算法 hash＋stderr 一行提示（非靜默）；不命中＝真竄改，照報。只有「可證明與舊記錄位元
    一致」的檔案會被改寫＝零洗白窗口；不另立 rehash 指令（遷移在 mismatch 首次被看見處——
    lint V11／publish 閘——自動完成、一次性）。"""
    import sys
    raw = _load_raw(home)
    frozen, legacy = _table(raw, "frozen"), _table(raw, "legacy")
    root = project_root.resolve()
    problems: list[tuple[str, str]] = []
    migrated: list[str] = []
    # 1) 兩表逐筆：被刪 or hash 不符（legacy 訊息分流＝遷入歷版，稽核時出處可辨）
    for table, deleted, tampered in (
            (frozen, "was deleted", "content was tampered with"),
            (legacy, "legacy history was deleted", "legacy history was tampered with")):
        for rel, want in table.items():
            f = root / rel
            if not f.is_file():
                problems.append((rel, deleted))
            elif _hash(f) != want:
                if _hash_legacy_algo(f) == want:
                    # 舊算法命中＝內容位元未變、僅算法升級 → 遷移該條目（一次性）
                    table[rel] = _hash(f)
                    migrated.append(rel)
                else:
                    problems.append((rel, tampered))
    if migrated:
        _write_manifest(home, frozen, legacy)
        for rel in sorted(migrated):
            sys.stderr.write(
                f"docspec: freeze manifest entry for {rel} migrated to the newline-normalized "
                "hash algorithm (content verified byte-identical under the old algorithm).\n")
    # 2) 磁碟上 archive/ 內、卻沒登記的檔（手動塞進凍結區）＝兩表聯集都查無；同步垃圾
    #    （desktop.ini 類）白名單排除——它們由同步工具自動生成、非人為放置，不該鎖發布。
    if docs_dir.is_dir():
        for f in docs_dir.rglob("*"):
            if f.is_file() and is_frozen_path(f) and not is_sync_junk(f.name):
                rel = f.resolve().relative_to(root).as_posix()
                if rel not in frozen and rel not in legacy:
                    problems.append((rel, "not registered (not produced by publish)"))
    return problems
