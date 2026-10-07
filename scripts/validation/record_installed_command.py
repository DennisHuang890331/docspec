"""Record actual installed CLI calls (or explicit environment setup commands).

Evaluator-side config is outside the project. No source import or PYTHONPATH
injection is allowed. Use: python recorder.py --config config.json -- <args>.
Use --exec after the separator for an explicit installer or hook command.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from workflow_runtime import record_command


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("args", nargs=argparse.REMAINDER)
    opts = parser.parse_args()
    args = opts.args[1:] if opts.args[:1] == ["--"] else opts.args
    config = json.loads(opts.config.read_text(encoding="utf-8"))
    executable = Path(config["executable"])
    command = args[1:] if args[:1] == ["--exec"] else [str(executable), *args]
    if not command:
        parser.error("a command is required")
    env = dict(os.environ)
    env.update(config.get("environment", {}))
    env["PYTHONPATH"] = None
    env["PYTHONUTF8"] = "1"
    env["PATH"] = str(executable.parent) + os.pathsep + env.get("PATH", "")
    stdin = sys.stdin.read() if config.get("stdin") else None
    row = record_command(command, cwd=config["project"], log=config["log"],
                         phase=config.get("phase", "unspecified"),
                         session=os.environ.get("CODEX_THREAD_ID") or
                         os.environ.get("DOCSPEC_ACTOR_ID") or config.get("session"),
                         env=env, input=stdin, metadata={"source_entrypoint": False})
    sys.stdout.write(row["stdout"])
    sys.stderr.write(row["stderr"])
    return row["exit"]


if __name__ == "__main__":
    raise SystemExit(main())
