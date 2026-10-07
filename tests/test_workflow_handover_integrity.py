"""Synthetic CLI handover/roadmap contracts; reads must not mutate project state."""
import datetime
import json
import os

import pytest

from test_software_archive import proj, _change, code
from test_freeze_and_baseline import doc, _write_prose
from dspx.commands.governance import handover, ruling, decision, roadmap
from dspx.commands.deliverable import freeze, render
from dspx.engine import handover as ho, governance as gv, roadmap_v2 as rv
from dspx.engine.layout import Layout
from dspx.engine.model import load_project
from dspx.engine.software import io


def _json(capsys):
    capsys.readouterr()
    assert handover.run(['--json']) == 0
    return json.loads(capsys.readouterr().out)


def _bytes(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('change', ['ruling', 'evidence', 'roadmap', 'spec'])
def test_same_day_managed_change_makes_handover_stale(proj, capsys, change):
    _change('fix', run=False)
    assert ruling.run(['add', '--quote', 'Begin']) == 0
    assert handover.run(['write', '--next', 'Resume the planned task']) == 0
    current = _json(capsys)
    assert current['freshness']['status'] == 'current'
    assert datetime.datetime.fromisoformat(current['note']['written-at']).utcoffset() is not None
    if change == 'ruling':
        assert ruling.run(['add', '--quote', 'Updated direction']) == 0
    elif change == 'evidence':
        assert code('evidence', 'run', 'fix', '1') == 0
    elif change == 'roadmap':
        assert roadmap.run(['add', '--title', 'Implementation', '--ref', 'swc:fix']) == 0
    else:
        assert code('change', 'delta', 'fix', '--capability', 'entry', '--op', 'modify-requirement',
                    '--ref', 'R2', '--statement', 'It MUST fit differently.') == 0
    stale = _json(capsys)
    assert stale['freshness']['status'] == 'stale'
    assert stale['note']['next'] == ['Resume the planned task']
    assert handover.run([]) == 0
    output = capsys.readouterr()
    assert 'artispec roadmap' in output.out + output.err
    assert handover.run(['write', '--next', 'Updated next step']) == 0
    assert _json(capsys)['freshness']['status'] == 'current'


def test_handover_read_mtime_and_unmanaged_files_do_not_change_freshness(proj, capsys, monkeypatch):
    assert ruling.run(['add', '--quote', 'Begin']) == 0
    assert handover.run(['write', '--done', 'Prepared', '--next', 'Continue']) == 0
    before = _bytes(proj.planning_home)
    for path in proj.planning_home.rglob('*.yaml'):
        os.utime(path, (1000000000, 1000000000))
    (proj.project_root / 'app/src/entry.py').write_text('X = 99\n', encoding='utf-8')
    cache = proj.project_root / 'preview.pdf'
    cache.write_bytes(b'not a real export')
    import subprocess
    def forbidden(*args, **kwargs):
        raise AssertionError('handover must not execute tests or external commands')
    monkeypatch.setattr(subprocess, 'run', forbidden)
    assert _json(capsys)['freshness']['status'] == 'current'
    assert _json(capsys)['freshness']['status'] == 'current'
    assert _bytes(proj.planning_home) == before


def test_legacy_handover_retains_contents_and_reports_unknown(proj, capsys):
    assert handover.run(['write', '--next', 'Original next step']) == 0
    note = ho.load(proj)
    legacy = {k: v for k, v in note.items() if k in (*ho.FIELDS, 'written-by', 'written-at')}
    ho.path(proj).write_text(gv.dump_record('handover', legacy), encoding='utf-8')
    before = ho.path(proj).read_bytes()
    result = _json(capsys)
    assert result['freshness']['status'] == 'unknown'
    assert result['note']['next'] == ['Original next step']
    assert ho.path(proj).read_bytes() == before
    assert handover.run(['write', '--next', 'Reviewed original next step']) == 0
    assert _json(capsys)['freshness']['status'] == 'current'


def test_unreadable_managed_record_reports_unknown_not_current(proj, capsys, monkeypatch):
    assert handover.run(['write', '--next', 'Resume']) == 0
    from pathlib import Path
    original = Path.read_bytes
    def denied(path):
        if path == io.config_path(proj):
            raise PermissionError('synthetic unreadable managed record')
        return original(path)
    monkeypatch.setattr(Path, 'read_bytes', denied)
    result = _json(capsys)
    assert result['freshness']['status'] == 'unknown'
    assert result['note']['next'] == ['Resume']


def test_managed_document_text_changes_handover(doc, capsys):
    layout = Layout(doc)
    _write_prose(doc)
    assert handover.run(['write', '--next', 'Freeze document']) == 0
    assert _json(capsys)['freshness']['status'] == 'current'
    _write_prose(doc, 'A revised working document.')
    assert _json(capsys)['freshness']['status'] == 'stale'
    assert ho.load(layout)['next'] == ['Freeze document']


@pytest.mark.parametrize('condition', ['plain', 'decision-only'])
def test_unlinked_small_work_can_be_manually_closed(proj, condition):
    assert ruling.run(['add', '--quote', 'Do the small task']) == 0
    args = ['add', '--title', 'Small task']
    if condition == 'decision-only':
        assert decision.run(['add', '--title', 'constraint', '--statement', 'Use this style',
                             '--based-on', 'RL-claude-1']) == 0
        assert decision.run(['activate', 'D-claude-1']) == 0
        args += ['--ref', 'gov:D-claude-1']
    assert roadmap.run(args) == 0
    assert roadmap.run(['done', 'W-claude-1', '--note', 'Completed the small task']) == 0
    assert rv.view(proj, [])['unassigned'][0]['status'] == 'done'


def test_parent_and_previous_close_use_current_child_conditions(proj):
    assert ruling.run(['add', '--quote', 'Begin']) == 0
    assert roadmap.run(['add', '--title', 'Parent']) == 0
    assert roadmap.run(['done', 'W-claude-1', '--note', 'Originally small']) == 0
    assert roadmap.run(['add', '--title', 'Child', '--parent', 'W-claude-1']) == 0
    assert rv.view(proj, [])['unassigned'][0]['status'] != 'done'
    assert roadmap.run(['done', 'W-claude-1', '--note', 'Force parent']) == 1
    assert roadmap.run(['done', 'W-claude-2', '--note', 'Finished child']) == 0
    assert rv.view(proj, [])['unassigned'][0]['status'] == 'done'


def test_previously_closed_work_gains_software_link(proj):
    assert ruling.run(['add', '--quote', 'Begin']) == 0
    assert roadmap.run(['add', '--title', 'Originally small']) == 0
    assert roadmap.run(['done', 'W-claude-1', '--note', 'Done']) == 0
    _change('fix', run=False)
    assert roadmap.run(['link', 'W-claude-1', '--ref', 'swc:fix']) == 0
    assert rv.view(proj, [])['unassigned'][0]['status'] != 'done'


def test_roadmap_text_and_json_expose_failure_and_parent_reason(proj, capsys):
    _change('fix', run=False)
    assert ruling.run(['add', '--quote', 'Begin']) == 0
    assert roadmap.run(['add', '--title', 'Parent']) == 0
    assert roadmap.run(['add', '--title', 'Child', '--parent', 'W-claude-1', '--ref', 'swc:fix']) == 0
    test_file = proj.project_root / 'app/tests/test_entry.py'
    test_file.write_text(test_file.read_text(encoding='utf-8').replace('assert True', 'assert False'), encoding='utf-8')
    assert code('testplan', 'sign', 'fix', '--by', 'gemini') == 0
    assert code('evidence', 'run', 'fix', '1') == 1
    before = _bytes(proj.planning_home)
    capsys.readouterr()
    assert roadmap.run(['--json']) == 0
    view = json.loads(capsys.readouterr().out)
    child = view['children']['W-claude-1'][0]
    assert child['details'] and view['unassigned'][0]['details']
    assert any('fail' in x.lower() or '失敗' in x for x in child['details'])
    assert roadmap.run([]) == 0
    output = capsys.readouterr().out
    for reason in child['details']:
        assert reason in output
    assert 'artispec code' in output
    assert _bytes(proj.planning_home) == before


def test_roadmap_text_names_blocking_prerequisite(proj, capsys):
    assert ruling.run(['add', '--quote', 'Begin']) == 0
    assert roadmap.run(['add', '--title', 'First']) == 0
    assert roadmap.run(['add', '--title', 'Second', '--depends-on', 'W-claude-1']) == 0
    capsys.readouterr()
    assert roadmap.run(['--json']) == 0
    second = json.loads(capsys.readouterr().out)['unassigned'][1]
    assert second['status'] == 'blocked'
    assert roadmap.run([]) == 0
    output = capsys.readouterr().out
    assert second['blocked-because'] in output
    assert 'W-claude-1' in second['blocked-because']


def test_current_frozen_document_is_done_but_section_does_not_require_freeze(doc):
    layout = Layout(doc)
    assert ruling.run(['add', '--quote', 'Write guide']) == 0
    _write_prose(doc)
    assert render.run(['g']) == 0
    assert roadmap.run(['add', '--title', 'Section', '--ref', 'doc:g/x']) == 0
    assert roadmap.run(['add', '--title', 'Delivery', '--ref', 'doc:g']) == 0
    rows = rv.view(layout, load_project(layout))['unassigned']
    assert rows[0]['status'] == 'done' and rows[1]['status'] != 'done'
    assert rows[1]['details']
    assert freeze.run(['g']) == 0
    assert rv.view(layout, load_project(layout))['unassigned'][1]['status'] == 'done'


@pytest.mark.parametrize('language', ['zh-TW', 'en'])
def test_generated_instructions_reuse_roadmap_and_preserve_owner_rules(tmp_path, monkeypatch, language):
    from dspx.commands.maintenance import init
    monkeypatch.chdir(tmp_path)
    rules = tmp_path / 'AGENTS.md'
    prefix, suffix = '# Owner rule\nKeep real data private.\n', '\nOwner footer stays.\n'
    rules.write_text(prefix, encoding='utf-8')
    args = ['--tool', 'codex', '--agents-md', '--lang', language, '--no-tex-hint', '--no-update-check']
    assert init.run(args) == 0
    rules.write_text(rules.read_text(encoding='utf-8') + suffix, encoding='utf-8')
    assert init.run(args) == 0
    text = rules.read_text(encoding='utf-8')
    assert text.startswith(prefix) and text.endswith(suffix)
    assert text.count('<!-- docspec:begin -->') == 1
    assert 'artispec roadmap add' in text and 'artispec roadmap link' in text
    assert 'artispec handover write' in text and 'artispec info add' in text
    assert 'artispec brief' not in text and 'docspec brief' not in text and 'dspx-govern' not in text
    if language == 'zh-TW':
        assert '有就沿用' in text and '沒有才' in text and '講得不清楚' in text
    else:
        assert 'reuse' in text and 'Only when none exists' in text and 'If they were unclear' in text


def test_s4_mechanical_handoff_exposes_empty_work_failure_and_changed_note(proj, capsys):
    """Fresh-context agents are E11; this tests S4's mechanically available facts."""
    assert ruling.run(['add', '--quote', 'Begin synthetic work']) == 0
    assert rv.view(proj, [])['unassigned'] == []
    assert handover.run(['write', '--next', 'Register and validate the implementation']) == 0
    assert _json(capsys)['freshness']['status'] == 'current'
    _change('fix', run=False)
    assert roadmap.run(['add', '--title', 'Implement behavior', '--ref', 'swc:fix']) == 0
    test_file = proj.project_root / 'app/tests/test_entry.py'
    test_file.write_text(test_file.read_text(encoding='utf-8').replace('assert True', 'assert False'), encoding='utf-8')
    assert code('testplan', 'sign', 'fix', '--by', 'gemini') == 0
    assert code('evidence', 'run', 'fix', '1') == 1
    view = rv.view(proj, [])
    assert view['unassigned'][0]['status'] != 'done'
    assert any('fail' in reason.lower() for reason in view['unassigned'][0]['details'])
    note = _json(capsys)
    assert note['freshness']['status'] == 'stale'
    assert 'artispec roadmap' in note['freshness']['next']
    assert handover.run(['write', '--in-progress', 'Fix the failing planned test', '--next',
                         'Rerun evidence then check archive readiness']) == 0
    fresh = _json(capsys)
    assert fresh['freshness']['status'] == 'current'
    assert fresh['note']['next'] == ['Rerun evidence then check archive readiness']


@pytest.mark.parametrize('article_asset', [False, True])
def test_document_source_asset_change_marks_handover_stale(doc, capsys, article_asset):
    layout = Layout(doc)
    folder = layout.docs_assets_dir('g' if article_asset else None)
    folder.mkdir(parents=True, exist_ok=True)
    asset = folder / 'workflow.drawio'
    asset.write_text('<mxfile>old source</mxfile>', encoding='utf-8')
    assert handover.run(['write', '--next', 'Review illustration']) == 0
    assert _json(capsys)['freshness']['status'] == 'current'
    asset.write_text('<mxfile>updated source</mxfile>', encoding='utf-8')
    assert _json(capsys)['freshness']['status'] == 'stale'


def test_invalid_governance_does_not_hide_handover_note(proj, capsys):
    assert ruling.run(['add', '--quote', 'Original direction']) == 0
    assert handover.run(['write', '--next', 'Keep this useful next step']) == 0
    path = gv.record_path(proj, 'ruling', 'RL-claude-1')
    path.write_text(path.read_text(encoding='utf-8').replace('Original direction', 'Unsealed edit'), encoding='utf-8')
    result = _json(capsys)
    assert result['freshness']['status'] == 'unknown'
    assert result['note']['next'] == ['Keep this useful next step']


def test_many_documents_are_read_without_scanning_external_code(proj, write_leaf, capsys, monkeypatch):
    for i in range(24):
        write_leaf(proj.planning_home, f'guide{i}/section',
                   concept={'id': f'c-{i}', 'title': f'Guide {i}', 'order': 1})
    external = proj.project_root / 'app'
    (external / 'untouched_large_data.bin').write_bytes(b'x' * 8192)
    original_walk = os.walk
    visited = []
    def scoped_walk(top, *args, **kwargs):
        from pathlib import Path
        root = Path(top).resolve()
        assert not root.is_relative_to(external.resolve())
        visited.append(root)
        return original_walk(top, *args, **kwargs)
    monkeypatch.setattr(os, 'walk', scoped_walk)
    import subprocess
    def no_execution(*args, **kwargs):
        raise AssertionError('handover must not execute external tools')
    monkeypatch.setattr(subprocess, 'run', no_execution)
    assert handover.run(['write', '--next', 'Review the document set']) == 0
    assert _json(capsys)['freshness']['status'] == 'current'
    assert len(visited) < 100


@pytest.mark.parametrize('missing', ['format', 'sections', 'article', 'nonmapping'])
@pytest.mark.parametrize('storage', ['dossier', 'flat'])
def test_malformed_corpus_cannot_establish_current_handover(doc, capsys, missing, storage):
    import yaml
    from dspx.engine.model import ModelError
    path = doc / 'corpus/g/article.yaml'
    contents = yaml.safe_load(path.read_text(encoding='utf-8'))
    if storage == 'flat':
        path.unlink()
        path = doc / 'corpus/g.yaml'
    if missing == 'nonmapping':
        contents = ['not', 'an', 'article']
    else:
        contents.pop(missing)
    path.write_text(yaml.safe_dump(contents), encoding='utf-8')
    with pytest.raises(ModelError):
        load_project(Layout(doc))
    assert handover.run(['write', '--next', 'Repair the malformed document']) == 0
    result = _json(capsys)
    assert result['freshness']['status'] == 'unknown'
    assert result['note']['next'] == ['Repair the malformed document']
