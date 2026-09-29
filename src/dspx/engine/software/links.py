"""軟體領域與治理層、文件樹的連結（第二期 P2-5）。

參照字串（與治理層的 `gov:`、文件的 `doc:` 並列）：
    swc:<change>              軟體 change（roadmap 工作項目用它當完成條件：封存＝完成）
    req:<能力>/R1             需求（文件章節可 realizes 它；需求改了，章節轉 stale-upstream）
    req:<能力>/R1/S2          情境
    task:<change>#<n>         任務（只在追溯圖裡出現）
    test:<change>/T1          規劃測試（只在追溯圖裡出現）

追溯圖的邊（只收進行中的 change；封存後的歷史不再是下游）：
    swc  ─based-on→ gov:D     （design.decisions、差異的 based-on）
    swc  ─modifies→ req
    req  ─based-on→ gov:D     （正式規格裡需求的 based-on）
    task ─implements→ req
    test ─covers→ req/S
所以決策被取代或撤回時，影響分析會替「依據它的 change 和需求」建立可疑標記。
"""

from __future__ import annotations

from dspx.engine.layout import Layout
from dspx.engine.software import changes as chg
from dspx.engine.software import io
from dspx.engine.software import specs as sp

SWC_NS = "swc:"
REQ_NS = "req:"


def requirement_index_entries(layout: Layout) -> dict:
    """正式規格的需求 → 文件引擎 decision_index 的外部條目（鍵帶 `req:`）。

    statement 用需求的正規化全文（含情境），所以需求被修改＝realizes 它的文件章節 deps 指紋改變
    ＝stale-upstream。已退役的需求標 deprecated（check 會要求改指向或拿掉）。"""
    if not io.has_software(layout):
        return {}
    out: dict = {}
    try:
        specs = sp.load_all(layout)
    except io.SoftwareError:
        return {}           # 壞封條由 check ⑭ 回報
    for cap, spec in specs.items():
        for r in spec.get("requirements") or []:
            out[f"{REQ_NS}{cap}/{r['id']}"] = {"section": None, "statement": sp.requirement_text(r),
                                               "kind": "decision", "status": "accepted",
                                               "superseded_by": None}
        for rid in io.as_list((spec.get("retired") or {}).get("requirements")):
            out[f"{REQ_NS}{cap}/{rid}"] = {"section": None, "statement": None, "kind": "decision",
                                           "status": "deprecated", "superseded_by": None}
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
    for ch in active:
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
