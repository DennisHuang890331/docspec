"""audit 子系統：紅隊查核發現的儲存/查詢/攻防 log。

設計（2026-06-16，網路趨勢＋使用者拍板；2026-06-17 redesign＝per-doc+forest）：
- audit 是審計記錄 → **全指令進出、append-only、寫時驗證**（不手改 audit.yaml）。
- 每條 finding 掛 append-only `log`（raised→responded→verified），= 攻防軌跡＋記憶。
- 非阻塞：audit 永不擋 publish（只有 check+lint 擋）。
- **儲存比照 roadmap（per-doc-root ＋ forest）**：
  - finding 觸及 1 文件 → 該文件 root 的 `corpus/<article>/audit.yaml`。
  - 觸及 ≥2 文件 → forest-level `<planning_home>/audit.yaml`。
  - 判準＝finding `targets` 裡的 **distinct 文件數**（確定性、引擎可強制）。
  - **按需生成**：沒 finding＝無檔；load 回空 store。
- finding 掛 `targets`（它觸及的 section-id/§anchor 清單，穩定 id、絕不用行號）；
  跨文件 finding 加可選 `sot-owner`（哪份文件/節是真相擁有者）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from dspx.engine.layout import Layout

STATUSES = ("open", "fixed", "rejected", "waived", "closed")
SEVERITIES = ("high", "med", "low")
# Optional NLI ruling for citation factchecks (D3). Recorded only for failures:
#   contradicted = a primary source refutes the claim; unsupported = no source backs it.
# An *entailed* (supported) claim raises no finding at all, so there is no "entailed"
# verdict to store — silence is the pass state (root-cause collapse: only flag problems).
VERDICTS = ("contradicted", "unsupported")
# 五核心攻擊面（config.audit.core）；掛載包（packs）另由 config 開
DEFAULT_FACES = ("logic", "completeness", "clarity", "discipline", "consistency")

AUDIT_FILE = "audit.yaml"
FOREST_STORE = "forest"


class AuditError(Exception):
    """audit 操作失敗（id 不存在、欄位非法、targets 無法路由等）。"""


def _yaml_position(exc: yaml.YAMLError) -> str:
    """YAML 解析錯誤 → ` (line N)` 定位字串（無 mark → 空字串）。"""
    mark = getattr(exc, "problem_mark", None)
    return f" (line {mark.line + 1})" if mark is not None else ""


@dataclass
class AuditStore:
    """一個 audit sibling 密封檔（findings 清單）；可為某 doc-root 或 forest。

    ★store-native：比照 article store 套封條紀律（engine-owned＋integrity 封條＋canonical＋
    原子寫＋hook 守門），走 `engine/sealed.py` 通用 helper。scope＝`store`（"doc:<a>" | "forest"）。"""

    path: Path
    findings: list[dict] = field(default_factory=list)
    store: str = ""        # "doc:<article>" | "forest"（aggregate 時標記來源＝封條 scope）
    revision: int = 1

    @classmethod
    def load(cls, path: Path, store: str = "") -> "AuditStore":
        from dspx.engine.sealed import load_sealed
        revision, items = load_sealed(path, list_key="findings", error_cls=AuditError)
        return cls(path=path, findings=items, store=store, revision=revision)

    def save(self) -> None:
        from dspx.engine.sealed import write_sealed
        write_sealed(self.path, kind="audit", scope=self.store or FOREST_STORE,
                     revision=self.revision, list_key="findings", items=self.findings)

    def by_id(self, fid: str) -> dict | None:
        for f in self.findings:
            if str(f.get("id")) == fid:
                return f
        return None

    def next_id(self) -> str:
        nums = []
        for f in self.findings:
            fid = str(f.get("id", ""))
            if fid.startswith("F") and fid[1:].isdigit():
                nums.append(int(fid[1:]))
        return f"F{(max(nums) + 1) if nums else 1}"


# ── 儲存路徑與 load helpers（比照 roadmap.py）─────────────────────────

def doc_audit_path(layout: Layout, article: str) -> Path:
    """per-doc audit 檔＝**sibling 密封檔** `corpus/<article>.audit.yaml`（一篇一檔 store 的兄弟；
    形狀命中 hook `_is_store_file`＝自動守手改）。"""
    return layout.corpus_dir / f"{article}.audit.yaml"


def forest_audit_path(layout: Layout) -> Path:
    return layout.planning_home / AUDIT_FILE


def load_doc_audit(layout: Layout, article: str) -> AuditStore:
    """讀 `corpus/<article>.audit.yaml`；缺席→空 store。標 store="doc:<article>"。"""
    return AuditStore.load(doc_audit_path(layout, article), store=f"doc:{article}")


def load_forest_audit(layout: Layout) -> AuditStore:
    """讀 forest audit.yaml；缺席→空 store。標 store="forest"。"""
    return AuditStore.load(forest_audit_path(layout), store=FOREST_STORE)


def all_findings(layout: Layout, leaves: list) -> list[dict]:
    """forest 全部 finding ＋ 每個 article-root 的 doc audit（每 distinct article 一份）。

    每筆掛 `_store`（"forest" | "doc:<article>"），供彙總/放置判定/反查。
    """
    out: list[dict] = []
    for f in load_forest_audit(layout).findings:
        out.append({**f, "_store": FOREST_STORE})
    seen_articles: list[str] = []
    for leaf in leaves:
        art = leaf.article
        if art and art not in seen_articles:
            seen_articles.append(art)
    for art in seen_articles:
        store = load_doc_audit(layout, art)
        for f in store.findings:
            out.append({**f, "_store": f"doc:{art}"})
    return out


def article_of_target(target: str, leaves: list) -> str | None:
    """target（section 路徑 或 concept id）→ 它所屬文件（article）；找不到回 None。

    §anchor（如 'zenoh/query#某段'）取 '#' 前的 section 部分解析。
    """
    sec = str(target).split("#", 1)[0]
    for leaf in leaves:
        if leaf.section == sec or (leaf.concept_id and str(leaf.concept_id) == sec):
            return leaf.article
    return None


def distinct_articles(targets: list, leaves: list) -> list[str]:
    """targets 解析出的 distinct 文件清單（保序、去重；無法解析的 target 略過）。"""
    out: list[str] = []
    for t in targets:
        art = article_of_target(t, leaves)
        if art and art not in out:
            out.append(art)
    return out


def route_store(layout: Layout, leaves: list, targets: list) -> AuditStore:
    """依 targets 的 distinct 文件數路由：1→該 doc-root、≥2→forest。

    0 個可解析 target → AuditError（targets 必須指向真實 section）。
    """
    arts = distinct_articles(targets, leaves)
    if not arts:
        raise AuditError("targets do not resolve to any real section (use a full section path or concept id)")
    if len(arts) == 1:
        return load_doc_audit(layout, arts[0])
    return load_forest_audit(layout)


def validate_finding(f: dict, faces: tuple[str, ...]) -> list[str]:
    """欄位級驗證（check 與寫時共用）。"""
    errs = []
    if not f.get("id"):
        errs.append("finding missing id")
    if f.get("face") not in faces:
        errs.append(f"finding {f.get('id')}: face \"{f.get('face')}\" not in {faces}")
    if f.get("severity") not in SEVERITIES:
        errs.append(f"finding {f.get('id')}: severity \"{f.get('severity')}\" not in {SEVERITIES}")
    if f.get("status") not in STATUSES:
        errs.append(f"finding {f.get('id')}: status \"{f.get('status')}\" not in {STATUSES}")
    # 晉升指標（promoted-to）collapse 後全文搬走，缺 finding 合法（搬家不複製）；
    # 一般 finding 仍必須帶內容。
    if not f.get("finding") and not f.get("promoted-to"):
        errs.append(f"finding {f.get('id')}: missing finding content")
    if not f.get("targets"):
        errs.append(f"finding {f.get('id')}: missing targets (the list of sections it touches)")
    elif not isinstance(f.get("targets"), list):
        errs.append(f"finding {f.get('id')}: targets must be a list")
    # verdict 為可選 NLI 判決；只在「present」時驗（缺＝合法，舊 finding 不破）。
    if "verdict" in f and f.get("verdict") not in VERDICTS:
        errs.append(f"finding {f.get('id')}: verdict \"{f.get('verdict')}\" not in {VERDICTS}")
    return errs


def raise_finding(store: AuditStore, *, face: str, severity: str, finding: str,
                  targets: list, suggestion: str = "", sot_owner: str = "",
                  verdict: str = "",
                  faces: tuple[str, ...] = DEFAULT_FACES,
                  fid: str | None = None) -> dict:
    """🔴紅隊開 finding（append；寫時驗證）。

    fid 可由呼叫端給全域唯一 id；targets＝它觸及的 section 清單（路由已由呼叫端定 store）。
    verdict＝可選 NLI 判決（contradicted/unsupported），只給引用查核的 finding 用。
    """
    entry = {
        "id": fid or store.next_id(),
        "face": face,
        "severity": severity,
        "status": "open",
        "targets": list(targets),
        "finding": finding,
        "suggestion": suggestion,
        "log": [{"round": 1, "actor": "factcheck", "action": "raised"}],
    }
    if sot_owner:
        entry["sot-owner"] = sot_owner
    if verdict:
        entry["verdict"] = verdict
    errs = validate_finding(entry, faces)
    if errs:
        raise AuditError("; ".join(errs))
    store.findings.append(entry)
    return entry


def find_store(layout: Layout, leaves: list, fid: str) -> AuditStore | None:
    """用 finding id 反查它所在的 store（forest ＋ 各 doc-root）。"""
    forest = load_forest_audit(layout)
    if forest.by_id(fid):
        return forest
    seen: list[str] = []
    for leaf in leaves:
        art = leaf.article
        if not art or art in seen:
            continue
        seen.append(art)
        store = load_doc_audit(layout, art)
        if store.by_id(fid):
            return store
    return None


def resolve_finding(store: AuditStore, fid: str, *, status: str, actor: str,
                    note: str = "") -> dict:
    """🔵藍隊回報 / 🔴紅隊驗證（append 一筆 log；更新當前 status；寫時驗證）。"""
    f = store.by_id(fid)
    if f is None:
        raise AuditError(f"finding not found \"{fid}\"")
    if status not in STATUSES:
        raise AuditError(f"status \"{status}\" not in {STATUSES}")
    rounds = f.get("log") or []
    entry = {"round": len(rounds) + 1, "actor": actor, "action": "responded",
             "status": status}
    if note:
        entry["note"] = note
    f.setdefault("log", []).append(entry)
    f["status"] = status        # 頂層存當前態（log 末筆），方便查
    return f
