"""Generate integrity baselines (.pack-hashes.json) for all bundled template packs.

Run this whenever a maintainer intentionally edits a bundled template pack:
  - docspec-typst pack  (template.typ, …)
  - journal-tables.lua  (shared Lua filter)

With no git in this workspace, the baseline is committed into the pack and shipped
in the wheel; `docspec export` recomputes live hashes and refuses a hand-tampered
bundled pack unless `--allow`.

    uv run --no-editable python tools/gen_pack_hashes.py
"""
from __future__ import annotations

import json
from pathlib import Path

from dspx import paths

TEMPLATES = Path(__file__).resolve().parent.parent / "src" / "dspx" / "assets" / "templates"

for pack_name in ("docspec-typst",):
    pack = TEMPLATES / pack_name
    if not pack.is_dir():
        print(f"skip {pack_name} (not found)")
        continue
    hashes = paths.pack_content_hashes(pack)
    out = pack / paths.PACK_HASHES_FILE
    out.write_text(json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(f"wrote {out} ({len(hashes)} files)")
    for k in sorted(hashes):
        print(f"  {k}")
