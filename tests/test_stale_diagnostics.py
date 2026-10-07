"""Stale-state explanations are factual, backwards compatible and read-only."""

import hashlib
import copy
import json
import os
from collections import Counter

import pytest
import yaml

from test_software_archive import proj, _change, code
from dspx.commands.governance import handover, roadmap, ruling, decision
from dspx.engine import governance as gv, handover as ho
from dspx.engine.software import changes as chg, evidence as ev, io, scope


def _bytes(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob('*') if p.is_file()}


def _json(capsys):
    capsys.readouterr()
    assert handover.run(['--json']) == 0
    return json.loads(capsys.readouterr().out)


def _save_note(proj, note):
    ho.path(proj).write_text(gv.dump_record('handover', note), encoding='utf-8')


def test_manifest_preserves_existing_fingerprint_algorithm_and_records_only_hashes(proj):
    assert handover.run(['write', '--next', 'Continue']) == 0
    note = ho.load(proj)
    manifest = note['state-manifest']
    assert manifest['version'] == 1
    expected_files = {p.relative_to(proj.project_root).as_posix():
                      'sha256:' + hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in ho._managed_files(proj)}
    assert manifest['files'] == expected_files
    digest = hashlib.sha256(b'handover-state-v1\n')
    for name, fingerprint in sorted(expected_files.items()):
        encoded = name.encode('utf-8')
        digest.update(len(encoded).to_bytes(8, 'big'))
        digest.update(encoded)
        digest.update(bytes.fromhex(fingerprint.removeprefix('sha256:')))
    assert note['state-fingerprint'] == 'sha256:' + digest.hexdigest()
    assert ho.path(proj).relative_to(proj.project_root).as_posix() not in manifest['files']


def test_added_modified_removed_paths_match_json_text_and_rewrite_recovers(proj, capsys):
    old = proj.planning_home / 'old-context.md'
    old.write_text('Original context', encoding='utf-8')
    assert handover.run(['write', '--next', 'Continue']) == 0
    old.unlink()
    new = proj.planning_home / 'new-context.md'
    new.write_text('New context', encoding='utf-8')
    config = io.config_path(proj)
    config.write_text(config.read_text(encoding='utf-8') + '\n# changed context\n', encoding='utf-8')
    before = _bytes(proj.project_root)
    fresh = _json(capsys)['freshness']
    expected = sorted([{'path': p.relative_to(proj.project_root).as_posix(), 'kind': kind}
                       for p, kind in [(old, 'removed'), (new, 'added'), (config, 'modified')]],
                      key=lambda x: x['path'])
    assert fresh['status'] == 'stale'
    assert fresh['changes-available'] is True
    assert fresh['changes'] == expected
    assert handover.run([]) == 0
    output = capsys.readouterr().out
    for change in expected:
        assert change['path'] in output
        assert change['kind'] in output
    assert _bytes(proj.project_root) == before
    assert handover.run(['write', '--next', 'Reviewed changed context']) == 0
    rewritten = _json(capsys)
    assert rewritten['freshness']['status'] == 'current'
    assert rewritten['freshness']['changes-available'] is True
    assert rewritten['freshness']['changes'] == []
    assert old.relative_to(proj.project_root).as_posix() not in rewritten['note']['state-manifest']['files']


@pytest.mark.parametrize('changed', [False, True])
def test_legacy_fingerprint_still_compares_without_inventing_change_details(proj, capsys, changed):
    assert handover.run(['write', '--next', 'Old note']) == 0
    note = ho.load(proj)
    note.pop('state-manifest', None)
    _save_note(proj, note)
    if changed:
        assert ruling.run(['add', '--quote', 'New direction']) == 0
    fresh = _json(capsys)['freshness']
    assert fresh['status'] == ('stale' if changed else 'current')
    assert fresh['changes-available'] is False
    assert fresh['changes'] == []
    assert handover.run([]) == 0
    output = capsys.readouterr().out.lower()
    assert '無法列出' in output or 'unavailable' in output


def test_mtime_and_external_repo_content_do_not_create_manifest_changes(proj, capsys):
    assert handover.run(['write', '--next', 'Continue']) == 0
    before = _bytes(proj.planning_home)
    for p in ho._managed_files(proj):
        os.utime(p, (1000000000, 1000000000))
    (proj.project_root / 'app/src/entry.py').write_text('X = 400\n', encoding='utf-8')
    fresh = _json(capsys)['freshness']
    assert fresh['status'] == 'current'
    assert fresh['changes-available'] is True
    assert fresh['changes'] == []
    assert _bytes(proj.planning_home) == before


@pytest.mark.parametrize('action', ['write', 'read'])
def test_manifest_and_overall_digest_use_one_checked_read_per_file(proj, monkeypatch, action):
    if action == 'read':
        assert handover.run(['write', '--next', 'Continue']) == 0
    original = ho._checked_content
    calls = Counter()
    def counted(p, *args, **kwargs):
        calls[p] += 1
        return original(p, *args, **kwargs)
    monkeypatch.setattr(ho, '_checked_content', counted)
    if action == 'write':
        assert handover.run(['write', '--next', 'Continue']) == 0
        assert 'state-manifest' in ho.load(proj)
    else:
        result = ho.freshness(proj, ho.load(proj))
        assert result['changes-available'] is True
    assert calls == Counter({p: 1 for p in ho._managed_files(proj)})


def test_broken_managed_seal_reports_unknown_without_fabricated_details(proj, capsys):
    assert ruling.run(['add', '--quote', 'Original direction']) == 0
    assert handover.run(['write', '--next', 'Continue']) == 0
    record = next(gv.gov_dir(proj).rglob('RL-*.yaml'))
    record.write_text(record.read_text(encoding='utf-8').replace('Original direction', 'Tampered direction'),
                      encoding='utf-8')
    before = _bytes(proj.planning_home)
    fresh = _json(capsys)['freshness']
    assert fresh['status'] == 'unknown'
    assert fresh['changes-available'] is False
    assert fresh['changes'] == []
    assert _bytes(proj.planning_home) == before


@pytest.mark.parametrize('field, expected', [
    ('statement', ('entry/R1', 'statement')),
    ('scenario', ('entry/R1/S1', 'scenario')),
    ('based-on', ('entry/R1', 'based-on', 'D-claude-99')),
    ('tests', ('T1', 'tests')),
    ('methods', ('methods', 'inspection')),
    ('runners', ('app', 'runners')),
    ('files', ('files', 'app:src/additional.py')),
])
def test_scope_explanation_identifies_changed_contract_field_and_reference(proj, field, expected):
    _change('fix', run=False)
    ch = chg.load_change(proj, 'fix')
    task = ch['tasks']['tasks'][0]
    saved = {'scope': scope.task_scope(proj, ch, task)}
    if field == 'statement':
        assert code('change', 'delta', 'fix', '--capability', 'entry', '--op', 'modify-requirement',
                    '--ref', 'R1', '--statement', 'It SHALL show the selected tasks.') == 0
        ch = chg.load_change(proj, 'fix')
    elif field == 'scenario':
        assert code('change', 'undelta', 'fix', '--capability', 'entry', '--ref', 'R1/S1') == 0
        assert code('change', 'delta', 'fix', '--capability', 'entry', '--op', 'modify-scenario',
                    '--ref', 'R1/S1', '--then', 'The selected first task is shown') == 0
        ch = chg.load_change(proj, 'fix')
    elif field == 'based-on':
        from dspx.engine.software import specs
        spec = specs.load_spec(proj, 'entry')
        spec['requirements'][0]['based-on'] = ['D-claude-99']
        specs.write_spec(proj, spec)
    elif field == 'tests':
        ch['tests']['tests'][0]['location'] = 'app:tests/test_entry.py::test_width'
    elif field == 'methods':
        task['verify']['methods'].append('inspection')
    elif field == 'runners':
        config = yaml.safe_load(io.config_path(proj).read_text(encoding='utf-8'))
        config['repos']['app']['test-command'] += ' -x'
        io.config_path(proj).write_text(yaml.safe_dump(config), encoding='utf-8')
    else:
        task['files'].append('app:src/additional.py')
    before = _bytes(proj.planning_home)
    why = ev.scope_problem(proj, ch, task, saved)
    assert why is not None
    for word in expected:
        assert word.lower() in why.lower()
    assert _bytes(proj.planning_home) == before


def test_scope_ignores_unrelated_requirements_and_presentation_titles(proj):
    _change('fix', run=False)
    ch = chg.load_change(proj, 'fix')
    task = ch['tasks']['tasks'][0]
    saved = {'scope': scope.task_scope(proj, ch, task)}
    assert code('change', 'delta', 'fix', '--capability', 'entry', '--op', 'modify-requirement',
                '--ref', 'R2', '--statement', 'It MUST fit 2048px.') == 0
    assert code('change', 'delta', 'fix', '--capability', 'entry', '--op', 'rename-requirement',
                '--ref', 'R1', '--title', 'A presentation-only title') == 0
    assert ev.scope_problem(proj, chg.load_change(proj, 'fix'), task, saved) is None


def test_legacy_scope_explanation_remains_actionable(proj):
    _change('fix', run=False)
    ch = chg.load_change(proj, 'fix')
    why = ev.scope_problem(proj, ch, ch['tasks']['tasks'][0], {})
    assert 'legacy' in why and 'rerun' in why


def test_stale_evidence_reason_flows_to_roadmap_text_and_json_without_writes(proj, capsys):
    _change('fix')
    assert ruling.run(['add', '--quote', 'Implement this change']) == 0
    assert roadmap.run(['add', '--title', 'Implementation', '--ref', 'swc:fix']) == 0
    assert code('change', 'delta', 'fix', '--capability', 'entry', '--op', 'modify-requirement',
                '--ref', 'R1', '--statement', 'It SHALL display only the selected tasks.') == 0
    before = _bytes(proj.planning_home)
    row = ev.explain(proj, 'fix')[0]
    assert row['status'] == 'needs-rerun'
    assert 'entry/R1' in row['why'] and 'statement' in row['why']
    capsys.readouterr()
    assert roadmap.run(['--json']) == 0
    details = json.loads(capsys.readouterr().out)['unassigned'][0]['details']
    assert any(row['why'] in detail for detail in details)
    assert roadmap.run([]) == 0
    output = capsys.readouterr().out
    assert row['why'] in output
    assert _bytes(proj.planning_home) == before


@pytest.mark.parametrize('changed', [False, True])
@pytest.mark.parametrize('damage', ['version', 'files-type', 'path', 'hash', 'inconsistent'])
def test_unusable_manifest_keeps_aggregate_judgment_and_reports_unavailable(proj, capsys, changed, damage):
    assert handover.run(['write', '--next', 'Continue']) == 0
    note = ho.load(proj)
    manifest = note['state-manifest']
    name = next(iter(manifest['files']))
    if damage == 'version':
        manifest['version'] = 999
    elif damage == 'files-type':
        manifest['files'] = ['not a mapping']
    elif damage == 'path':
        manifest['files']['../outside.txt'] = manifest['files'].pop(name)
    elif damage == 'hash':
        manifest['files'][name] = 'sha256:invalid'
    else:
        manifest['files'][name] = 'sha256:' + '0' * 64
    _save_note(proj, note)
    if changed:
        assert ruling.run(['add', '--quote', 'A later direction']) == 0
    before = _bytes(proj.planning_home)
    fresh = _json(capsys)['freshness']
    assert fresh['status'] == ('stale' if changed else 'current')
    assert fresh['changes-available'] is False
    assert fresh['changes'] == []
    assert handover.run([]) == 0
    assert fresh['changes-reason'] in capsys.readouterr().out
    assert _bytes(proj.planning_home) == before


def test_unreadable_record_discards_partial_manifest_and_can_still_write_note(proj, monkeypatch):
    assert handover.run(['write', '--next', 'Original next step']) == 0
    from pathlib import Path
    original = Path.read_bytes
    def denied(path):
        if path == io.config_path(proj):
            raise PermissionError('synthetic access failure')
        return original(path)
    monkeypatch.setattr(Path, 'read_bytes', denied)
    fresh = ho.freshness(proj, ho.load(proj))
    assert fresh['status'] == 'unknown'
    assert fresh['changes-available'] is False and fresh['changes'] == []
    assert handover.run(['write', '--next', 'Repair the unreadable configuration']) == 0
    note = ho.load(proj)
    assert 'state-manifest' not in note and 'state-fingerprint' not in note
    assert note['next'] == ['Repair the unreadable configuration']
    assert 'state-error' in note


@pytest.mark.parametrize('damage', ['unsupported', 'nonmapping', 'missing-contract', 'partial-contract'])
def test_uncomparable_scope_uses_generic_reason_without_inventing_differences(proj, damage):
    _change('fix', run=False)
    ch = chg.load_change(proj, 'fix')
    task = ch['tasks']['tasks'][0]
    old = scope.task_scope(proj, ch, task)
    if damage == 'unsupported':
        old['version'] = 999
    elif damage == 'nonmapping':
        old = 'old format'
    elif damage == 'missing-contract':
        old.pop('contract')
    else:
        old['contract'] = {'methods': ['test']}
    why = ev.scope_problem(proj, ch, task, {'scope': old})
    assert why == 'verification scope changed; review test sign-off and rerun evidence'


@pytest.mark.parametrize('kind, identifier', [('requirements', 'entry/R2'),
                                             ('scenarios', 'entry/R1/S2'), ('tests', 'T2')])
@pytest.mark.parametrize('operation', ['added', 'removed'])
def test_scope_collection_changes_name_the_affected_record(proj, kind, identifier, operation):
    _change('fix', run=False)
    ch = chg.load_change(proj, 'fix')
    old = scope.task_scope(proj, ch, ch['tasks']['tasks'][0])
    new = copy.deepcopy(old)
    if kind == 'requirements':
        new['contract'][kind].append(scope.requirement(proj, ch, 'entry/R2'))
    elif kind == 'scenarios':
        new['contract']['requirements'][0][kind].append({'id': 'S2', 'when': 'another input', 'then': 'another result'})
    else:
        new['contract'][kind].append({'id': 'T2', 'location': 'app:tests/test_entry.py::test_width',
                                      'covers': ['entry/R1/S1']})
    new = scope.seal(new['contract'])
    if operation == 'removed':
        old, new = new, old
    reason = '; '.join(scope.differences(old, new))
    assert identifier in reason
    assert kind.rstrip('s') in reason
    assert 'another input' not in reason and 'another result' not in reason


def test_changed_decision_body_is_identified_by_reference_without_quoting_owner(proj):
    assert ruling.run(['add', '--quote', 'Synthetic owner design direction']) == 0
    assert decision.run(['add', '--title', 'Design', '--statement', 'Synthetic private decision statement',
                         '--based-on', 'RL-claude-1']) == 0
    assert decision.run(['activate', 'D-claude-1']) == 0
    _change('fix', run=False)
    assert code('change', 'design', 'fix', '--decision', 'D-claude-1') == 0
    ch = chg.load_change(proj, 'fix')
    task = ch['tasks']['tasks'][0]
    saved = {'scope': scope.task_scope(proj, ch, task)}
    assert decision.run(['withdraw', 'D-claude-1']) == 0
    why = ev.scope_problem(proj, ch, task, saved)
    assert 'decisions' in why and 'D-claude-1' in why
    assert 'Synthetic private decision statement' not in why


@pytest.mark.parametrize('language', ['zh-TW', 'en'])
def test_generated_rules_include_operating_constraints_and_refresh_old_copies(tmp_path, monkeypatch, capsys, language):
    from dspx.commands.maintenance import init, _skills
    from dspx.env.skills import available_skills
    monkeypatch.chdir(tmp_path)
    args = ['--tool', 'codex', '--agents-md', '--lang', language, '--no-tex-hint', '--no-update-check']
    assert init.run(args) == 0
    rules = tmp_path / 'AGENTS.md'
    text = rules.read_text(encoding='utf-8')
    words = (('誰操作', '使用平台', '啟動方式', '安裝限制', '連線／離線限制', '交付方式',
              '只有缺漏且影響設計時才詢問', '不新增必填表單') if language == 'zh-TW' else
             ('who will operate', 'platform', 'startup method', 'installation restrictions',
              'network/offline restrictions', 'delivery method', 'ask only about missing', 'not a new mandatory form'))
    assert all(word in text for word in words)
    propose = next(skill for skill in available_skills() if skill.name == 'dspx-propose')
    installed = tmp_path / '.agents/skills/dspx-propose/SKILL.md'
    assert installed.read_text(encoding='utf-8') == propose.text
    assert 'network/offline restrictions' in propose.body
    assert _skills.outdated_installs(tmp_path) == []
    rules.write_text(text.replace(words[0], 'old workflow'), encoding='utf-8')
    old_propose = copy.deepcopy(propose)
    old_propose.frontmatter['metadata']['version'] = '1.1'
    installed.write_text(old_propose.text, encoding='utf-8')
    capsys.readouterr()
    assert handover.run([]) == 0
    warning = capsys.readouterr().err
    assert 'AGENTS.md' in warning and 'dspx-propose' in warning and 'artispec init --agents-md' in warning
    assert init.run(args) == 0
    assert _skills.outdated_installs(tmp_path) == []


def test_missing_note_does_not_hide_broken_governance_in_text(proj, capsys):
    record = gv.record_path(proj, 'question', 'Q-claude-1')
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text('invalid: true\n', encoding='utf-8')
    before = _bytes(proj.planning_home)
    data = _json(capsys)
    assert data['note'] is None
    assert data['freshness']['status'] == 'unknown'
    assert data['pending-questions'] is None
    assert 'pending-questions-error' in data
    assert handover.run([]) == 0
    assert data['freshness']['reason'] in capsys.readouterr().out
    assert _bytes(proj.planning_home) == before


def test_missing_note_without_broken_records_does_not_print_failure_warning(proj, capsys):
    data = _json(capsys)
    assert data['note'] is None and data['freshness']['status'] == 'unknown'
    assert data['pending-questions'] == 0
    assert handover.run([]) == 0
    assert '⚠' not in capsys.readouterr().out
