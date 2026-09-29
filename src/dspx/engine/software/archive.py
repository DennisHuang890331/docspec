"""封存（收尾）：把 change 的規格差異併回正式規格，資料夾收進 `changes/_archive/<日期>-<id>/`，寫一筆基線。

順序（交易式：先全部算好、檢查過，才開始寫；寫到一半失敗就還原）：
    1. 依證據刷新任務狀態
    2. 嚴格檢查（草稿決策、基準指紋不符、前置 change 未封存都算錯）
    3. 完整性：任務都完成或豁免；需要人看的需求（檢查／展示）要有使用者驗收或豁免
    4. 在副本上套用差異，併入「情境 ← 測試」（verified-by），驗證新規格
    5. 寫規格 → 寫基線 → 搬資料夾
"""

from __future__ import annotations

import datetime
import shutil

from dspx.engine import governance as gv
from dspx.engine.layout import Layout
from dspx.engine.software import changes as chg
from dspx.engine.software import evidence as ev
from dspx.engine.software import io
from dspx.engine.software import specs as sp
from dspx.engine.software import tasks as tk

DONE = ("done", "done-waived", "imported-done")
HUMAN_METHODS = ("inspection", "demonstration")


def _rename(ref: str, renames: dict[str, str]) -> str:
    """把 `cap/R3/S1` 依封存時的編號重配改寫。"""
    cap, rid, sid = sp.split_ref(ref)
    req = renames.get(f"{cap}/{rid}", f"{cap}/{rid}")
    if sid:
        full = f"{req}/{sid}"
        return renames.get(f"{cap}/{rid}/{sid}", full)
    return req


def blockers(layout: Layout, ch: dict, evs: list[dict]) -> list[str]:
    """封存前的完整性問題（不含格式／引用，那部分由 validate_change 負責）。"""
    out = []
    cid = ch["id"]
    tasks = ch["tasks"].get("tasks") or []
    if not tasks and ch["deltas"]:
        out.append(f"change {cid} has spec deltas but no tasks")
    for t in tasks:
        status, _support, why = ev.derive(layout, ch, t, ev.for_task(evs, cid, t["id"]))
        if status not in DONE:
            out.append(f"task {t['id']} ({t.get('title')}) is {tk.STATUS_LABEL.get(status, status)}: {why}")
    # 需要人看的需求：實作它的任務之中，至少一個有使用者驗收或豁免
    changed_reqs, _ = tk._changed_requirements(ch)
    for ref in sorted(changed_reqs):
        req = tk._requirement_after(layout, ch, ref) or {}
        if not set(io.as_list(req.get("verification"))) & set(HUMAN_METHODS):
            continue
        implementers = [t for t in tasks if any(
            f"{sp.split_ref(x)[0]}/{sp.split_ref(x)[1]}" == ref for x in io.as_list(t.get("implements")))]
        ok = any(e.get("type") in ("acceptance", "waiver")
                 for t in implementers for e in ev.for_task(evs, cid, t["id"]))
        if not ok:
            out.append(f"requirement {ref} is verified by "
                       f"{'/'.join(m for m in io.as_list(req.get('verification')) if m in HUMAN_METHODS)}"
                       f" and needs the owner's acceptance (`docspec code evidence accept`) or a waiver")
    return out


def plan(layout: Layout, cid: str) -> dict:
    """算出封存結果但不寫入。回 {ok, errors, warnings, specs, renames, affected, …}。"""
    ev.refresh(layout, cid)
    ch = chg.load_change(layout, cid)
    evs = ev.load_all(layout)
    errors, warnings = chg.validate_change(layout, ch, strict=True)
    errors += blockers(layout, ch, evs)
    new_specs, _conflicts, renames = chg.preview_specs(layout, ch)   # 衝突已在嚴格檢查裡

    # 被修改的情境：舊的 verified-by 不再保證新行為 → 改由這次規劃的測試接手（舊的列出來給測試角色確認）
    dropped: list[dict] = []
    for cap, cd in ch["deltas"].items():
        for x in cd.get("deltas") or []:
            if x.get("op") != "modify-scenario" or not ({"when", "then"} & set(x)) or cap not in new_specs:
                continue
            ref = _rename(f"{cap}/{x['ref']}", renames)
            _c, rid, sid = sp.split_ref(ref)
            scn = sp.find_scenario(sp.find_requirement(new_specs[cap], rid), sid)
            if scn is not None and scn.get("verified-by"):
                dropped.append({"scenario": ref, "tests": io.as_list(scn.pop("verified-by"))})

    # 併入「情境 ← 測試」（verified-by），依編號重配改寫引用；測到既有能力也一併記上
    for t in ch["tests"].get("tests") or []:
        for ref in io.as_list(t.get("covers")):
            cap, rid, sid = sp.split_ref(_rename(ref, renames))
            if cap not in new_specs:
                if cap in ch["deltas"]:
                    continue                                 # 有衝突的能力：不動
                current = sp.load_spec(layout, cap)
                if current is None:
                    continue
                new_specs[cap] = current
            scn = sp.find_scenario(sp.find_requirement(new_specs[cap], rid), sid)
            if scn is not None and t["location"] not in io.as_list(scn.get("verified-by")):
                scn["verified-by"] = io.as_list(scn.get("verified-by")) + [t["location"]]

    # 其他進行中 change 若也改這些能力，封存後它們的基準指紋可能對不上 → 列出來
    affected = []
    for other in chg.list_active(layout):
        if other == cid:
            continue
        oc = chg.load_change(layout, other)
        if set(oc["deltas"]) & set(new_specs):
            affected.append(other)
    tasks = ch["tasks"].get("tasks") or []
    def now_verifying(ref: str) -> list[str]:
        c, rid, sid = sp.split_ref(ref)
        return io.as_list(sp.find_scenario(sp.find_requirement(new_specs[c], rid), sid).get("verified-by"))

    # 這次又規劃了同一個測試的，不算被拿掉
    dropped = [{"scenario": d["scenario"],
                "tests": [x for x in d["tests"] if x not in now_verifying(d["scenario"])]} for d in dropped]
    dropped = [d for d in dropped if d["tests"]]
    return {"change": cid, "ok": not errors, "dropped-verified-by": dropped, "errors": errors, "warnings": warnings,
            "specs": new_specs, "renames": renames, "affected": affected, "ch": ch,
            "evidence": sorted({e for t in tasks for e in io.as_list(t.get("evidence"))}),
            "tasks": {s: sum(1 for t in tasks if t.get("status") == s) for s in DONE}}


def archive(layout: Layout, cid: str, *, tool: str) -> dict:
    p = plan(layout, cid)
    if not p["ok"]:
        raise io.SoftwareError(f"cannot archive {cid}:\n  - " + "\n  - ".join(p["errors"]))
    date = datetime.date.today().isoformat()
    dest = io.archive_dir(layout) / f"{date}-{cid}"
    if dest.exists():
        raise io.SoftwareError(f"{dest} already exists")

    repos = {"project": ev._git(layout.project_root, "rev-parse", "HEAD")}
    for name, root in chg.repos(layout).items():
        repos[name] = ev._git(root, "rev-parse", "HEAD") if root.is_dir() else None
    baseline = {"change": cid, "archived-at": gv.today(), "archived-by": tool,
                "folder": f"changes/{io.ARCHIVE_DIR}/{dest.name}",
                "specs": {cap: io.fingerprint(spec) for cap, spec in sorted(p["specs"].items())},
                "repos": {k: v for k, v in repos.items() if v},
                "evidence": p["evidence"], "tasks": {k: v for k, v in p["tasks"].items() if v}}
    if p["renames"]:
        baseline["renames"] = p["renames"]
    if p["dropped-verified-by"]:
        baseline["dropped-verified-by"] = p["dropped-verified-by"]
    baseline_path = io.baselines_dir(layout) / f"{date}-{cid}.yaml"

    # 交易：記下舊內容，失敗就還原
    backups = {}
    for cap in p["specs"]:
        path = io.spec_path(layout, cap)
        backups[path] = path.read_bytes() if path.is_file() else None
    try:
        for spec in p["specs"].values():
            sp.write_spec(layout, spec)
        io.write(baseline_path, "baseline", baseline)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(io.change_dir(layout, cid)), str(dest))
    except BaseException:
        for path, data in backups.items():
            if data is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(data)
        baseline_path.unlink(missing_ok=True)
        if dest.exists() and not io.change_dir(layout, cid).exists():
            shutil.move(str(dest), str(io.change_dir(layout, cid)))
        raise
    from dspx.engine.software.links import clear_requirement_suspects
    cleared = clear_requirement_suspects(layout, cid, p["ch"], tool)
    return {**p, "baseline": baseline, "dest": dest, "cleared-suspects": cleared}


# ── 回歸測試：依正式規格的 verified-by ────────────────────────────────────

def regression_list(layout: Layout, capability: str | None = None) -> dict[str, list[dict]]:
    """repo → [{location, scenario}]（同一個測試驗證多個情境時合併）。"""
    out: dict[str, dict[str, list[str]]] = {}
    for cap, spec in sp.load_all(layout).items():
        if capability and cap != capability:
            continue
        for r in spec.get("requirements") or []:
            for s in r.get("scenarios") or []:
                for loc in io.as_list(s.get("verified-by")):
                    repo, _path = tk.split_location(loc)
                    out.setdefault(repo, {}).setdefault(loc, []).append(f"{cap}/{r['id']}/{s['id']}")
    return {repo: [{"location": loc, "scenarios": scns} for loc, scns in sorted(locs.items())]
            for repo, locs in sorted(out.items())}


def run_regression(layout: Layout, capability: str | None = None, timeout: int = 3600) -> list[dict]:
    """每個 repo 跑一次；回 [{repo, command, exit, counts, failing: [{location, scenarios, outcome}]}]。"""
    import shlex
    import subprocess
    import tempfile
    from pathlib import Path

    results = []
    for repo, items in regression_list(layout, capability).items():
        if not tk.repo_known(layout, repo):
            results.append({"repo": repo, "error": "repo not registered in software/config.yaml"})
            continue
        base = (chg.repo_settings(layout).get(repo) or {}).get("test-command") or "python -m pytest"
        command = shlex.split(str(base)) + [tk.split_location(i["location"])[1] for i in items]
        with tempfile.TemporaryDirectory() as tmp:
            junit = Path(tmp) / "junit.xml"
            try:
                proc = subprocess.run(command + [f"--junitxml={junit}"], cwd=tk.repo_root(layout, repo),
                                      capture_output=True, text=True, timeout=timeout)
                code = proc.returncode
            except (OSError, subprocess.TimeoutExpired) as exc:
                results.append({"repo": repo, "command": shlex.join(command), "error": str(exc)})
                continue
            cases = ev._parse_junit(junit) if junit.is_file() else []
        failing = []
        for i in items:
            hit = [c for c in cases if ev._matches(i["location"], c)]
            outcome = ("not-run" if not hit else "failed" if any(c["outcome"] == "failed" for c in hit)
                       else "skipped" if all(c["outcome"] == "skipped" for c in hit) else "passed")
            if outcome != "passed":
                failing.append({**i, "outcome": outcome})
        counts = {k: sum(1 for c in cases if c["outcome"] == k) for k in ("passed", "failed", "skipped")}
        results.append({"repo": repo, "command": shlex.join(command), "exit": code, "counts": counts,
                        "failing": failing})
    return results


def validate_verified_by(layout: Layout) -> tuple[list[str], list[str]]:
    """正式規格引用的測試檔還在不在（測試檔刪除或改名＝引用斷了）。"""
    errs, warns = [], []
    for repo, items in regression_list(layout).items():
        if not tk.repo_known(layout, repo):
            errs.append(f"specs: verified-by uses unregistered repo \"{repo}\"")
            continue
        root = tk.repo_root(layout, repo)
        if not root.is_dir():
            warns.append(f"specs: repo \"{repo}\" is not checked out at {root}; verified-by not checked")
            continue
        for i in items:
            _r, path = tk.location_file(i["location"])
            if not (root / path).is_file():
                errs.append(f"specs: {', '.join(i['scenarios'])} verified-by {i['location']} — "
                            f"test file is missing (deleted or renamed?)")
    return errs, warns
