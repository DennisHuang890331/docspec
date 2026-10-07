"""A successor can inspect per-test sign-off without editing records or running tests."""

import json
import subprocess

import pytest

from test_software_archive import proj, _change, code
from dspx.engine.software import changes as chg, evidence as ev, io, tasks as tk


def _bytes(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob('*') if p.is_file()}


def _list(proj, capsys, monkeypatch):
    original = chg.load_change(proj, 'fix')['tests']
    before = _bytes(proj.project_root)
    def forbidden(*args, **kwargs):
        raise AssertionError('Listing sign-off must not execute a test or command')
    monkeypatch.setattr(subprocess, 'run', forbidden)
    capsys.readouterr()
    assert code('testplan', 'list', 'fix', '--json') == 0
    data = json.loads(capsys.readouterr().out)
    for key, value in original.items():
        assert data[key] == value
    assert code('testplan', 'list', 'fix') == 0
    text = capsys.readouterr().out
    for row in data['signoffs']:
        assert str(row['test']) in text
        assert 'sign-off: ' + row['status'] in text
        for reason in row['problems']:
            assert reason in text
    assert _bytes(proj.project_root) == before
    return data['signoffs']


def test_list_distinguishes_current_and_unsigned_tests_without_altering_original_json(proj, capsys, monkeypatch):
    _change('fix', run=False)
    assert code('testplan', 'add', 'fix', '--location', 'app:tests/test_entry.py::test_width',
                '--covers', 'entry/R1/S1', '--by', 'gemini') == 0
    ch = chg.load_change(proj, 'fix')
    rows = _list(proj, capsys, monkeypatch)
    assert rows == [
        {'test': 'T1', 'status': 'current', 'problems': []},
        {'test': 'T2', 'status': 'unsigned',
         'problems': ev.signoff_problems(proj, [ch['tests']['tests'][1]], ch)},
    ]


@pytest.mark.parametrize('change', ['test-body', 'scenario', 'legacy'])
def test_list_explains_signoff_needing_review(proj, capsys, monkeypatch, change):
    _change('fix', run=False)
    if change == 'test-body':
        test = proj.project_root / 'app/tests/test_entry.py'
        test.write_text(test.read_text(encoding='utf-8').replace('assert True', 'assert False', 1), encoding='utf-8')
    elif change == 'scenario':
        assert code('change', 'undelta', 'fix', '--capability', 'entry', '--ref', 'R1/S1') == 0
        assert code('change', 'delta', 'fix', '--capability', 'entry', '--op', 'modify-scenario',
                    '--ref', 'R1/S1', '--then', 'A changed expected behavior') == 0
    else:
        ch = chg.load_change(proj, 'fix')
        ch['tests']['tests'][0]['signed'].pop('scenario-fingerprint')
        chg.write_part(proj, 'fix', 'tests', ch['tests'])
    ch = chg.load_change(proj, 'fix')
    problems = ev.signoff_problems(proj, ch['tests']['tests'], ch)
    assert problems
    assert _list(proj, capsys, monkeypatch) == [
        {'test': 'T1', 'status': 'needs-review', 'problems': problems},
    ]


@pytest.mark.parametrize('exception', [PermissionError, UnicodeError, io.SoftwareError])
def test_list_reports_unknown_when_signed_test_cannot_be_read(proj, capsys, monkeypatch, exception):
    _change('fix', run=False)
    def unavailable(*args, **kwargs):
        raise exception('synthetic signed-test read failure')
    monkeypatch.setattr(tk, 'test_fingerprint', unavailable)
    rows = _list(proj, capsys, monkeypatch)
    assert len(rows) == 1
    assert rows[0]['test'] == 'T1' and rows[0]['status'] == 'unknown'
    assert any('synthetic signed-test read failure' in reason for reason in rows[0]['problems'])


def test_list_keeps_signed_test_current_when_only_another_test_body_changes(proj, capsys, monkeypatch):
    _change('fix', run=False)
    test = proj.project_root / 'app/tests/test_entry.py'
    content = test.read_text(encoding='utf-8')
    test.write_text(content.replace('def test_width():\n    assert True',
                                    'def test_width():\n    assert False'), encoding='utf-8')
    assert _list(proj, capsys, monkeypatch) == [
        {'test': 'T1', 'status': 'current', 'problems': []},
    ]
