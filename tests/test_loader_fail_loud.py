"""loader fail-loud：誤名頂層 key 不靜默當空（與 _entries 同契約，補 audit/roadmap/glossary）；
read_ledger 對壞檔可見降級而非默默失效；cli 把 domain 錯誤包成友善訊息而非 traceback。"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from dspx.audit import AuditError, AuditStore
from dspx.glossary import load_glossary
from dspx.layout import Layout
from dspx.model import ModelError, _load_yaml, keyed_list
from dspx.roadmap import _load_entries


# ── keyed_list 契約 ─────────────────────────────────────────────────

def test_keyed_list_empty_is_legal(tmp_path):
    p = tmp_path / "x.yaml"
    assert keyed_list(None, p, "entries") == []          # 空檔
    assert keyed_list({}, p, "entries") == []            # 空 mapping
    assert keyed_list({"entries": []}, p, "entries") == []  # 明確空 list


def test_keyed_list_misnamed_key_raises(tmp_path):
    p = tmp_path / "x.yaml"
    with pytest.raises(ModelError) as exc:
        keyed_list({"decisions": [{"id": "d1"}]}, p, "entries")
    assert "entries" in str(exc.value)   # hint 指向正確 key


# ── 三個 loader（audit/roadmap/glossary）誤名 key fail-loud ──────────

def test_audit_misnamed_findings_key_raises(tmp_path):
    p = tmp_path / "audit.yaml"
    p.write_text(yaml.safe_dump({"audits": [{"id": "f1", "face": "x"}]}), encoding="utf-8")
    with pytest.raises(AuditError):
        AuditStore.load(p)


def test_roadmap_misnamed_key_raises(tmp_path):
    p = tmp_path / "roadmap.yaml"
    p.write_text(yaml.safe_dump({"tasks": [{"id": "r1"}]}), encoding="utf-8")
    with pytest.raises(ModelError):
        _load_entries(p, "doc:art")


def test_glossary_misnamed_key_raises(make_project):
    home = make_project()
    (home / "glossary.yaml").write_text(
        yaml.safe_dump({"glossary": [{"id": "t1", "canonical": "x"}]}), encoding="utf-8")
    with pytest.raises(ModelError):
        load_glossary(Layout(home))


def test_loaders_legal_empty_or_correct(tmp_path, make_project):
    # 缺檔 / 正確 key 仍正常
    assert AuditStore.load(tmp_path / "nope.yaml").findings == []
    p = tmp_path / "audit.yaml"
    p.write_text(yaml.safe_dump({"findings": [{"id": "f1"}]}), encoding="utf-8")
    assert len(AuditStore.load(p).findings) == 1


# ── F3：corpus YAML 重複 mapping key fail-loud ──────────────────────

def test_load_yaml_duplicate_key_raises(tmp_path):
    p = tmp_path / "decisions.yaml"
    p.write_text("id: x\nstatement: first\nstatement: second\n", encoding="utf-8")
    with pytest.raises(ModelError) as exc:
        _load_yaml(p)
    msg = str(exc.value)
    assert "duplicate" in msg and "statement" in msg   # key 名
    assert "line 3" in msg                              # 行號定位


def test_load_yaml_duplicate_key_nested(tmp_path):
    # 巢狀 mapping 內的重複 key 也要抓（不只頂層）
    p = tmp_path / "x.yaml"
    p.write_text("brief:\n  depth: a\n  depth: b\n", encoding="utf-8")
    with pytest.raises(ModelError):
        _load_yaml(p)


def test_load_yaml_merge_key_not_flagged(tmp_path):
    # 合法 YAML merge key `<<` 不該被當重複 key 誤報
    p = tmp_path / "x.yaml"
    p.write_text(
        "defaults: &d\n  a: 1\nitem:\n  <<: *d\n  b: 2\n", encoding="utf-8")
    data = _load_yaml(p)
    assert data["item"] == {"a": 1, "b": 2}


def test_load_yaml_clean_file_unchanged(tmp_path):
    p = tmp_path / "x.yaml"
    p.write_text("id: x\nstatement: only\nkind: normative\n", encoding="utf-8")
    assert _load_yaml(p) == {"id": "x", "statement": "only", "kind": "normative"}


# ── read_ledger 壞檔可見降級（非靜默） ──────────────────────────────

def test_read_ledger_malformed_sidecar_warns_not_silent(make_project, capsys):
    from dspx.render import read_ledger
    home = make_project()
    led = Layout(home).docs_ledger("g")
    led.parent.mkdir(parents=True, exist_ok=True)
    led.write_text("entries: [unclosed\n", encoding="utf-8")   # 壞 YAML
    assert read_ledger(Layout(home), "g") == {}
    assert "malformed" in capsys.readouterr().err   # 可見警告，不是默默回 {}


def test_read_ledger_malformed_frontmatter_fallback_warns(make_project, capsys):
    from dspx.render import read_ledger
    home = make_project()
    latest = Layout(home).docs_latest("g")
    latest.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text("---\nbad frontmatter never closed\n\n## body\n", encoding="utf-8")
    assert read_ledger(Layout(home), "g") == {}      # 不 crash
    assert "malformed" in capsys.readouterr().err


# ── cli 把 domain 錯誤包成友善訊息（非 traceback） ──────────────────

def test_cli_wraps_domain_error_friendly(make_project, write_leaf, monkeypatch, capsys):
    from dspx import cli
    home = make_project()
    write_leaf(home, "a/x", concept={"id": "c1", "title": "X", "order": 1})
    # 把 decisions.yaml 寫成誤名頂層 key → load 時 ModelError
    (home / "corpus" / "a" / "x" / "decisions.yaml").write_text(
        yaml.safe_dump({"decisions": [{"id": "d1", "kind": "normative",
                                       "status": "accepted", "statement": "x"}]}),
        encoding="utf-8")
    monkeypatch.chdir(home.parent)
    rc = cli.main(["check"])
    assert rc == 1                                   # 非零、但不是 traceback
    err = capsys.readouterr().err
    assert "docspec:" in err and "entries" in err    # 友善一行訊息＋hint
