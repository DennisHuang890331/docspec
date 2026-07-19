"""docspec tidy（確定性、冪等的 corpus 遷移：刪空殼／剝重複 brief／剝章號／改名 via mv）。

覆蓋：四動作逐一、spec 情境（只剝逐字重複）、層級章號完整剝除、slug 改名（含 `/`、撞名、
article root 排除）、--dry-run 零 byte 變更、live history.yaml 只報告不動、冪等（二跑零動作）、
改名後散文零丟失回歸、紅 check 時改名跳過但其餘動作照做。
"""

from __future__ import annotations

from pathlib import Path

import yaml

from dspx.commands.query import check as check_cmd
from dspx.commands.deliverable import render as render_cmd
from dspx.commands.corpus import store as store_cmd
from dspx.engine.layout import Layout


def _leaf(write_leaf, home, section, *, cid, title, order=1, brief=None, **extra):
    write_leaf(home, section, concept={
        "id": cid, "title": title, "order": order, "concept": title,
        "brief": brief if brief is not None else {}}, **extra)


def _read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _art(home, article):
    from dspx.engine import store as _store
    return _store.load_article(_store.store_path(Layout(home), article), verify=False)


def _store_concept(home, section):
    """★store-only：某節 store 記錄的 concept dict。"""
    return _art(home, section.split("/", 1)[0]).record_by_path(section).concept


def _store_group_title(home, section):
    rec = _art(home, section.split("/", 1)[0]).record_by_path(section)
    return (rec.group or {}).get("title") if rec else None


def _store_sections(home, article):
    """★store-only：某篇 store 全部 section 路徑集合。"""
    return {r.path for r in _art(home, article).records}


def _snapshot_tree(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in sorted(root.rglob("*")) if p.is_file()}


def _render(home: Path, monkeypatch, article) -> Layout:
    monkeypatch.chdir(home.parent)
    render_cmd.run([article])
    return Layout(home)


def _inject_prose(layout: Layout, article: str, section: str, body: str) -> None:
    p = layout.docs_latest(article)
    lines = p.read_text(encoding="utf-8").split("\n")
    marker = f"<!-- dspx:section {section} -->"
    out: list[str] = []
    i = 0
    while i < len(lines):
        out.append(lines[i])
        if lines[i].strip() == marker:
            if i + 1 < len(lines):
                out.append(lines[i + 1])
                i += 1
            out.append("")
            out.append(body)
        i += 1
    p.write_text("\n".join(out), encoding="utf-8", newline="\n")


# ── 動作 1（★store-only 已消滅）：空殼 decisions 由 store canonical serializer 天然不落地 ──

def test_store_never_persists_empty_shell_decisions(make_project, write_leaf, monkeypatch, capsys):
    """★store-only：`decisions=[]` 空殼在 store canonical serializer 天然不落地（無 `decisions:`
    區塊），根本沒有可刪的空殼檔——舊 tidy「刪空殼 decisions.yaml」動作因此結構性消滅。
    tidy 對空殼節＝零動作；真決策節照常保留。"""
    home = make_project()
    _leaf(write_leaf, home, "sc/殼節", cid="c1", title="殼節", decisions=[])   # 空 → 不落地
    _leaf(write_leaf, home, "sc/實節", cid="c2", title="實節", order=2,
          decisions=[{"id": "d1", "statement": "真決策", "status": "accepted", "kind": "normative"}])
    monkeypatch.chdir(home.parent)

    # store 記錄：空殼節 decisions 空、實節保留（結構性、非 tidy 刪）
    assert _art(home, "sc").record_by_path("sc/殼節").decisions == []
    assert _art(home, "sc").record_by_path("sc/實節").decisions[0]["id"] == "d1"
    # store 檔文字裡沒有空殼節的 decisions 區塊
    store_text = (home / "corpus" / "sc" / "article.yaml").read_text(encoding="utf-8")
    assert "d1" in store_text and store_text.count("decisions:") == 1   # 只有實節那一塊

    assert store_cmd.run(["tidy"]) == 0
    out = capsys.readouterr().out
    assert "delete empty-shell" not in out                    # 該動作已消滅
    assert _art(home, "sc").record_by_path("sc/實節").decisions[0]["id"] == "d1"  # 真決策仍在


# ── 動作 2：brief 逐字重複剝除（spec 情境）────────────────────────────────

def test_tidy_strips_verbatim_dup_brief_field_keeps_specialized(
        make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    # article root leaf 供祖先鏈；root 信封必須完整且永不被剝
    _leaf(write_leaf, home, "sc", cid="root", title="sc",
          brief={"audience": "現場工程師", "depth": "深", "breadth": "窄"})
    # 子節：audience 與祖先 byte 相同、depth 差一字 → 只剝 audience
    _leaf(write_leaf, home, "sc/child", cid="c1", title="child",
          brief={"audience": "現場工程師", "depth": "深入"})
    # 子節：整個 brief 都是逐字複述 → brief 鍵整塊掉（＝繼承）
    _leaf(write_leaf, home, "sc/child2", cid="c2", title="child2", order=2,
          brief={"audience": "現場工程師"})

    monkeypatch.chdir(home.parent)
    assert store_cmd.run(["tidy"]) == 0
    out = capsys.readouterr().out
    assert "sc/child/concept.yaml brief.audience" in out

    child = _store_concept(home, "sc/child")
    assert "audience" not in child["brief"]            # 逐字相同 → 刪
    assert child["brief"]["depth"] == "深入"           # 一字之差 → 保留
    child2 = _store_concept(home, "sc/child2")
    assert "brief" not in child2                       # 空 brief 整塊省略＝繼承
    root = _store_concept(home, "sc")
    assert root["brief"]["audience"] == "現場工程師"   # root 永不剝


# ── 動作 3：title 章號前綴 ─────────────────────────────────────────────────

def test_tidy_strips_hierarchical_arabic_title_prefixes(
        make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    _leaf(write_leaf, home, "sc/防撞防護區域安全機能", cid="c1", title="11. 防撞防護區域安全機能")
    _leaf(write_leaf, home, "sc/概觀", cid="c2", title="6.1 概觀", order=2)
    _leaf(write_leaf, home, "sc/範圍", cid="c3", title="6、範圍", order=3)
    _leaf(write_leaf, home, "sc/5G 網路架構", cid="c4", title="5G 網路架構", order=4)
    _leaf(write_leaf, home, "sc/純數字", cid="c5", title="6.", order=5)        # 剝了變空→不動
    # group title 同樣剝（資料夾名先取剝後 slug、免二次改名）★store-only：group 是 store 記錄
    write_leaf.group(home, "sc/群組", title="3. 群組", order=9)
    _leaf(write_leaf, home, "sc/群組/子節", cid="c6", title="子節", order=1)

    monkeypatch.chdir(home.parent)
    assert store_cmd.run(["tidy"]) == 0
    out = capsys.readouterr().out

    c = lambda sec: _store_concept(home, sec)["title"]
    assert c("sc/防撞防護區域安全機能") == "防撞防護區域安全機能"
    assert c("sc/概觀") == "概觀"                       # 完整層級前綴：不是 "1 概觀"
    assert c("sc/範圍") == "範圍"
    assert c("sc/5G 網路架構") == "5G 網路架構"         # 數字後接字母＝名稱本體，不觸發
    assert c("sc/純數字") == "6."                       # 只剩空→不動
    assert "skip title strip" in out and "純數字" in out
    assert _store_group_title(home, "sc/群組") == "群組"


# ── 動作 4：改名（slug、撞名、root 排除、`/` 剝除）─────────────────────────

def test_tidy_renames_folder_to_delivery_language_slug(
        make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    _leaf(write_leaf, home, "sc/safety/protective-zone", cid="c1",
          title="11. 防撞防護區域安全機能")
    _leaf(write_leaf, home, "sc/arch", cid="c2", title="arch", order=2)
    _render(home, monkeypatch, "sc")
    capsys.readouterr()

    monkeypatch.chdir(home.parent)
    assert store_cmd.run(["tidy"]) == 0
    out = capsys.readouterr().out
    assert "sc/safety/protective-zone -> sc/safety/防撞防護區域安全機能" in out

    assert "sc/safety/protective-zone" not in _store_sections(home, "sc")
    assert "sc/safety/防撞防護區域安全機能" in _store_sections(home, "sc")
    assert _store_concept(home, "sc/safety/防撞防護區域安全機能")["title"] == "防撞防護區域安全機能"  # 先剝再改名
    # _latest marker 已由 mv 交易重寫
    latest = Layout(home).docs_latest("sc").read_text(encoding="utf-8")
    assert "<!-- dspx:section sc/safety/防撞防護區域安全機能 -->" in latest
    # 事後 check 全綠
    assert check_cmd.run([]) == 0


def test_tidy_renames_group_folder_from_group_yaml_title(
        make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    write_leaf.group(home, "sc/safety", title="安全機能", order=1)   # ★store-only：group 記錄
    _leaf(write_leaf, home, "sc/safety/zone", cid="c1", title="zone")
    _leaf(write_leaf, home, "sc/arch", cid="c2", title="arch", order=2)
    _render(home, monkeypatch, "sc")
    capsys.readouterr()

    monkeypatch.chdir(home.parent)
    assert store_cmd.run(["tidy"]) == 0
    assert "sc/安全機能/zone" in _store_sections(home, "sc")
    assert "sc/safety" not in _store_sections(home, "sc")
    assert check_cmd.run([]) == 0


def test_tidy_sibling_slug_collision_keeps_both_and_reports(
        make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    _leaf(write_leaf, home, "sc/alpha", cid="c1", title="同名節")
    _leaf(write_leaf, home, "sc/beta", cid="c2", title="同名節", order=2)
    _render(home, monkeypatch, "sc")
    capsys.readouterr()

    monkeypatch.chdir(home.parent)
    assert store_cmd.run(["tidy"]) == 0
    out = capsys.readouterr().out
    assert "rename conflict" in out and "sc/同名節" in out
    assert "sc/alpha" in _store_sections(home, "sc")   # 兩者原地保留
    assert "sc/beta" in _store_sections(home, "sc")
    assert "sc/同名節" not in _store_sections(home, "sc")


def test_tidy_never_renames_article_root(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    _leaf(write_leaf, home, "sc", cid="root", title="跨運車控制架構",
          brief={"audience": "a", "depth": "d", "breadth": "b"})
    _leaf(write_leaf, home, "sc/arch", cid="c1", title="arch")
    _render(home, monkeypatch, "sc")
    capsys.readouterr()

    monkeypatch.chdir(home.parent)
    assert store_cmd.run(["tidy"]) == 0
    assert "sc" in _store_sections(home, "sc")             # root 記錄不動（未改名）
    # ★store-only：root 未被改名成 title slug（無 corpus/跨運車控制架構.yaml store 檔）
    assert not (home / "corpus" / "跨運車控制架構.yaml").exists()


def test_tidy_slug_strips_slash_without_extra_dir_level(
        make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    _leaf(write_leaf, home, "sc/io", cid="c1", title="輸入/輸出介面")
    _leaf(write_leaf, home, "sc/arch", cid="c2", title="arch", order=2)
    _render(home, monkeypatch, "sc")
    capsys.readouterr()

    monkeypatch.chdir(home.parent)
    assert store_cmd.run(["tidy"]) == 0
    assert "sc/輸入輸出介面" in _store_sections(home, "sc")
    assert "sc/輸入" not in _store_sections(home, "sc")                  # 不產生額外層級
    assert check_cmd.run([]) == 0


# ── --dry-run 零寫入 ───────────────────────────────────────────────────────

def test_tidy_dry_run_lists_everything_and_writes_nothing(
        make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    _leaf(write_leaf, home, "sc", cid="root", title="sc",
          brief={"audience": "a", "depth": "d", "breadth": "b"})
    _leaf(write_leaf, home, "sc/shell", cid="c1", title="6.1 概觀", decisions=[],
          brief={"audience": "a"})
    _render(home, monkeypatch, "sc")
    capsys.readouterr()
    before = _snapshot_tree(home.parent)

    monkeypatch.chdir(home.parent)
    assert store_cmd.run(["tidy", "--dry-run"]) == 0
    out = capsys.readouterr().out
    # ★store-only：空殼 decisions 結構性消滅，無「delete empty-shell」動作
    assert "brief.audience" in out
    assert '"6.1 概觀" -> "概觀"' in out
    assert "rename: sc/shell -> sc/概觀" in out          # slug 以剝章號後 title 為基準
    assert "nothing written" in out
    assert _snapshot_tree(home.parent) == before          # 零 byte 變更


# ── history（★store-only）：history 住 store 記錄，tidy 只碰 brief/title/path、不動 history ──

def test_tidy_leaves_store_history_untouched(make_project, write_leaf, monkeypatch, capsys):
    """★store-only：舊「live 樹 history.yaml 只報告」動作已消滅（store 無散檔 history.yaml；
    history 是 store 記錄的一個區塊）。tidy 只改 brief/title/path，記錄的 history 一字不動。"""
    home = make_project()
    _leaf(write_leaf, home, "sc/old", cid="c1", title="6. 舊節",   # 帶章號前綴 → 觸發 title strip
          history=[{"id": "h1", "statement": "退場理由", "status": "superseded", "kind": "normative"}])

    monkeypatch.chdir(home.parent)
    assert store_cmd.run(["tidy"]) == 0
    rec = _art(home, "sc").record_by_path("sc/舊節")   # 章號剝除後改名 sc/old→sc/舊節
    assert rec.history == [{"id": "h1", "statement": "退場理由", "status": "superseded",
                            "kind": "normative"}]   # history 一字不動


# ── 冪等 ───────────────────────────────────────────────────────────────────

def test_tidy_is_idempotent_second_run_zero_actions(
        make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    _leaf(write_leaf, home, "sc", cid="root", title="sc",
          brief={"audience": "a", "depth": "d", "breadth": "b"})
    _leaf(write_leaf, home, "sc/shell", cid="c1", title="11. 防撞防護", decisions=[],
          brief={"audience": "a", "depth": "特化過的深度"})
    _leaf(write_leaf, home, "sc/arch", cid="c2", title="arch", order=2)
    _render(home, monkeypatch, "sc")
    capsys.readouterr()

    monkeypatch.chdir(home.parent)
    assert store_cmd.run(["tidy"]) == 0
    first = capsys.readouterr().out
    assert "action(s) applied" in first
    assert "sc/防撞防護" in _store_sections(home, "sc")

    assert store_cmd.run(["tidy"]) == 0
    second = capsys.readouterr().out
    assert "nothing to do" in second and "0 actions" in second
    # 二跑後磁碟不再變動（冪等的實體斷言）
    snap = _snapshot_tree(home.parent)
    assert store_cmd.run(["tidy"]) == 0
    assert _snapshot_tree(home.parent) == snap


# ── 改名後回歸：散文零丟失、check 綠 ───────────────────────────────────────

def test_tidy_rename_then_render_preserves_prose(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    _leaf(write_leaf, home, "sc/safety/protective-zone", cid="c1", title="防撞防護區域安全機能")
    _leaf(write_leaf, home, "sc/arch", cid="c2", title="arch", order=2)
    layout = _render(home, monkeypatch, "sc")
    _inject_prose(layout, "sc", "sc/safety/protective-zone", "本節描述防撞防護區域安全機能的散文。")
    render_cmd.run(["sc"])                                # 記 prose 指紋
    capsys.readouterr()

    monkeypatch.chdir(home.parent)
    assert store_cmd.run(["tidy"]) == 0
    capsys.readouterr()

    render_cmd.run(["sc"])                                # 改名後重 render
    captured = capsys.readouterr()
    assert "DISCARDED" not in captured.err                # 散文未被當無主丟棄
    latest = layout.docs_latest("sc").read_text(encoding="utf-8")
    assert "本節描述防撞防護區域安全機能的散文。" in latest
    assert "<!-- dspx:section sc/safety/防撞防護區域安全機能 -->" in latest
    assert check_cmd.run([]) == 0


# ── 紅 check：改名跳過、其餘動作照做 ───────────────────────────────────────

def test_tidy_red_check_skips_renames_but_does_other_actions(
        make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    # 撞 id ＝ check 紅（結構錯誤），但 model 照載
    _leaf(write_leaf, home, "sc/a", cid="dup", title="甲節", decisions=[])
    _leaf(write_leaf, home, "sc/b", cid="dup", title="乙節", order=2)

    monkeypatch.chdir(home.parent)
    assert store_cmd.run(["tidy"]) == 0
    out = capsys.readouterr().out
    assert "SKIPPED all record renames" in out
    assert "sc/a -> sc/甲節" in out                        # 列出本會執行的清單
    # ★store-only：空殼 decisions 結構性消滅；紅 check 下改名跳過但記錄仍在原路徑
    assert _art(home, "sc").record_by_path("sc/a").decisions == []
    assert "sc/a" in _store_sections(home, "sc")        # 未改名
    assert "sc/甲節" not in _store_sections(home, "sc")


# ── CLI 面 ─────────────────────────────────────────────────────────────────

def test_tidy_folded_into_store_and_help_exits_zero(capsys):
    from dspx.commands import REGISTRY
    assert "tidy" not in REGISTRY          # folded into `store tidy`
    assert "store" in REGISTRY
    import pytest
    with pytest.raises(SystemExit) as exc:
        store_cmd.run(["tidy", "--help"])
    assert exc.value.code == 0
    assert "--dry-run" in capsys.readouterr().out
