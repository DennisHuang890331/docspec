"""governance-store-native：audit/roadmap 收成封條 sibling store（比照 article store 紀律）。

驗：封條 round-trip 不動點＋竄改偵測；roadmap add 引擎寫入門＋路由＋封條；audit raise 寫封條
sibling；sibling 不被當文章載入；new 禁文章名含 `.`；hook 守 sibling＋forest；misnamed key fail-loud。
"""

from __future__ import annotations

import pytest
import yaml

from dspx.engine.layout import Layout
from dspx.engine import sealed


# ── 封條 helper ────────────────────────────────────────────────────────

def test_sealed_roundtrip_is_fixpoint(tmp_path):
    p = tmp_path / "x.audit.yaml"
    items = [{"id": "F1", "finding": "多\n行\n內容", "targets": ["a/x"]}]
    sealed.write_sealed(p, kind="audit", scope="doc:x", revision=1, list_key="findings", items=items)
    rev, got = sealed.load_sealed(p, list_key="findings", error_cls=ValueError)
    assert rev == 1 and got == items
    first = p.read_text(encoding="utf-8")
    sealed.write_sealed(p, kind="audit", scope="doc:x", revision=1, list_key="findings", items=got)
    assert p.read_text(encoding="utf-8") == first          # 冪等：dump(load(dump))==dump


def test_sealed_tamper_is_caught(tmp_path):
    p = tmp_path / "x.roadmap.yaml"
    sealed.write_sealed(p, kind="roadmap", scope="doc:x", revision=1, list_key="entries",
                        items=[{"id": "R1", "kind": "task", "title": "t", "target": "x"}])
    p.write_text(p.read_text(encoding="utf-8").replace("R1", "R9"), encoding="utf-8")
    with pytest.raises(ValueError):                        # 封條不符 → fail-loud
        sealed.load_sealed(p, list_key="entries", error_cls=ValueError)


def test_sealed_unsealed_old_file_reads_without_verify(tmp_path):
    """向後相容：無 integrity 頭的舊檔照讀（讓 migrate/首 save 自然升級）。"""
    p = tmp_path / "old.roadmap.yaml"
    p.write_text(yaml.safe_dump({"entries": [{"id": "R1"}]}), encoding="utf-8")
    rev, got = sealed.load_sealed(p, list_key="entries", error_cls=ValueError)
    assert got == [{"id": "R1"}]


# ── roadmap add 引擎寫入門（甲案核心）─────────────────────────────────

def test_roadmap_add_routes_to_doc_and_seals(make_project, write_leaf, monkeypatch, capsys):
    from dspx.commands.governance import roadmap as rmcmd
    from dspx.reports.roadmap import doc_roadmap_path
    home = make_project()
    write_leaf(home, "sc/x", concept={"id": "c1", "title": "X", "order": 1})
    monkeypatch.chdir(home.parent)
    assert rmcmd.run(["add", "--kind", "gap", "--title", "補圖", "--target", "sc/x"]) == 0
    layout = Layout(home)
    p = doc_roadmap_path(layout, "sc")                     # target 落在 sc → doc 檔
    assert p == layout.article_roadmap("sc") and p.is_file()   # dossier 案卷內定名檔
    text = p.read_text(encoding="utf-8")
    assert "integrity: sha256:" in text                    # 封條在
    rev, entries = sealed.load_sealed(p, list_key="entries", error_cls=ValueError)
    assert entries[0]["kind"] == "gap" and entries[0]["target"] == "sc/x"


def test_roadmap_add_rejects_bad_target(make_project, write_leaf, monkeypatch):
    from dspx.commands.governance import roadmap as rmcmd
    home = make_project()
    write_leaf(home, "sc/x", concept={"id": "c1", "title": "X", "order": 1})
    monkeypatch.chdir(home.parent)
    assert rmcmd.run(["add", "--kind", "gap", "--title", "t", "--target", "nope/zz"]) == 1


# ── audit raise 寫封條 sibling ─────────────────────────────────────────

def test_audit_doc_file_is_sibling_and_sealed(make_project, write_leaf):
    from dspx.reports.audit import doc_audit_path, load_doc_audit, raise_finding
    home = make_project()
    write_leaf(home, "sc/x", concept={"id": "c1", "title": "X", "order": 1})
    layout = Layout(home)
    store = load_doc_audit(layout, "sc")
    raise_finding(store, face="logic", severity="med", finding="x", targets=["sc/x"])
    store.save()
    p = doc_audit_path(layout, "sc")
    assert p == layout.article_audit("sc") and p.is_file()    # dossier 案卷內定名檔
    assert "integrity: sha256:" in p.read_text(encoding="utf-8")


# ── 防呆：sibling 不當文章、new 禁點、hook 守 ──────────────────────────

def test_sibling_files_not_loaded_as_articles(make_project, write_leaf):
    from dspx.engine.store import store_articles
    home = make_project()
    write_leaf(home, "g/x", concept={"id": "c1", "title": "X", "order": 1})
    (home / "corpus" / "g.audit.yaml").write_text("findings: []\n", encoding="utf-8")
    (home / "corpus" / "g.roadmap.yaml").write_text("entries: []\n", encoding="utf-8")
    layout = Layout(home)
    assert "g.audit" not in layout.articles() and "g.roadmap" not in layout.articles()
    assert "g.audit" not in store_articles(layout)


def test_put_forbids_dot_in_article_name():
    # ★retire-develop-workbench：路徑驗證住 put（唯一建節入口）
    from dspx.commands.corpus.put import validate_section_path
    assert validate_section_path("a.b/intro") is not None   # 首段含點 → 錯
    assert validate_section_path("ab/intro") is None         # 正常


def test_hook_guards_sibling_and_forest():
    from dspx.commands._internal.hook import _is_store_file
    assert _is_store_file("corpus/sc.audit.yaml")            # doc sibling（corpus 父）
    assert _is_store_file("corpus/sc.roadmap.yaml")
    assert _is_store_file("docspec/audit.yaml")              # forest（依名顯式守）
    assert _is_store_file("docspec/roadmap.yaml")
    assert not _is_store_file("docs/x.md")


# ── fable 審查補洞驗證 ──────────────────────────────────────────────────

def test_deleting_integrity_line_is_caught(tmp_path):
    """#10：sealed 檔被刪 integrity 行（想洗白）→ 必驗 mismatch，不再靜默照讀。"""
    p = tmp_path / "x.audit.yaml"
    sealed.write_sealed(p, kind="audit", scope="doc:x", revision=1, list_key="findings",
                        items=[{"id": "F1", "finding": "x", "targets": ["x"]}])
    kept = [ln for ln in p.read_text(encoding="utf-8").splitlines() if "integrity:" not in ln]
    p.write_text("\n".join(kept) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        sealed.load_sealed(p, list_key="findings", error_cls=ValueError, verify=True)


def test_fsck_repairs_corrupted_sealed_audit(make_project, write_leaf, monkeypatch, capsys):
    """#1：store fsck --accept 現在真的會重封壞掉的治理檔（以前是死路）。"""
    from dspx.commands.corpus import store as store_cmd
    from dspx.reports.audit import doc_audit_path, load_doc_audit, raise_finding
    home = make_project()
    write_leaf(home, "sc/x", concept={"id": "c1", "title": "X", "order": 1})
    layout = Layout(home)
    st = load_doc_audit(layout, "sc")
    raise_finding(st, face="logic", severity="med", finding="x", targets=["sc/x"])
    st.save()
    p = doc_audit_path(layout, "sc")
    p.write_text(p.read_text(encoding="utf-8").replace("severity: med", "severity: high"),
                 encoding="utf-8")                            # 手改 → 破封條
    monkeypatch.chdir(home.parent)
    assert store_cmd.run(["fsck", "sc"]) == 1                 # 未 --accept：抓到、非零
    assert store_cmd.run(["fsck", "sc", "--accept"]) == 0     # --accept：重封成功（不再死路）
    load_doc_audit(layout, "sc")                              # 重封後可正常載入（不 raise）
