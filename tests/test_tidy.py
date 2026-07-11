"""docspec tidy（確定性、冪等的 corpus 遷移：刪空殼／剝重複 brief／剝章號／改名 via mv）。

覆蓋：四動作逐一、spec 情境（只剝逐字重複）、層級章號完整剝除、slug 改名（含 `/`、撞名、
article root 排除）、--dry-run 零 byte 變更、live history.yaml 只報告不動、冪等（二跑零動作）、
改名後散文零丟失回歸、紅 check 時改名跳過但其餘動作照做。
"""

from __future__ import annotations

from pathlib import Path

import yaml

from dspx.commands import check as check_cmd
from dspx.commands import render as render_cmd
from dspx.commands import tidy as tidy_cmd
from dspx.layout import Layout


def _leaf(write_leaf, home, section, *, cid, title, order=1, brief=None, **extra):
    write_leaf(home, section, concept={
        "id": cid, "title": title, "order": order, "concept": title,
        "brief": brief if brief is not None else {}}, **extra)


def _read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


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


# ── 動作 1：空殼 decisions.yaml ────────────────────────────────────────────

def test_tidy_deletes_empty_shell_decisions(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    _leaf(write_leaf, home, "sc/殼節", cid="c1", title="殼節", decisions=[])   # entries: []
    _leaf(write_leaf, home, "sc/實節", cid="c2", title="實節", order=2,
          decisions=[{"id": "d1", "statement": "真決策", "status": "active"}])
    # 空 mapping 與純空白檔也是空殼
    empty_map = home / "corpus" / "sc" / "空映" ; empty_map.mkdir(parents=True)
    _leaf(write_leaf, home, "sc/空映", cid="c3", title="空映", order=3)
    (home / "corpus" / "sc" / "空映" / "decisions.yaml").write_text("{}\n", encoding="utf-8")
    _leaf(write_leaf, home, "sc/空白", cid="c4", title="空白", order=4)
    (home / "corpus" / "sc" / "空白" / "decisions.yaml").write_text("   \n", encoding="utf-8")
    # 壞檔（頂層 list）不是空殼——不能被 tidy 吃掉；但它會讓 load_model fail-loud，
    # 這裡不放壞檔（loader 行為另有回歸測試），只驗空殼三型＋實檔保留。

    monkeypatch.chdir(home.parent)
    assert tidy_cmd.run([]) == 0
    out = capsys.readouterr().out
    assert "sc/殼節/decisions.yaml" in out
    assert "sc/空映/decisions.yaml" in out
    assert "sc/空白/decisions.yaml" in out
    assert not (home / "corpus" / "sc" / "殼節" / "decisions.yaml").exists()
    assert not (home / "corpus" / "sc" / "空映" / "decisions.yaml").exists()
    assert not (home / "corpus" / "sc" / "空白" / "decisions.yaml").exists()
    assert (home / "corpus" / "sc" / "實節" / "decisions.yaml").is_file()      # 真決策保留
    assert "render sc --rebaseline" in out                                     # 收尾提示


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
    assert tidy_cmd.run([]) == 0
    out = capsys.readouterr().out
    assert "sc/child/concept.yaml brief.audience" in out

    child = _read_yaml(home / "corpus" / "sc" / "child" / "concept.yaml")
    assert "audience" not in child["brief"]            # 逐字相同 → 刪
    assert child["brief"]["depth"] == "深入"           # 一字之差 → 保留
    child2 = _read_yaml(home / "corpus" / "sc" / "child2" / "concept.yaml")
    assert "brief" not in child2                       # 空 brief 整塊省略＝繼承
    root = _read_yaml(home / "corpus" / "sc" / "concept.yaml")
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
    # group.yaml title 同樣剝（資料夾名先取剝後 slug、免二次改名）
    gdir = home / "corpus" / "sc" / "群組" ; gdir.mkdir(parents=True)
    (gdir / "group.yaml").write_text(
        yaml.safe_dump({"title": "3. 群組", "order": 9}, allow_unicode=True), encoding="utf-8")
    _leaf(write_leaf, home, "sc/群組/子節", cid="c6", title="子節", order=1)

    monkeypatch.chdir(home.parent)
    assert tidy_cmd.run([]) == 0
    out = capsys.readouterr().out

    c = lambda sec: _read_yaml(home / "corpus" / sec / "concept.yaml")["title"]
    assert c("sc/防撞防護區域安全機能") == "防撞防護區域安全機能"
    assert c("sc/概觀") == "概觀"                       # 完整層級前綴：不是 "1 概觀"
    assert c("sc/範圍") == "範圍"
    assert c("sc/5G 網路架構") == "5G 網路架構"         # 數字後接字母＝名稱本體，不觸發
    assert c("sc/純數字") == "6."                       # 只剩空→不動
    assert "skip title strip" in out and "純數字" in out
    assert _read_yaml(gdir / "group.yaml")["title"] == "群組"


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
    assert tidy_cmd.run([]) == 0
    out = capsys.readouterr().out
    assert "sc/safety/protective-zone -> sc/safety/防撞防護區域安全機能" in out

    assert not (home / "corpus" / "sc" / "safety" / "protective-zone").exists()
    new_dir = home / "corpus" / "sc" / "safety" / "防撞防護區域安全機能"
    assert (new_dir / "concept.yaml").is_file()
    assert _read_yaml(new_dir / "concept.yaml")["title"] == "防撞防護區域安全機能"  # 先剝再改名
    # _latest marker 已由 mv 交易重寫
    latest = Layout(home).docs_latest("sc").read_text(encoding="utf-8")
    assert "<!-- dspx:section sc/safety/防撞防護區域安全機能 -->" in latest
    # 事後 check 全綠
    assert check_cmd.run([]) == 0


def test_tidy_renames_group_folder_from_group_yaml_title(
        make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    gdir = home / "corpus" / "sc" / "safety" ; gdir.mkdir(parents=True)
    (gdir / "group.yaml").write_text(
        yaml.safe_dump({"title": "安全機能", "order": 1}, allow_unicode=True), encoding="utf-8")
    _leaf(write_leaf, home, "sc/safety/zone", cid="c1", title="zone")
    _leaf(write_leaf, home, "sc/arch", cid="c2", title="arch", order=2)
    _render(home, monkeypatch, "sc")
    capsys.readouterr()

    monkeypatch.chdir(home.parent)
    assert tidy_cmd.run([]) == 0
    assert (home / "corpus" / "sc" / "安全機能" / "zone" / "concept.yaml").is_file()
    assert not (home / "corpus" / "sc" / "safety").exists()
    assert check_cmd.run([]) == 0


def test_tidy_sibling_slug_collision_keeps_both_and_reports(
        make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    _leaf(write_leaf, home, "sc/alpha", cid="c1", title="同名節")
    _leaf(write_leaf, home, "sc/beta", cid="c2", title="同名節", order=2)
    _render(home, monkeypatch, "sc")
    capsys.readouterr()

    monkeypatch.chdir(home.parent)
    assert tidy_cmd.run([]) == 0
    out = capsys.readouterr().out
    assert "rename conflict" in out and "sc/同名節" in out
    assert (home / "corpus" / "sc" / "alpha" / "concept.yaml").is_file()   # 兩者原地保留
    assert (home / "corpus" / "sc" / "beta" / "concept.yaml").is_file()
    assert not (home / "corpus" / "sc" / "同名節").exists()


def test_tidy_never_renames_article_root(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    _leaf(write_leaf, home, "sc", cid="root", title="跨運車控制架構",
          brief={"audience": "a", "depth": "d", "breadth": "b"})
    _leaf(write_leaf, home, "sc/arch", cid="c1", title="arch")
    _render(home, monkeypatch, "sc")
    capsys.readouterr()

    monkeypatch.chdir(home.parent)
    assert tidy_cmd.run([]) == 0
    assert (home / "corpus" / "sc" / "concept.yaml").is_file()             # root 資料夾不動
    assert not (home / "corpus" / "跨運車控制架構").exists()


def test_tidy_slug_strips_slash_without_extra_dir_level(
        make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    _leaf(write_leaf, home, "sc/io", cid="c1", title="輸入/輸出介面")
    _leaf(write_leaf, home, "sc/arch", cid="c2", title="arch", order=2)
    _render(home, monkeypatch, "sc")
    capsys.readouterr()

    monkeypatch.chdir(home.parent)
    assert tidy_cmd.run([]) == 0
    assert (home / "corpus" / "sc" / "輸入輸出介面" / "concept.yaml").is_file()
    assert not (home / "corpus" / "sc" / "輸入").exists()                  # 不產生額外層級
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
    assert tidy_cmd.run(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "delete empty-shell decisions.yaml: sc/shell/decisions.yaml" in out
    assert "brief.audience" in out
    assert '"6.1 概觀" -> "概觀"' in out
    assert "rename: sc/shell -> sc/概觀" in out          # slug 以剝章號後 title 為基準
    assert "nothing written" in out
    assert _snapshot_tree(home.parent) == before          # 零 byte 變更


# ── live 樹 history.yaml：只報告、不動 ─────────────────────────────────────

def test_tidy_reports_live_history_yaml_untouched(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    _leaf(write_leaf, home, "sc/old", cid="c1", title="old",
          history=[{"id": "h1", "statement": "退場理由", "status": "superseded"}])

    monkeypatch.chdir(home.parent)
    assert tidy_cmd.run([]) == 0
    out = capsys.readouterr().out
    assert "sc/old/history.yaml" in out
    assert "status: superseded" in out                    # 遷移指引
    assert (home / "corpus" / "sc" / "old" / "history.yaml").is_file()   # 未動


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
    assert tidy_cmd.run([]) == 0
    first = capsys.readouterr().out
    assert "action(s) applied" in first
    assert (home / "corpus" / "sc" / "防撞防護" / "concept.yaml").is_file()

    assert tidy_cmd.run([]) == 0
    second = capsys.readouterr().out
    assert "nothing to do" in second and "0 actions" in second
    # 二跑後磁碟不再變動（冪等的實體斷言）
    snap = _snapshot_tree(home.parent)
    assert tidy_cmd.run([]) == 0
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
    assert tidy_cmd.run([]) == 0
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
    assert tidy_cmd.run([]) == 0
    out = capsys.readouterr().out
    assert "SKIPPED all folder renames" in out
    assert "sc/a -> sc/甲節" in out                        # 列出本會執行的清單
    assert not (home / "corpus" / "sc" / "a" / "decisions.yaml").exists()   # 空殼照刪
    assert (home / "corpus" / "sc" / "a" / "concept.yaml").is_file()        # 未改名
    assert not (home / "corpus" / "sc" / "甲節").exists()


# ── CLI 面 ─────────────────────────────────────────────────────────────────

def test_tidy_registered_and_help_exits_zero(capsys):
    from dspx.commands import REGISTRY
    assert "tidy" in REGISTRY
    import pytest
    with pytest.raises(SystemExit) as exc:
        tidy_cmd.run(["--help"])
    assert exc.value.code == 0
    assert "--dry-run" in capsys.readouterr().out
