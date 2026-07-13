"""skill-discipline-batch：〔#17〕new --reopen 重開已結晶節、〔#16〕派工排除清單、
〔#19〕標點寬度禁令、develop reasoning-lands-as-it-happens step 與 guide 投影。"""

from __future__ import annotations

import json

import yaml

from dspx.commands.projection import guide as guide_cmd
from dspx.commands.corpus import new as new_cmd
from dspx.commands.corpus import ready as ready_cmd
from dspx.commands.query import status as status_cmd
from dspx.env.skills import available_skills


def _skill_body(name: str) -> str:
    return next(s for s in available_skills() if s.name == name).body


def _status_state(capsys, section: str) -> str:
    """跑 status --json，回傳指定節的 state。"""
    assert status_cmd.run(["--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    row = next(r for r in data["sections"] if r["section"] == section)
    return row["state"]


# ── 1. 〔#17〕docspec new --reopen 三分支 ─────────────────────────────


def test_reopen_rebuilds_develop_from_concept(make_project, write_leaf, monkeypatch, capsys):
    """已結晶（有 concept.yaml、無 develop.md）→ 重建 develop.md，id/title/order 從 concept
    讀出（非路徑重算），status 該節轉 developing。"""
    home = make_project()
    write_leaf(home, "g/intro",
               concept={"id": "c-fixed-99", "title": "概覽標題", "order": 7, "concept": "real"},
               decisions=[{"id": "d1", "kind": "normative", "status": "accepted", "statement": "s"}])
    # ★store-only：concept 在 store 記錄、develop.md 在 work/
    work = home / "work" / "g" / "intro"
    assert not (work / "develop.md").exists()
    monkeypatch.chdir(home.parent)

    assert new_cmd.run(["g/intro", "--reopen"]) == 0
    body = (work / "develop.md").read_text(encoding="utf-8")
    assert "c-fixed-99" in body          # id 從 concept.yaml 讀，非 _stable_id 路徑重算
    assert "概覽標題" in body             # title 取 concept 現值
    assert "order: 7" in body            # order 取 concept 現值，非同層資料夾數重算
    # id 不是路徑 sha1 重算值（重算會是 sec-…）
    assert new_cmd._stable_id("g/intro") not in body
    # 種子是純註解 → 不擋畢業
    assert ready_cmd.drain_remainder(body) == ""
    # develop.md 在場 → status 自然轉 developing（零新狀態）
    capsys.readouterr()
    assert _status_state(capsys, "g/intro") == "developing"


def test_reopen_refuses_when_develop_already_open(make_project, write_leaf, monkeypatch, capsys):
    """develop.md 已在 → 拒（already open），非零、一個 byte 不動。"""
    home = make_project()
    write_leaf(home, "g/intro",
               concept={"id": "c1", "title": "X", "order": 1, "concept": "real"},
               decisions=[{"id": "d1", "kind": "normative", "status": "accepted", "statement": "s"}],
               develop="## still thinking\nkeep this")
    leaf = home / "work" / "g" / "intro"   # ★store-only：develop.md 住 work/
    before = (leaf / "develop.md").read_bytes()
    monkeypatch.chdir(home.parent)
    capsys.readouterr()
    assert new_cmd.run(["g/intro", "--reopen"]) == 2
    assert "already open" in capsys.readouterr().err
    assert (leaf / "develop.md").read_bytes() == before   # 不覆寫思考中的內容


def test_reopen_refuses_uncrystallized_and_points_at_plain_new(make_project, monkeypatch, capsys):
    """未結晶（無 concept.yaml）配 --reopen → 拒，指路普通 new。"""
    home = make_project()
    monkeypatch.chdir(home.parent)
    capsys.readouterr()
    assert new_cmd.run(["g/nope", "--reopen"]) == 2
    err = capsys.readouterr().err
    assert "not crystallized" in err
    assert "docspec new g/nope" in err        # 指路普通 new
    assert not (home / "corpus" / "g" / "nope").exists()   # 未建任何檔


def test_plain_new_on_crystallized_missing_develop_points_at_reopen(
        make_project, write_leaf, monkeypatch, capsys):
    """普通 new 對「已結晶且無 develop.md」的節 → 拒並指路 --reopen。"""
    home = make_project()
    write_leaf(home, "g/intro",
               concept={"id": "c1", "title": "X", "order": 1, "concept": "real"},
               decisions=[{"id": "d1", "kind": "normative", "status": "accepted", "statement": "s"}])
    monkeypatch.chdir(home.parent)
    capsys.readouterr()
    assert new_cmd.run(["g/intro"]) == 2
    err = capsys.readouterr().err
    assert "--reopen" in err
    assert not (home / "work" / "g" / "intro" / "develop.md").exists()   # 不覆寫


def test_plain_new_overwrite_message_unchanged_when_develop_present(
        make_project, write_leaf, monkeypatch, capsys):
    """回歸：develop.md 在場的重名拒絕訊息維持既有語（不誤指 --reopen）。"""
    home = make_project()
    write_leaf(home, "g/intro",
               concept={"id": "c1", "title": "X", "order": 1, "concept": "real"},
               develop="## thinking")
    monkeypatch.chdir(home.parent)
    capsys.readouterr()
    assert new_cmd.run(["g/intro"]) == 2
    err = capsys.readouterr().err
    assert "already exists" in err
    assert "--reopen" not in err


# ── 2. 〔develop step〕schema step 與 guide 投影 ──────────────────────


def test_guide_projects_reasoning_lands_step(make_project, monkeypatch, capsys):
    """docspec guide 投影 develop 的「Reasoning lands AS IT HAPPENS」step（含 reopen 路徑）。"""
    home = make_project()
    monkeypatch.chdir(home.parent)
    assert guide_cmd.run([]) == 0
    out = capsys.readouterr().out
    assert "Reasoning lands AS IT HAPPENS" in out
    assert "docspec new <section> --reopen" in out
    assert "central workbench" in out


def test_guide_json_carries_reasoning_step_in_develop_skill(make_project, monkeypatch, capsys):
    """--json 的結構化 develop steps 同步帶該 step（來源＝schema.yaml，非指令散文）。"""
    home = make_project()
    monkeypatch.chdir(home.parent)
    assert guide_cmd.run(["--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    develop = next(s for s in data["workflow"]["skills"] if s["id"] == "develop")
    steps_text = "\n".join(develop["steps"])
    assert "Reasoning lands AS IT HAPPENS" in steps_text
    assert "--reopen" in steps_text


# ── 2b. 〔develop step〕fractional order 也由 schema 投影（task 1.3）─────


def test_guide_projects_develop_fractional_order(make_project, monkeypatch, capsys):
    """docspec guide 的 develop steps 帶 fractional order（order: 2.5 插節不重編號）——來源＝schema。"""
    home = make_project()
    monkeypatch.chdir(home.parent)
    assert guide_cmd.run([]) == 0
    out = capsys.readouterr().out
    assert "order: 2.5" in out


# ── 3. 〔#16〕〔#19〕skill drive-through 落地（規則搬進投影、skill 只錨、不重抄）────


def test_apply_drives_both_modes_via_engine_routing():
    """dspx-apply 併 draft+edit：body 以 drive-through Steps 驅動 rewrite 與 align 兩模式，
    engine 路由（不查表）、錨定 instructions apply 投影；舊結構標題/舊名全廢。"""
    body = _skill_body("dspx-apply")
    assert "rewrite" in body and "align" in body
    assert "The engine routes" in body               # engine 路由、不查表
    assert "instructions apply" in body              # 錨定投影
    for old in ("# Rewrite mode", "# Align mode", "## Bans", "## The Routing Rule", "## Stage 1"):
        assert old not in body, f"old-structure header leaked: {old}"
    assert "dspx-draft" not in body and "dspx-edit" not in body   # 舊名不再出現


def test_apply_body_anchors_exclusion_list_but_does_not_restate_it():
    """派工排除清單搬進投影：apply body 只保留態度錨（copy the dispatch-exclusion list verbatim、
    SEMANTIC work only），不再逐條重抄（逐條在 instructions apply）。"""
    body = _skill_body("dspx-apply")
    assert "dispatch-exclusion list" in body          # 指向投影的錨
    assert "SEMANTIC work only" in body               # 保留「brief 開頭聲明」態度核
    assert "── Dispatch exclusions ──" not in body    # 逐條 header 不在 body（搬進投影）


def test_apply_punctuation_guardrail_points_to_normalize():
    """標點寬度紀律：apply Guardrails 仍指向引擎確定性 docspec normalize（禁手改 sweep、byte-exact
    點名），但長文寫作原則已搬進投影。"""
    body = _skill_body("dspx-apply")
    dont = body[body.rindex("**Guardrails**"):]
    assert "docspec edit --punct" in dont
    assert "byte-exact" in dont.lower()
    assert "width sweep" in dont.lower() or "blind regex" in dont.lower()
    assert "no punctuation auto-fix today" not in body       # 誠實版已過時、不得殘留


def test_develop_teaches_reopen_and_fractional_order():
    """dspx-develop（新格式）：Reversal 段教 reopen（--reopen＋根節工作台＋roadmap doing）；
    Steps 教 fractional order（order: 2.5 插節不重編號）。"""
    body = _skill_body("dspx-develop")
    assert "Reversal is normal" in body
    assert "--reopen" in body
    assert "central workbench" in body
    assert "roadmap" in body and "doing" in body
    assert "order: 2.5" in body                        # fractional order（task 1.3）
