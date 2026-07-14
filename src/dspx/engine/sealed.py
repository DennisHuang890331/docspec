"""sealed keyed-list store — 一個頂層 keyed list（audit findings／roadmap entries）的引擎擁有
密封單檔，套用與 article store 同一套紀律：canonical 序列化 ＋ integrity 封條 ＋ 原子寫 ＋
hook 守門。audit / roadmap 共用（「沒道理兩個設計思路不同」）。

封條＝**schema/鍵序無關**的內容 payload（`format/kind/scope/revision/<list>`）之 json canonical
sha256（比照 store.py `_integrity_of` 的解耦原則）；list 順序保留（append-only log 語義），只
dict 鍵序正規化。`revision` 固定 1、save 冪等（round-trip 不動點）。缺席檔＝空 store（按需生成）。
壞封條／壞形狀＝fail-loud 指路 `store fsck`；無 integrity 頭的舊檔相容讀入不驗（讓 migrate/首 save 自然升級）。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from dspx.engine.store import _yaml_dump, atomic_write_store

SEALED_FORMAT_VERSION = 1


def integrity_of(kind: str, scope: str, revision: int, list_key: str, items: list) -> str:
    payload = {"format": SEALED_FORMAT_VERSION, "kind": kind, "scope": scope,
               "revision": revision, list_key: items}
    body = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def dump_sealed(*, kind: str, scope: str, revision: int, list_key: str, items: list) -> str:
    """密封檔文字（註解頭＋format/kind/scope/revision/integrity＋<list_key>）。冪等。"""
    seal = integrity_of(kind, scope, revision, list_key, items)
    header = (f"# docspec {kind} store — engine-owned; never edit by hand.\n"
              f"# An integrity seal guards the body; a hand-edit makes the next docspec command\n"
              f"# fail loud and point you at `docspec store fsck --accept`.\n")
    doc = {"format": SEALED_FORMAT_VERSION, "kind": kind, "scope": scope,
           "revision": revision, "integrity": seal, list_key: items}
    return header + _yaml_dump(doc)


def write_sealed(path: Path, *, kind: str, scope: str, revision: int,
                 list_key: str, items: list) -> None:
    """原子寫密封檔（tmp + os.replace，複用 store.atomic_write_store）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_store(path, dump_sealed(
        kind=kind, scope=scope, revision=revision, list_key=list_key, items=items))


def load_sealed(path: Path, *, list_key: str, error_cls, verify: bool = True):
    """回 (revision, items)；缺席→(1, [])。壞形狀／封條不符＝raise error_cls（fail-loud 指路 fsck）。
    向後相容：無 `integrity` 頭的舊檔視為 unsealed、照讀不驗（下次 save 自動密封升級）。"""
    if not path.is_file():
        return 1, []
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        pos = f" (line {mark.line + 1})" if mark is not None else ""
        raise error_cls(f"YAML parse failed: {path}{pos}") from exc
    raw = raw or {}
    # 誤名頂層 key fail-loud（有內容卻缺正確 key＝別靜默當空，比照四 loader 共用契約）。
    from dspx.engine.model import keyed_list
    items = keyed_list(raw, path, list_key, error=error_cls)
    if not isinstance(raw, dict):
        raise error_cls(f"malformed sealed store (top-level not a mapping): {path}")
    revision = raw.get("revision")
    revision = revision if isinstance(revision, int) and revision >= 1 else 1
    # 真舊 unsealed 檔（無 kind 也無 integrity）＝相容讀入不驗；一旦 `kind` 在場（是密封檔）就必驗
    # ——缺 integrity（被刪一行洗白）視同 mismatch，否則下次 save 靜默重封＝手改零留痕。
    if verify and (raw.get("kind") is not None or raw.get("integrity") is not None):
        expect = integrity_of(raw.get("kind"), raw.get("scope"), revision, list_key, items)
        if raw.get("integrity") != expect:
            raise error_cls(
                f"integrity seal mismatch: {path} — a hand-edit corrupted the store; "
                f"run `docspec store fsck --accept` to adopt the external change and re-seal.")
    return revision, items
