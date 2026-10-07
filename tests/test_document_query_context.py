"""Document reads select official or one explicit draft; queries never manufacture a preview."""

import json
import subprocess

import pytest
import yaml

from dspx.commands.change import change
from dspx.commands.corpus import get, put
from dspx.commands.deliverable import render
from dspx.commands.projection import instructions
from dspx.commands.query import check, diff, find
from dspx.engine import change as chg
from dspx.engine.layout import Layout


def _bytes(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file()}


def _call(command, args):
    try:
        return command.run(args)
    except SystemExit as exc:
        return exc.code


def _inject(path, section, prose):
    lines = path.read_text(encoding="utf-8").splitlines()
    marker = f"<!-- dspx:section {section} -->"
    at = lines.index(marker) + 1
    while at < len(lines) and not lines[at].startswith("#"):
        at += 1
    assert at < len(lines)
    lines[at + 1:at + 1] = ["", prose, ""]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _stage(layout, capsys, cid="edit-manual", title="Draft X", framing="DRAFT_SOURCE"):
    assert change.run(["new", cid, "--publish", "advisory", "--why", "Synthetic review"]) == 0
    assert change.run(["add-target", cid, "guide/x", "--action", "revise"]) == 0
    capsys.readouterr()
    assert get.run(["guide/x", "concept", "--official"]) == 0
    concept = yaml.safe_load(capsys.readouterr().out)
    concept.update(title=title, concept=framing)
    source = layout.project_root / f"{cid}-concept-input.yaml"
    source.write_text(yaml.safe_dump(concept, allow_unicode=True), encoding="utf-8")
    assert put.run(["guide/x", "concept", str(source), "--change", cid]) == 0
    material = layout.project_root / f"{cid}-material-input.md"
    material.write_text("## fact {#draft-fact}\nDRAFT_MATERIAL 40 km/h\n", encoding="utf-8")
    assert put.run(["guide/x", "material", str(material), "--change", cid]) == 0


@pytest.fixture
def context_project(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    write_leaf(home, "guide/x", concept={"id": "c-x", "title": "X", "order": 1,
                                          "concept": "OFFICIAL_SOURCE", "brief": {"audience": "operator", "depth": "short", "breadth": "one task"}},
               material="## fact {#official-fact}\nOFFICIAL_MATERIAL 25 km/h\n")
    write_leaf(home, "guide/keep", concept={"id": "c-keep", "title": "Keep", "order": 2,
                                             "concept": "UNTOUCHED_SOURCE"})
    write_leaf(home, "other/y", concept={"id": "c-other", "title": "Other", "order": 1,
                                          "concept": "OTHER_SOURCE"})
    monkeypatch.chdir(home.parent)
    layout = Layout(home)
    assert render.run(["guide"]) == 0
    assert render.run(["other"]) == 0
    _inject(layout.docs_latest("guide"), "guide/x", "OFFICIAL_PROSE 25 km/h")
    _inject(layout.docs_latest("guide"), "guide/keep", "UNTOUCHED_PROSE")
    _inject(layout.docs_latest("other"), "other/y", "OTHER_PROSE")
    assert render.run(["guide"]) == 0
    assert render.run(["other"]) == 0
    _stage(layout, capsys)
    assert render.run(["guide", "--change", "edit-manual"]) == 0
    preview = chg.preview_dir(chg.load_change(layout, "edit-manual").dir) / "guide_latest.md"
    preview.write_text(preview.read_text(encoding="utf-8").replace("OFFICIAL_PROSE 25 km/h", "DRAFT_PROSE 40 km/h"),
                       encoding="utf-8", newline="\n")
    assert render.run(["guide", "--change", "edit-manual"]) == 0
    capsys.readouterr()
    return layout


@pytest.mark.parametrize("category,official,draft", [("concept", "OFFICIAL_SOURCE", "DRAFT_SOURCE"),
                                                    ("material", "OFFICIAL_MATERIAL", "DRAFT_MATERIAL")])
def test_get_defaults_to_official_and_explicit_change_reads_staging(context_project, capsys, category, official, draft):
    before = _bytes(context_project.project_root)
    assert get.run(["guide/x", category]) == 0
    default = capsys.readouterr()
    assert official in default.out and draft not in default.out
    assert "official" in (default.out + default.err).lower()
    assert get.run(["guide/x", category, "--official"]) == 0
    assert capsys.readouterr().out == default.out
    assert get.run(["guide/x", category, "--change", "edit-manual"]) == 0
    staged = capsys.readouterr()
    assert draft in staged.out and official not in staged.out
    assert "edit-manual" in staged.out + staged.err
    if category == "concept":
        assert yaml.safe_load(default.out)["id"] == yaml.safe_load(staged.out)["id"] == "c-x"
    assert _bytes(context_project.project_root) == before


def test_get_official_and_change_conflict_is_an_error_without_writing(context_project, capsys):
    before = _bytes(context_project.project_root)
    assert _call(get, ["guide/x", "concept", "--official", "--change", "edit-manual"]) != 0
    assert capsys.readouterr().err
    assert _bytes(context_project.project_root) == before


def test_multiple_active_changes_do_not_change_the_official_default(context_project, capsys):
    _stage(context_project, capsys, cid="alternative-manual", framing="ALTERNATIVE_SOURCE")
    capsys.readouterr()
    assert get.run(["guide/x", "concept"]) == 0
    assert yaml.safe_load(capsys.readouterr().out)["concept"] == "OFFICIAL_SOURCE"
    assert get.run(["guide/x", "concept", "--change", "alternative-manual"]) == 0
    assert yaml.safe_load(capsys.readouterr().out)["concept"] == "ALTERNATIVE_SOURCE"


def test_explicit_change_preserves_unstaged_official_records(context_project, capsys):
    assert get.run(["guide/keep", "concept", "--change", "edit-manual"]) == 0
    assert yaml.safe_load(capsys.readouterr().out)["concept"] == "UNTOUCHED_SOURCE"
    assert _call(find, ["UNTOUCHED_SOURCE", "--in", "concept", "--change", "edit-manual", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert any(h["section"] == "guide/keep" for h in result["hits"])


@pytest.mark.parametrize("selector", [[], ["--change", "edit-manual"]])
def test_factcheck_projection_uses_one_content_context(context_project, capsys, selector):
    assert _call(instructions, ["factcheck", "guide/x", "--json", *selector]) == 0
    payload = json.loads(capsys.readouterr().out)
    staged = bool(selector)
    assert payload["context"] == {"kind": "change" if staged else "official", "change": "edit-manual" if staged else None}
    reads = json.dumps(payload["reads"], ensure_ascii=False)
    assert ("DRAFT_SOURCE" if staged else "OFFICIAL_SOURCE") in reads
    assert ("DRAFT_PROSE" if staged else "OFFICIAL_PROSE") in reads
    assert ("OFFICIAL_SOURCE" if staged else "DRAFT_SOURCE") not in reads
    assert ("OFFICIAL_PROSE" if staged else "DRAFT_PROSE") not in reads


@pytest.mark.parametrize("face,query", [("concept", "DRAFT_SOURCE"), ("material", "DRAFT_MATERIAL"), ("prose", "DRAFT_PROSE")])
def test_find_searches_selected_union_instead_of_the_other_version(context_project, capsys, face, query):
    assert _call(find, [query, "--in", face, "--json", "--change", "edit-manual"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["context"] == {"kind": "change", "change": "edit-manual"}
    assert any(query in row["snippet"] and row["section"] == "guide/x" for row in payload["hits"])
    assert find.run([query, "--in", face, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["hits"] == []


def test_prose_hit_location_points_to_the_actual_selected_file(context_project, capsys):
    assert _call(find, ["DRAFT_PROSE", "--in", "prose", "--json", "--change", "edit-manual"]) == 0
    selected = json.loads(capsys.readouterr().out)
    hit = next(row for row in selected["hits"] if row["section"] == "guide/x")
    preview = chg.preview_dir(chg.load_change(context_project, "edit-manual").dir) / "guide_latest.md"
    assert preview.relative_to(context_project.project_root).as_posix() in hit["loc"]
    assert " L" in hit["loc"]
    assert find.run(["OFFICIAL_PROSE", "--in", "prose", "--json"]) == 0
    official = json.loads(capsys.readouterr().out)
    hit = next(row for row in official["hits"] if row["section"] == "guide/x")
    assert context_project.docs_latest("guide").relative_to(context_project.project_root).as_posix() in hit["loc"]
    assert "/preview/" not in hit["loc"]


def test_number_query_reads_selected_preview_and_retains_unaffected_articles(context_project, capsys):
    assert _call(find, ["--numbers", "--change", "edit-manual", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["context"] == {"kind": "change", "change": "edit-manual"}
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "40" in serialized and "25" not in serialized
    assert "edit-manual" in serialized


def test_diff_reads_preview_drift_and_leaves_official_drift_separate(context_project, capsys):
    preview = chg.preview_dir(chg.load_change(context_project, "edit-manual").dir) / "guide_latest.md"
    preview.write_text(preview.read_text(encoding="utf-8").replace("DRAFT_PROSE", "HAND_EDITED_DRAFT"), encoding="utf-8")
    before = _bytes(context_project.project_root)
    assert _call(diff, ["guide", "--change", "edit-manual", "--json"]) == 0
    selected = json.loads(capsys.readouterr().out)
    assert selected["context"] == {"kind": "change", "change": "edit-manual"}
    assert any(row["section"] == "guide/x" for row in selected["drift"])
    assert diff.run(["guide", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["drift"] == []
    assert _bytes(context_project.project_root) == before


@pytest.mark.parametrize("problem", ["missing", "stale"])
@pytest.mark.parametrize("command,args", [(instructions, ["factcheck", "guide/x", "--json"]),
                                          (find, ["PROSE", "--in", "prose", "--json"]),
                                          (find, ["--numbers", "--json"]),
                                          (diff, ["guide", "--json"])])
def test_missing_or_stale_preview_never_uses_official_prose_as_a_fresh_draft(context_project, capsys, problem, command, args):
    cdir = chg.load_change(context_project, "edit-manual").dir
    preview = chg.preview_dir(cdir) / "guide_latest.md"
    if problem == "missing":
        preview.unlink()
    else:
        capsys.readouterr()
        assert get.run(["guide/x", "concept", "--change", "edit-manual"]) == 0
        concept = yaml.safe_load(capsys.readouterr().out)
        concept["concept"] = "NEWER_DRAFT_SOURCE"
        source = context_project.project_root / "newer-draft.yaml"
        source.write_text(yaml.safe_dump(concept), encoding="utf-8")
        assert put.run(["guide/x", "concept", str(source), "--change", "edit-manual"]) == 0
    capsys.readouterr()
    before = _bytes(context_project.project_root)
    result = _call(command, [*args, "--change", "edit-manual"])
    assert result == (0 if command is instructions else 1)
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["context"] == {"kind": "change", "change": "edit-manual"}
    assert payload["diagnostics"]
    diagnostics = json.dumps(payload["diagnostics"], ensure_ascii=False).lower()
    assert "render" in diagnostics and problem in diagnostics
    if command is instructions:
        assert "OFFICIAL_PROSE" not in json.dumps(payload["reads"], ensure_ascii=False)
    elif command is find:
        assert "OFFICIAL_PROSE" not in json.dumps(payload.get("hits", payload.get("groups", [])), ensure_ascii=False)
    assert _bytes(context_project.project_root) == before


def test_check_uses_staged_source_but_always_checks_other_articles(context_project, write_leaf, capsys):
    # A correctly sealed corpus can contain invalid relationships; scope must not hide them.
    write_leaf.edit(context_project.planning_home, "other/y", concept={"governed-by": ["missing-authority"]})
    capsys.readouterr()
    before = _bytes(context_project.project_root)
    assert _call(check, ["guide", "--change", "edit-manual", "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["context"] == {"kind": "change", "change": "edit-manual"}
    assert any("missing-authority" in err for err in payload["errors"])
    assert all(section.startswith("guide/") for section in payload["index"]["sections"])
    assert _bytes(context_project.project_root) == before


def test_check_union_detects_staged_duplicate_id_and_official_remains_valid(context_project, capsys):
    assert change.run(["add-target", "edit-manual", "guide/new", "--action", "create"]) == 0
    capsys.readouterr()
    assert get.run(["guide/keep", "concept", "--official"]) == 0
    concept = yaml.safe_load(capsys.readouterr().out)
    concept.update(title="Duplicate staged ID", order=3)
    source = context_project.project_root / "duplicate-id.yaml"
    source.write_text(yaml.safe_dump(concept), encoding="utf-8")
    # Normal put correctly refuses known collisions, so write a sealed synthetic
    # staging record through the same store serializer to exercise read validation.
    from dspx.engine import store
    from dspx.engine.schema import load_schema
    path = chg.staging_store_path(chg.load_change(context_project, "edit-manual").dir, "guide")
    article = store.load_article(path, verify=True)
    rec = article.record_by_path("guide/new")
    rec.concept = concept
    store.save_article_to(path, article, load_schema())
    capsys.readouterr()
    assert _call(check, ["--change", "edit-manual", "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert any("c-keep" in err for err in payload["errors"])
    assert check.run(["--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True


@pytest.mark.parametrize("location", ["official", "pending-create"])
def test_check_does_not_hide_leaf_records_without_a_concept(context_project, capsys, location):
    if location == "pending-create":
        assert change.run(["add-target", "edit-manual", "guide/pending", "--action", "create"]) == 0
        section, selector = "guide/pending", ["--change", "edit-manual"]
    else:
        from dspx.engine import store
        from dspx.engine.schema import load_schema
        path = context_project.article_store("guide")
        article = store.load_article(path, verify=True)
        article.record_by_path("guide/keep").concept = None
        store.save_article_to(path, article, load_schema())
        section, selector = "guide/keep", []
    capsys.readouterr()
    before = _bytes(context_project.project_root)
    assert _call(check, ["guide", "--json", *selector]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is False
    assert any(section in error for error in result["errors"])
    assert _bytes(context_project.project_root) == before


@pytest.mark.parametrize("command,args", [(get, ["guide/x", "concept"]),
                                          (instructions, ["factcheck", "guide/x", "--json"]),
                                          (find, ["DRAFT_SOURCE", "--in", "concept", "--json"]),
                                          (check, ["guide", "--json"]), (diff, ["guide", "--json"])])
def test_unknown_change_is_an_error_not_a_fallback_to_official(context_project, capsys, command, args):
    before = _bytes(context_project.project_root)
    assert _call(command, [*args, "--change", "does-not-exist"]) != 0
    captured = capsys.readouterr()
    assert "does-not-exist" in captured.out + captured.err
    assert _bytes(context_project.project_root) == before


@pytest.mark.parametrize("command,args", [(get, ["guide/x", "concept"]),
                                          (instructions, ["factcheck", "guide/x", "--json"]),
                                          (find, ["DRAFT_SOURCE", "--in", "concept", "--json"]),
                                          (check, ["guide", "--json"]), (diff, ["guide", "--json"])])
def test_explicit_context_queries_do_not_render_execute_or_write(context_project, monkeypatch, capsys, command, args):
    before = _bytes(context_project.project_root)
    def forbidden(*args, **kwargs):
        raise AssertionError("Document queries must not render or execute an external command")
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(render, "run", forbidden)
    assert _call(command, [*args, "--change", "edit-manual"]) == 0
    capsys.readouterr()
    assert _bytes(context_project.project_root) == before


@pytest.mark.parametrize("storage", ["official", "staging"])
@pytest.mark.parametrize("command,args", [(get, ["guide/x", "concept"]),
                                          (instructions, ["factcheck", "guide/x", "--json"]),
                                          (find, ["SOURCE", "--in", "concept", "--json"]),
                                          (check, ["guide", "--json"]), (diff, ["guide", "--json"])])
def test_unreadable_selected_store_is_an_error_and_is_not_resealed(context_project, capsys, storage, command, args):
    if storage == "official":
        path = context_project.article_store("guide")
        old, new = "OFFICIAL_SOURCE", "ALTERED_OFFICIAL_SOURCE"
    else:
        path = chg.staging_store_path(chg.load_change(context_project, "edit-manual").dir, "guide")
        old, new = "DRAFT_SOURCE", "ALTERED_DRAFT_SOURCE"
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")
    before = _bytes(context_project.project_root)
    capsys.readouterr()
    assert _call(command, [*args, "--change", "edit-manual"]) != 0
    captured = capsys.readouterr()
    assert captured.out or captured.err
    assert path.name in captured.out + captured.err
    assert _bytes(context_project.project_root) == before


def test_staged_tombstone_hides_official_content_and_does_not_create_a_false_dead_target(context_project, capsys):
    from dspx.engine import store
    from dspx.engine.schema import load_schema
    assert change.run(["add-target", "edit-manual", "guide/keep", "--action", "retire"]) == 0
    path = chg.staging_store_path(chg.load_change(context_project, "edit-manual").dir, "guide")
    article = store.load_article(path, verify=True)
    article.records = [store.SectionRecord(path=r.path, kind="tombstone") if r.path == "guide/keep" else r
                       for r in article.records]
    store.save_article_to(path, article, load_schema())
    capsys.readouterr()
    before = _bytes(context_project.project_root)
    assert get.run(["guide/keep", "concept", "--change", "edit-manual"]) == 1
    removed = capsys.readouterr()
    assert "UNTOUCHED_SOURCE" not in removed.out
    assert "removed" in (removed.out + removed.err).lower()
    assert _call(find, ["UNTOUCHED_SOURCE", "--in", "concept", "--json", "--change", "edit-manual"]) == 0
    assert json.loads(capsys.readouterr().out)["hits"] == []
    assert find.run(["UNTOUCHED_SOURCE", "--in", "concept", "--json"]) == 0
    assert any(h["section"] == "guide/keep" for h in json.loads(capsys.readouterr().out)["hits"])
    assert _call(check, ["--json", "--change", "edit-manual"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert "guide/keep" not in result["index"]["sections"]
    assert _bytes(context_project.project_root) == before


def test_staged_new_article_is_visible_before_official_corpus_exists(context_project, capsys):
    assert change.run(["add-target", "edit-manual", "newbook/x", "--action", "create"]) == 0
    source = context_project.project_root / "newbook-input.yaml"
    source.write_text(yaml.safe_dump({"id": "c-newbook", "title": "New X", "order": 1,
                                      "status": "draft", "concept": "NEW_ARTICLE_SOURCE", "brief": {}}), encoding="utf-8")
    assert put.run(["newbook/x", "concept", str(source), "--change", "edit-manual"]) == 0
    assert render.run(["newbook", "--change", "edit-manual"]) == 0
    preview = chg.preview_dir(chg.load_change(context_project, "edit-manual").dir) / "newbook_latest.md"
    _inject(preview, "newbook/x", "NEW_ARTICLE_PROSE")
    assert render.run(["newbook", "--change", "edit-manual"]) == 0
    capsys.readouterr()
    before = _bytes(context_project.project_root)
    assert not context_project.article_store("newbook").exists()
    assert _call(instructions, ["factcheck", "newbook/x", "--change", "edit-manual", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert "NEW_ARTICLE_SOURCE" in json.dumps(result["reads"])
    assert "NEW_ARTICLE_PROSE" in json.dumps(result["reads"])
    assert _call(check, ["newbook", "--change", "edit-manual", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert "newbook/x" in result["index"]["sections"]
    assert check.run(["--json"]) == 0
    assert "newbook/x" not in json.loads(capsys.readouterr().out)["index"]["sections"]
    assert _bytes(context_project.project_root) == before


def test_staged_group_names_and_order_are_used_by_the_document_map(context_project, write_leaf, capsys):
    for section, cid in (("guide/a/first", "c-first"), ("guide/z/second", "c-second")):
        write_leaf(context_project.planning_home, section, concept={"id": cid, "title": section.rsplit("/", 1)[-1], "order": 1})
    for group, title, order in (("guide/a", "STAGED_GROUP_A", 9), ("guide/z", "STAGED_GROUP_Z", 1)):
        assert change.run(["add-target", "edit-manual", group, "--action", "create"]) == 0
        source = context_project.project_root / f"{group.rsplit('/', 1)[-1]}-group.yaml"
        source.write_text(yaml.safe_dump({"title": title, "order": order}), encoding="utf-8")
        assert put.run([group, "group", str(source), "--change", "edit-manual"]) == 0
    capsys.readouterr()
    before = _bytes(context_project.project_root)
    assert _call(instructions, ["apply", "guide/x", "--change", "edit-manual", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    groups = [row for row in result["documentMap"] if row["kind"] == "group"]
    assert [row["title"] for row in groups] == ["STAGED_GROUP_Z", "STAGED_GROUP_A"]
    assert [row["order"] for row in groups] == [1, 9]
    assert _bytes(context_project.project_root) == before


def _stage_file(layout, filename, official, staged):
    path = layout.planning_home / filename
    path.write_text(official, encoding="utf-8")
    assert change.run(["add-target", "edit-manual", f"docspec/{filename}", "--action", "revise", "--kind", "file"]) == 0
    cdir = chg.load_change(layout, "edit-manual").dir
    selected = chg.staging_target(cdir, layout, path)
    selected.write_text(staged, encoding="utf-8")
    return path, selected


def test_staged_glossary_writing_guide_and_purpose_are_selected_together(context_project, capsys):
    paths = [_stage_file(context_project, "glossary.yaml",
                         "terms:\n  - {id: term-1, canonical: OFFICIAL_TERM, bucket: standard}\n",
                         "terms:\n  - {id: term-1, canonical: STAGED_TERM, bucket: standard}\n"),
             _stage_file(context_project, "writing-guide.md", "OFFICIAL_WRITING_GUIDE", "STAGED_WRITING_GUIDE"),
             _stage_file(context_project, "config.yaml", "language: zh-TW\ndocs_layout: per-article\npurpose: OFFICIAL_PURPOSE\n",
                         "language: zh-TW\ndocs_layout: per-article\npurpose: STAGED_PURPOSE\n")]
    capsys.readouterr()
    before = _bytes(context_project.project_root)
    assert _call(instructions, ["apply", "guide/x", "--change", "edit-manual", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["projectPurpose"] == "STAGED_PURPOSE"
    assert result["writingGuide"] == "STAGED_WRITING_GUIDE"
    assert result["glossary"][0]["canonical"] == "STAGED_TERM"
    assert _call(find, ["STAGED_TERM", "--in", "glossary", "--change", "edit-manual", "--json"]) == 0
    assert any("STAGED_TERM" in h["snippet"] for h in json.loads(capsys.readouterr().out)["hits"])
    assert instructions.run(["apply", "guide/x", "--json"]) == 0
    official = json.loads(capsys.readouterr().out)
    assert official["projectPurpose"] == "OFFICIAL_PURPOSE"
    assert official["writingGuide"] == "OFFICIAL_WRITING_GUIDE"
    assert official["glossary"][0]["canonical"] == "OFFICIAL_TERM"
    assert _bytes(context_project.project_root) == before


@pytest.mark.parametrize("doctrine", ["glossary", "purpose"])
def test_legitimate_preview_style_review_uses_staged_doctrine_when_it_is_rerendered(context_project, capsys, doctrine):
    if doctrine == "glossary":
        _stage_file(context_project, "glossary.yaml",
                    "terms:\n  - {id: term-1, canonical: OFFICIAL_TERM, bucket: standard}\n",
                    "terms:\n  - {id: term-1, canonical: STAGED_TERM, bucket: standard}\n")
    else:
        _stage_file(context_project, "config.yaml", "language: zh-TW\ndocs_layout: per-article\npurpose: OFFICIAL_PURPOSE\n",
                    "language: zh-TW\ndocs_layout: per-article\npurpose: STAGED_PURPOSE\n")
    capsys.readouterr()
    official = {p.relative_to(context_project.project_root).as_posix(): p.read_bytes()
                for p in context_project.planning_home.rglob("*")
                if p.is_file() and p.relative_to(context_project.planning_home).parts[0] != "changes"}
    docs = _bytes(context_project.docs_dir)
    before_query = _bytes(context_project.project_root)
    assert _call(instructions, ["factcheck", "guide/x", "--change", "edit-manual", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert any(d["state"] == "stale-style" and d.get("section") == "guide/x" for d in result["diagnostics"])
    assert _bytes(context_project.project_root) == before_query
    assert render.run(["guide", "--change", "edit-manual", "--ack", "guide/x", "--ack", "guide/keep",
                       "--reason", "Reviewed metadata-only synthetic doctrine change; existing prose remains valid"]) == 0
    capsys.readouterr()
    before_query = _bytes(context_project.project_root)
    assert _call(instructions, ["factcheck", "guide/x", "--change", "edit-manual", "--json"]) == 0
    after = json.loads(capsys.readouterr().out)
    assert not any(d.get("section") == "guide/x" and d["state"] == "stale-style" for d in after["diagnostics"])
    assert "DRAFT_PROSE" in json.dumps(after["reads"])
    assert _call(instructions, ["apply", "guide/x", "--change", "edit-manual", "--json"]) == 0
    selected = json.loads(capsys.readouterr().out)
    if doctrine == "glossary":
        assert selected["glossary"][0]["canonical"] == "STAGED_TERM"
    else:
        assert selected["projectPurpose"] == "STAGED_PURPOSE"
    assert _bytes(context_project.project_root) == before_query
    assert all((context_project.project_root / path).read_bytes() == content for path, content in official.items())
    assert _bytes(context_project.docs_dir) == docs


def test_staged_shared_decision_and_governed_parent_use_the_same_union(context_project, capsys):
    assert change.run(["add-target", "edit-manual", "guide/keep", "--action", "revise"]) == 0
    capsys.readouterr()
    assert get.run(["guide/keep", "concept", "--official"]) == 0
    parent = yaml.safe_load(capsys.readouterr().out)
    parent.update(concept="STAGED_PARENT_FRAME", brief={"audience": "staged operator", "depth": "staged detail", "breadth": "one task"})
    source = context_project.project_root / "parent-concept.yaml"
    source.write_text(yaml.safe_dump(parent), encoding="utf-8")
    assert put.run(["guide/keep", "concept", str(source), "--change", "edit-manual"]) == 0
    source = context_project.project_root / "parent-decisions.yaml"
    source.write_text(yaml.safe_dump({"entries": [{"id": "d-parent", "kind": "normative", "status": "accepted", "statement": "STAGED_PARENT_DECISION"}]}), encoding="utf-8")
    assert put.run(["guide/keep", "decisions", str(source), "--change", "edit-manual"]) == 0
    capsys.readouterr()
    assert get.run(["guide/x", "concept", "--change", "edit-manual"]) == 0
    child = yaml.safe_load(capsys.readouterr().out)
    child.update({"governed-by": ["c-keep"], "realizes": ["d-parent"]})
    source = context_project.project_root / "child-concept.yaml"
    source.write_text(yaml.safe_dump(child), encoding="utf-8")
    assert put.run(["guide/x", "concept", str(source), "--change", "edit-manual"]) == 0
    capsys.readouterr()
    before = _bytes(context_project.project_root)
    assert _call(instructions, ["factcheck", "guide/x", "--change", "edit-manual", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert any("STAGED_PARENT_FRAME" in json.dumps(row) for row in result["parentBriefs"])
    assert any("STAGED_PARENT_DECISION" in json.dumps(row) for row in result["ancestorNormative"])
    assert any(row["id"] == "d-parent" and row["statement"] == "STAGED_PARENT_DECISION" for row in result["realized"])
    assert _bytes(context_project.project_root) == before


@pytest.mark.parametrize("command,args", [(get, ["guide/x", "concept"]),
                                          (instructions, ["factcheck", "guide/x", "--json"]),
                                          (find, ["DRAFT_SOURCE", "--in", "concept", "--json"]),
                                          (check, ["guide", "--json"]), (diff, ["guide", "--json"])])
def test_abandoned_change_is_not_accepted_as_a_current_draft_context(context_project, capsys, command, args):
    assert change.run(["archive", "edit-manual", "--abandon", "--reason", "Synthetic alternative discarded"]) == 0
    capsys.readouterr()
    before = _bytes(context_project.project_root)
    assert _call(command, [*args, "--change", "edit-manual"]) != 0
    captured = capsys.readouterr()
    assert "edit-manual" in captured.out + captured.err
    assert _bytes(context_project.project_root) == before
