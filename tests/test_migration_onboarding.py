"""migration-onboarding：register-legacy（legacy 第二白名單）＋ publish --set-version ＋ guide 投影。"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from dspx.reports import freeze
from dspx.commands.governance import freeze_cmd
from dspx.commands.deliverable import publish as publish_cmd


def _render_and_draft(home, monkeypatch, write_leaf, prose="內文。"):
    """建骨架＋模擬 draft 寫散文（per-article layout）。"""
    from dspx.commands.deliverable import render as render_cmd
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1})
    monkeypatch.chdir(home.parent)
    docs = home.parent / "docs" / "g"
    render_cmd.run(["g"])
    latest = docs / "_latest.md"
    latest.write_text(latest.read_text("utf-8").replace("## 1. X\n", f"## 1. X\n\n{prose}\n"),
                      encoding="utf-8")
    return docs


def _v11(home):
    """跑 lint、回傳 V11 findings（per-article layout）。"""
    import dspx.engine.lint as lint_mod
    from dspx.engine.layout import Layout
    from dspx.engine.model import load_project
    from dspx.engine.schema import load_schema
    layout = Layout(home, "per-article")
    return [f for f in lint_mod.run_lint(layout, load_project(layout), load_schema())
            if f.rule == "V11"]


# ── 2.x 指令面：註冊/可見性/子動詞分派 ─────────────────────────────────


def test_freeze_registered_agent_facing():
    """freeze 進 REGISTRY、不入 HUMAN_COMMANDS（--help 不列、--help-all 可見）。"""
    from dspx.cli import _help_text
    from dspx.commands import HUMAN_COMMANDS, REGISTRY
    assert "freeze" in REGISTRY
    assert REGISTRY["freeze"].NAME == "freeze"
    assert "freeze" not in HUMAN_COMMANDS
    assert "freeze" not in _help_text()
    assert "freeze" in _help_text(show_all=True)


def test_freeze_help_and_unknown_subverb(capsys):
    assert freeze_cmd.run(["--help"]) == 0
    assert "register-legacy" in capsys.readouterr().out
    assert freeze_cmd.run(["bogus"]) == 2          # 未知子動詞 → usage、exit 2
    assert freeze_cmd.run([]) == 2
    assert "Usage:" in capsys.readouterr().err


# ── 6.1–6.3 登記：搬入模式／原地模式／--into ──────────────────────────


def test_register_legacy_move_mode(make_project, write_leaf, monkeypatch):
    """6.1：archive 外來源夾 → 搬進 docs/archive/legacy/<name>/、legacy 表登記齊、V11 乾淨。"""
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1})
    monkeypatch.chdir(home.parent)
    src = home.parent / "old-versions"
    (src / "sub").mkdir(parents=True)
    (src / "a_v2.4.md").write_text("舊版 A", encoding="utf-8")
    (src / "sub" / "b.md").write_text("舊版 B", encoding="utf-8")
    (src / "desktop.ini").write_text("junk", encoding="utf-8")   # 同步垃圾：不登記

    assert freeze_cmd.run(["register-legacy", str(src), "--into", "taichung"]) == 0

    dest = home.parent / "docs" / "archive" / "legacy" / "taichung"
    assert (dest / "a_v2.4.md").read_text("utf-8") == "舊版 A"
    assert (dest / "sub" / "b.md").read_text("utf-8") == "舊版 B"
    legacy = freeze.load_legacy(home)
    assert set(legacy) == {"docs/archive/legacy/taichung/a_v2.4.md",
                           "docs/archive/legacy/taichung/sub/b.md"}
    assert freeze.load_manifest(home) == {}                       # frozen 表不動
    assert freeze.verify(home, home.parent, home.parent / "docs") == []
    assert _v11(home) == []                                       # lint V11 乾淨


def test_register_legacy_in_place_rescue(make_project, write_leaf, monkeypatch):
    """6.2：已在 archive 內（V11 紅）→ 原地登記、V11 清空、檔案未搬動。"""
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1})
    monkeypatch.chdir(home.parent)
    stuck = home.parent / "docs" / "archive" / "legacy" / "x"
    stuck.mkdir(parents=True)
    f = stuck / "old_v1.md"
    f.write_text("手動塞入的歷版", encoding="utf-8")
    assert any(f.rule == "V11" for f in _v11(home))               # 登記前：全紅

    assert freeze_cmd.run(["register-legacy", str(stuck)]) == 0
    assert f.is_file()                                            # 原地、未搬動
    assert "docs/archive/legacy/x/old_v1.md" in freeze.load_legacy(home)
    assert _v11(home) == []


def test_register_legacy_default_name_is_src_tail(make_project, write_leaf, monkeypatch):
    """6.3：--into 缺省 → 目的夾名取 src-dir 尾段。"""
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1})
    monkeypatch.chdir(home.parent)
    src = home.parent / "台中港歷版"
    src.mkdir()
    (src / "f.md").write_text("x", encoding="utf-8")
    assert freeze_cmd.run(["register-legacy", str(src)]) == 0
    assert (home.parent / "docs" / "archive" / "legacy" / "台中港歷版" / "f.md").is_file()


# ── 6.4–6.6 防洗白／竄改／刪除 ─────────────────────────────────────────


def test_register_legacy_collision_rejects_whole_batch(make_project, write_leaf, monkeypatch, capsys):
    """6.4：任一 rel 已在 legacy 表 → 整批拒絕、零寫入（含批內不碰撞檔）。"""
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1})
    monkeypatch.chdir(home.parent)
    stuck = home.parent / "docs" / "archive" / "legacy" / "t"
    stuck.mkdir(parents=True)
    (stuck / "a.md").write_text("A", encoding="utf-8")
    assert freeze_cmd.run(["register-legacy", str(stuck)]) == 0
    before = freeze.load_legacy(home)

    (stuck / "c.md").write_text("C", encoding="utf-8")            # 批內不碰撞的新檔
    capsys.readouterr()
    assert freeze_cmd.run(["register-legacy", str(stuck)]) == 1   # a.md 碰撞 → 整批拒
    err = capsys.readouterr().err
    assert "docs/archive/legacy/t/a.md" in err                    # 列出碰撞路徑
    assert freeze.load_legacy(home) == before                     # 零寫入（c.md 也沒進表）


def test_register_legacy_frozen_collision_rejected(make_project, write_leaf, monkeypatch, capsys):
    """6.4b：與 frozen 表碰撞同拒（不准用 legacy 登記覆蓋 publish 快照紀錄）。"""
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1})
    monkeypatch.chdir(home.parent)
    arch = home.parent / "docs" / "g" / "archive"
    arch.mkdir(parents=True)
    snap = arch / "v1.0.0.md"
    snap.write_text("published", encoding="utf-8")
    freeze.record(home, home.parent, snap)                        # 進 frozen 表

    capsys.readouterr()
    assert freeze_cmd.run(["register-legacy", str(arch)]) == 1    # 原地模式、rel 撞 frozen
    assert "docs/g/archive/v1.0.0.md" in capsys.readouterr().err
    assert freeze.load_legacy(home) == {}


def test_register_legacy_tamper_then_relaunder_refused(make_project, write_leaf, monkeypatch):
    """6.5：已登記 legacy 檔改內容 → V11 ERROR（訊息可辨識 legacy）；重登記洗白 → 拒、竄改仍在。"""
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1})
    monkeypatch.chdir(home.parent)
    stuck = home.parent / "docs" / "archive" / "legacy" / "t"
    stuck.mkdir(parents=True)
    f = stuck / "a.md"
    f.write_text("原始歷版", encoding="utf-8")
    assert freeze_cmd.run(["register-legacy", str(stuck)]) == 0

    f.write_text("竄改後", encoding="utf-8")
    findings = _v11(home)
    assert any("legacy history was tampered with" in x.detail for x in findings)

    assert freeze_cmd.run(["register-legacy", str(stuck)]) == 1   # 洗白被擋
    assert any("legacy history was tampered with" in x.detail for x in _v11(home))


def test_register_legacy_deletion_caught(make_project, write_leaf, monkeypatch):
    """6.6：legacy 表檔案消失 → V11 ERROR（刪除）。"""
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1})
    monkeypatch.chdir(home.parent)
    stuck = home.parent / "docs" / "archive" / "legacy" / "t"
    stuck.mkdir(parents=True)
    f = stuck / "a.md"
    f.write_text("歷版", encoding="utf-8")
    assert freeze_cmd.run(["register-legacy", str(stuck)]) == 0
    f.unlink()
    assert any("legacy history was deleted" in x.detail for x in _v11(home))


# ── 6.7 舊 manifest 相容＋批次單寫 ────────────────────────────────────


def test_old_manifest_without_legacy_key_unchanged(tmp_path):
    """6.7：無 legacy: 鍵的 .freeze.yaml → verify 行為與現行等價；record 不破壞既有面。"""
    home = tmp_path / "docspec"
    home.mkdir()
    arch = tmp_path / "docs" / "g" / "archive"
    arch.mkdir(parents=True)
    snap = arch / "v1.0.0.md"
    snap.write_text("frozen", encoding="utf-8")
    freeze.record(home, tmp_path, snap)
    text = (home / ".freeze.yaml").read_text("utf-8")
    assert "legacy" not in text                                   # 空表不落鍵（位元相容）
    assert freeze.load_legacy(home) == {}
    assert freeze.verify(home, tmp_path, tmp_path / "docs") == []

    snap.write_text("TAMPERED", encoding="utf-8")
    assert any("tampered" in p for _, p in freeze.verify(home, tmp_path, tmp_path / "docs"))


def test_record_preserves_legacy_table(tmp_path):
    """record（publish 路徑）寫 manifest 時保留 legacy 表（兩表平行、互不覆蓋）。"""
    home = tmp_path / "docspec"
    home.mkdir()
    leg = tmp_path / "docs" / "archive" / "legacy" / "t"
    leg.mkdir(parents=True)
    old = leg / "old.md"
    old.write_text("舊", encoding="utf-8")
    freeze.record_legacy(home, tmp_path, [old])

    arch = tmp_path / "docs" / "g" / "archive"
    arch.mkdir(parents=True)
    snap = arch / "v1.0.0.md"
    snap.write_text("new", encoding="utf-8")
    freeze.record(home, tmp_path, snap)                           # publish 登記
    assert "docs/archive/legacy/t/old.md" in freeze.load_legacy(home)
    assert "docs/g/archive/v1.0.0.md" in freeze.load_manifest(home)


def test_record_legacy_single_manifest_write(tmp_path, monkeypatch):
    """D2：整批登記＝manifest 單次寫入（非逐檔全檔重寫）。"""
    home = tmp_path / "docspec"
    home.mkdir()
    leg = tmp_path / "docs" / "archive" / "legacy" / "t"
    leg.mkdir(parents=True)
    files = []
    for i in range(5):
        f = leg / f"v{i}.md"
        f.write_text(f"歷版 {i}", encoding="utf-8")
        files.append(f)
    writes = []
    orig = Path.write_text

    def spy(self, *a, **k):
        if self.name == ".freeze.yaml":
            writes.append(self)
        return orig(self, *a, **k)

    monkeypatch.setattr(Path, "write_text", spy)
    freeze.record_legacy(home, tmp_path, files)
    assert len(writes) == 1
    assert len(freeze.load_legacy(home)) == 5


# ── 6.8 版本鏈隔離 ───────────────────────────────────────────────────


def test_legacy_folder_never_pollutes_version_chain(tmp_path):
    """6.8：legacy 子夾塞含版號字樣檔名 → existing_versions() 掃不到（flat＋per-article）。"""
    from dspx.engine.layout import Layout
    home = tmp_path / "docspec"
    home.mkdir()
    (home / "config.yaml").write_text("language: zh-TW\n", encoding="utf-8")

    flat = Layout(home, "flat")
    leg = tmp_path / "docs" / "archive" / "legacy" / "t"
    leg.mkdir(parents=True)
    (leg / "g_v2.4.0.md").write_text("舊", encoding="utf-8")
    assert flat.existing_versions("g") == []                      # legacy 不入鏈
    (tmp_path / "docs" / "archive" / "g_v1.0.0.md").write_text("新", encoding="utf-8")
    assert flat.existing_versions("g") == [(1, 0, 0)]             # 真快照照常

    per = Layout(home, "per-article")
    leg2 = tmp_path / "docs" / "g" / "archive" / "legacy"
    leg2.mkdir(parents=True)
    (leg2 / "v2.4.0.md").write_text("舊", encoding="utf-8")
    assert per.existing_versions("g") == []


def test_first_publish_after_register_legacy_starts_at_1_0_0(make_project, write_leaf, monkeypatch):
    """6.8b：register 後首次 publish 仍從 1.0.0 起算（existing_versions 不受污染）。"""
    home = make_project()
    docs = _render_and_draft(home, monkeypatch, write_leaf)
    src = home.parent / "舊歷版"
    src.mkdir()
    (src / "g_v2.4.0.md").write_text("pre-docspec", encoding="utf-8")
    assert freeze_cmd.run(["register-legacy", str(src)]) == 0
    assert publish_cmd.run(["g"]) == 0
    assert (docs / "archive" / "v1.0.0.md").is_file()


# ── 6.9 V11 訊息指路 ─────────────────────────────────────────────────


def test_v11_not_registered_message_points_to_migration(make_project, write_leaf, monkeypatch):
    """6.9：未登記訊息含 register-legacy 指路與「留在 archive/ 外」替代路；竄改訊息不加。"""
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1})
    monkeypatch.chdir(home.parent)
    arch = home.parent / "docs" / "archive"
    arch.mkdir(parents=True)
    (arch / "snuck.md").write_text("手動塞入", encoding="utf-8")
    findings = _v11(home)
    assert findings
    detail = findings[0].detail
    assert "docspec freeze register-legacy" in detail
    assert "docs/legacy/" in detail


# ── 6.10–6.14 publish --set-version ──────────────────────────────────


def test_set_version_seeds_chain_then_patch_continues(make_project, write_leaf, monkeypatch):
    """6.10：首次 publish --set-version 2.5.2 → 快照/changelog＝2.5.2、級別欄＝首版；
    下一次 --level patch → 2.5.3（版本鏈續接）。"""
    from dspx.engine.layout import Layout
    home = make_project()
    docs = _render_and_draft(home, monkeypatch, write_leaf, "中文內文第一版。")
    assert publish_cmd.run(["g", "--set-version", "2.5.2"]) == 0
    assert (docs / "archive" / "v2.5.2.md").is_file()
    cl = Layout(home, "per-article").docs_changelog("g").read_text("utf-8")
    assert "2.5.2" in cl and "首版" in cl and "Patch" not in cl

    latest = docs / "_latest.md"
    latest.write_text(latest.read_text("utf-8").replace("第一版", "第二版"), encoding="utf-8")
    assert publish_cmd.run(["g", "--level", "patch"]) == 0
    assert (docs / "archive" / "v2.5.3.md").is_file()


def test_set_version_non_first_refused_zero_writes(make_project, write_leaf, monkeypatch, capsys):
    """6.11：非首次 --set-version → 非零 abort、訊息含 cannot rewrite history、零寫入。"""
    home = make_project()
    docs = _render_and_draft(home, monkeypatch, write_leaf)
    assert publish_cmd.run(["g"]) == 0                            # v1.0.0
    latest = docs / "_latest.md"
    before_latest = latest.read_bytes()
    from dspx.engine.layout import Layout
    changelog = Layout(home, "per-article").docs_changelog("g")
    before_cl = changelog.read_bytes()

    capsys.readouterr()
    assert publish_cmd.run(["g", "--set-version", "9.0.0"]) == 1
    assert "version chain already exists; --set-version cannot rewrite history" \
        in capsys.readouterr().err
    assert latest.read_bytes() == before_latest                   # 零寫入
    assert changelog.read_bytes() == before_cl
    assert not (docs / "archive" / "v9.0.0.md").exists()


@pytest.mark.parametrize("bad", ["v2.5", "2.5", "2.5.x"])
def test_set_version_malformed_refused(make_project, write_leaf, monkeypatch, capsys, bad):
    """6.12：壞 semver → 非零拒絕、不凍結（防版本掃描日後靜默跳過＝斷鏈）。"""
    home = make_project()
    docs = _render_and_draft(home, monkeypatch, write_leaf)
    capsys.readouterr()
    assert publish_cmd.run(["g", "--set-version", bad]) == 1
    assert "semver" in capsys.readouterr().err
    assert not (docs / "archive").exists()


def test_set_version_with_level_hints_level_ineffective(make_project, write_leaf, monkeypatch, capsys):
    """6.13：--set-version＋非預設 --level → 照 set 版發行＋提示 level 對首版無效（不阻擋）。"""
    home = make_project()
    docs = _render_and_draft(home, monkeypatch, write_leaf)
    capsys.readouterr()
    assert publish_cmd.run(["g", "--set-version", "2.5.2", "--level", "major"]) == 0
    err = capsys.readouterr().err
    assert "no effect on the first version" in err and "2.5.2" in err
    assert (docs / "archive" / "v2.5.2.md").is_file()
    assert not (docs / "archive" / "v3.0.0.md").exists()


def test_dry_run_set_version_previews_and_forecasts_refusal(make_project, write_leaf,
                                                            monkeypatch, capsys):
    """6.14：--dry-run --set-version 預覽 seed 版、零寫入；版本鏈已存在 → 預告拒絕、NO-GO。"""
    home = make_project()
    docs = _render_and_draft(home, monkeypatch, write_leaf)
    capsys.readouterr()
    assert publish_cmd.run(["g", "--dry-run", "--set-version", "2.5.2"]) == 0
    out = capsys.readouterr().out
    assert "version preview: v2.5.2" in out and "dry-run verdict: GO" in out
    assert not (docs / "archive").exists()                        # 零寫入

    assert publish_cmd.run(["g"]) == 0                            # 真發行 → 鏈存在
    capsys.readouterr()
    assert publish_cmd.run(["g", "--dry-run", "--set-version", "2.5.2", "--allow-noop"]) == 1
    out = capsys.readouterr().out
    assert "--set-version cannot rewrite history" in out
    assert "dry-run verdict: NO-GO" in out
    assert not (docs / "archive" / "v2.5.2.md").exists()


# ── 6.15 guide 投影＋skill stance ─────────────────────────────────────


def test_guide_projects_migration_recipe(make_project, monkeypatch, capsys):
    """6.15a：docspec guide 輸出遷移配方區塊，三步依序（register-legacy → 預種沿革 → --set-version）。"""
    from dspx.commands.projection import guide
    home = make_project()
    monkeypatch.chdir(home.parent)
    assert guide.run([]) == 0
    out = capsys.readouterr().out
    assert "Migration onboarding" in out                          # 含 ToC 條目＋區塊
    i1 = out.index("freeze register-legacy")
    i2 = out.index("revision history")
    i3 = out.index("--set-version")
    assert i1 < i2 < i3                                           # 三步依序


def test_guide_json_carries_migration(make_project, monkeypatch, capsys):
    import json
    from dspx.commands.projection import guide
    home = make_project()
    monkeypatch.chdir(home.parent)
    assert guide.run(["--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    steps = data["workflow"]["migration"]["steps"]
    assert len(steps) == 3 and "register-legacy" in steps[0] and "--set-version" in steps[2]


def test_guide_omits_migration_when_schema_lacks_key(make_project, monkeypatch, capsys):
    """6.15b：schema 缺 workflow.migration 鍵 → guide 正常輸出、無遷移區塊、不報錯。"""
    import dataclasses
    from dspx.commands.projection import guide
    from dspx.engine.schema import load_schema
    s = load_schema()
    wf = {k: v for k, v in s.workflow.items() if k != "migration"}
    stripped = dataclasses.replace(s, workflow=wf)
    monkeypatch.setattr(guide, "load_engine_schema", lambda _config: stripped)
    home = make_project()
    monkeypatch.chdir(home.parent)
    assert guide.run([]) == 0
    out = capsys.readouterr().out
    assert "Migration onboarding" not in out
    assert "Workflow (loop)" in out                               # 其餘照印


def test_publish_skill_carries_migration_stance():
    """6.15c：dspx-publish SKILL.md 帶遷移 stance、機制細節指向 docspec guide（不重抄旗標）。"""
    from dspx.env.skills import available_skills
    skill = next(s for s in available_skills() if s.name == "dspx-publish")
    text = skill.source.read_text("utf-8")
    assert "Migrating an existing project" in text
    assert "Migration onboarding" in text and "docspec guide" in text
    assert "--set-version" not in text                            # 旗標不重抄（會漂移）
    assert "register-legacy" not in text
