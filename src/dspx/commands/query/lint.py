"""docspec lint — 交付物潔淨度報告（單跑不擋；publish 時 ERROR 級當閘）。

article 引數＝輸出過濾（lint 永遠跑全模型——縮輸入 leaves 會廢掉 V1 的跨文件 id 洩漏
偵測＝false green）。歸屬契約（Decision 5）：對 `where` 的**檔案路徑段**做前綴比對——
第一個 ` § ` 起是章節定位器、歸屬時必須忽略；絕不對 `docs/<article>/_latest.md`
做全字串相等比對。歸不到任何已知 article 的 finding（forest roadmap、封存區…）
永遠保留——scope 只會多顯示、不會藏專案級問題。
"""

from __future__ import annotations

import argparse
import json
import sys

from dspx.commands._shared import BootstrapError, bootstrap, load_engine_schema, load_model
from dspx.engine.lint import ERROR, run_lint

NAME = "lint"
HELP = "deliverable cleanliness (leaked ids/anchors/scaffolding/[TBD], material chunking)"


def _finding_article(where: str, known_articles: set[str]) -> str | None:
    """finding 歸屬：`where` 的檔案路徑段（` § ` 前）屬於哪個 article。

    A 命中 iff 路徑以 `docs/{A}/` 或 `corpus/{A}/` 開頭、或首段＝A；
    比對永遠是前綴/首段，絕非全字串相等。歸不到 → None（scoping 永遠保留）。"""
    path = where.split(" § ", 1)[0]
    for prefix in ("docs/", "corpus/"):
        if path.startswith(prefix):
            seg = path[len(prefix):].split("/", 1)[0]
            return seg if seg in known_articles else None
    seg = path.split("/", 1)[0]
    return seg if seg in known_articles else None


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="docspec lint", description=HELP)
    parser.add_argument("article", nargs="?", default=None,
                        help="scope findings to this article (project-level findings stay visible)")
    parser.add_argument("--json", action="store_true", dest="as_json", help="output as JSON")
    args = parser.parse_args(argv)

    try:
        layout, config = bootstrap()
        schema = load_engine_schema(config)
        leaves = load_model(layout)
    except BootstrapError as exc:
        return exc.exit_code

    known = {lf.article for lf in leaves}
    if args.article:
        if args.article not in known:
            sys.stderr.write(f"docspec: no leaf sections found for article \"{args.article}\"\n")
            return 1

    findings = run_lint(layout, leaves, schema)
    if args.article:
        findings = [f for f in findings
                    if _finding_article(f.where, known) in (args.article, None)]
    errors = [f for f in findings if f.level == ERROR]

    if args.as_json:
        print(json.dumps({
            "errorCount": len(errors),
            "findings": [{"rule": f.rule, "level": f.level, "where": f.where,
                          "detail": f.detail} for f in findings],
        }, ensure_ascii=False, indent=2))
        return 0

    if not findings:
        print("lint: clean (no issues).")
        return 0
    print(f"lint: {len(findings)} issue(s) (ERROR {len(errors)})")
    for f in findings:
        mark = "✗" if f.level == ERROR else "⚠"
        print(f"  {mark} [{f.rule} {f.level}] {f.where}: {f.detail}")
    return 0
