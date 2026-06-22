"""Generate the bundled template pack's integrity baseline (.pack-hashes.json).

Run this whenever a maintainer intentionally edits the bundled docspec-cas pack
(preamble.tex / before.tex / docspec-tables.lua / reference.md / .cls / .sty /
pandoc-data). With no git in this workspace, the baseline is committed into the
pack and shipped in the wheel; `docspec export` recomputes live hashes and refuses
a hand-tampered bundled pack unless `--allow`.

    uv run --no-editable python tools/gen_pack_hashes.py
"""
from __future__ import annotations

import json
from pathlib import Path

from dspx import paths

pack = Path(__file__).resolve().parent.parent / "src" / "dspx" / "assets" / "templates" / "docspec-cas"
hashes = paths.pack_content_hashes(pack)
out = pack / paths.PACK_HASHES_FILE
out.write_text(json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
               encoding="utf-8")
print(f"wrote {out} ({len(hashes)} files)")
for k in sorted(hashes):
    print(f"  {k}")
