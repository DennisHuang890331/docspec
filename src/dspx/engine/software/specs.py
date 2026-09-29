"""能力規格（現行基線）：`docspec/software/specs/<能力>.yaml`。

結構：
    capability: task-entry-page
    purpose: …
    requirements:
      - id: R1
        title: …
        statement: …SHALL…
        verification: [test, inspection]      # test / demonstration / inspection / analysis
        based-on: [gov:D-claude-2]            # 可選
        scenarios:
          - {id: S1, title: …, when: …, then: …, verified-by: [labelvault:tests/x.py::test_y]}
    retired: {requirements: [R4], scenarios: [R1/S2]}   # 編號永不重用

規格只能由 change 的 sync／封存改動（見 delta.py）。
"""

from __future__ import annotations

import re

from dspx.engine.layout import Layout
from dspx.engine.software import io

VERIFICATION_METHODS = ("test", "demonstration", "inspection", "analysis")
_NORMATIVE = re.compile(r"\b(SHALL|MUST)\b")
_REQ_ID = re.compile(r"^R[1-9][0-9]*$")
_SCN_ID = re.compile(r"^S[1-9][0-9]*$")
REQ_FIELDS = ("id", "title", "statement", "verification", "based-on", "scenarios")
SCN_FIELDS = ("id", "title", "when", "then", "verified-by")


# ── 讀寫 ─────────────────────────────────────────────────────────────────

def load_spec(layout: Layout, capability: str) -> dict | None:
    path = io.spec_path(layout, capability)
    return io.load(path, "spec") if path.is_file() else None


def write_spec(layout: Layout, spec: dict) -> None:
    io.write(io.spec_path(layout, spec["capability"]), "spec", spec)


def list_capabilities(layout: Layout) -> list[str]:
    d = io.specs_dir(layout)
    if not d.is_dir():
        return []
    return sorted(str(p.relative_to(d).with_suffix("")).replace("\\", "/")
                  for p in d.rglob("*.yaml"))


def load_all(layout: Layout) -> dict[str, dict]:
    return {c: load_spec(layout, c) for c in list_capabilities(layout)}


# ── 定址與指紋 ───────────────────────────────────────────────────────────

def split_ref(ref: str) -> tuple[str, str | None, str | None]:
    """`task-entry-page/R1/S2` → (能力, R1, S2)。能力名可含 `/`，所以從尾巴解析。"""
    ref = str(ref)
    for prefix in ("req:", "scn:"):
        if ref.startswith(prefix):
            ref = ref[len(prefix):]
    parts = ref.split("/")
    scn = parts[-1] if parts and _SCN_ID.match(parts[-1]) else None
    if scn:
        parts = parts[:-1]
    req = parts[-1] if parts and _REQ_ID.match(parts[-1]) else None
    if req:
        parts = parts[:-1]
    return "/".join(parts), req, scn


def find_requirement(spec: dict | None, rid: str) -> dict | None:
    for r in (spec or {}).get("requirements") or []:
        if str(r.get("id")) == rid:
            return r
    return None


def find_scenario(req: dict | None, sid: str) -> dict | None:
    for s in (req or {}).get("scenarios") or []:
        if str(s.get("id")) == sid:
            return s
    return None


def scenario_fp(s: dict) -> str:
    return io.fingerprint({k: s.get(k) for k in ("title", "when", "then")})


def requirement_head_fp(r: dict) -> str:
    """需求本身（不含情境）的指紋：只改情境的並行 change 不會和改規範句的 change 互相衝突。"""
    return io.fingerprint({k: r.get(k) for k in ("title", "statement", "verification", "based-on")})


def requirement_fp(r: dict) -> str:
    """需求含全部情境的指紋（移除需求時用；也是文件章節 realizes 的內容來源）。"""
    return io.fingerprint({"head": requirement_head_fp(r),
                           "scenarios": [scenario_fp(s) for s in r.get("scenarios") or []]})


def requirement_text(r: dict) -> str:
    """需求的正規化全文（文件章節 realizes `req:` 時投影與 hash 的內容）。"""
    lines = [f"{r.get('title')}: {r.get('statement')}"]
    for s in r.get("scenarios") or []:
        lines.append(f"- {s.get('title')}: WHEN {s.get('when')} THEN {s.get('then')}")
    return "\n".join(lines)


def used_ids(spec: dict | None) -> tuple[set[str], set[str]]:
    """(用過的需求編號, 用過的 R/S 情境編號)，含已退役的——編號永不重用。"""
    reqs, scns = set(), set()
    for r in (spec or {}).get("requirements") or []:
        reqs.add(str(r.get("id")))
        for s in r.get("scenarios") or []:
            scns.add(f"{r.get('id')}/{s.get('id')}")
    retired = (spec or {}).get("retired") or {}
    reqs |= set(io.as_list(retired.get("requirements")))
    scns |= set(io.as_list(retired.get("scenarios")))
    return reqs, scns


def next_number(used: set[str], prefix: str) -> int:
    nums = [int(x[len(prefix):]) for x in used if x.startswith(prefix) and x[len(prefix):].isdigit()]
    return (max(nums) + 1) if nums else 1


# ── 驗證 ─────────────────────────────────────────────────────────────────

def validate_spec(spec: dict, where: str | None = None) -> list[str]:
    where = where or f"spec {spec.get('capability')}"
    errs: list[str] = []
    if not spec.get("capability"):
        errs.append(f"{where}: missing capability name")
    if not str(spec.get("purpose") or "").strip():
        errs.append(f"{where}: missing purpose")
    seen: set[str] = set()
    for r in spec.get("requirements") or []:
        rid = str(r.get("id"))
        rw = f"{where} {rid}"
        if not _REQ_ID.match(rid):
            errs.append(f"{rw}: requirement id must look like R<n>")
        if rid in seen:
            errs.append(f"{rw}: duplicate requirement id")
        seen.add(rid)
        for k in r:
            if k not in REQ_FIELDS:
                errs.append(f"{rw}: unknown field \"{k}\"")
        if not str(r.get("title") or "").strip():
            errs.append(f"{rw}: missing title")
        if not _NORMATIVE.search(str(r.get("statement") or "")):
            errs.append(f"{rw}: statement must state the rule with SHALL or MUST")
        for m in io.as_list(r.get("verification")):
            if m not in VERIFICATION_METHODS:
                errs.append(f"{rw}: verification \"{m}\" not in {VERIFICATION_METHODS}")
        if not io.as_list(r.get("verification")):
            errs.append(f"{rw}: missing verification method")
        scns = r.get("scenarios") or []
        if not scns:
            errs.append(f"{rw}: every requirement needs at least one scenario")
        sseen: set[str] = set()
        for s in scns:
            sid = str(s.get("id"))
            sw = f"{rw}/{sid}"
            if not _SCN_ID.match(sid):
                errs.append(f"{sw}: scenario id must look like S<n>")
            if sid in sseen:
                errs.append(f"{sw}: duplicate scenario id")
            sseen.add(sid)
            for k in s:
                if k not in SCN_FIELDS:
                    errs.append(f"{sw}: unknown field \"{k}\"")
            for k in ("title", "when", "then"):
                if not str(s.get(k) or "").strip():
                    errs.append(f"{sw}: missing {k}")
    retired_r = set(io.as_list((spec.get("retired") or {}).get("requirements")))
    for rid in seen & retired_r:
        errs.append(f"{where} {rid}: id is both live and retired")
    return errs


# ── 給人讀的 Markdown ────────────────────────────────────────────────────

def render_md(spec: dict, only_req: str | None = None) -> str:
    lines = [f"# {spec.get('capability')}", "", "## Purpose", str(spec.get("purpose", "")).strip(),
             "", "## Requirements", ""]
    for r in spec.get("requirements") or []:
        if only_req and str(r.get("id")) != only_req:
            continue
        lines += [f"### {r.get('id')} {r.get('title')}", str(r.get("statement", "")).strip(), ""]
        meta = [f"verification: {', '.join(io.as_list(r.get('verification')))}"]
        if r.get("based-on"):
            meta.append(f"based on: {', '.join(io.as_list(r.get('based-on')))}")
        lines += [f"_{'; '.join(meta)}_", ""]
        for s in r.get("scenarios") or []:
            lines += [f"#### {s.get('id')} {s.get('title')}",
                      f"- **WHEN** {s.get('when')}", f"- **THEN** {s.get('then')}"]
            if s.get("verified-by"):
                lines.append(f"- verified by: {', '.join(io.as_list(s.get('verified-by')))}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"
