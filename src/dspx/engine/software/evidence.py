"""證據與任務完成的自動推導。

證據一筆一檔：`docspec/software/evidence/<E-工具-n>.yaml`（封條）。型別：

    test-run       引擎代跑測試：指令、repo、commit、環境指紋、各項數字、每個規劃測試的結果
    inspection     檢查紀錄：看了什麼、結論、pass/fail
    demonstration  展示紀錄（同上）
    analysis       分析紀錄（同上）
    acceptance     使用者驗收：agent 覆述、使用者確認原文（同裁定的覆述流程）
    waiver         豁免：依據哪條有效裁定、什麼情況重新打開

每筆證據都記下「當時」任務宣告檔案與測試檔的內容指紋。之後檔案內容變了，這筆證據就不再算數，
任務退回「需重跑證據」——不依賴 git，也涵蓋未 commit 的改動。

任務狀態（tasks.yaml 的 status／completed-at／evidence）只由 `refresh` 寫入：
    done          每一種驗證方法都有最新、通過、仍新鮮的證據
    done-waived   有豁免
    needs-rerun   原本通過的證據因檔案改動而失效
    in-progress   有證據但還不夠（或最新一次失敗）
    not-started   沒有證據
"""

from __future__ import annotations

import datetime
import hashlib
import os
import platform
import re
import shlex
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from dspx.engine import governance as gv
from dspx.engine.layout import Layout
from dspx.engine.software import changes as chg
from dspx.engine.software import io
from dspx.engine.software import tasks as tk

EVIDENCE_TYPES = ("test-run", "inspection", "demonstration", "analysis", "acceptance", "waiver")
_SATISFIES = {"test": ("test-run",), "inspection": ("inspection", "acceptance"),
              "demonstration": ("demonstration", "acceptance"), "analysis": ("analysis",)}
_E_RE = re.compile(r"^E-(?P<tool>[a-z]+)-(?P<n>[1-9][0-9]*)$")
OUTPUT_TAIL = 2000


# ── 儲存 ─────────────────────────────────────────────────────────────────

def _path(layout: Layout, eid: str) -> Path:
    return io.evidence_dir(layout) / f"{eid}.yaml"


def load_all(layout: Layout) -> list[dict]:
    d = io.evidence_dir(layout)
    if not d.is_dir():
        return []
    return [io.load(p, "evidence") for p in sorted(d.glob("*.yaml"))]


def next_id(layout: Layout, tool: str) -> str:
    top = 0
    d = io.evidence_dir(layout)
    if d.is_dir():
        for p in d.glob("*.yaml"):
            m = _E_RE.match(p.stem)
            if m and m.group("tool") == tool:
                top = max(top, int(m.group("n")))
    return f"E-{tool}-{top + 1}"


def _now() -> str:
    return datetime.datetime.now().replace(microsecond=0).isoformat()


def _write(layout: Layout, rec: dict) -> dict:
    io.write(_path(layout, rec["id"]), "evidence", rec)
    return rec


def for_task(evs: list[dict], cid: str, task_id: str) -> list[dict]:
    """這個任務的證據，舊到新。"""
    rows = [e for e in evs if e.get("change") == cid and str(e.get("task")) == str(task_id)]
    return sorted(rows, key=lambda e: (str(e.get("at")), _num(e.get("id"))))


def _num(eid) -> int:
    m = _E_RE.match(str(eid))
    return int(m.group("n")) if m else 0


# ── 檔案指紋（證據新鮮度）────────────────────────────────────────────────

def watched_files(ch: dict, task: dict) -> list[str]:
    """任務宣告的檔案＋它引用的規劃測試所在檔（`repo:路徑`，去重、排序）。"""
    out = set()
    for f in io.as_list(task.get("files")):
        repo, path = tk.location_file(f)
        out.add(f"{repo}:{path}")
    wanted = set(io.as_list((task.get("verify") or {}).get("tests")))
    for t in ch["tests"].get("tests") or []:
        if str(t.get("id")) in wanted:
            repo, path = tk.location_file(t.get("location") or "")
            out.add(f"{repo}:{path}")
    return sorted(out)


def file_hash(layout: Layout, key: str) -> str:
    repo, path = key.split(":", 1)
    if not tk.repo_known(layout, repo):
        return "unknown-repo"
    p = tk.repo_root(layout, repo) / path
    if not p.is_file():
        return "missing"
    return "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def snapshot(layout: Layout, keys: list[str]) -> dict[str, str]:
    return {k: file_hash(layout, k) for k in keys}


def stale_files(layout: Layout, ev: dict, current_keys: list[str]) -> list[str]:
    """證據之後內容變了（或新宣告而證據沒涵蓋）的檔案。"""
    recorded = ev.get("files") or {}
    return [k for k in current_keys if recorded.get(k) != file_hash(layout, k)]


# ── 狀態推導 ─────────────────────────────────────────────────────────────

def _covers_tests(ev: dict, task: dict) -> bool:
    wanted = set(io.as_list((task.get("verify") or {}).get("tests")))
    return wanted <= set(io.as_list(ev.get("tests")))


def derive(layout: Layout, ch: dict, task: dict, evs: list[dict]) -> tuple[str, list[str], str]:
    """回 (狀態, 支持完成的證據 id, 說明)。evs＝這個任務的證據（舊到新）。"""
    waivers = [e for e in evs if e.get("type") == "waiver"]
    if waivers:
        return "done-waived", [waivers[-1]["id"]], f"waived by {waivers[-1].get('ruling')}"
    methods = io.as_list((task.get("verify") or {}).get("methods"))
    keys = watched_files(ch, task)
    support, missing, stale, failing = [], [], [], []
    for m in methods:
        cands = [e for e in evs if e.get("type") in _SATISFIES.get(m, ())]
        if m == "test":
            cands = [e for e in cands if _covers_tests(e, task)]
        if not cands:
            missing.append(m)
            continue
        latest = cands[-1]
        if latest.get("result") != "pass":
            failing.append(f"{m} ({latest['id']}: {latest.get('reason') or 'failed'})")
            continue
        changed = stale_files(layout, latest, keys)
        if changed:
            stale.append(f"{m} ({latest['id']}; changed: {', '.join(changed)})")
            continue
        support.append(latest["id"])
    if methods and not missing and not stale and not failing:
        return "done", support, "all verification methods have fresh passing evidence"
    if stale:
        return "needs-rerun", support, "evidence is stale: " + "; ".join(stale)
    if evs:
        parts = []
        if failing:
            parts.append("latest failed: " + "; ".join(failing))
        if missing:
            parts.append("no evidence yet for: " + ", ".join(missing))
        return "in-progress", support, "; ".join(parts)
    if task.get("status") == "imported-done":
        return "imported-done", [], "completed before import (no evidence)"
    return "not-started", [], "no evidence yet"


def refresh(layout: Layout, cid: str, evs: list[dict] | None = None) -> list[tuple[str, str, str]]:
    """重新推導這個 change 每個任務的狀態並寫回 tasks.yaml（只有變了才寫）。回 [(任務, 舊, 新)]。"""
    ch = chg.load_change(layout, cid)
    evs = load_all(layout) if evs is None else evs
    changed = []
    for t in ch["tasks"].get("tasks") or []:
        mine = for_task(evs, cid, t["id"])
        status, support, _why = derive(layout, ch, t, mine)
        old = t.get("status", "not-started")
        new_fields = {"status": status}
        if status in ("done", "done-waived"):
            new_fields["completed-at"] = (t.get("completed-at") if old == status and t.get("completed-at")
                                          else gv.today())
            new_fields["evidence"] = support
        cur = {k: t.get(k) for k in ("status", "completed-at", "evidence") if k in t}
        if cur != new_fields:
            for k in ("completed-at", "evidence"):
                t.pop(k, None)
            t.update(new_fields)
            changed.append((str(t["id"]), old, status))
    if changed:
        chg.write_part(layout, cid, "tasks", ch["tasks"])
    return changed


def explain(layout: Layout, cid: str) -> list[dict]:
    ch = chg.load_change(layout, cid)
    evs = load_all(layout)
    out = []
    for t in ch["tasks"].get("tasks") or []:
        status, support, why = derive(layout, ch, t, for_task(evs, cid, t["id"]))
        out.append({"task": t["id"], "title": t.get("title"), "status": status,
                    "recorded": t.get("status"), "evidence": support, "why": why})
    return out


# ── 環境指紋 ─────────────────────────────────────────────────────────────

def environment(layout: Layout, cwd: Path) -> dict:
    cfg = chg.load_config(layout).get("environment") or {}
    env = {"python": platform.python_version(), "platform": platform.platform()}
    wanted = [str(v) for v in cfg.get("vars") or []]
    if wanted:
        env["vars"] = {v: os.environ.get(v) for v in wanted}
    checks = []
    for c in cfg.get("checks") or []:
        name, cmd = (c.get("name"), c.get("run")) if isinstance(c, dict) else (str(c), str(c))
        try:
            r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=60)
            checks.append({"name": name, "ok": r.returncode == 0})
        except (OSError, subprocess.TimeoutExpired):
            checks.append({"name": name, "ok": False})
    if checks:
        env["checks"] = checks
    return env


def _git(cwd: Path, *args: str) -> str | None:
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


# ── pytest 結果解析 ──────────────────────────────────────────────────────

def _parse_junit(path: Path) -> list[dict]:
    """[{classname, name, outcome: passed|failed|skipped}]。"""
    root = ET.parse(path).getroot()
    out = []
    for tc in root.iter("testcase"):
        outcome = "passed"
        for child in tc:
            if child.tag in ("failure", "error"):
                outcome = "failed"
            elif child.tag == "skipped" and outcome == "passed":
                outcome = "skipped"
        out.append({"classname": tc.get("classname") or "", "name": tc.get("name") or "",
                    "outcome": outcome})
    return out


def _matches(location: str, case: dict) -> bool:
    _repo, loc = tk.split_location(location)
    file_part, _, rest = loc.partition("::")
    mod = file_part[:-3] if file_part.endswith(".py") else file_part
    mod = mod.replace("/", ".").replace("\\", ".")
    parts = [p for p in rest.split("::") if p]
    func = parts[-1] if parts else None
    expected_cls = ".".join([mod, *parts[:-1]]) if parts else mod
    cls = case["classname"]

    def same(a: str, b: str) -> bool:     # pytest 的 rootdir 可能比 repo 根深或淺：比對尾段
        return a == b or a.endswith("." + b) or b.endswith("." + a)

    if not parts:       # 只寫檔案＝那個模組（含其中的類別）裡的全部測試
        return same(cls, mod) or any(same(cls[:i], mod) for i in range(len(cls)) if cls[i] == ".")
    return same(cls, expected_cls) and case["name"].split("[", 1)[0] == func


_SUMMARY = re.compile(r"(\d+) (passed|failed|skipped|errors?|error)")


def _summary_counts(text: str) -> dict:
    counts = {"passed": 0, "failed": 0, "skipped": 0}
    for n, kind in _SUMMARY.findall(text):
        key = "failed" if kind.startswith("error") else kind
        counts[key] += int(n)
    return counts


# ── 產生證據 ─────────────────────────────────────────────────────────────

def _task(ch: dict, task_id: str) -> dict:
    for t in ch["tasks"].get("tasks") or []:
        if str(t.get("id")) == str(task_id):
            return t
    raise io.SoftwareError(f"change {ch['id']} has no task \"{task_id}\"")


def _planned(ch: dict, task: dict) -> list[dict]:
    wanted = io.as_list((task.get("verify") or {}).get("tests"))
    by_id = {str(t.get("id")): t for t in ch["tests"].get("tests") or []}
    missing = [w for w in wanted if w not in by_id]
    if missing:
        raise io.SoftwareError(f"task {task['id']} references unplanned test(s): {', '.join(missing)}")
    return [by_id[w] for w in wanted]


def run_tests(layout: Layout, cid: str, task_id: str, command: list[str] | None, *, tool: str,
              timeout: int = 1800) -> dict:
    """引擎代跑測試並寫一筆 test-run 證據；回紀錄。不讓 agent 手填數字。"""
    ch = chg.load_change(layout, cid)
    task = _task(ch, task_id)
    planned = _planned(ch, task)
    if not planned:
        raise io.SoftwareError(f"task {task_id} has no planned tests (verify.tests) to run")
    repos_used = {tk.split_location(t["location"])[0] for t in planned}
    if len(repos_used) > 1:
        raise io.SoftwareError(f"task {task_id}'s planned tests span repos {sorted(repos_used)}; "
                               f"split the task per repo")
    repo = repos_used.pop()
    if not tk.repo_known(layout, repo):
        raise io.SoftwareError(f"repo \"{repo}\" is not registered in software/config.yaml")
    cwd = tk.repo_root(layout, repo)
    if not command:
        base = (chg.repo_settings(layout).get(repo) or {}).get("test-command") or "python -m pytest"
        command = shlex.split(str(base)) + [tk.split_location(t["location"])[1] for t in planned]
    is_pytest = any("pytest" in part for part in command)
    keys = watched_files(ch, task)
    files_before = snapshot(layout, keys)
    with tempfile.TemporaryDirectory() as tmp:
        junit = Path(tmp) / "junit.xml"
        argv = list(command) + ([f"--junitxml={junit}"] if is_pytest else [])
        try:
            proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout)
            exit_code, output = proc.returncode, (proc.stdout or "") + (proc.stderr or "")
        except FileNotFoundError as exc:
            raise io.SoftwareError(f"cannot run {command[0]!r}: {exc}") from exc
        except subprocess.TimeoutExpired:
            exit_code, output = -1, f"timed out after {timeout}s"
        cases = _parse_junit(junit) if is_pytest and junit.is_file() else None

    allow_skips = bool((task.get("verify") or {}).get("allow-skips"))
    per_test = []
    reasons = []
    if cases is not None:
        counts = {k: sum(1 for c in cases if c["outcome"] == k) for k in ("passed", "failed", "skipped")}
        for t in planned:
            hit = [c for c in cases if _matches(t["location"], c)]
            if not hit:
                outcome = "not-run"
            elif any(c["outcome"] == "failed" for c in hit):
                outcome = "failed"
            elif all(c["outcome"] == "skipped" for c in hit):
                outcome = "skipped"
            else:
                outcome = "passed"
            per_test.append({"test": t["id"], "location": t["location"], "outcome": outcome,
                             "cases": len(hit)})
        not_run = [p["test"] for p in per_test if p["outcome"] == "not-run"]
        if not_run:
            reasons.append(f"planned test(s) not found in the run: {', '.join(not_run)}")
    else:
        counts = _summary_counts(output)
        reasons.append("pytest produced no junit report" if is_pytest
                       else "non-pytest command: per-test results unavailable")
    if exit_code != 0:
        reasons.append(f"exit code {exit_code}")
    if counts["failed"]:
        reasons.append(f"{counts['failed']} failed")
    if counts["skipped"] and not allow_skips:
        reasons.append(f"{counts['skipped']} skipped (not declared with --allow-skips)")
    if cases is None and is_pytest:
        result = "fail"
    else:
        blocking = [r for r in reasons if not r.startswith("non-pytest")]
        result = "fail" if blocking else "pass"
    if files_before != snapshot(layout, keys):
        reasons.append("files changed while the tests ran")
        result = "fail"

    ran = [t["id"] for t in planned if cases is None
           or any(p["test"] == t["id"] and p["outcome"] != "not-run" for p in per_test)]
    rec = {"id": next_id(layout, tool), "type": "test-run", "change": cid, "task": str(task_id),
           "recorded-by": tool, "at": _now(), "repo": repo, "command": shlex.join(command),
           "commit": _git(cwd, "rev-parse", "HEAD"), "environment": environment(layout, cwd),
           "exit-code": exit_code, "counts": counts, "tests": ran,
           "result": result, "files": files_before, "output-tail": output[-OUTPUT_TAIL:]}
    if per_test:
        rec["per-test"] = per_test
    if reasons:
        rec["reason"] = "; ".join(reasons)
    if rec["commit"] is None:
        rec.pop("commit")
    return _write(layout, rec)


def record(layout: Layout, cid: str, task_id: str, etype: str, *, tool: str, subject: str,
           conclusion: str, result: str) -> dict:
    if etype not in ("inspection", "demonstration", "analysis"):
        raise io.SoftwareError("--type must be inspection, demonstration or analysis "
                               "(tests: `code evidence run`; the owner's sign-off: `code evidence accept`)")
    if result not in ("pass", "fail"):
        raise io.SoftwareError("--result must be pass or fail")
    if not subject.strip() or not conclusion.strip():
        raise io.SoftwareError("--subject and --conclusion must not be empty")
    ch = chg.load_change(layout, cid)
    task = _task(ch, task_id)
    rec = {"id": next_id(layout, tool), "type": etype, "change": cid, "task": str(task_id),
           "recorded-by": tool, "at": _now(), "subject": subject.strip(),
           "conclusion": conclusion.strip(), "result": result,
           "files": snapshot(layout, watched_files(ch, task))}
    return _write(layout, rec)


def accept(layout: Layout, cid: str, task_id: str, *, tool: str, read_back: str,
           confirmed: str) -> dict:
    if not read_back.strip() or not confirmed.strip():
        raise io.SoftwareError("acceptance needs the read-back and the owner's confirming reply "
                               "(--read-back and --confirmed must not be empty)")
    ch = chg.load_change(layout, cid)
    task = _task(ch, task_id)
    rec = {"id": next_id(layout, tool), "type": "acceptance", "change": cid, "task": str(task_id),
           "recorded-by": tool, "at": _now(), "read-back": read_back.strip(),
           "confirmed-reply": confirmed.strip(), "result": "pass",
           "files": snapshot(layout, watched_files(ch, task))}
    return _write(layout, rec)


def waive(layout: Layout, cid: str, task_id: str, *, tool: str, ruling: str, reopen_when: str) -> dict:
    ch = chg.load_change(layout, cid)
    _task(ch, task_id)
    rid = gv.strip_ns(ruling)
    if not gv.has_governance(layout):
        raise io.SoftwareError("a waiver must cite an effective ruling, but there is no governance/")
    gov = gv.load_governance(layout)
    r = next((x for x in gov.rulings if str(x.get("id")) == rid), None)
    if r is None or gv.ruling_effective_status(r, gov) != "effective":
        raise io.SoftwareError(f"waiver needs an effective ruling; \"{rid}\" is "
                               f"{'missing' if r is None else gv.ruling_effective_status(r, gov)}")
    if not reopen_when.strip():
        raise io.SoftwareError("waiver needs --reopen-when (the condition that brings the task back)")
    rec = {"id": next_id(layout, tool), "type": "waiver", "change": cid, "task": str(task_id),
           "recorded-by": tool, "at": _now(), "ruling": f"gov:{rid}",
           "reopen-when": reopen_when.strip(), "result": "pass"}
    return _write(layout, rec)


# ── 引用檢查（check ⑭ 追加）──────────────────────────────────────────────

def validate(layout: Layout) -> tuple[list[str], list[str]]:
    errs, warns = [], []
    try:
        evs = load_all(layout)
    except io.SoftwareError as exc:
        return [str(exc)], []
    active = set(chg.list_active(layout))
    archived = set(chg.archived_ids(layout))
    seen = set()
    for e in evs:
        eid = e.get("id")
        if eid in seen:
            errs.append(f"evidence {eid}: duplicate id")
        seen.add(eid)
        if e.get("type") not in EVIDENCE_TYPES:
            errs.append(f"evidence {eid}: unknown type \"{e.get('type')}\"")
        if e.get("change") not in active | archived:
            errs.append(f"evidence {eid}: change \"{e.get('change')}\" does not exist")
    for cid in active:
        ch = chg.load_change(layout, cid)
        by_id = {str(t.get("id")): t for t in ch["tests"].get("tests") or []}
        for row in explain(layout, cid):
            if row["recorded"] != row["status"]:
                warns.append(f"software change {cid}: task {row['task']} is recorded "
                             f"\"{row['recorded']}\" but evidence says \"{row['status']}\" — run "
                             f"`docspec code change status {cid}` to refresh ({row['why']})")
        for e in [x for x in evs if x.get("change") == cid and x.get("type") == "test-run"]:
            for tid in io.as_list(e.get("tests")):
                t = by_id.get(tid)
                if t and t.get("written-by") == e.get("recorded-by") and t.get("written-by") != "user":
                    warns.append(f"software change {cid}: test {tid} was written by "
                                 f"{t.get('written-by')}, the same agent that ran it for task "
                                 f"{e.get('task')} — tests should come from the test role")
                    break
    return errs, list(dict.fromkeys(warns))
