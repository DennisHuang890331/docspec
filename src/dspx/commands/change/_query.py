"""Shared read-only change list/show and explicit legacy migration."""
import argparse
import json
import sys
import yaml

from dspx.commands._shared import BootstrapError, bootstrap, load_engine_schema
from dspx.engine import change_catalog, change
from dspx.engine.software.io import SoftwareError
from dspx.engine.model import ModelError


def _text(value, depth=1):
    """Render the shared result without dropping multiline reasons or identifiers."""
    prefix = "  " * depth
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                print(f"{prefix}{key}:")
                _text(item, depth + 1)
            else:
                print(f"{prefix}{key}: {item}")
    elif isinstance(value, list):
        if not value:
            print(f"{prefix}(none)")
        for item in value:
            if isinstance(item, (dict, list)):
                print(f"{prefix}-")
                _text(item, depth + 1)
            else:
                print(f"{prefix}- {item}")


def run(argv):
    operation = argv[0] if argv and argv[0] in ("list", "show", "migrate") else "list"
    rest = argv[1:] if argv and argv[0] == operation else argv
    parser = argparse.ArgumentParser(prog=f"artispec change {operation}")
    parser.add_argument("--json", action="store_true")
    if operation == "show":
        parser.add_argument("id")
    elif operation == "migrate":
        parser.add_argument("--dry-run", action="store_true")
    else:
        parser.add_argument("--all", action="store_true", help="include archived and abandoned changes")
    args = parser.parse_args(rest)
    try:
        layout, config = bootstrap()
        if operation == "migrate":
            result = {"schema-version": 1, "dry-run": args.dry_run,
                      "moves": change_catalog.migrate(layout, dry_run=args.dry_run)}
        else:
            catalog = change_catalog.entries(layout)
            schema = load_engine_schema(config)
            if operation == "show":
                entry = next((e for e in catalog if e.id == args.id), None)
                if entry is None:
                    raise SoftwareError(f'no change "{args.id}"')
                result = change_catalog.show(layout, entry, schema)
            else:
                result = {"schema-version": 1, "changes": [change_catalog.show(layout, e, schema)
                          for e in catalog if args.all or e.state == "active"]}
    except BootstrapError as exc:
        return exc.exit_code
    except (ModelError, change.ChangeError, OSError, UnicodeError, yaml.YAMLError,
            ValueError, TypeError, KeyError, AttributeError) as exc:
        sys.stderr.write(f"artispec change: cannot read change records: {exc}\n")
        return 1
    # Both outputs consume the same result; JSON rendering keeps every reason and source.
    if args.json:
        print(json.dumps(result, ensure_ascii=False, default=str))
    elif operation == "migrate":
        print("Migration preview" if args.dry_run else "Migration complete")
        for move in result["moves"]:
            print(f"  {move['from']} -> {move['to']}")
        if not result["moves"]:
            print("  No legacy changes to move.")
    else:
        rows = result["changes"] if operation == "list" else [result]
        if not rows:
            print("No active changes." if not args.all else "No changes.")
        for row in rows:
            print(f"{row['id']} [{row['domain']}, {row['state']}]: {row['summary']}")
            if operation == "show":
                _text(row["details"])
                print("Sources:\n  " + "\n  ".join(row["sources"]))
            for problem in row["diagnostics"]:
                print(f"  ! {problem}")
    return 0
