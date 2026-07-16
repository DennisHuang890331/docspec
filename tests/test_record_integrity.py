"""engine-record-integrity（B1–B6）＋ human-decision-provenance 引擎半（decided-in/notes WARN）
＋三角色紀律投影。全部對應 2026-07-16 壓測 v2 抓到的檔案櫃違規——逐條釘死。"""

from __future__ import annotations

import json

import yaml

from dspx.engine import change as chg
from dspx.engine import store as st
from dspx.commands.change import change as change_cmd
from dspx.commands.corpus import put as put_cmd
from dspx.commands.deliverable import render as render_cmd
from dspx.commands.query import show as show_cmd
from dspx.commands.query import status as status_cmd
from dspx.engine.layout import Layout


def _wl_basic(write_leaf, home):
    write_leaf(home, "g", concept={"id": "sec-root", "title": "Guide", "order": 1,
                                   "status": "stable",
                                   "brief": {"audience": "a", "depth": "d", "breadth": "b"}},
               decisions=[{"id": "dec-1", "kind": "normative", "status": "accepted",
                           "statement": "Use metric units."}])
    write_leaf(home, "g/intro", concept={"id": "sec-intro", "title": "Intro", "order": 1,
                                         "realizes": ["dec-1"]})


def _yaml_file(tmp_path, name, data):
    p = tmp_path / name
    p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                 encoding="utf-8", newline="\n")
    return str(p)


def _inject_prose(home, prose_by_section):
    """對 docs/g/_latest.md 各節 marker 後注入一行散文（ack 需節有散文/帳本記錄）。"""
    import re
    latest = home.parent / "docs" / "g" / "_latest.md"
    txt = latest.read_text(encoding="utf-8")
    for sec, prose in prose_by_section.items():
        pattern = "(<!-- dspx:section " + re.escape(sec) + " -->" + chr(10) + "[^" + chr(10) + "]*" + chr(10) + ")"
        txt = re.sub(pattern, lambda m: m.group(1) + chr(10) + prose + chr(10), txt, count=1)
    latest.write_text(txt, encoding="utf-8", newline=chr(10))


def _baseline_with_prose(home, monkeypatch):
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    _inject_prose(home, {"g": "Guide prose.", "g/intro": "Intro prose."})
    render_cmd.run(["g"])


def _official_concept(home, section):
    layout = Layout(home, "per-article")
    art = st.load_article(st.store_path(layout, section.split("/", 1)[0]), verify=False)
    return art.record_by_path(section).concept


# ── B2 put 身份保全 ─────────────────────────────────────────────────────

def test_put_concept_omission_preserves_identity(make_project, write_leaf, monkeypatch,
                                                 tmp_path, capsys):
    """重 put 沒帶 id/order → 沿用既有值（omission 永不清引擎蓋的身份）、輸出註明。"""
    home = make_project()
    _wl_basic(write_leaf, home)
    monkeypatch.chdir(home.parent)
    src = _yaml_file(tmp_path, "c.yaml", {"title": "Intro v2", "status": "draft",
                                          "concept": "改個說法", "realizes": ["dec-1"]})
    assert put_cmd.run(["g/intro", "concept", src]) == 0
    out = capsys.readouterr().out
    assert "preserved id/order" in out
    c = _official_concept(home, "g/intro")
    assert c["id"] == "sec-intro" and c["order"] == 1     # 身份還在
    assert c["title"] == "Intro v2"                        # 內容真的更新了


def test_put_concept_different_id_refused(make_project, write_leaf, monkeypatch,
                                          tmp_path, capsys):
    """帶不同 id ＝改寫身份 → 拒收、記錄一個 byte 不動。"""
    home = make_project()
    _wl_basic(write_leaf, home)
    monkeypatch.chdir(home.parent)
    src = _yaml_file(tmp_path, "c.yaml", {"id": "sec-other", "title": "Intro", "order": 1,
                                          "status": "draft", "concept": "x"})
    assert put_cmd.run(["g/intro", "concept", src]) == 1
    err = capsys.readouterr().err
    assert "cannot be rewritten" in err and "retire" in err
    assert _official_concept(home, "g/intro")["id"] == "sec-intro"


# ── B3 put group ───────────────────────────────────────────────────────

def test_put_group_creates_meta_and_render_uses_it(make_project, write_leaf, monkeypatch,
                                                   tmp_path, capsys):
    home = make_project()
    write_leaf(home, "g", concept={"id": "sec-root", "title": "Guide", "order": 1,
                                   "brief": {"audience": "a", "depth": "d", "breadth": "b"}})
    write_leaf(home, "g/ops/setup", concept={"id": "sec-setup", "title": "Setup", "order": 1})
    monkeypatch.chdir(home.parent)
    src = _yaml_file(tmp_path, "grp.yaml", {"title": "操作指南", "order": 2})
    assert put_cmd.run(["g/ops", "group", src]) == 0
    layout = Layout(home, "per-article")
    art = st.load_article(st.store_path(layout, "g"), verify=False)
    rec = art.record_by_path("g/ops")
    assert rec is not None and rec.kind == "group" and rec.group["title"] == "操作指南"
    capsys.readouterr()
    render_cmd.run(["g"])
    latest = home.parent / "docs" / "g" / "_latest.md"
    assert "操作指南" in latest.read_text(encoding="utf-8")   # render 用了在地化標題


def test_put_group_refuses_leaf_collision_and_bad_fields(make_project, write_leaf,
                                                         monkeypatch, tmp_path, capsys):
    home = make_project()
    _wl_basic(write_leaf, home)
    monkeypatch.chdir(home.parent)
    src = _yaml_file(tmp_path, "grp.yaml", {"title": "T"})
    assert put_cmd.run(["g/intro", "group", src]) == 1        # leaf 撞名拒
    assert "cannot be both" in capsys.readouterr().err
    bad = _yaml_file(tmp_path, "bad.yaml", {"title": "T", "colour": "red"})
    assert put_cmd.run(["g/ops", "group", bad]) == 1           # 未知欄拒
    assert "unknown group field" in capsys.readouterr().err


# ── B4 realized-by 節輸入聚合 ──────────────────────────────────────────

def test_realized_by_section_aggregates_owned_decisions(make_project, write_leaf,
                                                        monkeypatch, capsys):
    """深耦合節（concept 無人 realize、決策有下游）不再誤報 not-yet-consumed。"""
    home = make_project()
    _wl_basic(write_leaf, home)   # g 擁 dec-1、g/intro realizes dec-1（g 的 concept 沒人 realize）
    monkeypatch.chdir(home.parent)
    assert show_cmd.run(["g", "--realized-by"]) == 0
    out = capsys.readouterr().out
    assert "not-yet-consumed" not in out
    assert "dec-1" in out and "g/intro" in out                # 按決策分組列出下游
    assert show_cmd.run(["dec-1", "--realized-by"]) == 0      # 決策 id 輸入行為不變
    assert "g/intro" in capsys.readouterr().out


# ── B5 roadmap id 跨區唯一 ─────────────────────────────────────────────

def test_roadmap_id_not_reused_after_done(make_project, write_leaf, monkeypatch, capsys):
    from dspx.reports import roadmap as rm
    from dspx.engine.model import load_project
    home = make_project()
    _wl_basic(write_leaf, home)
    monkeypatch.chdir(home.parent)
    layout = Layout(home, "per-article")
    leaves = load_project(layout)
    e1 = rm.add_entry(layout, leaves, kind="task", title="第一件", target="forest")
    assert e1["id"] == "R1"
    rm.mark_done(layout, leaves, e1["id"], note="done") if hasattr(rm, "mark_done") else None
    # done 走 CLI 語義：直接用 reports 層的完成路徑（找不到 helper 就模擬 archive append）
    if not hasattr(rm, "mark_done"):
        from dspx.reports.roadmap import _append_archive, forest_roadmap_archive_path
        from dspx.reports.roadmap import _write_entries, forest_roadmap_path
        _append_archive(forest_roadmap_archive_path(layout),
                        {"id": "R1", "title": "第一件", "note": "done"})
        _write_entries(layout, forest_roadmap_path(layout), [])
    e2 = rm.add_entry(layout, leaves, kind="task", title="第二件", target="forest")
    assert e2["id"] != "R1"                                    # 封存序號永不重發
    assert e2["id"] == "R2"


def test_roadmap_live_archive_collision_warns(make_project, write_leaf, monkeypatch):
    from dspx.reports.roadmap import (_append_archive, forest_roadmap_archive_path)
    from dspx.reports import roadmap as rm
    from dspx.engine.model import load_project
    from dspx.check import run_check
    from dspx.engine.schema import load_schema
    home = make_project()
    _wl_basic(write_leaf, home)
    monkeypatch.chdir(home.parent)
    layout = Layout(home, "per-article")
    leaves = load_project(layout)
    e1 = rm.add_entry(layout, leaves, kind="task", title="活的", target="forest")
    _append_archive(forest_roadmap_archive_path(layout),
                    {"id": e1["id"], "title": "前世的另一件", "note": "done"})
    res = run_check(load_project(layout), load_schema(), layout)
    assert any("exists both live and in roadmap-archive" in w for w in res.warnings)


# ── B6 stale-own 診斷行 ────────────────────────────────────────────────

def test_status_diagnoses_stale_own_with_unchanged_prose(make_project, write_leaf,
                                                         monkeypatch, capsys):
    home = make_project()
    _wl_basic(write_leaf, home)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])                                       # 基準（空散文也入帳）
    latest = home.parent / "docs" / "g" / "_latest.md"
    txt = latest.read_text(encoding="utf-8").replace(
        "<!-- dspx:section g/intro -->", "<!-- dspx:section g/intro -->", 1)
    # 給 g/intro 一行散文再 render（有散文才記指紋）
    import re as _re
    txt = _re.sub(r"(<!-- dspx:section g/intro -->\n[^\n]*\n)",
                  r"\1\nIntro prose here.\n", txt, count=1)
    latest.write_text(txt, encoding="utf-8", newline="\n")
    render_cmd.run(["g"])
    write_leaf.edit(home, "g/intro", concept={"concept": "源料改了"})   # own 變、散文沒動
    capsys.readouterr()
    assert status_cmd.run([]) == 0
    out = capsys.readouterr().out
    assert "stale-own" in out
    assert "prose was not rewritten" in out or "keeps the signal on purpose" in out


# ── B1 verdict 路由 + decided-in + 空 notes WARN（change 一條龍）───────

def test_change_verdicts_land_in_preview_and_official_frozen(make_project, write_leaf,
                                                             monkeypatch, tmp_path, capsys):
    home = make_project()
    _wl_basic(write_leaf, home)
    _baseline_with_prose(home, monkeypatch)
    layout = Layout(home, "per-article")
    official_journal = home / ".ledger" / "g.verdicts.yaml"
    before = official_journal.read_bytes() if official_journal.is_file() else None

    change_cmd.run(["new", "chg-v", "--publish", "advisory"])
    change_cmd.run(["add-target", "chg-v", "sec-intro", "--action", "review"])
    render_cmd.run(["g", "--change", "chg-v"])                    # seed preview
    capsys.readouterr()
    assert render_cmd.run(["g", "--change", "chg-v", "--ack", "g/intro",
                           "--reason", "人已確認：散文合法未變"]) == 0

    change = chg.load_change(layout, "chg-v")
    pv = chg.preview_dir(change.dir) / "g.verdicts.yaml"
    assert pv.is_file()                                            # 落 preview
    entries = yaml.safe_load(pv.read_text(encoding="utf-8")) or []
    assert any(e.get("section") == "g/intro" and e.get("verb") == "ack" for e in entries)
    after = official_journal.read_bytes() if official_journal.is_file() else None
    assert before == after                                         # 官方 journal 凍結

    # review target 判定吃得到 preview verdict（不再永遠 no review verdict）
    statuses = chg.derive_change_status(layout, change, __import__(
        "dspx.engine.schema", fromlist=["load_schema"]).load_schema())
    review = next(s for s in statuses if s.action == "review")
    assert review.done, review.why


def test_decided_in_stamped_in_change_and_dangling_checked(make_project, write_leaf,
                                                           monkeypatch, tmp_path, capsys):
    home = make_project()
    _wl_basic(write_leaf, home)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    change_cmd.run(["new", "chg-d", "--publish", "advisory"])
    change_cmd.run(["add-target", "chg-d", "sec-root", "--action", "revise"])
    src = _yaml_file(tmp_path, "d.yaml", {"entries": [
        {"id": "dec-1", "kind": "normative", "status": "accepted",
         "statement": "Use metric units."},                        # 未變 → 不蓋
        {"id": "dec-2", "kind": "normative", "status": "accepted",
         "statement": "New ruling."},                              # 新 → 蓋
    ]})
    capsys.readouterr()
    assert put_cmd.run(["g", "decisions", src, "--change", "chg-d"]) == 0
    assert "stamped decided-in" in capsys.readouterr().out
    layout = Layout(home, "per-article")
    change = chg.load_change(layout, "chg-d")
    art = chg._load_staging_article(change.dir, "g")
    by_id = {e["id"]: e for e in art.record_by_path("g").decisions}
    assert by_id["dec-2"].get("decided-in") == "chg-d"             # 新條目蓋章
    assert "decided-in" not in by_id["dec-1"]                      # 未變不動

    # dangling decided-in → check ERROR
    from dspx.check import run_check
    from dspx.engine.model import load_project
    from dspx.engine.schema import load_schema
    write_leaf.edit_decision(home, "g", 0, **{"decided-in": "ghost-change"})
    res = run_check(load_project(layout), load_schema(), layout)
    assert any("decided-in points to unknown change" in e for e in res.errors)


def test_decided_in_preserved_when_omitted_and_statement_unchanged(make_project, write_leaf,
                                                                   monkeypatch, tmp_path):
    home = make_project()
    write_leaf(home, "g", concept={"id": "sec-root", "title": "G", "order": 1,
                                   "brief": {"audience": "a", "depth": "d", "breadth": "b"}},
               decisions=[{"id": "dec-1", "kind": "normative", "status": "accepted",
                           "statement": "Rule.", "decided-in": "chg-old"}])
    monkeypatch.chdir(home.parent)
    src = _yaml_file(tmp_path, "d.yaml", {"entries": [
        {"id": "dec-1", "kind": "normative", "status": "accepted", "statement": "Rule."}]})
    assert put_cmd.run(["g", "decisions", src]) == 0
    layout = Layout(home, "per-article")
    art = st.load_article(st.store_path(layout, "g"), verify=False)
    assert art.record_by_path("g").decisions[0].get("decided-in") == "chg-old"   # 保全


def test_archive_warns_on_empty_notes(make_project, write_leaf, monkeypatch, tmp_path, capsys):
    home = make_project()
    _wl_basic(write_leaf, home)
    _baseline_with_prose(home, monkeypatch)
    change_cmd.run(["new", "chg-n", "--publish", "advisory", "--why", "一句話理由"])
    change_cmd.run(["add-target", "chg-n", "sec-intro", "--action", "review"])
    render_cmd.run(["g", "--change", "chg-n"])
    render_cmd.run(["g", "--change", "chg-n", "--ack", "g/intro", "--reason", "人已確認"])
    capsys.readouterr()
    assert change_cmd.run(["archive", "chg-n"]) == 0
    err = capsys.readouterr().err
    assert "human-decision record" in err                          # 空 notes 提醒
    # 有實質 notes 就不吵：下一張 change 寫了 notes 再 archive
    change_cmd.run(["new", "chg-m", "--publish", "advisory", "--why", "理由"])
    change_cmd.run(["add-target", "chg-m", "sec-intro", "--action", "review"])
    layout = Layout(home, "per-article")
    change = chg.load_change(layout, "chg-m")
    chg.notes_path(change.dir).write_text("# 理由\n\n人拍板：維持公制、rationale 記這裡。\n",
                                          encoding="utf-8", newline="\n")
    render_cmd.run(["g", "--change", "chg-m"])
    render_cmd.run(["g", "--change", "chg-m", "--ack", "g/intro", "--reason", "人已確認"])
    capsys.readouterr()
    assert change_cmd.run(["archive", "chg-m"]) == 0
    assert "human-decision record" not in capsys.readouterr().err


# ── 三角色紀律投影（B/C 的 schema/skill 半）────────────────────────────

def test_guide_projects_three_role_discipline(make_project, monkeypatch, capsys):
    from dspx.commands.projection import guide as guide_cmd
    home = make_project()
    monkeypatch.chdir(home.parent)
    assert guide_cmd.run([]) == 0
    out = capsys.readouterr().out
    assert "Per-decision human confirmation" in out               # 逐條確認 step
    assert "Value crystallization self-check" in out              # 裸值自問 step
    assert "NORMATIVE VALUE" in out                               # filing rule 投影


def test_skills_carry_human_ruling_stances():
    from dspx.env.skills import available_skills
    bodies = {s.name: s.body for s in available_skills()}
    dev = bodies["dspx-develop"]
    assert "INDIVIDUAL confirmation" in dev and "notes.md" in dev
    ap = bodies["dspx-apply"]
    assert "after the human rules" in ap or "human's ruling" in ap
    fc = bodies["dspx-factcheck"]
    assert "recommends crystallization" in fc
