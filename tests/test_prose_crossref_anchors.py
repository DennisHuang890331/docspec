"""prose-crossref-anchors（P1b）：散文交叉引用改穩定錨、render 注入 §號碼。

錨形＝`<!--@<id>-->` 綁定 + render 擁有的可見標籤（`§6.5`／`附錄 A`／numbering:none 標題名）
+ closing sentinel `<!--@-->`。號碼 derive（每次 render 重算、不入源、prose 指紋正規化掉），
交叉引用變成 check 守得住的結構邊（死引用＝ERROR），未綁錨的字面章號＝lint V21 WARN。

反作弊紀律：指紋排除號碼的核心測試斷言「重排→引用節顯示號碼真的變了、但該節 status 維持
synced」，不挑「號碼沒變」的軟柿子。
"""

from __future__ import annotations

import yaml

from dspx.commands import render as render_cmd
from dspx.layout import Layout
from dspx.model import decision_index, load_project
from dspx.render import (
    normalize_prose_anchors,
    prose_hash,
    resolve_prose_anchors,
    strip_anchor_bindings,
)
from dspx.schema import load_schema


def _latest(home, article="g"):
    return home.parent / "docs" / article / "_latest.md"


def _body(home, article="g"):
    return _latest(home, article).read_text(encoding="utf-8")


def _put_prose(home, article, section, prose):
    """把 prose 塞進 `<!-- dspx:section <section> -->` 後的空槽並重 render（注入錨號碼）。"""
    latest = _latest(home, article)
    text = latest.read_text(encoding="utf-8")
    lines = text.split("\n")
    out = []
    i = 0
    while i < len(lines):
        out.append(lines[i])
        if lines[i] == f"<!-- dspx:section {section} -->" and i + 1 < len(lines):
            out.append(lines[i + 1])           # heading 行
            out.append("")
            out.append(prose)
            i += 2
            # 吃掉原本的空 body 行（到下個 marker 或檔尾前的空行）
            while i < len(lines) and lines[i].strip() == "":
                i += 1
            continue
        i += 1
    latest.write_text("\n".join(out), encoding="utf-8")
    assert render_cmd.run([article]) == 0


def _sync_of(home, article, section):
    from dspx.commands.status import _docs_hashes, _leaf_row
    layout = Layout(home)
    leaves = load_project(layout)
    by = {lf.section: lf for lf in leaves}
    return _leaf_row(layout, by[section], load_schema(), True,
                     _docs_hashes(layout, article), by, decision_index(leaves))["sync"]


def _three_section_project(make_project, write_leaf, monkeypatch):
    """g/a(order1) g/b(order2) g/c(order3)，同層兄弟＝章號 1./2./3.。"""
    home = make_project()
    write_leaf(home, "g/a", concept={"id": "sec-a", "title": "甲", "order": 1})
    write_leaf(home, "g/b", concept={"id": "sec-b", "title": "乙", "order": 2})
    write_leaf(home, "g/c", concept={"id": "sec-c", "title": "丙", "order": 3})
    monkeypatch.chdir(home.parent)
    assert render_cmd.run(["g"]) == 0
    return home


# ── 1. render 注入號碼（作者未手寫號碼）──────────────────────────────────────

def test_render_injects_number_from_anchor(make_project, write_leaf, monkeypatch):
    """散文只綁錨（`<!--@sec-c--><!--@-->`）、未寫號碼 → render 注入 §3（丙＝第 3 章）。"""
    home = _three_section_project(make_project, write_leaf, monkeypatch)
    _put_prose(home, "g", "g/a", "詳見 <!--@sec-c--><!--@--> 的說明。")
    line = next(l for l in _body(home).split("\n") if "詳見" in l)
    assert "<!--@sec-c-->§3<!--@-->" in line       # 號碼算出來的、作者沒寫


# ── 2. 反作弊核心：重排 → 顯示號碼真的變、但引用節維持 synced ─────────────────

def test_reorder_updates_number_but_referencing_section_stays_synced(
        make_project, write_leaf, monkeypatch):
    """★重排使目標 c 的章號 3→2；引用它的 a 之散文顯示號碼 §3→§2（真的變），但 a 的 status
    維持 synced（號碼 derive、排除於 prose 指紋，不誤標 drift）。"""
    home = _three_section_project(make_project, write_leaf, monkeypatch)
    _put_prose(home, "g", "g/a", "詳見 <!--@sec-c--><!--@--> 的說明。")
    _put_prose(home, "g", "g/b", "本節無引用。")
    _put_prose(home, "g", "g/c", "被引用的目標節。")
    # 基準：a 引用 c＝§3、a synced
    assert "<!--@sec-c-->§3<!--@-->" in _body(home)
    assert _sync_of(home, "g", "g/a") == "synced"
    prose_before = prose_hash("詳見 <!--@sec-c-->§3<!--@--> 的說明。")

    # 重排：把 c 的 order 提前到 1.5（甲之後、乙之前）→ c 變第 2 章
    cc = home / "corpus" / "g" / "c" / "concept.yaml"
    cc.write_text(cc.read_text("utf-8").replace("order: 3", "order: 1.5"), "utf-8")
    assert render_cmd.run(["g"]) == 0

    # 顯示號碼真的變了：§3 → §2
    line = next(l for l in _body(home).split("\n") if "詳見" in l)
    assert "<!--@sec-c-->§2<!--@-->" in line
    assert "§3" not in line
    # 但引用節 a 維持 synced（不因號碼刷新誤標 drift/stale）
    assert _sync_of(home, "g", "g/a") == "synced"
    # 指紋層面：號碼不同的兩個 body，prose_hash 相同（正規化掉號碼）
    assert prose_hash("詳見 <!--@sec-c-->§2<!--@--> 的說明。") == prose_before


# ── 3. 冪等 + 錨綁定 byte 不變 ───────────────────────────────────────────────

def test_render_idempotent_and_binding_bytes_stable(make_project, write_leaf, monkeypatch):
    """未重排連跑兩次 render → _latest byte 相同；錨綁定 `<!--@sec-c-->` byte 不變。"""
    home = _three_section_project(make_project, write_leaf, monkeypatch)
    _put_prose(home, "g", "g/a", "見 <!--@sec-c--><!--@-->。")
    once = _body(home)
    assert render_cmd.run(["g"]) == 0
    assert _body(home) == once                      # 冪等
    assert "<!--@sec-c-->" in once                  # 綁定持久


# ── 4. 只在散文 span：code fence 內的錨樣式 byte-exact 不動 ───────────────────

def test_anchor_in_code_fence_untouched():
    """fence 內 `<!--@sec-c-->§9.9<!--@-->` byte 不動；同 body 散文區的錨照解析。"""
    labels = {"sec-c": "§3"}
    body = "```\n<!--@sec-c-->§9.9<!--@-->\n```\n\n散文 <!--@sec-c--><!--@-->。"
    out = resolve_prose_anchors(body, lambda i: labels.get(i))
    assert "<!--@sec-c-->§9.9<!--@-->" in out       # fence 內原封不動
    assert "散文 <!--@sec-c-->§3<!--@-->。" in out    # 散文區解析注入


# ── 5. 改錨目標＝合法 prose drift ────────────────────────────────────────────

def test_retarget_is_real_prose_change():
    """把引用從指 X 改成指 Y（綁定變）→ prose 指紋變＝合法 drift（引用內容真的變了）。"""
    to_x = "詳見 <!--@sec-x-->§6.5<!--@-->。"
    to_y = "詳見 <!--@sec-y-->§6.5<!--@-->。"
    assert prose_hash(to_x) != prose_hash(to_y)     # 綁定變＝真變動
    # 反面：同綁定、只號碼刷新 → 指紋不變（已於 test 2 斷言，這裡補純函式面）
    assert prose_hash(to_x) == prose_hash("詳見 <!--@sec-x-->§7.2<!--@-->。")


# ── 6. numbering:none 目標 → 注入標題名、不吐空 § ────────────────────────────

def test_numbering_none_target_injects_title_no_empty_section_sign(
        make_project, write_leaf, monkeypatch):
    """錨指向 numbering:none 的節 → render 注入該節標題名（無號碼），不產出空 §。"""
    home = make_project()
    write_leaf(home, "g/a", concept={"id": "sec-a", "title": "甲", "order": 1})
    write_leaf(home, "g/hist", concept={"id": "sec-hist", "title": "修訂歷史",
                                        "order": 9, "numbering": "none"})
    monkeypatch.chdir(home.parent)
    assert render_cmd.run(["g"]) == 0
    _put_prose(home, "g", "g/a", "見 <!--@sec-hist--><!--@-->。")
    line = next(l for l in _body(home).split("\n") if "見 " in l)
    assert "<!--@sec-hist-->修訂歷史<!--@-->" in line   # 注標題名
    assert "§" not in line                              # 不吐空 §


# ── 7. check 死引用（跨文件引用第一次可驗）───────────────────────────────────

def test_check_dead_prose_anchor_is_error(make_project, write_leaf, monkeypatch):
    """散文錨指向不存在 id → check ERROR、附散文位置與失效 id。"""
    from dspx.check import run_check
    home = _three_section_project(make_project, write_leaf, monkeypatch)
    _put_prose(home, "g", "g/a", "見 <!--@sec-ghost--><!--@-->。")
    res = run_check(load_project(Layout(home)), load_schema(), Layout(home))
    assert not res.ok
    hit = [e for e in res.errors if "sec-ghost" in e and "nonexistent" in e]
    assert hit and "docs/g/_latest.md § g/a" in hit[0]


def test_check_live_prose_anchor_is_green(make_project, write_leaf, monkeypatch):
    """錨指向存在活節 → check 綠（引用可解析）。"""
    from dspx.check import run_check
    home = _three_section_project(make_project, write_leaf, monkeypatch)
    _put_prose(home, "g", "g/a", "見 <!--@sec-c--><!--@-->。")
    res = run_check(load_project(Layout(home)), load_schema(), Layout(home))
    assert not [e for e in res.errors if "anchor" in e]


def test_check_retired_prose_anchor_is_error(make_project, write_leaf, monkeypatch):
    """錨指向已退役（deprecated concept）id → check 死引用 ERROR。"""
    from dspx.check import run_check
    home = make_project()
    write_leaf(home, "g/a", concept={"id": "sec-a", "title": "甲", "order": 1})
    write_leaf(home, "g/old", concept={"id": "sec-old", "title": "舊", "order": 2,
                                       "status": "deprecated"})
    monkeypatch.chdir(home.parent)
    assert render_cmd.run(["g"]) == 0
    _put_prose(home, "g", "g/a", "見 <!--@sec-old--><!--@-->。")
    res = run_check(load_project(Layout(home)), load_schema(), Layout(home))
    assert [e for e in res.errors if "sec-old" in e and "retired" in e]


# ── 8. lint V21：未綁錨字面章號 WARN；錨綁定/外部標準不誤報 ───────────────────

def test_lint_v21_flags_unanchored_literal(make_project, write_leaf, monkeypatch):
    """散文未綁錨的 `§9.2` → V21 WARN；同節已綁錨的 §3 不報。"""
    from dspx.lint import run_lint
    home = _three_section_project(make_project, write_leaf, monkeypatch)
    _put_prose(home, "g", "g/a", "已綁錨 <!--@sec-c--><!--@-->；未綁錨 §9.2 的舊寫法。")
    v21 = [f for f in run_lint(Layout(home), load_project(Layout(home)), load_schema())
           if f.rule == "V21"]
    assert len(v21) == 1 and "g/a" in v21[0].where       # 只抓未綁錨的那一處


def test_lint_v21_exempts_external_standard(make_project, write_leaf, monkeypatch):
    """外部標準條號（`ISO 13849-1 §4.2`）不誤報。"""
    from dspx.lint import run_lint
    home = _three_section_project(make_project, write_leaf, monkeypatch)
    _put_prose(home, "g", "g/a", "依 ISO 13849-1 §4.2 的分級與 IEC 61508 §7.4。")
    v21 = [f for f in run_lint(Layout(home), load_project(Layout(home)), load_schema())
           if f.rule == "V21"]
    assert v21 == []


def test_lint_v21_flags_chinese_chapter_phrase(make_project, write_leaf, monkeypatch):
    """`第 6 章` 亦為未綁錨字面章號 → V21 WARN。"""
    from dspx.lint import run_lint
    home = _three_section_project(make_project, write_leaf, monkeypatch)
    _put_prose(home, "g", "g/a", "詳見第 6 章的規定。")
    v21 = [f for f in run_lint(Layout(home), load_project(Layout(home)), load_schema())
           if f.rule == "V21"]
    assert len(v21) == 1


def test_v21_table_cell_internal_ref_not_exempted_but_same_cell_standard_is():
    """ground-truth 回歸（table-pipe）：表格列裡標準名在別格、§ 指本文件內部節（相距兩格以上）
    → 不豁免＝WARN；但外部標準條款落在標準名的相鄰描述格（`| IEC 61508-2 | …(§7.4.2.3) |`）
    → 仍豁免（不誤報外部標準）。"""
    from dspx.lint import _LITERAL_CHAPTER_RE, _is_external_standard_ref
    seg = "| ISO 12100 | 三份架構文件皆缺 | 依 §3 適用文件欄納入 SC |"
    m3 = next(m for m in _LITERAL_CHAPTER_RE.finditer(seg) if m.group(0) == "§3")
    assert not _is_external_standard_ref(seg, m3.start())      # 內部節→WARN
    seg2 = "| IEC 61508-2 | 非安全功能獨立性(§7.4.2.3) | 監督/安全 |"
    m2 = next(iter(_LITERAL_CHAPTER_RE.finditer(seg2)))
    assert _is_external_standard_ref(seg2, m2.start())         # 外部條款→豁免


def test_v21_flags_internal_annex_reference(make_project, write_leaf, monkeypatch):
    """ground-truth 回歸（Annex/附錄）：內部 `Annex B`／`附錄 A` 交叉引用一樣重排即漂 → V21 WARN。"""
    from dspx.lint import run_lint
    home = _three_section_project(make_project, write_leaf, monkeypatch)
    _put_prose(home, "g", "g/a", "詳見 Annex B 的序列圖，另見附錄 A 對照表。")
    v21 = [f for f in run_lint(Layout(home), load_project(Layout(home)), load_schema())
           if f.rule == "V21"]
    assert len(v21) == 1                                       # 一節聚一筆（含 2 命中）


def test_v21_external_standard_annex_not_flagged():
    """外部標準的 annex（`ISO 12100 Annex B`）＝外部條款、不誤報。"""
    from dspx.lint import _LITERAL_CHAPTER_RE, _is_external_standard_ref
    seg = "本設計為 Type A 地基標準，依 ISO 12100 Annex B 的風險評估流程。"
    m = next(m for m in _LITERAL_CHAPTER_RE.finditer(seg) if m.group(0) == "Annex B")
    assert _is_external_standard_ref(seg, m.start())


def test_v21_appendix_heading_not_flagged(make_project, write_leaf, monkeypatch):
    """render 推導的附錄標題 `## 附錄 A 名稱` 是正當標題（HEADING 遮蔽）、非交叉引用 → 不誤報。"""
    from dspx.lint import run_lint
    home = make_project()
    write_leaf(home, "g/a", concept={"id": "sec-a", "title": "甲", "order": 1})
    write_leaf(home, "g/annex", concept={"id": "sec-annex", "title": "法規對照",
                                         "order": 9, "numbering": "appendix"})
    monkeypatch.chdir(home.parent)
    assert render_cmd.run(["g"]) == 0
    _put_prose(home, "g", "g/a", "本節無任何交叉引用。")
    body = _body(home)
    assert "附錄 A" in body                                     # render 確實產了附錄 A 標題
    v21 = [f for f in run_lint(Layout(home), load_project(Layout(home)), load_schema())
           if f.rule == "V21"]
    assert v21 == []                                           # 標題不被當字面章號誤報


# ── 9. publish 剝綁定、留號碼 ────────────────────────────────────────────────

def test_strip_anchor_bindings_keeps_visible_number():
    """凍結快照剝掉隱形綁定、留當下號碼（號碼凍結進不可變快照）。"""
    body = "詳見 <!--@sec-c-->§3<!--@--> 的說明。"
    assert strip_anchor_bindings(body) == "詳見 §3 的說明。"
    assert "<!--@" not in strip_anchor_bindings(body)


def test_publish_snapshot_has_no_binding_comments(make_project, write_leaf, monkeypatch):
    """真 publish：凍結快照含可見號碼、零 `<!--@…-->` 綁定痕跡。"""
    from dspx.commands import publish as publish_cmd
    home = _three_section_project(make_project, write_leaf, monkeypatch)
    # 補齊晉升所需欄位（concept/brief）讓 publish 過閘
    for sec, cid, title, order in [("g/a", "sec-a", "甲", 1), ("g/b", "sec-b", "乙", 2),
                                   ("g/c", "sec-c", "丙", 3)]:
        cy = home / "corpus" / "g" / sec.split("/")[-1] / "concept.yaml"
        data = yaml.safe_load(cy.read_text("utf-8"))
        data.update({"concept": "real", "brief": {"audience": "a", "depth": "d", "breadth": "b"}})
        cy.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), "utf-8")
    _put_prose(home, "g", "g/a", "詳見 <!--@sec-c--><!--@--> 的說明。")
    _put_prose(home, "g", "g/b", "乙散文。")
    _put_prose(home, "g", "g/c", "丙散文。")
    assert publish_cmd.run(["g"]) == 0
    snaps = sorted((home.parent / "docs" / "g" / "archive").glob("v*.md"))
    assert snaps, "expected a frozen snapshot"
    snap = snaps[-1].read_text("utf-8")
    assert "<!--@" not in snap                   # 零綁定痕跡
    assert "§3" in snap                           # 號碼凍結進快照


# ── 10. normalize 純函式（冪等、只縮錨標籤）─────────────────────────────────

def test_normalize_prose_anchors_idempotent():
    s = "見 <!--@sec-x-->§6.5<!--@-->。"
    once = normalize_prose_anchors(s)
    assert once == "見 <!--@sec-x--><!--@-->。"
    assert normalize_prose_anchors(once) == once          # 冪等
