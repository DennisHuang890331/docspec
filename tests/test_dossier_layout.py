"""article-dossier-layout：一篇一夾案卷化——migrate-layout 遷移、兩位並存 fail-loud、
explorations/ 思考面、投影規則。（活/退場同拓撲已在 test_article_store/retire 測試釘死。）"""

from __future__ import annotations

import yaml

from dspx.commands.corpus import store as store_cmd
from dspx.commands.query import find as find_cmd
from dspx.engine import store as st
from dspx.engine.layout import Layout


def _legacy_flat_project(make_project, write_leaf, home=None):
    """手工造前一代扁平佈局：flat store＋sibling 治理檔＋.ledger 簿記。"""
    from dspx.engine.schema import load_schema
    home = home or make_project()
    # 用 conftest 工廠建（新佈局）再手動搬回舊位＝內容保證合法
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1})
    new_store = home / "corpus" / "g" / "article.yaml"
    (home / "corpus" / "g.yaml").write_text(new_store.read_text(encoding="utf-8"),
                                            encoding="utf-8", newline="")
    new_store.unlink(); new_store.parent.rmdir()
    # sibling 治理檔（密封）＋.ledger 簿記
    from dspx.engine.sealed import write_sealed
    write_sealed(home / "corpus" / "g.audit.yaml", kind="audit", scope="doc:g",
                 revision=1, list_key="findings",
                 items=[{"id": "F1", "face": "logic", "severity": "med", "status": "open",
                         "targets": ["g/x"], "finding": "舊佈局 finding"}])
    ledger_dir = home / ".ledger"
    ledger_dir.mkdir(exist_ok=True)
    (ledger_dir / "g.sections.yaml").write_text("version: 5\nsections: {}\n",
                                                encoding="utf-8", newline="\n")
    (ledger_dir / "g.verdicts.yaml").write_text("- verb: ack\n  section: g/x\n",
                                                encoding="utf-8", newline="\n")
    return home


def test_migrate_layout_moves_everything_and_is_idempotent(make_project, write_leaf,
                                                           monkeypatch, capsys):
    home = _legacy_flat_project(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    assert store_cmd.run(["migrate-layout"]) == 0
    # 全部就位：案卷內定名檔
    assert (home / "corpus" / "g" / "article.yaml").is_file()
    assert (home / "corpus" / "g" / "audit.yaml").is_file()
    assert (home / "corpus" / "g" / "ledger.yaml").is_file()
    assert (home / "corpus" / "g" / "verdicts.yaml").is_file()
    # 舊位清空、.ledger/ 消滅、explorations/ 立家
    assert not (home / "corpus" / "g.yaml").exists()
    assert not (home / "corpus" / "g.audit.yaml").exists()
    assert not (home / ".ledger").exists()
    assert (home / "explorations").is_dir()
    # 內容存活：store 封條有效、audit finding 還在
    art = st.load_article(home / "corpus" / "g" / "article.yaml", verify=True)
    assert art.record_by_path("g/x") is not None
    from dspx.reports.audit import load_doc_audit
    assert load_doc_audit(Layout(home), "g").findings[0]["id"] == "F1"
    # 冪等：再跑一次零動作
    capsys.readouterr()
    assert store_cmd.run(["migrate-layout"]) == 0
    assert "nothing to move" in capsys.readouterr().out


def test_migrate_layout_refuses_both_layouts(make_project, write_leaf, monkeypatch, capsys):
    """兩位並存（新案卷＋舊扁平都有料）＝拒猜真相：migrate-layout 拒收、fsck 點名。"""
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1})   # 新佈局
    new_store = home / "corpus" / "g" / "article.yaml"
    (home / "corpus" / "g.yaml").write_text(new_store.read_text(encoding="utf-8"),
                                            encoding="utf-8", newline="")     # 舊位也放一份
    monkeypatch.chdir(home.parent)
    assert store_cmd.run(["migrate-layout"]) == 1
    assert "BOTH layouts" in capsys.readouterr().err
    capsys.readouterr()
    assert store_cmd.run(["fsck"]) == 1
    assert "BOTH layouts" in capsys.readouterr().err


def test_legacy_flat_layout_still_reads_via_fallback(make_project, write_leaf, monkeypatch,
                                                     capsys):
    """舊佈局 fallback：未遷移專案照常讀（status 綠）——一版期相容。"""
    from dspx.commands.query import status as status_cmd
    home = _legacy_flat_project(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    assert status_cmd.run([]) == 0
    assert "g/x" in capsys.readouterr().out


def test_find_in_explorations(make_project, write_leaf, monkeypatch, capsys):
    """explorations/＝思考級記錄；引擎唯一接點＝find 唯讀搜尋面；check 對它全盲。"""
    from dspx.check import run_check
    from dspx.engine.model import load_project
    from dspx.engine.schema import load_schema
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1})
    exp = home / "explorations"
    exp.mkdir()
    (exp / "2026-07-19-佈局討論.md").write_text(
        "# 佈局討論\n\n人拍板：一篇一夾。[TBD] 這種殘句在這裡完全合法。\n",
        encoding="utf-8", newline="\n")
    monkeypatch.chdir(home.parent)
    capsys.readouterr()
    assert find_cmd.run(["一篇一夾", "--in", "explorations"]) == 0
    out = capsys.readouterr().out
    assert "explorations/2026-07-19-佈局討論.md" in out
    # check 全盲：exploration 內容（含 [TBD]）零 finding
    res = run_check(load_project(Layout(home)), load_schema(), Layout(home))
    assert res.ok and not any("exploration" in w for w in res.warnings)


def test_guide_projects_exploration_rule(make_project, monkeypatch, capsys):
    from dspx.commands.projection import guide as guide_cmd
    home = make_project()
    monkeypatch.chdir(home.parent)
    assert guide_cmd.run([]) == 0
    out = capsys.readouterr().out
    assert "exploration" in out and "NEVER a source of truth" in out


# ── C1/C2（壓測 v3）：change 層 × 案卷世界的兩個接縫 ─────────────────────


def test_c1_brand_new_article_first_put_inside_change(make_project, monkeypatch,
                                                      tmp_path, capsys):
    """C1：全新文章（尚無 store 檔）的首個 put 就該能進 change——doctrine「文件首建決策批＝
    一張 change」；archive 落地時官方 store 檔誕生。不再逼 agent 裸 put 繞凍結。"""
    import yaml as _yaml
    from dspx.commands.change import change as change_cmd
    from dspx.commands.corpus import put as put_cmd
    from dspx.commands.deliverable import render as render_cmd
    from dspx.engine import store as st
    from dspx.engine.layout import Layout
    home = make_project()
    monkeypatch.chdir(home.parent)
    assert change_cmd.run(["new", "chg-birth", "--publish", "advisory"]) == 0
    # 官方連 store 檔都沒有 → add-target create + put --change 都要能走
    assert change_cmd.run(["add-target", "chg-birth", "新文件/簡介", "--action", "create"]) == 0
    cpt = tmp_path / "c.yaml"
    cpt.write_text("title: 簡介\nstatus: draft\nconcept: 首建即在 change 內\n", encoding="utf-8")
    assert put_cmd.run(["新文件/簡介", "concept", str(cpt), "--change", "chg-birth"]) == 0
    layout = Layout(home, "per-article")
    assert not st.legacy_store_path(layout, "新文件").is_file()      # 官方面凍結：尚無官方檔
    assert not layout.article_store("新文件").is_file()
    # render preview + 補散文 → archive 落地 → 官方 store 誕生
    render_cmd.run(["新文件", "--change", "chg-birth"])
    from dspx.engine import change as chg
    change = chg.load_change(layout, "chg-birth")
    pv = chg.preview_dir(change.dir) / "新文件_latest.md"
    txt = pv.read_text(encoding="utf-8")
    pv.write_text(txt.replace("## 1. 簡介", "## 1. 簡介\n\n首建散文。"),
                  encoding="utf-8", newline="\n")
    render_cmd.run(["新文件", "--change", "chg-birth"])
    capsys.readouterr()
    assert change_cmd.run(["archive", "chg-birth"]) == 0
    art = st.load_article(layout.article_store("新文件"), verify=True)   # 官方檔此刻誕生、封條有效
    assert art.record_by_path("新文件/簡介") is not None


def test_c2_group_target_completes_and_preview_order_correct(make_project, write_leaf,
                                                             monkeypatch, tmp_path, capsys):
    """C2：group 進 change 治理——staged group 的 target 可判 done；union preview 的章序
    用 staging 的 order（不再拿官方空值排出顛倒章序）。"""
    import yaml as _yaml
    from dspx.commands.change import change as change_cmd
    from dspx.commands.corpus import put as put_cmd
    from dspx.commands.deliverable import render as render_cmd
    from dspx.engine import change as chg
    from dspx.engine.layout import Layout
    from dspx.engine.schema import load_schema
    home = make_project()
    write_leaf(home, "g", concept={"id": "sec-root", "title": "G", "order": 1,
                                   "brief": {"audience": "a", "depth": "d", "breadth": "b"}})
    write_leaf(home, "g/乙章/末節B", concept={"id": "sec-b", "title": "末節B", "order": 1})
    write_leaf(home, "g/甲章/末節A", concept={"id": "sec-a", "title": "末節A", "order": 1})
    monkeypatch.chdir(home.parent)
    change_cmd.run(["new", "chg-grp", "--publish", "advisory"])
    # staging 內 put group：甲章 order=1、乙章 order=2（字典序會排反——正是 v3 撞的形）
    for sec, meta in (("g/甲章", {"title": "甲章", "order": 1}),
                      ("g/乙章", {"title": "乙章", "order": 2})):
        gf = tmp_path / "grp.yaml"
        gf.write_text(_yaml.safe_dump(meta, allow_unicode=True), encoding="utf-8")
        assert change_cmd.run(["add-target", "chg-grp", sec, "--action", "create"]) == 0
        assert put_cmd.run([sec, "group", str(gf), "--change", "chg-grp"]) == 0
    capsys.readouterr()
    render_cmd.run(["g", "--change", "chg-grp"])
    change = chg.load_change(Layout(home, "per-article"), "chg-grp")
    pv = (chg.preview_dir(change.dir) / "g_latest.md").read_text(encoding="utf-8")
    assert pv.index("甲章") < pv.index("乙章")          # preview 章序照 staging order（不顛倒）
    # group target 判得了 done
    statuses = chg.derive_change_status(Layout(home, "per-article"), change, load_schema())
    by_ref = {s.ref: s for s in statuses}
    assert by_ref["g/甲章"].done and by_ref["g/乙章"].done
