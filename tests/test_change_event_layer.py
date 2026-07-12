"""change-event-layer：修改事件層（容器/暫存/union view/收案）測試。

反作弊核心（brief）：3.1b（入單前就 synced／未標髒 → MUST 不導出 done）與 2.2b（G2：只改一節
→ 該節 stale、其餘每節顯示原有散文且 synced）斷言的是真案子——不挑軟柿子。
"""

from __future__ import annotations

import re

import pytest
import yaml

from dspx.engine import change as chg
from dspx.engine import store as st
from dspx.commands.change import change as change_cmd
from dspx.commands.deliverable import render as render_cmd
from dspx.commands.corpus import store as store_cmd
from dspx.engine.layout import Layout
from dspx.engine.schema import load_schema


def _project(make_project, write_leaf, monkeypatch=None, backend="tree"):
    """root g（含 normative 決策 dec-1）＋ g/intro（realizes dec-1）＋ g/usage；三節皆寫散文並
    render 記 synced 基準。回傳 planning home。

    backend="store"：建完散檔後 `store migrate g` 收成一篇一檔（★E 雙 backend 參數化——同一批
    change 工作流測試在 tree 與 store 都跑）。own 軸 v5 backend-neutral ⇒ 遷移後帳本仍 synced。"""
    home = make_project()
    write_leaf(home, "g", concept={"id": "sec-root", "title": "Guide", "order": 1,
                                   "status": "stable",
                                   "brief": {"audience": "devs", "depth": "deep", "breadth": "all"}},
               decisions=[{"id": "dec-1", "kind": "normative", "status": "accepted",
                           "statement": "Use metric units."}])
    write_leaf(home, "g/intro", concept={"id": "sec-intro", "title": "Intro", "order": 1,
                                         "realizes": ["dec-1"]})
    write_leaf(home, "g/usage", concept={"id": "sec-usage", "title": "Usage", "order": 2})
    if backend == "store":
        assert monkeypatch is not None, "store backend needs monkeypatch to chdir for migrate"
        monkeypatch.chdir(home.parent)
        assert store_cmd.run(["migrate", "g"]) == 0
        assert st.article_has_store(Layout(home, "per-article"), "g")
    return home


def _latest(home):
    return home.parent / "docs" / "g" / "_latest.md"


def _inject_all(home, prose_by_section):
    """把散文注入每個 marker 後的槽（marker→標題行→空行→散文）。"""
    latest = _latest(home)
    text = latest.read_text(encoding="utf-8")
    lines = text.split("\n")
    out = []
    i = 0
    marker_re = re.compile(r"^<!-- dspx:section (.+?) -->$")
    while i < len(lines):
        out.append(lines[i])
        m = marker_re.match(lines[i])
        if m and m.group(1) in prose_by_section:
            i += 1
            # heading line
            if i < len(lines):
                out.append(lines[i]); i += 1
            # blank
            if i < len(lines) and not lines[i].strip():
                out.append(lines[i]); i += 1
            out.append("")
            out.append(prose_by_section[m.group(1)])
            continue
        i += 1
    latest.write_text("\n".join(out), encoding="utf-8", newline="\n")


def _render_baseline(home, monkeypatch):
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    _inject_all(home, {"g": "This guide uses metric units.",
                       "g/intro": "The intro implements the metric rule.",
                       "g/usage": "Usage details here."})
    render_cmd.run(["g"])


def _load_change(home, cid):
    layout = Layout(home, "per-article")
    return chg.load_change(layout, cid), layout


def _status_map(home, cid):
    change, layout = _load_change(home, cid)
    schema = load_schema()
    return {s.ref: s for s in chg.derive_change_status(layout, change, schema)}


# ── 容器 / 開單門檻 ────────────────────────────────────────────────

def test_new_requires_publish(make_project, write_leaf, monkeypatch, capsys):
    home = _project(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    rc = change_cmd.run(["new", "chg-x", "--seed", "dec-1"])
    assert rc == 2
    assert "requires --publish" in capsys.readouterr().err
    assert chg.change_state(Layout(home, "per-article"), "chg-x") is None


def test_new_creates_container_and_notes(make_project, write_leaf, monkeypatch):
    home = _project(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    assert change_cmd.run(["new", "chg-x", "--publish", "advisory", "--title", "T",
                           "--why", "reason"]) == 0
    layout = Layout(home, "per-article")
    cdir = chg.change_dir(layout, "chg-x")
    assert chg.change_yaml_path(cdir).is_file()
    assert chg.notes_path(cdir).is_file()
    change = chg.load_change(layout, "chg-x")
    assert change.publish == "advisory"
    assert change.title == "T"
    # 無 status 欄
    raw = yaml.safe_load(chg.change_yaml_path(cdir).read_text(encoding="utf-8").split("\n", 1)[1])
    assert "status" not in raw


def test_seed_snapshots_reverse_realizes(make_project, write_leaf, monkeypatch):
    home = _project(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    change_cmd.run(["new", "chg-x", "--seed", "dec-1", "--publish", "advisory"])
    change, _ = _load_change(home, "chg-x")
    refs = {t.ref for t in change.targets}
    assert "sec-intro" in refs   # g/intro realizes dec-1 → auto target
    assert all(t.action == "revise" and t.origin == "auto" for t in change.targets)


# ── 2.2b ★G2：只改一節 → 該節 stale、其餘每節顯示原有散文且 synced ──

def test_g2_preview_seeded_only_changed_section_stale(make_project, write_leaf, monkeypatch):
    home = _project(make_project, write_leaf)
    _render_baseline(home, monkeypatch)
    layout = Layout(home, "per-article")

    # 開單、**只**改一節 g/intro 的決策（改源 → 該節須重寫散文）
    change_cmd.run(["new", "chg-x", "--publish", "advisory"])
    change_cmd.run(["add-target", "chg-x", "sec-intro", "--action", "revise"])
    # 改 staging 副本的 realizes-源：把 g/intro 的 concept 改一下（源變）
    change = chg.load_change(layout, "chg-x")
    staged_intro = chg.staging_target(change.dir, layout, layout.section_dir("g/intro"))
    cpath = staged_intro / "concept.yaml"
    cdata = yaml.safe_load(cpath.read_text(encoding="utf-8"))
    cdata["concept"] = "changed framing"
    cpath.write_text(yaml.safe_dump(cdata, allow_unicode=True, sort_keys=False), encoding="utf-8")

    render_cmd.run(["g", "--change", "chg-x"])
    pv = chg.preview_dir(change.dir) / "g_latest.md"
    ptext = pv.read_text(encoding="utf-8")

    # ★其餘每一節 MUST 顯示其原有散文（seed 生效，未動的節不被誤判 unwritten）
    assert "This guide uses metric units." in ptext        # g 根節原散文在
    assert "Usage details here." in ptext                  # g/usage 原散文在
    assert "The intro implements the metric rule." in ptext  # intro 舊散文仍在（源變、散文待改）

    # preview 側帳本：g 與 g/usage synced（seed），g/intro stale-own（源變）
    from dspx.commands.query.status import _leaf_row
    from dspx.engine.model import decision_index
    pv_ledger = chg._read_preview_ledger(change, "g")
    union = chg.load_union(layout, change)
    by = {lf.section: lf for lf in union}
    overlay = chg.OverlayLayout(layout, change)
    dindex = decision_index(union)
    schema = load_schema()

    def sync(sec):
        return _leaf_row(overlay, by[sec], schema, True, pv_ledger, by, dindex)["sync"]

    assert sync("g") == "synced"          # 未動 → synced（不是 unwritten！）
    assert sync("g/usage") == "synced"    # 未動 → synced
    assert sync("g/intro") == "stale-own"  # 源改 → stale


def test_official_docs_untouched_by_preview(make_project, write_leaf, monkeypatch):
    home = _project(make_project, write_leaf)
    _render_baseline(home, monkeypatch)
    official_before = _latest(home).read_text(encoding="utf-8")
    layout = Layout(home, "per-article")
    change_cmd.run(["new", "chg-x", "--publish", "advisory"])
    change_cmd.run(["add-target", "chg-x", "sec-intro", "--action", "revise"])
    render_cmd.run(["g", "--change", "chg-x"])
    # 正式 docs 零 byte 變化（D2）
    assert _latest(home).read_text(encoding="utf-8") == official_before


# ── 3.1b ★反作弊：入單前就 synced／未標髒 → MUST 不導出 done ──

def _rewrite_preview_prose(home, cid, section, new_prose):
    change, layout = _load_change(home, cid)
    pv = chg.preview_dir(change.dir) / "g_latest.md"
    text = pv.read_text(encoding="utf-8")
    # 換掉該節現有散文（marker 後）
    text = re.sub(r"(<!-- dspx:section " + re.escape(section) + r" -->\n[^\n]*\n\n)[^\n]*",
                  lambda m: m.group(1) + new_prose, text, count=1)
    pv.write_text(text, encoding="utf-8", newline="\n")


def test_anticheat_synced_without_work_is_not_done(make_project, write_leaf, monkeypatch):
    """★對抗（3.1b）：一個 revise target，apply 期**零工作**（散文從未重寫）→ MUST 不 done。
    即使有人手動把 preview 帳本 re-stamp 成 synced（清 redraft、蓋現值），散文仍 byte 等於正式
    baseline → prose-guard 擋下，導出仍非 done。單看『當下 synced』不足以證明本單做過事。"""
    home = _project(make_project, write_leaf)
    _render_baseline(home, monkeypatch)
    layout = Layout(home, "per-article")

    change_cmd.run(["new", "chg-x", "--publish", "advisory"])
    change_cmd.run(["add-target", "chg-x", "sec-intro", "--action", "revise"])
    render_cmd.run(["g", "--change", "chg-x"])

    # 入單即標髒 → 現在 stale-own、不 done
    st = _status_map(home, "chg-x")["sec-intro"]
    assert st.done is False

    # 作弊模擬：把 preview 帳本的 g/intro re-stamp 成完全對齊現值（清 redraft）——但**散文一字未改**
    change = chg.load_change(layout, "chg-x")
    pv_ledger = chg._read_preview_ledger(change, "g")
    from dspx.engine.model import decision_index
    union = chg.load_union(layout, change)
    by = {lf.section: lf for lf in union}
    lf = by["g/intro"]
    dindex = decision_index(union)
    from dspx.engine.model import (ancestor_brief_fingerprint, ancestor_normative_fingerprint,
                            deps_fingerprint, style_fingerprint)
    overlay = chg.OverlayLayout(layout, change)
    pv_ledger["g/intro"] = {
        "own": lf.source_hash(),
        "anc": ancestor_brief_fingerprint("g/intro", by),
        "deps": deps_fingerprint(lf, dindex),
        "norm": ancestor_normative_fingerprint("g/intro", by),
        "style": style_fingerprint(overlay),
        "prose": pv_ledger["g/intro"]["prose"],   # 散文指紋不變（沒改散文）
    }
    chg._write_preview_ledger(change, "g", pv_ledger)

    # 現在該節「當下 synced」了，但散文 == 正式 baseline → MUST 仍不 done（prose-guard）
    st2 = _status_map(home, "chg-x")["sec-intro"]
    assert st2.done is False
    assert "prose is byte-identical" in st2.detail or "no work" in st2.detail


def test_contrast_staled_then_rewritten_is_done(make_project, write_leaf, monkeypatch):
    """對照組（3.1b）：入單標髒 → apply 期重渲染成 synced（散文真改）→ MUST 導出 done。"""
    home = _project(make_project, write_leaf)
    _render_baseline(home, monkeypatch)

    change_cmd.run(["new", "chg-x", "--publish", "advisory"])
    change_cmd.run(["add-target", "chg-x", "sec-intro", "--action", "revise"])
    render_cmd.run(["g", "--change", "chg-x"])
    assert _status_map(home, "chg-x")["sec-intro"].done is False

    # 真重寫 preview 散文 → render --change 記 synced（prose 變）
    _rewrite_preview_prose(home, "chg-x", "g/intro", "The intro now uses imperial units.")
    render_cmd.run(["g", "--change", "chg-x"])
    st = _status_map(home, "chg-x")["sec-intro"]
    assert st.done is True
    assert "rewritten" in st.detail


# ── ★8.1 P0 靜默資料遺失回歸：旁節逐 byte 存活、leaf 計數不減 ──────

def _leaf_count(home):
    from dspx.engine.model import load_project
    return len(load_project(Layout(home, "per-article")))


def test_p0_bystander_survives_when_parent_root_staged(make_project, write_leaf, monkeypatch):
    """★P0（8.1）：change enlist 根節 g（owner）＋子節 g/intro，旁節 g/usage **未 enlist**。
    收案後 g/usage 在 corpus＋交付物逐 byte 存活、leaf 計數不減。舊 bug（父子樹刪除語義）會
    在 land 根節時 rmtree 整個 g/ 資料夾、連 g/usage 一起刪掉（4→3 或 3→2）。"""
    home = _project(make_project, write_leaf)
    _render_baseline(home, monkeypatch)
    layout = Layout(home, "per-article")

    # 旁節 g/usage 的收案前狀態（corpus 源 + 交付物散文）
    usage_concept_before = (home / "corpus" / "g" / "usage" / "concept.yaml").read_bytes()
    latest_before = _latest(home).read_text(encoding="utf-8")
    assert "Usage details here." in latest_before
    leaves_before = _leaf_count(home)

    # seed dec-1 → 8.2 auto-enlist owner(g) + realizes(g/intro)；g/usage 是旁節
    change_cmd.run(["new", "chg-x", "--seed", "dec-1", "--publish", "advisory"])
    change, _ = _load_change(home, "chg-x")
    refs = {t.ref for t in change.targets}
    assert "sec-root" in refs and "sec-intro" in refs   # 8.2: root owner enlisted
    assert "sec-usage" not in refs                       # bystander NOT enlisted

    render_cmd.run(["g", "--change", "chg-x"])
    _rewrite_preview_prose(home, "chg-x", "g", "Root prose rewritten.")
    _rewrite_preview_prose(home, "chg-x", "g/intro", "Intro prose rewritten.")
    render_cmd.run(["g", "--change", "chg-x"])
    st = _status_map(home, "chg-x")
    assert st["sec-root"].done and st["sec-intro"].done

    assert change_cmd.run(["archive", "chg-x"]) == 0

    # ★旁節 g/usage 逐 byte 存活（corpus）＋交付物散文仍在＋leaf 計數不減
    assert (home / "corpus" / "g" / "usage" / "concept.yaml").read_bytes() == usage_concept_before
    final = _latest(home).read_text(encoding="utf-8")
    assert "Usage details here." in final
    assert _leaf_count(home) == leaves_before
    # 兩個 target 的新散文有落地
    assert "Root prose rewritten." in final and "Intro prose rewritten." in final


def test_p0_bystander_survives_when_only_leaf_staged(make_project, write_leaf, monkeypatch):
    """★P0（8.1）A/B 對照：只 enlist 一個子葉 g/intro（父/根不進暫存），旁節 g/usage 仍存活。"""
    home = _project(make_project, write_leaf)
    _render_baseline(home, monkeypatch)
    usage_before = (home / "corpus" / "g" / "usage" / "concept.yaml").read_bytes()
    leaves_before = _leaf_count(home)

    change_cmd.run(["new", "chg-x", "--publish", "advisory"])
    change_cmd.run(["add-target", "chg-x", "sec-intro", "--action", "revise"])
    render_cmd.run(["g", "--change", "chg-x"])
    _rewrite_preview_prose(home, "chg-x", "g/intro", "Only intro changed.")
    render_cmd.run(["g", "--change", "chg-x"])
    assert change_cmd.run(["archive", "chg-x"]) == 0

    assert (home / "corpus" / "g" / "usage" / "concept.yaml").read_bytes() == usage_before
    assert "Usage details here." in _latest(home).read_text(encoding="utf-8")
    assert _leaf_count(home) == leaves_before


def test_82_seed_enlists_decision_owner(make_project, write_leaf, monkeypatch):
    """★8.2：seed 一條由根節擁有的頂層決策 → 根節（owner）在 auto targets 內、無需手動 add。"""
    home = _project(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    change_cmd.run(["new", "chg-x", "--seed", "dec-1", "--publish", "advisory"])
    change, _ = _load_change(home, "chg-x")
    owner = change.target_by_ref("sec-root")
    assert owner is not None and owner.origin == "auto"


def test_84_remove_target_unblocks(make_project, write_leaf, monkeypatch):
    """★8.4：remove-target 丟棄該 target staging＋自 change 移除、不再卡導出完成度。"""
    home = _project(make_project, write_leaf)
    _render_baseline(home, monkeypatch)
    layout = Layout(home, "per-article")
    change_cmd.run(["new", "chg-x", "--publish", "advisory"])
    change_cmd.run(["add-target", "chg-x", "sec-intro", "--action", "revise"])
    change_cmd.run(["add-target", "chg-x", "sec-usage", "--action", "revise"])
    render_cmd.run(["g", "--change", "chg-x"])
    _rewrite_preview_prose(home, "chg-x", "g/intro", "Intro rewritten.")
    render_cmd.run(["g", "--change", "chg-x"])
    # sec-usage 未做工 → 卡 archivable
    assert change_cmd.run(["archive", "chg-x"]) == 1
    # 移除誤納的 sec-usage → 只剩 sec-intro（已 done）→ archivable
    assert change_cmd.run(["remove-target", "chg-x", "sec-usage"]) == 0
    change = chg.load_change(layout, "chg-x")
    assert change.target_by_ref("sec-usage") is None
    assert change.target_by_ref("sec-intro") is not None
    assert change_cmd.run(["archive", "chg-x"]) == 0
    assert chg.change_state(layout, "chg-x") == "archived"


def test_85_archived_status_shows_terminal(make_project, write_leaf, monkeypatch, capsys):
    home = _project(make_project, write_leaf)
    _render_baseline(home, monkeypatch)
    change_cmd.run(["new", "chg-x", "--publish", "advisory"])
    change_cmd.run(["archive", "chg-x", "--abandon", "--reason", "nope"])
    capsys.readouterr()
    change_cmd.run(["status", "chg-x"])
    out = capsys.readouterr().out
    assert "ABANDONED" in out and "not archivable" not in out


# ── 收案 / 棄案 / fork 漂移 ────────────────────────────────────────

@pytest.mark.parametrize("backend", ["tree", "store"])
def test_archive_lands_and_prunes(make_project, write_leaf, monkeypatch, backend):
    """★E 雙 backend：同一 revise→archive 工作流在散檔與 store 都綠（docs 落地判準 backend-無關）。"""
    home = _project(make_project, write_leaf, monkeypatch, backend)
    _render_baseline(home, monkeypatch)
    layout = Layout(home, "per-article")

    change_cmd.run(["new", "chg-x", "--publish", "advisory"])
    change_cmd.run(["add-target", "chg-x", "sec-intro", "--action", "revise"])
    render_cmd.run(["g", "--change", "chg-x"])
    _rewrite_preview_prose(home, "chg-x", "g/intro", "The intro now uses imperial units.")
    render_cmd.run(["g", "--change", "chg-x"])

    assert change_cmd.run(["archive", "chg-x"]) == 0
    # 收案後：正式 _latest 該節換成新散文、其他槽 byte 不動、案卷搬 _archive
    final = _latest(home).read_text(encoding="utf-8")
    assert "imperial units" in final
    assert "Usage details here." in final           # 其他槽 slot-patch 不動
    assert "This guide uses metric units." in final  # 根節不動
    assert chg.change_state(layout, "chg-x") == "archived"


def test_archive_refused_when_not_green(make_project, write_leaf, monkeypatch, capsys):
    home = _project(make_project, write_leaf)
    _render_baseline(home, monkeypatch)
    change_cmd.run(["new", "chg-x", "--publish", "advisory"])
    change_cmd.run(["add-target", "chg-x", "sec-intro", "--action", "revise"])
    render_cmd.run(["g", "--change", "chg-x"])   # 無實質重寫 → 未 done
    rc = change_cmd.run(["archive", "chg-x"])
    assert rc == 1
    assert "not archivable" in capsys.readouterr().err
    assert chg.change_state(Layout(home, "per-article"), "chg-x") == "active"


def test_abandon_zero_change(make_project, write_leaf, monkeypatch):
    home = _project(make_project, write_leaf)
    _render_baseline(home, monkeypatch)
    layout = Layout(home, "per-article")
    official_before = _latest(home).read_text(encoding="utf-8")
    corpus_before = (home / "corpus" / "g" / "intro" / "concept.yaml").read_text(encoding="utf-8")

    change_cmd.run(["new", "chg-x", "--publish", "advisory"])
    change_cmd.run(["add-target", "chg-x", "sec-intro", "--action", "revise"])
    # 動 staging 副本
    change = chg.load_change(layout, "chg-x")
    sp = chg.staging_target(change.dir, layout, layout.section_dir("g/intro")) / "concept.yaml"
    sp.write_text(sp.read_text(encoding="utf-8") + "\n# scribble\n", encoding="utf-8")

    assert change_cmd.run(["archive", "chg-x", "--abandon", "--reason", "wrong direction"]) == 0
    assert chg.change_state(layout, "chg-x") == "abandoned"
    # 正式面零 byte 變化
    assert _latest(home).read_text(encoding="utf-8") == official_before
    assert (home / "corpus" / "g" / "intro" / "concept.yaml").read_text(encoding="utf-8") == corpus_before
    # reason 入 change.yaml
    ac = chg.load_change(layout, "chg-x")
    assert ac.abandoned and ac.abandoned["reason"] == "wrong direction"


def test_abandon_requires_reason(make_project, write_leaf, monkeypatch, capsys):
    home = _project(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    change_cmd.run(["new", "chg-x", "--publish", "advisory"])
    rc = change_cmd.run(["archive", "chg-x", "--abandon"])
    assert rc == 2
    assert "requires --reason" in capsys.readouterr().err


def test_fork_drift_guard(make_project, write_leaf, monkeypatch, capsys):
    """fork 後正式 corpus 被零開單直改 → archive 中止、列漂移清單（★#9/D5）。"""
    home = _project(make_project, write_leaf)
    _render_baseline(home, monkeypatch)
    layout = Layout(home, "per-article")

    change_cmd.run(["new", "chg-x", "--publish", "advisory"])
    change_cmd.run(["add-target", "chg-x", "sec-intro", "--action", "revise"])
    render_cmd.run(["g", "--change", "chg-x"])
    _rewrite_preview_prose(home, "chg-x", "g/intro", "imperial now.")
    render_cmd.run(["g", "--change", "chg-x"])

    # 第三方零開單直改正式 corpus 的同節 concept（fork hash 就失配）
    off = home / "corpus" / "g" / "intro" / "concept.yaml"
    off.write_text(off.read_text(encoding="utf-8") + "\n# third-party edit\n", encoding="utf-8")

    rc = change_cmd.run(["archive", "chg-x"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "drift" in err.lower()
    assert chg.change_state(layout, "chg-x") == "active"   # 未落地
    # --override-drift 放行
    assert change_cmd.run(["archive", "chg-x", "--override-drift"]) == 0
    assert chg.change_state(layout, "chg-x") == "archived"


def test_archive_whole_file_route_for_structural_action(make_project, write_leaf, monkeypatch):
    """G5 第二路：含結構性 action（redraft）→ 整份換（正式 _latest 以 preview 全文替換）。"""
    home = _project(make_project, write_leaf)
    _render_baseline(home, monkeypatch)
    change_cmd.run(["new", "chg-r", "--publish", "advisory"])
    change_cmd.run(["add-target", "chg-r", "sec-intro", "--action", "redraft"])
    render_cmd.run(["g", "--change", "chg-r"])
    _rewrite_preview_prose(home, "chg-r", "g/intro", "Fully redrafted intro prose.")
    render_cmd.run(["g", "--change", "chg-r"])
    change, layout = _load_change(home, "chg-r")
    preview_text = (chg.preview_dir(change.dir) / "g_latest.md").read_text(encoding="utf-8")
    assert change_cmd.run(["archive", "chg-r"]) == 0
    final = _latest(home).read_text(encoding="utf-8")
    assert "Fully redrafted intro prose." in final
    # 整份換：正式 _latest 的散文內容＝preview（骨架重排場景的路）
    assert "Usage details here." in final


def test_file_target_hash_baseline(make_project, write_leaf, monkeypatch):
    """外部 file target：hash≠baseline＝done；未改＝不 done；收案整檔搬回。"""
    home = _project(make_project, write_leaf)
    _render_baseline(home, monkeypatch)
    layout = Layout(home, "per-article")
    schema_file = home.parent / "docs" / "schemas" / "x.json"
    schema_file.parent.mkdir(parents=True, exist_ok=True)
    schema_file.write_text('{"v": 1}\n', encoding="utf-8")

    change_cmd.run(["new", "chg-f", "--publish", "advisory"])
    change_cmd.run(["add-target", "chg-f", "docs/schemas/x.json",
                    "--action", "revise", "--kind", "file"])
    # 未改 staging 檔 → 不 done
    st = _status_map(home, "chg-f")
    ref = "docs/schemas/x.json"
    assert st[ref].done is False
    # 改 staging 副本 → done
    change = chg.load_change(layout, "chg-f")
    staged = chg.staging_target(change.dir, layout, schema_file)
    staged.write_text('{"v": 2}\n', encoding="utf-8")
    assert _status_map(home, "chg-f")[ref].done is True
    # 收案：正式檔整檔搬回為 v2
    assert change_cmd.run(["archive", "chg-f"]) == 0
    assert '"v": 2' in schema_file.read_text(encoding="utf-8")


# ── 1.4 check 收 changes/ ──────────────────────────────────────────

def test_check_rejects_dead_target_ref(make_project, write_leaf, monkeypatch):
    home = _project(make_project, write_leaf)
    _render_baseline(home, monkeypatch)
    layout = Layout(home, "per-article")
    change_cmd.run(["new", "chg-x", "--publish", "advisory"])
    # 手動塞一個死 ref target（繞過命令的解析）
    change = chg.load_change(layout, "chg-x")
    change.targets.append(chg.Target(ref="sec-nonexistent", action="revise"))
    chg.save_change(change)

    from dspx.check._changes import _validate_changes
    from dspx.engine.model import load_project
    leaves = load_project(layout)
    id_set = {lf.concept_id for lf in leaves if lf.concept_id} | {lf.section for lf in leaves}
    concept_ids = {lf.concept_id for lf in leaves if lf.concept_id}
    errs = _validate_changes(layout, leaves, set(map(str, id_set)), set(map(str, concept_ids)))
    assert any("nonexistent" in e for e in errs)


# ── 投影：status 概觀 / publish policy 閘 ──────────────────────────

def test_status_shows_active_changes_overview(make_project, write_leaf, monkeypatch, capsys):
    from dspx.commands.query import status as status_cmd
    home = _project(make_project, write_leaf)
    _render_baseline(home, monkeypatch)
    change_cmd.run(["new", "chg-x", "--publish", "advisory", "--title", "My change"])
    change_cmd.run(["add-target", "chg-x", "sec-intro", "--action", "revise"])
    capsys.readouterr()
    status_cmd.run([])
    out = capsys.readouterr().out
    assert "active changes (in flight)" in out
    assert "chg-x" in out and "0/1" in out


def test_instructions_shows_active_change_context(make_project, write_leaf, monkeypatch, capsys):
    from dspx.commands.projection import instructions as instr_cmd
    home = _project(make_project, write_leaf)
    _render_baseline(home, monkeypatch)
    change_cmd.run(["new", "chg-x", "--publish", "advisory", "--why", "switch units"])
    change_cmd.run(["add-target", "chg-x", "sec-intro", "--action", "revise"])
    capsys.readouterr()
    instr_cmd.run(["develop", "g/intro"])
    out = capsys.readouterr().out
    assert "Active change context" in out
    assert "chg-x" in out and "action=revise" in out
    # 一個不在任何單的節：零 change context
    capsys.readouterr()
    instr_cmd.run(["develop", "g/usage"])
    assert "Active change context" not in capsys.readouterr().out


def test_publish_release_bound_blocks(make_project, write_leaf, monkeypatch, capsys):
    from dspx.commands.deliverable import publish as publish_cmd
    home = _project(make_project, write_leaf)
    _render_baseline(home, monkeypatch)
    change_cmd.run(["new", "chg-x", "--publish", "release-bound"])
    change_cmd.run(["add-target", "chg-x", "sec-intro", "--action", "revise"])
    capsys.readouterr()
    rc = publish_cmd.run(["g"])
    assert rc == 1
    assert "release-bound" in capsys.readouterr().err


def test_publish_advisory_warns_but_proceeds(make_project, write_leaf, monkeypatch, capsys):
    from dspx.commands.deliverable import publish as publish_cmd
    home = _project(make_project, write_leaf)
    _render_baseline(home, monkeypatch)
    change_cmd.run(["new", "chg-x", "--publish", "advisory"])
    change_cmd.run(["add-target", "chg-x", "sec-intro", "--action", "revise"])
    capsys.readouterr()
    rc = publish_cmd.run(["g", "--note", "release"])
    err = capsys.readouterr().err
    assert rc == 0                      # advisory 放行
    assert "advisory" in err            # 但有 WARN


def test_check_rejects_bad_publish_and_action(make_project, write_leaf, monkeypatch):
    home = _project(make_project, write_leaf)
    _render_baseline(home, monkeypatch)
    layout = Layout(home, "per-article")
    change_cmd.run(["new", "chg-x", "--publish", "advisory"])
    change = chg.load_change(layout, "chg-x")
    change.publish = "whenever"
    change.targets.append(chg.Target(ref="sec-intro", action="frobnicate"))
    chg.save_change(change)
    errs = chg.validate_change(change)
    assert any("publish" in e for e in errs)
    assert any("action" in e for e in errs)


# ── ★C：store 篇 change 工作流（結構化 merge-by-section-id、P0 旁節 byte 不變）──────────

def _store_block(text: str, path: str) -> str:
    """從 canonical store 文字抽出某 `- path: <path>` 記錄到下個 `- path:`（或檔尾）的 byte 區塊。"""
    lines = text.split("\n")
    start = next((i for i, ln in enumerate(lines) if ln.strip() == f"- path: {path}"), None)
    assert start is not None, f"path {path} not found in store text"
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("- path:"):
            end = j
            break
    return "\n".join(lines[start:end])


def test_store_change_e2e_landing_bystander_byte_identical(make_project, write_leaf,
                                                           monkeypatch, tmp_path):
    """★store 篇完整 change e2e ＋ landing P0：new→put 進 staging→render --change→rewrite→archive。
    收案後正式 store 的**非 target 節序列化 block 逐 byte 相等**（＋旁節記錄深等值雙保險）、target
    節記錄真換、official 於 staging 期 byte 凍結。這證明 change 層結構化 landing 真的保住旁節。"""
    from dspx.commands.corpus import put as put_cmd
    home = _project(make_project, write_leaf, monkeypatch, backend="store")
    _render_baseline(home, monkeypatch)
    layout = Layout(home, "per-article")
    sp = st.store_path(layout, "g")

    assert change_cmd.run(["new", "chg-x", "--publish", "advisory"]) == 0
    assert change_cmd.run(["add-target", "chg-x", "sec-intro", "--action", "revise"]) == 0

    # put material 進 staging → 改 target 記錄；★official store byte 凍結（寫入落在 staging partial store）
    mat = tmp_path / "mat.md"
    mat.write_text("## fact 改 {#m-x}\n- 新值 = 42\n", encoding="utf-8")
    off_frozen = sp.read_text(encoding="utf-8")
    assert put_cmd.run(["g/intro", "material", str(mat), "--change", "chg-x"]) == 0
    assert sp.read_text(encoding="utf-8") == off_frozen, "put --change must not touch official store"

    change = chg.load_change(layout, "chg-x")
    staging = chg._load_staging_article(change.dir, "g")
    assert staging is not None
    srec = staging.record_by_path("g/intro")
    assert srec is not None and srec.material and "新值 = 42" in srec.material

    assert render_cmd.run(["g", "--change", "chg-x"]) == 0
    _rewrite_preview_prose(home, "chg-x", "g/intro", "The intro now cites fact m-x.")
    assert render_cmd.run(["g", "--change", "chg-x"]) == 0

    # 收案前抽正式 store 旁節 block（g, g/usage）＋深等值基準
    art_before = st.load_article(sp)
    before_text = sp.read_text(encoding="utf-8")
    bys_before = {p: _store_block(before_text, p) for p in ("g", "g/usage")}
    tgt_before = _store_block(before_text, "g/intro")

    assert change_cmd.run(["archive", "chg-x"]) == 0
    assert chg.change_state(layout, "chg-x") == "archived"

    # ★P0 byte 斷言：正式 store 旁節序列化 block 收案前後逐 byte 相等
    after_text = sp.read_text(encoding="utf-8")
    for p, blk in bys_before.items():
        assert _store_block(after_text, p) == blk, f"bystander {p} store block changed on landing"
    assert _store_block(after_text, "g/intro") != tgt_before, "target record must actually change"

    # 深等值雙保險：旁節記錄逐分類相同；target material 落地為新值
    art_after = st.load_article(sp)
    for p in ("g", "g/usage"):
        rb, ra = art_before.record_by_path(p), art_after.record_by_path(p)
        assert rb.concept == ra.concept and rb.decisions == ra.decisions and rb.material == ra.material
    assert "新值 = 42" in (art_after.record_by_path("g/intro").material or "")
    # 交付面：新散文落地正式 _latest、旁節散文不動
    final = _latest(home).read_text(encoding="utf-8")
    assert "cites fact m-x" in final and "Usage details here." in final


def test_store_put_routes_into_staging_official_frozen(make_project, write_leaf,
                                                       monkeypatch, tmp_path):
    """put <section> <cat> --change 對 store 篇：寫進 partial store staging、official store byte 凍結。"""
    from dspx.commands.corpus import put as put_cmd
    home = _project(make_project, write_leaf, monkeypatch, backend="store")
    layout = Layout(home, "per-article")
    sp = st.store_path(layout, "g")
    off_before = sp.read_text(encoding="utf-8")

    change_cmd.run(["new", "chg-x", "--publish", "advisory"])
    change_cmd.run(["add-target", "chg-x", "sec-intro", "--action", "revise"])
    dec = tmp_path / "d.yaml"
    dec.write_text("entries:\n  - id: dec-i1\n    kind: rationale\n    statement: 因為如此\n",
                   encoding="utf-8")
    assert put_cmd.run(["g/intro", "decisions", str(dec), "--change", "chg-x"]) == 0
    assert sp.read_text(encoding="utf-8") == off_before   # official 凍結
    change = chg.load_change(layout, "chg-x")
    srec = chg._load_staging_article(change.dir, "g").record_by_path("g/intro")
    assert any(e.get("id") == "dec-i1" for e in srec.decisions)


def test_store_abandon_zero_residue(make_project, write_leaf, monkeypatch, tmp_path):
    """store 篇 abandon：official store byte 零變化、staging/preview 隨案卷搬走且無殘留。"""
    from dspx.commands.corpus import put as put_cmd
    home = _project(make_project, write_leaf, monkeypatch, backend="store")
    _render_baseline(home, monkeypatch)
    layout = Layout(home, "per-article")
    sp = st.store_path(layout, "g")
    off_before = sp.read_text(encoding="utf-8")

    change_cmd.run(["new", "chg-x", "--publish", "advisory"])
    change_cmd.run(["add-target", "chg-x", "sec-intro", "--action", "revise"])
    mat = tmp_path / "m.md"
    mat.write_text("改動內容\n", encoding="utf-8")
    put_cmd.run(["g/intro", "material", str(mat), "--change", "chg-x"])
    change = chg.load_change(layout, "chg-x")
    assert chg.staging_store_path(change.dir, "g").is_file()

    assert change_cmd.run(["archive", "chg-x", "--abandon", "--reason", "wrong path"]) == 0
    assert chg.change_state(layout, "chg-x") == "abandoned"
    assert sp.read_text(encoding="utf-8") == off_before        # ★official store 零 byte 變化
    ab = chg.change_dir(layout, "chg-x", chg.STATE_ABANDONED)
    assert not chg.staging_dir(ab).exists() and not chg.preview_dir(ab).exists()


def test_store_fork_drift_guard(make_project, write_leaf, monkeypatch, tmp_path, capsys):
    """store 篇 fork 守門：第三方零開單直改正式 store 同節分類 → fork hash 失配、archive 中止。"""
    from dspx.commands.corpus import put as put_cmd
    home = _project(make_project, write_leaf, monkeypatch, backend="store")
    _render_baseline(home, monkeypatch)
    layout = Layout(home, "per-article")

    change_cmd.run(["new", "chg-x", "--publish", "advisory"])
    change_cmd.run(["add-target", "chg-x", "sec-intro", "--action", "revise"])
    mat = tmp_path / "m.md"
    mat.write_text("改動內容\n", encoding="utf-8")
    put_cmd.run(["g/intro", "material", str(mat), "--change", "chg-x"])
    render_cmd.run(["g", "--change", "chg-x"])
    _rewrite_preview_prose(home, "chg-x", "g/intro", "new prose here.")
    render_cmd.run(["g", "--change", "chg-x"])

    # 第三方零開單直改正式 store 的同節 material（fork 當下值以來變過）
    off = st.load_article(st.store_path(layout, "g"), verify=False)
    off.record_by_path("g/intro").material = "第三方直改的材料\n"
    st.save_article(layout, off, load_schema())
    st._ARTICLE_CACHE.clear()

    rc = change_cmd.run(["archive", "chg-x"])
    assert rc == 1
    assert "drift" in capsys.readouterr().err.lower()
    assert chg.change_state(layout, "chg-x") == "active"     # 未落地
    # --override-drift 放行
    assert change_cmd.run(["archive", "chg-x", "--override-drift"]) == 0
    assert chg.change_state(layout, "chg-x") == "archived"
