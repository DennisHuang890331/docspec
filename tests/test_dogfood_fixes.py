"""dogfood 發現的修正：全域 audit id、show/resolve 免 --section、publish changelog+open-finding 警告。"""

from __future__ import annotations

from dspx.commands import audit as audit_cmd
from dspx.commands import publish as publish_cmd
from dspx.commands import render as render_cmd


def _draft(home, article):
    """快速讓某 article 有散文可發行。"""
    latest = home.parent / "docs" / article / "_latest.md"
    t = latest.read_text(encoding="utf-8")
    # 在每個 marker 後的標題下塞一句
    import re
    out, lines = [], t.split("\n")
    for i, ln in enumerate(lines):
        out.append(ln)
        if ln.startswith("## ") or ln.startswith("# "):
            if i + 1 < len(lines) and not lines[i + 1].strip():
                out.append("")
                out.append("內文。")
    latest.write_text("\n".join(out), encoding="utf-8")


def test_audit_ids_are_global(make_project, write_leaf, monkeypatch):
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    write_leaf(home, "a/y", concept={"id": "c2", "title": "Y", "order": 2})
    monkeypatch.chdir(home.parent)
    audit_cmd.run(["raise", "--target", "a/x", "--face", "logic", "--sev", "high", "--finding", "p1"])
    audit_cmd.run(["raise", "--target", "a/y", "--face", "clarity", "--sev", "low", "--finding", "p2"])
    from dspx.audit import load_doc_audit
    # 同文件 a → 都進 corpus/a/audit.yaml，全域 id 序列 F1/F2
    doc = load_doc_audit(home / "corpus" / "a", "a")
    ids = {f["id"] for f in doc.findings}
    assert ids == {"F1", "F2"}               # 全域唯一，不再都是 F1
    # resolve / show 免指定 store（用 id 反查）
    assert audit_cmd.run(["resolve", "F2", "--status", "fixed"]) == 0
    assert audit_cmd.run(["show", "F2"]) == 0


def test_publish_writes_changelog(make_project, write_leaf, monkeypatch):
    import datetime as _dt
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1})
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    _draft(home, "g")
    assert publish_cmd.run(["g", "--note", "首次發行"]) == 0
    changelog = home.parent / "docs" / "g" / "changelog.md"
    assert changelog.is_file()
    text = changelog.read_text(encoding="utf-8")
    # 精瘦 markdown 表：表頭 + 一列（版本/日期/級別/說明）
    assert "| 版本 | 日期 | 級別 | 說明 |" in text
    today = _dt.date.today().isoformat()
    # 預設 level=patch、無前版 → 1.0.0
    assert f"| 1.0.0 | {today} | Patch | 首次發行 |" in text


def test_publish_semver_bump_levels(make_project, write_leaf, monkeypatch):
    """連續 publish：無前版→1.0.0；--level minor→1.1.0；patch→1.1.1；major→2.0.0。"""
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1})
    monkeypatch.chdir(home.parent)
    archive = home.parent / "docs" / "g" / "archive"
    render_cmd.run(["g"])
    _draft(home, "g")

    assert publish_cmd.run(["g", "--note", "init"]) == 0          # 預設 patch、無前版 → 1.0.0
    assert (archive / "v1.0.0.md").is_file()
    assert publish_cmd.run(["g", "--level", "minor", "--note", "m"]) == 0
    assert (archive / "v1.1.0.md").is_file()
    assert publish_cmd.run(["g", "--level", "patch", "--note", "p"]) == 0
    assert (archive / "v1.1.1.md").is_file()
    assert publish_cmd.run(["g", "--level", "major", "--note", "M"]) == 0
    assert (archive / "v2.0.0.md").is_file()

    # changelog：四列、各標對的級別
    text = (home.parent / "docs" / "g" / "changelog.md").read_text(encoding="utf-8")
    rows = [ln for ln in text.splitlines() if ln.startswith("| ") and "---" not in ln]
    assert "| 版本 | 日期 | 級別 | 說明 |" in rows[0]
    cells = [r.split("|")[1].strip() for r in rows[1:]]
    assert cells == ["1.0.0", "1.1.0", "1.1.1", "2.0.0"]


def test_publish_changelog_row_is_lean_one_line(make_project, write_leaf, monkeypatch):
    """note 含換行 → 摺成一行，不抄細節（避說明列爆炸）。"""
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1})
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    _draft(home, "g")
    assert publish_cmd.run(["g", "--note", "第一行\n第二行   多空白"]) == 0
    text = (home.parent / "docs" / "g" / "changelog.md").read_text(encoding="utf-8")
    row = [ln for ln in text.splitlines() if ln.startswith("| 1.0.0 |")][0]
    assert "\n" not in row
    assert "第一行 第二行 多空白" in row


def test_publish_warns_but_proceeds_on_open_finding(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1})
    monkeypatch.chdir(home.parent)
    render_cmd.run(["g"])
    _draft(home, "g")
    audit_cmd.run(["raise", "--target", "g/x", "--face", "logic", "--sev", "high", "--finding", "未解"])
    rc = publish_cmd.run(["g"])
    assert rc == 0                            # 非阻塞：仍發行
    assert "unresolved audit finding" in capsys.readouterr().err   # 但有警告
