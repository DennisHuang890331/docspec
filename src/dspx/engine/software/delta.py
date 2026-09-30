"""規格差異：以需求／情境編號為單位，只寫改到的部分；引擎補基準指紋、配發編號、套用與偵測衝突。

change 資料夾裡每個受影響的能力一個檔 `specs/<能力>.yaml`：
    capability: task-entry-page
    new: false                 # true＝這個 change 新增的能力（需帶 purpose，只能 add-requirement）
    purpose: …                 # new 時必填
    deltas: [ {op: …}, … ]

動作：
    add-requirement     {id, title, statement, verification, based-on?, scenarios:[{id,title,when,then}]}
    modify-requirement  {ref: R1, base, title?, statement?, verification?, based-on?}   ← 不含情境
    rename-requirement  {ref: R1, base, title}
    remove-requirement  {ref: R1, base, reason}
    add-scenario        {ref: R1, id: S3, title, when, then}
    modify-scenario     {ref: R1/S1, base, title?, when?, then?}   ← 只改這個情境
    remove-scenario     {ref: R1/S2, base, reason}

基準指紋（base）：modify/rename-requirement 用需求本身（不含情境）的指紋，情境動作用該情境的指紋，
remove-requirement 用需求含情境的全文指紋。所以兩個 change 各改同一條需求的不同情境不會衝突；
真的改到同一處時，後封存者因 base 不符而停下（不會靜默覆蓋）。
"""

from __future__ import annotations

import copy

from dspx.engine.software import io
from dspx.engine.software import specs as sp

OPS = ("add-requirement", "modify-requirement", "rename-requirement", "remove-requirement",
       "add-scenario", "modify-scenario", "remove-scenario")
_REQ_EDIT = ("title", "statement", "verification", "based-on")
_SCN_EDIT = ("title", "when", "then")
_ALLOWED = {
    "add-requirement": {"op", "id", "title", "statement", "verification", "based-on", "scenarios"},
    "modify-requirement": {"op", "ref", "base", *_REQ_EDIT},
    "rename-requirement": {"op", "ref", "base", "title"},
    "remove-requirement": {"op", "ref", "base", "reason"},
    "add-scenario": {"op", "ref", "id", "title", "when", "then"},
    "modify-scenario": {"op", "ref", "base", *_SCN_EDIT},
    "remove-scenario": {"op", "ref", "base", "reason"},
}


def _find_added_req(cap_delta: dict, rid: str) -> dict | None:
    for d in cap_delta.get("deltas") or []:
        if d.get("op") == "add-requirement" and str(d.get("id")) == rid:
            return d
    return None


def _methods(raw) -> list[str]:
    """驗證方法：寫入時就擋下不認得的值（例如 "test/inspection"），不要等到 status 才發現。"""
    out = io.as_list(raw)
    bad = [m for m in out if m not in sp.VERIFICATION_METHODS]
    if bad:
        raise io.SoftwareError(f"verification {', '.join(repr(b) for b in bad)} not one of "
                               f"{', '.join(sp.VERIFICATION_METHODS)} (several: comma-separated, e.g. "
                               f"\"test,inspection\")")
    return out


def prepare(spec: dict | None, cap_delta: dict, raw: dict, reserved: set[str] | None = None) -> dict:
    """驗證一筆差異、補基準指紋與編號，回傳正規化後的差異（尚未寫入）。

    reserved：其他進行中 change 已為同一能力預留的需求編號（降低並行撞號）。"""
    op = raw.get("op")
    if op not in OPS:
        raise io.SoftwareError(f"unknown delta op \"{op}\" (choose from {', '.join(OPS)})")
    extra = set(raw) - _ALLOWED[op] - {"base", "id"}
    if extra:
        raise io.SoftwareError(f"{op}: unknown field(s) {', '.join(sorted(extra))}")
    d = {k: v for k, v in raw.items() if v not in (None, "", [])}
    is_new = bool(cap_delta.get("new"))
    if is_new and op != "add-requirement" and op != "add-scenario":
        raise io.SoftwareError(f"{op}: a new capability only takes add-requirement / add-scenario")
    used_r, used_s = sp.used_ids(spec)
    used_r |= set(reserved or ())
    for other in cap_delta.get("deltas") or []:
        if other.get("op") == "add-requirement":
            used_r.add(str(other.get("id")))
            for s in other.get("scenarios") or []:
                used_s.add(f"{other.get('id')}/{s.get('id')}")
        if other.get("op") == "add-scenario":
            used_s.add(f"{other.get('ref')}/{other.get('id')}")

    if op == "add-requirement":
        for k in ("title", "statement", "verification"):
            if not d.get(k):
                raise io.SoftwareError(f"add-requirement needs --{k}")
        if not d.get("scenarios"):
            raise io.SoftwareError("add-requirement needs at least one scenario")
        d["id"] = f"R{sp.next_number(used_r, 'R')}"
        d["verification"] = _methods(d["verification"])
        d["scenarios"] = [{"id": f"S{i}", **{k: s.get(k) for k in _SCN_EDIT}}
                          for i, s in enumerate(d["scenarios"], 1)]
        return d

    parts = str(d.get("ref") or "").strip("/").split("/")   # 相對於能力：R1 或 R1/S2
    rid = parts[0]
    sid = parts[1] if len(parts) > 1 else None
    target_req = sp.find_requirement(spec, rid)
    added = _find_added_req(cap_delta, rid)
    if target_req is None and added is None:
        raise io.SoftwareError(f"{op}: requirement \"{rid}\" not found in {cap_delta.get('capability')}")

    if op == "add-scenario":
        for k in _SCN_EDIT:
            if not d.get(k):
                raise io.SoftwareError(f"add-scenario needs --{k}")
        d["ref"] = rid
        taken = {x.split("/", 1)[1] for x in used_s if x.startswith(rid + "/")}
        d["id"] = f"S{sp.next_number(taken, 'S')}"
        return d

    if added is not None and target_req is None:
        raise io.SoftwareError(f"{op}: \"{rid}\" is added by this change — edit the add-requirement "
                               f"entry instead")
    if op in ("modify-requirement", "rename-requirement"):
        if not any(k in d for k in (_REQ_EDIT if op == "modify-requirement" else ("title",))):
            raise io.SoftwareError(f"{op}: nothing to change")
        if "verification" in d:
            d["verification"] = _methods(d["verification"])
        d["ref"] = rid
        d["base"] = sp.requirement_head_fp(target_req)
        return d
    if op == "remove-requirement":
        if not d.get("reason"):
            raise io.SoftwareError("remove-requirement needs --reason")
        d["ref"] = rid
        d["base"] = sp.requirement_fp(target_req)
        return d
    # 情境動作
    if not sid:
        raise io.SoftwareError(f"{op}: ref must name a scenario, e.g. R1/S2")
    scn = sp.find_scenario(target_req, sid)
    if scn is None:
        raise io.SoftwareError(f"{op}: scenario \"{rid}/{sid}\" not found")
    if op == "modify-scenario" and not any(k in d for k in _SCN_EDIT):
        raise io.SoftwareError("modify-scenario: nothing to change")
    if op == "remove-scenario" and not d.get("reason"):
        raise io.SoftwareError("remove-scenario needs --reason")
    d["ref"] = f"{rid}/{sid}"
    d["base"] = sp.scenario_fp(scn)
    return d


def apply(spec: dict | None, cap_delta: dict) -> tuple[dict, list[str], dict[str, str]]:
    """把一個能力的差異套到規格副本。回 (新規格, 衝突清單, 編號重配 {舊: 新})。

    衝突＝目標不存在或基準指紋不符（規格已被別的 change 改過）。有衝突時新規格不可用。
    新增需求的編號若已被占用（並行分支先封存了同號），自動改配下一個並回報對照。"""
    cap = cap_delta.get("capability")
    if spec is None:
        if not cap_delta.get("new"):
            return {}, [f"{cap}: capability does not exist (mark the delta file new: true)"], {}
        spec = {"capability": cap, "purpose": cap_delta.get("purpose"), "requirements": []}
    elif cap_delta.get("new"):
        return {}, [f"{cap}: capability already exists; it cannot be added again"], {}
    out = copy.deepcopy(spec)
    reqs = out.setdefault("requirements", [])
    retired = out.setdefault("retired", {})
    conflicts: list[str] = []
    renames: dict[str, str] = {}
    used_r, used_s = sp.used_ids(out)

    def conflict(d: dict, why: str) -> None:
        conflicts.append(f"{cap}: {d.get('op')} {d.get('ref') or d.get('id')}: {why}")

    for d in cap_delta.get("deltas") or []:
        op = d.get("op")
        if op == "add-requirement":
            rid = str(d["id"])
            if rid in used_r:
                new = f"R{sp.next_number(used_r, 'R')}"
                renames[f"{cap}/{rid}"] = f"{cap}/{new}"
                rid = new
            used_r.add(rid)
            reqs.append({"id": rid, **{k: copy.deepcopy(d[k]) for k in
                                       ("title", "statement", "verification", "based-on", "scenarios")
                                       if k in d}})
            continue
        rid = str(d.get("ref")).split("/")[0]
        rid = renames.get(f"{cap}/{rid}", f"{cap}/{rid}").split("/")[-1]
        req = sp.find_requirement(out, rid)
        if req is None:
            conflict(d, "requirement no longer exists")
            continue
        if op in ("modify-requirement", "rename-requirement"):
            if d.get("base") and d["base"] != sp.requirement_head_fp(req):
                conflict(d, "the requirement changed since this delta was written")
                continue
            for k in _REQ_EDIT:
                if k in d:
                    req[k] = copy.deepcopy(d[k])
        elif op == "remove-requirement":
            if d.get("base") and d["base"] != sp.requirement_fp(req):
                conflict(d, "the requirement changed since this delta was written")
                continue
            reqs.remove(req)
            retired.setdefault("requirements", []).append(rid)
        elif op == "add-scenario":
            sid = str(d["id"])
            taken = {x.split("/", 1)[1] for x in used_s if x.startswith(rid + "/")}
            if sid in taken:
                new = f"S{sp.next_number(taken, 'S')}"
                renames[f"{cap}/{rid}/{sid}"] = f"{cap}/{rid}/{new}"
                sid = new
            used_s.add(f"{rid}/{sid}")
            req.setdefault("scenarios", []).append({"id": sid, **{k: d[k] for k in _SCN_EDIT}})
        else:
            sid = str(d.get("ref")).split("/")[1]
            scn = sp.find_scenario(req, sid)
            if scn is None:
                conflict(d, "scenario no longer exists")
                continue
            if d.get("base") and d["base"] != sp.scenario_fp(scn):
                conflict(d, "the scenario changed since this delta was written")
                continue
            if op == "modify-scenario":
                for k in _SCN_EDIT:
                    if k in d:
                        scn[k] = d[k]
            else:
                req["scenarios"].remove(scn)
                retired.setdefault("scenarios", []).append(f"{rid}/{sid}")
    if not retired.get("requirements") and not retired.get("scenarios"):
        out.pop("retired", None)
    return out, conflicts, renames


def touched_refs(cap_delta: dict) -> list[str]:
    """這個能力差異碰到的需求與情境（`<能力>/R1`、`<能力>/R1/S2`）。"""
    cap = cap_delta.get("capability")
    out = []
    for d in cap_delta.get("deltas") or []:
        if d.get("op") == "add-requirement":
            out.append(f"{cap}/{d.get('id')}")
            out += [f"{cap}/{d.get('id')}/{s.get('id')}" for s in d.get("scenarios") or []]
        elif d.get("op") == "add-scenario":
            out.append(f"{cap}/{d.get('ref')}/{d.get('id')}")
        else:
            out.append(f"{cap}/{d.get('ref')}")
    return out
