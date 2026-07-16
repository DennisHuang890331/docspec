"""put-change-aware：put/get 感知 active change（staging 路由、official 凍結）＋ show 定址統一
＋ change 收案語義（2.1 generic-reference 提示 / 2.2 silently-absorbed 列名）。

反作弊紀律（★P0 逐 byte）：active change 期間 put target → staging 有新內容、**official 檔逐
byte 不變**（讀 official bytes 前後比對）；abandon 後 official 零殘留（回歸壓測 C-1 恢復路徑）。
定址：同一節用 concept.id 與完整路徑**都查得到、輸出等價**；錯定址給指路訊息。測真實跨檔案狀態
與具體內容，不只斷 exit code。
"""

from __future__ import annotations

import json
import re

import yaml

from dspx.engine import change as chg
from dspx.engine import store as st
from dspx.commands.change import change as change_cmd
from dspx.commands.corpus import get as get_cmd
from dspx.commands.corpus import put as put_cmd
from dspx.commands.deliverable import render as render_cmd
from dspx.commands.query import show as show_cmd
from dspx.commands.query import status as status_cmd
from dspx.engine.layout import Layout


# ── 共用專案（root g 擁 normative dec-1；g/intro realizes dec-1；旁節 g/usage）──

def _project(make_project, write_leaf):
    home = make_project()
    write_leaf(home, "g", concept={"id": "sec-root", "title": "Guide", "order": 1,
                                   "status": "stable",
                                   "brief": {"audience": "devs", "depth": "deep", "breadth": "all"}},
               decisions=[{"id": "dec-1", "kind": "normative", "status": "accepted",
                           "statement": "Use metric units."}])
    write_leaf(home, "g/intro", concept={"id": "sec-intro", "title": "Intro", "order": 1,
                                         "realizes": ["dec-1"]})
    write_leaf(home, "g/usage", concept={"id": "sec-usage", "title": "Usage", "order": 2})
    return home


def _latest(home):
    return home.parent / "docs" / "g" / "_latest.md"


def _inject_all(home, prose_by_section):
    latest = _latest(home)
    lines = latest.read_text(encoding="utf-8").split("\n")
    out, i = [], 0
    marker_re = re.compile(r"^<!-- dspx:section (.+?) -->$")
    while i < len(lines):
        out.append(lines[i])
        m = marker_re.match(lines[i])
        if m and m.group(1) in prose_by_section:
            i += 1
            if i < len(lines):
                out.append(lines[i]); i += 1
            if i < len(lines) and not lines[i].strip():
                out.append(lines[i]); i += 1
            out.append("")
            out.append(prose_by_section[m.group(1)])
            continue
        i += 1
    latest.write_text("\n".join(out), encoding="utf-8", newline="\n")


def _render_baseline(home, monkeypatch, prose=None):
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    _inject_all(home, prose or {"g": "This guide uses metric units.",
                                "g/intro": "The intro implements the metric rule.",
                                "g/usage": "Usage details here."})
    render_cmd.run(["g"])


def _rewrite_preview_prose(home, cid, section, new_prose):
    change = chg.load_change(Layout(home, "per-article"), cid)
    pv = chg.preview_dir(change.dir) / "g_latest.md"
    text = pv.read_text(encoding="utf-8")
    text = re.sub(r"(<!-- dspx:section " + re.escape(section) + r" -->\n[^\n]*\n\n)[^\n]*",
                  lambda m: m.group(1) + new_prose, text, count=1)
    pv.write_text(text, encoding="utf-8", newline="\n")


def _concept_src(tmp_path, name, concept_field):
    data = {"id": "sec-intro", "title": "Intro", "order": 1, "status": "draft",
            "concept": concept_field, "brief": {}, "realizes": ["dec-1"]}
    p = tmp_path / name
    p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                 encoding="utf-8", newline="\n")
    return str(p)


# ── ★store-only staging accessors（取代舊的散檔 staging_target/<file>）──

def _official_sp(home, article="g"):
    """正式 store 檔路徑（official byte-frozen 斷言的實體）。"""
    return st.store_path(Layout(home, "per-article"), article)


def _official_concept(home, section):
    layout = Layout(home, "per-article")
    art = st.load_article(st.store_path(layout, section.split("/", 1)[0]), verify=False)
    return art.record_by_path(section).concept


def _staging_rec(home, cid, section):
    layout = Layout(home, "per-article")
    change = chg.load_change(layout, cid)
    staging = chg._load_staging_article(change.dir, section.split("/", 1)[0])
    return staging.record_by_path(section) if staging is not None else None


def _staging_concept_text(home, cid, section):
    """change staging 內某節 concept 的 yaml 文字（無記錄＝空字串）。"""
    import yaml as _y
    rec = _staging_rec(home, cid, section)
    return _y.safe_dump(rec.concept, allow_unicode=True) if (rec and rec.concept) else ""


def test_edit_refuses_when_section_in_active_change(
        make_project, write_leaf, monkeypatch, tmp_path):
    """#2（fable 審查）：change 期間 official 交付面凍結——edit 命中 active change 的節→拒絕
    （否則靜默改正式版→收案 drift 閘瞎＋反作弊假勾）。"""
    from dspx.commands.deliverable import edit as edit_cmd
    home = _project(make_project, write_leaf)
    _render_baseline(home, monkeypatch)
    change_cmd.run(["new", "chg-x", "--publish", "advisory"])
    change_cmd.run(["add-target", "chg-x", "sec-intro", "--action", "revise"])
    monkeypatch.chdir(home.parent)
    assert edit_cmd.run(["g/intro", "--replace", "x", "y"]) == 1     # 命中 active change → 拒絕
    assert edit_cmd.run(["g", "--punct"]) == 1                        # 整篇 edit 亦拒絕（含該節）
    # #2（壓測）：--dry-run 也要擋——dry-run 的意義是準確預覽真跑，真跑會拒、dry-run 就不能假放行。
    assert edit_cmd.run(["g/intro", "--replace", "x", "y", "--dry-run"]) == 1


# ── 4.1：active change 期間 put target → staging 有新內容、official byte 不變 ──

def test_put_target_routes_to_staging_official_byte_frozen(
        make_project, write_leaf, monkeypatch, tmp_path):
    home = _project(make_project, write_leaf)
    _render_baseline(home, monkeypatch)
    layout = Layout(home, "per-article")
    sp = _official_sp(home)                 # ★store-only：official＝corpus/g.yaml store 檔
    before = sp.read_bytes()                # ★收案前的 official store bytes

    change_cmd.run(["new", "chg-x", "--publish", "advisory"])
    change_cmd.run(["add-target", "chg-x", "sec-intro", "--action", "revise"])

    src = _concept_src(tmp_path, "c.yaml", "REVISED-IN-STAGING")
    assert put_cmd.run(["g/intro", "concept", src]) == 0

    # ★official store 逐 byte 不變（byte-frozen）
    assert sp.read_bytes() == before

    # ★staging partial store 有新內容
    assert "REVISED-IN-STAGING" in _staging_concept_text(home, "chg-x", "g/intro")
    assert "REVISED-IN-STAGING" not in sp.read_text(encoding="utf-8")


def test_official_status_unaffected_change_status_reflects(
        make_project, write_leaf, monkeypatch, tmp_path, capsys):
    home = _project(make_project, write_leaf)
    _render_baseline(home, monkeypatch)

    change_cmd.run(["new", "chg-x", "--publish", "advisory"])
    change_cmd.run(["add-target", "chg-x", "sec-intro", "--action", "revise"])
    src = _concept_src(tmp_path, "c.yaml", "REVISED-IN-STAGING")
    assert put_cmd.run(["g/intro", "concept", src]) == 0

    # official status：g/intro 仍 synced（official 源沒動）
    capsys.readouterr()
    assert status_cmd.run(["g", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)["sections"]
    intro = next(r for r in rows if r["section"] == "g/intro")
    assert intro["sync"] == "synced"

    # change status：sec-intro 在單、未 done（源改進 staging、散文未重寫）
    capsys.readouterr()
    assert change_cmd.run(["status", "chg-x", "--json"]) == 0
    st = json.loads(capsys.readouterr().out)
    tgt = next(t for t in st["targets"] if t["ref"] == "sec-intro")
    assert tgt["done"] is False


def test_put_nontarget_writes_official(make_project, write_leaf, monkeypatch, tmp_path):
    """非 target 節：即使有 active change（在別節），put 照舊寫 official。"""
    home = _project(make_project, write_leaf)
    _render_baseline(home, monkeypatch)
    layout = Layout(home, "per-article")

    change_cmd.run(["new", "chg-x", "--publish", "advisory"])
    change_cmd.run(["add-target", "chg-x", "sec-intro", "--action", "revise"])

    # 對旁節 g/usage（不在任何單）put → 寫 official store（無 staging 路由）★store-only
    data = dict(_official_concept(home, "g/usage"))
    data["concept"] = "USAGE-OFFICIAL-EDIT"
    p = tmp_path / "u.yaml"
    p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    assert put_cmd.run(["g/usage", "concept", str(p)]) == 0
    assert _official_concept(home, "g/usage")["concept"] == "USAGE-OFFICIAL-EDIT"
    # 沒有 g/usage 的 staging 記錄冒出來
    assert _staging_rec(home, "chg-x", "g/usage") is None


# ── 4.2：多 change 同 target fail-loud；--change 指名可寫 ──

def test_multi_change_same_target_fail_loud(make_project, write_leaf, monkeypatch, tmp_path, capsys):
    home = _project(make_project, write_leaf)
    _render_baseline(home, monkeypatch)
    sp = _official_sp(home)
    before = sp.read_bytes()

    change_cmd.run(["new", "chg-a", "--publish", "advisory"])
    change_cmd.run(["add-target", "chg-a", "sec-intro", "--action", "revise"])
    change_cmd.run(["new", "chg-b", "--publish", "advisory"])
    change_cmd.run(["add-target", "chg-b", "sec-intro", "--action", "revise"])

    a_before = _staging_concept_text(home, "chg-a", "g/intro")
    b_before = _staging_concept_text(home, "chg-b", "g/intro")

    src = _concept_src(tmp_path, "c.yaml", "AMBIGUOUS")
    capsys.readouterr()
    rc = put_cmd.run(["g/intro", "concept", src])
    assert rc == 2                                   # ★fail-loud、不猜
    err = capsys.readouterr().err
    assert "--change" in err and "chg-a" in err and "chg-b" in err
    # 沒寫任何一邊（★store-only：official store 檔 + 兩張 staging partial store 皆不變）
    assert sp.read_bytes() == before
    assert _staging_concept_text(home, "chg-a", "g/intro") == a_before
    assert _staging_concept_text(home, "chg-b", "g/intro") == b_before

    # --change 指名 chg-a → 只寫 chg-a staging
    assert put_cmd.run(["g/intro", "concept", src, "--change", "chg-a"]) == 0
    assert "AMBIGUOUS" in _staging_concept_text(home, "chg-a", "g/intro")
    assert _staging_concept_text(home, "chg-b", "g/intro") == b_before
    assert sp.read_bytes() == before


def test_put_change_not_targeting_section_errors(
        make_project, write_leaf, monkeypatch, tmp_path, capsys):
    """--change 指名一張不以此節為 target 的 active change → 拒絕、不隱式加 target。"""
    home = _project(make_project, write_leaf)
    _render_baseline(home, monkeypatch)
    change_cmd.run(["new", "chg-x", "--publish", "advisory"])
    change_cmd.run(["add-target", "chg-x", "sec-usage", "--action", "revise"])  # 目標是 g/usage
    src = _concept_src(tmp_path, "c.yaml", "X")
    capsys.readouterr()
    rc = put_cmd.run(["g/intro", "concept", src, "--change", "chg-x"])  # 但寫 g/intro
    assert rc == 2
    assert "does not target" in capsys.readouterr().err


# ── 4.3：get 預設 staging／--official 對照；abandon 後 official 零殘留（C-1）──

def test_get_default_staging_official_flag(make_project, write_leaf, monkeypatch, tmp_path, capsys):
    home = _project(make_project, write_leaf)
    _render_baseline(home, monkeypatch)
    change_cmd.run(["new", "chg-x", "--publish", "advisory"])
    change_cmd.run(["add-target", "chg-x", "sec-intro", "--action", "revise"])
    src = _concept_src(tmp_path, "c.yaml", "REVISED-IN-STAGING")
    assert put_cmd.run(["g/intro", "concept", src]) == 0

    # 預設 → staging 版（所見即所編）
    capsys.readouterr()
    assert get_cmd.run(["g/intro", "concept"]) == 0
    assert "REVISED-IN-STAGING" in capsys.readouterr().out

    # --official → 凍結基準（未含 staging 編輯）
    assert get_cmd.run(["g/intro", "concept", "--official"]) == 0
    out = capsys.readouterr().out
    assert "REVISED-IN-STAGING" not in out


def test_abandon_after_put_leaves_official_zero_residue(
        make_project, write_leaf, monkeypatch, tmp_path):
    """★回歸壓測 C-1：put 進 staging → abandon → official 逐 byte 零殘留、staging 消失。"""
    home = _project(make_project, write_leaf)
    _render_baseline(home, monkeypatch)
    layout = Layout(home, "per-article")
    sp = _official_sp(home)                 # ★store-only：official＝store 檔
    before = sp.read_bytes()
    latest_before = _latest(home).read_bytes()

    change_cmd.run(["new", "chg-x", "--publish", "advisory"])
    change_cmd.run(["add-target", "chg-x", "sec-intro", "--action", "revise"])
    src = _concept_src(tmp_path, "c.yaml", "REVISED-IN-STAGING")
    assert put_cmd.run(["g/intro", "concept", src]) == 0
    change = chg.load_change(layout, "chg-x")
    staging_root = chg.staging_dir(change.dir)
    assert staging_root.exists()

    assert change_cmd.run(["archive", "chg-x", "--abandon", "--reason", "wrong turn"]) == 0

    # ★official store + 交付物零 byte 變化；staging 副本整包消失（零回滾假設成立）
    assert sp.read_bytes() == before
    assert _latest(home).read_bytes() == latest_before
    assert chg.change_state(layout, "chg-x") == "abandoned"
    abandoned = chg.change_dir(layout, "chg-x", chg.STATE_ABANDONED)
    assert not chg.staging_dir(abandoned).exists()


# ── 4.4：show 定址統一（id 與路徑都查得到、輸出等價；錯定址指路）──

def _addr_project(make_project, write_leaf):
    """A 篇（root a → a/rules[dec-x] → a/rules/sub）；B 篇 b/impl realizes dec-x。"""
    home = make_project()
    write_leaf(home, "a", concept={"id": "c-a", "title": "A", "order": 0, "concept": "A 主旨",
                                   "brief": {"audience": "x", "depth": "y", "breadth": "z"}})
    write_leaf(home, "a/rules", concept={"id": "c-arules", "title": "規則", "order": 1,
                                         "concept": "規則層"},
               decisions=[{"id": "dec-x", "kind": "normative", "status": "accepted",
                           "statement": "頂層四態。"}])
    write_leaf(home, "a/rules/sub", concept={"id": "c-asub", "title": "子", "order": 1,
                                             "concept": "子層"})
    write_leaf(home, "b/impl", concept={"id": "c-bimpl", "title": "實作", "order": 1,
                                        "concept": "實作 A", "realizes": ["dec-x"]})
    return home


def _payload_no_id(capsys):
    d = json.loads(capsys.readouterr().out)
    d.pop("id", None)
    return d


def test_impact_addressing_path_and_concept_id_equivalent(
        make_project, write_leaf, monkeypatch, capsys):
    home = _addr_project(make_project, write_leaf)
    monkeypatch.chdir(home.parent)

    assert show_cmd.run(["a/rules", "--impact", "--json"]) == 0
    by_path = _payload_no_id(capsys)
    assert show_cmd.run(["c-arules", "--impact", "--json"]) == 0   # 同節、concept.id 定址
    by_id = _payload_no_id(capsys)
    assert by_path == by_id                                        # ★輸出等價
    assert by_path["section"] == "a/rules"
    assert {r["section"] for r in by_path["staleUpstream"]} == {"b/impl"}


def test_referenced_by_addressing_path_and_concept_id_equivalent(
        make_project, write_leaf, monkeypatch, capsys):
    home = _addr_project(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    render_cmd.run(["a"]); render_cmd.run(["b"])
    capsys.readouterr()

    assert show_cmd.run(["a/rules", "--referenced-by", "--json"]) == 0
    by_path = _payload_no_id(capsys)
    assert show_cmd.run(["c-arules", "--referenced-by", "--json"]) == 0
    by_id = _payload_no_id(capsys)
    assert by_path == by_id
    assert by_path["section"] == "a/rules"


def test_realized_by_accepts_section_path_form(make_project, write_leaf, monkeypatch, capsys):
    """--realized-by 也吃節路徑——★B4（engine-record-integrity）：節輸入＝聚合該節 concept＋
    全部自有決策的下游（原本只查 concept.id → 深耦合節誤報「沒人用」）。"""
    home = _addr_project(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    # decision id 直查（原行為不變）
    assert show_cmd.run(["dec-x", "--realized-by", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["realizedBy"] == ["b/impl"]
    # 節路徑形式：聚合——a/rules 的 concept 沒人 realize，但它擁有的 dec-x 有下游 → 不再假空集
    assert show_cmd.run(["a/rules", "--realized-by", "--json"]) == 0
    q = json.loads(capsys.readouterr().out)
    assert q["section"] == "a/rules" and q["realizedBy"] == ["b/impl"]
    assert any(g["id"] == "dec-x" and g["realizedBy"] == ["b/impl"] for g in q["ids"])


def test_misaddress_gives_pointing_message(make_project, write_leaf, monkeypatch, capsys):
    home = _addr_project(make_project, write_leaf)
    monkeypatch.chdir(home.parent)
    # 完全不存在的定址 → exit 1 + 指路
    assert show_cmd.run(["ghost-xyz", "--impact"]) == 1
    err = capsys.readouterr().err
    assert "could not resolve" in err and ("concept id" in err or "section path" in err)
    # 把 decision id 丟給 --referenced-by（該節用途錯）→ 解析到其擁有節仍可回；用一個死路徑測指路
    assert show_cmd.run(["no/such/path", "--referenced-by"]) == 1
    assert "could not resolve" in capsys.readouterr().err


# ── 2.1：change new --seed 對「通用引用型下游」提示可 remove-target ──

def test_seed_hints_remove_target_for_generic_reference_downstream(
        make_project, write_leaf, monkeypatch, capsys):
    home = _project(make_project, write_leaf)
    # g/intro 的散文以穩定錨引用 dec-1（generic reference、不硬寫值）
    _render_baseline(home, monkeypatch,
                     prose={"g": "This guide uses metric units.",
                            "g/intro": "The intro follows <!--@dec-1--><!--@--> exactly.",
                            "g/usage": "Usage details here."})
    capsys.readouterr()
    assert change_cmd.run(["new", "chg-x", "--seed", "dec-1", "--publish", "advisory"]) == 0
    out = capsys.readouterr().out
    assert "generic-reference downstream" in out
    assert "sec-intro" in out and "remove-target" in out


# ── 2.2：archive 重算把被 remove-target 踢出的下游靜默轉 synced → 列名「未經本次顯式復驗」──

def test_archive_lists_silently_absorbed_downstream(
        make_project, write_leaf, monkeypatch, capsys):
    home = _project(make_project, write_leaf)
    _render_baseline(home, monkeypatch)
    layout = Layout(home, "per-article")

    # seed dec-1 → auto-enlist owner g(sec-root) + realizer g/intro(sec-intro)
    change_cmd.run(["new", "chg-x", "--seed", "dec-1", "--publish", "advisory"])

    # 改上游（staging g 的 dec-1 statement）——落地後會令下游 g/intro stale-upstream
    # ★store-only：改 change 的 partial store staging 記錄 g 的 decisions
    change = chg.load_change(layout, "chg-x")
    chg.stage_section(change, layout, "g")
    staging = chg._load_staging_article(change.dir, "g")
    staging.record_by_path("g").decisions[0]["statement"] = "Use imperial units."
    chg._save_staging_article(change.dir, staging)

    # 把下游 g/intro 踢出單（通用引用型、不需重寫）
    assert change_cmd.run(["remove-target", "chg-x", "sec-intro"]) == 0

    # 只把上游 g 做完（重寫 preview 散文）
    render_cmd.run(["g", "--change", "chg-x"])
    _rewrite_preview_prose(home, "chg-x", "g", "This guide now uses imperial units.")
    render_cmd.run(["g", "--change", "chg-x"])

    capsys.readouterr()
    assert change_cmd.run(["archive", "chg-x"]) == 0
    err = capsys.readouterr().err
    # ★被 rebaseline 靜默轉 synced 的非 target 下游 g/intro 被列名、標「未經本次顯式復驗」
    assert "g/intro" in err
    assert "not re-verified" in err or "absorbed" in err
