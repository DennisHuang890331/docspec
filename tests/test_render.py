"""render flow：骨架同步、保留散文、hash 記錄、publish 剝標記、lint 忽略標記。"""

from __future__ import annotations

import yaml

from dspx.commands import lint as lint_cmd
from dspx.commands import publish as publish_cmd
from dspx.commands import render as render_cmd
from dspx.frontmatter import parse_frontmatter
from dspx.render import MARKER_RE, strip_markers


def _setup(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "g/intro", concept={"id": "c1", "title": "概覽", "order": 1})
    write_leaf(home, "g/usage", concept={"id": "c2", "title": "用法", "order": 2})
    return home


def _latest(home):
    return home.parent / "docs" / "g" / "_latest.md"


def test_render_builds_skeleton_in_order(make_project, write_leaf, monkeypatch):
    home = _setup(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    assert render_cmd.run(["g"]) == 0
    text = _latest(home).read_text(encoding="utf-8")
    # 兩節各有隱形標記 + 標題，依 order
    assert "<!-- dspx:section g/intro -->" in text
    assert "<!-- dspx:section g/usage -->" in text
    assert text.index("g/intro") < text.index("g/usage")
    assert "## 概覽" in text and "## 用法" in text


def test_render_preserves_written_prose(make_project, write_leaf, monkeypatch):
    home = _setup(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    # 模擬 draft：在 intro 槽寫散文
    latest = _latest(home)
    text = latest.read_text(encoding="utf-8")
    text = text.replace("## 概覽\n", "## 概覽\n\n限流保護後端。\n")
    latest.write_text(text, encoding="utf-8")
    # 再 render：散文要保留，且 intro 記了 hash
    render_cmd.run(["g"])
    text2 = latest.read_text(encoding="utf-8")
    assert "限流保護後端。" in text2
    meta, _ = parse_frontmatter(text2)
    assert "g/intro" in meta["sections"]      # 有散文 → 記 hash
    assert "g/usage" not in meta["sections"]  # 沒散文 → 不記


def test_status_synced_after_draft_and_render(make_project, write_leaf, monkeypatch):
    home = _setup(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    latest = _latest(home)
    latest.write_text(
        latest.read_text(encoding="utf-8").replace("## 概覽\n", "## 概覽\n\n內文。\n"),
        encoding="utf-8")
    render_cmd.run(["g"])
    from dspx.commands.status import _docs_hashes
    from dspx.layout import Layout
    from dspx.model import load_project
    layout = Layout(home)
    leaves = {lf.section: lf for lf in load_project(layout)}
    hashes = _docs_hashes(layout, "g")
    assert hashes["g/intro"]["own"] == leaves["g/intro"].source_hash()  # synced


def test_two_flavor_staleness(make_project, write_leaf, monkeypatch):
    """父 brief 改→子節 stale-inherited；子節自己改→stale-own。"""
    from dspx.commands import render as render_cmd
    from dspx.commands.status import _docs_hashes, _leaf_row
    from dspx.layout import Layout
    from dspx.model import load_project
    home = make_project()
    # 父節 sec（有自己的 concept/brief）＋ 子末節 sec/a
    write_leaf(home, "doc/sec", concept={"id": "p1", "title": "Sec", "order": 1,
                                         "concept": "父概念", "brief": {"受眾": "X"}})
    write_leaf(home, "doc/sec/a", concept={"id": "c1", "title": "A", "order": 1})
    monkeypatch.chdir(home.parent)
    render_cmd.run(["doc"])
    latest = home.parent / "docs" / "doc" / "_latest.md"
    # 兩節都寫散文
    t = latest.read_text(encoding="utf-8")
    t = t.replace("## Sec\n", "## Sec\n\n父散文。\n").replace("## A\n", "## A\n\n子散文。\n")
    latest.write_text(t, encoding="utf-8")
    render_cmd.run(["doc"])

    def sync_of(section):
        from dspx.model import decision_index
        layout = Layout(home)
        leaves = load_project(layout)
        by = {lf.section: lf for lf in leaves}
        h = _docs_hashes(layout, "doc")
        from dspx.schema import load_schema
        return _leaf_row(layout, by[section], load_schema(), True, h, by,
                         decision_index(leaves))["sync"]

    assert sync_of("doc/sec/a") == "synced"
    # 改父節 brief（子節自己的檔沒動）→ 子節 stale-inherited
    sec_concept = home / "corpus" / "doc" / "sec" / "concept.yaml"
    sec_concept.write_text(
        sec_concept.read_text(encoding="utf-8").replace("受眾: X", "受眾: Y"), encoding="utf-8")
    assert sync_of("doc/sec/a") == "stale-inherited"
    assert sync_of("doc/sec") == "stale-own"   # 父節自己的源變了＝對它自己是 stale-own


def test_diff_detects_hand_edit(make_project, write_leaf, monkeypatch):
    """手改 _latest 散文 → diff 抓到；重 render 後 → 不再漂移。"""
    from dspx.commands import render as render_cmd
    from dspx.layout import Layout
    from dspx.render import detect_drift
    home = _setup(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    latest = _latest(home)
    latest.write_text(
        latest.read_text(encoding="utf-8").replace("## 概覽\n", "## 概覽\n\n原始散文。\n"),
        encoding="utf-8")
    render_cmd.run(["g"])                       # 定基準
    assert detect_drift(Layout(home), "g") == []   # 剛 render，無漂移

    # 直接手改交付物（不經 render）
    latest.write_text(
        latest.read_text(encoding="utf-8").replace("原始散文。", "被偷改的散文。"),
        encoding="utf-8")
    drift = detect_drift(Layout(home), "g")
    assert len(drift) == 1 and drift[0]["section"] == "g/intro"

    render_cmd.run(["g"])                       # 重 render = 接受、重設基準
    assert detect_drift(Layout(home), "g") == []


def test_root_section_is_intro(make_project, write_leaf, monkeypatch):
    """根節(section==article)＝# 標題＋導言；子節 ##；無重複純標題。"""
    from dspx.commands import render as render_cmd
    home = make_project()
    write_leaf(home, "guide", concept={"id": "root", "title": "指南", "order": 1})
    write_leaf(home, "guide/intro", concept={"id": "c1", "title": "簡介", "order": 1})
    monkeypatch.chdir(home.parent)
    render_cmd.run(["guide"])
    text = (home.parent / "docs" / "guide" / "_latest.md").read_text(encoding="utf-8")
    assert "# 指南" in text                 # 根節＝doc 標題
    assert "## 簡介" in text                # 子節＝##
    assert "<!-- dspx:section guide -->" in text
    assert text.count("# 指南") == 1        # 不重複（沒有 bare # article + ## root）
    # 根節在最前
    assert text.index("# 指南") < text.index("## 簡介")


def test_no_root_falls_back_to_bare_title(make_project, write_leaf, monkeypatch):
    """無根節 → 退回印一行純標題（不強制導言）。"""
    from dspx.commands import render as render_cmd
    home = make_project()
    write_leaf(home, "guide/intro", concept={"id": "c1", "title": "簡介", "order": 1})
    monkeypatch.chdir(home.parent)
    render_cmd.run(["guide"])
    text = (home.parent / "docs" / "guide" / "_latest.md").read_text(encoding="utf-8")
    assert "# guide" in text and "## 簡介" in text


def test_strip_markers():
    text = "<!-- dspx:section a -->\n## A\n內文\n<!-- dspx:section b -->\n## B\n"
    out = strip_markers(text)
    assert "dspx:section" not in out
    assert "## A" in out and "內文" in out


def test_lint_ignores_section_markers(make_project, write_leaf, monkeypatch):
    home = _setup(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    # _latest 滿是 <!-- dspx:section --> 標記，lint 不該因此報 ERROR
    from dspx.layout import Layout
    from dspx.lint import ERROR, run_lint
    from dspx.model import load_project
    from dspx.schema import load_schema
    layout = Layout(home)
    findings = run_lint(layout, load_project(layout), load_schema())
    assert [f for f in findings if f.level == ERROR] == []


def test_publish_snapshot_is_marker_free(make_project, write_leaf, monkeypatch):
    home = _setup(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    latest = _latest(home)
    # 兩節都寫散文（publish 要求至少有 drafted）
    text = latest.read_text(encoding="utf-8")
    text = text.replace("## 概覽\n", "## 概覽\n\n限流保護後端。\n")
    text = text.replace("## 用法\n", "## 用法\n\n呼叫 API 即可。\n")
    latest.write_text(text, encoding="utf-8")
    assert publish_cmd.run(["g"]) == 0
    snapshot = home.parent / "docs" / "g" / "archive" / "v1.0.0.md"
    snap_text = snapshot.read_text(encoding="utf-8")
    # ★凍結快照完全無隱形標記
    assert "dspx:section" not in snap_text
    assert not any(MARKER_RE.match(line) for line in snap_text.split("\n"))
    # 散文還在
    assert "限流保護後端。" in snap_text and "呼叫 API 即可。" in snap_text


def test_publish_aborts_when_nothing_drafted(make_project, write_leaf, monkeypatch):
    home = _setup(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])  # 只有骨架、無散文
    assert publish_cmd.run(["g"]) == 1
