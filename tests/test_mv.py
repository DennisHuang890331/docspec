"""docspec mv（引擎交易原語：改名/搬移＋path-keyed 引用同步重寫；原子、失敗零半套）。

覆蓋：節改名全鏈綠（marker/audit/roadmap 重寫）、subtree（group）改名、中途失敗零半套、
root/跨 article 拒絕、asset 模式改名＋圖引用重寫。
"""

from __future__ import annotations

from pathlib import Path

import yaml

from dspx.commands.corpus import mv as mv_cmd
from dspx.commands.deliverable import render as render_cmd
from dspx.layout import Layout


def _leaf(write_leaf, home, section, *, cid, title="X", order=1):
    write_leaf(home, section, concept={
        "id": cid, "title": title, "order": order, "concept": title,
        "brief": {"audience": "a", "depth": "d", "breadth": "b", "forbidden": ["f"]}})


def _render(home: Path, monkeypatch, article) -> Layout:
    monkeypatch.chdir(home.parent)
    render_cmd.run([article])
    return Layout(home)


def _inject_prose(layout: Layout, article: str, section: str, body: str) -> None:
    """在 section marker 對應的標題行後插入 body 段。"""
    p = layout.docs_latest(article)
    lines = p.read_text(encoding="utf-8").split("\n")
    marker = f"<!-- dspx:section {section} -->"
    out: list[str] = []
    i = 0
    while i < len(lines):
        out.append(lines[i])
        if lines[i].strip() == marker:
            # 下一行是標題；插在標題後
            if i + 1 < len(lines):
                out.append(lines[i + 1])
                i += 1
            out.append("")
            out.append(body)
        i += 1
    p.write_text("\n".join(out), encoding="utf-8", newline="\n")


# ── 節模式 ─────────────────────────────────────────────────────────────────

def test_mv_leaf_rewrites_marker_and_preserves_prose(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    _leaf(write_leaf, home, "sc/safety/protective-zone", cid="c1", title="防護區")
    _leaf(write_leaf, home, "sc/arch", cid="c2", title="架構", order=2)
    layout = _render(home, monkeypatch, "sc")
    _inject_prose(layout, "sc", "sc/safety/protective-zone", "本節描述防撞防護區域安全機能。")
    render_cmd.run(["sc"])   # 記 prose 指紋
    capsys.readouterr()

    monkeypatch.chdir(home.parent)
    rc = mv_cmd.run(["sc/safety/protective-zone", "sc/safety/防撞防護區域安全機能"])
    assert rc == 0

    # 資料夾改名
    assert not (home / "corpus" / "sc" / "safety" / "protective-zone").exists()
    assert (home / "corpus" / "sc" / "safety" / "防撞防護區域安全機能" / "concept.yaml").is_file()

    # _latest marker 重寫為新路徑、散文原樣保留
    latest = layout.docs_latest("sc").read_text(encoding="utf-8")
    assert "<!-- dspx:section sc/safety/防撞防護區域安全機能 -->" in latest
    assert "<!-- dspx:section sc/safety/protective-zone -->" not in latest
    assert "本節描述防撞防護區域安全機能。" in latest

    out = capsys.readouterr().out
    assert "section marker" in out
    assert "render sc --rebaseline" in out


def test_mv_rewrites_audit_and_roadmap_targets(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    _leaf(write_leaf, home, "sc/safety/zone", cid="c1")
    _leaf(write_leaf, home, "sc/arch", cid="c2", order=2)
    _render(home, monkeypatch, "sc")
    layout = Layout(home)

    # per-article audit + roadmap 指向舊路徑（含 #anchor 與 concept-id target）
    from dspx.audit import doc_audit_path
    from dspx.roadmap import doc_roadmap_path
    doc_audit_path(layout, "sc").write_text(yaml.safe_dump({"findings": [
        {"id": "F1", "face": "logic", "severity": "low", "status": "open",
         "finding": "x", "targets": ["sc/safety/zone#seg", "c2"], "suggestion": ""},
    ]}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    doc_roadmap_path(layout, "sc").write_text(yaml.safe_dump({"entries": [
        {"id": "R1", "kind": "gap", "target": "sc/safety/zone"},
    ]}, allow_unicode=True, sort_keys=False), encoding="utf-8")

    monkeypatch.chdir(home.parent)
    assert mv_cmd.run(["sc/safety/zone", "sc/safety/區域"]) == 0

    audit = yaml.safe_load(doc_audit_path(layout, "sc").read_text(encoding="utf-8"))
    assert audit["findings"][0]["targets"][0] == "sc/safety/區域#seg"   # #anchor 保留
    assert audit["findings"][0]["targets"][1] == "c2"                    # concept-id 不動
    roadmap = yaml.safe_load(doc_roadmap_path(layout, "sc").read_text(encoding="utf-8"))
    assert roadmap["entries"][0]["target"] == "sc/safety/區域"


def test_mv_group_subtree_remaps_descendants(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    _leaf(write_leaf, home, "sc/safety/zone-a", cid="c1")
    _leaf(write_leaf, home, "sc/safety/zone-b", cid="c2", order=2)
    _leaf(write_leaf, home, "sc/arch", cid="c3", order=2)
    layout = _render(home, monkeypatch, "sc")
    capsys.readouterr()

    monkeypatch.chdir(home.parent)
    # 改整個 group `sc/safety` → `sc/安全`
    assert mv_cmd.run(["sc/safety", "sc/安全"]) == 0

    assert (home / "corpus" / "sc" / "安全" / "zone-a" / "concept.yaml").is_file()
    assert (home / "corpus" / "sc" / "安全" / "zone-b" / "concept.yaml").is_file()
    assert not (home / "corpus" / "sc" / "safety").exists()

    latest = layout.docs_latest("sc").read_text(encoding="utf-8")
    assert "<!-- dspx:section sc/安全/zone-a -->" in latest
    assert "<!-- dspx:section sc/安全/zone-b -->" in latest
    assert "<!-- dspx:group sc/安全 -->" in latest
    assert "sc/safety" not in latest


def test_mv_aborts_when_destination_exists(make_project, write_leaf, monkeypatch):
    home = make_project()
    _leaf(write_leaf, home, "sc/a", cid="c1")
    _leaf(write_leaf, home, "sc/b", cid="c2", order=2)
    layout = _render(home, monkeypatch, "sc")
    before = layout.docs_latest("sc").read_text(encoding="utf-8")

    monkeypatch.chdir(home.parent)
    rc = mv_cmd.run(["sc/a", "sc/b"])   # 目標已存在
    assert rc == 1
    # 零半套：原資料夾仍在、目標仍是原本的 b、_latest 未動
    assert (home / "corpus" / "sc" / "a" / "concept.yaml").is_file()
    assert layout.docs_latest("sc").read_text(encoding="utf-8") == before


def test_mv_rollback_on_check_failure(make_project, write_leaf, monkeypatch):
    """中途失敗（check 紅）→ 資料夾與所有檔案回滾至原狀。

    構造：audit finding 的 target 指向一個「搬移後仍不存在」的死引用，使搬移後 check 轉紅。
    這裡直接讓 check 在搬移後偵測到問題——用一個引用 old 路徑但 mv 不會重寫的偽造 store
    不現實；改以 monkeypatch 讓 run_check 在第二次呼叫回紅，驗回滾。"""
    import dspx.commands.corpus.mv as mvmod

    home = make_project()
    _leaf(write_leaf, home, "sc/a", cid="c1")
    _leaf(write_leaf, home, "sc/b", cid="c2", order=2)
    layout = _render(home, monkeypatch, "sc")
    before_latest = layout.docs_latest("sc").read_text(encoding="utf-8")

    calls = {"n": 0}
    real = mvmod._check_result

    class _Red:
        ok = False
        errors = ["synthetic post-move failure"]

    def fake(layout_, schema_):
        calls["n"] += 1
        if calls["n"] == 1:
            return real(layout_, schema_)   # pre-check 綠、放行
        return _Red()                        # post-move 紅 → 觸發回滾

    monkeypatch.setattr(mvmod, "_check_result", fake)
    monkeypatch.chdir(home.parent)
    rc = mv_cmd.run(["sc/a", "sc/新"])
    assert rc == 1
    # 回滾：資料夾回原位、目標不存在、_latest 還原
    assert (home / "corpus" / "sc" / "a" / "concept.yaml").is_file()
    assert not (home / "corpus" / "sc" / "新").exists()
    assert layout.docs_latest("sc").read_text(encoding="utf-8") == before_latest


def test_mv_refuses_article_root(make_project, write_leaf, monkeypatch):
    home = make_project()
    _leaf(write_leaf, home, "sc/a", cid="c1")
    _render(home, monkeypatch, "sc")
    monkeypatch.chdir(home.parent)
    rc = mv_cmd.run(["sc", "control"])
    assert rc == 1
    assert (home / "corpus" / "sc" / "a" / "concept.yaml").is_file()


def test_mv_refuses_cross_article(make_project, write_leaf, monkeypatch):
    home = make_project()
    _leaf(write_leaf, home, "sc/a", cid="c1")
    _leaf(write_leaf, home, "other/z", cid="c2")
    _render(home, monkeypatch, "sc")
    _render(home, monkeypatch, "other")
    monkeypatch.chdir(home.parent)
    rc = mv_cmd.run(["sc/a", "other/a"])
    assert rc == 1
    assert (home / "corpus" / "sc" / "a" / "concept.yaml").is_file()


def test_mv_refuses_unknown_section(make_project, write_leaf, monkeypatch):
    home = make_project()
    _leaf(write_leaf, home, "sc/a", cid="c1")
    _render(home, monkeypatch, "sc")
    monkeypatch.chdir(home.parent)
    assert mv_cmd.run(["sc/nope", "sc/x"]) == 1


def test_mv_refuses_illegal_destination(make_project, write_leaf, monkeypatch):
    home = make_project()
    _leaf(write_leaf, home, "sc/a", cid="c1")
    _render(home, monkeypatch, "sc")
    monkeypatch.chdir(home.parent)
    # `_` 前綴段＝引擎隱形保留，validate_section_path 拒收
    assert mv_cmd.run(["sc/a", "sc/_hidden"]) == 2
    assert (home / "corpus" / "sc" / "a" / "concept.yaml").is_file()


# ── asset 模式 ─────────────────────────────────────────────────────────────

def test_mv_asset_renames_file_and_rewrites_refs(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    _leaf(write_leaf, home, "sc/a", cid="c1",)
    layout = _render(home, monkeypatch, "sc")

    # 建 docs/assets/old-diagram.png（per-article layout → docs/sc/assets/）並在 _latest 引用
    assets = layout.docs_assets_dir("sc")
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "old-diagram.png").write_bytes(b"\x89PNG\r\n\x1a\n fake")
    _inject_prose(layout, "sc", "sc/a", "見下圖：\n\n![防護區](assets/old-diagram.png)")
    render_cmd.run(["sc"])
    capsys.readouterr()

    monkeypatch.chdir(home.parent)
    rc = mv_cmd.run([str(assets / "old-diagram.png"), "new-diagram.png"])
    assert rc == 0

    assert not (assets / "old-diagram.png").exists()
    assert (assets / "new-diagram.png").is_file()
    latest = layout.docs_latest("sc").read_text(encoding="utf-8")
    assert "![防護區](assets/new-diagram.png)" in latest
    assert "old-diagram.png" not in latest


def test_mv_asset_aborts_when_destination_exists(make_project, write_leaf, monkeypatch):
    home = make_project()
    _leaf(write_leaf, home, "sc/a", cid="c1")
    layout = _render(home, monkeypatch, "sc")
    assets = layout.docs_assets_dir("sc")
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "a.png").write_bytes(b"a")
    (assets / "b.png").write_bytes(b"b")
    monkeypatch.chdir(home.parent)
    rc = mv_cmd.run([str(assets / "a.png"), "b.png"])
    assert rc == 1
    assert (assets / "a.png").is_file()      # 未動
    assert (assets / "b.png").read_bytes() == b"b"
