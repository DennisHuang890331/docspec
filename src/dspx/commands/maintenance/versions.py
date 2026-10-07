"""Read document versions or explicitly relocate legacy history."""
from __future__ import annotations

import argparse
import json
import sys

from dspx.commands._shared import BootstrapError, bootstrap
from dspx.engine import document_versions
from dspx.engine.layout import LayoutError
from dspx.reports.freeze import FreezeError

NAME = "versions"
HELP = "list document versions; migrate legacy history explicitly"


def run(argv: list[str]) -> int:
    migrating = bool(argv and argv[0] == "migrate")
    parser = argparse.ArgumentParser(prog="artispec versions" + (" migrate" if migrating else ""), description=HELP)
    parser.add_argument("article", nargs="?", help="document name (omit = all)")
    parser.add_argument("--json", action="store_true", dest="as_json")
    if migrating:
        parser.add_argument("--dry-run", action="store_true", help="preflight and display moves without writing")
    args = parser.parse_args(argv[1:] if migrating else argv)
    try:
        layout, _ = bootstrap()
        result = (document_versions.migrate(layout, args.article, dry_run=args.dry_run) if migrating
                  else {"schema-version": 1, "versions": document_versions.rows(layout, args.article)})
    except BootstrapError as exc:
        return exc.exit_code
    except (LayoutError, FreezeError, OSError) as exc:
        sys.stderr.write(f"artispec: versions: {exc}\n")
        return 1
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif migrating:
        print("migration preflight (no changes)" if args.dry_run else "document history migration")
        for move in result["moves"]:
            print(f"  {move['from']} -> {move['to']}")
        print(f"  {len(result['moves'])} file(s)")
        for warning in result["diagnostics"]:
            print(f"  note: {warning}")
    else:
        if not result["versions"]:
            print("No frozen document versions.")
        for row in result["versions"]:
            print(f"{row['document']} v{row['version']} [{row['storage']}] — {row['snapshot']}")
            for warning in row["diagnostics"]:
                print(f"  note: {warning}")
        if any(row["storage"] == "legacy" for row in result["versions"]):
            print("Inspect relocation with `artispec versions migrate --dry-run`.")
    return 0
