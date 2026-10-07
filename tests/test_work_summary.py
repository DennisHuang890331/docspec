"""Work summaries follow recorded links and preserve the existing evidence truth."""

import json
import os
import shlex
import subprocess

import pytest

from test_software_archive import proj, _change, code
from test_freeze_and_baseline import doc, _write_prose
from dspx.commands.governance import roadmap, ruling, decision, info
from dspx.commands.deliverable import freeze, render
from dspx.engine import governance as gv, handover as ho
from dspx.engine.layout import Layout
from dspx.engine.model import load_project
from dspx.engine.software import changes as chg, evidence as ev, specs as sp, tasks as tk, io as swio


def _bytes(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob('*') if p.is_file()}


def _work(proj, *, title='Selected work', refs='', parent=None, dependency=None, what=''):
    args = ['add', '--title', title]
    for flag, value in [('--ref', refs), ('--parent', parent), ('--depends-on', dependency), ('--what', what)]:
        if value:
            args += [flag, value]
    assert roadmap.run(args) == 0
    return gv.load_governance(proj).work[-1]['id']


def _summary(proj, work_id, monkeypatch):
    from dspx.engine import work_summary as ws
    before = _bytes(proj.project_root)
    def forbidden(*args, **kwargs):
        raise AssertionError('A work summary must not refresh records, execute commands or write a handover')
    with monkeypatch.context() as patch:
        patch.setattr(subprocess, 'run', forbidden)
        patch.setattr(ev, 'refresh', forbidden)
        patch.setattr(ev, 'run_tests', forbidden)
        patch.setattr(ho, 'write', forbidden)
        result = ws.build(proj, load_project(proj), work_id)
        text = ws.render(result)
    assert result['schema-version'] == 2
    assert result['work']['id'] == work_id
    for row in [*result['actions'], *result['diagnostics']]:
        assert row['code'] and row['reason'] and isinstance(row['ids'], list)
        assert row['reason'] in text
    for row in result['actions']:
        assert 'command' in row
        if row['command']:
            assert row['command'] in text
    assert _bytes(proj.project_root) == before
    return result


def _related_action(result, *ids):
    return [a for a in result['actions']
            if all(any(identifier in str(ref) for ref in a['ids']) for identifier in ids)]


def test_unlinked_work_reports_coverage_limit_without_inventing_completion(proj, monkeypatch):
    assert ruling.run(['add', '--quote', 'Start the synthetic project']) == 0
    wid = _work(proj, what='Inspect the delivery path')
    result = _summary(proj, wid, monkeypatch)
    assert result['work']['what'] == 'Inspect the delivery path'
    assert result['work']['status'] == 'not-started'
    assert result['work']['refs'] == []
    assert result['governance'] == [] and result['software'] == [] and result['documents'] == []
    assert result['diagnostics']
    assert any('link' in d['reason'].lower() or '連結' in d['reason'] for d in result['diagnostics'])


def test_summary_cli_and_renderer_share_contents_and_do_not_refresh(proj, monkeypatch, capsys):
    from dspx.engine import work_summary as ws
    assert ruling.run(['add', '--quote', 'Start']) == 0
    wid = _work(proj, what='The actual work description')
    expected = _summary(proj, wid, monkeypatch)
    before = _bytes(proj.project_root)
    capsys.readouterr()
    assert roadmap.run(['show', wid, '--json']) == 0
    assert json.loads(capsys.readouterr().out) == expected
    assert roadmap.run(['show', wid]) == 0
    assert capsys.readouterr().out.strip() == ws.render(expected).strip()
    assert _bytes(proj.project_root) == before


def test_link_closure_includes_descendants_and_prerequisites_once_and_excludes_unrelated(proj, monkeypatch):
    assert ruling.run(['add', '--quote', 'Related constraint']) == 0
    assert decision.run(['add', '--title', 'Related', '--statement', 'Use this behavior',
                         '--based-on', 'RL-claude-1']) == 0
    assert decision.run(['activate', 'D-claude-1']) == 0
    _change('fix', run=False)
    assert code('change', 'design', 'fix', '--decision', 'D-claude-1') == 0
    prerequisite = _work(proj, title='Prerequisite', refs='swc:fix')
    selected = _work(proj, dependency=prerequisite)
    child = _work(proj, title='Child', parent=selected, refs='swc:fix')
    grandchild = _work(proj, title='Grandchild', parent=child, refs='gov:D-claude-1')
    assert info.run(['add', '--about', 'Other topic', '--quote', 'Unrelated environment fact']) == 0
    unrelated = _work(proj, title='Unrelated work', refs='gov:I-claude-1')
    result = _summary(proj, selected, monkeypatch)
    pairs = {(row['id'], row['relation']) for row in result['dependencies']}
    assert (prerequisite, 'prerequisite') in pairs
    assert (child, 'child') in pairs and (grandchild, 'child') in pairs
    assert unrelated not in {row['id'] for row in result['dependencies']}
    assert [row['id'] for row in result['software']] == ['fix']
    ids = [row['id'] for row in result['governance']]
    assert len(ids) == len(set(ids))
    assert {'D-claude-1', 'RL-claude-1'} <= set(ids)
    assert 'I-claude-1' not in ids


def test_superseded_decision_preserves_original_link_and_lists_current_replacement(proj, monkeypatch):
    assert ruling.run(['add', '--quote', 'Original direction']) == 0
    assert decision.run(['add', '--title', 'Original', '--statement', 'Original complete decision',
                         '--based-on', 'RL-claude-1']) == 0
    assert decision.run(['activate', 'D-claude-1']) == 0
    wid = _work(proj, refs='gov:D-claude-1')
    assert ruling.run(['add', '--quote', 'Replacement direction']) == 0
    assert decision.run(['add', '--title', 'Replacement', '--statement', 'Replacement complete decision',
                         '--supersedes', 'D-claude-1', '--based-on', 'RL-claude-2']) == 0
    assert decision.run(['activate', 'D-claude-2']) == 0
    result = _summary(proj, wid, monkeypatch)
    records = {row['id']: row for row in result['governance']}
    old = records['D-claude-1']
    assert old['status'] == 'superseded'
    assert old['statement'] == 'Original complete decision'
    assert old['original-references'] and old['sources']
    assert old['current-ids'] == ['D-claude-2']
    assert records['D-claude-2']['statement'] == 'Replacement complete decision'
    assert result['work']['refs'] == ['gov:D-claude-1']
    assert _related_action(result, 'D-claude-1', 'D-claude-2')
    assert any(row['kind'] == 'suspect' for row in result['governance'])


def test_software_requirements_follow_their_basis_without_importing_other_requirements(proj, monkeypatch):
    assert ruling.run(['add', '--quote', 'Requirement direction']) == 0
    assert decision.run(['add', '--title', 'Basis', '--statement', 'Selected requirement basis',
                         '--based-on', 'RL-claude-1']) == 0
    assert decision.run(['activate', 'D-claude-1']) == 0
    assert ruling.run(['add', '--quote', 'Unrelated requirement direction']) == 0
    assert decision.run(['add', '--title', 'Other basis', '--statement', 'Unrelated requirement basis',
                         '--based-on', 'RL-claude-2']) == 0
    assert decision.run(['activate', 'D-claude-2']) == 0
    spec = sp.load_spec(proj, 'entry')
    spec['requirements'][0]['based-on'] = ['D-claude-1']
    spec['requirements'][1]['based-on'] = ['D-claude-2']
    sp.write_spec(proj, spec)
    _change('fix', run=False)
    wid = _work(proj, refs='swc:fix')
    result = _summary(proj, wid, monkeypatch)
    ids = {row['id'] for row in result['governance']}
    assert {'D-claude-1', 'RL-claude-1'} <= ids
    assert 'D-claude-2' not in ids and 'RL-claude-2' not in ids


@pytest.mark.parametrize('state', ['unsigned', 'needs-review', 'current'])
def test_test_role_actions_use_existing_per_test_signoff_truth(proj, monkeypatch, state):
    _change('fix', run=False)
    if state == 'unsigned':
        ch = chg.load_change(proj, 'fix')
        ch['tests']['tests'][0].pop('signed')
        chg.write_part(proj, 'fix', 'tests', ch['tests'])
    elif state == 'needs-review':
        test = proj.project_root / 'app/tests/test_entry.py'
        test.write_text(test.read_text(encoding='utf-8').replace('assert True', 'assert False', 1), encoding='utf-8')
    assert ruling.run(['add', '--quote', 'Start']) == 0
    wid = _work(proj, refs='swc:fix')
    result = _summary(proj, wid, monkeypatch)
    row = result['software'][0]['signoffs'][0]
    assert row['test'] == 'T1' and row['status'] == state
    if state != 'current':
        assert row['problems']
        actions = _related_action(result, 'T1')
        assert actions
        assert any('test role' in a['reason'].lower() or '測試角色' in a['reason'] for a in actions)
    else:
        assert not row['problems']
    assert result['work']['status'] not in ('done', 'done-waived')


def test_latest_failed_evidence_overrides_earlier_pass_and_has_a_recovery_action(proj, monkeypatch):
    _change('fix')
    test = proj.project_root / 'app/tests/test_entry.py'
    test.write_text(test.read_text(encoding='utf-8').replace('assert True', 'assert False', 1), encoding='utf-8')
    assert code('testplan', 'sign', 'fix', '--by', 'gemini') == 0
    assert code('evidence', 'run', 'fix', '1') == 1
    latest = ev.load_all(proj)[-1]
    assert latest['result'] == 'fail'
    assert ruling.run(['add', '--quote', 'Start']) == 0
    wid = _work(proj, refs='swc:fix')
    result = _summary(proj, wid, monkeypatch)
    software = result['software'][0]
    assert software['tasks'] == ev.explain(proj, 'fix')
    assert software['tasks'][0]['status'] not in ('done', 'done-waived')
    assert any(e['id'] == latest['id'] and e['result'] == 'fail' for e in software['evidence'])
    assert _related_action(result, latest['id'], '1')
    assert result['work']['status'] not in ('done', 'done-waived')


def test_waiver_keeps_existing_task_status_and_does_not_claim_archive_finished(proj, monkeypatch):
    _change('fix', run=False)
    assert ruling.run(['add', '--quote', 'Waive the unchanged synthetic task']) == 0
    assert code('evidence', 'waive', 'fix', '1', '--ruling', 'RL-claude-1',
                '--reopen-when', 'Scope changes') == 0
    wid = _work(proj, refs='swc:fix')
    result = _summary(proj, wid, monkeypatch)
    assert result['software'][0]['tasks'] == ev.explain(proj, 'fix')
    assert result['software'][0]['tasks'][0]['status'] == 'done-waived'
    assert result['work']['status'] != 'done'


def test_document_realizes_facts_and_requires_owner_to_freeze_current_prose(doc, monkeypatch, write_leaf):
    layout = Layout(doc)
    assert info.run(['add', '--about', 'Operating environment', '--quote', 'Synthetic Windows terminals']) == 0
    write_leaf.edit(doc, 'g/x', concept={'realizes': ['gov:I-claude-1']})
    assert render.run(['g']) == 0
    _write_prose(doc)
    assert render.run(['g']) == 0
    wid = _work(layout, refs='doc:g')
    result = _summary(layout, wid, monkeypatch)
    document = next(d for d in result['documents'] if d['id'] == 'doc:g')
    assert document['written'] is True and document['frozen'] is False
    assert result['work']['status'] != 'done'
    fact = next(g for g in result['governance'] if g['id'] == 'I-claude-1')
    assert fact['quote'] == 'Synthetic Windows terminals' and fact['sources']
    freeze_actions = [a for a in result['actions'] if 'freeze' in (a['command'] or '')]
    assert freeze_actions
    assert any('owner' in a['reason'].lower() or '負責人' in a['reason'] or '使用者' in a['reason']
               for a in freeze_actions)
    assert freeze.run(['g']) == 0
    refreshed = _summary(layout, wid, monkeypatch)
    assert refreshed['work']['status'] == 'done'
    assert refreshed['documents'][0]['frozen'] is True


@pytest.mark.parametrize('broken', ['missing-ref', 'missing-prerequisite', 'cycle'])
def test_missing_links_and_dependency_cycles_cannot_be_reported_done(proj, monkeypatch, broken):
    assert ruling.run(['add', '--quote', 'Start']) == 0
    wid = _work(proj)
    assert roadmap.run(['done', wid, '--note', 'Originally completed small work']) == 0
    path = gv.record_path(proj, 'work', wid)
    work = gv.load_record(path, 'work')
    if broken == 'missing-ref':
        work['refs'] = ['swc:missing-change']
    elif broken == 'missing-prerequisite':
        work['depends-on'] = ['W-claude-999']
    else:
        other = _work(proj, dependency=wid)
        work['depends-on'] = [other]
    gv.write_record(proj, 'work', work)
    result = _summary(proj, wid, monkeypatch)
    assert result['work']['status'] not in ('done', 'done-waived')
    assert result['diagnostics']
    assert any(d['ids'] for d in result['diagnostics'])


@pytest.mark.parametrize('broken', ['missing-work', 'damaged-linked-record'])
def test_cli_returns_error_for_missing_work_or_unreadable_required_records(proj, capsys, broken):
    assert ruling.run(['add', '--quote', 'Start']) == 0
    if broken == 'missing-work':
        wid = 'W-claude-999'
    else:
        _change('fix', run=False)
        wid = _work(proj, refs='swc:fix')
        path = swio.change_dir(proj, 'fix') / 'tests.yaml'
        path.write_text('invalid: true\n', encoding='utf-8')
    before = _bytes(proj.project_root)
    capsys.readouterr()
    assert roadmap.run(['show', wid, '--json']) != 0
    output = capsys.readouterr()
    assert output.out or output.err
    assert _bytes(proj.project_root) == before


@pytest.mark.parametrize('condition', ['unknown', 'legacy'])
def test_summary_preserves_unknown_and_legacy_signoff_reasons(proj, monkeypatch, condition):
    _change('fix', run=False)
    assert ruling.run(['add', '--quote', 'Start']) == 0
    wid = _work(proj, refs='swc:fix')
    if condition == 'unknown':
        def denied(*args, **kwargs):
            raise PermissionError('synthetic test file access failure')
        monkeypatch.setattr(tk, 'test_fingerprint', denied)
    else:
        ch = chg.load_change(proj, 'fix')
        ch['tests']['tests'][0]['signed'].pop('scenario-fingerprint')
        chg.write_part(proj, 'fix', 'tests', ch['tests'])
    result = _summary(proj, wid, monkeypatch)
    signoff = result['software'][0]['signoffs'][0]
    assert signoff['status'] == ('unknown' if condition == 'unknown' else 'needs-review')
    assert signoff['problems']
    assert _related_action(result, 'T1')
    assert result['work']['status'] not in ('done', 'done-waived')


def test_missing_transitive_basis_cannot_support_a_closed_work_item(proj, monkeypatch):
    assert ruling.run(['add', '--quote', 'Selected direction']) == 0
    assert decision.run(['add', '--title', 'Selected basis', '--statement', 'Complete selected basis',
                         '--based-on', 'RL-claude-1']) == 0
    assert decision.run(['activate', 'D-claude-1']) == 0
    wid = _work(proj, refs='gov:D-claude-1')
    assert roadmap.run(['done', wid, '--note', 'Completed the small work']) == 0
    gv.record_path(proj, 'ruling', 'RL-claude-1').unlink()
    result = _summary(proj, wid, monkeypatch)
    assert any('RL-claude-1' in str(row['ids']) for row in result['diagnostics'])
    assert result['work']['status'] not in ('done', 'done-waived')


def test_multistep_supersession_points_to_final_effective_decision(proj, monkeypatch):
    for n in range(1, 4):
        assert ruling.run(['add', '--quote', f'Direction version {n}']) == 0
        args = ['add', '--title', f'Version {n}', '--statement', f'Complete decision version {n}',
                '--based-on', f'RL-claude-{n}']
        if n > 1:
            args += ['--supersedes', f'D-claude-{n - 1}']
        assert decision.run(args) == 0
        assert decision.run(['activate', f'D-claude-{n}']) == 0
    wid = _work(proj, refs='gov:D-claude-1')
    result = _summary(proj, wid, monkeypatch)
    records = {row['id']: row for row in result['governance']}
    assert records['D-claude-1']['current-ids'] == ['D-claude-3']
    assert records['D-claude-2']['current-ids'] == ['D-claude-3']
    assert records['D-claude-3']['status'] == 'active'
    assert result['work']['refs'] == ['gov:D-claude-1']


def test_archived_software_stays_completed_and_exposes_recorded_evidence(proj, monkeypatch):
    _change('fix')
    assert code('archive', 'fix') == 0
    (proj.project_root / 'app/tests/test_entry.py').unlink()
    assert ruling.run(['add', '--quote', 'Track the completed change']) == 0
    wid = _work(proj, refs='swc:fix')
    result = _summary(proj, wid, monkeypatch)
    assert result['work']['status'] == 'done'
    software = result['software'][0]
    assert software['status'] == 'archived'
    assert software['historical'] is True
    assert software['tasks'][0]['status'] == 'done'
    assert software['tasks'][0]['evidence'] == ['E-claude-1']
    assert all(row['status'] == 'historical' for row in software['signoffs'])
    assert not any(row['code'] in ('review-signoff', 'failed-verification', 'verification-needed')
                   for row in result['actions'])
    assert any(row['id'] == 'E-claude-1' and row['result'] == 'pass' for row in software['evidence'])
    assert '_archive' in software['source']
    assert software['details'] == []


def test_human_verified_work_reports_pending_acceptance_without_overriding_task_truth(proj, monkeypatch):
    assert code('change', 'new', 'layout', '--why', 'Adjust layout', '--modified', 'entry') == 0
    assert code('change', 'delta', 'layout', '--capability', 'entry', '--op', 'modify-requirement',
                '--ref', 'R2', '--statement', 'It MUST fit 1024px.') == 0
    assert code('task', 'add', 'layout', '--title', 'Layout', '--implements', 'entry/R2',
                '--files', 'app:src/entry.py', '--verify', 'inspection') == 0
    assert code('evidence', 'add', 'layout', '1', '--type', 'inspection', '--subject', 'Layout',
                '--conclusion', 'Checked the synthetic layout', '--result', 'pass') == 0
    assert ruling.run(['add', '--quote', 'Track layout work']) == 0
    wid = _work(proj, refs='swc:layout')
    result = _summary(proj, wid, monkeypatch)
    software = result['software'][0]
    assert software['tasks'] == ev.explain(proj, 'layout')
    assert software['tasks'][0]['status'] == 'done'
    assert any("owner's acceptance" in reason for reason in software['details'])
    assert result['work']['status'] not in ('done', 'done-waived')


def test_mtime_and_unrelated_file_changes_do_not_change_the_work_summary(proj, monkeypatch):
    _change('fix', run=False)
    assert ruling.run(['add', '--quote', 'Start']) == 0
    wid = _work(proj, refs='swc:fix')
    before = _summary(proj, wid, monkeypatch)
    for path in proj.planning_home.rglob('*.yaml'):
        os.utime(path, (1000000000, 1000000000))
    (proj.project_root / 'unrelated.txt').write_text('Unrelated scratch note', encoding='utf-8')
    assert _summary(proj, wid, monkeypatch) == before


def test_document_software_divergence_is_shown_without_blocking_frozen_document(proj, monkeypatch, write_leaf):
    write_leaf(proj.planning_home, 'g/x', concept={'id': 'c1', 'title': 'X', 'order': 1,
                                                  'realizes': ['req:entry/R1']})
    assert render.run(['g']) == 0
    _write_prose(proj.planning_home)
    assert render.run(['g']) == 0
    _change('fix')
    assert code('archive', 'fix') == 0
    assert freeze.run(['g']) == 0
    assert ruling.run(['add', '--quote', 'Track document delivery']) == 0
    wid = _work(proj, refs='doc:g')
    result = _summary(proj, wid, monkeypatch)
    assert result['work']['status'] == 'done'
    document = result['documents'][0]
    assert document['frozen'] is True and document['written'] is True
    assert document['sync']['g/x'] == 'stale-software'
    assert any('stale-software' in reason for reason in document['details'])
    assert result['software'] == []


@pytest.mark.parametrize('target', ['task:fix#1', 'test:fix/T1', 'doc:g/x',
                                    'req:entry/R1', 'req:entry/R1/S1'])
def test_nested_review_flags_include_their_trigger_but_not_unrelated_flags(proj, monkeypatch, write_leaf, target):
    assert ruling.run(['add', '--quote', 'A relevant review trigger']) == 0
    assert ruling.run(['add', '--quote', 'An unrelated review trigger']) == 0
    if target.startswith('doc:'):
        write_leaf(proj.planning_home, 'g/x', concept={'id': 'c1', 'title': 'X', 'order': 1})
        assert render.run(['g']) == 0
        linked = 'doc:g'
    else:
        _change('fix', run=False)
        linked = 'swc:fix'
    for sid, affected, trigger in [('S-claude-1', target, 'RL-claude-1'),
                                   ('S-claude-2', 'task:other#1', 'RL-claude-2')]:
        gv.write_record(proj, 'suspect', {'id': sid, 'trigger': trigger, 'target': affected,
                                        'status': 'open', 'created-at': gv.today()})
    wid = _work(proj, refs=linked)
    result = _summary(proj, wid, monkeypatch)
    records = {row['id']: row for row in result['governance']}
    assert records['S-claude-1']['status'] == 'open'
    assert records['S-claude-1']['target'] == target
    assert records['RL-claude-1']['quote'] == 'A relevant review trigger'
    assert 'S-claude-2' not in records and 'RL-claude-2' not in records
    assert _related_action(result, 'S-claude-1', target, 'RL-claude-1')


def test_document_drilldown_command_works_for_an_article_without_a_root_section(doc, monkeypatch, capsys):
    from dspx.commands.query import show
    layout = Layout(doc)
    assert ruling.run(['add', '--quote', 'Read the document']) == 0
    wid = _work(layout, refs='doc:g')
    result = _summary(layout, wid, monkeypatch)
    command = shlex.split(result['documents'][0]['command'])
    assert command[:2] == ['artispec', 'show']
    before = _bytes(layout.project_root)
    capsys.readouterr()
    assert show.run(command[2:]) == 0
    assert 'g/x' in capsys.readouterr().out
    assert _bytes(layout.project_root) == before


@pytest.mark.parametrize('problem', ['unfinished-prerequisite', 'base-conflict'])
def test_summary_exposes_strict_archive_blockers_not_just_task_evidence(proj, monkeypatch, problem):
    _change('fix', run=False)
    if problem == 'unfinished-prerequisite':
        assert code('change', 'new', 'foundation', '--why', 'Precondition') == 0
        change = chg.load_change(proj, 'fix')
        change['proposal']['depends-on'] = ['foundation']
        chg.write_part(proj, 'fix', 'proposal', change['proposal'])
        expected_words = ['foundation', 'archived first']
    else:
        spec = sp.load_spec(proj, 'entry')
        spec['requirements'][0]['scenarios'][0]['then'] = 'Another change already updated this behavior'
        sp.write_spec(proj, spec)
        expected_words = ['entry', 'R1/S1', 'changed since this delta']
    assert ruling.run(['add', '--quote', 'Track the selected change']) == 0
    wid = _work(proj, refs='swc:fix')
    result = _summary(proj, wid, monkeypatch)
    software = next(row for row in result['software'] if row['id'] == 'fix')
    assert any(all(word in reason for word in expected_words) for reason in software['details'])
    from dspx.engine import work_summary as ws
    text = ws.render(result)
    assert all(word in text for word in expected_words)
    assert result['work']['status'] not in ('done', 'done-waived')


def test_text_summarizes_healthy_records_while_preserving_failure_details(proj, monkeypatch):
    from dspx.engine import work_summary as ws
    _change('fix', run=False)
    assert code('testplan', 'add', 'fix', '--location', 'app:tests/test_entry.py::test_width',
                '--covers', 'entry/R1/S1', '--by', 'gemini') == 0
    assert code('testplan', 'sign', 'fix', '--by', 'gemini') == 0
    assert code('task', 'add', 'fix', '--title', 'Second implementation task', '--implements', 'entry/R1',
                '--files', 'app:src/entry.py', '--verify', 'test', '--tests', 'T2') == 0
    test = proj.project_root / 'app/tests/test_entry.py'
    test.write_text(test.read_text(encoding='utf-8').replace('def test_width():\n    assert True',
                                                           'def test_width():\n    assert False'), encoding='utf-8')
    assert code('testplan', 'sign', 'fix', 'T2', '--by', 'gemini') == 0
    assert code('evidence', 'run', 'fix', '1') == 0
    assert code('evidence', 'run', 'fix', '2') == 1
    assert ruling.run(['add', '--quote', 'Inspect mixed progress']) == 0
    wid = _work(proj, refs='swc:fix')
    result = _summary(proj, wid, monkeypatch)
    rows = {str(row['task']): row for row in result['software'][0]['tasks']}
    assert rows['1']['status'] == 'done' and rows['2']['status'] == 'in-progress'
    text = ws.render(result)
    assert '已完成任務 1' in text and '有效簽收 2/2' in text
    assert rows['1']['why'] not in text
    assert rows['2']['why'] in text
    assert 'E-claude-1' in text and 'E-claude-2' in text
    assert 'T1 sign-off: current' not in text and 'T2 sign-off: current' not in text


def test_software_prerequisite_cycle_has_an_explicit_diagnostic(proj, monkeypatch):
    _change('fix', run=False)
    assert code('change', 'new', 'foundation', '--why', 'Prerequisite work') == 0
    for cid, dependency in [('fix', 'foundation'), ('foundation', 'fix')]:
        change = chg.load_change(proj, cid)
        change['proposal']['depends-on'] = [dependency]
        chg.write_part(proj, cid, 'proposal', change['proposal'])
    assert ruling.run(['add', '--quote', 'Inspect the selected work']) == 0
    wid = _work(proj, refs='swc:fix')
    result = _summary(proj, wid, monkeypatch)
    cycles = [row for row in result['diagnostics']
              if 'cycle' in row['code'].lower() or '循環' in row['reason']]
    assert any('fix' in str(row['ids']) and 'foundation' in str(row['ids']) for row in cycles)
    assert result['work']['status'] not in ('done', 'done-waived')
    assert {row['id'] for row in result['software']} == {'fix', 'foundation'}


def test_archived_requirement_basis_comes_from_saved_evidence_scope(proj, monkeypatch):
    assert ruling.run(['add', '--quote', 'Original requirement direction']) == 0
    assert decision.run(['add', '--title', 'Original basis', '--statement', 'The archived requirement basis',
                         '--based-on', 'RL-claude-1']) == 0
    assert decision.run(['activate', 'D-claude-1']) == 0
    spec = sp.load_spec(proj, 'entry')
    spec['requirements'][0]['based-on'] = ['D-claude-1']
    sp.write_spec(proj, spec)
    _change('fix')
    assert code('archive', 'fix') == 0
    assert ruling.run(['add', '--quote', 'Another independent direction']) == 0
    assert decision.run(['add', '--title', 'Later basis', '--statement', 'The current requirement basis',
                         '--based-on', 'RL-claude-2']) == 0
    assert decision.run(['activate', 'D-claude-2']) == 0
    current = sp.load_spec(proj, 'entry')
    current['requirements'][0]['based-on'] = ['D-claude-2']
    sp.write_spec(proj, current)
    wid = _work(proj, refs='swc:fix')
    result = _summary(proj, wid, monkeypatch)
    records = {row['id']: row for row in result['governance']}
    assert records['D-claude-1']['statement'] == 'The archived requirement basis'
    assert 'RL-claude-1' in records
    assert 'D-claude-2' not in records and 'RL-claude-2' not in records
    assert result['work']['status'] == 'done'
