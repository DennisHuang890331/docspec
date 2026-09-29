"""軟體 change：一個 change 一個資料夾（照 OpenSpec 的結構，格式為 YAML，一律透過指令寫入）。

    docspec/software/changes/<change>/
    ├─ proposal.yaml        why / what / capabilities{new, modified} / code-areas / depends-on
    ├─ design.yaml          context / goals / non-goals / risks / migration / open-questions / decisions
    ├─ specs/<能力>.yaml    規格差異（delta.py）
    ├─ tests.yaml           測試規劃與測試異議（tests.py）
    └─ tasks.yaml           任務（tasks.py；完成欄位只由引擎寫入）

封存後整個資料夾搬到 `changes/_archive/<YYYY-MM-DD>-<change>/`。
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from dspx.engine import governance as gv
from dspx.engine.layout import Layout
from dspx.engine.software import delta as dl
from dspx.engine.software import io
from dspx.engine.software import specs as sp

_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PROPOSAL_FIELDS = ("id", "why", "what", "capabilities", "code-areas", "depends-on",
                   "created-by", "created-at", "imported-from")
DESIGN_FIELDS = ("context", "goals", "non-goals", "risks", "migration", "open-questions", "decisions")
DEFAULT_SIZE_WARNING = {"tasks": 30, "capabilities": 4}


# ── 設定（使用者可手改的一般 YAML，不封條）──────────────────────────────

def load_config(layout: Layout) -> dict:
    p = io.config_path(layout)
    if not p.is_file():
        return {}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def repo_settings(layout: Layout) -> dict[str, dict]:
    """登記的程式 repo：名稱 → {path, test-command?}。config 可寫 `名稱: 路徑` 或 `名稱: {path, test-command}`。"""
    out = {}
    for k, v in (load_config(layout).get("repos") or {}).items():
        out[str(k)] = dict(v) if isinstance(v, dict) else {"path": str(v)}
    return out


def repos(layout: Layout) -> dict[str, Path]:
    """登記的程式 repo：名稱 → 絕對路徑（相對專案根）。"""
    return {k: (layout.project_root / str(v.get("path") or ".")).resolve()
            for k, v in repo_settings(layout).items()}


def size_warning(layout: Layout) -> dict:
    return {**DEFAULT_SIZE_WARNING, **(load_config(layout).get("change-size-warning") or {})}


# ── 路徑與載入 ───────────────────────────────────────────────────────────

def validate_id(cid: str) -> str | None:
    if not _ID_RE.match(cid or ""):
        return "change id must be lowercase letters, digits and single hyphens (kebab-case)"
    return None


def list_active(layout: Layout) -> list[str]:
    d = io.changes_dir(layout)
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.iterdir()
                  if p.is_dir() and p.name != io.ARCHIVE_DIR and (p / "proposal.yaml").is_file())


def list_archived(layout: Layout) -> list[str]:
    d = io.archive_dir(layout)
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.iterdir() if p.is_dir())


def archived_ids(layout: Layout) -> dict[str, str]:
    """封存資料夾名（日期-id）→ change id。"""
    out = {}
    for name in list_archived(layout):
        m = re.match(r"^\d{4}-\d{2}-\d{2}-(.+)$", name)
        out[m.group(1) if m else name] = name
    return out


def change_state(layout: Layout, cid: str) -> str | None:
    if (io.change_dir(layout, cid) / "proposal.yaml").is_file():
        return "active"
    if cid in archived_ids(layout):
        return "archived"
    return None


def load_change(layout: Layout, cid: str, folder: Path | None = None) -> dict:
    """{id, folder, proposal, design, deltas{能力: delta}, tests, tasks}。"""
    folder = folder or io.change_dir(layout, cid)
    if not (folder / "proposal.yaml").is_file():
        raise io.SoftwareError(f"no software change \"{cid}\"")
    out = {"id": cid, "folder": folder, "proposal": io.load(folder / "proposal.yaml", "proposal"),
           "design": io.load(folder / "design.yaml", "design") if (folder / "design.yaml").is_file() else {},
           "deltas": {}, "tests": {"tests": [], "objections": []}, "tasks": {"tasks": []}}
    sdir = folder / "specs"
    if sdir.is_dir():
        for p in sorted(sdir.rglob("*.yaml")):
            body = io.load(p, "delta")
            out["deltas"][body["capability"]] = body
    if (folder / "tests.yaml").is_file():
        out["tests"] = io.load(folder / "tests.yaml", "tests")
    if (folder / "tasks.yaml").is_file():
        out["tasks"] = io.load(folder / "tasks.yaml", "tasks")
    return out


def load_archived(layout: Layout, cid: str) -> dict:
    name = archived_ids(layout).get(cid)
    if name is None:
        raise io.SoftwareError(f"no archived software change \"{cid}\"")
    return load_change(layout, cid, io.archive_dir(layout) / name)


def write_part(layout: Layout, cid: str, part: str, body, capability: str | None = None) -> None:
    folder = io.change_dir(layout, cid)
    if part == "delta":
        io.write(folder / "specs" / f"{capability}.yaml", "delta", body)
    else:
        io.write(folder / f"{part}.yaml", part, body)


# ── 建立與差異 ───────────────────────────────────────────────────────────

def new_change(layout: Layout, cid: str, *, why: str, what: list[str], new_caps: list[str],
               modified_caps: list[str], code_areas: list[str], depends_on: list[str],
               tool: str) -> dict:
    reason = validate_id(cid)
    if reason:
        raise io.SoftwareError(reason)
    if change_state(layout, cid):
        raise io.SoftwareError(f"software change \"{cid}\" already exists ({change_state(layout, cid)})")
    from dspx.commands.change.archive import name_taken_elsewhere
    clash = name_taken_elsewhere(layout, cid, "software")
    if clash:
        raise io.SoftwareError(f"{clash} — change names are shared by documents and software "
                               f"(one `docspec archive`)")
    existing = set(sp.list_capabilities(layout))
    for c in new_caps:
        if c in existing:
            raise io.SoftwareError(f"capability \"{c}\" already exists; list it as modified")
    for c in modified_caps:
        if c not in existing:
            raise io.SoftwareError(f"capability \"{c}\" does not exist; list it as new")
    proposal = {"id": cid, "why": why.strip(), "what": [w.strip() for w in what if w.strip()],
                "capabilities": {"new": new_caps, "modified": modified_caps},
                "created-by": tool, "created-at": gv.today()}
    if code_areas:
        proposal["code-areas"] = code_areas
    if depends_on:
        proposal["depends-on"] = depends_on
    write_part(layout, cid, "proposal", proposal)
    write_part(layout, cid, "design", {})
    write_part(layout, cid, "tests", {"tests": [], "objections": []})
    write_part(layout, cid, "tasks", {"tasks": []})
    return proposal


def reserved_requirement_ids(layout: Layout, capability: str, except_change: str) -> set[str]:
    """其他進行中 change 已為同一能力預留的新需求編號。"""
    out: set[str] = set()
    for cid in list_active(layout):
        if cid == except_change:
            continue
        d = load_change(layout, cid)["deltas"].get(capability)
        for x in (d or {}).get("deltas") or []:
            if x.get("op") == "add-requirement":
                out.add(str(x.get("id")))
    return out


def add_delta(layout: Layout, cid: str, capability: str, raw: dict, purpose: str | None = None) -> dict:
    ch = load_change(layout, cid)
    caps = ch["proposal"].get("capabilities") or {}
    is_new = capability in (caps.get("new") or [])
    if not is_new and capability not in (caps.get("modified") or []):
        raise io.SoftwareError(f"capability \"{capability}\" is not listed in this change's proposal "
                               f"(add it with `docspec code change set {cid} --modified {capability}`)")
    cap_delta = ch["deltas"].get(capability) or {"capability": capability, "new": is_new, "deltas": []}
    if is_new:
        if purpose:
            cap_delta["purpose"] = purpose
        if not cap_delta.get("purpose"):
            raise io.SoftwareError(f"new capability \"{capability}\" needs --purpose")
    spec = None if is_new else sp.load_spec(layout, capability)
    d = dl.prepare(spec, cap_delta, raw, reserved_requirement_ids(layout, capability, cid))
    cap_delta.setdefault("deltas", []).append(d)
    write_part(layout, cid, "delta", cap_delta, capability)
    return d


def remove_deltas(layout: Layout, cid: str, capability: str, ref: str) -> int:
    """拿掉指向 ref 的差異（R1 連同它底下的情境差異；新增需求用它的編號）。"""
    ch = load_change(layout, cid)
    cd = ch["deltas"].get(capability)
    if not cd:
        raise io.SoftwareError(f"change {cid} has no deltas on \"{capability}\"")
    ref = ref.strip("/")

    def hit(d: dict) -> bool:
        target = str(d.get("ref") or d.get("id") or "")
        if d.get("op") == "add-scenario":
            target = f"{d.get('ref')}/{d.get('id')}"
        return target == ref or target.startswith(ref + "/")

    keep = [d for d in cd.get("deltas") or [] if not hit(d)]
    removed = len(cd.get("deltas") or []) - len(keep)
    if not removed:
        raise io.SoftwareError(f"no delta on {capability} {ref} in change {cid}")
    path = io.change_dir(layout, cid) / "specs" / f"{capability}.yaml"
    if keep:
        write_part(layout, cid, "delta", {**cd, "deltas": keep}, capability)
    else:
        path.unlink()
    return removed


def preview_specs(layout: Layout, ch: dict) -> tuple[dict[str, dict], list[str], dict[str, str]]:
    """把 change 的全部差異套到現行規格的副本上（不寫入）。回 (新規格們, 衝突, 編號重配)。"""
    out, conflicts, renames = {}, [], {}
    for cap, cap_delta in ch["deltas"].items():
        new_spec, c, r = dl.apply(sp.load_spec(layout, cap), cap_delta)
        conflicts += c
        renames.update(r)
        if not c:
            out[cap] = new_spec
    return out, conflicts, renames


# ── 引用檢查（格式以外：內容之間是否接得上）────────────────────────────

def validate_change(layout: Layout, ch: dict, *, strict: bool = False) -> tuple[list[str], list[str]]:
    """回 (errors, warnings)。strict＝封存前（草稿決策、基準指紋不符升為錯誤）。"""
    errs: list[str] = []
    warns: list[str] = []
    cid = ch["id"]
    where = f"software change {cid}"
    p = ch["proposal"]
    for k in p:
        if k not in PROPOSAL_FIELDS:
            errs.append(f"{where}: proposal has unknown field \"{k}\"")
    if not str(p.get("why") or "").strip():
        errs.append(f"{where}: proposal.why is empty")
    for k in ch["design"]:
        if k not in DESIGN_FIELDS:
            errs.append(f"{where}: design has unknown field \"{k}\"")
    caps = p.get("capabilities") or {}
    listed = set(caps.get("new") or []) | set(caps.get("modified") or [])
    for cap in ch["deltas"]:
        if cap not in listed:
            errs.append(f"{where}: delta for \"{cap}\" but the proposal does not list that capability")
    for cap in listed:
        if cap not in ch["deltas"]:
            warns.append(f"{where}: proposal lists \"{cap}\" but there is no delta for it yet")

    # 決策引用：設計決策與需求依據
    gov = gv.load_governance(layout) if gv.has_governance(layout) else gv.Governance([], [], [], [])
    decisions = {str(d.get("id")): d for d in gov.decisions}

    def check_decision(ref: str, field: str) -> None:
        did = gv.strip_ns(ref)
        d = decisions.get(did)
        if d is None:
            errs.append(f"{where}: {field} points to nonexistent decision \"{ref}\"")
            return
        st = gv.decision_effective_status(d, gov)
        if st in ("superseded", "withdrawn"):
            errs.append(f"{where}: {field} points to a {st} decision \"{ref}\" "
                        f"(use its successor{': gov:' + str(gv.superseded_by(d, gov)) if gv.superseded_by(d, gov) else ''})")
        elif st == "draft":
            (errs if strict else warns).append(f"{where}: {field} points to a draft decision \"{ref}\" "
                                               f"(activate it before archiving)")

    for ref in io.as_list(ch["design"].get("decisions")):
        check_decision(ref, "design.decisions")
    for cap, cd in ch["deltas"].items():
        for d in cd.get("deltas") or []:
            for ref in io.as_list(d.get("based-on")):
                check_decision(ref, f"{cap} {d.get('op')} {d.get('ref') or d.get('id')} based-on")

    # 差異對現行規格：目標存在、基準指紋一致
    _preview, conflicts, _ren = preview_specs(layout, ch)
    for c in conflicts:
        (errs if strict else warns).append(f"{where}: {c}")
    for cap, new_spec in _preview.items():
        for e in sp.validate_spec(new_spec, where=f"{where} (after applying) {cap}"):
            errs.append(e)

    # 前置 change
    deps = io.as_list(p.get("depends-on"))
    for dep in deps:
        st = change_state(layout, dep)
        if st is None:
            errs.append(f"{where}: depends-on \"{dep}\" does not exist")
        elif strict and st != "archived":
            errs.append(f"{where}: depends-on \"{dep}\" must be archived first")
    if cid in deps:
        errs.append(f"{where}: depends on itself")

    # 上游決策變更影響（影響分析建立的可疑標記）
    from dspx.engine.software.links import SWC_NS, open_suspects
    for s in open_suspects(layout, SWC_NS + cid):
        (errs if strict else warns).append(
            f"{where}: affected by a change to {s.get('trigger')} — review the change, then "
            f"`docspec impact clear {s.get('id')} --reason …` ({s.get('id')})")

    # 大小提醒
    lim = size_warning(layout)
    ntasks = len(ch["tasks"].get("tasks") or [])
    if ntasks > int(lim["tasks"]) or len(listed) > int(lim["capabilities"]):
        warns.append(f"{where}: large change ({ntasks} tasks, {len(listed)} capabilities) — consider "
                     f"splitting unrelated work into its own change")

    from dspx.engine.software import tasks as tk
    e2, w2 = tk.validate_tasks_and_tests(layout, ch)
    if p.get("imported-from") and not strict:
        # 從 OpenSpec 匯入的 change 本來就沒有「任務→需求」「測試→情境」連結：平常只合併成一則提醒，
        # 不讓整個專案的 check 變紅；封存（strict）時照樣逐條擋下。
        gaps = [e for e in e2 if "no task implements it" in e or "no planned test covers it" in e]
        if gaps:
            e2 = [e for e in e2 if e not in gaps]
            n_req = sum(1 for e in gaps if "no task implements it" in e)
            w2 = w2 + [f"{where}: imported from OpenSpec — {n_req} requirement(s) have no implementing "
                       f"task and {len(gaps) - n_req} scenario(s) have no planned test; link them with "
                       f"`docspec code task set` / `docspec code testplan add` before archiving"]
    return errs + e2, warns + w2


def render_md(layout: Layout, ch: dict) -> str:
    p = ch["proposal"]
    lines = [f"# Change: {ch['id']}", "", "## Why", str(p.get("why", "")).strip(), "",
             "## What changes"]
    lines += [f"- {w}" for w in p.get("what") or []]
    caps = p.get("capabilities") or {}
    lines += ["", "## Capabilities", f"- new: {', '.join(caps.get('new') or []) or '—'}",
              f"- modified: {', '.join(caps.get('modified') or []) or '—'}"]
    if p.get("depends-on"):
        lines.append(f"- depends on: {', '.join(p['depends-on'])}")
    d = ch["design"]
    if d:
        lines += ["", "## Design"]
        for k in ("context", "goals", "non-goals", "risks", "migration", "open-questions", "decisions"):
            if d.get(k):
                lines.append(f"### {k}")
                v = d[k]
                if isinstance(v, list):
                    lines += [f"- {x if not isinstance(x, dict) else ' → '.join(str(y) for y in x.values())}"
                              for x in v]
                else:
                    lines.append(str(v).strip())
    for cap, cd in ch["deltas"].items():
        lines += ["", f"## Spec delta: {cap}{' (new)' if cd.get('new') else ''}"]
        for x in cd.get("deltas") or []:
            ref = x.get("ref") or x.get("id")
            body = "; ".join(f"{k}: {x[k]}" for k in ("title", "statement", "when", "then", "reason")
                             if k in x)
            lines.append(f"- **{x['op']}** {ref} — {body}")
    from dspx.engine.software import tasks as tk
    lines += ["", tk.render_md(layout, ch)]
    return "\n".join(lines).rstrip() + "\n"
