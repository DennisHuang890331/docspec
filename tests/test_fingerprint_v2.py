"""fingerprint v2：四項指紋算法缺陷合體修（change `fingerprint-v2`）。

1. CRLF 正規化——own/style/content_hash 讀端 `\\r\\n`→`\\n`、引擎寫檔釘 LF（跨 OS／autocrlf 免疫）。
2. supersede 第二跳入帳——deps item 擴 (succ_id, succ_stmt)（B→C 換終端接替時下游有信號）。
3. style 拆三子軸 guide/gloss/purpose——definition-only 零擾動、purpose 入帳、載體指名。
4. anc-norm 新軸——祖先 active normative 決策入帳（stale-norm；優先序 own > upstream > norm >
   inherited > style；--ack 一併重蓋）。
帳本 v2：頂層 `fingerprint: 2` 版本鍵；v1 → status needs-migration、render 拒跑、
`--rebaseline` 一次遷移（散文保留、待處理信號吸收）。
"""

from __future__ import annotations

import json

import yaml

from dspx.commands.deliverable import render as render_cmd
from dspx.commands.query import status as status_cmd
from dspx.engine.layout import Layout
from dspx.engine.model import (
    ancestor_normative_fingerprint,
    content_hash,
    decision_index,
    deps_fingerprint,
    load_project,
    style_fingerprint,
)
from dspx.engine.render import read_ledger, read_ledger_version


def _latest(home, article="g"):
    return home.parent / "docs" / article / "_latest.md"


def _row_of(home, article, section):
    """重算某節 status row（同 status._leaf_row；含 styleMoved 診斷欄）。"""
    from dspx.commands.query.status import _docs_hashes, _leaf_row
    from dspx.engine.schema import load_schema
    layout = Layout(home)
    leaves = load_project(layout)
    by = {lf.section: lf for lf in leaves}
    return _leaf_row(layout, by[section], load_schema(), True,
                     _docs_hashes(layout, article), by, decision_index(leaves))


def _sync_of(home, article, section):
    return _row_of(home, article, section)["sync"]


def _write_prose(home, article, heading, prose):
    """在 `## <heading>` 後塞散文並重 render（建立帳本基準）。"""
    latest = _latest(home, article)
    latest.write_text(
        latest.read_text("utf-8").replace(f" {heading}\n", f" {heading}\n\n{prose}\n", 1),
        "utf-8")
    assert render_cmd.run([article]) == 0


def _to_crlf(path):
    data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    path.write_bytes(data)


def _to_lf(path):
    path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))


# ── 1. CRLF 正規化 ─────────────────────────────────────────────────────────────


def test_source_hash_crlf_lf_equal(make_project, write_leaf):
    """1.1：同內容 CRLF/LF 位元組 → own 指紋相等；孤 `\\r`（非 CRLF）不正規化。"""
    home = make_project()
    leaf_dir = write_leaf(home, "g/intro", concept={"id": "c1", "title": "概覽", "order": 1},
                          material="來源甲。\n第二行。\n")
    leaves = load_project(Layout(home))
    lf_hash = leaves[0].source_hash()

    for f in ("concept.yaml", "material.md"):
        _to_crlf(leaf_dir / f)
    crlf_hash = load_project(Layout(home))[0].source_hash()
    assert crlf_hash == lf_hash                       # CRLF/LF 指紋相同

    # 孤 \r（老 Mac 格式）＝內容差異，不正規化
    mat = leaf_dir / "material.md"
    mat.write_bytes(mat.read_bytes().replace(b"\r\n", b"\r"))
    assert load_project(Layout(home))[0].source_hash() != lf_hash


def test_content_hash_crlf_lf_equal(tmp_path):
    a, b = tmp_path / "a.md", tmp_path / "b.md"
    a.write_bytes(b"line one\nline two\n")
    b.write_bytes(b"line one\r\nline two\r\n")
    assert content_hash(a) == content_hash(b)
    assert content_hash(tmp_path / "missing.md") is None


def test_style_guide_crlf_immune(make_project):
    """writing-guide 僅換行差異 → guide 子軸不變。"""
    home = make_project()
    guide = home / "writing-guide.md"
    guide.write_bytes("# Guide\n規則一。\n".encode("utf-8"))
    fp_lf = style_fingerprint(Layout(home))
    _to_crlf(guide)
    assert style_fingerprint(Layout(home)) == fp_lf


def test_engine_writes_lf_only(make_project, write_leaf, monkeypatch):
    """1.2：引擎產物（_latest.md／ledger sidecar）不含 CRLF（Windows 上 write_text 預設會翻譯）。"""
    home = make_project()
    write_leaf(home, "g/intro", concept={"id": "c1", "title": "概覽", "order": 1})
    monkeypatch.chdir(home.parent)
    assert render_cmd.run(["g"]) == 0
    assert b"\r\n" not in _latest(home).read_bytes()
    assert b"\r\n" not in Layout(home).docs_ledger("g").read_bytes()


def test_crlf_worktree_to_lf_worktree_no_false_stale(make_project, write_leaf, monkeypatch):
    """1.4 整合：CRLF worktree render 入帳 → 全檔換行改 LF（模擬 LF 檢出）→ 全 synced、零漂移。"""
    from dspx.engine.render import detect_drift
    home = make_project()
    (home / "writing-guide.md").write_text("# Guide\n規則一。\n", encoding="utf-8")
    leaf_dir = write_leaf(home, "g/intro", concept={"id": "c1", "title": "概覽", "order": 1},
                          material="來源甲。\n")
    # 模擬 autocrlf=true 檢出：corpus＋doctrine 全 CRLF
    for f in (leaf_dir / "concept.yaml", leaf_dir / "material.md", home / "writing-guide.md"):
        _to_crlf(f)
    monkeypatch.chdir(home.parent)
    assert render_cmd.run(["g"]) == 0
    _write_prose(home, "g", "概覽", "限流保護後端。")
    assert _sync_of(home, "g", "g/intro") == "synced"
    # 換行全轉 LF（fresh clone／macOS worktree）；帳本入版控跨 worktree 不動
    for f in (leaf_dir / "concept.yaml", leaf_dir / "material.md",
              home / "writing-guide.md", _latest(home)):
        _to_lf(f)
    assert _sync_of(home, "g", "g/intro") == "synced"           # 無假 stale
    assert detect_drift(Layout(home), "g") == []                 # 零漂移


# ── 2. supersede 第二跳 ────────────────────────────────────────────────────────


def _supersede_chain_project(make_project, write_leaf, monkeypatch):
    """上游 u 節帶決策 A；消費節 c realizes A；散文入帳（synced）。"""
    home = make_project()
    write_leaf(home, "u/root", concept={"id": "cu", "title": "上游", "order": 1},
               decisions=[{"id": "A", "statement": "採方案A", "status": "accepted"}])
    write_leaf(home, "c/use", concept={"id": "cc", "title": "消費", "order": 1,
                                       "realizes": ["A"]},
               decisions=[])
    monkeypatch.chdir(home.parent)
    assert render_cmd.run(["c"]) == 0
    _write_prose(home, "c", "消費", "依方案A實作。")
    assert _sync_of(home, "c", "c/use") == "synced"
    return home


def _set_upstream_decisions(home, entries):
    (home / "corpus" / "u" / "root" / "decisions.yaml").write_text(
        yaml.safe_dump({"entries": entries}, allow_unicode=True, sort_keys=False),
        encoding="utf-8")


def test_second_hop_supersession_restales_consumer(make_project, write_leaf, monkeypatch):
    """2.2：A→B 入帳後 B→C 第二跳 → stale-upstream；改終端接替 C 的 statement 也 stale；重寫散文回 synced。"""
    home = _supersede_chain_project(make_project, write_leaf, monkeypatch)
    # 第一跳 A→B
    _set_upstream_decisions(home, [
        {"id": "A", "statement": "採方案A", "status": "superseded", "superseded-by": "B"},
        {"id": "B", "statement": "採方案B", "status": "accepted", "supersedes": "A"},
    ])
    assert _sync_of(home, "c", "c/use") == "stale-upstream"
    _write_prose(home, "c", "消費", "依方案B實作。")             # 重渲、帳本記入 B 為終端接替
    assert _sync_of(home, "c", "c/use") == "synced"
    # 第二跳 B→C：A 的 (id, statement, status) 三元組一個 byte 都不動——v1 零信號、v2 必須有
    _set_upstream_decisions(home, [
        {"id": "A", "statement": "採方案A", "status": "superseded", "superseded-by": "B"},
        {"id": "B", "statement": "採方案B", "status": "superseded", "superseded-by": "C",
         "supersedes": "A"},
        {"id": "C", "statement": "採方案C", "status": "accepted", "supersedes": "B"},
    ])
    assert _sync_of(home, "c", "c/use") == "stale-upstream"
    _write_prose(home, "c", "消費", "依方案C實作。")
    assert _sync_of(home, "c", "c/use") == "synced"
    # 只改終端接替 C 的 statement 文字（draft 渲染的正是 successor_statement）→ 同樣 stale
    _set_upstream_decisions(home, [
        {"id": "A", "statement": "採方案A", "status": "superseded", "superseded-by": "B"},
        {"id": "B", "statement": "採方案B", "status": "superseded", "superseded-by": "C",
         "supersedes": "A"},
        {"id": "C", "statement": "採方案C（修訂）", "status": "accepted", "supersedes": "B"},
    ])
    assert _sync_of(home, "c", "c/use") == "stale-upstream"


def test_deps_item_live_decision_has_empty_successor(make_project, write_leaf):
    """2.1：活決策（無接替）succ 欄空值；指紋與 realized_statements 同源（第二跳指紋必變）。"""
    from dspx.engine.model import realized_statements
    home = make_project()
    write_leaf(home, "u/root", concept={"id": "cu", "title": "上游", "order": 1},
               decisions=[{"id": "A", "statement": "採方案A", "status": "accepted"}])
    write_leaf(home, "c/use", concept={"id": "cc", "title": "消費", "order": 1,
                                       "realizes": ["A"]}, decisions=[])
    leaves = load_project(Layout(home))
    consumer = next(lf for lf in leaves if lf.section == "c/use")
    dindex = decision_index(leaves)
    (item,) = realized_statements(consumer, dindex)
    assert item["superseded_by"] is None and item["successor_statement"] is None
    fp_live = deps_fingerprint(consumer, dindex)
    assert fp_live != ""
    # A→B、再 B→C：終端接替變 → 指紋逐跳都變
    _set_upstream_decisions(home, [
        {"id": "A", "statement": "採方案A", "status": "superseded", "superseded-by": "B"},
        {"id": "B", "statement": "採方案B", "status": "accepted", "supersedes": "A"},
    ])
    leaves2 = load_project(Layout(home))
    consumer2 = next(lf for lf in leaves2 if lf.section == "c/use")
    fp_hop1 = deps_fingerprint(consumer2, decision_index(leaves2))
    assert fp_hop1 != fp_live
    _set_upstream_decisions(home, [
        {"id": "A", "statement": "採方案A", "status": "superseded", "superseded-by": "B"},
        {"id": "B", "statement": "採方案B", "status": "superseded", "superseded-by": "C",
         "supersedes": "A"},
        {"id": "C", "statement": "採方案C", "status": "accepted", "supersedes": "B"},
    ])
    leaves3 = load_project(Layout(home))
    consumer3 = next(lf for lf in leaves3 if lf.section == "c/use")
    assert deps_fingerprint(consumer3, decision_index(leaves3)) != fp_hop1


# ── 3. style 三子軸 ────────────────────────────────────────────────────────────

_TERM = {"id": "t1", "canonical": "節流模組", "bucket": "module", "code": "RMM",
         "english": "throttle module", "definition": "限制單位時間請求數的模組。",
         "aliases_forbidden": ["限流器"]}


def _glossary_write(home, terms):
    (home / "glossary.yaml").write_text(
        yaml.safe_dump({"terms": terms}, allow_unicode=True, sort_keys=False),
        encoding="utf-8")


def _style_baseline(make_project, write_leaf, monkeypatch):
    home = make_project()
    (home / "writing-guide.md").write_text("# Guide\n規則一。\n", encoding="utf-8")
    _glossary_write(home, [dict(_TERM)])
    write_leaf(home, "g/intro", concept={"id": "c1", "title": "概覽", "order": 1})
    monkeypatch.chdir(home.parent)
    assert render_cmd.run(["g"]) == 0
    _write_prose(home, "g", "概覽", "節流模組保護後端。")
    assert _sync_of(home, "g", "g/intro") == "synced"
    return home


def test_style_fingerprint_is_three_subaxes(make_project):
    home = make_project()
    fp = style_fingerprint(Layout(home))
    assert set(fp) == {"guide", "gloss", "purpose"}


def test_glossary_definition_only_edit_does_not_restale(make_project, write_leaf, monkeypatch):
    """3.3：definition-only／english-only／純排序修改 → 零擾動（仍 synced）。"""
    home = _style_baseline(make_project, write_leaf, monkeypatch)
    t = dict(_TERM); t["definition"] = "改寫過的定義句。"
    _glossary_write(home, [t])
    assert _sync_of(home, "g", "g/intro") == "synced"
    t = dict(_TERM); t["english"] = "rate-limit module"
    _glossary_write(home, [t])
    assert _sync_of(home, "g", "g/intro") == "synced"
    # 純排序（多 term 重排）：加入第二 term 定基準後重排
    t2 = {"id": "t2", "canonical": "閘道", "bucket": "module"}
    _glossary_write(home, [dict(_TERM), t2])
    assert _sync_of(home, "g", "g/intro") == "stale-style"       # 新 term＝索引變，先清基準
    assert render_cmd.run(["g", "--ack", "g/intro"]) == 0
    assert _sync_of(home, "g", "g/intro") == "synced"
    _glossary_write(home, [t2, dict(_TERM)])                     # 只換順序
    assert _sync_of(home, "g", "g/intro") == "synced"


def test_glossary_canonical_or_alias_change_is_stale_style(make_project, write_leaf, monkeypatch):
    home = _style_baseline(make_project, write_leaf, monkeypatch)
    t = dict(_TERM); t["canonical"] = "流量節制模組"
    _glossary_write(home, [t])
    row = _row_of(home, "g", "g/intro")
    assert row["sync"] == "stale-style"
    assert row["styleMoved"] == ["glossary"]                     # 載體指名
    # aliases_forbidden 修改亦然
    _glossary_write(home, [dict(_TERM)])                         # 還原
    assert _sync_of(home, "g", "g/intro") == "synced"
    t = dict(_TERM); t["aliases_forbidden"] = ["限流器", "節流器"]
    _glossary_write(home, [t])
    assert _sync_of(home, "g", "g/intro") == "stale-style"


def test_config_purpose_change_is_stale_style(make_project, write_leaf, monkeypatch):
    """3.3：config.purpose 改寫 → stale-style（載體指名 purpose）。"""
    home = _style_baseline(make_project, write_leaf, monkeypatch)
    (home / "config.yaml").write_text(
        "language: zh-TW\ndocs_layout: per-article\npurpose: 建立完整的限流設計規範。\n",
        encoding="utf-8")
    row = _row_of(home, "g", "g/intro")
    assert row["sync"] == "stale-style"
    assert row["styleMoved"] == ["purpose"]
    # ack 清除（散文合法不需變）
    assert render_cmd.run(["g", "--ack", "g/intro"]) == 0
    assert _sync_of(home, "g", "g/intro") == "synced"


def test_unparsable_glossary_falls_back_to_bytes(make_project):
    """3.1：glossary 壞檔 → gloss 子軸 fallback 全檔 bytes（不 raise、信號保住）。"""
    home = make_project()
    _glossary_write(home, [dict(_TERM)])
    fp_ok = style_fingerprint(Layout(home))
    (home / "glossary.yaml").write_text("terms: [unclosed\n", encoding="utf-8")
    fp_broken = style_fingerprint(Layout(home))                  # 不 raise
    assert fp_broken["gloss"] != fp_ok["gloss"]


# ── 4. anc-norm 軸（stale-norm）──────────────────────────────────────────────


def _norm_project(make_project, write_leaf, monkeypatch):
    """根節 g 帶 active normative；子節 g/sub 散文入帳（synced）。"""
    home = make_project()
    write_leaf(home, "g", concept={"id": "root", "title": "總則", "order": 0},
               decisions=[{"id": "N1", "statement": "全文禁用被動語態", "status": "accepted",
                           "kind": "normative"}])
    write_leaf(home, "g/sub", concept={"id": "sub", "title": "細則", "order": 1})
    monkeypatch.chdir(home.parent)
    assert render_cmd.run(["g"]) == 0
    _write_prose(home, "g", "細則", "本節以主動語態撰寫。")
    assert _sync_of(home, "g", "g/sub") == "synced"
    return home


def _set_root_decisions(home, entries):
    (home / "corpus" / "g" / "decisions.yaml").write_text(
        yaml.safe_dump({"entries": entries}, allow_unicode=True, sort_keys=False),
        encoding="utf-8")


def test_ancestor_normative_rewrite_restales_descendants(make_project, write_leaf, monkeypatch):
    """4.4：祖先改寫 normative → 子孫 stale-norm；信號在 no-op render 後存活。"""
    home = _norm_project(make_project, write_leaf, monkeypatch)
    _set_root_decisions(home, [{"id": "N1", "statement": "全文禁用被動語態與展望語",
                                "status": "accepted", "kind": "normative"}])
    assert _sync_of(home, "g", "g/sub") == "stale-norm"
    assert render_cmd.run(["g"]) == 0                            # no-op 骨架重 render
    assert _sync_of(home, "g", "g/sub") == "stale-norm"          # 信號存活（prose 未變沿用舊值）


def test_ancestor_normative_retirement_restales(make_project, write_leaf, monkeypatch):
    """4.4：normative 自 active 集合消失（supersede/deprecate）→ stale-norm。"""
    home = _norm_project(make_project, write_leaf, monkeypatch)
    _set_root_decisions(home, [{"id": "N1", "statement": "全文禁用被動語態",
                                "status": "deprecated", "kind": "normative"}])
    assert _sync_of(home, "g", "g/sub") == "stale-norm"


def test_ack_clears_stale_norm_and_is_refused_on_stale_own(
        make_project, write_leaf, monkeypatch, capsys):
    """4.4：ack 清除合法不需變的 stale-norm；own 同時變 → 報 stale-own、ack 拒。"""
    home = _norm_project(make_project, write_leaf, monkeypatch)
    _set_root_decisions(home, [{"id": "N1", "statement": "全文禁用被動語態與展望語",
                                "status": "accepted", "kind": "normative"}])
    assert _sync_of(home, "g", "g/sub") == "stale-norm"
    assert render_cmd.run(["g", "--ack", "g/sub"]) == 0
    assert _sync_of(home, "g", "g/sub") == "synced"              # 散文未被捏造、norm 重蓋
    # own 同時變 → stale-own 優先、ack 拒
    _set_root_decisions(home, [{"id": "N1", "statement": "改第二次",
                                "status": "accepted", "kind": "normative"}])
    cpt = home / "corpus" / "g" / "sub" / "concept.yaml"
    cpt.write_text(cpt.read_text("utf-8").replace("title: 細則", "title: 細則（改）"), "utf-8")
    assert _sync_of(home, "g", "g/sub") == "stale-own"
    capsys.readouterr()
    render_cmd.run(["g", "--ack", "g/sub"])
    assert "refused" in capsys.readouterr().err
    assert _sync_of(home, "g", "g/sub") == "stale-own"           # 沒被吞


def test_norm_fingerprint_covers_governed_by_ancestors(make_project, write_leaf):
    """4.1：governed-by 跨樹祖先的 normative 入帳；無祖先 normative＝穩定空值。"""
    home = make_project()
    write_leaf(home, "p", concept={"id": "gov-root", "title": "治理父", "order": 0},
               decisions=[{"id": "NP", "statement": "跨樹規矩", "status": "accepted",
                           "kind": "normative"}])
    write_leaf(home, "t/leaf", concept={"id": "t-leaf", "title": "被治理", "order": 1,
                                        "governed-by": ["gov-root"]}, decisions=[])
    write_leaf(home, "t/free", concept={"id": "t-free", "title": "無祖先", "order": 2},
               decisions=[])
    leaves = load_project(Layout(home))
    by = {lf.section: lf for lf in leaves}
    governed_fp = ancestor_normative_fingerprint("t/leaf", by)
    assert governed_fp != ""                                     # 跨樹治理父的 ruling 入帳
    assert ancestor_normative_fingerprint("t/free", by) == ""    # 穩定空值
    # 治理父改寫 ruling → 被治理節指紋變
    (home / "corpus" / "p" / "decisions.yaml").write_text(
        yaml.safe_dump({"entries": [{"id": "NP", "statement": "跨樹規矩（修訂）",
                                     "status": "accepted", "kind": "normative"}]},
                       allow_unicode=True, sort_keys=False), encoding="utf-8")
    leaves2 = load_project(Layout(home))
    by2 = {lf.section: lf for lf in leaves2}
    assert ancestor_normative_fingerprint("t/leaf", by2) != governed_fp


# ── 5. 帳本 v2 與一次性遷移 ────────────────────────────────────────────────────


def _baseline(make_project, write_leaf, monkeypatch):
    home = make_project()
    write_leaf(home, "g/intro", concept={"id": "c1", "title": "概覽", "order": 1})
    monkeypatch.chdir(home.parent)
    assert render_cmd.run(["g"]) == 0
    _write_prose(home, "g", "概覽", "限流保護後端。")
    assert _sync_of(home, "g", "g/intro") == "synced"
    return home


def _downgrade_ledger_to_v1(home, article="g"):
    """把現行 v2 帳本改寫成 v1 形制（去版本鍵；style 壓回 v1 的單字串）。"""
    ledger = Layout(home).docs_ledger(article)
    data = yaml.safe_load(ledger.read_text(encoding="utf-8"))
    data.pop("fingerprint", None)
    for rec in (data.get("sections") or {}).values():
        if isinstance(rec, dict):
            rec.pop("norm", None)
            if isinstance(rec.get("style"), dict):
                rec["style"] = "0" * 16
    ledger.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                      encoding="utf-8")


def test_write_ledger_carries_version_key(make_project, write_leaf, monkeypatch):
    """5.1：render 寫出的帳本頂層帶現行 `fingerprint:` 版本；read_ledger_version 回報。"""
    home = _baseline(make_project, write_leaf, monkeypatch)
    data = yaml.safe_load(Layout(home).docs_ledger("g").read_text(encoding="utf-8"))
    from dspx.engine.render import LEDGER_FINGERPRINT_VERSION
    assert data["fingerprint"] == LEDGER_FINGERPRINT_VERSION
    assert read_ledger_version(Layout(home), "g") == LEDGER_FINGERPRINT_VERSION


def test_leaf_order_change_is_not_stale_own(make_project, write_leaf, monkeypatch):
    """v3（contract-slimming）：`order` 是位置元資料、排除於 own 指紋——顯式改一節的 order
    值（對調兄弟/搬位）**不**誤標 stale-own（位置變、內容沒變；章號由 render 從 order 推導、
    散文不重寫）。D4 的殘缺半邊：小數插入本就不觸發，此處釘死「明確改 order 值」也不觸發。"""
    home = make_project()
    write_leaf(home, "g/a", concept={"id": "ca", "title": "甲", "order": 1})
    write_leaf(home, "g/b", concept={"id": "cb", "title": "乙", "order": 2})
    monkeypatch.chdir(home.parent)
    assert render_cmd.run(["g"]) == 0
    _write_prose(home, "g", "甲", "甲的散文。")
    _write_prose(home, "g", "乙", "乙的散文。")
    assert _sync_of(home, "g", "g/a") == "synced"
    assert _sync_of(home, "g", "g/b") == "synced"
    # 對調兩節 order 值（甲←→乙）：只動位置元資料，內容欄一字不改
    ca = home / "corpus" / "g" / "a" / "concept.yaml"
    cb = home / "corpus" / "g" / "b" / "concept.yaml"
    ca.write_text(ca.read_text("utf-8").replace("order: 1", "order: 2"), "utf-8")
    cb.write_text(cb.read_text("utf-8").replace("order: 2", "order: 1"), "utf-8")
    # 兩節皆維持 synced——order 不在 own 指紋（不誤標 stale-own）
    assert _sync_of(home, "g", "g/a") == "synced"
    assert _sync_of(home, "g", "g/b") == "synced"
    # 重 render：章號自動對調（乙=1./甲=2.），散文原樣保留、仍 synced
    assert render_cmd.run(["g"]) == 0
    text = _latest(home).read_text("utf-8")
    assert "## 1. 乙" in text and "## 2. 甲" in text
    assert "甲的散文。" in text and "乙的散文。" in text
    assert _sync_of(home, "g", "g/a") == "synced"
    assert _sync_of(home, "g", "g/b") == "synced"


def test_concept_content_change_still_stale_own(make_project, write_leaf, monkeypatch):
    """反面守門：排除 order 沒把該髒的內容欄一起吞掉——改 concept 內容欄仍 stale-own。
    title（渲進標題＝內容）與 concept 一句話（aperture 錨）都保留在 own 指紋內。"""
    home = _baseline(make_project, write_leaf, monkeypatch)   # g/intro synced（有散文）
    cpt = home / "corpus" / "g" / "intro" / "concept.yaml"
    # 改 title＝內容欄（保留在 own 指紋）→ stale-own
    cpt.write_text(cpt.read_text("utf-8").replace("title: 概覽", "title: 概覽（修訂）"), "utf-8")
    assert _sync_of(home, "g", "g/intro") == "stale-own"


def test_v1_ledger_shows_needs_migration_not_stale_storm(
        make_project, write_leaf, monkeypatch, capsys):
    """5.2：v1 帳本 → 各節 needs-migration（不假報 stale-*、不報 synced）＋文章級指示。"""
    home = _baseline(make_project, write_leaf, monkeypatch)
    _downgrade_ledger_to_v1(home)
    assert read_ledger_version(Layout(home), "g") == 1
    capsys.readouterr()
    assert status_cmd.run(["g", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    (row,) = [r for r in payload["sections"] if r["section"] == "g/intro"]
    assert row["sync"] == "needs-migration"
    assert payload["needsMigration"] == ["g"]
    # 人讀輸出帶遷移指示
    assert status_cmd.run(["g"]) == 0
    out = capsys.readouterr().out
    assert "needs-migration" in out and "docspec render g --rebaseline" in out


def test_regular_render_refuses_v1_ledger(make_project, write_leaf, monkeypatch, capsys):
    """5.3：常規 render 遇 v1 → 非零退出、帳本與 _latest 一個 byte 不動。"""
    home = _baseline(make_project, write_leaf, monkeypatch)
    _downgrade_ledger_to_v1(home)
    ledger_bytes = Layout(home).docs_ledger("g").read_bytes()
    latest_bytes = _latest(home).read_bytes()
    capsys.readouterr()
    assert render_cmd.run(["g"]) != 0
    assert "older fingerprint version" in capsys.readouterr().err
    assert Layout(home).docs_ledger("g").read_bytes() == ledger_bytes
    assert _latest(home).read_bytes() == latest_bytes


def test_rebaseline_migrates_v1_to_v2_in_one_shot(make_project, write_leaf, monkeypatch, capsys):
    """5.4：v1 → --rebaseline 一次過（散文保留、吸收警語）→ synced；之後現行語義各一發。"""
    home = _baseline(make_project, write_leaf, monkeypatch)
    _glossary_write(home, [dict(_TERM)])
    assert render_cmd.run(["g", "--ack", "g/intro"]) == 0        # 先把 gloss 基準清乾淨
    _downgrade_ledger_to_v1(home)
    capsys.readouterr()
    assert render_cmd.run(["g", "--rebaseline"]) == 0
    err = capsys.readouterr().err
    assert "absorbed" in err                                     # 吸收警語明講
    from dspx.engine.render import LEDGER_FINGERPRINT_VERSION
    assert read_ledger_version(Layout(home), "g") == LEDGER_FINGERPRINT_VERSION
    assert "限流保護後端。" in _latest(home).read_text("utf-8")   # 散文原樣保留
    assert _sync_of(home, "g", "g/intro") == "synced"
    rec = read_ledger(Layout(home), "g")["g/intro"]
    assert set(rec) >= {"own", "anc", "deps", "norm", "style", "prose"}
    # v2 語義抽驗：CRLF 免疫（concept 轉 CRLF 仍 synced）＋ definition-only 零擾動
    _to_crlf(home / "corpus" / "g" / "intro" / "concept.yaml")
    assert _sync_of(home, "g", "g/intro") == "synced"
    t = dict(_TERM); t["definition"] = "另一句定義。"
    _glossary_write(home, [t])
    assert _sync_of(home, "g", "g/intro") == "synced"
    # canonical 修改 → stale-style（v2 gloss 子軸有信號）
    t = dict(_TERM); t["canonical"] = "節流模組（新名）"
    _glossary_write(home, [t])
    assert _sync_of(home, "g", "g/intro") == "stale-style"


def test_stale_verb_refuses_v1_ledger(make_project, write_leaf, monkeypatch, capsys):
    """v1 帳本上 stale/redraft 拒跑（write_ledger 會蓋版本鍵＝把舊值謊稱 v2）。"""
    from dspx.commands.deliverable import stale as stale_cmd
    home = _baseline(make_project, write_leaf, monkeypatch)
    _downgrade_ledger_to_v1(home)
    capsys.readouterr()
    assert stale_cmd.run(["g/intro", "--reason", "test"]) == 1
    assert "older fingerprint version" in capsys.readouterr().err


# ── 7.2 與 ledger-verdict-verbs 介面對齊（雙 change 交界）─────────────────────


def test_ack_own_keeps_norm_so_masked_stale_norm_surfaces(
        make_project, write_leaf, monkeypatch):
    """--ack-own 蓋 own/deps、沿用 norm/anc/style → 被 stale-own 遮蔽的 stale-norm 浮出；
    再以 --ack 清（守門：own 已被 ack-own 蓋至現值 → 通過）。"""
    home = _norm_project(make_project, write_leaf, monkeypatch)
    # 祖先 ruling 與子節自身 metadata 同時變：precedence 顯 stale-own（遮蔽 stale-norm）。
    # own 變更用 `sources`（外部出處指標＝結構/元資料，散文未必需改 → ack-own 正當）；
    # **不用 order**——order 已排除於 own 指紋（v3），改 order 不再 stale-own
    # （見 test_leaf_order_change_is_not_stale_own）。
    _set_root_decisions(home, [{"id": "N1", "statement": "全文禁用被動語態與展望語",
                                "status": "accepted", "kind": "normative"}])
    cpt = home / "corpus" / "g" / "sub" / "concept.yaml"
    cpt.write_text(cpt.read_text("utf-8") + 'sources: ["Author\'s design"]\n', "utf-8")
    assert _sync_of(home, "g", "g/sub") == "stale-own"
    # ack-own（結構接線類變更）：own/deps 蓋現值、norm 沿用舊值 → stale-norm 浮出
    assert render_cmd.run(["g", "--ack-own", "g/sub", "--reason", "sources provenance note only"]) == 0
    assert _sync_of(home, "g", "g/sub") == "stale-norm"
    # 核對散文合法 → --ack 清 norm（own 已符現值、守門通過）
    assert render_cmd.run(["g", "--ack", "g/sub"]) == 0
    assert _sync_of(home, "g", "g/sub") == "synced"
