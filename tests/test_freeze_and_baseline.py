"""2026/09/30 裁定：publish 改名 `docspec freeze`（檢查併進指令）、專案基線甲（定版自動記下軟體狀態）
與乙（`docspec baseline <名稱>`）、change 預覽標示草稿。"""

from __future__ import annotations

import json

import pytest

from dspx.commands.deliverable import freeze as freeze_cmd
from dspx.commands.deliverable import render as render_cmd
from dspx.commands.governance import baseline as baseline_cmd
from dspx.engine import project_baseline as pb
from dspx.engine.layout import Layout
from dspx.engine.software import io as swio
from dspx.engine.software import specs as sp


@pytest.fixture
def doc(make_project, write_leaf, monkeypatch):
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1})
    monkeypatch.chdir(home.parent)
    monkeypatch.setenv("DOCSPEC_AGENT", "claude")
    render_cmd.run(["g"])
    return home


def _write_prose(home, text="內文。"):
    latest = home.parent / "docs" / "g" / "_latest.md"
    body = latest.read_text(encoding="utf-8")
    if "## 1. X\n\n" in body and "內文" in body:
        body = body.replace("內文。", text)
    else:
        body = body.replace("## 1. X\n", f"## 1. X\n\n{text}\n")
    latest.write_text(body, encoding="utf-8")


def test_freeze_refuses_unwritten_sections(doc, write_leaf, capsys):
    write_leaf(doc, "g/y", concept={"id": "c2", "title": "Y", "order": 2})
    render_cmd.run(["g"])
    _write_prose(doc)                                            # 只寫了 g/x，g/y 還沒寫
    capsys.readouterr()
    assert freeze_cmd.run(["g"]) == 1
    err = capsys.readouterr().err
    assert "not ready" in err and "g/y: unwritten" in err
    assert not (doc.parent / "docs" / "g" / "archive").exists()
    assert freeze_cmd.run(["g", "--allow-incomplete"]) == 0     # 使用者明確接受時可以定版


def test_freeze_writes_the_version_and_records_software_state(doc, capsys):
    layout = Layout(doc)
    sp.write_spec(layout, {"capability": "c", "purpose": "p", "requirements": [
        {"id": "R1", "title": "t", "statement": "It SHALL x.", "verification": ["test"],
         "scenarios": [{"id": "S1", "title": "s", "when": "w", "then": "t"}]}]})
    _write_prose(doc)
    assert freeze_cmd.run(["g"]) == 0
    out = capsys.readouterr()
    assert "frozen \"g\" v1.0.0" in out.out
    assert "no review record yet" in out.err                     # factcheck：只提醒
    rec = pb.doc_version_record(layout, "g", "1.0.0")
    assert rec["document"] == "g" and list(rec["software"]["specs"]) == ["c"]
    assert baseline_cmd.run(["doc", "g", "1.0.0", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["version"] == "1.0.0"


def test_freeze_suggests_the_level_and_publish_is_an_alias(doc, capsys):
    from dspx.commands.deliverable import publish as publish_alias
    _write_prose(doc)
    assert publish_alias.run(["g"]) == 0                        # 舊名仍可用
    _write_prose(doc, "改過的內文。")
    capsys.readouterr()
    assert freeze_cmd.run(["g"]) == 0
    captured = capsys.readouterr()
    assert "level patch chosen automatically" in captured.err and "v1.0.1" in captured.out


def test_date_versioned_document(doc, capsys):
    import datetime
    _write_prose(doc)
    assert freeze_cmd.run(["g", "--date-version"]) == 0
    t = datetime.date.today()
    assert f"v{t.year}.{t.month}.{t.day}" in capsys.readouterr().out
    _write_prose(doc, "同一天又改。")
    assert freeze_cmd.run(["g", "--date-version"]) == 1           # 同一天只能一版
    assert "already has a version for today" in capsys.readouterr().err


def test_project_baseline_pins_everything(doc, capsys):
    layout = Layout(doc)
    _write_prose(doc)
    freeze_cmd.run(["g"])
    _write_prose(doc, "定版後又改了。")
    capsys.readouterr()
    assert baseline_cmd.run(["期中交付", "--note", "計畫期中查核"]) == 0
    out = capsys.readouterr().out
    assert "baseline \"期中交付\" recorded" in out
    assert "g: v1.0.0" in out and "edits after v1.0.0 that are not frozen" in out
    b = pb.load(layout, "期中交付")
    assert b["documents"]["g"] == {"version": "1.0.0", "unfrozen-edits": True}
    assert baseline_cmd.run(["期中交付"]) == 1                    # 名稱不可重複
    assert "never overwritten" in capsys.readouterr().err
    assert baseline_cmd.run(["list"]) == 0
    assert "期中交付" in capsys.readouterr().out
    assert baseline_cmd.run(["show", "期中交付"]) == 0
    assert "計畫期中查核" in capsys.readouterr().out


def test_baseline_files_are_sealed(doc):
    layout = Layout(doc)
    _write_prose(doc)
    freeze_cmd.run(["g"])
    baseline_cmd.run(["交付"])
    p = pb.project_path(layout, "交付")
    p.write_text(p.read_text(encoding="utf-8").replace("1.0.0", "9.9.9"), encoding="utf-8")
    from dspx.engine.software import validate_all
    errs, _w = validate_all(layout)
    assert any("integrity seal mismatch" in e for e in errs)


def test_change_preview_is_marked_as_draft(doc, capsys):
    from dspx.commands.change import change as change_cmd
    _write_prose(doc)
    assert change_cmd.run(["new", "fix-x", "--publish", "advisory"]) == 0
    assert change_cmd.run(["add-target", "fix-x", "g/x", "--action", "revise"]) == 0
    assert render_cmd.run(["g", "--change", "fix-x"]) == 0
    preview = doc / "changes" / "fix-x" / "preview"
    text = next(preview.glob("*_latest.md")).read_text(encoding="utf-8")
    assert "fix-x" in text and ("草稿，尚未定版" in text or "DRAFT, not frozen" in text)


def test_hook_protects_baselines(monkeypatch):
    from dspx.commands._internal.hook import _protected_message
    assert _protected_message("/p/docspec/baselines/期中交付.yaml")
    assert _protected_message("/p/docspec/baselines/documents/g@1.0.0.yaml")
    assert _protected_message("/p/docspec/software/config.yaml") is None


def test_software_io_unaffected():
    assert swio.ARCHIVE_DIR == "_archive"
