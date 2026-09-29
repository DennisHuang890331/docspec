"""追溯圖與影響分析（第一期：治理層＋文件章節）。

- **追溯圖**每次執行時從紀錄重建，不另存索引（SR1）。節點以參照字串表示：治理紀錄用 id
  （`D-claude-13`），文件章節用 `doc:<section path>`。邊有型別：
    answers（裁定→問題）、based-on（決策→裁定）、supersedes（新→舊）、
    realizes（文件章節→治理決策，沿用 concept.realizes 的 `gov:` 條目）。
- **影響分析**：一條裁定被駁回／取代、或一條決策被取代／撤回時，找出依賴它的下游：
    - 治理紀錄（例：依據該裁定的決策）→ 建立「可疑標記」（suspects/），附理由才能清除。
    - 文件章節 → 不另建標記，沿用文件引擎既有的 staleness（上游決策狀態變＝deps 指紋變＝
      stale-upstream）；影響檢視仍列出它們，處理方式是審閱後把 realizes 改指向接替的決策。
  已完成的項目只標「需重看」，不重新打開。
- 軟體領域（第二期）：進行中的 change（`swc:`）與正式規格的需求（`req:`）依據決策時也是下游，
  一樣建立可疑標記；節點與邊見 `engine/software/links.py`。
- 完整性只相對於「已記錄的連結」（SR7）；忘了建的連結看不見，由 check 的強制規則補。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dspx.engine import governance as gv
from dspx.engine.layout import Layout

DOC_NS = "doc:"


@dataclass
class TraceGraph:
    edges: list[tuple[str, str, str]] = field(default_factory=list)   # (from, type, to)

    def add(self, src: str, etype: str, dst: str) -> None:
        self.edges.append((src, etype, dst))

    def downstream(self, ref: str) -> list[tuple[str, str]]:
        """直接依賴 ref 的節點：(節點, 連結型別)。"""
        return [(s, t) for (s, t, d) in self.edges if d == ref and t in ("based-on", "realizes", "refs")]

    def upstream(self, ref: str) -> list[tuple[str, str]]:
        return [(d, t) for (s, t, d) in self.edges if s == ref]

    def dependents(self, ref: str) -> list[tuple[str, str]]:
        return [(s, t) for (s, t, d) in self.edges if d == ref]


def build_graph(layout: Layout, leaves: list | None = None,
                gov: gv.Governance | None = None) -> TraceGraph:
    g = TraceGraph()
    gov = gov or gv.load_governance(layout)
    for r in gov.rulings:
        for q in gv._as_list(r.get("answers")):
            g.add(str(r["id"]), "answers", q)
        for old in gv._as_list(r.get("supersedes")):
            g.add(str(r["id"]), "supersedes", old)
    for d in gov.decisions:
        for r in gv._as_list(d.get("based-on")):
            g.add(str(d["id"]), "based-on", r)
        for old in gv._as_list(d.get("supersedes")):
            g.add(str(d["id"]), "supersedes", old)
    for w in gov.work:
        for ref in gv._as_list(w.get("refs")):
            if ref.startswith(gv.GOV_NAMESPACE):
                g.add(str(w["id"]), "refs", gv.strip_ns(ref))
            elif ref.startswith(DOC_NS):
                g.add(str(w["id"]), "refs", ref)
        for dep in gv._as_list(w.get("depends-on")):
            g.add(str(w["id"]), "depends-on", dep)
        for wv in (w.get("waivers") or []):
            if isinstance(wv, dict) and wv.get("ruling"):
                g.add(str(w["id"]), "based-on", str(wv["ruling"]))
    if leaves is None:
        from dspx.engine.model import load_project
        leaves = load_project(layout)
    for leaf in leaves:
        if not leaf.concept:
            continue
        for t in (leaf.concept.get("realizes") or []):
            t = str(t)
            if t.startswith(gv.GOV_NAMESPACE):
                g.add(DOC_NS + leaf.section, "realizes", gv.strip_ns(t))
            elif t.startswith("req:"):
                g.add(DOC_NS + leaf.section, "realizes", t)
    for w in gov.work:
        for ref in gv._as_list(w.get("refs")):
            if ref.startswith("swc:"):
                g.add(str(w["id"]), "refs", ref)
    from dspx.engine.software.links import add_to_graph
    add_to_graph(layout, g)
    return g


def _open_suspect_keys(gov: gv.Governance) -> set[tuple[str, str]]:
    return {(str(s.get("trigger")), str(s.get("target"))) for s in gov.suspects
            if s.get("status") == "open"}


def flag_after_change(layout: Layout, changed_id: str, tool: str | None = None,
                      leaves: list | None = None) -> list[str]:
    """changed_id（被取代／撤回的決策，或被駁回／取代的裁定所屬的新紀錄）發生變化後，替受影響
    的治理紀錄建立可疑標記。回傳新建的標記 id。文件章節不建標記（見模組說明）。

    changed_id 可以是「新的取代者」：此時觸發源是它 supersedes 的舊紀錄。"""
    gov = gv.load_governance(layout)
    by_id = gov.by_id()
    changed = by_id.get(changed_id)
    if changed is None:
        return []
    kind = gv.kind_of_id(changed_id)
    # 觸發源：新紀錄 supersedes 的舊紀錄；撤回／駁回時就是自己
    if kind == "decision" and changed.get("status") == "active":
        triggers = gv._as_list(changed.get("supersedes"))
    elif kind == "ruling" and changed.get("status") == "effective":
        triggers = gv._as_list(changed.get("supersedes"))
    else:
        triggers = [changed_id]
    graph = build_graph(layout, leaves, gov)
    if kind == "decision" and changed.get("status") == "active":
        # 取代者已生效＝被取代的舊決策上的可疑標記已由取代本身處理，自動清除並寫明理由。
        for s in gov.suspects:
            if s.get("status") == "open" and str(s.get("target")) in triggers:
                rec = {k: v for k, v in s.items() if not k.startswith("_")}
                rec.update({"status": "cleared", "cleared-by": "docspec", "cleared-at": gv.today(),
                            "cleared-reason": f"superseded by {changed_id}"})
                gv.write_record(layout, "suspect", rec)
    existing = _open_suspect_keys(gov)
    try:
        tool = tool or gv.detect_tool()
    except gv.GovernanceError:
        tool = "user"
    created: list[str] = []
    for trig in triggers:
        for node, etype in graph.dependents(trig):
            if node.startswith(DOC_NS) or etype not in ("based-on", "refs"):
                continue
            if node == changed_id or (trig, node) in existing:
                continue
            sid = gv.next_id(layout, "suspect", tool)
            gv.write_record(layout, "suspect", {
                "id": sid, "trigger": trig, "target": node, "path": [trig, etype, node],
                "status": "open", "created-at": gv.today()})
            existing.add((trig, node))
            created.append(sid)
    return created


def doc_sections_needing_review(layout: Layout, leaves: list,
                                gov: gv.Governance | None = None) -> list[dict]:
    """realizes 指向「已被取代／撤回」治理決策的文件章節——需審閱後改指向接替者。"""
    gov = gov or gv.load_governance(layout)
    out = []
    for d in gov.decisions:
        st = gv.decision_effective_status(d, gov)
        if st not in ("superseded", "withdrawn"):
            continue
        ref = gv.GOV_NAMESPACE + str(d["id"])
        succ = gv.superseded_by(d, gov)
        for leaf in leaves:
            if leaf.concept and ref in [str(x) for x in (leaf.concept.get("realizes") or [])]:
                out.append({"section": leaf.section, "decision": str(d["id"]), "status": st,
                            "successor": succ, "title": leaf.title})
    return out
