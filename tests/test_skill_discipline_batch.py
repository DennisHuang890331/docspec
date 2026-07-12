"""skill-discipline-batch：〔#17〕new --reopen 重開已結晶節、〔#16〕派工排除清單、
〔#19〕標點寬度禁令、develop reasoning-lands-as-it-happens step 與 guide 投影。"""

from __future__ import annotations

import json

import yaml

from dspx.commands import guide as guide_cmd
from dspx.commands import new as new_cmd
from dspx.commands import ready as ready_cmd
from dspx.commands import status as status_cmd
from dspx.skills import available_skills


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
    leaf = home / "corpus" / "g" / "intro"
    assert (leaf / "concept.yaml").is_file()
    assert not (leaf / "develop.md").exists()
    monkeypatch.chdir(home.parent)

    assert new_cmd.run(["g/intro", "--reopen"]) == 0
    body = (leaf / "develop.md").read_text(encoding="utf-8")
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
    leaf = home / "corpus" / "g" / "intro"
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
    assert not (home / "corpus" / "g" / "intro" / "develop.md").exists()   # 不覆寫


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


# ── 3. 〔#16〕〔#19〕skill 文案落地 ──────────────────────────────────


def test_apply_merges_both_modes():
    """dspx-apply 併 draft+edit 雙模式：body 真含 rewrite（盲渲染/寫作原則/Bans）
    與 align（三階段/verdict verb/exclusion list）兩模式內容——非空殼。"""
    body = _skill_body("dspx-apply")
    assert "Choosing the mode" in body            # 模式選擇段（engine 路由、不查表）
    assert "# Rewrite mode" in body               # rewrite 模式（原 draft）
    assert "Inverted pyramid" in body
    assert "blind to its siblings" in body
    assert "## Bans" in body
    assert "# Align mode" in body                 # align 模式（原 edit）
    assert "## The Routing Rule" in body
    assert "Stage 1 — Line edit" in body
    assert "Stage 3 — Proofread" in body
    assert "--ack-own" in body                    # verdict verb 白名單
    assert "dspx-draft" not in body and "dspx-edit" not in body   # 舊名不再出現


def test_apply_align_carries_exclusion_list_after_routing_rule_before_stage1():
    """dspx-apply align 模式：排除清單節在「The Routing Rule」之後、Stage 1 之前，逐條列排除項＋去處。"""
    body = _skill_body("dspx-apply")
    routing = body.index("## The Routing Rule")
    excl = body.index("## Subagent dispatch briefs — the exclusion list")
    stage1 = body.index("## Stage 1")
    assert routing < excl < stage1               # 插入位置正確
    section = body[excl:stage1]
    assert "SEMANTIC work only" in section        # brief 開頭必聲明
    assert "Punctuation width" in section
    assert "docspec normalize" in section         # 引擎確定性 auto-fix
    assert "V18" in section                        # lint 殘留兜底、指回 normalize
    assert "docspec lint" in section              # 洩漏 scaffolding／drift 去處
    assert "docspec check" in section             # 錨點去處
    assert "grep" in section                      # banned openers 監工手動、同樣不派


def test_apply_guardrails_dont_has_punctuation_ban():
    """dspx-apply 共用 Guardrails Don't 含標點寬度禁令（禁手改 sweep、byte-exact 點名、導向 normalize）。"""
    body = _skill_body("dspx-apply")
    dont = body[body.rindex("**Don't**"):]        # 最後一段＝共用 Guardrails Don't
    assert "punctuation-width sweep" in dont.lower()
    assert "no blind regex" in dont.lower()
    assert "byte-exact" in dont.lower()
    assert "code spans, identifiers, protocol tokens, and URLs" in dont
    assert "docspec normalize" in dont       # 導向引擎確定性 normalize（非手改、非 audit finding）


def test_apply_rewrite_bans_have_punctuation_ban():
    """dspx-apply rewrite 模式 Bans 含同旨禁令（禁手改 sweep、不禁寫稿當下寫對、byte-exact 點名、導向 normalize）。"""
    body = _skill_body("dspx-apply")
    bans = body[body.index("## Bans"):body.index("## Rewrite guardrails")]
    assert "punctuation-width sweep" in bans.lower()
    assert "as you compose" in bans          # 不禁寫稿當下寫對
    assert "docspec normalize" in bans       # 導向引擎確定性 normalize
    assert "byte-exact" in bans.lower()


def test_develop_teaches_reopen_after_reversal_paragraph():
    """dspx-develop：「Reversal is normal.」段後有 reopen 段落（--reopen＋根節工作台＋roadmap doing）。"""
    body = _skill_body("dspx-develop")
    reversal = body.index("**Reversal is normal.**")
    reopen = body.index("Reasoning lands as it happens")
    what = body.index("## What You Might Do")
    assert reversal < reopen < what           # 插在 Reversal 段之後、清單之前
    para = body[reopen:what]
    assert "docspec new <section>\n--reopen" in para or "--reopen" in para
    assert "root section" in para.lower() and "central workbench" in para
    assert "roadmap" in para and "doing" in para


def test_punctuation_stance_points_to_normalize():
    """punctuation-normalizer 落地後：標點文案改指向引擎確定性 `docspec normalize`（不再手改、
    不再是誠實版「無 auto-fix」）；仍不宣稱引擎會創作/改寫內容（normalize 只換字寬）。"""
    for name in ("dspx-apply",):
        body = _skill_body(name)
        assert "docspec normalize" in body                     # 導向引擎確定性 auto-fix
        assert "no punctuation auto-fix today" not in body       # 誠實版已過時、不得殘留
