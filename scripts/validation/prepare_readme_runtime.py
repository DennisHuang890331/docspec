"""Install current and baseline wheels in separate disposable native runtimes."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--wheel", type=Path, required=True)
parser.add_argument("--baseline-wheel", type=Path, required=True)
parser.add_argument("--output-dir", type=Path, required=True)
args = parser.parse_args()
root = args.output_dir.resolve()
root.mkdir(parents=True, exist_ok=False)
env = dict(os.environ)
env.pop("PYTHONPATH", None)
env["PYTHONUTF8"] = "1"
records = []
result_paths = {}
for name, wheel in (("current", args.wheel), ("baseline", args.baseline_wheel)):
    venv = root / name
    commands = [[sys.executable, "-m", "venv", "--without-pip", str(venv)]]
    bindir = venv / ("Scripts" if os.name == "nt" else "bin")
    python = bindir / ("python.exe" if os.name == "nt" else "python")
    uv = shutil.which("uv")
    commands.append(([uv, "pip", "install", "--python", str(python)] if uv else [sys.executable, "-m", "pip", "--python", str(python), "install"])
                    + [str(wheel.resolve()) + "[export]", "pytest"])
    for command in commands:
        result = subprocess.run(command, env=env, capture_output=True, encoding="utf-8", errors="strict")
        records.append({"command": command, "exit": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
        (root / "preparation.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        if result.returncode:
            raise RuntimeError(result.stderr)
    result_paths[name] = {"python": str(python), "cli": str(bindir / ("artispec.exe" if os.name == "nt" else "artispec"))}
print(json.dumps(result_paths, indent=2))
