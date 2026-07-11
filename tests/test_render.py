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


def test_ledger_lives_in_sidecar_not_frontmatter(make_project, write_leaf, monkeypatch):
    """ISSUE-3：指紋帳本住隱藏 sidecar，_latest frontmatter 只剩 article/version。"""
    from dspx.layout import Layout
    from dspx.render import read_ledger
    home = _setup(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    latest = _latest(home)
    render_cmd.run(["g"])
    # 寫點散文再 render，確保有指紋
    latest.write_text(latest.read_text("utf-8").replace("## 1. 概覽\n", "## 1. 概覽\n\n內文。\n"), "utf-8")
    render_cmd.run(["g"])
    meta, _ = parse_frontmatter(latest.read_text("utf-8"))
    assert "sections" not in meta and set(meta) <= {"article", "version"}
    ledger_file = Layout(home).docs_ledger("g")
    assert ledger_file.is_file()
    # 機器簿記住 docspec/（planning_home）底下的 .ledger/、**不在 docs/（交付物）**
    assert ledger_file.parent.name == ".ledger"
    assert home in ledger_file.parents
    assert Layout(home).docs_dir not in ledger_file.parents
    assert "g/intro" in read_ledger(Layout(home), "g")


def test_ledger_migrates_from_old_frontmatter(make_project, write_leaf, monkeypatch, capsys):
    """更舊格式（sections 在 frontmatter、無 sidecar）＝fingerprint v1：read_ledger fallback
    仍讀得到；常規 render 拒跑（v1 值與 v2 算法不可比）、`--rebaseline` 一次遷移
    （sidecar 建立＋版本鍵、frontmatter sections 消失、散文保留）。"""
    from dspx.layout import Layout
    from dspx.render import read_ledger, read_ledger_version
    home = _setup(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    latest = _latest(home)
    latest.parent.mkdir(parents=True, exist_ok=True)
    # 模擬舊格式：sections 在 frontmatter、無 sidecar
    latest.write_text(
        "---\narticle: g\nversion: 0.0.0\n"
        "sections:\n  g/intro:\n    prose: deadbeef\n---\n\n<!-- dspx:section g/intro -->\n## 1. 概覽\n\n舊文。\n",
        encoding="utf-8")
    assert not Layout(home).docs_ledger("g").is_file()
    assert read_ledger(Layout(home), "g").get("g/intro", {}).get("prose") == "deadbeef"  # fallback
    assert read_ledger_version(Layout(home), "g") == 1
    capsys.readouterr()
    assert render_cmd.run(["g"]) != 0           # 舊版本帳本：常規 render 拒跑、零改動
    assert "older fingerprint version" in capsys.readouterr().err
    assert not Layout(home).docs_ledger("g").is_file()
    assert render_cmd.run(["g", "--rebaseline"]) == 0   # 顯式一次遷移
    assert Layout(home).docs_ledger("g").is_file()
    assert read_ledger_version(Layout(home), "g") == 3   # 遷移後＝現行版本
    meta, _ = parse_frontmatter(latest.read_text("utf-8"))
    assert "sections" not in meta               # frontmatter 已遷出
    assert "舊文。" in latest.read_text("utf-8")  # 散文原樣保留


def test_render_builds_skeleton_in_order(make_project, write_leaf, monkeypatch):
    home = _setup(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    assert render_cmd.run(["g"]) == 0
    text = _latest(home).read_text(encoding="utf-8")
    # 兩節各有隱形標記 + 標題，依 order
    assert "<!-- dspx:section g/intro -->" in text
    assert "<!-- dspx:section g/usage -->" in text
    assert text.index("g/intro") < text.index("g/usage")
    assert "## 1. 概覽" in text and "## 2. 用法" in text   # 章號 derive 注入標題前綴


def test_render_preserves_written_prose(make_project, write_leaf, monkeypatch):
    home = _setup(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    # 模擬 draft：在 intro 槽寫散文
    latest = _latest(home)
    text = latest.read_text(encoding="utf-8")
    text = text.replace("## 1. 概覽\n", "## 1. 概覽\n\n限流保護後端。\n")
    latest.write_text(text, encoding="utf-8")
    # 再 render：散文要保留，且 intro 記了 hash
    render_cmd.run(["g"])
    text2 = latest.read_text(encoding="utf-8")
    assert "限流保護後端。" in text2
    # 指紋帳本現存隱藏 sidecar（ISSUE-3），不在 _latest frontmatter
    from dspx.layout import Layout
    from dspx.render import read_ledger
    ledger = read_ledger(Layout(home), "g")
    assert "g/intro" in ledger      # 有散文 → 記 hash
    assert "g/usage" not in ledger  # 沒散文 → 不記


def test_status_synced_after_draft_and_render(make_project, write_leaf, monkeypatch):
    home = _setup(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    latest = _latest(home)
    latest.write_text(
        latest.read_text(encoding="utf-8").replace("## 1. 概覽\n", "## 1. 概覽\n\n內文。\n"),
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
    t = t.replace("## 1. Sec\n", "## 1. Sec\n\n父散文。\n").replace("### 1.1 A\n", "### 1.1 A\n\n子散文。\n")
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
        latest.read_text(encoding="utf-8").replace("## 1. 概覽\n", "## 1. 概覽\n\n原始散文。\n"),
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
    assert "# 指南" in text                 # 根節＝doc 標題（根不編號）
    assert "## 1. 簡介" in text             # 子節＝## ＋章號前綴
    assert "<!-- dspx:section guide -->" in text
    assert text.count("# 指南") == 1        # 不重複（沒有 bare # article + ## root）
    # 根節在最前
    assert text.index("# 指南") < text.index("## 1. 簡介")


def test_no_root_falls_back_to_humanized_title(make_project, write_leaf, monkeypatch):
    """A1：無根節 → 封面標題退回 humanize slug（非裸 slug）。"""
    from dspx.commands import render as render_cmd
    home = make_project()
    write_leaf(home, "guide/intro", concept={"id": "c1", "title": "簡介", "order": 1})
    monkeypatch.chdir(home.parent)
    render_cmd.run(["guide"])
    text = (home.parent / "docs" / "guide" / "_latest.md").read_text(encoding="utf-8")
    assert "# Guide" in text and "## 1. 簡介" in text


def test_no_root_uses_article_group_yaml_title(make_project, write_leaf, monkeypatch):
    """A1：無根節 + corpus/<article>/group.yaml title → 封面在地化標題（治 CJK 文件冒拼音 slug）。"""
    from dspx.commands import render as render_cmd
    home = make_project()
    write_leaf(home, "guide/intro", concept={"id": "c1", "title": "簡介", "order": 1})
    (home / "corpus" / "guide" / "group.yaml").write_text("title: 系統概念\n", encoding="utf-8")
    monkeypatch.chdir(home.parent)
    render_cmd.run(["guide"])
    text = (home.parent / "docs" / "guide" / "_latest.md").read_text(encoding="utf-8")
    assert "# 系統概念" in text and "# Guide" not in text


def test_group_node_uses_localized_group_yaml_title(make_project, write_leaf, monkeypatch):
    """② 分組節點放 group.yaml → 標題在地化（治中文文件冒英文 slug 標題）。"""
    home = make_project()
    write_leaf(home, "g/howto/s3", concept={"id": "c1", "title": "S3 後端", "order": 1})
    (home / "corpus" / "g" / "howto" / "group.yaml").write_text("title: 操作指南\n", encoding="utf-8")
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    text = _latest(home).read_text(encoding="utf-8")
    assert "## 1. 操作指南" in text                    # group.yaml title 生效＋章號前綴
    assert "Howto" not in text and "How-to" not in text  # 不再冒英文 slug


def test_group_node_falls_back_to_humanize(make_project, write_leaf, monkeypatch):
    """② 無 group.yaml → 維持路徑末段 humanize（向後相容）。"""
    home = make_project()
    write_leaf(home, "g/howto/s3", concept={"id": "c1", "title": "S3 後端", "order": 1})
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    text = _latest(home).read_text(encoding="utf-8")
    assert "## 1. Howto" in text                        # humanize fallback（既有行為）＋章號前綴


def test_group_node_sorts_by_group_yaml_order(make_project, write_leaf, monkeypatch):
    """B8：分組節點 group.yaml order 排在有序兄弟之間（非固定 0.0 排最前）。"""
    home = make_project()
    write_leaf(home, "g/intro", concept={"id": "c1", "title": "簡介", "order": 1})
    write_leaf(home, "g/methods/a", concept={"id": "c2", "title": "方法A", "order": 1})
    write_leaf(home, "g/results", concept={"id": "c3", "title": "結果", "order": 4})
    (home / "corpus" / "g" / "methods" / "group.yaml").write_text(
        "title: 方法\norder: 3.0\n", encoding="utf-8")
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    text = _latest(home).read_text(encoding="utf-8")
    # order：簡介(1) < 方法(3) < 結果(4)＝章號 1./2./3.
    assert text.index("## 1. 簡介") < text.index("## 2. 方法") < text.index("## 3. 結果")


def test_group_node_without_order_keeps_default(make_project, write_leaf, monkeypatch):
    """B8 回歸：分組節點無 order → 維持既有預設 0.0（無回歸）。"""
    home = make_project()
    write_leaf(home, "g/intro", concept={"id": "c1", "title": "簡介", "order": 1})
    write_leaf(home, "g/methods/a", concept={"id": "c2", "title": "方法A", "order": 1})
    (home / "corpus" / "g" / "methods" / "group.yaml").write_text("title: 方法\n", encoding="utf-8")
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    text = _latest(home).read_text(encoding="utf-8")
    # 無 order → 分組 0.0 排在 intro(1) 之前（既有行為，未變）＝章號 1./2.
    assert text.index("## 1. 方法") < text.index("## 2. 簡介")


def test_render_output_locked_byte_for_byte(make_project, write_leaf, monkeypatch):
    """projection-order-and-map-fixes 1.1 回歸鎖：抽共用 outline 排序器前先鎖住 render 輸出。

    golden＝抽取**前**（d700c68）對本 fixture（group.yaml order＋concept.order＋非字典序末節
    ＋兩節散文）實跑的 `_latest.md` 全文與各節指紋——重構後 MUST 逐 byte 相同（行為不變）。"""
    from dspx.layout import Layout
    from dspx.render import read_ledger
    home = make_project()
    write_leaf(home, "g/foreword", concept={"id": "c-fw", "title": "前言", "order": 0.5})
    write_leaf(home, "g/intro", concept={"id": "c-in", "title": "簡介", "order": 1})
    write_leaf(home, "g/methods/analysis", concept={"id": "c-ma", "title": "分析", "order": 2})
    write_leaf(home, "g/methods/survey", concept={"id": "c-ms", "title": "調查", "order": 1})
    write_leaf(home, "g/annex-b", concept={"id": "c-ab", "title": "附錄B", "order": 99})
    (home / "corpus" / "g" / "methods" / "group.yaml").write_text(
        "title: 方法\norder: 3.0\n", encoding="utf-8")
    monkeypatch.chdir(home.parent)
    assert render_cmd.run(["g"]) == 0
    latest = _latest(home)
    text = latest.read_text(encoding="utf-8")
    text = text.replace("### 3.1 調查\n", "### 3.1 調查\n\n調查散文內容。\n")
    text = text.replace("## 1. 前言\n", "## 1. 前言\n\n前言散文內容。\n")
    latest.write_text(text, encoding="utf-8")
    assert render_cmd.run(["g"]) == 0

    # 章號 derive（D4）：全 arabic — 前言(0.5)=1./簡介(1)=2./方法群(3.0)=3.（子 3.1/3.2）/附錄B(99)=4.。
    # 章號只在 heading 行注入、不寫入 corpus/散文 → 指紋帳本（own/anc/deps/norm/style/prose）逐 byte 不變。
    golden = (
        "---\narticle: g\nversion: 0.0.0\n---\n# G\n\n"
        "<!-- dspx:section g/foreword -->\n## 1. 前言\n\n前言散文內容。\n\n"
        "<!-- dspx:section g/intro -->\n## 2. 簡介\n\n\n"
        "<!-- dspx:group g/methods -->\n## 3. 方法\n\n"
        "<!-- dspx:section g/methods/survey -->\n### 3.1 調查\n\n調查散文內容。\n\n"
        "<!-- dspx:section g/methods/analysis -->\n### 3.2 分析\n\n\n"
        "<!-- dspx:section g/annex-b -->\n## 4. 附錄B\n\n"
    )
    assert latest.read_text(encoding="utf-8") == golden          # 全文逐 byte
    # 指紋 golden＝fingerprint v3 算法實跑值。v3＝own 軸把 concept.yaml 的 `order`（位置元資料）
    # 排除於 hash 外（改 order/搬位不誤標 stale-own）——故 own 值自 v2 一次性跳點；anc/deps/norm/
    # style/prose 算法未變（與 v2 同值）。own 經 CRLF 正規化後**跨 OS 位元一致**（同 fixture 在
    # Windows/Linux 得同值）。
    _style = {"guide": "e3b0c44298fc1c14", "gloss": "4f53cda18c2baa0c",
              "purpose": "e3b0c44298fc1c14"}
    golden_ledger = {
        "g/foreword": {"own": "f2fdde6b035bcbe9", "anc": "e3b0c44298fc1c14", "deps": "",
                       "norm": "", "style": _style, "prose": "70bd4b9c2c6996e3"},
        "g/methods/survey": {"own": "b767e1456cfe2672", "anc": "e3b0c44298fc1c14", "deps": "",
                             "norm": "", "style": _style, "prose": "3caa63c3965f8115"},
    }
    assert read_ledger(Layout(home), "g") == golden_ledger       # 各節指紋逐 byte


def test_heading_level_clamped_to_max(make_project, write_leaf, monkeypatch):
    """③ 過深章節樹：render clamp 至 H5（四級），絕不吐字面 #######。"""
    home = make_project()
    write_leaf(home, "g/a/b/c/d/e", concept={"id": "c1", "title": "葉", "order": 1})  # depth 5 → 本應 H6
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    text = _latest(home).read_text(encoding="utf-8")
    assert "######" not in text                         # 不吐 H6+（CommonMark 字面文字）
    # 章號深度與 `#` clamp 獨立：`#` clamp 至 H5，章號仍帶完整點分編號（1.1.1.1.1）。
    assert "##### 1.1.1.1.1 葉" in text                  # 末節 clamp 至 H5（四級）＋完整章號


def test_strip_markers():
    text = "<!-- dspx:section a -->\n## A\n內文\n<!-- dspx:section b -->\n## B\n"
    out = strip_markers(text)
    assert "dspx:section" not in out
    assert "## A" in out and "內文" in out


# ── 圖引用解析（lint-false-positive-batch D2：lazy alt、單一定義）────────────

def test_find_image_refs_alt_with_bracket():
    """alt 含裸 `]`（如 errors[]）不再咬斷整條引用——V14/check ⑨/export 同時生效。"""
    from dspx.render import find_image_refs
    body = "前文。\n\n![errors[] 佇列圖](assets/q.png)\n\n後文。\n"
    assert find_image_refs(body) == ["assets/q.png"]


def test_find_image_refs_plain_title_whitespace_unchanged():
    """一般引用（含 title、路徑前空白）行為不回歸。"""
    from dspx.render import find_image_refs
    body = '![系統架構圖](assets/arch.png "架構")\n\n![圖]( assets/b.png )\n'
    assert find_image_refs(body) == ["assets/arch.png", "assets/b.png"]


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
    text = text.replace("## 1. 概覽\n", "## 1. 概覽\n\n限流保護後端。\n")
    text = text.replace("## 2. 用法\n", "## 2. 用法\n\n呼叫 API 即可。\n")
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


# ── F2：散文未重寫時 source 指紋不前進（保住 stale 信號） ────────────

def _sync_of(home, article, section):
    """重算某節的 sync 狀態（同 status._leaf_row 邏輯）。"""
    from dspx.commands.status import _docs_hashes, _leaf_row
    from dspx.layout import Layout
    from dspx.model import decision_index, load_project
    from dspx.schema import load_schema
    layout = Layout(home)
    leaves = load_project(layout)
    by = {lf.section: lf for lf in leaves}
    return _leaf_row(layout, by[section], load_schema(), True,
                     _docs_hashes(layout, article), by, decision_index(leaves))["sync"]


def test_f2_source_change_without_prose_rewrite_keeps_stale_signal(
        make_project, write_leaf, monkeypatch):
    """F2 核心：源改了但散文未重寫，再 render（哪怕只重生骨架）也 MUST 保住 stale-own
    ——不被『現在源料』抹掉信號（修 false-green）。"""
    from dspx.layout import Layout
    from dspx.render import read_ledger
    home = _setup(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    latest = _latest(home)
    # draft：intro 寫散文 → render 定基準
    latest.write_text(
        latest.read_text("utf-8").replace("## 1. 概覽\n", "## 1. 概覽\n\n限流保護後端。\n"), "utf-8")
    render_cmd.run(["g"])
    assert _sync_of(home, "g", "g/intro") == "synced"
    own_before = read_ledger(Layout(home), "g")["g/intro"]["own"]

    # 改 intro 自己的源（concept），但散文一個字沒動
    cpt = home / "corpus" / "g" / "intro" / "concept.yaml"
    cpt.write_text(cpt.read_text("utf-8").replace("title: 概覽", "title: 概覽（修訂）"), "utf-8")
    assert _sync_of(home, "g", "g/intro") == "stale-own"     # 源改 → 該重寫

    # 關鍵：再 render（散文仍未重寫）→ 信號 MUST 存活、own 指紋 MUST 凍住
    render_cmd.run(["g"])
    assert _sync_of(home, "g", "g/intro") == "stale-own"     # 不被抹成 synced（false-green）
    assert read_ledger(Layout(home), "g")["g/intro"]["own"] == own_before  # 指紋未前進


def test_f2_prose_rewrite_advances_fingerprints(make_project, write_leaf, monkeypatch):
    """F2 對偶：散文真的重寫（基於新源）→ 指紋前進、回 synced。"""
    from dspx.layout import Layout
    from dspx.render import read_ledger
    home = _setup(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    latest = _latest(home)
    latest.write_text(
        latest.read_text("utf-8").replace("## 1. 概覽\n", "## 1. 概覽\n\n舊散文。\n"), "utf-8")
    render_cmd.run(["g"])
    cpt = home / "corpus" / "g" / "intro" / "concept.yaml"
    cpt.write_text(cpt.read_text("utf-8").replace("title: 概覽", "title: 概覽（修訂）"), "utf-8")
    assert _sync_of(home, "g", "g/intro") == "stale-own"
    own_stale = read_ledger(Layout(home), "g")["g/intro"]["own"]

    # 重寫散文 → render → 指紋前進、synced
    latest.write_text(latest.read_text("utf-8").replace("舊散文。", "已對齊新源的散文。"), "utf-8")
    render_cmd.run(["g"])
    assert _sync_of(home, "g", "g/intro") == "synced"
    assert read_ledger(Layout(home), "g")["g/intro"]["own"] != own_stale  # 前進


# ── F5：--ack 給 stale-inherited 一個 acknowledge/重蓋章路徑（治 F2 副作用） ──

def test_f5_ack_clears_stale_inherited(make_project, write_leaf, monkeypatch):
    """祖先 brief 改了、但本節散文依設計合理不需改 → 普通 render 因 F2 卡 stale-inherited；
    --ack 重蓋 anc 章 → 回 synced（不必捏造散文）。"""
    home = make_project()
    write_leaf(home, "doc/sec", concept={"id": "p1", "title": "Sec", "order": 1,
                                         "concept": "父概念", "brief": {"受眾": "X"}})
    write_leaf(home, "doc/sec/a", concept={"id": "c1", "title": "A", "order": 1})
    monkeypatch.chdir(home.parent)
    render_cmd.run(["doc"])
    latest = home.parent / "docs" / "doc" / "_latest.md"
    latest.write_text(latest.read_text("utf-8").replace("### 1.1 A\n", "### 1.1 A\n\n子散文。\n"), "utf-8")
    render_cmd.run(["doc"])
    assert _sync_of(home, "doc", "doc/sec/a") == "synced"

    # 改父 brief → 子節 stale-inherited
    sec = home / "corpus" / "doc" / "sec" / "concept.yaml"
    sec.write_text(sec.read_text("utf-8").replace("受眾: X", "受眾: Y"), "utf-8")
    assert _sync_of(home, "doc", "doc/sec/a") == "stale-inherited"
    # 普通 render（不重寫散文）→ F2 沿用舊 anc → 仍卡 stale-inherited
    render_cmd.run(["doc"])
    assert _sync_of(home, "doc", "doc/sec/a") == "stale-inherited"
    # --ack → 重蓋 anc → synced
    assert render_cmd.run(["doc", "--ack", "doc/sec/a"]) == 0
    assert _sync_of(home, "doc", "doc/sec/a") == "synced"


def test_f5_ack_refused_on_stale_own(make_project, write_leaf, monkeypatch, capsys):
    """守門：節其實 stale-own（自己源變了＝需重寫散文）→ --ack 拒絕、保住信號、警告。"""
    home = _setup(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    latest = _latest(home)
    latest.write_text(latest.read_text("utf-8").replace("## 1. 概覽\n", "## 1. 概覽\n\n內文。\n"), "utf-8")
    render_cmd.run(["g"])
    cpt = home / "corpus" / "g" / "intro" / "concept.yaml"
    cpt.write_text(cpt.read_text("utf-8").replace("title: 概覽", "title: 概覽（改）"), "utf-8")
    assert _sync_of(home, "g", "g/intro") == "stale-own"
    capsys.readouterr()
    render_cmd.run(["g", "--ack", "g/intro"])          # 嘗試 ack
    assert _sync_of(home, "g", "g/intro") == "stale-own"   # 仍 stale-own（沒被吞）
    assert "refused" in capsys.readouterr().err


# ── 13b：關閉式標記剝除（凍結快照）＋不掩蓋手改 ─────────────────────────


def test_strip_markers_drops_closing_form_lines():
    """7.1a/c：關閉式 `<!-- /dspx… -->` 行被剝除；開啟式剝除行為不變、散文保留。"""
    text = ("<!-- dspx:section g/x -->\n## T\n\n內文。\n"
            "<!-- /dspx:section g/x -->\n"
            "<!-- / dspx:group g -->\n"
            "<!-- dspx:group g -->\n尾。\n")
    out = strip_markers(text)
    assert "dspx" not in out                       # 開啟式＋關閉式全剝
    assert "內文。" in out and "尾。" in out and "## T" in out


def test_closing_marker_in_body_still_counts_as_prose_drift(make_project, write_leaf,
                                                            monkeypatch):
    """7.1b：手加關閉式標記行仍算該節散文（parse 刻意不剝）→ prose 指紋變、diff 報漂移。"""
    from dspx.layout import Layout
    from dspx.render import detect_drift
    home = _setup(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    latest = _latest(home)
    latest.write_text(latest.read_text("utf-8").replace("## 1. 概覽\n", "## 1. 概覽\n\n內文。\n"), "utf-8")
    render_cmd.run(["g"])                              # 記 prose 指紋
    assert detect_drift(Layout(home), "g") == []
    latest.write_text(latest.read_text("utf-8").replace(
        "內文。\n", "內文。\n<!-- /dspx:section g/intro -->\n"), "utf-8")
    assert [d["section"] for d in detect_drift(Layout(home), "g")] == ["g/intro"]


# ── 13a：CJK 封面 stderr 提示（Decision 9）──────────────────────────────


def test_cjk_slug_cover_hint_fires_only_with_cjk_prose(make_project, write_leaf,
                                                       monkeypatch, capsys):
    """7.2a/d：CJK 散文＋slug 封面 → stderr 提示、輸出檔不變；空文章（無散文）→ 沉默。"""
    home = make_project()
    write_leaf(home, "gongyuan/x", concept={"id": "c1", "title": "節", "order": 1})
    monkeypatch.chdir(home.parent)
    assert render_cmd.run(["gongyuan"]) == 0           # 空文章：fallback "en" → 無提示
    assert "cover title falls back" not in capsys.readouterr().err
    latest = home.parent / "docs" / "gongyuan" / "_latest.md"
    latest.write_text(latest.read_text("utf-8").replace("## 1. 節\n", "## 1. 節\n\n中文內文散文。\n"),
                      "utf-8")
    assert render_cmd.run(["gongyuan"]) == 0
    err = capsys.readouterr().err
    assert ('cover title falls back to the humanized slug "Gongyuan" '
            "but the article's content is CJK") in err
    assert "corpus/gongyuan/group.yaml" in err and "title:" in err
    text = latest.read_text("utf-8")
    assert "cover title falls back" not in text        # 提示只上 stderr、不進輸出檔
    assert "# Gongyuan" in text                        # 封面照舊 humanize fallback（無行為變更）


def test_cjk_cover_hint_silent_with_group_title(make_project, write_leaf, monkeypatch, capsys):
    """7.2b：group.yaml title 在 → 無提示、封面在地化。"""
    home = make_project()
    write_leaf(home, "art/x", concept={"id": "c1", "title": "節", "order": 1})
    (home / "corpus" / "art" / "group.yaml").write_text(
        yaml.safe_dump({"title": "在地化標題"}, allow_unicode=True), encoding="utf-8")
    monkeypatch.chdir(home.parent)
    render_cmd.run(["art"])
    latest = home.parent / "docs" / "art" / "_latest.md"
    latest.write_text(latest.read_text("utf-8").replace("## 1. 節\n", "## 1. 節\n\n中文散文內容。\n"),
                      "utf-8")
    capsys.readouterr()
    assert render_cmd.run(["art"]) == 0
    assert "cover title falls back" not in capsys.readouterr().err
    assert "# 在地化標題" in latest.read_text("utf-8")


def test_cjk_cover_hint_silent_with_root_section(make_project, write_leaf, monkeypatch, capsys):
    """7.2c：root 節存在（封面＝root 標題、非 fallback）→ 無提示。"""
    home = make_project()
    write_leaf(home, "art", concept={"id": "c1", "title": "根", "order": 1})
    monkeypatch.chdir(home.parent)
    render_cmd.run(["art"])
    latest = home.parent / "docs" / "art" / "_latest.md"
    latest.write_text(latest.read_text("utf-8").replace("# 根\n", "# 根\n\n中文導言散文。\n"),
                      "utf-8")
    capsys.readouterr()
    assert render_cmd.run(["art"]) == 0
    assert "cover title falls back" not in capsys.readouterr().err


def test_cjk_cover_hint_silent_for_english_prose(make_project, write_leaf, monkeypatch, capsys):
    """7.2e：英文散文 → 非 CJK 多數 → 無提示。"""
    home = make_project()
    write_leaf(home, "gateway/x", concept={"id": "c1", "title": "Node", "order": 1})
    monkeypatch.chdir(home.parent)
    render_cmd.run(["gateway"])
    latest = home.parent / "docs" / "gateway" / "_latest.md"
    latest.write_text(latest.read_text("utf-8").replace(
        "## 1. Node\n", "## 1. Node\n\nEnglish prose body for the section.\n"), "utf-8")
    capsys.readouterr()
    assert render_cmd.run(["gateway"]) == 0
    assert "cover title falls back" not in capsys.readouterr().err


# ── 4. 章號 derive（D4/D7）：outline 推導、F2 沿用、export 相容、numbering 政策 ──────────


def _headings(text: str) -> list[str]:
    """從 _latest.md 抽出所有標題行的文字（去 `#` 前綴）。"""
    import re as _re
    return [ln.split(" ", 1)[1] for ln in text.split("\n")
            if _re.match(r"^#{1,6}\s", ln)]


def test_numbering_injected_into_headings(make_project, write_leaf, monkeypatch):
    """4.1：leaf＋分組節點標題皆注入 derive 章號（頂層 arabic 尾綴一點 6.、子節 6.1）；
    corpus title 欄不含任何章號（單一真相＝order＋樹位置）。"""
    home = make_project()
    write_leaf(home, "g/intro", concept={"id": "c1", "title": "簡介", "order": 1})
    write_leaf(home, "g/methods/a", concept={"id": "c2", "title": "方法A", "order": 1})
    (home / "corpus" / "g" / "methods" / "group.yaml").write_text(
        "title: 方法\norder: 2\n", encoding="utf-8")
    monkeypatch.chdir(home.parent)
    assert render_cmd.run(["g"]) == 0
    text = _latest(home).read_text(encoding="utf-8")
    assert "## 1. 簡介" in text          # 頂層 arabic：尾綴一點
    assert "## 2. 方法" in text          # 分組節點同步編號
    assert "### 2.1 方法A" in text       # 子節：父前綴 + .序（無尾點）
    # corpus title 欄不含章號
    cpt = (home / "corpus" / "g" / "intro" / "concept.yaml").read_text("utf-8")
    assert "title: 簡介" in cpt and "1." not in cpt.split("title:", 1)[1].split("\n", 1)[0]


def test_f2_reorder_renumbers_without_staleness(make_project, write_leaf, monkeypatch):
    """4.2：調換分組節點 order 後重 render → 受影響 leaf 標題自動重編號，但散文 byte 不變、
    own/anc/deps 指紋逐 byte 沿用（F2）→ status 不誤標 stale-own。

    採「分組 order 調換」而非 leaf order：leaf 的 order 住 concept.yaml、屬 source_hash 輸入，
    改它本就是 stale-own（引擎既定契約、guide 指向 --ack-own）；分組 order 住 group.yaml、非 leaf
    源，重排它只改骨架呈現＝純章號 churn，正是本測要釘的「編號變動不誤標髒」。"""
    from dspx.layout import Layout
    from dspx.render import read_ledger
    home = make_project()
    write_leaf(home, "g/alpha/x", concept={"id": "cx", "title": "X 節", "order": 1})
    write_leaf(home, "g/beta/y", concept={"id": "cy", "title": "Y 節", "order": 1})
    (home / "corpus" / "g" / "alpha" / "group.yaml").write_text(
        "title: 甲群\norder: 1\n", encoding="utf-8")
    (home / "corpus" / "g" / "beta" / "group.yaml").write_text(
        "title: 乙群\norder: 2\n", encoding="utf-8")
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    latest = _latest(home)
    t = latest.read_text("utf-8")
    t = t.replace("### 1.1 X 節\n", "### 1.1 X 節\n\nX 散文。\n")
    t = t.replace("### 2.1 Y 節\n", "### 2.1 Y 節\n\nY 散文。\n")
    latest.write_text(t, encoding="utf-8")
    render_cmd.run(["g"])                       # 定基準
    before = latest.read_text("utf-8")
    assert "### 1.1 X 節" in before and "### 2.1 Y 節" in before
    ledger_before = read_ledger(Layout(home), "g")

    # 調換分組 order（甲↔乙）：只動 group.yaml、不碰 leaf concept
    (home / "corpus" / "g" / "alpha" / "group.yaml").write_text(
        "title: 甲群\norder: 2\n", encoding="utf-8")
    (home / "corpus" / "g" / "beta" / "group.yaml").write_text(
        "title: 乙群\norder: 1\n", encoding="utf-8")
    render_cmd.run(["g"])
    after = latest.read_text("utf-8")

    # (a) 標題自動重編號：乙群現為 1.（Y=1.1）、甲群 2.（X=2.1）
    assert "### 1.1 Y 節" in after and "### 2.1 X 節" in after
    assert "### 1.1 X 節" not in after and "### 2.1 Y 節" not in after
    # (b) 散文 byte 不變
    assert "X 散文。" in after and "Y 散文。" in after
    # (c) status 不誤標 stale-own（own 未動）
    assert _sync_of(home, "g", "g/alpha/x") == "synced"
    assert _sync_of(home, "g", "g/beta/y") == "synced"
    # (d) own/anc/deps 指紋逐 byte 沿用（F2）
    ledger_after = read_ledger(Layout(home), "g")
    for sec in ("g/alpha/x", "g/beta/y"):
        for axis in ("own", "anc", "deps", "prose"):
            assert ledger_after[sec][axis] == ledger_before[sec][axis]


def test_export09_denumber_recognizes_injected_forms(make_project, write_leaf, monkeypatch):
    """4.3：render 注入的章號形態＝export #09 去編號後處理的輸入假設（相容釘死、不改 export spec）。
    頂層 `N.`、子節 `N.M`、附錄 `附錄 A`／`A.1` 皆須被 `_denumber_manual_headings` 認得並改寫，
    否則 numbered profile 下會雙重編號。"""
    from dspx.commands.export._preprocess import _denumber_manual_headings
    home = make_project()
    write_leaf(home, "g/intro", concept={"id": "c1", "title": "簡介", "order": 1})
    write_leaf(home, "g/methods/a", concept={"id": "c2", "title": "方法A", "order": 1})
    (home / "corpus" / "g" / "methods" / "group.yaml").write_text(
        "title: 方法\norder: 2\n", encoding="utf-8")
    write_leaf(home, "g/annex", concept={"id": "c3", "title": "附錄一", "order": 3,
                                         "numbering": "appendix"})
    write_leaf(home, "g/annex/detail", concept={"id": "c4", "title": "細節", "order": 1})
    monkeypatch.chdir(home.parent)
    assert render_cmd.run(["g"]) == 0
    text = _latest(home).read_text(encoding="utf-8")
    # render 實際注入的章號形態（釘住輸入形狀）
    expected = ["1. 簡介", "2. 方法", "2.1 方法A", "附錄 A 附錄一", "A.1 細節"]
    heads = _headings(text)
    for e in expected:
        assert e in heads, f"render 未注入預期章號形態：{e}（實得 {heads}）"
        # 每個帶章號標題餵進 export 去編號 → 必被改寫成 #heading(... numbering: none ...)
        out = _denumber_manual_headings(f"= {e}\n")
        assert out.startswith("#heading(level: 1, numbering: none)["), \
            f"export #09 未認得 render 注入形態：{e}"


def test_numbering_single_source_render_matches_topology(make_project, write_leaf, monkeypatch):
    """4.4：render 標題章號、aperture documentMap number、共用 outline 拓樸三處同源
    （outline_numbering 單一真相）。"""
    from dspx.aperture import project
    from dspx.config import load_config
    from dspx.layout import Layout
    from dspx.model import load_project
    from dspx.render import outline_numbering
    from dspx.schema import load_schema
    home = make_project()
    write_leaf(home, "g/intro", concept={"id": "c1", "title": "簡介", "order": 1,
                                         "concept": "界定"})
    write_leaf(home, "g/methods/a", concept={"id": "c2", "title": "方法A", "order": 1,
                                             "concept": "方法"})
    (home / "corpus" / "g" / "methods" / "group.yaml").write_text(
        "title: 方法\norder: 2\n", encoding="utf-8")
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    layout = Layout(home)
    leaves = load_project(layout)
    art_leaves = [lf for lf in leaves if lf.article == "g"]
    labels = outline_numbering(layout, art_leaves, "g")
    text = _latest(home).read_text(encoding="utf-8")
    # render 標題含拓樸推導的章號
    by = {lf.section: lf for lf in art_leaves}
    assert f"## {labels['g/intro']} {by['g/intro'].title}" in text
    assert f"### {labels['g/methods/a']} {by['g/methods/a'].title}" in text
    assert f"## {labels['g/methods']} 方法" in text
    # documentMap 的 number 欄同源
    proj = project(layout, load_schema(), "draft", "g/intro", leaves, load_config(home))
    dm = {r["section"]: r for r in proj.document_map}
    assert dm["g/intro"]["number"] == labels["g/intro"] == "1."
    assert dm["g/methods"]["number"] == labels["g/methods"] == "2."
    assert dm["g/methods/a"]["number"] == labels["g/methods/a"] == "2.1"


def test_numbering_appendix_letters_and_none_not_consuming(make_project, write_leaf, monkeypatch):
    """4.5：附錄字母序（附錄 A／A.1）＋ none 不佔阿拉伯號＋附錄不佔阿拉伯號（D7）。"""
    from dspx.layout import Layout
    from dspx.model import load_project
    from dspx.render import outline_numbering
    home = make_project()
    write_leaf(home, "doc/a", concept={"id": "c1", "title": "甲", "order": 1})
    write_leaf(home, "doc/hist", concept={"id": "c2", "title": "修訂歷史", "order": 2,
                                          "numbering": "none"})
    write_leaf(home, "doc/b", concept={"id": "c3", "title": "乙", "order": 3})
    write_leaf(home, "doc/anx1", concept={"id": "c4", "title": "附錄一", "order": 4,
                                          "numbering": "appendix"})
    write_leaf(home, "doc/anx1/sub", concept={"id": "c5", "title": "子項", "order": 1})
    write_leaf(home, "doc/anx2", concept={"id": "c6", "title": "附錄二", "order": 5,
                                          "numbering": "appendix"})
    write_leaf(home, "doc/c", concept={"id": "c7", "title": "丙", "order": 6})
    monkeypatch.chdir(home.parent)
    layout = Layout(home)
    art_leaves = [lf for lf in load_project(layout) if lf.article == "doc"]
    labels = outline_numbering(layout, art_leaves, "doc")
    assert labels["doc/a"] == "1."               # arabic 1
    assert labels["doc/hist"] is None            # none：不編號
    assert labels["doc/b"] == "2."               # none 未佔號 → 仍是 2（非 3）
    assert labels["doc/anx1"] == "附錄 A"         # appendix 字母序（獨立計數）
    assert labels["doc/anx1/sub"] == "A.1"       # 附錄子節退回阿拉伯、承字母前綴
    assert labels["doc/anx2"] == "附錄 B"
    assert labels["doc/c"] == "3."               # 附錄未佔阿拉伯號 → a=1,b=2,c=3


def test_numbering_appendix_renders_realistic_annex(make_project, write_leaf, monkeypatch):
    """4.5：附錄節實跑 render → 標題注入「附錄 A」式編號（其子節 A.1）。"""
    home = make_project()
    write_leaf(home, "spec/scope", concept={"id": "c1", "title": "範圍", "order": 1})
    write_leaf(home, "spec/annexA", concept={"id": "c2", "title": "詞彙表", "order": 2,
                                             "numbering": "appendix"})
    write_leaf(home, "spec/annexA/terms", concept={"id": "c3", "title": "術語", "order": 1})
    write_leaf(home, "spec/annexB", concept={"id": "c4", "title": "參考文獻", "order": 3,
                                             "numbering": "appendix"})
    monkeypatch.chdir(home.parent)
    assert render_cmd.run(["spec"]) == 0
    text = (home.parent / "docs" / "spec" / "_latest.md").read_text(encoding="utf-8")
    assert "## 1. 範圍" in text                  # 正文 arabic
    assert "## 附錄 A 詞彙表" in text            # 頂層附錄字母
    assert "### A.1 術語" in text                # 附錄子節
    assert "## 附錄 B 參考文獻" in text          # 第二附錄＝B（不佔 arabic）
    assert "## 2. 詞彙表" not in text            # 附錄不冒 arabic 號
