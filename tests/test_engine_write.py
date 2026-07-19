"""engine-write：get/put——corpus 真相的引擎讀出面 + **唯一驗證寫入門**。

反作弊紀律：put 的拒收矩陣斷言**原檔 byte 不變**（不寫半套），不只斷 exit code；round-trip 斷
內容不動點；首寫斷真的帶入 id/order 且 check 跟著綠。
"""

from __future__ import annotations

import json

import yaml

from dspx.check import run_check
from dspx.commands.query import check as check_cmd
from dspx.commands.corpus import get as get_cmd
from dspx.commands.corpus import put as put_cmd
from dspx.commands.query import status as status_cmd
from dspx.engine.layout import Layout
from dspx.engine.model import load_project
from dspx.engine.schema import load_schema


def _project(make_project, write_leaf, monkeypatch):
    """doc/intro（帶決策 d1）＋ doc/impl（realizes d1）；兩者皆有 '/'＝無 root-brief 要求。"""
    home = make_project()
    write_leaf(home, "doc/intro", concept={"id": "c-intro", "title": "簡介", "order": 1,
                                           "concept": "導言"},
               decisions=[{"id": "d1", "kind": "normative", "status": "accepted",
                           "statement": "規則一。"}])
    write_leaf(home, "doc/impl", concept={"id": "c-impl", "title": "實作", "order": 2,
                                          "concept": "實作", "realizes": ["d1"]})
    monkeypatch.chdir(home.parent)
    return home


def _src(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8", newline="\n")
    return str(p)


# ── 4.1：get/put round-trip 不動點 ─────────────────────────────────────────

def test_get_put_roundtrip_is_fixpoint(make_project, write_leaf, monkeypatch, tmp_path):
    home = _project(make_project, write_leaf, monkeypatch)
    out1 = str(tmp_path / "d1.yaml")
    assert get_cmd.run(["doc/intro", "decisions", "--out", out1]) == 0
    first = (tmp_path / "d1.yaml").read_text(encoding="utf-8")
    # 原樣寫回
    assert put_cmd.run(["doc/intro", "decisions", out1]) == 0
    # 再取一次＝同內容（冪等）
    out2 = str(tmp_path / "d2.yaml")
    assert get_cmd.run(["doc/intro", "decisions", "--out", out2]) == 0
    assert (tmp_path / "d2.yaml").read_text(encoding="utf-8") == first


def test_get_concept_roundtrip(make_project, write_leaf, monkeypatch, tmp_path):
    home = _project(make_project, write_leaf, monkeypatch)
    out1 = str(tmp_path / "c1.yaml")
    assert get_cmd.run(["doc/impl", "concept", "--out", out1]) == 0
    first = (tmp_path / "c1.yaml").read_text(encoding="utf-8")
    assert put_cmd.run(["doc/impl", "concept", out1]) == 0
    out2 = str(tmp_path / "c2.yaml")
    assert get_cmd.run(["doc/impl", "concept", "--out", out2]) == 0
    # get→put→get 不動點（既有 concept、非首寫、無 stamp → verbatim 回寫）
    assert (tmp_path / "c2.yaml").read_text(encoding="utf-8") == first


# ── 4.2：put 驗證拒收矩陣（壞 YAML／重複 id／壞 enum／斷 relation）；原檔 byte 不變 ──

def _assert_rejected_unchanged(run_args, target_path):
    before = target_path.read_bytes()
    assert put_cmd.run(run_args) == 1
    assert target_path.read_bytes() == before   # ★不寫半套


def test_put_rejects_bad_yaml(make_project, write_leaf, monkeypatch, tmp_path):
    home = _project(make_project, write_leaf, monkeypatch)
    dpath = home / "corpus" / "doc" / "article.yaml"   # dossier：拒收要驗 store 檔 byte 不變
    src = _src(tmp_path, "bad.yaml", "entries: [ {id: d9, kind: normative, ")  # 未閉合
    _assert_rejected_unchanged(["doc/intro", "decisions", src], dpath)


def test_put_rejects_duplicate_id(make_project, write_leaf, monkeypatch, tmp_path):
    home = _project(make_project, write_leaf, monkeypatch)
    dpath = home / "corpus" / "doc" / "article.yaml"   # dossier：拒收要驗 store 檔 byte 不變
    src = _src(tmp_path, "dup.yaml",
               "entries:\n"
               "  - {id: dd, kind: normative, status: accepted, statement: \"一\"}\n"
               "  - {id: dd, kind: normative, status: accepted, statement: \"二\"}\n")
    _assert_rejected_unchanged(["doc/intro", "decisions", src], dpath)


def test_put_rejects_id_claimed_by_other_section(make_project, write_leaf, monkeypatch, tmp_path):
    home = _project(make_project, write_leaf, monkeypatch)
    dpath = home / "corpus" / "doc" / "impl" / "decisions.yaml"  # 不存在→用 impl 建新決策
    # 撞 doc/intro 既有 id d1
    src = _src(tmp_path, "clash.yaml",
               "entries:\n  - {id: d1, kind: normative, status: accepted, statement: \"撞號\"}\n")
    before_exists = dpath.is_file()
    assert put_cmd.run(["doc/impl", "decisions", src]) == 1
    assert dpath.is_file() == before_exists   # 拒收＝沒建出半套檔


def test_put_rejects_bad_enum(make_project, write_leaf, monkeypatch, tmp_path):
    home = _project(make_project, write_leaf, monkeypatch)
    dpath = home / "corpus" / "doc" / "article.yaml"   # dossier：拒收要驗 store 檔 byte 不變
    src = _src(tmp_path, "enum.yaml",
               "entries:\n  - {id: d9, kind: normative, status: bogus, statement: \"x\"}\n")
    _assert_rejected_unchanged(["doc/intro", "decisions", src], dpath)


def test_put_rejects_dangling_relation(make_project, write_leaf, monkeypatch, tmp_path):
    home = _project(make_project, write_leaf, monkeypatch)
    cpath = home / "corpus" / "doc" / "article.yaml"   # dossier：拒收要驗 store 檔 byte 不變
    src = _src(tmp_path, "rel.yaml",
               "id: c-impl\ntitle: 實作\norder: 2\nstatus: draft\nconcept: 實作\n"
               "realizes: [ghost-id]\n")
    _assert_rejected_unchanged(["doc/impl", "concept", src], cpath)


# ── 4.3：首寫 concept 帶 id/order；put 後 status/check 行為正確 ────────────────

def test_first_write_concept_stamps_id_order(make_project, write_leaf, monkeypatch, tmp_path):
    home = _project(make_project, write_leaf, monkeypatch)
    newdir = home / "corpus" / "doc" / "newpart"
    newdir.mkdir(parents=True)
    (newdir / "develop.md").write_text("# 思考\n", encoding="utf-8")
    cpath = newdir / "concept.yaml"
    assert not cpath.is_file()
    # 送進來的內容故意不帶 id/order
    src = _src(tmp_path, "new.yaml",
               "title: 新章\nstatus: draft\nconcept: 新內容\nbrief:\n  audience: 讀者\n")
    assert put_cmd.run(["doc/newpart", "concept", src]) == 0
    # ★store-only：put 寫進 corpus/doc.yaml store 記錄，非散檔 concept.yaml
    from dspx.engine import store as _store
    data = _store.load_article(_store.store_path(Layout(home), "doc"), verify=False) \
        .record_by_path("doc/newpart").concept
    assert str(data["id"]).startswith("sec-")            # 帶入穩定 id
    assert isinstance(data["order"], (int, float))       # 帶入 order
    assert data["concept"] == "新內容"                    # 原內容保留

    # check 仍綠（新節結構完整、無斷引用）
    assert check_cmd.run(["doc"]) == 0


def test_first_write_status_reflects_concept(make_project, write_leaf, monkeypatch, tmp_path, capsys):
    home = _project(make_project, write_leaf, monkeypatch)
    newdir = home / "corpus" / "doc" / "np2"
    newdir.mkdir(parents=True)
    src = _src(tmp_path, "np2.yaml",
               "title: 二\nstatus: draft\nconcept: 內容\n")
    assert put_cmd.run(["doc/np2", "concept", src]) == 0
    capsys.readouterr()
    assert status_cmd.run(["doc", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)["sections"]
    row = next(r for r in rows if r["section"] == "doc/np2")
    assert row["files"]["concept"] is True


# ── put 不擋「完整性」（developing 半成品照收，寫入當下合法）────────────────────

def test_put_accepts_incomplete_concept_developing(make_project, write_leaf, monkeypatch, tmp_path):
    """completeness 閘在晉升、不在寫入：缺必填 concept 的半成品照寫（結構沒壞）。"""
    home = _project(make_project, write_leaf, monkeypatch)
    newdir = home / "corpus" / "doc" / "wip"
    newdir.mkdir(parents=True)
    # 缺必填 `concept` 欄（未齊＝developing、非結構壞）→ put 仍收
    src = _src(tmp_path, "wip.yaml", "title: 半成品\nstatus: draft\n")
    assert put_cmd.run(["doc/wip", "concept", src]) == 0
    # ★store-only：真相在 store 記錄
    from dspx.engine import store as _store
    assert _store.load_article(_store.store_path(Layout(home), "doc"), verify=False) \
        .record_by_path("doc/wip") is not None


# ── get 缺檔回 schema 空骨架 ──────────────────────────────────────────────

def test_get_empty_skeleton_when_absent(make_project, write_leaf, monkeypatch, capsys):
    home = _project(make_project, write_leaf, monkeypatch)
    # doc/impl 無 material.md → 回 material 模板骨架（非空）
    assert get_cmd.run(["doc/impl", "material"]) == 0
    assert capsys.readouterr().out.strip() != ""
    # 尚不存在的節 concept → schema 空骨架（含 id/title 欄）
    assert get_cmd.run(["doc/ghost", "concept"]) == 0
    out = capsys.readouterr().out
    assert "id:" in out and "title:" in out


def test_put_then_get_material(make_project, write_leaf, monkeypatch, tmp_path, capsys):
    home = _project(make_project, write_leaf, monkeypatch)
    src = _src(tmp_path, "m.md", "## fact: 甲 {#m-a}\n- 一條事實\n")
    assert put_cmd.run(["doc/impl", "material", src]) == 0
    capsys.readouterr()
    assert get_cmd.run(["doc/impl", "material"]) == 0
    assert "一條事實" in capsys.readouterr().out


def test_get_put_are_agent_facing(make_project, write_leaf, monkeypatch):
    from dspx.commands import HUMAN_COMMANDS, REGISTRY
    assert "get" in REGISTRY and "put" in REGISTRY
    assert "get" not in HUMAN_COMMANDS and "put" not in HUMAN_COMMANDS
