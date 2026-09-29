"""OpenSpec 匯入（第二期 P2-6）：`openspec/` → `docspec/software/`。

- 現行規格 `openspec/specs/<能力>/spec.md` → `software/specs/<能力>.yaml`
  需求依出現順序編 R1、R2…，情境編 S1、S2…；驗證方法 OpenSpec 沒有，一律先設 test（報告提醒檢查）。
- 進行中的 change `openspec/changes/<id>/` → `software/changes/<id>/`，可以接著做：
  proposal.md → proposal.yaml；design.md 全文 → design.yaml 的 context；
  規格差異（ADDED／MODIFIED／REMOVED／RENAMED）→ 引擎的差異（經 delta.prepare，自動補基準指紋）。
  MODIFIED 在 OpenSpec 是整段取代：規範句變了＝modify-requirement；情境依名稱比對，
  變了＝modify-scenario、新的＝add-scenario、不見的＝remove-scenario。
  tasks.md → tasks.yaml：已打勾＝「匯入時已完成（無證據）」，未打勾＝未開始。
- 已封存的 change `openspec/changes/archive/<日期>-<id>/` → `software/changes/_archive/<日期>-<id>/`，
  只保留提案、設計與任務作為歷史（它們的差異早已反映在現行規格裡，不重放）。
- 不動 `openspec/` 本身；其他檔案（discussion.md、verification.md…）列在報告裡，原檔留著參考。
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from dspx.engine import governance as gv
from dspx.engine.layout import Layout
from dspx.engine.software import changes as chg
from dspx.engine.software import delta as dl
from dspx.engine.software import io
from dspx.engine.software import specs as sp

_REQ_H = re.compile(r"^###\s+Requirement:\s*(.+?)\s*#*\s*$")
_SCN_H = re.compile(r"^####\s+Scenario:\s*(.+?)\s*#*\s*$")
_H2 = re.compile(r"^##\s+(.+?)\s*$")
_BULLET = re.compile(r"^\s*[-*+]\s+\*\*(GIVEN|WHEN|THEN|AND|BUT)\*\*:?\s*(.*)$", re.I)
_RENAME_FROM = re.compile(r"^\s*[-*+]?\s*FROM:\s*`?###\s*Requirement:\s*(.+?)`?\s*$")
_RENAME_TO = re.compile(r"^\s*[-*+]?\s*TO:\s*`?###\s*Requirement:\s*(.+?)`?\s*$")
_TASK = re.compile(r"^\s*[-*+]\s+\[( |x|X)\]\s+(.*)$")
_KNOWN_CHANGE_FILES = {"proposal.md", "design.md", "tasks.md", ".openspec.yaml"}


# ── Markdown 解析 ────────────────────────────────────────────────────────

def _strip_fences(lines: list[str]) -> list[tuple[str, bool]]:
    """(行, 是否在 code fence 內)：fence 內的 `###` 不是標題。"""
    out, inside = [], False
    for line in lines:
        if line.strip().startswith("```"):
            inside = not inside
            out.append((line, True))
            continue
        out.append((line, inside))
    return out


def _sections(text: str) -> dict[str, list[str]]:
    """`## 標題` → 內容行（fence 內不切）。"""
    out: dict[str, list[str]] = {}
    cur = None
    for line, fenced in _strip_fences(text.splitlines()):
        m = None if fenced else _H2.match(line)
        if m:
            cur = m.group(1).strip()
            out.setdefault(cur, [])
        elif cur is not None:
            out[cur].append(line)
    return out


def _para(lines: list[str]) -> str:
    return "\n".join(line.rstrip() for line in lines).strip()


def _parse_scenario(title: str, lines: list[str]) -> dict:
    when, then, extra = [], [], []
    phase = "when"
    for line in lines:
        m = _BULLET.match(line)
        if m:
            kw, body = m.group(1).upper(), m.group(2).strip()
            if kw == "THEN":
                phase = "then"
                then.append(body)
            elif kw == "GIVEN":
                when.append(f"given {body}")
            elif kw == "WHEN":
                phase = "when"
                when.append(body)
            else:                                  # AND／BUT 跟著目前的段落
                (then if phase == "then" else when).append(body)
        elif line.strip():
            extra.append(line.strip())
    scn = {"title": title, "when": "; ".join(when), "then": "; ".join(then)}
    if extra:
        scn["then"] = (scn["then"] + "\n" + "\n".join(extra)).strip()
    return scn


def parse_requirements(lines: list[str]) -> list[dict]:
    """`### Requirement:` 區塊 → [{title, statement, scenarios:[{title, when, then}]}]。"""
    reqs: list[dict] = []
    cur = None
    scn_title, scn_lines = None, []

    def close_scn():
        nonlocal scn_title, scn_lines
        if cur is not None and scn_title is not None:
            cur["scenarios"].append(_parse_scenario(scn_title, scn_lines))
        scn_title, scn_lines = None, []

    for line, fenced in _strip_fences(lines):
        rm = None if fenced else _REQ_H.match(line)
        sm = None if fenced else _SCN_H.match(line)
        if rm:
            close_scn()
            cur = {"title": rm.group(1).strip(), "_body": [], "scenarios": []}
            reqs.append(cur)
        elif sm and cur is not None:
            close_scn()
            scn_title = sm.group(1).strip()
        elif cur is not None:
            (scn_lines if scn_title is not None else cur["_body"]).append(line)
    close_scn()
    for r in reqs:
        r["statement"] = _para(r.pop("_body"))
    return reqs


def parse_spec(text: str) -> dict:
    secs = _sections(text)
    purpose = _para(secs.get("Purpose", []))
    return {"purpose": purpose, "requirements": parse_requirements(secs.get("Requirements", []))}


def parse_delta(text: str) -> dict:
    """{purpose, added, modified, removed:[{title, reason}], renamed:[(from, to)]}。"""
    secs = {k.lower(): v for k, v in _sections(text).items()}
    removed = []
    cur = None
    for line, fenced in _strip_fences(secs.get("removed requirements", [])):
        m = None if fenced else (_REQ_H.match(line) or re.match(
            r"^\s*[-*+]\s*`?###\s*Requirement:\s*(.+?)`?\s*$", line))
        if m:
            cur = {"title": m.group(1).strip(), "reason": []}
            removed.append(cur)
        elif cur is not None and line.strip():
            cur["reason"].append(line.strip().replace("**", ""))
    renamed, pending = [], None
    for line, fenced in _strip_fences(secs.get("renamed requirements", [])):
        if fenced:
            continue
        fm, tm = _RENAME_FROM.match(line), _RENAME_TO.match(line)
        if fm:
            pending = fm.group(1).strip()
        elif tm and pending:
            renamed.append((pending, tm.group(1).strip()))
            pending = None
    return {"purpose": _para(secs.get("purpose", [])),
            "added": parse_requirements(secs.get("added requirements", [])),
            "modified": parse_requirements(secs.get("modified requirements", [])),
            "removed": [{"title": r["title"], "reason": " ".join(r["reason"]) or "removed in OpenSpec"}
                        for r in removed],
            "renamed": renamed}


def parse_tasks(text: str) -> list[dict]:
    out = []
    for line in text.splitlines():
        m = _TASK.match(line)
        if m:
            out.append({"title": " ".join(m.group(2).split()), "checked": m.group(1).lower() == "x"})
    return out


def parse_proposal(text: str) -> dict:
    secs = _sections(text)
    what = []
    for line in secs.get("What Changes", []):
        m = re.match(r"^\s*[-*+]\s+(.*)$", line)
        if m:
            what.append(m.group(1).strip())
        elif what and line.strip() and line.startswith((" ", "\t")):
            what[-1] += " " + line.strip()
    return {"why": _para(secs.get("Why", [])) or _para(text.splitlines()[:20]), "what": what,
            "impact": _para(secs.get("Impact", []))}


# ── 轉換 ─────────────────────────────────────────────────────────────────

def _to_spec(cap: str, parsed: dict) -> dict:
    reqs = []
    for i, r in enumerate(parsed["requirements"], 1):
        reqs.append({"id": f"R{i}", "title": r["title"], "statement": r["statement"],
                     "verification": ["test"],
                     "scenarios": [{"id": f"S{j}", **s} for j, s in enumerate(r["scenarios"], 1)]})
    return {"capability": cap, "purpose": parsed["purpose"] or f"(imported from OpenSpec: {cap})",
            "requirements": reqs}


def _cap_of(spec_md: Path, base: Path) -> str:
    return str(spec_md.parent.relative_to(base)).replace("\\", "/")


def _find_by_title(spec: dict | None, title: str) -> dict | None:
    for r in (spec or {}).get("requirements") or []:
        if r.get("title") == title:
            return r
    return None


def _deltas_for(cap: str, spec: dict | None, parsed: dict, notes: list[str], where: str) -> dict | None:
    """一個能力的 OpenSpec 差異 → 引擎差異（經 delta.prepare）。"""
    is_new = spec is None
    cd = {"capability": cap, "new": is_new, "deltas": []}
    if is_new:
        cd["purpose"] = parsed["purpose"] or f"(imported from OpenSpec: {cap})"
        if parsed["modified"] or parsed["removed"] or parsed["renamed"]:
            notes.append(f"{where} {cap}: MODIFIED/REMOVED/RENAMED on a capability that does not "
                         f"exist yet — skipped")

    def add(raw: dict) -> None:
        try:
            cd["deltas"].append(dl.prepare(spec, cd, raw))
        except io.SoftwareError as exc:
            notes.append(f"{where} {cap}: {exc}")

    for old, new in ([] if is_new else parsed["renamed"]):
        r = _find_by_title(spec, old)
        if r is None:
            notes.append(f"{where} {cap}: RENAMED \"{old}\" not found in the current spec — skipped")
        else:
            add({"op": "rename-requirement", "ref": r["id"], "title": new})
    for m in ([] if is_new else parsed["modified"]):
        r = _find_by_title(spec, m["title"])
        if r is None:
            notes.append(f"{where} {cap}: MODIFIED \"{m['title']}\" not found in the current spec — "
                         f"skipped (add it by hand with `docspec code change delta`)")
            continue
        if m["statement"] != r.get("statement"):
            add({"op": "modify-requirement", "ref": r["id"], "statement": m["statement"]})
        old_scn = {s["title"]: s for s in r.get("scenarios") or []}
        new_titles = {s["title"] for s in m["scenarios"]}
        for s in m["scenarios"]:
            o = old_scn.get(s["title"])
            if o is None:
                add({"op": "add-scenario", "ref": r["id"], **s})
            elif (o.get("when"), o.get("then")) != (s["when"], s["then"]):
                add({"op": "modify-scenario", "ref": f"{r['id']}/{o['id']}", "when": s["when"],
                     "then": s["then"]})
        for title, o in old_scn.items():
            if title not in new_titles:
                add({"op": "remove-scenario", "ref": f"{r['id']}/{o['id']}",
                     "reason": "dropped from the requirement's MODIFIED block in OpenSpec"})
    for rem in ([] if is_new else parsed["removed"]):
        r = _find_by_title(spec, rem["title"])
        if r is None:
            notes.append(f"{where} {cap}: REMOVED \"{rem['title']}\" not found — skipped")
        else:
            add({"op": "remove-requirement", "ref": r["id"], "reason": rem["reason"]})
    for a in parsed["added"]:
        if not is_new and _find_by_title(spec, a["title"]):
            notes.append(f"{where} {cap}: ADDED \"{a['title']}\" already exists in the current spec — "
                         f"skipped")
            continue
        if not a["scenarios"]:
            notes.append(f"{where} {cap}: ADDED \"{a['title']}\" has no scenario — skipped")
            continue
        add({"op": "add-requirement", "title": a["title"], "statement": a["statement"],
             "verification": ["test"], "scenarios": a["scenarios"]})
    return cd if cd["deltas"] else None


def _change_meta(folder: Path) -> dict:
    meta = folder / ".openspec.yaml"
    if meta.is_file():
        try:
            return yaml.safe_load(meta.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            return {}
    return {}


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def _change_parts(folder: Path, cid: str, tool: str, rel: str) -> tuple[dict, dict, dict]:
    prop = parse_proposal(_read(folder / "proposal.md"))
    created = str(_change_meta(folder).get("created") or gv.today())
    proposal = {"id": cid, "why": prop["why"] or "(imported from OpenSpec; no Why section)",
                "what": prop["what"], "capabilities": {"new": [], "modified": []},
                "created-by": tool, "created-at": created, "imported-from": rel}
    design_text = _read(folder / "design.md").strip()
    design = {"context": design_text} if design_text else {}
    if prop["impact"]:
        design["migration"] = prop["impact"]
    tasks = {"tasks": []}
    for i, t in enumerate(parse_tasks(_read(folder / "tasks.md")), 1):
        rec = {"id": str(i), "title": t["title"], "verify": {"methods": []},
               "status": "imported-done" if t["checked"] else "not-started"}
        tasks["tasks"].append(rec)
    return proposal, design, tasks


def run_import(layout: Layout, source: Path, *, tool: str, dry_run: bool = False) -> dict:
    """匯入；回報告資料。已有軟體規格或 change 時拒絕（避免重複匯入）。"""
    specs_root = source / "specs"
    changes_root = source / "changes"
    if not specs_root.is_dir() and not changes_root.is_dir():
        raise io.SoftwareError(f"{source} does not look like an OpenSpec folder (no specs/ or changes/)")
    if sp.list_capabilities(layout) or chg.list_active(layout) or chg.list_archived(layout):
        raise io.SoftwareError("docspec/software already has specs or changes; import only into an "
                               "empty software domain")
    rel_base = source.resolve()
    try:
        rel_base = source.resolve().relative_to(layout.project_root.resolve())
    except ValueError:
        pass
    notes: list[str] = []
    report = {"specs": [], "active": [], "archived": [], "notes": notes, "not-imported": []}

    # 1. 現行規格
    specs: dict[str, dict] = {}
    for md in sorted(specs_root.rglob("spec.md")) if specs_root.is_dir() else []:
        cap = _cap_of(md, specs_root)
        spec = _to_spec(cap, parse_spec(md.read_text(encoding="utf-8")))
        for e in sp.validate_spec(spec):
            notes.append(f"imported {e}")
        specs[cap] = spec
        report["specs"].append({"capability": cap, "requirements": len(spec["requirements"]),
                                "scenarios": sum(len(r["scenarios"]) for r in spec["requirements"])})

    # 2. 進行中的 change（差異對照剛匯入的規格）
    active: list[tuple[str, dict, dict, dict, dict]] = []
    for folder in sorted(p for p in changes_root.iterdir() if p.is_dir() and p.name != "archive") \
            if changes_root.is_dir() else []:
        cid = folder.name
        if chg.validate_id(cid):
            notes.append(f"change \"{cid}\": {chg.validate_id(cid)} — skipped")
            continue
        proposal, design, tasks = _change_parts(folder, cid, tool, f"{rel_base}/changes/{cid}")
        deltas = {}
        sdir = folder / "specs"
        for md in sorted(sdir.rglob("spec.md")) if sdir.is_dir() else []:
            cap = _cap_of(md, sdir)
            cd = _deltas_for(cap, specs.get(cap), parse_delta(md.read_text(encoding="utf-8")), notes,
                             f"change {cid}:")
            if cd:
                deltas[cap] = cd
                proposal["capabilities"]["new" if cd["new"] else "modified"].append(cap)
        extra = sorted(str(p.relative_to(folder)) for p in folder.iterdir()
                       if p.is_file() and p.name not in _KNOWN_CHANGE_FILES)
        if extra:
            report["not-imported"].append({"change": cid, "files": extra})
        active.append((cid, proposal, design, tasks, deltas))
        n = tasks["tasks"]
        report["active"].append({"change": cid, "deltas": sum(len(d["deltas"]) for d in deltas.values()),
                                 "tasks": len(n),
                                 "imported-done": sum(1 for t in n if t["status"] == "imported-done")})

    # 3. 已封存的 change（只留歷史）
    archived: list[tuple[str, str, dict, dict, dict]] = []
    arch_root = changes_root / "archive"
    for folder in sorted(p for p in arch_root.iterdir() if p.is_dir()) if arch_root.is_dir() else []:
        m = re.match(r"^(\d{4}-\d{2}-\d{2})-(.+)$", folder.name)
        cid = m.group(2) if m else folder.name
        proposal, design, tasks = _change_parts(folder, cid, tool,
                                                f"{rel_base}/changes/archive/{folder.name}")
        sdir = folder / "specs"
        caps = sorted(_cap_of(md, sdir) for md in sdir.rglob("spec.md")) if sdir.is_dir() else []
        proposal["capabilities"]["modified"] = caps
        archived.append((folder.name, cid, proposal, design, tasks))
        report["archived"].append({"change": cid, "folder": folder.name, "tasks": len(tasks["tasks"])})

    if dry_run:
        return report

    # 寫入（全部算好後才寫）
    for spec in specs.values():
        sp.write_spec(layout, spec)
    for cid, proposal, design, tasks, deltas in active:
        chg.write_part(layout, cid, "proposal", proposal)
        chg.write_part(layout, cid, "design", design)
        chg.write_part(layout, cid, "tests", {"tests": [], "objections": []})
        chg.write_part(layout, cid, "tasks", tasks)
        for cap, cd in deltas.items():
            chg.write_part(layout, cid, "delta", cd, cap)
    for name, _cid, proposal, design, tasks in archived:
        folder = io.archive_dir(layout) / name
        io.write(folder / "proposal.yaml", "proposal", proposal)
        io.write(folder / "design.yaml", "design", design)
        io.write(folder / "tests.yaml", "tests", {"tests": [], "objections": []})
        io.write(folder / "tasks.yaml", "tasks", tasks)
    return report


def render_report(report: dict, source: str) -> str:
    lines = ["# OpenSpec 匯入報告", "", f"來源：`{source}`（原檔未改動，可自行決定保留或刪除）", ""]
    lines += ["## 現行規格", ""]
    for s in report["specs"]:
        lines.append(f"- {s['capability']}：{s['requirements']} 條需求、{s['scenarios']} 個情境")
    lines += ["", "所有需求的驗證方法先設為 test（OpenSpec 沒有這個欄位）。需要人看的需求（畫面、版面），"
              "請用一個 change 改成 inspection 或 demonstration。", ""]
    lines += ["## 進行中的 change", ""]
    for c in report["active"]:
        lines.append(f"- {c['change']}：{c['deltas']} 筆規格差異、{c['tasks']} 個任務"
                     f"（其中 {c['imported-done']} 個標為「匯入時已完成（無證據）」）")
    if report["active"]:
        lines += ["", "接著做之前：用 `docspec code change status <change>` 看還缺什麼。匯入的任務沒有"
                  "驗證方法與測試規劃，需要用 `docspec code task set` 補上，並由測試角色用 "
                  "`docspec code testplan add` 規劃測試。", ""]
    lines += ["## 已封存的 change（歷史）", ""]
    for c in report["archived"]:
        lines.append(f"- {c['folder']}：{c['tasks']} 個任務")
    if report["not-imported"]:
        lines += ["", "## 沒有匯入的檔案（原檔仍在 openspec/）", ""]
        for x in report["not-imported"]:
            lines.append(f"- {x['change']}：{', '.join(x['files'])}")
    if report["notes"]:
        lines += ["", "## 需要注意", ""]
        lines += [f"- {n}" for n in report["notes"]]
    return "\n".join(lines).rstrip() + "\n"
