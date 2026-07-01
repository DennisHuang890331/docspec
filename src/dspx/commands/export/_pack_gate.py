"""逃生口 gate：偵測內建模板包被手改（規則 b＝只用旋鈕；例外 a＝手改要 --allow）。"""

from __future__ import annotations

import sys
from pathlib import Path

from dspx import paths


def _check_pack_integrity(template_dir: Path, is_bundled: bool, allow: bool) -> int:
    """內建模板包完整性 gate（engine 後盾、三家通用）。

    docctrine：格式變動走**驗證過的旋鈕**（rule b）；真要手改內建包＝例外，要人明確 `--allow`
    （rule a）。`--template` 使用者自有包＝合法替換、**跳過此 gate**（is_bundled=False）。

    比 pack 內 `.pack-hashes.json` 基線：不符且無 --allow → 拒（非零、不 build）。基線缺（dev
    源樹未生成）→ 印提示、放行（不破開發流）。誠實：bundled pack 在 site-packages、agent 少在
    cwd，故 hook 只是 defense-in-depth、**此 engine gate 才是真擋**。
    回傳 0＝放行、1＝拒。
    """
    if not is_bundled:
        return 0  # 使用者 --template 包：合法替換，不設限
    baseline = paths.read_pack_baseline(template_dir)
    if baseline is None:
        sys.stderr.write(
            "docspec: ⚠ the bundled template pack has no integrity baseline (.pack-hashes.json) — skipping the tamper gate "
            "(normal in a dev source tree; a release wheel should include it).\n")
        return 0
    live = paths.pack_content_hashes(template_dir)
    changed = sorted(set(baseline) | set(live))
    diffs = [f for f in changed if baseline.get(f) != live.get(f)]
    if not diffs:
        return 0
    verb = "⚠ (--allow: hand-edited pack explicitly allowed)" if allow else "✗"
    sys.stderr.write(
        f"docspec: {verb} the bundled template pack was hand-edited ({len(diffs)} file(s) differ from the baseline): "
        f"{', '.join(diffs[:8])}{' …' if len(diffs) > 8 else ''}\n")
    if allow:
        return 0
    sys.stderr.write(
        "  Make format changes through validated knobs (--format-config; see docspec guide); "
        "to really change the layout, use your own template pack with --template <dir>. To use this hand-edited bundled pack, add --allow.\n")
    return 1
