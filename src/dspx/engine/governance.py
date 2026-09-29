"""治理層紀錄（專案最外層）：待裁定問題、裁定、決策、可疑標記、roadmap。

設計依據：docs/dev/system-design.md（架構第二版）、docs/dev/phase1-design.md。

- **一筆一檔**：`docspec/governance/<夾>/<id>.yaml`。兩個分支各自新增紀錄＝只多出不同檔案，
  git 合併不衝突；每檔各自封條（沿用 sealed.integrity_of），手改 fail-loud 指路 fsck。
- **編號**：`<類別>-<工具前綴>-<流水號>`（例 `D-claude-13`）。前綴＝claude/gpt/gemini/user；
  各前綴各自流水號，不同工具並行不撞號。同一工具在兩分支同時編號的撞號由 check 抓出。
- **引用命名空間**：文件側以 `gov:<id>` 引用治理決策，避免與文件內自由命名的決策 id 撞名。
- **狀態盡量推導、不改舊檔**：裁定「被取代」、決策「被取代」、問題「已裁定」都由其他紀錄推導，
  舊紀錄檔一個 byte 不動（合併友善，且符合「歷史只追加」）。
- 這層只做「忠實載入＋結構驗證＋推導」；語義對錯不判。
"""

from __future__ import annotations

import datetime
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from dspx.engine.layout import Layout
from dspx.engine.model import ModelError
from dspx.engine.sealed import integrity_of
from dspx.engine.store import _yaml_dump, atomic_write_store

GOV_DIR_NAME = "governance"
GOV_NAMESPACE = "gov:"
RECORD_FORMAT_VERSION = 1

# 紀錄型別 → (編號類別字首, 子資料夾)
KINDS: dict[str, tuple[str, str]] = {
    "question": ("Q", "questions"),
    "ruling": ("RL", "rulings"),
    "decision": ("D", "decisions"),
    "suspect": ("S", "suspects"),
    "milestone": ("M", "roadmap"),      # 唯一一份專案 roadmap：里程碑與工作項目同住 roadmap/
    "work": ("W", "roadmap"),
}
PREFIX_TO_KIND = {v[0]: k for k, v in KINDS.items()}

TOOLS = ("claude", "gpt", "gemini", "user")
_ID_RE = re.compile(r"^(?P<cls>[A-Z]+)-(?P<tool>[a-z]+)-(?P<n>[1-9][0-9]*)$")

# ── 各型別的欄位（封閉集合：未知欄位＝check ERROR）與可存狀態 ─────────────────
FIELDS: dict[str, dict[str, bool]] = {   # 欄位 → 是否必填
    "question": {"id": True, "title": True, "body": False, "status": True,
                 "raised-by": True, "raised-at": True, "affects": False},
    # 裁定（2026/09/30 裁定）：agent 先在對話中覆述（read-back），使用者回覆確認（confirmed-reply）
    # 後才寫入，寫入即生效。原話、覆述、確認回覆、轉記者一起留下（可見性取代事前把關）。
    "ruling": {"id": True, "quote": True, "date": True, "recorded-by": True,
               "read-back": True, "confirmed-reply": True, "status": True, "answers": False,
               "supersedes": False, "provisional": False, "rejected-reason": False,
               "rejected-at": False},
    "decision": {"id": True, "title": True, "statement": True, "rationale": False,
                 "status": True, "based-on": False, "supersedes": False,
                 "created-by": True, "created-at": True},
    "suspect": {"id": True, "trigger": True, "target": True, "path": False,
                "status": True, "created-at": True, "cleared-reason": False,
                "cleared-by": False, "cleared-at": False},
    # roadmap：狀態一律推導（不存 status 欄）；做完的項目保留，不再移出檔案。
    "milestone": {"id": True, "title": True, "type": True, "due": False, "note": False,
                  "created-by": True, "created-at": True},
    "work": {"id": True, "title": True, "what": False, "milestone": False, "parent": False,
             "depends-on": False, "refs": False, "kind": False, "priority": False,
             "closed": False, "waivers": False, "from-audit": False, "legacy-id": False,
             "created-by": True, "created-at": True},
}
MILESTONE_TYPES = ("checkpoint", "deliverable")   # 計畫查核點 vs 交付物（分開，SR15）
STORED_STATUS: dict[str, tuple[str, ...]] = {
    "question": ("open", "needs-explanation", "withdrawn"),
    "ruling": ("effective", "rejected"),
    "decision": ("draft", "active", "withdrawn"),
    "suspect": ("open", "cleared"),
}


class GovernanceError(ModelError):
    """治理層操作失敗（ModelError 子類＝沿用既有 fail-loud/CLI 友善錯誤路徑）。"""


# ── 路徑 ─────────────────────────────────────────────────────────────────

def gov_dir(layout: Layout) -> Path:
    return layout.planning_home / GOV_DIR_NAME


def kind_dir(layout: Layout, kind: str) -> Path:
    return gov_dir(layout) / KINDS[kind][1]


def record_path(layout: Layout, kind: str, rid: str) -> Path:
    return kind_dir(layout, kind) / f"{rid}.yaml"


def kind_of_id(rid: str) -> str | None:
    m = _ID_RE.match(str(rid))
    return PREFIX_TO_KIND.get(m.group("cls")) if m else None


def strip_ns(ref: str) -> str:
    ref = str(ref)
    return ref[len(GOV_NAMESPACE):] if ref.startswith(GOV_NAMESPACE) else ref


# ── 工具前綴判斷 ──────────────────────────────────────────────────────────

def detect_tool(explicit: str | None = None) -> str:
    """回傳工具前綴。優先序：--by 明示 → DOCSPEC_AGENT → 各家 agent 環境變數 → 真人終端＝user。
    判斷不出來（非互動、無任何 agent 記號）→ GovernanceError 要求 --by。"""
    for cand in (explicit, os.environ.get("DOCSPEC_AGENT")):
        if cand:
            cand = cand.strip().lower()
            if cand not in TOOLS:
                raise GovernanceError(f"unknown tool prefix \"{cand}\"; choose one of {', '.join(TOOLS)}")
            return cand
    env = os.environ
    if env.get("CLAUDECODE") or env.get("CLAUDE_CODE_ENTRYPOINT"):
        return "claude"
    if env.get("GEMINI_CLI") or env.get("ANTIGRAVITY_AGENT"):
        return "gemini"
    if _codex_marker(env):
        return "gpt"
    if sys.stdin.isatty() and sys.stdout.isatty():
        return "user"
    raise GovernanceError("cannot tell which agent is running this command; pass --by claude|gpt|gemini")


def _codex_marker(env) -> bool:
    # CODEX_HOME 是使用者自己也可能設定的設定目錄，不算「正在 Codex 裡執行」的記號。
    return any(k.startswith("CODEX_") and k != "CODEX_HOME" for k in env)


AGENT_ENV_MARKERS = ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "GEMINI_CLI", "ANTIGRAVITY_AGENT",
                     "DOCSPEC_AGENT")


def today() -> str:
    return datetime.date.today().strftime("%Y-%m-%d")


# ── 單筆紀錄的封條讀寫 ─────────────────────────────────────────────────────

def _seal(kind: str, record: dict) -> str:
    return integrity_of(f"governance-{kind}", "project", RECORD_FORMAT_VERSION, "record", record)


def dump_record(kind: str, record: dict) -> str:
    header = (f"# docspec governance {kind} — engine-owned; never edit by hand.\n"
              f"# Change it through docspec commands; a hand-edit breaks the integrity seal.\n")
    doc = {"format": RECORD_FORMAT_VERSION, "kind": f"governance-{kind}",
           "integrity": _seal(kind, record), "record": record}
    return header + _yaml_dump(doc)


def write_record(layout: Layout, kind: str, record: dict) -> Path:
    path = record_path(layout, kind, record["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_store(path, dump_record(kind, record))
    return path


def load_record(path: Path, kind: str) -> dict:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise GovernanceError(f"YAML parse failed: {path}") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("record"), dict):
        raise GovernanceError(f"malformed governance record (missing `record` mapping): {path}")
    record = raw["record"]
    if raw.get("integrity") != _seal(kind, record):
        raise GovernanceError(
            f"integrity seal mismatch: {path} — a hand-edit corrupted this governance record; "
            f"change it through docspec commands (or run `docspec store fsck --accept` to adopt it).")
    return record


def load_all(layout: Layout, kind: str) -> list[dict]:
    d = kind_dir(layout, kind)
    if not d.is_dir():
        return []
    cls = KINDS[kind][0]
    out = []
    for p in sorted(d.glob("*.yaml")):
        if p.stem.split("-", 1)[0] != cls:       # roadmap/ 同夾住兩種紀錄
            continue
        rec = load_record(p, kind)
        out.append({**rec, "_file": p.stem})
    return out


@dataclass
class Governance:
    """整個治理層的一次快照（每次執行重新載入，不另存索引）。"""

    questions: list[dict]
    rulings: list[dict]
    decisions: list[dict]
    suspects: list[dict]
    milestones: list[dict] = field(default_factory=list)
    work: list[dict] = field(default_factory=list)

    def by_id(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for recs in (self.questions, self.rulings, self.decisions, self.suspects,
                     self.milestones, self.work):
            for r in recs:
                out[str(r.get("id"))] = r
        return out


def load_governance(layout: Layout) -> Governance:
    return Governance(*(load_all(layout, k) for k in ("question", "ruling", "decision",
                                                        "suspect", "milestone",
                                                        "work")))


def has_governance(layout: Layout) -> bool:
    return gov_dir(layout).is_dir()


# ── 編號配發 ──────────────────────────────────────────────────────────────

def next_id(layout: Layout, kind: str, tool: str) -> str:
    cls = KINDS[kind][0]
    top = 0
    d = kind_dir(layout, kind)
    if d.is_dir():
        for p in d.glob("*.yaml"):
            m = _ID_RE.match(p.stem)
            if m and m.group("cls") == cls and m.group("tool") == tool:
                top = max(top, int(m.group("n")))
    return f"{cls}-{tool}-{top + 1}"


# ── 推導狀態 ──────────────────────────────────────────────────────────────

def _as_list(v) -> list:
    if v is None:
        return []
    return [str(x) for x in (v if isinstance(v, list) else [v])]


def ruling_effective_status(r: dict, gov: Governance) -> str:
    """effective 且被某條 effective 裁定取代 → superseded；其餘照存值。"""
    status = r.get("status")
    if status == "effective":
        rid = str(r.get("id"))
        for other in gov.rulings:
            if other.get("status") == "effective" and rid in _as_list(other.get("supersedes")):
                return "superseded"
    return status


def decision_effective_status(d: dict, gov: Governance) -> str:
    """active 且被某條 active 決策取代 → superseded；其餘照存值。"""
    status = d.get("status")
    if status == "active":
        did = str(d.get("id"))
        for other in gov.decisions:
            if other.get("status") == "active" and did in _as_list(other.get("supersedes")):
                return "superseded"
    return status


def question_effective_status(q: dict, gov: Governance) -> str:
    """有未被駁回的裁定回答它 → answered（withdrawn 優先）。"""
    if q.get("status") == "withdrawn":
        return "withdrawn"
    qid = str(q.get("id"))
    for r in gov.rulings:
        if r.get("status") == "effective" and qid in _as_list(r.get("answers")):
            return "answered"
    return q.get("status")


def superseded_by(d: dict, gov: Governance) -> str | None:
    did = str(d.get("id"))
    for other in gov.decisions:
        if other.get("status") == "active" and did in _as_list(other.get("supersedes")):
            return str(other["id"])
    return None


def invalid_basis(d: dict, gov: Governance) -> list[str]:
    """決策依據中「不能作為生效依據」的裁定：不存在，或已被使用者駁回。"""
    rulings = {str(r.get("id")): r for r in gov.rulings}
    bad = []
    for rid in _as_list(d.get("based-on")):
        r = rulings.get(rid)
        if r is None or r.get("status") != "effective":
            bad.append(rid)
    return bad


# ── 給文件引擎用的決策索引（gov: 命名空間） ────────────────────────────────

# 治理決策狀態 → 文件引擎的決策狀態語彙（ACTIVE_DECISION_STATUSES / _DEAD_DECISION_STATUSES）
_STATUS_MAP = {"active": "accepted", "superseded": "superseded", "withdrawn": "deprecated",
               "draft": "draft"}


def decision_index_entries(layout: Layout) -> dict:
    """治理決策 → 文件引擎 decision_index 的外部條目（鍵帶 `gov:`）。無治理層＝{}。"""
    if not has_governance(layout):
        return {}
    gov = load_governance(layout)
    out: dict = {}
    for d in gov.decisions:
        status = decision_effective_status(d, gov)
        succ = superseded_by(d, gov)
        out[GOV_NAMESPACE + str(d["id"])] = {
            "section": None, "statement": d.get("statement"), "kind": "decision",
            "status": _STATUS_MAP.get(status, status),
            "superseded_by": (GOV_NAMESPACE + succ) if succ else None,
        }
    return out


# ── 結構驗證（check ⑬） ───────────────────────────────────────────────────

def validate(layout: Layout) -> list[str]:
    if not has_governance(layout):
        return []
    errs: list[str] = []
    try:
        gov = load_governance(layout)
    except GovernanceError as exc:
        return [str(exc)]
    ids: dict[str, str] = {}
    for kind, recs in (("question", gov.questions), ("ruling", gov.rulings),
                       ("decision", gov.decisions), ("suspect", gov.suspects),
                       ("milestone", gov.milestones),
                       ("work", gov.work)):
        fields = FIELDS[kind]
        for r in recs:
            rid = str(r.get("id") or "")
            where = f"governance {kind} {rid or r.get('_file')}"
            if not rid:
                errs.append(f"{where}: missing id")
                continue
            if rid != r.get("_file"):
                errs.append(f"{where}: id does not match its file name ({r.get('_file')}.yaml)")
            if kind_of_id(rid) != kind:
                errs.append(f"{where}: id \"{rid}\" is not a valid {kind} id "
                            f"({KINDS[kind][0]}-<tool>-<n>)")
            if rid in ids:
                errs.append(f"duplicate governance id \"{rid}\" (two branches numbered the same "
                            f"record; run `docspec gov renumber {rid}` on the newer one)")
            ids[rid] = kind
            for key in r:
                if key != "_file" and key not in fields:
                    errs.append(f"{where}: unknown field \"{key}\"")
            for key, required in fields.items():
                if required and r.get(key) in (None, ""):
                    errs.append(f"{where}: missing required field \"{key}\"")
            if kind in STORED_STATUS and r.get("status") not in STORED_STATUS[kind]:
                errs.append(f"{where}: status \"{r.get('status')}\" not in {STORED_STATUS[kind]}")

    def expect(where: str, refs, kind: str, field: str) -> None:
        for ref in _as_list(refs):
            if ids.get(strip_ns(ref)) != kind:
                errs.append(f"{where}: {field} points to nonexistent {kind} \"{ref}\"")

    for r in gov.rulings:
        where = f"governance ruling {r.get('id')}"
        expect(where, r.get("answers"), "question", "answers")
        expect(where, r.get("supersedes"), "ruling", "supersedes")
    for d in gov.decisions:
        where = f"governance decision {d.get('id')}"
        expect(where, d.get("based-on"), "ruling", "based-on")
        expect(where, d.get("supersedes"), "decision", "supersedes")
        if d.get("status") == "active":
            bad = invalid_basis(d, gov)
            if bad:
                errs.append(f"{where}: active but based on missing or rejected rulings: "
                            f"{', '.join(bad)}")
        if str(d.get("id")) in _as_list(d.get("supersedes")):
            errs.append(f"{where}: supersedes itself")
    # question.affects 可指向任何紀錄（含文件章節），不在此驗死引用。
    for m in gov.milestones:
        if m.get("type") not in MILESTONE_TYPES:
            errs.append(f"governance milestone {m.get('id')}: type \"{m.get('type')}\" not in "
                        f"{MILESTONE_TYPES}")
    for w in gov.work:
        where = f"governance work item {w.get('id')}"
        expect(where, w.get("milestone"), "milestone", "milestone")
        expect(where, w.get("parent"), "work", "parent")
        expect(where, w.get("depends-on"), "work", "depends-on")
        for wv in (w.get("waivers") or []):
            if not isinstance(wv, dict) or not wv.get("ruling"):
                errs.append(f"{where}: each waiver needs a ruling")
            else:
                expect(where, wv.get("ruling"), "ruling", "waiver ruling")
        # refs（doc:/change:/gov:）的死引用需要 corpus 與 changes 脈絡 → check 層另驗
    errs.extend(_dep_cycles(gov.work, "depends-on"))
    errs.extend(_dep_cycles(gov.work, "parent"))
    errs.extend(_supersede_cycles(gov.decisions, "decision"))
    errs.extend(_supersede_cycles(gov.rulings, "ruling"))
    return errs


def _dep_cycles(recs: list[dict], field_name: str) -> list[str]:
    return [e.replace("supersede cycle", f"{field_name} cycle")
            for e in _supersede_cycles(recs, "work item", field_name)]


def _supersede_cycles(recs: list[dict], kind: str, field_name: str = "supersedes") -> list[str]:
    graph = {str(r.get("id")): _as_list(r.get(field_name)) for r in recs}
    errs: list[str] = []
    state: dict[str, int] = {}

    def visit(n: str, stack: list[str]) -> None:
        state[n] = 1
        for m in graph.get(n, []):
            if state.get(m) == 1:
                cyc = stack[stack.index(m):] + [m] if m in stack else [n, m]
                errs.append(f"governance {kind} supersede cycle: {' -> '.join(cyc)}")
            elif state.get(m) is None and m in graph:
                visit(m, stack + [m])
        state[n] = 2

    for n in graph:
        if state.get(n) is None:
            visit(n, [n])
    return errs
