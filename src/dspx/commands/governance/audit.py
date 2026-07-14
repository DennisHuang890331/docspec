"""docspec audit — 審計記錄全指令進出（list / raise / resolve / show），append-only。

audit 是結構化審計記錄：不手改 audit.yaml，一律走指令、寫時驗證、攻防 log 累積。
非阻塞：永不擋 publish。

儲存＝sibling 密封檔（`corpus/<article>.audit.yaml`）＋ forest（`<home>/audit.yaml`），
比照 roadmap：finding 依 targets 的 distinct 文件數路由（1→doc、≥2→forest）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dspx.reports.audit import (
    AuditError,
    all_findings,
    article_of_target,
    find_store,
    raise_finding,
    resolve_finding,
    route_store,
)
from dspx.commands._shared import BootstrapError, bootstrap, load_model

NAME = "audit"
HELP = "Audit record: list / raise / resolve / show findings (append-only)"


def _faces(config: dict) -> tuple[str, ...]:
    audit = config.get("audit") or {}
    core = tuple(audit.get("core") or ())
    packs = tuple((audit.get("packs") or {}).keys())
    return core + packs


def _global_next_id(layout, leaves) -> str:
    """全專案唯一 finding id（掃 forest＋所有 doc-root audit，F 編號 +1）。"""
    nums = []
    for f in all_findings(layout, leaves):
        fid = str(f.get("id", ""))
        if fid.startswith("F") and fid[1:].isdigit():
            nums.append(int(fid[1:]))
    return f"F{(max(nums) + 1) if nums else 1}"


def _parse_targets(raw: list[str] | None) -> list[str]:
    """--target 可重複，也可逗號分隔；攤平＋去空白＋保序去重。"""
    out: list[str] = []
    for item in raw or []:
        for t in str(item).split(","):
            t = t.strip()
            if t and t not in out:
                out.append(t)
    return out


def _text_arg(inline: str | None, file: str | None) -> str:
    if file:
        return Path(file).read_text(encoding="utf-8").strip()
    return (inline or "").strip()


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec audit", description=HELP)
    sub = parser.add_subparsers(dest="op")

    p_raise = sub.add_parser("raise", help="🔴 raise a finding")
    p_raise.add_argument("--target", action="append", required=True,
                         help="the section(s) it touches (path or concept id); repeatable or comma-separated")
    p_raise.add_argument("--face", required=True,
                         help="the attack face — core set: logic, completeness, clarity, discipline, "
                              "consistency (config.audit may mount more packs); an unknown face is "
                              "rejected with the valid set")
    p_raise.add_argument("--sev", required=True, choices=["high", "med", "low"])
    p_raise.add_argument("--finding"); p_raise.add_argument("--finding-file")
    p_raise.add_argument("--suggest", default=None); p_raise.add_argument("--suggest-file")
    p_raise.add_argument("--sot-owner", default=None,
                         help="cross-document finding: the source-of-truth owner document/section")
    p_raise.add_argument("--verdict", default=None, choices=["contradicted", "unsupported"],
                         help="citation-check NLI verdict: contradicted (source disagrees) / unsupported (no source backs it); "
                              "entailed (passes) raises no finding")

    p_res = sub.add_parser("resolve", help="🔵 report / 🔴 verify a finding")
    p_res.add_argument("id")
    p_res.add_argument("--status", required=True,
                       choices=["fixed", "rejected", "waived", "closed", "open"])
    p_res.add_argument("--actor", default="author")
    p_res.add_argument("--note", default=None); p_res.add_argument("--note-file")

    p_show = sub.add_parser("show", help="view a finding (with its red-team thread)")
    p_show.add_argument("id")

    p_sum = sub.add_parser("summary", help="mechanical convergence summary of the audit store "
                                           "(explicit zero-state; never a gate)")
    p_sum.add_argument("article", nargs="?", default=None,
                       help="scope to this article (its doc store + forest findings touching it)")
    p_sum.add_argument("--json", action="store_true", dest="sum_json")

    # 預設（無 op）= 彙總列出
    parser.add_argument("--article", dest="list_article", default=None, metavar="ARTICLE",
                        help="list only findings in this document's store — pass the article NAME "
                             "(e.g. --article my-doc), NOT the doc:<name> store key")
    parser.add_argument("--open", action="store_true", dest="only_open")
    parser.add_argument("--face", dest="list_face", default=None)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    try:
        layout, config = bootstrap()
    except BootstrapError as exc:
        return exc.exit_code
    faces = _faces(config)
    leaves = load_model(layout)

    if args.op == "raise":
        targets = _parse_targets(args.target)
        # 每個 target 必須解析到真實 section（防漏前綴默默建孤兒 audit.yaml）
        bad = [t for t in targets if article_of_target(t, leaves) is None]
        if bad:
            sys.stderr.write(
                f"docspec: target {bad} does not exist — an audit must hang off a real section. "
                f"Use a full section path (e.g. zenoh/query, not query) or a concept id; "
                f"see docspec status / list.\n")
            return 1
        try:
            store = route_store(layout, leaves, targets)
            f = raise_finding(store, face=args.face, severity=args.sev,
                              finding=_text_arg(args.finding, args.finding_file),
                              targets=targets,
                              suggestion=_text_arg(args.suggest, args.suggest_file),
                              sot_owner=(args.sot_owner or "").strip(),
                              verdict=(args.verdict or "").strip(),
                              faces=faces, fid=_global_next_id(layout, leaves))
        except AuditError as exc:
            sys.stderr.write(f"docspec: {exc}\n"); return 1
        store.save()
        where = "forest" if store.store == "forest" else store.store
        print(f"Raised {f['id']} ({where}, {f['face']}/{f['severity']}, targets={targets})")
        return 0

    if args.op == "resolve":
        store = find_store(layout, leaves, args.id)
        if store is None:
            sys.stderr.write(f"docspec: finding \"{args.id}\" not found\n"); return 1
        try:
            f = resolve_finding(store, args.id, status=args.status, actor=args.actor,
                                note=_text_arg(args.note, args.note_file))
        except AuditError as exc:
            sys.stderr.write(f"docspec: {exc}\n"); return 1
        store.save()
        print(f"{args.id} → {f['status']} ({args.actor}, {store.store})")
        return 0

    if args.op == "show":
        store = find_store(layout, leaves, args.id)
        if store is None:
            sys.stderr.write(f"docspec: {args.id} not found\n"); return 1
        f = store.by_id(args.id)
        if args.as_json:
            print(json.dumps(f, ensure_ascii=False, indent=2)); return 0
        _render_finding(store.store, f)
        return 0

    if args.op == "summary":
        # 涵蓋規則＝mirror publish._count_open_findings：doc store ＝ doc:<article>，
        # **加上** targets 觸及該文章的 forest findings（distinct_articles）。刻意不沿用
        # 預設列表 `--article` 的 doc-store-only 過濾——那會漏算 factcheck 最需要看的跨文件 finding。
        from dspx.reports.audit import distinct_articles
        rows = []
        for f in all_findings(layout, leaves):
            if args.article:
                store = f.get("_store", "")
                in_scope = (
                    store == f"doc:{args.article}"
                    or (store == "forest"
                        and args.article in distinct_articles(f.get("targets") or [], leaves)))
                if not in_scope:
                    continue
            rows.append(f)

        statuses = ("open", "fixed", "rejected", "waived", "closed")
        by_status = {s: 0 for s in statuses}
        for r in rows:
            s = str(r.get("status"))
            by_status[s] = by_status.get(s, 0) + 1
        open_rows = [r for r in rows if r.get("status") == "open"]
        open_by_sev: dict[str, int] = {}
        open_by_face: dict[str, int] = {}
        for r in open_rows:
            open_by_sev[str(r.get("severity"))] = open_by_sev.get(str(r.get("severity")), 0) + 1
            open_by_face[str(r.get("face"))] = open_by_face.get(str(r.get("face")), 0) + 1
        by_verdict = {"contradicted": 0, "unsupported": 0, "none": 0}
        for r in rows:
            v = str(r.get("verdict") or "").strip() or "none"
            by_verdict[v] = by_verdict.get(v, 0) + 1

        if args.sum_json:
            print(json.dumps({"article": args.article, "byStatus": by_status,
                              "openBySeverity": open_by_sev, "openByFace": open_by_face,
                              "byVerdict": by_verdict, "open": len(open_rows)},
                             ensure_ascii=False, indent=2))
            return 0

        scope = f"article \"{args.article}\"" if args.article else "the project"
        print(f"audit summary — {scope}")
        for s in statuses:
            print(f"  {s}: {by_status[s]}")
        if open_rows:
            print("  open by severity: "
                  + "  ".join(f"{k}:{v}" for k, v in sorted(open_by_sev.items())))
            print("  open by face: "
                  + "  ".join(f"{k}:{v}" for k, v in sorted(open_by_face.items())))
        print("  verdict: " + "  ".join(f"{k}:{v}" for k, v in by_verdict.items()))
        if not open_rows:
            target = f"\"{args.article}\"" if args.article else "the project"
            print(f"0 open finding(s) — nothing unresolved for {target}")
        return 0

    # ── 預設：彙總 ──
    rows = []
    for f in all_findings(layout, leaves):
        if args.list_article and f.get("_store") != f"doc:{args.list_article}":
            continue
        if args.only_open and f.get("status") not in ("open",):
            continue
        if args.list_face and f.get("face") != args.list_face:
            continue
        rows.append(f)

    if args.as_json:
        print(json.dumps({"findings": rows}, ensure_ascii=False, indent=2)); return 0

    if not rows:
        print("audit: no matching findings."); return 0
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    summary = "  ".join(f"{k}:{v}" for k, v in sorted(by_status.items()))
    print(f"audit: {len(rows)} finding(s)  ({summary})\n")
    for r in rows:
        first = (r.get("finding") or "").splitlines()[0][:60]
        tgts = ",".join(str(t) for t in (r.get("targets") or []))
        print(f"  {r['id']:<5} [{r['face']}/{r['severity']}] {r['status']:<8} "
              f"{r.get('_store', ''):<12} → {tgts}")
        print(f"        {first}")
    print("\n(view a single thread: docspec audit show <id>)")
    return 0


def _render_finding(store: str, f: dict) -> None:
    tgts = ", ".join(str(t) for t in (f.get("targets") or []))
    print(f"{f['id']}  [{f['face']}/{f['severity']}]  status: {f['status']}  ({store})")
    print(f"targets: {tgts}")
    if f.get("sot-owner"):
        print(f"sot-owner: {f['sot-owner']}")
    if f.get("verdict"):
        print(f"verdict: {f['verdict']}")
    print()
    print("🔴 finding:")
    print("  " + (f.get("finding") or "").replace("\n", "\n  "))
    if f.get("suggestion"):
        print("\n🔴 suggestion:")
        print("  " + f["suggestion"].replace("\n", "\n  "))
    print("\n── red-team log ──")
    for e in (f.get("log") or []):
        line = f"  r{e.get('round')} [{e.get('actor')}] {e.get('action')}"
        if e.get("status"):
            line += f" → {e['status']}"
        print(line)
        if e.get("note"):
            print("       " + e["note"].replace("\n", "\n       "))
