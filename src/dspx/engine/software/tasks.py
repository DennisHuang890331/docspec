"""change 的測試規劃（tests.yaml）與任務（tasks.yaml）。

tests.yaml（測試角色撰寫，類似 audit：寫測試的不是實作者）
    tests:
      - {id: T1, location: labelvault:tests/test_entry.py::test_first_row, covers: [task-entry-page/R1/S1],
         level: unit, written-by: claude, created-at: …}
    objections:                     # 實作者認為測試寫錯時提出，測試角色回應；一來一回留紀錄
      - {id: O1, test: T1, by: gpt, reason: …, at: …, resolution: open|test-fixed|rejected,
         response: …, responded-by: …, responded-at: …}

tasks.yaml（任務；完成欄位只由引擎寫入）
    tasks:
      - id: "1"
        title: …
        implements: [task-entry-page/R1]
        files: [labelvault:src/entry.py]
        verify: {methods: [test], tests: [T1], allow-skips: false}
        depends-on: ["2"]
        status: not-started          # ← 引擎寫：not-started / in-progress / done / done-waived / needs-rerun
        completed-at: …              # ← 引擎寫
        evidence: [E-claude-3]       # ← 引擎寫

檔案位置寫成 `<repo>:<路徑>`（repo 在 software/config.yaml 登記）；沒寫 repo 前綴＝專案根目錄。
"""

from __future__ import annotations

from dspx.engine.layout import Layout
from dspx.engine.software import delta as dl
from dspx.engine.software import io
from dspx.engine.software import specs as sp

TEST_LEVELS = ("unit", "integration", "browser", "real-model", "e2e")
TASK_STATUSES = ("not-started", "in-progress", "done", "done-waived", "needs-rerun")
ENGINE_TASK_FIELDS = ("status", "completed-at", "evidence", "waived-by")
TASK_FIELDS = ("id", "title", "implements", "files", "verify", "depends-on", "created-by",
               *ENGINE_TASK_FIELDS)
TEST_FIELDS = ("id", "location", "covers", "level", "written-by", "created-at", "note", "signed")
STATUS_LABEL = {"not-started": "未開始", "in-progress": "進行中", "done": "完成",
                "done-waived": "完成（含豁免）", "needs-rerun": "需重跑證據",
                "imported-done": "匯入時已完成（無證據）"}
PROJECT_REPO = "."


# ── 位置 ─────────────────────────────────────────────────────────────────

def split_location(loc: str) -> tuple[str, str]:
    """`labelvault:tests/x.py::test_y` → ("labelvault", "tests/x.py::test_y")；無前綴 → (".", loc)。"""
    loc = str(loc)
    head, sep, rest = loc.partition(":")
    if sep and rest and not rest.startswith(":") and "/" not in head and head:
        return head, rest
    return PROJECT_REPO, loc


def location_file(loc: str) -> tuple[str, str]:
    repo, path = split_location(loc)
    return repo, path.split("::", 1)[0]


def repo_known(layout: Layout, repo: str) -> bool:
    from dspx.engine.software import changes as chg
    return repo == PROJECT_REPO or repo in chg.repos(layout)


def repo_root(layout: Layout, repo: str):
    from dspx.engine.software import changes as chg
    return layout.project_root if repo == PROJECT_REPO else chg.repos(layout)[repo]


# ── 新增 ─────────────────────────────────────────────────────────────────

def _next(items: list[dict], prefix: str = "") -> str:
    nums = [int(str(x.get("id"))[len(prefix):]) for x in items
            if str(x.get("id")).startswith(prefix) and str(x.get("id"))[len(prefix):].isdigit()]
    return f"{prefix}{(max(nums) + 1) if nums else 1}"


def add_test(tests: dict, *, location: str, covers: list[str], level: str, tool: str,
             note: str | None, today: str) -> dict:
    if level not in TEST_LEVELS:
        raise io.SoftwareError(f"--level must be one of {', '.join(TEST_LEVELS)}")
    if not covers:
        raise io.SoftwareError("a planned test must cover at least one scenario (--covers cap/R1/S1)")
    for c in covers:
        _cap, rid, sid = sp.split_ref(c)
        if not rid or not sid:
            raise io.SoftwareError(f"--covers \"{c}\" must name a scenario, e.g. task-entry-page/R1/S1")
    rec = {"id": _next(tests.setdefault("tests", []), "T"), "location": location,
           "covers": covers, "level": level, "written-by": tool, "created-at": today}
    if note:
        rec["note"] = note
    tests["tests"].append(rec)
    return rec


def sign_tests(layout: Layout, ch: dict, test_ids: list[str], *, tool: str, now: str,
               fingerprint) -> list[dict]:
    """測試角色簽收：記下測試檔目前的內容指紋。只能由撰寫者（或使用者）簽；檔案必須已存在。"""
    tests = ch["tests"].get("tests") or []
    chosen = [t for t in tests if not test_ids or str(t.get("id")) in test_ids]
    missing = set(test_ids) - {str(t.get("id")) for t in tests}
    if missing:
        raise io.SoftwareError(f"no planned test(s) {', '.join(sorted(missing))}")
    if not chosen:
        raise io.SoftwareError("nothing to sign: the change has no planned tests")
    implementers = {t.get("created-by") for t in ch["tasks"].get("tasks") or []} - {None, "user"}
    for t in chosen:
        if tool != "user" and tool != t.get("written-by"):
            raise io.SoftwareError(f"test {t['id']} was written by {t.get('written-by')}; only its author "
                                   f"(the test role) or the owner signs it off")
        if tool in implementers and tool != "user":
            raise io.SoftwareError(f"{tool} created implementation tasks in this change; the test role "
                                   f"must be a different agent")
        fp = fingerprint(t["location"])
        if fp in ("missing", "unknown-repo"):
            raise io.SoftwareError(f"test {t['id']}: {t['location']} does not exist yet — write it first")
        t["signed"] = {"by": tool, "at": now, "fingerprint": fp}
    return chosen


def add_task(tasks: dict, *, title: str, implements: list[str], files: list[str],
             methods: list[str], tests: list[str], allow_skips: bool, depends_on: list[str],
             tool: str | None = None) -> dict:
    if not title.strip():
        raise io.SoftwareError("task needs --title")
    for m in methods:
        if m not in sp.VERIFICATION_METHODS:
            raise io.SoftwareError(f"--verify \"{m}\" not in {sp.VERIFICATION_METHODS}")
    if not methods:
        raise io.SoftwareError("task needs --verify (test / demonstration / inspection / analysis)")
    if "test" in methods and not tests:
        raise io.SoftwareError("a task verified by test needs --tests (planned test ids, e.g. T1,T2)")
    rec = {"id": _next(tasks.setdefault("tasks", [])), "title": title.strip()}
    if implements:
        rec["implements"] = implements
    if files:
        rec["files"] = files
    verify = {"methods": methods}
    if tests:
        verify["tests"] = tests
    if allow_skips:
        verify["allow-skips"] = True
    rec["verify"] = verify
    if depends_on:
        rec["depends-on"] = depends_on
    if tool:
        rec["created-by"] = tool
    rec["status"] = "not-started"
    tasks["tasks"].append(rec)
    return rec


def set_task(ch: dict, task_id: str, changes: dict) -> dict:
    """改任務的連結欄位（None＝不動；空清單＝拿掉）。changes 的鍵：title, implements, files, verify,
    tests, allow-skips, depends-on。"""
    t = next((x for x in ch["tasks"].get("tasks") or [] if str(x.get("id")) == str(task_id)), None)
    if t is None:
        raise io.SoftwareError(f"change {ch['id']} has no task \"{task_id}\"")
    v = t.setdefault("verify", {})
    if changes.get("title"):
        t["title"] = str(changes["title"]).strip()
    for key in ("implements", "files", "depends-on"):
        if changes.get(key) is not None:
            vals = io.as_list(changes[key])
            if vals:
                t[key] = vals
            else:
                t.pop(key, None)
    if changes.get("verify") is not None:
        methods = io.as_list(changes["verify"])
        bad = [m for m in methods if m not in sp.VERIFICATION_METHODS]
        if bad:
            raise io.SoftwareError(f"task {task_id}: unknown verification method(s) {', '.join(bad)}")
        v["methods"] = methods
    if changes.get("tests") is not None:
        v["tests"] = io.as_list(changes["tests"])
        if not v["tests"]:
            v.pop("tests")
    if changes.get("allow-skips") is not None:
        if changes["allow-skips"]:
            v["allow-skips"] = True
        else:
            v.pop("allow-skips", None)
    if "test" in io.as_list(v.get("methods")) and not v.get("tests"):
        raise io.SoftwareError(f"task {task_id}: a task verified by test needs tests (planned test ids)")
    return t


def gaps(layout: Layout, ch: dict) -> dict:
    """還缺的連結：沒有任務實作的需求、沒有規劃測試的情境、還沒填驗證方法或檔案的任務。"""
    tasks = ch["tasks"].get("tasks") or []
    changed_reqs, changed_scns = _changed_requirements(ch)
    implemented = {f"{sp.split_ref(x)[0]}/{sp.split_ref(x)[1]}" for t in tasks
                   for x in io.as_list(t.get("implements"))}
    covered = {c for t in ch["tests"].get("tests") or [] for c in io.as_list(t.get("covers"))}
    need_test = []
    for ref in sorted(changed_scns):
        cap, rid, _ = sp.split_ref(ref)
        req = _requirement_after(layout, ch, f"{cap}/{rid}") or {}
        if "test" in io.as_list(req.get("verification")) and ref not in covered:
            need_test.append(ref)
    return {"requirements-without-task": sorted(r for r in changed_reqs if r not in implemented),
            "scenarios-without-test": need_test,
            "tasks-to-complete": [t for t in tasks if t.get("status") != "imported-done"
                                  and (not io.as_list((t.get("verify") or {}).get("methods"))
                                       or not io.as_list(t.get("files")))]}


def add_objection(tests: dict, *, test_id: str, reason: str, tool: str, today: str) -> dict:
    if not any(str(t.get("id")) == test_id for t in tests.get("tests") or []):
        raise io.SoftwareError(f"no planned test \"{test_id}\"")
    if not reason.strip():
        raise io.SoftwareError("an objection needs --reason")
    rec = {"id": _next(tests.setdefault("objections", []), "O"), "test": test_id, "by": tool,
           "reason": reason.strip(), "at": today, "resolution": "open"}
    tests["objections"].append(rec)
    return rec


def respond_objection(tests: dict, *, oid: str, resolution: str, response: str, tool: str,
                      today: str) -> dict:
    if resolution not in ("test-fixed", "rejected"):
        raise io.SoftwareError("--resolution must be test-fixed or rejected")
    if not response.strip():
        raise io.SoftwareError("a response needs --reason")
    for o in tests.get("objections") or []:
        if str(o.get("id")) == oid:
            if o.get("resolution") != "open":
                raise io.SoftwareError(f"objection {oid} is already {o.get('resolution')}")
            if o.get("by") == tool and tool != "user":
                raise io.SoftwareError(f"objection {oid} was raised by {tool}; the test role (a "
                                       f"different agent) must answer it")
            o.update({"resolution": resolution, "response": response.strip(),
                      "responded-by": tool, "responded-at": today})
            return o
    raise io.SoftwareError(f"no objection \"{oid}\"")


# ── 引用檢查 ─────────────────────────────────────────────────────────────

def _changed_requirements(ch: dict) -> tuple[set[str], set[str]]:
    """(新增或修改的需求 cap/R, 新增或修改的情境 cap/R/S)。移除的不算。"""
    reqs, scns = set(), set()
    for cap, cd in ch["deltas"].items():
        for d in cd.get("deltas") or []:
            op = d.get("op")
            if op == "add-requirement":
                reqs.add(f"{cap}/{d.get('id')}")
                scns |= {f"{cap}/{d.get('id')}/{s.get('id')}" for s in d.get("scenarios") or []}
            elif op in ("modify-requirement", "rename-requirement"):
                reqs.add(f"{cap}/{d.get('ref')}")
            elif op == "add-scenario":
                reqs.add(f"{cap}/{d.get('ref')}")
                scns.add(f"{cap}/{d.get('ref')}/{d.get('id')}")
            elif op == "modify-scenario":
                reqs.add(f"{cap}/{str(d.get('ref')).split('/')[0]}")
                scns.add(f"{cap}/{d.get('ref')}")
    return reqs, scns


def _requirement_after(layout: Layout, ch: dict, ref: str) -> dict | None:
    """這個 change 套用後的需求（新增的從差異取；否則現行規格，再疊上修改）。"""
    cap, rid, _ = sp.split_ref(ref)
    cd = ch["deltas"].get(cap)
    if cd:
        for d in cd.get("deltas") or []:
            if d.get("op") == "add-requirement" and str(d.get("id")) == rid:
                return d
    req = sp.find_requirement(sp.load_spec(layout, cap), rid)
    if req is None:
        return None
    out = dict(req)
    for d in (cd or {}).get("deltas") or []:
        if d.get("op") == "modify-requirement" and d.get("ref") == rid:
            out.update({k: d[k] for k in ("title", "statement", "verification", "based-on") if k in d})
    return out


def _scenario_exists(layout: Layout, ch: dict, ref: str) -> bool:
    cap, rid, sid = sp.split_ref(ref)
    if ref in _changed_requirements(ch)[1]:
        return True
    req = sp.find_requirement(sp.load_spec(layout, cap), rid)
    return sp.find_scenario(req, sid) is not None


def validate_tasks_and_tests(layout: Layout, ch: dict) -> tuple[list[str], list[str]]:
    errs: list[str] = []
    warns: list[str] = []
    where = f"software change {ch['id']}"
    tests = ch["tests"].get("tests") or []
    tasks = ch["tasks"].get("tasks") or []
    test_ids = {str(t.get("id")) for t in tests}
    task_ids = {str(t.get("id")) for t in tasks}
    changed_reqs, changed_scns = _changed_requirements(ch)

    test_files: set[tuple[str, str]] = set()
    for t in tests:
        tw = f"{where}: test {t.get('id')}"
        for k in t:
            if k not in TEST_FIELDS:
                errs.append(f"{tw}: unknown field \"{k}\"")
        repo, path = location_file(t.get("location") or "")
        if not path:
            errs.append(f"{tw}: missing location")
        elif not repo_known(layout, repo):
            errs.append(f"{tw}: repo \"{repo}\" is not registered in software/config.yaml")
        else:
            test_files.add((repo, path))
        for c in io.as_list(t.get("covers")):
            if not _scenario_exists(layout, ch, c):
                errs.append(f"{tw}: covers nonexistent scenario \"{c}\"")

    implemented: set[str] = set()
    method_cover: dict[str, set[str]] = {}
    for t in tasks:
        tw = f"{where}: task {t.get('id')}"
        for k in t:
            if k not in TASK_FIELDS:
                errs.append(f"{tw}: unknown field \"{k}\"")
        if t.get("status") not in TASK_STATUSES and t.get("status") != "imported-done":
            errs.append(f"{tw}: bad status \"{t.get('status')}\"")
        v = t.get("verify") or {}
        methods = io.as_list(v.get("methods"))
        for x in io.as_list(v.get("tests")):
            if x not in test_ids:
                errs.append(f"{tw}: verify.tests points to unplanned test \"{x}\"")
        for ref in io.as_list(t.get("implements")):
            cap, rid, _ = sp.split_ref(ref)
            key = f"{cap}/{rid}"
            if _requirement_after(layout, ch, key) is None:
                errs.append(f"{tw}: implements nonexistent requirement \"{ref}\"")
                continue
            implemented.add(key)
            method_cover.setdefault(key, set()).update(methods)
        for f in io.as_list(t.get("files")):
            repo, path = location_file(f)
            if not repo_known(layout, repo):
                errs.append(f"{tw}: file \"{f}\" is in unregistered repo \"{repo}\"")
            elif (repo, path) in test_files:
                errs.append(f"{tw}: declares test file \"{f}\" — tests belong to the test role, "
                            f"not the implementer")
        if "test" in methods and not io.as_list(t.get("files")) and t.get("status") != "imported-done":
            warns.append(f"{tw}: declares no files, so later code changes will not send it back to "
                         f"\"needs re-run\" (`docspec code task set … --files`)")
        for dep in io.as_list(t.get("depends-on")):
            if dep not in task_ids:
                errs.append(f"{tw}: depends-on unknown task \"{dep}\"")
    errs += _task_cycles(tasks, where)

    for ref in sorted(changed_reqs):
        if ref not in implemented:
            errs.append(f"{where}: requirement {ref} is added or modified but no task implements it")
            continue
        req = _requirement_after(layout, ch, ref) or {}
        for m in io.as_list(req.get("verification")):
            if m != "test" and m not in method_cover.get(ref, set()):
                errs.append(f"{where}: requirement {ref} is verified by {m} but no implementing "
                            f"task verifies by {m}")
    covered = {c for t in tests for c in io.as_list(t.get("covers"))}
    for ref in sorted(changed_scns):
        cap, rid, _sid = sp.split_ref(ref)
        req = _requirement_after(layout, ch, f"{cap}/{rid}") or {}
        if "test" in io.as_list(req.get("verification")) and ref not in covered:
            errs.append(f"{where}: scenario {ref} is added or modified but no planned test covers it "
                        f"(the test role adds one with `docspec code testplan add`)")
    for o in ch["tests"].get("objections") or []:
        if o.get("resolution") == "open":
            warns.append(f"{where}: objection {o.get('id')} on test {o.get('test')} is open")
    return errs, warns


def _task_cycles(tasks: list[dict], where: str) -> list[str]:
    deps = {str(t.get("id")): io.as_list(t.get("depends-on")) for t in tasks}
    out, state = [], {}

    def visit(n: str, path: list[str]) -> None:
        if state.get(n) == 2:
            return
        if state.get(n) == 1:
            out.append(f"{where}: task dependency cycle {' → '.join(path + [n])}")
            return
        state[n] = 1
        for m in deps.get(n, []):
            if m in deps:
                visit(m, path + [n])
        state[n] = 2

    for n in deps:
        visit(n, [])
    return out


# ── 呈現 ─────────────────────────────────────────────────────────────────

def render_md(layout: Layout, ch: dict) -> str:
    lines = ["## Test plan"]
    for t in ch["tests"].get("tests") or []:
        lines.append(f"- {t.get('id')} [{t.get('level')}] `{t.get('location')}` covers "
                     f"{', '.join(io.as_list(t.get('covers')))} (by {t.get('written-by')})")
    if not ch["tests"].get("tests"):
        lines.append("- (none yet)")
    for o in ch["tests"].get("objections") or []:
        lines.append(f"- objection {o.get('id')} on {o.get('test')} by {o.get('by')}: {o.get('reason')} "
                     f"→ {o.get('resolution')}" + (f": {o.get('response')}" if o.get("response") else ""))
    lines += ["", "## Tasks"]
    for t in ch["tasks"].get("tasks") or []:
        st = t.get("status", "not-started")
        box = "x" if st in ("done", "done-waived", "imported-done") else " "
        v = t.get("verify") or {}
        extra = f"verify: {', '.join(io.as_list(v.get('methods')))}"
        if v.get("tests"):
            extra += f" ({', '.join(io.as_list(v.get('tests')))})"
        lines.append(f"- [{box}] {t.get('id')}. {t.get('title')} — {STATUS_LABEL.get(st, st)}; {extra}")
        if t.get("implements"):
            lines.append(f"    - implements: {', '.join(io.as_list(t['implements']))}")
    if not ch["tasks"].get("tasks"):
        lines.append("- (none yet)")
    return "\n".join(lines)


def touched_summary(ch: dict) -> list[str]:
    out = []
    for cd in ch["deltas"].values():
        out += dl.touched_refs(cd)
    return out
