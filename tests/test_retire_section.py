"""retire-section / retired：整節退場、扁平封存、引擎隱形、查詢；develop 殘留＝developing。"""

from __future__ import annotations

import json

import yaml

from dspx.commands.corpus import retire as retire_cmd
from dspx.commands.corpus import retire_section as rs_cmd
from dspx.commands.corpus import retired as retired_cmd
from dspx.commands.query import status as status_cmd
from dspx.layout import Layout
from dspx.model import load_project


def test_retire_section_moves_and_records(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    write_leaf(home, "zenoh/hello-world",
               concept={"id": "c1", "title": "Hello", "order": 1,
                        "concept": "新手第一個 pub/sub"},
               decisions=[{"id": "d1", "status": "accepted", "statement": "用官方範例"}])
    write_leaf(home, "zenoh/arch", concept={"id": "c2", "title": "Arch", "order": 2})
    monkeypatch.chdir(home.parent)

    assert rs_cmd.run(["zenoh/hello-world", "--in", "v2"]) == 0

    # 原位已不在、扁平 archive 有了
    assert not (home / "corpus" / "zenoh" / "hello-world").exists()
    dest = home / "corpus" / "_archive" / "zenoh__hello-world"
    assert dest.is_dir()
    # 退場記錄＝該節 history.yaml 一筆 kind:section entry（id=concept.id 非路徑、含 archive link）
    data = yaml.safe_load((dest / "history.yaml").read_text(encoding="utf-8"))
    sec = next(e for e in data["entries"] if e.get("kind") == "section")
    assert sec["id"] == "c1"                                  # ★concept.id，不是路徑
    assert sec["archive"] == "corpus/_archive/zenoh__hello-world"   # link → folder
    assert sec["status"] == "retired"
    assert sec["statement"] == "新手第一個 pub/sub"            # note 預設取 concept.concept
    assert sec["retired-in"] == "v2"
    # 整節退場不寫 history.md（細節＝archive 資料夾本身；history.md 只給決策退場散文）
    md_path = dest / "history.md"
    assert not md_path.is_file() or "## c1" not in md_path.read_text(encoding="utf-8")

    # 引擎隱形：load_project 不再看到被退場節，兄弟節還在
    secs = {lf.section for lf in load_project(Layout(home))}
    assert "zenoh/hello-world" not in secs
    assert "zenoh/arch" in secs

    # retired 查得到（顯示還原的原路徑＋一句話）
    assert retired_cmd.run([]) == 0
    out = capsys.readouterr().out
    assert "zenoh/hello-world" in out and "新手第一個 pub/sub" in out


def test_retire_section_prefix_filter(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    write_leaf(home, "b/y", concept={"id": "c2", "title": "Y", "order": 1})
    monkeypatch.chdir(home.parent)
    assert rs_cmd.run(["a/x"]) == 0
    assert rs_cmd.run(["b/y"]) == 0
    capsys.readouterr()                       # 清掉退場輸出
    assert retired_cmd.run(["a"]) == 0
    out = capsys.readouterr().out
    assert "a/x" in out and "b/y" not in out


def test_retire_decision_reports_in_place_non_mutating(make_project, write_leaf, monkeypatch,
                                                       capsys):
    """contract-slimming D3：retire＝純報告——死決策**留在原 decisions.yaml**，
    不搬 history.yaml、不寫 history.md、零檔案異動。"""
    home = make_project()
    write_leaf(home, "a/x",
               concept={"id": "c1", "title": "X", "order": 1},
               decisions=[
                   {"id": "d-old", "kind": "normative", "status": "deprecated",
                    "statement": "鎖 Linux", "rationale": "當時只有 Linux wheel",
                    "rejected": ["MQTT", "gRPC"]},
                   {"id": "d-new", "kind": "normative", "status": "accepted",
                    "statement": "雙語"},
               ])
    monkeypatch.chdir(home.parent)
    leaf = home / "corpus" / "a" / "x"
    dec_before = (leaf / "decisions.yaml").read_bytes()
    assert retire_cmd.run(["a/x"]) == 0                          # retire＝純報告、零寫入
    out = capsys.readouterr().out
    assert "d-old" in out and "deprecated" in out                # 逐條點名死決策
    assert "STAY IN PLACE" in out                                # 就地即終態、無物可搬
    # 零寫入：decisions.yaml 位元不變（d-old 連 rationale/rejected 都原樣留著）
    assert (leaf / "decisions.yaml").read_bytes() == dec_before
    dec = yaml.safe_load((leaf / "decisions.yaml").read_text(encoding="utf-8"))
    assert [d["id"] for d in dec["entries"]] == ["d-old", "d-new"]
    # 不再生 live 樹 history.yaml / history.md
    assert not (leaf / "history.yaml").exists()
    assert not (leaf / "history.md").exists()


def test_retire_section_rejects_unknown(make_project, write_leaf, monkeypatch):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    monkeypatch.chdir(home.parent)
    assert rs_cmd.run(["a/nope"]) == 1
    assert not (home / "corpus" / "_archive").exists()


# （test_check_enforces_history_binding 已移除：history.md 改為可選散文細節、乾淨 ## <id>
#   非硬綁；舊的破折號雙向 binding check 在 P2 退場 redesign 移除。）


def test_status_flags_leftover_develop_as_developing(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    # 已結晶（concept+decisions）但 develop.md 還在 → developing，不是 ready
    write_leaf(home, "a/x",
               concept={"id": "c1", "title": "X", "order": 1},
               decisions=[{"id": "d1", "status": "accepted", "statement": "s"}],
               develop="還在討論")
    monkeypatch.chdir(home.parent)
    assert status_cmd.run(["--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    row = next(r for r in data["sections"] if r["section"] == "a/x")
    assert row["state"] == "developing"
