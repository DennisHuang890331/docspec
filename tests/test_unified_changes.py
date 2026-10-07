"""A shared change surface preserves each domain's storage and completion rules."""

import json
import shutil
import subprocess

import pytest

from test_software_archive import proj, _change, code
from dspx.commands.change import change as change_cmd
from dspx.engine import change as doc_changes, handover
from dspx.engine.schema import load_schema
from dspx.engine.software import changes as software_changes, evidence, archive, io


def _bytes(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob('*') if p.is_file()}


def _document(proj, write_leaf, cid='document-edit'):
    write_leaf(proj.planning_home, 'g/x', concept={'id': 'section-x', 'title': 'X', 'order': 1})
    assert change_cmd.run(['new', cid, '--publish', 'advisory', '--seed', 'section-x',
                           '--why', 'Revise the synthetic document']) == 0
    return doc_changes.load_change(proj, cid)


def _legacy(proj, cid='software-edit'):
    _change(cid, run=False)
    source = software_changes.load_change(proj, cid)['folder']
    target = proj.planning_home / 'software/changes' / cid
    if source != target:
        assert source.resolve().is_relative_to(proj.planning_home.resolve())
        assert target.resolve().is_relative_to(proj.planning_home.resolve())
        assert not target.exists()
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)
    return target


def _query(proj, capsys, monkeypatch, *args):
    before = _bytes(proj.project_root)
    def forbidden(*args, **kwargs):
        raise AssertionError('A shared change query must not execute tests, refresh or write records')
    with monkeypatch.context() as patch:
        patch.setattr(subprocess, 'run', forbidden)
        patch.setattr(evidence, 'refresh', forbidden)
        patch.setattr(evidence, 'run_tests', forbidden)
        patch.setattr(archive, 'plan', forbidden)
        patch.setattr(handover, 'write', forbidden)
        patch.setattr(doc_changes, 'save_change', forbidden)
        patch.setattr(software_changes, 'write_part', forbidden)
        capsys.readouterr()
        assert change_cmd.run([*args, '--json']) == 0
        result = json.loads(capsys.readouterr().out)
        assert change_cmd.run(list(args)) == 0
        output = capsys.readouterr().out
    assert _bytes(proj.project_root) == before
    assert result['schema-version'] == 1
    return result, output


def test_new_software_change_uses_shared_home_without_changing_software_artifacts(proj):
    _change('software-edit', run=False)
    folder = proj.planning_home / 'changes/software-edit'
    assert software_changes.load_change(proj, 'software-edit')['folder'] == folder
    assert {'proposal.yaml', 'design.yaml', 'tests.yaml', 'tasks.yaml', 'specs'} <= {p.name for p in folder.iterdir()}
    assert not (folder / 'change.yaml').exists()
    assert not (proj.planning_home / 'software/changes/software-edit').exists()
    assert io.config_path(proj).is_file() and io.spec_path(proj, 'entry').is_file()


def test_document_change_keeps_its_original_container_and_staging(proj, write_leaf):
    document = _document(proj, write_leaf)
    folder = proj.planning_home / 'changes/document-edit'
    assert document.dir == folder
    assert (folder / 'change.yaml').is_file() and (folder / 'notes.md').is_file()
    assert (folder / 'staging').is_dir()
    assert not (folder / 'proposal.yaml').exists()
    assert document.targets[0].ref == 'section-x'


def test_shared_overview_lists_both_domains_and_exposes_sources_without_writes(proj, write_leaf, capsys, monkeypatch):
    _document(proj, write_leaf)
    _change('software-edit', run=False)
    result, text = _query(proj, capsys, monkeypatch)
    rows = {row['id']: row for row in result['changes']}
    assert set(rows) == {'document-edit', 'software-edit'}
    assert rows['document-edit']['domain'] == 'document'
    assert rows['software-edit']['domain'] == 'software'
    for cid, row in rows.items():
        assert row['state'] == 'active' and row['sources'] and row['summary']
        assert cid in text


def test_shared_document_show_preserves_existing_target_judgments(proj, write_leaf, capsys, monkeypatch):
    document = _document(proj, write_leaf)
    targets = doc_changes.derive_change_status(proj, document, load_schema())
    assert targets and not all(target.done for target in targets)
    result, text = _query(proj, capsys, monkeypatch, 'show', document.id)
    assert result['id'] == document.id and result['domain'] == 'document' and result['state'] == 'active'
    assert result['summary'] and result['sources'] and result['details']
    serialized = json.dumps(result['details'], ensure_ascii=False)
    for target in targets:
        assert target.ref in serialized and target.detail in serialized
        assert target.ref in text and target.detail in text


def test_shared_software_show_preserves_evidence_failure_and_signoff_information(proj, capsys, monkeypatch):
    _change('software-edit')
    test = proj.project_root / 'app/tests/test_entry.py'
    test.write_text(test.read_text(encoding='utf-8').replace('assert True', 'assert False', 1), encoding='utf-8')
    assert code('testplan', 'sign', 'software-edit', '--by', 'gemini') == 0
    assert code('evidence', 'run', 'software-edit', '1') == 1
    why = evidence.explain(proj, 'software-edit')[0]['why']
    result, text = _query(proj, capsys, monkeypatch, 'show', 'software-edit')
    assert result['domain'] == 'software' and result['state'] == 'active'
    serialized = json.dumps(result['details'], ensure_ascii=False)
    assert why in serialized and why in text
    assert 'E-claude-2' in serialized and 'T1' in serialized
    assert result['sources'] and result['summary']


def test_legacy_software_change_is_readable_and_queries_do_not_migrate_it(proj, capsys, monkeypatch):
    legacy = _legacy(proj)
    before = _bytes(legacy)
    assert software_changes.load_change(proj, 'software-edit')['folder'] == legacy
    result, text = _query(proj, capsys, monkeypatch, 'show', 'software-edit')
    assert result['domain'] == 'software' and result['state'] == 'active'
    sources = json.dumps(result['sources']).replace('\\\\', '/')
    assert 'software/changes/software-edit' in sources
    assert 'software-edit' in text and _bytes(legacy) == before
    assert not (proj.planning_home / 'changes/software-edit').exists()


@pytest.mark.parametrize('original', ['document-active', 'document-abandoned', 'software-active', 'software-archived'])
def test_change_names_are_reserved_across_domains_and_history(proj, write_leaf, original):
    cid = 'reserved-name'
    if original.startswith('document'):
        _document(proj, write_leaf, cid)
        if original.endswith('abandoned'):
            assert change_cmd.run(['archive', cid, '--abandon', '--reason', 'No longer required']) == 0
        before = _bytes(proj.project_root)
        assert code('change', 'new', cid, '--why', 'Cannot reuse this identity') != 0
    else:
        _change(cid, run=original.endswith('archived'))
        if original.endswith('archived'):
            assert code('archive', cid) == 0
        before = _bytes(proj.project_root)
        assert change_cmd.run(['new', cid, '--publish', 'advisory']) != 0
    assert _bytes(proj.project_root) == before


def test_history_is_available_via_all_and_show_but_not_active_overview(proj, write_leaf, capsys, monkeypatch):
    _document(proj, write_leaf, 'abandoned-doc')
    assert change_cmd.run(['archive', 'abandoned-doc', '--abandon', '--reason', 'Retired proposal']) == 0
    _change('archived-software')
    assert code('archive', 'archived-software') == 0
    assert code('change', 'new', 'active-empty', '--why', 'Still a draft') == 0
    active, _ = _query(proj, capsys, monkeypatch)
    assert {row['id'] for row in active['changes']} == {'active-empty'}
    assert active['changes'][0]['state'] == 'active'
    all_changes, text = _query(proj, capsys, monkeypatch, '--all')
    rows = {row['id']: row for row in all_changes['changes']}
    assert rows['abandoned-doc']['state'] == 'abandoned'
    assert rows['archived-software']['state'] == 'archived'
    assert 'abandoned-doc' in text and 'archived-software' in text
    for cid in ('abandoned-doc', 'archived-software'):
        result, _ = _query(proj, capsys, monkeypatch, 'show', cid)
        assert result['state'] == rows[cid]['state']


@pytest.mark.parametrize('broken', ['missing', 'document', 'software'])
def test_missing_or_broken_change_show_fails_without_mutating_or_claiming_completion(proj, write_leaf, capsys, broken):
    cid = 'missing-change'
    if broken == 'document':
        cid = 'document-edit'
        document = _document(proj, write_leaf, cid)
        (document.dir / 'change.yaml').write_text('invalid: true\n', encoding='utf-8')
    elif broken == 'software':
        cid = 'software-edit'
        _change(cid, run=False)
        (software_changes.load_change(proj, cid)['folder'] / 'proposal.yaml').write_text('invalid: true\n', encoding='utf-8')
    before = _bytes(proj.project_root)
    capsys.readouterr()
    assert change_cmd.run(['show', cid, '--json']) != 0
    output = capsys.readouterr()
    assert output.out or output.err
    assert 'unknown subcommand' not in (output.out + output.err)
    assert _bytes(proj.project_root) == before


def test_duplicate_new_and_legacy_change_ids_are_rejected_without_choosing_a_copy(proj, capsys):
    legacy = _legacy(proj)
    shared = proj.planning_home / 'changes/software-edit'
    shared.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(legacy, shared)
    before = _bytes(proj.project_root)
    capsys.readouterr()
    assert change_cmd.run(['show', 'software-edit', '--json']) != 0
    assert change_cmd.run(['--json']) != 0
    output = capsys.readouterr()
    assert 'unknown subcommand' not in (output.out + output.err)
    assert _bytes(proj.project_root) == before


def test_explicit_migration_dry_run_and_apply_preserve_record_bytes(proj, capsys):
    legacy = _legacy(proj)
    original = _bytes(legacy)
    shared = proj.planning_home / 'changes/software-edit'
    before = _bytes(proj.project_root)
    capsys.readouterr()
    assert change_cmd.run(['migrate', '--dry-run']) == 0
    assert _bytes(proj.project_root) == before and legacy.is_dir() and not shared.exists()
    assert change_cmd.run(['migrate']) == 0
    assert shared.is_dir() and not legacy.exists()
    assert _bytes(shared) == original
    assert software_changes.load_change(proj, 'software-edit')['folder'] == shared
    after = _bytes(proj.project_root)
    assert change_cmd.run(['migrate']) == 0
    assert _bytes(proj.project_root) == after


def test_migration_preflights_collisions_before_moving_any_change(proj, capsys):
    first = _legacy(proj, 'a-first')
    collision = _legacy(proj, 'z-collision')
    target = proj.planning_home / 'changes/z-collision'
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(collision, target)
    before = _bytes(proj.project_root)
    capsys.readouterr()
    assert change_cmd.run(['migrate']) != 0
    output = capsys.readouterr()
    assert 'unknown subcommand' not in (output.out + output.err)
    assert _bytes(proj.project_root) == before
    assert first.is_dir() and collision.is_dir()
    assert not (proj.planning_home / 'changes/a-first').exists()
