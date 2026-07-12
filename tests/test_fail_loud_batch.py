"""corpus-fail-loud-batch：邊界狀態從「靜默綠」變「吵鬧紅/黃」。

覆蓋：docs_layout 封閉 enum、存在性互驗（deliverable-missing/render 拒蓋）、壞帳本隔離拒跑、
group.yaml 入檢入帳、四 loader 友善錯誤、凍結區垃圾白名單、corpus 衛生 WARN、退役三補洞。
"""

from __future__ import annotations

import pytest
import yaml

from dspx.commands.deliverable import render as render_cmd
from dspx.commands.corpus import retire as rs_cmd
from dspx.commands.query import status as status_cmd
from dspx.config import ConfigError, load_config
from dspx.layout import Layout


def _write_prose(latest, heading: str, prose: str) -> None:
    """模擬 draft：在指定標題槽寫散文。"""
    text = latest.read_text(encoding="utf-8")
    latest.write_text(text.replace(f"{heading}\n", f"{heading}\n\n{prose}\n"), encoding="utf-8")


def _rendered_article(make_project, write_leaf, monkeypatch):
    """建好一篇已 render、帳本有散文記錄的文章（a/x）；回傳 (home, layout, latest, ledger)。"""
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1},
               decisions=[{"id": "d1", "kind": "normative", "status": "accepted",
                           "statement": "s"}])
    monkeypatch.chdir(home.parent)
    assert render_cmd.run(["a"]) == 0
    layout = Layout(home)
    latest = layout.docs_latest("a")
    _write_prose(latest, "## 1. X", "已寫散文。")
    assert render_cmd.run(["a"]) == 0
    ledger = layout.docs_ledger("a")
    assert "a/x" in yaml.safe_load(ledger.read_text(encoding="utf-8"))["sections"]
    return home, layout, latest, ledger


# ── 1.1 docs_layout 封閉 enum ───────────────────────────────────────

@pytest.mark.parametrize("bad", ["falt", "Flat", "flat ", " per-article", "peer-article", 1])
def test_docs_layout_invalid_fail_loud(make_project, bad):
    home = make_project(f"docs_layout: '{bad}'\n" if isinstance(bad, str)
                        else f"docs_layout: {bad}\n")
    with pytest.raises(ConfigError) as exc:
        load_config(home)
    msg = str(exc.value)
    assert "flat | per-article" in msg          # 訊息列合法值
    assert str(bad) in msg                       # 訊息含實際值


@pytest.mark.parametrize("good", ["flat", "per-article"])
def test_docs_layout_valid_unchanged(make_project, good):
    home = make_project(f"docs_layout: {good}\n")
    assert load_config(home)["docs_layout"] == good


def test_docs_layout_absent_uses_default(make_project):
    home = make_project("language: zh-TW\n")
    assert load_config(home)["docs_layout"] == "flat"


# ── 1.2 存在性互驗：deliverable-missing / render 拒蓋 ────────────────

def test_status_flags_deliverable_missing(make_project, write_leaf, monkeypatch, capsys):
    import json
    _home, _layout, latest, _ledger = _rendered_article(make_project, write_leaf, monkeypatch)
    latest.unlink()                              # 交付檔被誤刪
    capsys.readouterr()                          # 清掉 render 輸出
    assert status_cmd.run(["--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    row = next(r for r in data["sections"] if r["section"] == "a/x")
    assert row["sync"] == "deliverable-missing"  # 不顯 synced


def test_render_refuses_over_missing_deliverable(make_project, write_leaf, monkeypatch, capsys):
    _home, _layout, latest, ledger = _rendered_article(make_project, write_leaf, monkeypatch)
    before = ledger.read_bytes()
    latest.unlink()
    assert render_cmd.run(["a"]) == 1            # 拒跑
    err = capsys.readouterr().err
    assert "rebaseline" in err and "refusing" in err
    assert ledger.read_bytes() == before         # 帳本一個 byte 都不動
    assert not latest.is_file()                  # 也沒生空骨架


def test_render_rebaseline_rebuilds_missing_deliverable(make_project, write_leaf, monkeypatch):
    _home, layout, latest, _ledger = _rendered_article(make_project, write_leaf, monkeypatch)
    latest.unlink()
    assert render_cmd.run(["a", "--rebaseline"]) == 0
    assert latest.is_file()                      # 顯式旗標＝重生骨架
    data = yaml.safe_load(layout.docs_ledger("a").read_text(encoding="utf-8"))
    assert data["sections"] == {}                # 基準重置（散文已失、無指紋）


# ── 1.3 壞帳本：隔離備份＋拒跑，不靜默重建 ──────────────────────────

def test_render_quarantines_corrupt_ledger_and_refuses(make_project, write_leaf,
                                                       monkeypatch, capsys):
    _home, _layout, latest, ledger = _rendered_article(make_project, write_leaf, monkeypatch)
    latest_before = latest.read_text(encoding="utf-8")
    ledger.write_text("sections: [unclosed\n", encoding="utf-8")   # Drive 截斷式壞檔
    assert render_cmd.run(["a"]) == 1
    err = capsys.readouterr().err
    assert "corrupt" in err and "rebaseline" in err
    backups = list(ledger.parent.glob("*.corrupt-*"))
    assert len(backups) == 1                     # 壞檔改名隔離、供還原/考古
    assert backups[0].read_text(encoding="utf-8") == "sections: [unclosed\n"
    assert not ledger.is_file()                  # 原位已隔離、未被改寫
    assert latest.read_text(encoding="utf-8") == latest_before   # _latest 未動


def test_render_rebaseline_after_corrupt_ledger(make_project, write_leaf, monkeypatch):
    _home, layout, latest, ledger = _rendered_article(make_project, write_leaf, monkeypatch)
    ledger.write_text("sections: [unclosed\n", encoding="utf-8")
    assert render_cmd.run(["a", "--rebaseline"]) == 0
    assert list(ledger.parent.glob("*.corrupt-*"))               # 仍留備份
    data = yaml.safe_load(ledger.read_text(encoding="utf-8"))
    assert "a/x" in data["sections"]             # 以現有交付物散文重建基準


def test_read_ledger_warning_no_longer_claims_next_render_fixes(make_project, capsys):
    from dspx.render import read_ledger
    home = make_project()
    layout = Layout(home)
    led = layout.docs_ledger("g")
    led.parent.mkdir(parents=True, exist_ok=True)
    led.write_text("entries: [unclosed\n", encoding="utf-8")
    assert read_ledger(layout, "g") == {}
    err = capsys.readouterr().err
    assert "rebaseline" in err                   # 指向顯式重建路徑
    assert "until the next" not in err           # 不再宣稱「下次 render 修復」


# ── 2.1 group.yaml 壞檔 stderr 警告（fallback 行為維持） ─────────────

def test_group_yaml_malformed_warns_not_silent(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    write_leaf(home, "guide/part/intro", concept={"id": "c1", "title": "簡介", "order": 1})
    gdir = home / "corpus" / "guide" / "part"
    (gdir / "group.yaml").write_text("title: [unclosed\n", encoding="utf-8")
    monkeypatch.chdir(home.parent)
    assert render_cmd.run(["guide"]) == 0        # 不擋 render
    err = capsys.readouterr().err
    assert "group.yaml" in err and "malformed" in err            # 指名該檔
    text = Layout(home).docs_latest("guide").read_text(encoding="utf-8")
    assert "## 1. Part" in text                  # 標題 fallback＝humanize slug 維持（含章號）


# ── 2.2 check 的 group.yaml 輕量驗證 ────────────────────────────────

def _check_errors(home, write_leaf) -> list[str]:
    from dspx.check import run_check
    from dspx.model import load_project
    from dspx.schema import load_schema
    layout = Layout(home)
    return run_check(load_project(layout), load_schema(None), layout).errors


def test_check_group_yaml_parse_and_types(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "g/part/x", concept={"id": "c1", "title": "X", "order": 1})
    gdir = home / "corpus" / "g" / "part"
    (gdir / "group.yaml").write_text("title: [unclosed\n", encoding="utf-8")
    errs = _check_errors(home, write_leaf)
    assert any("g/part/group.yaml" in e and "parse failed" in e for e in errs)

    (gdir / "group.yaml").write_text("title:\n  - 不是字串\norder: 二\n", encoding="utf-8")
    errs = _check_errors(home, write_leaf)
    assert any("title must be a non-empty string" in e for e in errs)
    assert any("order must be a number" in e for e in errs)


def test_check_group_order_collision_with_sibling(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 2})
    gdir = home / "corpus" / "g" / "part"
    gdir.mkdir(parents=True)
    (gdir / "group.yaml").write_text("title: 第一部\norder: 2\n", encoding="utf-8")
    write_leaf(home, "g/part/y", concept={"id": "c2", "title": "Y", "order": 1})
    errs = _check_errors(home, write_leaf)
    assert any("collides with sibling" in e and "g/x" in e for e in errs)


def test_check_group_yaml_valid_is_green(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "g/part/x", concept={"id": "c1", "title": "X", "order": 1},
               decisions=[{"id": "d1", "kind": "normative", "status": "accepted",
                           "statement": "s"}])
    (home / "corpus" / "g" / "part" / "group.yaml").write_text(
        "title: 第一部\norder: 1\n", encoding="utf-8")
    assert not [e for e in _check_errors(home, write_leaf) if "group.yaml" in e]


# ── 2.3 group.yaml title/order 變動 → 可見信號 ──────────────────────

def test_group_title_change_raises_skeleton_stale_signal(make_project, write_leaf,
                                                         monkeypatch, capsys):
    import json
    home = make_project()
    write_leaf(home, "a/part/x", concept={"id": "c1", "title": "X", "order": 1},
               decisions=[{"id": "d1", "kind": "normative", "status": "accepted",
                           "statement": "s"}])
    gy = home / "corpus" / "a" / "part" / "group.yaml"
    gy.write_text("title: 第一章\norder: 1\n", encoding="utf-8")
    monkeypatch.chdir(home.parent)
    assert render_cmd.run(["a"]) == 0
    capsys.readouterr()                          # 清掉 render 輸出

    # 未改 → 無信號
    assert status_cmd.run(["--json"]) == 0
    assert json.loads(capsys.readouterr().out)["skeletonStale"] == []

    # 改 title → 有信號（人類輸出也提示需 render）
    gy.write_text("title: 改名的一章\norder: 1\n", encoding="utf-8")
    assert status_cmd.run(["--json"]) == 0
    assert json.loads(capsys.readouterr().out)["skeletonStale"] == ["a"]
    assert status_cmd.run([]) == 0
    assert "docspec render a" in capsys.readouterr().out

    # render 後信號清掉
    assert render_cmd.run(["a"]) == 0
    capsys.readouterr()
    assert status_cmd.run(["--json"]) == 0
    assert json.loads(capsys.readouterr().out)["skeletonStale"] == []


# ── 3.1 audit/roadmap/glossary/freeze 壞檔 → 友善錯誤（無 traceback） ─

@pytest.mark.parametrize("relpath,command", [
    ("audit.yaml", "check"),
    ("roadmap.yaml", "check"),
    ("glossary.yaml", "check"),
    (".freeze.yaml", "lint"),
])
def test_truncated_yaml_friendly_error(make_project, write_leaf, monkeypatch, capsys,
                                       relpath, command):
    from dspx import cli
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1},
               decisions=[{"id": "d1", "kind": "normative", "status": "accepted",
                           "statement": "s"}])
    (home / relpath).write_text("findings: [truncated by drive\n", encoding="utf-8")
    monkeypatch.chdir(home.parent)
    rc = cli.main([command])
    err = capsys.readouterr().err
    assert rc == 1                               # 非零離開碼
    assert "docspec:" in err and relpath in err  # 一行友善錯誤、含路徑
    assert "Traceback" not in err


# ── 3.2 凍結區同步垃圾白名單 ────────────────────────────────────────

def test_freeze_verify_whitelists_sync_junk(tmp_path):
    from dspx import freeze
    home = tmp_path / "docspec"
    docs = tmp_path / "docs"
    archive = docs / "archive"
    archive.mkdir(parents=True)
    home.mkdir()
    for junk in ("desktop.ini", "Thumbs.db", ".DS_Store", "~$report.docx",
                 "a_v1.0.0.md.tmp.drive123"):
        (archive / junk).write_text("junk", encoding="utf-8")
    (archive / "rogue.md").write_text("手動塞進凍結區", encoding="utf-8")
    problems = freeze.verify(home, tmp_path, docs)
    assert [p for p, _ in problems] == ["docs/archive/rogue.md"]   # 垃圾不報、.md 照報


# ── 4. corpus 衛生 WARN ─────────────────────────────────────────────

def _check_warnings(home) -> list[str]:
    from dspx.check import run_check
    from dspx.model import load_project
    from dspx.schema import load_schema
    layout = Layout(home)
    return run_check(load_project(layout), load_schema(None), layout).warnings


def test_hygiene_conflict_copies_warn(make_project, write_leaf):
    home = make_project()
    leaf = write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    (leaf / "concept (1).yaml").write_text("id: c1\n", encoding="utf-8")
    (leaf / "material.md.tmp.drive007").write_text("tmp", encoding="utf-8")
    (home / "corpus" / "a" / "scope (1)").mkdir()
    warns = _check_warnings(home)
    assert any("concept (1).yaml" in w and "sync-conflict copy" in w for w in warns)
    assert any("material.md.tmp.drive007" in w for w in warns)
    assert any("scope (1)" in w and "folder" in w for w in warns)


def test_hygiene_dead_folder_warns(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    dead = home / "corpus" / "a" / "concpet-typo"        # 拼錯字的死資料夾
    dead.mkdir()
    (dead / "material.md").write_text("- 只有素材\n", encoding="utf-8")
    warns = _check_warnings(home)
    assert any("concpet-typo" in w and "dead folder" in w for w in warns)


def test_hygiene_no_false_positives(make_project, write_leaf):
    home = make_project()
    leaf = write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    (leaf / "assets").mkdir()
    (leaf / "assets" / "fig.png").write_bytes(b"png")     # 慣例 assets 夾＝非死資料夾
    dev = home / "corpus" / "a" / "wip"
    dev.mkdir()
    (dev / "develop.md").write_text("施工中\n", encoding="utf-8")   # develop-only 不誤傷
    parent_only = home / "corpus" / "a"                   # 有有效後代的中繼夾不誤傷
    assert parent_only.is_dir()
    archive = home / "corpus" / "_archive" / "old (1)"    # 隱形區不掃
    archive.mkdir(parents=True)
    assert _check_warnings(home) == []


# ── 5.1 退役 id 撞號拒絕 ────────────────────────────────────────────

def test_retire_rejects_id_collision_with_archive(make_project, write_leaf,
                                                  monkeypatch, capsys):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    write_leaf(home, "a/keep", concept={"id": "c9", "title": "K", "order": 9})
    monkeypatch.chdir(home.parent)
    assert rs_cmd.run(["a/x"]) == 0
    # 原路徑重建同 id 節（台中港式路徑重用）
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X2", "order": 1})
    capsys.readouterr()
    assert rs_cmd.run(["a/x"]) == 1              # 拒絕
    err = capsys.readouterr().err
    assert "c1" in err and "_archive" in err     # 指出撞號 id 與封存位置
    assert (home / "corpus" / "a" / "x").is_dir()          # 沒被搬走
    # 換新 id 就放行
    write_leaf(home, "a/x", concept={"id": "c1b", "title": "X2", "order": 1})
    (home / "corpus" / "_archive" / "a__x").rename(
        home / "corpus" / "_archive" / "a__x-old")         # 讓 dest 空出（扁平名另案）
    assert rs_cmd.run(["a/x"]) == 0


# ── 5.2 退役前反向引用警告（不擋） ──────────────────────────────────

def test_retire_warns_on_audit_and_roadmap_back_references(make_project, write_leaf,
                                                           monkeypatch, capsys):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    write_leaf(home, "a/keep", concept={"id": "c9", "title": "K", "order": 9})
    (home / "corpus" / "a" / "audit.yaml").write_text(yaml.safe_dump({"findings": [
        {"id": "F1", "face": "logic", "severity": "med", "status": "open",
         "targets": ["a/x"], "finding": "指著待退節"},
    ]}, allow_unicode=True), encoding="utf-8")
    (home / "roadmap.yaml").write_text(yaml.safe_dump({"entries": [
        {"id": "r1", "kind": "task", "target": "c1"},
        {"id": "r2", "kind": "task", "target": "a/keep"},
    ]}, allow_unicode=True), encoding="utf-8")
    monkeypatch.chdir(home.parent)
    assert rs_cmd.run(["a/x"]) == 0              # 警告不擋、照常退役
    err = capsys.readouterr().err
    assert "F1" in err and "r1" in err           # 逐條列出將變死的引用
    assert "r2" not in err                        # 沒指著待退子樹的不列
    assert not (home / "corpus" / "a" / "x").exists()      # 退役完成


# ── 5.3 整篇退役搬遷交付檔＋帳本 ────────────────────────────────────

def test_whole_article_retire_migrates_deliverable_and_ledger(make_project, write_leaf,
                                                              monkeypatch, capsys):
    home, layout, latest, ledger = _rendered_article(make_project, write_leaf, monkeypatch)
    assert rs_cmd.run(["a/x"]) == 0              # a 只有一節 → 整篇退場
    dest = home / "corpus" / "_archive" / "a__x"
    assert not latest.exists() and not ledger.exists()     # docs/.ledger 無殘留
    assert (dest / latest.name).is_file()                   # 散文隨封存包
    assert (dest / ledger.name).is_file()                   # 帳本隨封存包
    assert "已寫散文。" in (dest / latest.name).read_text(encoding="utf-8")
    out = capsys.readouterr().out
    assert "whole article" in out


def test_partial_retire_keeps_deliverable(make_project, write_leaf, monkeypatch):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    write_leaf(home, "a/y", concept={"id": "c2", "title": "Y", "order": 2})
    monkeypatch.chdir(home.parent)
    assert render_cmd.run(["a"]) == 0
    latest = Layout(home).docs_latest("a")
    assert rs_cmd.run(["a/x"]) == 0              # 還有 a/y 活著 → 非整篇退場
    assert latest.is_file()                      # 交付檔留在 docs/
