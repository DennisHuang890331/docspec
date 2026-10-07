"""軟體領域與治理層、文件樹的連結（第二期 P2-5）。

參照字串（與治理層的 `gov:`、文件的 `doc:` 並列）：
    swc:<change>              軟體 change（roadmap 工作項目用它當完成條件：封存＝完成）
    req:<能力>/R1             需求（文件章節可 realizes 它；需求改了，章節轉 stale-upstream）
    req:<能力>/R1/S2          情境
    draft-req:<change>/<能力>/R1  指定 change 的需求，封存後沿 sealed baseline 追查
    task:<change>#<n>         任務（只在追溯圖裡出現）
    test:<change>/T1          規劃測試（只在追溯圖裡出現）

追溯圖的邊（含封存歷史供影響審閱；歷史只標需重看，不重開）：
    swc  ─based-on→ gov:D     （design.decisions、差異的 based-on）
    swc  ─modifies→ req
    req  ─based-on→ gov:D     （正式規格裡需求的 based-on）
    task ─implements→ req
    test ─covers→ req/S
所以決策被取代或撤回時，影響分析會替「依據它的 change 和需求」建立可疑標記。
"""

from __future__ import annotations

import re
from pathlib import Path

from dspx.engine.layout import Layout
from dspx.engine.software import changes as chg
from dspx.engine.software import delta as dl
from dspx.engine.software import io
from dspx.engine.software import specs as sp

SWC_NS = "swc:"
REQ_NS = "req:"
DRAFT_REQ_NS = "draft-req:"
SOURCE_KIND = "software-requirement"


def is_requirement_source(ref: str, record: dict | None = None) -> bool:
    """Recognize software provenance even when its record cannot be resolved."""
    return ((record or {}).get("source-kind") == SOURCE_KIND
            or str(ref).startswith((REQ_NS, DRAFT_REQ_NS)))


def _source_fingerprint(requirement: dict) -> str:
    """Semantic source scope: descriptive titles and verification locators are not rules."""
    return io.fingerprint({
        "statement": requirement.get("statement"),
        "verification": sorted(io.as_list(requirement.get("verification"))),
        "based-on": sorted(io.as_list(requirement.get("based-on"))),
        "scenarios": [{k: scenario.get(k) for k in ("id", "when", "then")}
                      for scenario in requirement.get("scenarios") or []],
    })


def _source_result(ref: str) -> dict:
    return {"original-ref": ref, "source-kind": SOURCE_KIND, "state": "unresolved",
            "source-ref": None, "change": None, "baseline": None, "statement": None,
            "fingerprint": None, "based-on": [], "diagnostics": []}


def _source_problem(result: dict, state: str, reason: str) -> dict:
    result.update({"state": state, "statement": None, "fingerprint": None})
    result["diagnostics"].append(f"{result['original-ref']}: {reason}")
    return result


def _resolve_spec_source(result: dict, spec: dict | None, cap: str, rid: str,
                         state: str, source_ref: str) -> dict:
    result["source-ref"] = source_ref
    if spec is not None and (not isinstance(spec, dict) or spec.get("capability") != cap):
        return _source_problem(result, "unknown", f"specification identity does not match capability {cap}")
    requirement = sp.find_requirement(spec, rid)
    if requirement is None:
        retired = io.as_list(((spec or {}).get("retired") or {}).get("requirements"))
        return _source_problem(result, "retired" if rid in retired else "unresolved",
                               f"requirement {source_ref} is " + ("retired" if rid in retired else "missing"))
    result.update({"state": state, "statement": sp.requirement_text(requirement),
                   "fingerprint": _source_fingerprint(requirement),
                   "based-on": io.as_list(requirement.get("based-on"))})
    return result


def resolve_requirement_source(layout: Layout, ref: str) -> dict:
    """Read one explicit requirement source without adopting or rewriting its reference.

    A sealed archive baseline proves landing; a current same-number requirement
    alone does not. Later formal changes remain visible after that proof.
    """
    ref = str(ref)
    result = _source_result(ref)

    def problem(state: str, reason: str) -> dict:
        return _source_problem(result, state, reason)

    def finish(spec: dict | None, cap: str, rid: str, state: str, source_ref: str) -> dict:
        return _resolve_spec_source(result, spec, cap, rid, state, source_ref)

    draft = ref.startswith(DRAFT_REQ_NS)
    if not draft and not ref.startswith(REQ_NS):
        return problem("unresolved", "not a software requirement reference")
    raw = ref[len(DRAFT_REQ_NS if draft else REQ_NS):]
    if draft:
        cid, separator, raw = raw.partition("/")
        result["change"] = cid
        if not separator or chg.validate_id(cid):
            return problem("unresolved", "invalid draft change identity")
    cap, rid, sid = sp.split_ref(raw)
    if (not cap or not rid or sid or "\\" in cap or ":" in cap
            or any(part in ("", ".", "..") for part in cap.split("/"))):
        return problem("unresolved", "expected a requirement-level reference; unsafe paths and scenarios are unsupported")
    try:
        if not draft:
            return finish(sp.load_spec(layout, cap), cap, rid, "formal", REQ_NS + raw)
        state = chg.change_state(layout, cid)
        if state is None:
            return problem("unresolved", f"software change {cid} does not exist or is not active/archived")
        change = chg.load_change(layout, cid) if state == "active" else chg.load_archived(layout, cid)
        cap_delta = change["deltas"].get(cap)
        if cap_delta is None or not any(sp.split_ref(touched)[1] == rid
                                        for touched in dl.touched_refs(cap_delta)):
            return problem("unresolved", f"software change {cid} does not change {cap}/{rid}")
        if state == "active":
            projected, conflicts, renames = chg.preview_specs(layout, change)
            if conflicts:
                return problem("base-conflict", "; ".join(conflicts))
            landed = renames.get(f"{cap}/{rid}", f"{cap}/{rid}")
            target_cap, target_rid, _ = sp.split_ref(landed)
            return finish(projected.get(target_cap), target_cap, target_rid, "draft",
                          f"{DRAFT_REQ_NS}{cid}/{landed}")

        # Read candidate baselines once. Do not ignore a corrupt candidate or
        # choose among duplicate proofs, including copies with another filename.
        candidates = []
        for path in sorted(io.baselines_dir(layout).glob("*.yaml")):
            candidate_name = bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}-" + re.escape(cid), path.stem))
            try:
                body = io.load(path, "baseline")
            except (io.SoftwareError, OSError, UnicodeError):
                if candidate_name:
                    raise
                continue
            if candidate_name or (isinstance(body, dict) and body.get("change") == cid):
                candidates.append((path, body))
        if len(candidates) != 1:
            return problem("unknown", f"expected one sealed landing baseline for {cid}; found {len(candidates)}")
        path, baseline = candidates[0]
        result["baseline"] = path.relative_to(layout.project_root).as_posix()
        baseline_specs = baseline.get("specs") if isinstance(baseline, dict) else None
        if (not isinstance(baseline, dict) or baseline.get("change") != cid
                or Path(str(baseline.get("folder") or "")).name != change["folder"].name
                or not isinstance(baseline_specs, dict)
                or not re.fullmatch(r"sha256:[0-9a-f]{16}", str(baseline_specs.get(cap) or ""))):
            return problem("unknown", "sealed baseline cannot prove this change, archive container and capability landed")
        renames = baseline.get("renames") or {}
        if not isinstance(renames, dict):
            return problem("unknown", "sealed baseline has an unreadable requirement landing mapping")
        landed = renames.get(f"{cap}/{rid}", f"{cap}/{rid}")
        target_cap, target_rid, target_sid = sp.split_ref(landed)
        if target_cap != cap or not target_rid or target_sid:
            return problem("unknown", "sealed baseline has an invalid requirement landing mapping")
        return finish(sp.load_spec(layout, target_cap), target_cap, target_rid, "formal", REQ_NS + landed)
    except (io.SoftwareError, OSError, UnicodeError, TypeError, ValueError, KeyError, AttributeError) as exc:
        return problem("unknown", f"requirement source cannot be read: {exc}")


def requirement_index_entries(layout: Layout, references=()) -> dict:
    """正式需求及明確引用的草稿 → 文件引擎 decision_index 的軟體來源。

    statement 用需求的正規化全文（含情境），所以需求被修改＝realizes 它的文件章節 deps 指紋改變
    ＝stale-software。正式 req: 保留舊指紋，草稿另帶規則指紋與來源診斷。
    已退役的正式需求仍標 deprecated；兩類來源都不屬文件硬依賴。"""
    out: dict = {}
    try:
        specs = sp.load_all(layout) if io.has_software(layout) else {}
    except io.SoftwareError:
        specs = {}           # 壞封條由 check ⑭ 回報；明確草稿仍需個別診斷
    for cap, spec in specs.items():
        for r in spec.get("requirements") or []:
            ref = f"{REQ_NS}{cap}/{r['id']}"
            source = _resolve_spec_source(_source_result(ref), spec, cap, r["id"], "formal", ref)
            out[ref] = {"section": None, "statement": sp.requirement_text(r),
                                               "kind": "decision", "status": "accepted",
                                               "superseded_by": None, "source-kind": SOURCE_KIND,
                                               "source": source}
        for rid in io.as_list((spec.get("retired") or {}).get("requirements")):
            ref = f"{REQ_NS}{cap}/{rid}"
            source = _resolve_spec_source(_source_result(ref), spec, cap, rid, "formal", ref)
            out[ref] = {"section": None, "statement": None, "kind": "decision",
                                           "status": "deprecated", "superseded_by": None,
                                           "source-kind": SOURCE_KIND, "source": source}
    for ref in dict.fromkeys(str(r) for r in references if str(r).startswith(DRAFT_REQ_NS)):
        source = resolve_requirement_source(layout, ref)
        out[ref] = {"section": None, "statement": source["statement"], "kind": "decision",
                    "status": "accepted" if source["state"] in ("draft", "formal") else source["state"],
                    "superseded_by": None, "source-kind": SOURCE_KIND, "source": source}
    return out


def _gov(ref: str) -> str:
    return ref[len("gov:"):] if str(ref).startswith("gov:") else str(ref)


def add_to_graph(layout: Layout, g) -> None:
    """把軟體節點與邊加進治理層的追溯圖（impact.TraceGraph）。"""
    if not io.has_software(layout):
        return
    try:
        specs = sp.load_all(layout)
        active = [chg.load_change(layout, c) for c in chg.list_active(layout)]
    except io.SoftwareError:
        return
    for cap, spec in specs.items():
        for r in spec.get("requirements") or []:
            for d in io.as_list(r.get("based-on")):
                g.add(f"{REQ_NS}{cap}/{r['id']}", "based-on", _gov(d))
    history = []
    for cid in chg.archived_ids(layout):
        try:
            history.append(chg.load_archived(layout, cid))
        except io.SoftwareError:
            continue  # Broken historical seals are reported by software validation.
    for ch in [*active, *history]:
        node = SWC_NS + ch["id"]
        for d in io.as_list(ch["design"].get("decisions")):
            g.add(node, "based-on", _gov(d))
        for cap, cd in ch["deltas"].items():
            for x in cd.get("deltas") or []:
                for d in io.as_list(x.get("based-on")):
                    g.add(node, "based-on", _gov(d))
                ref = x.get("ref") or x.get("id")
                g.add(node, "modifies", f"{REQ_NS}{cap}/{str(ref).split('/')[0]}")
        for dep in io.as_list(ch["proposal"].get("depends-on")):
            g.add(node, "depends-on", SWC_NS + dep)
        for t in ch["tasks"].get("tasks") or []:
            for ref in io.as_list(t.get("implements")):
                cap, rid, _ = sp.split_ref(ref)
                g.add(f"task:{ch['id']}#{t['id']}", "implements", f"{REQ_NS}{cap}/{rid}")
        for t in ch["tests"].get("tests") or []:
            for ref in io.as_list(t.get("covers")):
                g.add(f"test:{ch['id']}/{t['id']}", "covers", REQ_NS + ref)


def open_suspects(layout: Layout, target: str) -> list[dict]:
    from dspx.engine import governance as gv
    if not gv.has_governance(layout):
        return []
    try:
        gov = gv.load_governance(layout)
    except gv.GovernanceError:
        return []
    return [s for s in gov.suspects if s.get("status") == "open" and str(s.get("target")) == target]


def clear_requirement_suspects(layout: Layout, cid: str, ch: dict, tool: str) -> list[str]:
    """封存時：這個 change 改寫了需求的依據（based-on 不再含觸發的舊決策）→ 自動清除該需求的標記。"""
    from dspx.engine import governance as gv
    if not gv.has_governance(layout):
        return []
    gov = gv.load_governance(layout)
    new_basis: dict[str, set[str]] = {}
    for cap, cd in ch["deltas"].items():
        for x in cd.get("deltas") or []:
            if x.get("op") in ("modify-requirement", "add-requirement") and "based-on" in x:
                ref = x.get("ref") or x.get("id")
                new_basis[f"{REQ_NS}{cap}/{ref}"] = {_gov(d) for d in io.as_list(x.get("based-on"))}
            if x.get("op") == "remove-requirement":
                new_basis[f"{REQ_NS}{cap}/{x.get('ref')}"] = set()
    cleared = []
    for s in gov.suspects:
        tgt = str(s.get("target"))
        if s.get("status") == "open" and tgt in new_basis and str(s.get("trigger")) not in new_basis[tgt]:
            rec = {k: v for k, v in s.items() if not k.startswith("_")}
            rec.update({"status": "cleared", "cleared-by": tool, "cleared-at": gv.today(),
                        "cleared-reason": f"requirement rewritten by software change {cid}"})
            gv.write_record(layout, "suspect", rec)
            cleared.append(str(s["id"]))
    return cleared


def requirement_downstream(layout: Layout, req_ref: str, graph) -> list[tuple[str, str]]:
    """需求被標記後，順著鏈再往下：驗證它的測試、實作它的任務（含已封存＝只標需重看、不重開）、
    realizes 它的文件章節。回 [(節點, 連結型別)]。"""
    cap, rid, _ = sp.split_ref(req_ref)
    out: list[tuple[str, str]] = []
    spec = sp.load_spec(layout, cap) if io.has_software(layout) else None
    req = sp.find_requirement(spec, rid)
    for s in (req or {}).get("scenarios") or []:
        for loc in io.as_list(s.get("verified-by")):
            node = f"test:{loc}"
            if (node, "verifies") not in out:
                out.append((node, "verifies"))
    for node, etype in graph.dependents(req_ref):
        if etype in ("implements", "realizes") and (node, etype) not in out:
            out.append((node, etype))
    for cid in chg.archived_ids(layout):
        try:
            hist = chg.load_archived(layout, cid)
        except io.SoftwareError:
            continue
        for t in hist["tasks"].get("tasks") or []:
            if any(f"{sp.split_ref(x)[0]}/{sp.split_ref(x)[1]}" == f"{cap}/{rid}"
                   for x in io.as_list(t.get("implements"))):
                out.append((f"task:{cid}#{t['id']}", "implements"))
    return out
