"""docspec show <id> — payload 下鑽：回某 id 的內容，讓 agent 免開原始檔（省 token）。

配 `impact <id>`（反向圖）＝`show <id>`（正向內容）。
- decision → statement / rationale / rejected / status / supersede 連結
- concept  → concept 一句話 / brief / must_cover / sources
- history  → 結構（statement / retired-in / superseded-by）；散文 rationale 目前在 history.md
  （P2 退場 redesign 會折回 history.yaml entries，屆時這裡直接回 rationale）
"""

from __future__ import annotations

import argparse
import json
import sys

from dspx.commands._shared import BootstrapError, bootstrap, load_model
from dspx.glossary import load_glossary

NAME = "show"
HELP = "Drill down: return an id's payload (decision/concept/history) without opening the source file"


def _read_history_md(section_dir, the_id: str) -> str | None:
    """撈 history.md 的 `## <id>` 段散文（乾淨 id：標題第一個 token＝id；讀到下個 ## 為止）。"""
    path = section_dir / "history.md"
    if not path.is_file():
        return None
    out: list[str] = []
    capturing = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            parts = line[3:].split()
            capturing = bool(parts) and parts[0] == the_id
            continue
        if capturing:
            out.append(line)
    text = "\n".join(out).strip()
    return text or None


def _find(leaves: list, the_id: str, layout=None) -> dict | None:
    # glossary term 下鑽：精瘦索引只投 canonical/bucket/code/aliases_forbidden；
    # 完整 record（含 definition/english）只在這裡按需回。
    if layout is not None:
        for t in load_glossary(layout):
            if str(t.get("id")) == the_id:
                return {"kind": "glossary", "canonical": t.get("canonical"),
                        "bucket": t.get("bucket"), "code": t.get("code"),
                        "english": t.get("english"),
                        "aliases_forbidden": t.get("aliases_forbidden"),
                        "definition": t.get("definition")}
    for leaf in leaves:
        c = leaf.concept or {}
        if str(c.get("id")) == the_id:
            return {"kind": "concept", "section": leaf.section, "title": c.get("title"),
                    "status": c.get("status"), "concept": c.get("concept"),
                    "brief": c.get("brief"), "must_cover": c.get("must_cover"),
                    "sources": c.get("sources"), "realizes": c.get("realizes"),
                    "governedBy": c.get("governed-by")}
        for e in leaf.decisions:
            if str(e.get("id")) == the_id:
                return {"kind": "decision", "section": leaf.section,
                        "decisionKind": e.get("kind"), "status": e.get("status"),
                        "statement": e.get("statement"), "rationale": e.get("rationale"),
                        "rejected": e.get("rejected"), "supersedes": e.get("supersedes"),
                        "supersededBy": e.get("superseded-by"), "decidedIn": e.get("decided-in"),
                        "trace": e.get("trace")}
        for e in leaf.history:
            if str(e.get("id")) == the_id:
                out = {"kind": "history", "section": leaf.section,
                       "historyKind": e.get("kind"), "status": e.get("status"),
                       "statement": e.get("statement"), "retiredIn": e.get("retired-in"),
                       "supersededBy": e.get("superseded-by")}
                if e.get("kind") == "section":
                    out["archive"] = e.get("archive")          # 整節退場：細節＝封存資料夾
                else:
                    out["rationale"] = _read_history_md(leaf.dir, the_id)  # 決策退場：撈 md 散文
                return out
    return None


def _find_section(leaves: list, layout, arg: str) -> dict | None:
    """section 路徑模式（id 查找 miss 後的第二種地址形狀）：回該節身份 payload。

    命中條件＝引數含 `/`，或指到既有非封存 corpus 節資料夾。leaf → conceptId/title/status
    （＝concept.status，非 sync 狀態）/order＋決策 id（statement 截 80 字）＋history id；
    develop-only（尚無 concept.yaml）→ conceptId: null＋note。"""
    section = arg.strip("/")
    if not section:
        return None
    section_dir = layout.section_dir(section)
    dir_hit = section_dir.is_dir() and not layout.is_archived_path(section_dir)
    if "/" not in arg and not dir_hit:
        return None
    for leaf in leaves:
        if leaf.section != section:
            continue
        c = leaf.concept or {}
        return {"kind": "section", "section": section,
                "conceptId": c.get("id"), "title": c.get("title"),
                "status": c.get("status"), "order": c.get("order"),
                "decisions": [{"id": e.get("id"), "status": e.get("status"),
                               "statement": (str(e.get("statement") or ""))[:80]}
                              for e in leaf.decisions],
                "history": [{"id": e.get("id"), "kind": e.get("kind"),
                             "status": e.get("status")} for e in leaf.history]}
    if dir_hit:
        return {"kind": "section", "section": section, "conceptId": None,
                "note": "not yet crystallized (develop-only section: no concept.yaml yet)"}
    return None


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec show", description=HELP)
    parser.add_argument("id", help="id of the decision/concept/retirement, or a section path")
    parser.add_argument("--json", action="store_true", dest="as_json", help="output as JSON")
    args = parser.parse_args(argv)

    try:
        layout, _config = bootstrap()
        leaves = load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code

    found = _find(leaves, args.id, layout)
    if found is None:
        found = _find_section(leaves, layout, args.id)
    if found is None:
        sys.stderr.write(f"docspec: id or section \"{args.id}\" not found "
                         "(use docspec list to see sections, docspec impact for back-references)\n")
        return 1

    payload = {"id": args.id, **found}
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    where = f" @ {found['section']}" if found.get("section") else ""
    print(f"id: {args.id} ({found['kind']}{where})")
    for k, v in payload.items():
        if k in ("id", "kind", "section") or v in (None, [], {}):
            continue
        print(f"  {k}: {v}")
    return 0
