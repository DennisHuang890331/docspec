"""ledger-verdict-verbs：--ack-own／stale／redraft 裁決動詞、verdicts journal、
〔#02〕無主散文丟棄 WARN。"""

from __future__ import annotations

from pathlib import Path

import yaml

from dspx.commands import redraft as redraft_cmd
from dspx.commands import render as render_cmd
from dspx.commands import stale as stale_cmd
from dspx.layout import Layout
from dspx.render import parse_section_bodies, read_ledger, verdicts_path


def _project(tmp_path, name, write_leaf) -> Path:
    """獨立最小專案（兩專案內容全同→指紋全同；兩步法等價性比對用）。"""
    home = tmp_path / name / "docspec"
    home.mkdir(parents=True)
    (home / "config.yaml").write_text("language: zh-TW\ndocs_layout: per-article\n",
                                      encoding="utf-8")
    write_leaf(home, "g/intro", concept={"id": "c1", "title": "概覽", "order": 1})
    write_leaf(home, "g/usage", concept={"id": "c2", "title": "用法", "order": 2})
    return home


def _latest(home, article="g"):
    return home.parent / "docs" / article / "_latest.md"


def _write_prose(home, article, heading, prose):
    latest = _latest(home, article)
    latest.write_text(
        latest.read_text("utf-8").replace(f"{heading}\n", f"{heading}\n\n{prose}\n"), "utf-8")


def _sync_of(home, article, section):
    """重算某節 sync 狀態（同 status._leaf_row 邏輯）。"""
    from dspx.commands.status import _docs_hashes, _leaf_row
    from dspx.model import decision_index, load_project
    from dspx.schema import load_schema
    layout = Layout(home)
    leaves = load_project(layout)
    by = {lf.section: lf for lf in leaves}
    return _leaf_row(layout, by[section], load_schema(), True,
                     _docs_hashes(layout, article), by, decision_index(leaves))["sync"]


def _read_journal(home, article="g") -> list[dict]:
    path = verdicts_path(Layout(home), article)
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text("utf-8"))
    assert isinstance(data, list)          # 整檔恆為合法 YAML list
    return data


# ── 6.1 兩步法等價性：ack-own 終態 == 擾動→render→復原→render 的 dance 終態 ──


def test_ack_own_equals_perturb_revert_dance(tmp_path, write_leaf, monkeypatch):
    """ack-own 後的帳本終態與 dance 逐鍵相等（own/anc/deps/style/prose）——差別只在留痕。"""
    ledgers = {}
    for name, flow in (("p_ack", "ack-own"), ("p_dance", "dance")):
        home = _project(tmp_path, name, write_leaf)
        monkeypatch.chdir(home.parent)
        render_cmd.run(["g"])
        _write_prose(home, "g", "## 1. 概覽", "限流保護後端。")
        render_cmd.run(["g"])
        assert _sync_of(home, "g", "g/intro") == "synced"
        # 結構接線類源變更（散文合法不需改）
        cpt = home / "corpus" / "g" / "intro" / "concept.yaml"
        cpt.write_text(cpt.read_text("utf-8").replace("title: 概覽", "title: 概覽（改）"), "utf-8")
        assert _sync_of(home, "g", "g/intro") == "stale-own"
        if flow == "ack-own":
            assert render_cmd.run(["g", "--ack-own", "g/intro", "--reason", "接線變更"]) == 0
        else:
            latest = _latest(home)
            latest.write_text(latest.read_text("utf-8").replace("限流保護後端。", "限流保護後端。X"),
                              "utf-8")
            render_cmd.run(["g"])                                   # 擾動→蓋新源
            latest.write_text(latest.read_text("utf-8").replace("限流保護後端。X", "限流保護後端。"),
                              "utf-8")
            render_cmd.run(["g"])                                   # 復原→再蓋
        assert _sync_of(home, "g", "g/intro") == "synced"
        ledgers[flow] = read_ledger(Layout(home), "g")["g/intro"]
    # 逐鍵相等（兩專案內容全同→指紋內容導出、可跨專案比）
    assert ledgers["ack-own"] == ledgers["dance"]


def test_ack_own_without_reason_refused(tmp_path, write_leaf, monkeypatch, capsys):
    """--ack-own 無 --reason → 拒跑（非零、指名必填）、帳本不動。"""
    home = _project(tmp_path, "p1", write_leaf)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    _write_prose(home, "g", "## 1. 概覽", "內文。")
    render_cmd.run(["g"])
    before = read_ledger(Layout(home), "g")
    capsys.readouterr()
    assert render_cmd.run(["g", "--ack-own", "g/intro"]) != 0
    assert "--reason" in capsys.readouterr().err
    assert read_ledger(Layout(home), "g") == before                 # 拒跑＝零副作用


def test_ack_own_unwritten_section_skipped(tmp_path, write_leaf, monkeypatch, capsys):
    """無帳本記錄（未撰寫）的節 → ack-own 跳過並可見回報（不 fail 整輪 render）。"""
    home = _project(tmp_path, "p1", write_leaf)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])                                            # usage 無散文＝無記錄
    capsys.readouterr()
    assert render_cmd.run(["g", "--ack-own", "g/usage", "--reason", "r"]) == 0
    err = capsys.readouterr().err
    assert "--ack-own skipped" in err and "g/usage" in err
    assert _read_journal(home) == []                                 # 跳過＝不留 journal


# ── 6.2 遮蔽浮出＋組合＋既有 --ack refusal 回歸 ────────────────────────


def _parent_child(tmp_path, write_leaf):
    home = tmp_path / "pc" / "docspec"
    home.mkdir(parents=True)
    (home / "config.yaml").write_text("language: zh-TW\ndocs_layout: per-article\n",
                                      encoding="utf-8")
    write_leaf(home, "doc/sec", concept={"id": "p1", "title": "Sec", "order": 1,
                                         "concept": "父概念", "brief": {"受眾": "X"}})
    write_leaf(home, "doc/sec/a", concept={"id": "c1", "title": "A", "order": 1})
    return home


def test_masked_stale_inherited_surfaces_after_ack_own(tmp_path, write_leaf, monkeypatch):
    """own+anc 同時變 → ack-own 只蓋 own/deps、anc 沿用 → stale-inherited 浮出；
    再補 --ack 同節 → synced。"""
    home = _parent_child(tmp_path, write_leaf)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["doc"])
    _write_prose(home, "doc", "### 1.1 A", "子散文。")
    render_cmd.run(["doc"])
    assert _sync_of(home, "doc", "doc/sec/a") == "synced"
    # 父 brief（anc 軸）＋子自身 concept（own 軸）同時變 → own precedence 遮蔽 anc
    sec = home / "corpus" / "doc" / "sec" / "concept.yaml"
    sec.write_text(sec.read_text("utf-8").replace("受眾: X", "受眾: Y"), "utf-8")
    child = home / "corpus" / "doc" / "sec" / "a" / "concept.yaml"
    child.write_text(child.read_text("utf-8").replace("title: A", "title: A（改）"), "utf-8")
    assert _sync_of(home, "doc", "doc/sec/a") == "stale-own"
    # ack-own → own/deps 蓋現值、anc 沿用舊值 → 被遮蔽的 stale-inherited 浮出
    assert render_cmd.run(["doc", "--ack-own", "doc/sec/a", "--reason", "標題重編號"]) == 0
    assert _sync_of(home, "doc", "doc/sec/a") == "stale-inherited"
    # 剩餘軸只有 --ack 能清
    assert render_cmd.run(["doc", "--ack", "doc/sec/a"]) == 0
    assert _sync_of(home, "doc", "doc/sec/a") == "synced"


def test_ack_and_ack_own_compose_in_one_render(tmp_path, write_leaf, monkeypatch):
    """同節同給 --ack-own＋--ack ＝ 全四軸蓋現值 → synced。"""
    home = _parent_child(tmp_path, write_leaf)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["doc"])
    _write_prose(home, "doc", "### 1.1 A", "子散文。")
    render_cmd.run(["doc"])
    sec = home / "corpus" / "doc" / "sec" / "concept.yaml"
    sec.write_text(sec.read_text("utf-8").replace("受眾: X", "受眾: Y"), "utf-8")
    child = home / "corpus" / "doc" / "sec" / "a" / "concept.yaml"
    child.write_text(child.read_text("utf-8").replace("title: A", "title: A（改）"), "utf-8")
    assert _sync_of(home, "doc", "doc/sec/a") == "stale-own"
    assert render_cmd.run(["doc", "--ack-own", "doc/sec/a", "--ack", "doc/sec/a",
                           "--reason", "接線＋祖先皆已對齊"]) == 0
    assert _sync_of(home, "doc", "doc/sec/a") == "synced"


def test_ack_alone_still_refused_on_stale_own(tmp_path, write_leaf, monkeypatch, capsys):
    """回歸：不給 --ack-own 時，--ack 單獨用於 stale-own 的 refusal 語義逐字不變。"""
    home = _project(tmp_path, "p1", write_leaf)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    _write_prose(home, "g", "## 1. 概覽", "內文。")
    render_cmd.run(["g"])
    cpt = home / "corpus" / "g" / "intro" / "concept.yaml"
    cpt.write_text(cpt.read_text("utf-8").replace("title: 概覽", "title: 概覽（改）"), "utf-8")
    capsys.readouterr()
    assert render_cmd.run(["g", "--ack", "g/intro"]) == 0
    assert _sync_of(home, "g", "g/intro") == "stale-own"             # 沒被吞
    assert "refused" in capsys.readouterr().err
    assert _read_journal(home) == []                                 # 被拒＝零 journal


def test_ack_own_stdout_carries_heavier_accountability_note(tmp_path, write_leaf,
                                                            monkeypatch, capsys):
    """ack-own 責任註記（加重語氣）：證言「散文仍實現已變更的源料」→ 導向 factcheck 覆檢。"""
    home = _project(tmp_path, "p1", write_leaf)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    _write_prose(home, "g", "## 1. 概覽", "內文。")
    render_cmd.run(["g"])
    cpt = home / "corpus" / "g" / "intro" / "concept.yaml"
    cpt.write_text(cpt.read_text("utf-8").replace("title: 概覽", "title: 概覽（改）"), "utf-8")
    capsys.readouterr()
    assert render_cmd.run(["g", "--ack-own", "g/intro", "--reason", "接線"]) == 0
    out = capsys.readouterr().out
    assert "ack-own" in out and "CHANGED source" in out and "factcheck" in out


# ── 6.3 redraft 旗標生命週期 ─────────────────────────────────────────


def test_stale_marks_and_fingerprints_untouched(tmp_path, write_leaf, monkeypatch):
    """stale 標髒 → status stale-own；指紋逐位元不變（只多 redraft 鍵）。"""
    home = _project(tmp_path, "p1", write_leaf)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    _write_prose(home, "g", "## 1. 概覽", "內文。")
    render_cmd.run(["g"])
    before = dict(read_ledger(Layout(home), "g")["g/intro"])
    assert _sync_of(home, "g", "g/intro") == "synced"
    assert stale_cmd.run(["g/intro", "--reason", "重構後語義過時"]) == 0
    after = dict(read_ledger(Layout(home), "g")["g/intro"])
    assert after.pop("redraft") is True
    assert after == before                                           # 指紋一律不動
    assert _sync_of(home, "g", "g/intro") == "stale-own"


def test_redraft_flag_survives_skeleton_render_clears_on_rewrite(tmp_path, write_leaf,
                                                                 monkeypatch):
    """旗標跨骨架 render 存活（F2 沿用分支攜帶）；散文真重寫→自然清除＝synced。"""
    home = _project(tmp_path, "p1", write_leaf)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    _write_prose(home, "g", "## 1. 概覽", "舊散文。")
    render_cmd.run(["g"])
    assert stale_cmd.run(["g/intro", "--reason", "r"]) == 0
    render_cmd.run(["g"])                                            # 純骨架 render
    assert read_ledger(Layout(home), "g")["g/intro"].get("redraft") is True
    assert _sync_of(home, "g", "g/intro") == "stale-own"             # 信號存活
    # 散文真重寫 → _current()（無旗標）＝自然清除
    latest = _latest(home)
    latest.write_text(latest.read_text("utf-8").replace("舊散文。", "重寫後的散文。"), "utf-8")
    render_cmd.run(["g"])
    assert "redraft" not in read_ledger(Layout(home), "g")["g/intro"]
    assert _sync_of(home, "g", "g/intro") == "synced"


def test_ack_own_clears_redraft_flag(tmp_path, write_leaf, monkeypatch):
    """--ack-own＝作者顯式反裁決 → 一併清 redraft 旗標。"""
    home = _project(tmp_path, "p1", write_leaf)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    _write_prose(home, "g", "## 1. 概覽", "內文。")
    render_cmd.run(["g"])
    assert stale_cmd.run(["g/intro", "--reason", "r"]) == 0
    assert _sync_of(home, "g", "g/intro") == "stale-own"
    assert render_cmd.run(["g", "--ack-own", "g/intro", "--reason", "覆核過不需重寫"]) == 0
    assert "redraft" not in read_ledger(Layout(home), "g")["g/intro"]
    assert _sync_of(home, "g", "g/intro") == "synced"


def test_stale_refusals(tmp_path, write_leaf, monkeypatch, capsys):
    """無 --reason／未撰寫節／未知節 → 拒跑（非零）。"""
    home = _project(tmp_path, "p1", write_leaf)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    _write_prose(home, "g", "## 1. 概覽", "內文。")
    render_cmd.run(["g"])
    capsys.readouterr()
    assert stale_cmd.run(["g/intro"]) != 0                           # 無 reason
    assert "--reason" in capsys.readouterr().err
    assert stale_cmd.run(["g/usage", "--reason", "r"]) != 0          # 未撰寫（無帳本記錄）
    assert "draft" in capsys.readouterr().err
    assert stale_cmd.run(["g/nope", "--reason", "r"]) != 0           # 未知節
    assert "no leaf section" in capsys.readouterr().err
    assert "redraft" not in read_ledger(Layout(home), "g")["g/intro"]
    assert _read_journal(home) == []                                 # 全被拒＝零 journal


# ── 6.4 verdicts journal（append-only） ─────────────────────────────


def test_journal_appends_per_verdict_with_full_schema(tmp_path, write_leaf, monkeypatch):
    """ack 1＋ack-own 1＋redraft（兩節）2 ＝ 4 筆，欄位齊、依執行序；整檔合法 YAML list。"""
    home = _parent_child(tmp_path, write_leaf)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["doc"])
    _write_prose(home, "doc", "## 1. Sec", "父散文。")
    _write_prose(home, "doc", "### 1.1 A", "子散文。")
    render_cmd.run(["doc"])
    # 父 brief 變 → sec 自己 stale-own、sec/a stale-inherited
    sec = home / "corpus" / "doc" / "sec" / "concept.yaml"
    sec.write_text(sec.read_text("utf-8").replace("受眾: X", "受眾: Y"), "utf-8")
    own_before = read_ledger(Layout(home), "doc")["doc/sec"]["own"]
    assert render_cmd.run(["doc", "--ack-own", "doc/sec", "--ack", "doc/sec/a",
                           "--reason", "接線對齊"]) == 0
    assert redraft_cmd.run(["doc", "--reason", "全文重投"]) == 0
    j = _read_journal(home, "doc")
    assert [(e["verb"], e["section"]) for e in j] == [
        ("ack-own", "doc/sec"), ("ack", "doc/sec/a"),
        ("redraft", "doc/sec"), ("redraft", "doc/sec/a")]
    for e in j:
        assert set(e) == {"when", "verb", "section", "reason", "own_before", "own_after", "prose"}
        assert e["reason"]
    assert j[0]["own_before"] == own_before
    assert j[0]["own_after"] != own_before                           # ack-own 蓋了現值
    assert j[2]["own_before"] == j[2]["own_after"]                   # redraft 不動指紋


def test_journal_untouched_by_plain_renders(tmp_path, write_leaf, monkeypatch):
    """多輪純 render（無 ack 旗標）前後 journal 位元不變（render 永不重寫/重生它）。"""
    home = _project(tmp_path, "p1", write_leaf)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    _write_prose(home, "g", "## 1. 概覽", "內文。")
    render_cmd.run(["g"])
    assert stale_cmd.run(["g/intro", "--reason", "r"]) == 0          # 先留一筆
    path = verdicts_path(Layout(home), "g")
    before = path.read_bytes()
    render_cmd.run(["g"])
    render_cmd.run(["g"])
    assert path.read_bytes() == before
    assert render_cmd.run(["g", "--ack-own", "g/intro", "--reason", "覆核"]) == 0
    assert len(_read_journal(home)) == 2                             # 只 append、不重排


def test_journal_ack_reason_optional(tmp_path, write_leaf, monkeypatch):
    """既有 --ack 加選配 --reason：不帶照跑（reason 空字串）、帶了入 journal。"""
    home = _parent_child(tmp_path, write_leaf)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["doc"])
    _write_prose(home, "doc", "### 1.1 A", "子散文。")
    render_cmd.run(["doc"])
    sec = home / "corpus" / "doc" / "sec" / "concept.yaml"
    sec.write_text(sec.read_text("utf-8").replace("受眾: X", "受眾: Y"), "utf-8")
    assert render_cmd.run(["doc", "--ack", "doc/sec/a"]) == 0        # 無 reason、行為不變
    assert _sync_of(home, "doc", "doc/sec/a") == "synced"
    j = _read_journal(home, "doc")
    assert len(j) == 1 and j[0]["verb"] == "ack" and j[0]["reason"] == ""


# ── 6.5 redraft 備份 ────────────────────────────────────────────────


def test_redraft_backs_up_latest_and_marks_all_written(tmp_path, write_leaf, monkeypatch):
    """備份==標髒前 _latest；docs/ 零新增檔；全部已撰寫節帶旗標＋stale-own。"""
    home = _project(tmp_path, "p1", write_leaf)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    _write_prose(home, "g", "## 1. 概覽", "甲。")
    _write_prose(home, "g", "## 2. 用法", "乙。")
    render_cmd.run(["g"])
    docs_before = sorted(p.as_posix() for p in (home.parent / "docs").rglob("*"))
    pre = _latest(home).read_text("utf-8")
    assert redraft_cmd.run(["g", "--reason", "全文重投"]) == 0
    backups = list((home / ".ledger" / "redraft-backup").glob("g.*.md"))
    assert len(backups) == 1
    assert backups[0].read_text("utf-8") == pre                      # 內容==標髒前交付物
    assert sorted(p.as_posix() for p in (home.parent / "docs").rglob("*")) == docs_before
    ledger = read_ledger(Layout(home), "g")
    assert ledger["g/intro"].get("redraft") is True
    assert ledger["g/usage"].get("redraft") is True
    assert _sync_of(home, "g", "g/intro") == "stale-own"
    assert _sync_of(home, "g", "g/usage") == "stale-own"


def test_redraft_refusals(tmp_path, write_leaf, monkeypatch, capsys):
    """無 --reason／無已撰寫節／未知文章 → 拒跑；拒跑不產備份。"""
    home = _project(tmp_path, "p1", write_leaf)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])                                            # 全未撰寫
    capsys.readouterr()
    assert redraft_cmd.run(["g"]) != 0                               # 無 reason
    assert "--reason" in capsys.readouterr().err
    assert redraft_cmd.run(["g", "--reason", "r"]) != 0              # 無已撰寫節
    assert "no written sections" in capsys.readouterr().err
    assert redraft_cmd.run(["nope", "--reason", "r"]) != 0           # 未知文章
    assert "no leaf sections found for article" in capsys.readouterr().err
    assert not (home / ".ledger" / "redraft-backup").exists()        # 拒跑＝零備份


# ── 6.6 〔#02〕無主散文丟棄 WARN ─────────────────────────────────────


def _group_project(tmp_path, write_leaf):
    home = tmp_path / "gp" / "docspec"
    home.mkdir(parents=True)
    (home / "config.yaml").write_text("language: zh-TW\ndocs_layout: per-article\n",
                                      encoding="utf-8")
    write_leaf(home, "g/methods/a", concept={"id": "c1", "title": "方法A", "order": 1})
    return home


def test_unowned_prose_under_group_heading_warns(tmp_path, write_leaf, monkeypatch, capsys):
    """group 標題下手寫散文 → render stderr WARN（exit 0、輸出檔照舊＝內容仍被丟棄）。"""
    home = _group_project(tmp_path, write_leaf)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    latest = _latest(home)
    clean = latest.read_text("utf-8")
    # 在分組標題行下塞手寫散文（分組無散文槽＝無主）
    latest.write_text(clean.replace("## 1. Methods\n", "## 1. Methods\n\n手寫的無主散文。\n"), "utf-8")
    capsys.readouterr()
    assert render_cmd.run(["g"]) == 0                                # WARN 不改 exit code
    err = capsys.readouterr().err
    assert "unowned prose" in err and "g/methods" in err and "\"g\"" in err
    assert latest.read_text("utf-8") == clean                        # 輸出檔照舊（丟棄行為不變）


def test_unowned_prose_in_preamble_warns(tmp_path, write_leaf, monkeypatch, capsys):
    """首個 marker 前（preamble）的手寫內容 → WARN 指名 preamble。"""
    home = _group_project(tmp_path, write_leaf)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    latest = _latest(home)
    latest.write_text(latest.read_text("utf-8").replace(
        "<!-- dspx:group g/methods -->", "偷放在封面後的散文。\n\n<!-- dspx:group g/methods -->"),
        "utf-8")
    capsys.readouterr()
    assert render_cmd.run(["g"]) == 0
    assert "preamble" in capsys.readouterr().err


def test_render_generated_skeleton_never_warns(tmp_path, write_leaf, monkeypatch, capsys):
    """純 render 自產骨架（分組標題＋封面標題）重 render 零 WARN（自產行剝除後空白）。"""
    home = _group_project(tmp_path, write_leaf)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    _write_prose(home, "g", "### 1.1 方法A", "節內散文。")
    capsys.readouterr()
    assert render_cmd.run(["g"]) == 0
    assert render_cmd.run(["g"]) == 0
    assert "unowned prose" not in capsys.readouterr().err


def test_parse_section_bodies_default_unchanged_and_callback_reports():
    """無回呼＝既有行為位元零變化；有回呼＝逐塊回報 (位置, 內容)。"""
    text = ("---\narticle: g\n---\n# 封面\n\npreamble 手寫。\n\n"
            "<!-- dspx:group g/grp -->\n## 分組\n\n分組下手寫。\n\n"
            "<!-- dspx:section g/grp/a -->\n### A\n\n節文。\n")
    assert parse_section_bodies(text) == {"g/grp/a": "節文。"}       # 既有呼叫端不變
    seen = []
    bodies = parse_section_bodies(text, on_discard=lambda loc, block: seen.append((loc, block)))
    assert bodies == {"g/grp/a": "節文。"}
    assert [loc for loc, _ in seen] == ["preamble", "g/grp"]
    assert "preamble 手寫。" in seen[0][1]
    assert "分組下手寫。" in seen[1][1]


# ── registry／投影 ───────────────────────────────────────────────────


def test_verdict_commands_registered_agent_facing():
    from dspx.commands import HUMAN_COMMANDS, REGISTRY
    for name in ("stale", "redraft"):
        assert name in REGISTRY
        assert name not in HUMAN_COMMANDS                            # agent-facing、預設 help 隱藏


def test_guide_projects_verdict_verbs_and_whitelist(tmp_path, write_leaf, monkeypatch, capsys):
    """docspec guide 投影裁決動詞與 ack-own 白名單（schema workflow.skills steps）。"""
    from dspx.commands import guide as guide_cmd
    home = _project(tmp_path, "p1", write_leaf)
    monkeypatch.chdir(home.parent)
    assert guide_cmd.run([]) == 0
    out = capsys.readouterr().out
    assert "--ack-own" in out
    assert "must_cover" in out                                       # 白名單反例（content-bearing）
    assert "docspec stale" in out and "docspec redraft" in out
    assert "perturb-render-revert" in out                            # 禁止擾動復原 dance
