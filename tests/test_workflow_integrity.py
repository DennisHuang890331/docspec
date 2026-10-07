"""Workflow integrity contracts reproduced with synthetic, portable projects."""
import json
import copy
import shlex
import subprocess
import sys
import yaml
import pytest
from test_software_archive import proj, _change, code
from dspx.engine.software import archive as arc, evidence as ev, changes as chg, io, specs as sp
from dspx.engine import governance as gv, roadmap_v2 as rv
from dspx.commands.governance import ruling, decision, roadmap
from test_freeze_and_baseline import doc, _write_prose
from dspx.commands.deliverable import freeze as freeze_cmd, render as render_cmd
from dspx.engine.layout import Layout
from dspx.engine.model import load_project
from dspx.engine import project_baseline as pb


def _config(proj, command):
    config = yaml.safe_load(io.config_path(proj).read_text(encoding='utf-8'))
    config['repos']['app']['test-command'] = command
    io.config_path(proj).write_text(yaml.safe_dump(config), encoding='utf-8')


def _passing(proj):
    _change('fix')
    assert ev.load_all(proj)[-1]['result'] == 'pass'
    assert ev.explain(proj, 'fix')[0]['status'] == 'done'


def test_required_unexecuted_test_blocks_archive(proj):
    test_path = proj.project_root / 'app/tests/test_entry.py'
    test_path.write_text(test_path.read_text(encoding='utf-8') + '\ndef test_second():\n    assert False\n', encoding='utf-8')
    _change('fix', run=False)
    assert code('change', 'delta', 'fix', '--capability', 'entry', '--op', 'add-scenario', '--ref', 'R1', '--title', 'second', '--when', 'second', '--then', 'second works') == 0
    assert code('testplan', 'add', 'fix', '--location', 'app:tests/test_entry.py::test_second', '--covers', 'entry/R1/S2', '--by', 'gemini') == 0
    assert code('testplan', 'sign', 'fix', '--by', 'gemini') == 0
    assert code('evidence', 'run', 'fix', '1') == 0
    assert not arc.plan(proj, 'fix')['ok']
    assert code('archive', 'fix') == 1
    assert len(sp.load_spec(proj, 'entry')['requirements'][0]['scenarios']) == 1


def test_latest_failed_run_without_collected_tests_blocks_completion(proj):
    _change('fix')
    config = yaml.safe_load(io.config_path(proj).read_text(encoding='utf-8'))
    config['repos']['app']['test-command'] += ' -k no_such_test_for_review'
    io.config_path(proj).write_text(yaml.safe_dump(config), encoding='utf-8')
    assert code('evidence', 'run', 'fix', '1') == 1
    latest = ev.for_task(ev.load_all(proj), 'fix', '1')[-1]
    assert latest['result'] == 'fail' and latest['tests'] == []
    assert ev.explain(proj, 'fix')[0]['status'] != 'done'
    assert not arc.plan(proj, 'fix')['ok']


def test_changed_scenario_invalidates_old_evidence(proj):
    _change('fix')
    before = ev.load_all(proj)
    assert code('change', 'undelta', 'fix', '--capability', 'entry', '--ref', 'R1/S1') == 0
    assert code('change', 'delta', 'fix', '--capability', 'entry', '--op', 'modify-scenario', '--ref', 'R1/S1', '--then', 'A completely different required outcome') == 0
    assert ev.load_all(proj) == before
    assert ev.explain(proj, 'fix')[0]['status'] != 'done'
    assert not arc.plan(proj, 'fix')['ok']


def test_test_location_change_invalidates_signoff_and_evidence(proj):
    _change('fix')
    assert code('testplan', 'set', 'fix', 'T1', '--location', 'app:tests/test_entry.py::test_width', '--by', 'gemini') == 0
    assert not chg.load_change(proj, 'fix')['tests']['tests'][0].get('signed')
    assert ev.explain(proj, 'fix')[0]['status'] != 'done'
    assert not arc.plan(proj, 'fix')['ok']


def test_rejected_waiver_cannot_complete_task(proj):
    _change('fix', run=False)
    assert ruling.run(['add', '--quote', 'Temporarily waive this task']) == 0
    assert code('evidence', 'waive', 'fix', '1', '--ruling', 'RL-claude-1', '--reopen-when', 'Owner withdraws waiver') == 0
    assert ruling.run(['reject', 'RL-claude-1', '--reason', 'Do not waive it now']) == 0
    assert gv.ruling_effective_status(gv.load_governance(proj).rulings[0], gv.load_governance(proj)) == 'rejected'
    assert ev.explain(proj, 'fix')[0]['status'] != 'done-waived'
    assert not arc.plan(proj, 'fix')['ok']


def test_stale_owner_acceptance_blocks_archive(proj):
    assert code('change', 'new', 'layout', '--why', 'fix', '--modified', 'entry') == 0
    assert code('change', 'delta', 'layout', '--capability', 'entry', '--op', 'modify-requirement', '--ref', 'R2', '--statement', 'It MUST fit 1024px.') == 0
    assert code('task', 'add', 'layout', '--title', 'layout', '--implements', 'entry/R2', '--files', 'app:src/entry.py', '--verify', 'inspection') == 0
    assert code('evidence', 'accept', 'layout', '1', '--read-back', 'Owner saw version one', '--confirmed', 'Yes') == 0
    (proj.project_root / 'app/src/entry.py').write_text('X = 2\n', encoding='utf-8')
    assert ev.explain(proj, 'layout')[0]['status'] == 'needs-rerun'
    assert code('evidence', 'add', 'layout', '1', '--type', 'inspection', '--subject', 'New version', '--conclusion', 'Agent inspected version two', '--result', 'pass') == 0
    assert not arc.plan(proj, 'layout')['ok']


def test_proposal_can_create_test_task_before_test_plan(proj):
    assert code('change', 'new', 'proposal', '--why', 'fix', '--modified', 'entry') == 0
    assert code('task', 'add', 'proposal', '--title', 'implement', '--implements', 'entry/R1', '--files', 'app:src/entry.py', '--verify', 'test') == 0
    assert ev.explain(proj, 'proposal')[0]['status'] == 'not-started'
    assert code('evidence', 'run', 'proposal', '1') == 1
    assert not arc.plan(proj, 'proposal')['ok']


def test_roadmap_manual_done_cannot_override_linked_work(proj):
    _change('fix', run=False)
    assert ruling.run(['add', '--quote', 'Start work']) == 0
    assert roadmap.run(['add', '--title', 'unfinished', '--ref', 'swc:fix']) == 0
    assert roadmap.run(['done', 'W-claude-1', '--note', 'done by mistake']) == 1
    assert rv.view(proj, [])['unassigned'][0]['status'] != 'done'
    assert not arc.plan(proj, 'fix')['ok']


def test_rejected_decision_basis_blocks_related_archive(proj):
    assert ruling.run(['add', '--quote', 'Use this design']) == 0
    assert decision.run(['add', '--title', 'design', '--statement', 'The chosen design', '--based-on', 'RL-claude-1']) == 0
    assert decision.run(['activate', 'D-claude-1']) == 0
    _change('fix')
    assert code('change', 'design', 'fix', '--decision', 'D-claude-1') == 0
    assert ruling.run(['reject', 'RL-claude-1', '--reason', 'Recorded incorrectly']) == 0
    assert gv.validate(proj)
    assert not arc.plan(proj, 'fix')['ok']


def test_roadmap_requires_current_document_content_frozen(doc):
    layout = Layout(doc)
    assert ruling.run(['add', '--quote', 'Write guide']) == 0
    _write_prose(doc)
    assert freeze_cmd.run(['g']) == 0
    assert roadmap.run(['add', '--title', 'deliver revised guide', '--ref', 'doc:g']) == 0
    _write_prose(doc, 'Changed content after freeze.')
    assert render_cmd.run(['g']) == 0
    assert pb._has_unfrozen_edits(layout, 'g', '1.0.0')
    assert rv.view(layout, load_project(layout))['unassigned'][0]['status'] != 'done'


def test_complete_evidence_archives_and_records_only_passed_test(proj):
    _passing(proj)
    assert code('archive', 'fix') == 0
    scenario = sp.load_spec(proj, 'entry')['requirements'][0]['scenarios'][0]
    assert scenario['verified-by'] == ['app:tests/test_entry.py::test_first_row']


def test_unrelated_requirement_and_title_changes_preserve_task_evidence(proj):
    _passing(proj)
    assert code('change', 'delta', 'fix', '--capability', 'entry', '--op', 'modify-requirement',
                '--ref', 'R2', '--statement', 'It MUST fit 2048px.') == 0
    assert ev.explain(proj, 'fix')[0]['status'] == 'done'
    assert code('change', 'delta', 'fix', '--capability', 'entry', '--op', 'rename-requirement',
                '--ref', 'R1', '--title', 'A clearer label') == 0
    assert ev.explain(proj, 'fix')[0]['status'] == 'done'


def test_changed_scenario_requires_resign_before_successful_retry(proj):
    _passing(proj)
    assert code('change', 'undelta', 'fix', '--capability', 'entry', '--ref', 'R1/S1') == 0
    assert code('change', 'delta', 'fix', '--capability', 'entry', '--op', 'modify-scenario',
                '--ref', 'R1/S1', '--then', 'A revised behavior') == 0
    assert code('evidence', 'run', 'fix', '1') == 1
    assert code('testplan', 'sign', 'fix', '--by', 'gemini') == 0
    assert code('evidence', 'run', 'fix', '1') == 0
    assert ev.explain(proj, 'fix')[0]['status'] == 'done'
    assert arc.plan(proj, 'fix')['ok']


@pytest.mark.parametrize('failure', ['partial', 'no-report', 'timeout', 'missing-runner'])
def test_latest_failed_attempt_cannot_fall_back_and_retry_recovers(proj, monkeypatch, failure):
    _change('fix', run=False)
    assert code('testplan', 'add', 'fix', '--location', 'app:tests/test_entry.py::test_width',
                '--covers', 'entry/R1/S1', '--by', 'gemini') == 0
    assert code('testplan', 'sign', 'fix', '--by', 'gemini') == 0
    assert code('task', 'set', 'fix', '1', '--tests', 'T1,T2') == 0
    assert code('evidence', 'run', 'fix', '1') == 0
    command = chg.repo_settings(proj)['app']['test-command']
    if failure == 'partial':
        _config(proj, command + ' -k first_row')
        assert code('evidence', 'run', 'fix', '1') == 1
    elif failure == 'no-report':
        _config(proj, shlex.join([sys.executable, '-c', 'print("2 passed")']))
        assert code('evidence', 'run', 'fix', '1') == 1
    elif failure == 'missing-runner':
        _config(proj, 'docspec_nonexistent_runner_for_test')
        assert code('evidence', 'run', 'fix', '1') == 1
    else:
        original = subprocess.run
        def timeout_for_tests(argv, *args, **kwargs):
            if any(str(x).startswith('--junitxml=') for x in argv):
                raise subprocess.TimeoutExpired(argv, 1)
            return original(argv, *args, **kwargs)
        with monkeypatch.context() as patch:
            patch.setattr(subprocess, 'run', timeout_for_tests)
            assert code('evidence', 'run', 'fix', '1') == 1
    latest = ev.for_task(ev.load_all(proj), 'fix', '1')[-1]
    assert latest['result'] == 'fail'
    assert ev.explain(proj, 'fix')[0]['status'] not in ('done', 'done-waived')
    assert not arc.plan(proj, 'fix')['ok']
    _config(proj, command)
    assert code('evidence', 'run', 'fix', '1') == 0
    assert ev.explain(proj, 'fix')[0]['status'] == 'done'
    assert len(ev.for_task(ev.load_all(proj), 'fix', '1')) == 3


def test_valid_waiver_allows_archive_without_claiming_test_passed(proj):
    _change('fix', run=False)
    assert ruling.run(['add', '--quote', 'Waive this unchanged scope']) == 0
    assert code('evidence', 'waive', 'fix', '1', '--ruling', 'RL-claude-1',
                '--reopen-when', 'Scope changes') == 0
    assert ev.explain(proj, 'fix')[0]['status'] == 'done-waived'
    assert code('archive', 'fix') == 0
    assert not sp.load_spec(proj, 'entry')['requirements'][0]['scenarios'][0].get('verified-by')
    baseline = io.load(next(io.baselines_dir(proj).glob('*-fix.yaml')), 'baseline')
    assert baseline['tasks'] == {'done-waived': 1}


@pytest.mark.parametrize('change', ['supersede', 'scope'])
def test_waiver_rechecks_authority_and_task_scope(proj, change):
    _change('fix', run=False)
    assert ruling.run(['add', '--quote', 'Waive this scope']) == 0
    assert code('evidence', 'waive', 'fix', '1', '--ruling', 'RL-claude-1',
                '--reopen-when', 'Review again') == 0
    if change == 'supersede':
        assert ruling.run(['add', '--quote', 'Tests are required', '--supersedes', 'RL-claude-1']) == 0
    else:
        assert code('change', 'undelta', 'fix', '--capability', 'entry', '--ref', 'R1/S1') == 0
        assert code('change', 'delta', 'fix', '--capability', 'entry', '--op', 'modify-scenario',
                    '--ref', 'R1/S1', '--then', 'New required result') == 0
    assert ev.explain(proj, 'fix')[0]['status'] != 'done-waived'
    assert not arc.plan(proj, 'fix')['ok']


def test_rejected_historical_waiver_does_not_hide_valid_test(proj):
    _change('fix', run=False)
    assert ruling.run(['add', '--quote', 'Waive']) == 0
    assert code('evidence', 'waive', 'fix', '1', '--ruling', 'RL-claude-1', '--reopen-when', 'Review') == 0
    assert ruling.run(['reject', 'RL-claude-1', '--reason', 'Now test']) == 0
    assert code('evidence', 'run', 'fix', '1') == 0
    assert ev.explain(proj, 'fix')[0]['status'] == 'done'
    assert arc.plan(proj, 'fix')['ok']


def test_unrelated_rejected_decision_does_not_block_archive(proj):
    assert ruling.run(['add', '--quote', 'Unrelated topic']) == 0
    assert decision.run(['add', '--title', 'other', '--statement', 'Unrelated design',
                         '--based-on', 'RL-claude-1']) == 0
    assert decision.run(['activate', 'D-claude-1']) == 0
    assert ruling.run(['reject', 'RL-claude-1', '--reason', 'Incorrect']) == 0
    _passing(proj)
    assert arc.plan(proj, 'fix')['ok']


def test_proposal_test_role_handoff_then_execution(proj):
    assert code('change', 'new', 'fix', '--why', 'change behavior', '--modified', 'entry') == 0
    assert code('change', 'delta', 'fix', '--capability', 'entry', '--op', 'modify-scenario',
                '--ref', 'R1/S1', '--then', 'New behavior') == 0
    assert code('task', 'add', 'fix', '--title', 'implement', '--implements', 'entry/R1',
                '--files', 'app:src/entry.py', '--verify', 'test') == 0
    errors, warnings = chg.validate_change(proj, chg.load_change(proj, 'fix'), strict=False)
    assert not errors
    assert warnings
    assert not arc.plan(proj, 'fix')['ok']
    assert code('testplan', 'add', 'fix', '--location', 'app:tests/test_entry.py::test_first_row',
                '--covers', 'entry/R1/S1', '--by', 'gemini') == 0
    assert code('testplan', 'sign', 'fix', '--by', 'gemini') == 0
    assert code('task', 'set', 'fix', '1', '--tests', 'T1') == 0
    assert ev.explain(proj, 'fix')[0]['status'] == 'not-started'
    assert code('evidence', 'run', 'fix', '1') == 0
    assert arc.plan(proj, 'fix')['ok']


@pytest.mark.parametrize('command, executable, environment', [
    (r'.venv\Scripts\python.exe -m pytest', r'.venv\Scripts\python.exe', {}),
    (r'FLAG=yes C:\Python\python.exe -m pytest', r'C:\Python\python.exe', {'FLAG': 'yes'}),
    (r'FLAG="two words" "C:\Program Files\Python\python.exe" -m pytest',
     r'C:\Program Files\Python\python.exe', {'FLAG': 'two words'}),
    ("FLAG='two words' '/opt/with space/python' -m pytest", '/opt/with space/python', {'FLAG': 'two words'}),
])
def test_runner_preserves_windows_and_posix_paths(command, executable, environment):
    env, argv = ev._split_command('app', {'test-command': command})
    assert env == environment
    assert argv == [executable, '-m', 'pytest']


def test_windows_unquoted_executable_with_spaces_has_clear_error():
    with pytest.raises(io.SoftwareError, match='(?i)quot'):
        ev._split_command('app', {'test-command': r'C:\Program Files\Python\python.exe -m pytest'})


@pytest.mark.parametrize('suffix, expected', [
    (r'--label "say \"yes\""', ['--label', 'say "yes"']),
    (r'ordinary\ argument', ['ordinary argument']),
])
def test_windows_runner_preserves_posix_escaped_argument_semantics(suffix, expected):
    _env, argv = ev._split_command('app', {'test-command': r'C:\Python\python.exe -m pytest ' + suffix})
    assert argv == [r'C:\Python\python.exe', '-m', 'pytest', *expected]


def _decision_basis(proj):
    assert ruling.run(['add', '--quote', 'Use the selected behavior']) == 0
    assert decision.run(['add', '--title', 'behavior', '--statement', 'The chosen behavior',
                         '--based-on', 'RL-claude-1']) == 0
    assert decision.run(['activate', 'D-claude-1']) == 0
    spec = sp.load_spec(proj, 'entry')
    spec['requirements'][0]['based-on'] = ['gov:D-claude-1']
    sp.write_spec(proj, spec)


def test_rejected_ruling_traces_transitive_software_and_cannot_clear_away(proj):
    from dspx.commands.governance import impact
    _decision_basis(proj)
    _passing(proj)
    assert code('change', 'design', 'fix', '--decision', 'D-claude-1') == 0
    assert ruling.run(['reject', 'RL-claude-1', '--reason', 'Incorrectly recorded']) == 0
    suspects = [s for s in gv.load_governance(proj).suspects if s.get('status') == 'open']
    targets = {s['target'] for s in suspects}
    assert {'D-claude-1', 'req:entry/R1', 'swc:fix', 'task:fix#1', 'test:fix/T1'} <= targets
    for suspect in suspects:
        assert impact.run(['clear', suspect['id'], '--reason', 'Reviewed the impact']) == 0
    assert not arc.plan(proj, 'fix')['ok']


def test_rejected_ruling_marks_archived_work_without_rewriting_history(proj):
    _decision_basis(proj)
    _passing(proj)
    assert code('change', 'design', 'fix', '--decision', 'D-claude-1') == 0
    assert code('evidence', 'run', 'fix', '1') == 0
    assert code('archive', 'fix') == 0
    historic = {p: p.read_bytes() for p in io.archive_dir(proj).rglob('*') if p.is_file()}
    evidence = {p: p.read_bytes() for p in io.evidence_dir(proj).glob('*.yaml')}
    assert ruling.run(['reject', 'RL-claude-1', '--reason', 'Reconsider']) == 0
    assert chg.change_state(proj, 'fix') == 'archived'
    assert {p: p.read_bytes() for p in historic} == historic
    assert {p: p.read_bytes() for p in evidence} == evidence
    suspects = gv.load_governance(proj).suspects
    assert any(s.get('target') == 'task:fix#1' for s in suspects)


def test_legacy_active_evidence_is_readable_but_requires_reverification(proj):
    _passing(proj)
    latest = copy.deepcopy(ev.load_all(proj)[-1])
    # Keep exactly the fields written by the pre-upgrade engine.
    old_fields = {'id', 'type', 'change', 'task', 'recorded-by', 'at', 'repo', 'command',
                  'commit', 'environment', 'exit-code', 'counts', 'tests', 'result', 'files',
                  'output-tail', 'per-test', 'reason'}
    legacy = {k: v for k, v in latest.items() if k in old_fields}
    path = io.evidence_dir(proj) / (legacy['id'] + '.yaml')
    io.write(path, 'evidence', legacy)
    before = path.read_bytes()
    assert ev.explain(proj, 'fix')[0]['status'] != 'done'
    assert path.read_bytes() == before
    assert not arc.plan(proj, 'fix')['ok']
    assert code('evidence', 'run', 'fix', '1') == 0
    assert ev.explain(proj, 'fix')[0]['status'] == 'done'
    assert path.read_bytes() == before


def test_legacy_signoff_needs_test_role_resign(proj):
    _change('fix', run=False)
    ch = chg.load_change(proj, 'fix')
    signed = ch['tests']['tests'][0]['signed']
    ch['tests']['tests'][0]['signed'] = {k: v for k, v in signed.items()
                                      if k in ('by', 'at', 'fingerprint', 'test-fingerprint')}
    chg.write_part(proj, 'fix', 'tests', ch['tests'])
    assert code('evidence', 'run', 'fix', '1') == 1
    assert code('testplan', 'sign', 'fix', '--by', 'gemini') == 0
    assert code('evidence', 'run', 'fix', '1') == 0


def test_owner_reaccepts_current_version_before_archive(proj):
    assert code('change', 'new', 'layout', '--why', 'fix', '--modified', 'entry') == 0
    assert code('change', 'delta', 'layout', '--capability', 'entry', '--op', 'modify-requirement',
                '--ref', 'R2', '--statement', 'It MUST fit 1024px.') == 0
    assert code('task', 'add', 'layout', '--title', 'layout', '--implements', 'entry/R2',
                '--files', 'app:src/entry.py', '--verify', 'inspection') == 0
    assert code('evidence', 'accept', 'layout', '1', '--read-back', 'Version A', '--confirmed', 'Yes') == 0
    (proj.project_root / 'app/src/entry.py').write_text('X = 2\n', encoding='utf-8')
    assert code('evidence', 'add', 'layout', '1', '--type', 'inspection', '--subject', 'B',
                '--conclusion', 'Checked B', '--result', 'pass') == 0
    assert not arc.plan(proj, 'layout')['ok']
    assert code('evidence', 'accept', 'layout', '1', '--read-back', 'Version B', '--confirmed', 'Yes') == 0
    assert arc.plan(proj, 'layout')['ok']


def test_requirement_statement_change_requires_existing_scenario_evidence(proj):
    assert code('change', 'new', 'statement', '--why', 'revise', '--modified', 'entry') == 0
    assert code('change', 'delta', 'statement', '--capability', 'entry', '--op', 'modify-requirement',
                '--ref', 'R1', '--statement', 'It SHALL list every task.') == 0
    assert code('task', 'add', 'statement', '--title', 'inspect', '--implements', 'entry/R1',
                '--files', 'app:src/entry.py', '--verify', 'inspection') == 0
    assert code('evidence', 'add', 'statement', '1', '--type', 'inspection', '--subject', 'code',
                '--conclusion', 'Looks good', '--result', 'pass') == 0
    assert not arc.plan(proj, 'statement')['ok']


def test_allow_skips_policy_change_invalidates_previous_evidence(proj):
    _passing(proj)
    assert code('task', 'set', 'fix', '1', '--allow-skips', 'yes') == 0
    assert ev.explain(proj, 'fix')[0]['status'] != 'done'
    assert code('evidence', 'run', 'fix', '1') == 0
    assert ev.explain(proj, 'fix')[0]['status'] == 'done'


def test_one_shared_test_covers_two_required_scenarios_with_one_run(proj):
    _change('fix', run=False)
    assert code('change', 'delta', 'fix', '--capability', 'entry', '--op', 'add-scenario',
                '--ref', 'R1', '--title', 'Second', '--when', 'Other input', '--then', 'Same valid result') == 0
    assert code('testplan', 'set', 'fix', 'T1', '--covers', 'entry/R1/S1,entry/R1/S2', '--by', 'gemini') == 0
    assert code('testplan', 'sign', 'fix', '--by', 'gemini') == 0
    assert code('evidence', 'run', 'fix', '1') == 0
    assert code('archive', 'fix') == 0
    assert len(ev.load_all(proj)) == 1
    for scenario in sp.load_spec(proj, 'entry')['requirements'][0]['scenarios']:
        assert scenario['verified-by'] == ['app:tests/test_entry.py::test_first_row']


def test_owner_acceptance_covers_other_tasks_implementing_same_requirement(proj):
    second_file = proj.project_root / 'app/src/other.py'
    second_file.write_text('WIDTH = 1024\n', encoding='utf-8')
    assert code('change', 'new', 'layout', '--why', 'fix', '--modified', 'entry') == 0
    assert code('change', 'delta', 'layout', '--capability', 'entry', '--op', 'modify-requirement',
                '--ref', 'R2', '--statement', 'It MUST fit 1024px.') == 0
    for title, path in [('first', 'entry.py'), ('second', 'other.py')]:
        assert code('task', 'add', 'layout', '--title', title, '--implements', 'entry/R2',
                    '--files', 'app:src/' + path, '--verify', 'inspection') == 0
    assert code('evidence', 'add', 'layout', '2', '--type', 'inspection', '--subject', 'Second',
                '--conclusion', 'Initial checked', '--result', 'pass') == 0
    assert code('evidence', 'accept', 'layout', '1', '--read-back', 'Both tasks accepted', '--confirmed', 'Yes') == 0
    assert arc.plan(proj, 'layout')['ok']
    second_file.write_text('WIDTH = 2048\n', encoding='utf-8')
    assert code('evidence', 'add', 'layout', '2', '--type', 'inspection', '--subject', 'Second',
                '--conclusion', 'New content checked', '--result', 'pass') == 0
    assert not arc.plan(proj, 'layout')['ok']
    assert code('evidence', 'accept', 'layout', '1', '--read-back', 'Both updated tasks accepted', '--confirmed', 'Yes') == 0
    assert arc.plan(proj, 'layout')['ok']


@pytest.mark.parametrize('with_delta', [True, False])
def test_imported_done_without_test_evidence_cannot_archive(proj, with_delta):
    _change('fix', run=False)
    if not with_delta:
        assert code('change', 'undelta', 'fix', '--capability', 'entry', '--ref', 'R1/S1') == 0
    ch = chg.load_change(proj, 'fix')
    ch['tasks']['tasks'][0]['status'] = 'imported-done'
    chg.write_part(proj, 'fix', 'tasks', ch['tasks'])
    assert not arc.plan(proj, 'fix')['ok']


def test_native_runner_executable_path_with_spaces_and_environment(proj, tmp_path):
    """A real interpreter in a spaced directory, not only a parser simulation."""
    import os
    from pathlib import Path
    import venv
    interpreter_home = tmp_path / 'Python with spaces'
    venv.EnvBuilder(with_pip=False).create(interpreter_home)
    executable = interpreter_home / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    package_dir = Path(pytest.__file__).resolve().parent.parent
    command = f'PYTHONPATH="{package_dir}" DOCSPEC_TEST_WORDS="two words" "{executable}" -m pytest -q -p no:cacheprovider'
    _config(proj, command)
    test_file = proj.project_root / 'app/tests/test_entry.py'
    test_file.write_text('import os\n\ndef test_first_row():\n    assert os.environ["DOCSPEC_TEST_WORDS"] == "two words"\n',
                         encoding='utf-8')
    _change('fix', run=False)
    assert code('evidence', 'run', 'fix', '1') == 0
    record = ev.load_all(proj)[-1]
    assert record['result'] == 'pass' and record['counts']['passed'] == 1
    assert ev.explain(proj, 'fix')[0]['status'] == 'done'


@pytest.mark.parametrize('archived', [False, True])
def test_nested_capability_ruling_impact_reaches_tests_and_tasks(proj, archived):
    _decision_basis(proj)
    nested = sp.load_spec(proj, 'entry')
    nested['capability'] = 'ui/entry'
    sp.write_spec(proj, nested)
    assert code('change', 'new', 'nested', '--why', 'Nested behavior', '--modified', 'ui/entry') == 0
    assert code('change', 'delta', 'nested', '--capability', 'ui/entry', '--op', 'modify-scenario',
                '--ref', 'R1/S1', '--then', 'Complete nested result') == 0
    assert code('testplan', 'add', 'nested', '--location', 'app:tests/test_entry.py::test_first_row',
                '--covers', 'ui/entry/R1/S1', '--by', 'gemini') == 0
    assert code('testplan', 'sign', 'nested', '--by', 'gemini') == 0
    assert code('task', 'add', 'nested', '--title', 'Nested implementation', '--implements', 'ui/entry/R1',
                '--files', 'app:src/entry.py', '--verify', 'test', '--tests', 'T1') == 0
    before = {}
    if archived:
        assert code('evidence', 'run', 'nested', '1') == 0
        assert code('archive', 'nested') == 0
        before = {p: p.read_bytes() for p in io.archive_dir(proj).rglob('*') if p.is_file()}
    assert ruling.run(['reject', 'RL-claude-1', '--reason', 'Reject nested basis']) == 0
    targets = {s['target'] for s in gv.load_governance(proj).suspects if s.get('status') == 'open'}
    assert {'req:ui/entry/R1', 'task:nested#1'} <= targets
    if archived:
        assert 'test:app:tests/test_entry.py::test_first_row' in targets
        assert {p: p.read_bytes() for p in before} == before
    else:
        assert 'test:nested/T1' in targets


def test_implementation_only_change_still_requires_current_owner_acceptance(proj):
    assert code('change', 'new', 'implementation', '--why', 'Fix implementation', '--modified', 'entry') == 0
    assert code('task', 'add', 'implementation', '--title', 'Layout implementation',
                '--implements', 'entry/R2', '--files', 'app:src/entry.py', '--verify', 'inspection') == 0
    def inspect():
        assert code('evidence', 'add', 'implementation', '1', '--type', 'inspection',
                    '--subject', 'Layout', '--conclusion', 'Inspected current layout', '--result', 'pass') == 0
    def accept():
        assert code('evidence', 'accept', 'implementation', '1', '--read-back', 'Current layout reviewed',
                    '--confirmed', 'Accepted') == 0
    inspect()
    assert not arc.plan(proj, 'implementation')['ok']
    accept()
    assert arc.plan(proj, 'implementation')['ok']
    (proj.project_root / 'app/src/entry.py').write_text('X = 2\n', encoding='utf-8')
    inspect()
    assert not arc.plan(proj, 'implementation')['ok']
    accept()
    assert arc.plan(proj, 'implementation')['ok']


def test_stale_test_and_latest_failed_inspection_are_both_explained(proj):
    _change('fix', run=False)
    assert code('task', 'set', 'fix', '1', '--verify', 'test,inspection') == 0
    assert code('evidence', 'run', 'fix', '1') == 0
    assert code('evidence', 'add', 'fix', '1', '--type', 'inspection', '--subject', 'Version A',
                '--conclusion', 'Looks correct', '--result', 'pass') == 0
    assert ev.explain(proj, 'fix')[0]['status'] == 'done'
    (proj.project_root / 'app/src/entry.py').write_text('X = 2\n', encoding='utf-8')
    assert code('evidence', 'add', 'fix', '1', '--type', 'inspection', '--subject', 'Version B',
                '--conclusion', 'Layout is wrong', '--result', 'fail') == 1
    latest = ev.for_task(ev.load_all(proj), 'fix', '1')[-1]
    explained = ev.explain(proj, 'fix')[0]
    assert explained['status'] not in ('done', 'done-waived')
    assert 'stale' in explained['why']
    assert latest['id'] in explained['why'] and 'fail' in explained['why']


def test_implementation_only_test_requirement_cannot_use_analysis_instead(proj):
    assert code('change', 'new', 'implementation', '--why', 'Fix implementation', '--modified', 'entry') == 0
    assert code('task', 'add', 'implementation', '--title', 'Implement behavior',
                '--implements', 'entry/R1', '--files', 'app:src/entry.py', '--verify', 'analysis') == 0
    assert code('evidence', 'add', 'implementation', '1', '--type', 'analysis', '--subject', 'Behavior',
                '--conclusion', 'Reasoned about it', '--result', 'pass') == 0
    assert not arc.plan(proj, 'implementation')['ok']


def test_scope_records_explain_original_local_contract_without_rewriting_history(proj):
    _passing(proj)
    record = ev.load_all(proj)[-1]
    contract = record['scope']
    serialized = json.dumps(contract, ensure_ascii=False)
    assert '第一列完整可見' in serialized
    assert 'app:tests/test_entry.py::test_first_row' in serialized
    assert 'It MUST fit.' not in serialized             # Unrelated R2 must not contaminate the local scope.
    path = io.evidence_dir(proj) / (record['id'] + '.yaml')
    original = path.read_bytes()
    assert code('change', 'undelta', 'fix', '--capability', 'entry', '--ref', 'R1/S1') == 0
    assert code('change', 'delta', 'fix', '--capability', 'entry', '--op', 'modify-scenario',
                '--ref', 'R1/S1', '--then', 'A new outcome') == 0
    assert ev.explain(proj, 'fix')[0]['status'] != 'done'
    assert path.read_bytes() == original
