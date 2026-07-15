"""skill-discipline-batch：〔#16〕派工排除清單、〔#19〕標點寬度禁令、develop step 的 guide 投影。
（原〔#17〕new --reopen 與 reasoning-lands step 已隨 retire-develop-workbench 廢除。）"""

from __future__ import annotations

import json

import yaml

from dspx.commands.projection import guide as guide_cmd
from dspx.env.skills import available_skills


def _skill_body(name: str) -> str:
    return next(s for s in available_skills() if s.name == name).body


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


def test_develop_teaches_rethink_via_put_and_fractional_order():
    """dspx-develop（★retire-develop-workbench 後）：Reversal 段教「直接 put 更新」＋
    notes.md 當耐久討論記錄；不再出現 --reopen／工作台字樣；fractional order（order: 2.5）保留。"""
    body = _skill_body("dspx-develop")
    assert "Reversal is normal" in body
    assert "--reopen" not in body and "workbench" not in body   # 廢案字樣不殘留
    assert "notes.md" in body                          # 耐久討論的家＝change notes.md
    assert "roadmap" in body and "task" in body
    assert "order: 2.5" in body                        # fractional order（task 1.3）
