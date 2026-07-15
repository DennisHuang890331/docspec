"""article-store-backend（階段 2）：一篇一檔 store 的地基與遷移測試。

覆蓋：canonical serializer 冪等/literal-block、integrity 封條 fail-loud、per-article 自動偵測、
own 軸 v5 backend-neutral（散檔/store 同內容同值）＋五軸零改、migrate 平價閘＋可逆、
結構化替換旁節 byte 不變（Phase C 的 P0 幾何地基）、store dump/load/fsck。
"""

from __future__ import annotations

import copy

import pytest
import yaml

from dspx.engine import store as st
from dspx.commands.deliverable import render as render_cmd
from dspx.commands.corpus import store as store_cmd
from dspx.engine.layout import Layout
from dspx.engine.model import (ancestor_brief_fingerprint, ancestor_normative_fingerprint,
                        decision_index, deps_fingerprint, leaf_from_dir, load_project)
from dspx.engine.schema import load_schema

SCHEMA = load_schema()


# ── fixtures ───────────────────────────────────────────────────────────

def _wl(home, section, *, concept, decisions=None, material=None, develop=None):
    d = home / "corpus"
    for p in section.split("/"):
        d = d / p
    d.mkdir(parents=True, exist_ok=True)
    full = {"status": "draft", "concept": section, "brief": {}, **concept}
    (d / "concept.yaml").write_text(
        yaml.safe_dump(full, allow_unicode=True, sort_keys=False), encoding="utf-8")
    if decisions is not None:
        (d / "decisions.yaml").write_text(
            yaml.safe_dump({"entries": decisions}, allow_unicode=True, sort_keys=False),
            encoding="utf-8")
    if material is not None:
        (d / "material.md").write_text(material, encoding="utf-8")
    if develop is not None:
        (d / "develop.md").write_text(develop, encoding="utf-8")
    return d


def _sample_corpus(home):
    """一份含 group、多行決策、材料、跨節 realizes 的代表性語料。"""
    _wl(home, "g", concept={"id": "c-root", "title": "總文件", "order": 1})
    _wl(home, "g/intro", concept={"id": "c-in", "title": "簡介", "order": 1},
        material="## fact 甲 {#m1}\n- x = 1\n- y = 2\n")
    _wl(home, "g/rules", concept={"id": "c-ru", "title": "規則", "order": 2},
        decisions=[{"id": "dec-1", "kind": "normative", "status": "accepted",
                    "statement": "系統必須 X", "rationale": "因為\n多行\n理由"}])
    _wl(home, "g/impl", concept={"id": "c-im", "title": "實作", "order": 3,
                                 "realizes": ["dec-1"]},
        material="實作細節。\n")
    (home / "corpus" / "g" / "grp").mkdir()
    (home / "corpus" / "g" / "grp" / "group.yaml").write_text(
        "title: 分組節點\norder: 5\n", encoding="utf-8")
    _wl(home, "g/grp/leaf", concept={"id": "c-gl", "title": "組內葉", "order": 1})


def _make_article_obj():
    """純記憶體 Article（不依賴檔案系統）——序列化測試用。"""
    return st.Article(name="g", revision=3, records=[
        st.SectionRecord(path="g", kind="leaf", concept={
            "id": "c-root", "title": "總文件", "order": 1, "status": "stable",
            "concept": "單一登錄簿", "brief": {"layout": "table", "kind": "reference"}}),
        st.SectionRecord(path="g/grp", kind="group", group={"title": "分組節點", "order": 5}),
        st.SectionRecord(path="g/rules", kind="leaf",
            concept={"id": "c-ru", "title": "規則", "order": 2, "status": "draft",
                     "concept": "規則集", "brief": {}},
            decisions=[{"id": "dec-1", "kind": "normative", "status": "accepted",
                        "statement": "系統必須 X", "rationale": "因為\n多行\n理由"}],
            material="## fact {#m1}\n- x = 1\n"),
    ])


# ── canonical serializer 冪等 ──────────────────────────────────────────

def test_serializer_idempotent_fixpoint():
    art = _make_article_obj()
    text1 = st.dump_article(art, SCHEMA)
    # dump(dump(x)) == dump(x)
    a2 = st.article_from_dict(yaml.safe_load(text1), "x", verify=True)
    text2 = st.dump_article(a2, SCHEMA)
    assert text1 == text2
    # load->dump->load 不動點
    a3 = st.article_from_dict(yaml.safe_load(text2), "x", verify=True)
    assert st.dump_article(a3, SCHEMA) == text1


def test_serializer_multiline_is_literal_block():
    """多行字串 → literal block（`|`），非 PyYAML 預設引號化+`\\n` 轉義（git diff 可讀）。"""
    art = _make_article_obj()
    text = st.dump_article(art, SCHEMA)
    assert "rationale: |" in text            # literal block scalar
    assert "\\n" not in text                 # 沒有轉義換行
    assert "因為" in text and "多行" in text  # 內容直出（unicode）


def test_key_order_follows_fieldmap():
    """concept 鍵序＝schema concept fieldmap 宣告序（id, title, order, …）。"""
    art = st.Article(name="g", revision=1, records=[
        st.SectionRecord(path="g", kind="leaf", concept={
            "concept": "後宣告", "status": "draft", "title": "標題", "order": 1, "id": "c1"})])
    text = st.dump_article(art, SCHEMA)
    body = text[text.index("concept:"):]
    # id 在 title 前、title 在 order 前、order 在 status 前（fieldmap 序）
    assert body.index("id:") < body.index("title:") < body.index("order:") < body.index("status:")


# ── integrity 封條 ─────────────────────────────────────────────────────

def test_integrity_seal_fail_loud_on_hand_edit(tmp_path):
    art = _make_article_obj()
    p = tmp_path / "g.yaml"
    p.write_text(st.dump_article(art, SCHEMA), encoding="utf-8")
    # 手改 body（改 statement）→ 下次 load 驗封條 fail-loud、指路 fsck
    tampered = p.read_text(encoding="utf-8").replace("系統必須 X", "系統必須 Y")
    p.write_text(tampered, encoding="utf-8")
    with pytest.raises(st.StoreError) as exc:
        st.load_article(p, verify=True)
    assert "integrity seal mismatch" in str(exc.value)
    assert "store fsck" in str(exc.value)
    # verify=False 仍讀得回（維修門用）
    assert st.load_article(p, verify=False).record_by_path("g/rules").decisions[0]["statement"] \
        == "系統必須 Y"


# ── per-article 自動偵測 ──────────────────────────────────────────────

def test_autodetect_store_vs_tree_vs_both(make_project):
    home = make_project()
    _wl(home, "t/leaf", concept={"id": "c-t", "title": "散檔", "order": 1})   # tree article "t"
    layout = Layout(home)
    st.save_article(layout, st.Article(name="s", revision=1, records=[
        st.SectionRecord(path="s", kind="leaf", concept={
            "id": "c-s", "title": "store", "order": 1, "status": "draft",
            "concept": "x", "brief": {}})]), SCHEMA)
    assert st.backend_of(layout, "t") == "tree"
    assert st.backend_of(layout, "s") == "store"
    # 同篇兩者並存 → fail-loud
    _wl(home, "s/leaf", concept={"id": "c-s2", "title": "撞", "order": 1})
    with pytest.raises(st.StoreError) as exc:
        st.backend_of(layout, "s")
    assert "BOTH a store file" in str(exc.value)


# ── own 軸 v5 backend-neutral + 五軸零改 ───────────────────────────────

def _six_faces(leaves):
    by_section = {lf.section: lf for lf in leaves}
    concept_by_id = {lf.concept["id"]: lf for lf in leaves
                     if lf.concept and lf.concept.get("id")}
    dindex = decision_index(leaves)
    out = {}
    for lf in leaves:
        out[lf.section] = {
            "own": lf.source_hash(),
            "anc": ancestor_brief_fingerprint(lf.section, by_section, concept_by_id),
            "deps": deps_fingerprint(lf, dindex),
            "norm": ancestor_normative_fingerprint(lf.section, by_section, concept_by_id),
        }
    return out


def test_own_axis_v5_backend_neutral():
    """同內容的散檔 leaf 與 store leaf → own 軸 v5 逐 bit 相等（backend-neutral）。"""
    concept = {"id": "c-ru", "title": "規則", "order": 2, "status": "draft",
               "concept": "規則集", "brief": {}}
    decisions = [{"id": "dec-1", "kind": "normative", "status": "accepted",
                  "statement": "系統必須 X", "rationale": "因為\n多行\n理由"}]
    material = "## fact {#m1}\n- x = 1\n"
    from dspx.engine.model import Leaf
    tree_leaf = Leaf(section="g/rules", dir=None, concept=concept,
                     decisions=decisions, has_material=True, material=material)
    store_art = st.Article(name="g", revision=1, records=[
        st.SectionRecord(path="g/rules", kind="leaf", concept=concept,
                         decisions=decisions, material=material)])
    # store round-trip（過序列化+解析）後再建 leaf——證明「經過 store 儲存」不改 own 值
    rt = st.article_from_dict(yaml.safe_load(st.dump_article(store_art, SCHEMA)), "x")
    store_leaf = st.leaves_from_article(_DummyLayout(), rt)[0]
    assert store_leaf.source_hash() == tree_leaf.source_hash()


class _DummyLayout:
    """leaves_from_article 只用到 section_dir（回不存在路徑）。"""
    from pathlib import Path as _P
    planning_home = _P("/__nonexistent__")

    def section_dir(self, section):
        return self._P("/__nonexistent__").joinpath(*section.split("/"))

    def article_of(self, section):
        return section.split("/", 1)[0]


def test_migrate_five_faces_zero_change(make_project, monkeypatch):
    """遷移前（散檔）與遷移後（store）逐節六面指紋逐 bit 相等（own 含）——backend-neutral 主證。"""
    home = make_project()
    _sample_corpus(home)
    layout = Layout(home)
    # ★store-only：遷移前的 g 是散檔，正常 load_project 已不讀散檔——經遷移橋唯讀路徑取。
    before = _six_faces(st.load_tree_leaves(layout, "g"))
    monkeypatch.chdir(home.parent)
    assert store_cmd.run(["migrate", "g"]) == 0
    after = _six_faces([lf for lf in load_project(layout)
                        if layout.article_of(lf.section) == "g"])
    assert set(before) == set(after)
    for sec in before:
        assert before[sec] == after[sec], f"{sec}: face changed across migrate {before[sec]} -> {after[sec]}"


# ── migrate 平價閘 + 可逆 ──────────────────────────────────────────────

def test_migrate_creates_store_deletes_scatter_and_is_reversible(make_project, monkeypatch, tmp_path):
    home = make_project()
    _sample_corpus(home)
    monkeypatch.chdir(home.parent)
    assert store_cmd.run(["migrate", "g"]) == 0
    assert st.store_path(Layout(home), "g").is_file()
    assert not (home / "corpus" / "g").exists()      # 散檔樹已刪
    # store 篇仍完整載入（4 leaves）
    leaves = load_project(Layout(home))
    assert {lf.section for lf in leaves} == {"g", "g/intro", "g/rules", "g/impl", "g/grp/leaf"}
    # 可逆：dump → 散檔還原
    out = tmp_path / "exp"
    assert store_cmd.run(["dump", "g", str(out)]) == 0
    assert (out / "g" / "intro" / "material.md").read_text(encoding="utf-8") == "## fact 甲 {#m1}\n- x = 1\n- y = 2\n"
    assert (out / "g" / "grp" / "group.yaml").is_file()
    assert (out / "g" / "rules" / "decisions.yaml").is_file()


def test_migrate_refuses_legacy_develop(make_project, monkeypatch, capsys):
    """★retire-develop-workbench：散檔樹殘留 develop.md → migrate fail-loud 拒遷（不搬不刪——
    工作台已廢除、store 不承載；留人裁決：put 蒸餾或自行刪除）。原檔逐 byte 存活、store 檔沒寫半套。"""
    home = make_project()
    _wl(home, "g/intro", concept={"id": "c-in", "title": "簡介", "order": 1},
        develop="草稿中的想法\n")
    monkeypatch.chdir(home.parent)
    assert store_cmd.run(["migrate", "g"]) == 1
    err = capsys.readouterr().err
    assert "develop.md" in err and "workbench" in err
    dev = home / "corpus" / "g" / "intro" / "develop.md"
    assert dev.read_text(encoding="utf-8") == "草稿中的想法\n"   # 一個 byte 不動
    assert not (home / "corpus" / "g.yaml").exists()             # store 檔沒寫半套


def test_migrate_refuses_unexpected_file(make_project, monkeypatch, capsys):
    home = make_project()
    _wl(home, "g/intro", concept={"id": "c-in", "title": "簡介", "order": 1})
    (home / "corpus" / "g" / "intro" / "stray.txt").write_text("x", encoding="utf-8")
    monkeypatch.chdir(home.parent)
    assert store_cmd.run(["migrate", "g"]) == 1
    err = capsys.readouterr().err
    assert "stray.txt" in err and "lose them" in err
    assert st.backend_of(Layout(home), "g") == "tree"   # 未寫 store（散檔完好）


def test_store_backed_article_renders_with_groups(make_project, monkeypatch):
    home = make_project()
    _sample_corpus(home)
    monkeypatch.chdir(home.parent)
    assert store_cmd.run(["migrate", "g"]) == 0
    assert render_cmd.run(["g"]) == 0
    text = Layout(home).docs_latest("g").read_text(encoding="utf-8")
    # store-aware group：本地化標題（非 humanize slug "Grp"）＋群下子節在群標題後。
    assert "分組節點" in text and "組內葉" in text
    assert text.index("分組節點") < text.index("組內葉")
    import re
    assert re.search(r"##\s+\d+\.\s+分組節點", text)       # group 有大綱號（title 由 store 供）
    assert "Grp" not in text                               # 未降級成英文 slug


# ── fsck ───────────────────────────────────────────────────────────────

def test_fsck_accept_reseals(make_project, monkeypatch, capsys):
    home = make_project()
    _wl(home, "g/intro", concept={"id": "c-in", "title": "簡介", "order": 1})
    monkeypatch.chdir(home.parent)
    assert store_cmd.run(["migrate", "g"]) == 0
    p = st.store_path(Layout(home), "g")
    p.write_text(p.read_text(encoding="utf-8").replace("簡介", "序言"), encoding="utf-8")
    assert store_cmd.run(["fsck"]) == 1                   # 封條不符
    assert store_cmd.run(["fsck", "--accept"]) == 0       # 顯式吸收重封
    assert store_cmd.run(["fsck"]) == 0                   # 再驗 OK


# ── store load 往返 ────────────────────────────────────────────────────

def test_store_load_roundtrip(make_project, monkeypatch, tmp_path):
    home = make_project()
    # 準備散檔 DIR（非 corpus 內）
    src = tmp_path / "scattered" / "g"
    (src / "intro").mkdir(parents=True)
    (src / "concept.yaml").write_text(
        yaml.safe_dump({"id": "c-root", "title": "根", "order": 1, "status": "draft",
                        "concept": "x", "brief": {}}, allow_unicode=True, sort_keys=False),
        encoding="utf-8")
    (src / "intro" / "concept.yaml").write_text(
        yaml.safe_dump({"id": "c-in", "title": "簡介", "order": 1, "status": "draft",
                        "concept": "y", "brief": {}}, allow_unicode=True, sort_keys=False),
        encoding="utf-8")
    monkeypatch.chdir(home.parent)
    assert store_cmd.run(["load", "g", str(src)]) == 0     # src＝該篇散檔根（含根 concept.yaml）
    assert st.article_has_store(Layout(home), "g")
    art = st.load_article(st.store_path(Layout(home), "g"))
    assert {r.path for r in art.leaf_records()} == {"g", "g/intro"}


# ── Phase C 的 P0 幾何地基：結構化替換旁節 byte 不變 ────────────────────

def test_structured_swap_leaves_bystanders_byte_identical():
    """換掉一節記錄、canonical 重 dump → 其餘節的序列化區塊逐 byte 不變。

    這是 change 層 landing「非 target 節 byte 不變」P0 的幾何地基（serializer 冪等 ⇒ 旁節不動）：
    非 target 記錄全程同一物件、序列化決定性 ⇒ 其 block byte 穩定。"""
    art = _make_article_obj()
    text_before = st.dump_article(art, SCHEMA)

    # 深拷貝、只改 g/rules 的 decisions（target 節），其餘節物件不動
    art2 = st.Article(name=art.name, revision=art.revision + 1,
                      records=[copy.deepcopy(r) for r in art.records])
    tgt = art2.record_by_path("g/rules")
    tgt.decisions[0]["statement"] = "系統必須 Z（改過）"
    text_after = st.dump_article(art2, SCHEMA)

    # 旁節（g、g/grp）的序列化區塊在前後 dump 中逐 byte 相等。
    for bystander in ("g", "g/grp"):
        blk_before = _section_block(text_before, bystander)
        blk_after = _section_block(text_after, bystander)
        assert blk_before == blk_after, f"bystander {bystander} block changed"
    # target 區塊確實變了（反向：證明測試有效、非空斷言）
    assert _section_block(text_before, "g/rules") != _section_block(text_after, "g/rules")


# ── hook guard：擋手改 store 檔（task 3.4）────────────────────────────

def _run_guard(monkeypatch, payload):
    import io
    import json
    from dspx.commands._internal import hook as hook_cmd
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)
    return hook_cmd.run(["guard"])


def test_hook_guard_blocks_store_edit(monkeypatch, capsys):
    rc = _run_guard(monkeypatch, {"tool_input": {"file_path": "docspec/corpus/g.yaml"}})
    assert rc == 2
    assert "engine-owned single-file store" in capsys.readouterr().err


@pytest.mark.parametrize("command", [
    "echo x > docspec/corpus/g.yaml",
    "sed -i 's/a/b/' docspec/corpus/g.yaml",
    "rm docspec/corpus/g.yaml",
])
def test_hook_guard_blocks_store_command(monkeypatch, command):
    assert _run_guard(monkeypatch, {"tool_input": {"command": command}}) == 2


def test_hook_guard_allows_scattered_and_store_dir(monkeypatch):
    # 散檔 concept.yaml（更深的節夾內、父非 corpus）＝放行；_archive 前綴＝放行。
    assert _run_guard(monkeypatch, {"tool_input": {"file_path": "docspec/corpus/g/intro/concept.yaml"}}) == 0
    assert _run_guard(monkeypatch, {"tool_input": {"file_path": "docspec/corpus/_archive.yaml"}}) == 0


def _section_block(text: str, path: str) -> str:
    """從 canonical store 文字抽出某 `- path: <path>` 記錄到下個 `- path:`（或檔尾）的 byte 區塊。"""
    lines = text.split("\n")
    start = None
    for i, ln in enumerate(lines):
        if ln.strip() == f"- path: {path}":
            start = i
            break
    assert start is not None, f"path {path} not found"
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("- path:"):
            end = j
            break
    return "\n".join(lines[start:end])


# ── Phase-C 尾巴：生命週期指令 backend-neutral（store 篇也能走）───────────────────

def test_store_put_first_write_lifecycle(make_project, monkeypatch, tmp_path):
    """★retire-develop-workbench：建節唯一入口＝put 首寫（無鷹架步）。首寫 concept 蓋 id/order、
    記錄直接進 store、不建任何 corpus 散檔／工作台目錄。"""
    from dspx.commands.corpus import put as put_cmd
    home = make_project()
    _wl(home, "g", concept={"id": "c-root", "title": "根", "order": 1,
                            "brief": {"audience": "a", "depth": "d", "breadth": "b"}})
    monkeypatch.chdir(home.parent)
    assert store_cmd.run(["migrate", "g"]) == 0
    layout = Layout(home)

    # put 首寫 concept（無鷹架前置）→ 節即存在、id/order 引擎蓋章
    cpt = tmp_path / "c.yaml"
    cpt.write_text("title: 新節\nstatus: draft\nconcept: 一句話說明\n", encoding="utf-8")
    assert put_cmd.run(["g/newsec", "concept", str(cpt)]) == 0
    art = st.load_article(st.store_path(layout, "g"))
    rec = art.record_by_path("g/newsec")
    assert rec is not None and rec.concept and rec.concept.get("id")
    assert rec.concept.get("order") is not None
    assert not (home / "corpus" / "g" / "newsec").exists()   # 零散檔
    assert not (home / "work").exists()                       # 零工作台目錄
    assert st.backend_of(layout, "g") == "store"


def test_store_mv_repoints_records_sidesections_survive(make_project, monkeypatch, capsys):
    """mv 對 store 篇＝真的改記錄 path 前綴（不搬資料夾）；旁節記錄逐欄不變、check 綠、revision+1。"""
    from dspx.commands.corpus import mv as mv_cmd
    from dspx.commands.query import check as check_cmd
    home = make_project()
    _wl(home, "g", concept={"id": "c-root", "title": "根", "order": 1,
                            "brief": {"audience": "a", "depth": "d", "breadth": "b"}})
    _wl(home, "g/intro", concept={"id": "c-in", "title": "簡介", "order": 2},
        material="原材料\n")
    _wl(home, "g/other", concept={"id": "c-ot", "title": "旁節", "order": 3},
        decisions=[{"id": "d-o", "kind": "normative", "status": "accepted", "statement": "旁規"}])
    monkeypatch.chdir(home.parent)
    assert store_cmd.run(["migrate", "g"]) == 0
    rev_before = st.load_article(st.store_path(Layout(home), "g")).revision
    other_before = copy.deepcopy(st.load_article(st.store_path(Layout(home), "g")).record_by_path("g/other"))

    capsys.readouterr()
    assert mv_cmd.run(["g/intro", "g/preface"]) == 0
    art = st.load_article(st.store_path(Layout(home), "g"))
    assert art.record_by_path("g/intro") is None                 # 舊 path 記錄消失
    moved = art.record_by_path("g/preface")
    assert moved is not None and moved.concept["id"] == "c-in"    # 身份不變、path 改了
    assert moved.material == "原材料\n"                            # 內容隨記錄走
    assert art.revision == rev_before + 1                        # revision+1
    # 旁節記錄逐欄不變（結構化搬移不碰非 target 記錄）
    other_after = art.record_by_path("g/other")
    assert other_after.concept == other_before.concept
    assert other_after.decisions == other_before.decisions
    # check 綠（mv 自驗）
    assert check_cmd.run([]) == 0


def test_store_retire_extracts_record_and_archives(make_project, monkeypatch, capsys):
    """retire 對 store 篇＝抽記錄→ dump 封存包、活 store 移除記錄、revision+1；retired 查得到、旁節存活。"""
    from dspx.commands.corpus import retire as retire_cmd
    from dspx.commands.query import status as status_cmd
    home = make_project()
    _wl(home, "g", concept={"id": "c-root", "title": "根", "order": 1,
                            "brief": {"audience": "a", "depth": "d", "breadth": "b"}})
    _wl(home, "g/intro", concept={"id": "c-in", "title": "簡介", "order": 2,
                                  "concept": "新手第一課"},
        material="材料內容\n")
    _wl(home, "g/other", concept={"id": "c-ot", "title": "旁節", "order": 3})
    monkeypatch.chdir(home.parent)
    assert store_cmd.run(["migrate", "g"]) == 0
    rev_before = st.load_article(st.store_path(Layout(home), "g")).revision

    capsys.readouterr()
    assert retire_cmd.run(["g/intro", "--in", "v2"]) == 0
    art = st.load_article(st.store_path(Layout(home), "g"))
    assert art.record_by_path("g/intro") is None                 # 活 store 已無此記錄
    assert art.record_by_path("g/other") is not None             # 旁節存活
    assert art.record_by_path("g") is not None                   # 根存活
    assert art.revision == rev_before + 1
    # 封存包＝可回復的散檔形態＋history.yaml（kind:section entry）
    dest = home / "corpus" / "_archive" / "g__intro"
    assert (dest / "concept.yaml").is_file()
    assert (dest / "material.md").read_text(encoding="utf-8") == "材料內容\n"
    hist = yaml.safe_load((dest / "history.yaml").read_text(encoding="utf-8"))
    sec = next(e for e in hist["entries"] if e.get("kind") == "section")
    assert sec["id"] == "c-in" and sec["statement"] == "新手第一課" and sec["retired-in"] == "v2"
    # 引擎隱形：load_project 不再看到退場節
    assert "g/intro" not in {lf.section for lf in load_project(Layout(home))}
    # retired 查得到
    capsys.readouterr()
    assert status_cmd.run(["--retired"]) == 0
    assert "g/intro" in capsys.readouterr().out


def test_store_retire_whole_article_removes_store_and_migrates_deliverable(
        make_project, monkeypatch, capsys):
    """整篇 store 退役（退掉唯一/根節、活 store 無 leaf 殘留）→ 刪 store 檔＋交付物/帳本搬進封存包。"""
    from dspx.commands.corpus import retire as retire_cmd
    home = make_project()
    _wl(home, "solo", concept={"id": "c-solo", "title": "獨", "order": 1,
                               "brief": {"audience": "a", "depth": "d", "breadth": "b"}})
    monkeypatch.chdir(home.parent)
    assert store_cmd.run(["migrate", "solo"]) == 0
    render_cmd.run(["solo"])
    latest = Layout(home).docs_latest("solo")
    assert st.store_path(Layout(home), "solo").is_file() and latest.is_file()

    capsys.readouterr()
    assert retire_cmd.run(["solo"]) == 0
    assert not st.store_path(Layout(home), "solo").is_file()      # 整篇退役＝刪 store 檔
    dest = home / "corpus" / "_archive" / "solo"
    assert (dest / "concept.yaml").is_file()                      # 記錄 dump 成散檔（可回復）
    assert not latest.exists() and (dest / "_latest.md").is_file()  # 交付物搬進封存包
    assert (dest / "solo.sections.yaml").is_file()               # 帳本一併搬走、docs/.ledger 無孤兒


def test_store_get_put_roundtrip(make_project, monkeypatch, tmp_path, capsys):
    """get/put 對 store 篇：get 從記錄吐內容（非空骨架）、put 寫回正式 store 記錄。"""
    from dspx.commands.corpus import get as get_cmd
    from dspx.commands.corpus import put as put_cmd
    home = make_project()
    _wl(home, "g/intro", concept={"id": "c-in", "title": "簡介", "order": 1},
        material="原材料內容\n")
    monkeypatch.chdir(home.parent)
    assert store_cmd.run(["migrate", "g"]) == 0

    capsys.readouterr()
    assert get_cmd.run(["g/intro", "material"]) == 0
    assert "原材料內容" in capsys.readouterr().out          # 從 store 記錄吐、非空骨架
    capsys.readouterr()
    assert get_cmd.run(["g/intro", "concept"]) == 0
    assert "簡介" in capsys.readouterr().out

    m = tmp_path / "m.md"
    m.write_text("改後材料\n", encoding="utf-8")
    assert put_cmd.run(["g/intro", "material", str(m)]) == 0
    capsys.readouterr()
    assert get_cmd.run(["g/intro", "material"]) == 0
    assert "改後材料" in capsys.readouterr().out
