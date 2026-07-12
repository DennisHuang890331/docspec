"""docspec rename-term（prose-span 限定術語代換；識別碼/code/URL byte-exact；dry-run）。

ground-truth＝台中港 F10：`OCC`→`行控中心` 換散文、不得誤傷 `OCC_LIMIT_WEATHER_API_*` 參數碼、
code span、URL。另驗 dry-run 零寫入、prose 指紋自持（無假 drift）。
"""

from __future__ import annotations

from pathlib import Path

from dspx.commands.deliverable import render as render_cmd
from dspx.commands.deliverable import rename_term as rt_cmd
from dspx.engine.layout import Layout
from dspx.engine.render import detect_drift


def _leaf(write_leaf, home, section="sc/a"):
    write_leaf(home, section, concept={
        "id": "c1", "title": "X", "order": 1, "concept": "x",
        "brief": {"audience": "a", "depth": "d", "breadth": "b", "forbidden": ["f"]}})


def _render(home: Path, monkeypatch, article="sc") -> Layout:
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


def test_ground_truth_occ_identifier_untouched(make_project, write_leaf, monkeypatch, capsys):
    """台中港 F10：OCC→行控中心 換散文、OCC_LIMIT_* 識別碼/code/URL 逐 byte 不動。"""
    home = make_project()
    _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    body = (
        "OCC 是行車控制核心。\n\n"
        "參數 `OCC_LIMIT_WEATHER_API_TIMEOUT` 由 OCC 下發，識別碼 OCC_LIMIT_WEATHER_API_MAX 不改。\n\n"
        "詳見 https://example.com/OCC/spec 與 OCC 之關係。\n\n"
        "```\nOCC_STATE = read(OCC_LIMIT)\n```")
    _inject_prose(layout, "sc", "sc/a", body)
    render_cmd.run(["sc"])
    capsys.readouterr()

    monkeypatch.chdir(home.parent)
    rc = rt_cmd.run(["OCC", "行控中心"])
    assert rc == 0
    out = layout.docs_latest("sc").read_text(encoding="utf-8")

    # 散文 OCC 被換
    assert "行控中心 是行車控制核心。" in out
    assert "由 行控中心 下發" in out
    assert "與 行控中心 之關係。" in out
    # 識別碼（inline code 內／散文中裸識別碼）逐 byte 不動
    assert "`OCC_LIMIT_WEATHER_API_TIMEOUT`" in out
    assert "OCC_LIMIT_WEATHER_API_MAX 不改" in out
    # URL 內不動
    assert "https://example.com/OCC/spec" in out
    # fenced code 逐 byte 不動
    assert "OCC_STATE = read(OCC_LIMIT)" in out
    # 沒有把識別碼腐化成 行控中心_LIMIT_*
    assert "行控中心_LIMIT" not in out


def test_dry_run_writes_nothing(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject_prose(layout, "sc", "sc/a", "SC 跨運車由 SC 控制；識別碼 SC_ID 不變。")
    render_cmd.run(["sc"])
    capsys.readouterr()

    before = layout.docs_latest("sc").read_text(encoding="utf-8")
    monkeypatch.chdir(home.parent)
    rc = rt_cmd.run(["SC", "跨運車", "--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "--dry-run" in out
    assert "[SC -> 跨運車]" in out
    # 零寫入
    assert layout.docs_latest("sc").read_text(encoding="utf-8") == before


def test_no_false_drift_after_rename(make_project, write_leaf, monkeypatch, capsys):
    """代換後 prose 指紋自持 → detect_drift 不誤報。"""
    home = make_project()
    _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject_prose(layout, "sc", "sc/a", "AGV 自動導引車，AGV 於場區運行。")
    render_cmd.run(["sc"])
    capsys.readouterr()
    monkeypatch.chdir(home.parent)
    assert detect_drift(layout, "sc") == []
    rt_cmd.run(["AGV", "無人搬運車"])
    out = layout.docs_latest("sc").read_text(encoding="utf-8")
    assert "無人搬運車 自動導引車" in out
    assert detect_drift(layout, "sc") == []       # 無假 drift


def test_identifier_boundary_left_and_right(make_project, write_leaf, monkeypatch, capsys):
    """左右任一側為 ASCII 識別碼字元＝屬更大 token，跳過；純 CJK 鄰居則代換。"""
    home = make_project()
    _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    # OCC系統（CJK 緊鄰）應換；myOCC（左鄰字母）與 OCCX（右鄰字母）不換
    _inject_prose(layout, "sc", "sc/a", "OCC系統啟動；變數 myOCC 與 OCCX 不動。")
    render_cmd.run(["sc"])
    capsys.readouterr()
    monkeypatch.chdir(home.parent)
    rt_cmd.run(["OCC", "行控中心"])
    out = layout.docs_latest("sc").read_text(encoding="utf-8")
    assert "行控中心系統啟動" in out       # CJK 鄰居 → 換
    assert "myOCC" in out                  # 左鄰字母 → 跳過
    assert "OCCX" in out                   # 右鄰字母 → 跳過


def test_no_hits_reports_zero(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    _leaf(write_leaf, home)
    layout = _render(home, monkeypatch)
    _inject_prose(layout, "sc", "sc/a", "本節與該術語無關。")
    render_cmd.run(["sc"])
    capsys.readouterr()
    monkeypatch.chdir(home.parent)
    rc = rt_cmd.run(["ZZZ", "改過"])
    assert rc == 0
    assert "0 prose hit" in capsys.readouterr().out


def test_article_scope(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    _leaf(write_leaf, home, "sc/a")
    _leaf(write_leaf, home, "other/z")
    layout = _render(home, monkeypatch, "sc")
    _render(home, monkeypatch, "other")
    _inject_prose(layout, "sc", "sc/a", "OCC 在 sc。")
    _inject_prose(layout, "other", "other/z", "OCC 在 other。")
    render_cmd.run(["sc"]); render_cmd.run(["other"])
    capsys.readouterr()
    monkeypatch.chdir(home.parent)
    rt_cmd.run(["OCC", "行控中心", "--article", "sc"])
    assert "行控中心 在 sc" in layout.docs_latest("sc").read_text(encoding="utf-8")
    assert "OCC 在 other" in layout.docs_latest("other").read_text(encoding="utf-8")  # 未觸及
