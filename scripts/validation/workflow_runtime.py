"""Evaluator-side UTF-8 recording and verified artifact checkpoints.

These helpers do not decide product completion. Keep evaluator records outside
participant projects and stop all writers before taking a checkpoint.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import errno
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import subprocess
import time


class ValidationError(RuntimeError):
    """Missing or inconsistent evaluator evidence; never a passing result."""


@contextmanager
def _recording_lock(log, *, timeout=30):
    """Protect complete JSONL records across processes, only while appending.

    Keep the sidecar in place: unlinking it while another process waits would
    create two independently locked files. OS handles release the lock on exit.
    """
    with Path(str(log) + '.lock').open('a+b') as stream:
        if stream.seek(0, os.SEEK_END) == 0:
            stream.write(b'\0')
            stream.flush()
        if os.name == 'nt':
            import msvcrt

            def acquire():
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)

            def release():
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            def acquire():
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

            def release():
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

        deadline = time.monotonic() + timeout
        while True:
            try:
                acquire()
                break
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                    raise ValidationError(f'cannot lock command log: {log}') from exc
                if time.monotonic() >= deadline:
                    raise ValidationError(f'timed out locking command log: {log}') from exc
                time.sleep(0.01)
        try:
            yield
        finally:
            release()


def record_command(argv, *, cwd, log, phase, session, env=None, input=None, metadata=None):
    command = [str(arg) for arg in argv]
    if not command:
        raise ValidationError('a command is required')
    environment = dict(os.environ)
    for key, value in (env or {}).items():
        if value is None:
            environment.pop(key, None)
        else:
            environment[key] = value
    environment['PYTHONUTF8'] = '1'
    started = time.monotonic()
    try:
        result = subprocess.run(command, cwd=cwd, env=environment, input=input,
                                capture_output=True, encoding='utf-8', errors='replace')
        code, out, err = result.returncode, result.stdout, result.stderr
    except OSError as exc:
        code, out, err = 127, '', str(exc) + '\n'
    event = {'time': datetime.now(timezone.utc).isoformat(), 'command': command,
             'argv': command, 'cwd': str(cwd), 'exit': code, 'stdout': out,
             'stderr': err, 'phase': phase, 'session': session,
             'elapsed': time.monotonic() - started}
    if metadata:
        if set(metadata) & set(event):
            raise ValidationError('metadata must not replace recorded execution facts')
        event.update(metadata)
    log = Path(log)
    log.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(event, ensure_ascii=False) + '\n').encode('utf-8')
    with _recording_lock(log):
        with log.open('ab') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    return event


def parse_codex_events(path):
    path = Path(path)
    result = {'acquisition': 'incomplete', 'session': None, 'events': [], 'diagnostics': []}
    if not path.is_file():
        result.update(acquisition='missing', diagnostics=['shell event file unavailable'])
        return result
    sessions, commands = set(), {}
    finished = False
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except (OSError, UnicodeError) as exc:
        result['diagnostics'].append(f'cannot read shell events: {exc}')
        return result
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            result['diagnostics'].append(f'malformed JSON at line {line_number}')
            continue
        if not isinstance(row, dict):
            result['diagnostics'].append(f'unknown event at line {line_number}')
            continue
        kind = row.get('type')
        if kind == 'thread.started' and isinstance(row.get('thread_id'), str):
            sessions.add(row['thread_id'])
        elif kind == 'turn.completed':
            finished = True
        elif kind in ('turn.failed', 'error'):
            result['diagnostics'].append(f'{kind} at line {line_number}')
        elif kind in ('item.started', 'item.updated', 'item.completed'):
            item = row.get('item')
            if not isinstance(item, dict) or item.get('type') != 'command_execution':
                continue
            identifier = item.get('id')
            if not isinstance(identifier, str) or not isinstance(item.get('command'), str):
                result['diagnostics'].append(f'incomplete command metadata at line {line_number}')
                continue
            previous = commands.get(identifier)
            if previous and previous['status'] == 'completed':
                if kind == 'item.completed' and (
                        previous['command'] != item['command'] or previous['exit'] != item.get('exit_code')):
                    result['diagnostics'].append(f'conflicting completed command {identifier}')
                continue
            commands[identifier] = {'id': identifier, 'command': item['command'],
                                    'status': 'completed' if kind == 'item.completed' else 'in_progress',
                                    'exit': item.get('exit_code'),
                                    'stdout': item.get('aggregated_output', '')}
        elif kind != 'turn.started':
            result['diagnostics'].append(f'unknown event type at line {line_number}: {kind}')
    if len(sessions) == 1:
        result['session'] = next(iter(sessions))
    else:
        result['diagnostics'].append('missing or conflicting actual session ids')
    for command in commands.values():
        if command['status'] == 'completed' and isinstance(command['exit'], int):
            result['events'].append(command)
        else:
            result['diagnostics'].append(f"command result unavailable: {command['id']}")
    if not finished:
        result['diagnostics'].append('turn completion unavailable')
    if not commands:
        result['diagnostics'].append('no supported shell events acquired; shell history not proven complete')
    if not result['diagnostics']:
        result['acquisition'] = 'complete'
    return result


def resolve_source(location, *, case_root, cwd=None, mappings=None):
    root = Path(case_root).resolve()
    name = str(location).strip().strip('`"')
    name = re.sub(r'(?:\s+L\d+(?:[-:]\d+)?|:\d+(?::\d+)?)$', '', name).strip()
    name = name.replace('\\', '/')
    candidates = []
    for prefix, target in (mappings or {}).items():
        prefix = str(prefix).replace('\\', '/').rstrip('/')
        if name == prefix or name.startswith(prefix + '/'):
            candidates.append(Path(target) / name[len(prefix):].lstrip('/'))
    if not candidates:
        path = Path(name)
        if path.is_absolute() or PureWindowsPath(name).is_absolute():
            candidates.append(path)
        else:
            if cwd is not None:
                candidates.append(Path(cwd) / path)
            candidates.append(root / path)
    matches = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if not candidate.is_relative_to(root):
            raise ValidationError(f'source leaves declared case: {location}')
        if candidate.is_file():
            matches.add(candidate)
    if len(matches) != 1:
        raise ValidationError(f'source is missing or ambiguous: {location}')
    return matches.pop()


def _category(path):
    parts = path.parts
    if any(parts[i] == 'changes' and parts[i + 1] in ('archive', '_archive')
           for i in range(len(parts) - 1)):
        return 'immutable_snapshot'
    # The article-level history is appended across versions. A history file
    # captured inside a version snapshot remains part of that immutable version.
    if any(parts[i] == 'changes' and parts[i + 1] == '_versions'
           and len(parts) == i + 4 and path.name == 'history.md'
           for i in range(len(parts) - 1)):
        return 'append_history'
    if any(parts[i] == 'changes' and parts[i + 1] == '_versions'
           for i in range(len(parts) - 1)):
        return 'immutable_snapshot'
    if path.suffix in ('.yaml', '.yml') and ('history' in path.name or 'journal' in path.name):
        return 'append_history'
    if parts[0] == 'tests' or parts[:2] == ('app', 'tests'):
        return 'test_source'
    if parts[0] == 'docs' or path.suffix == '.md' and (
            path.name.startswith(('test-handover', 'test-handoff'))
            or path.name.endswith('-test-handoff.md')):
        return 'public_projection'
    return 'other'


def build_manifest(root):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValidationError(f'artifact root is unavailable: {root}')
    categories = {key: [] for key in ('immutable_snapshot', 'append_history', 'test_source',
                                     'public_projection', 'other')}
    files = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValidationError(f'artifact symlink requires an explicit materialized source: {path}')
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        key = relative.as_posix()
        files[key] = hashlib.sha256(path.read_bytes()).hexdigest()
        categories[_category(relative)].append(key)
    for entries in categories.values():
        entries.sort()
    return {'version': 1, 'files': files, 'categories': categories}


def checkpoint_artifacts(source, destination, *, expected_manifest, manifest_path=None):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if destination.exists() or destination.is_symlink():
        raise ValidationError(f'checkpoint already exists: {destination}')
    if destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValidationError('checkpoint source and destination must be separate')
    sidecar = Path(manifest_path).resolve() if manifest_path is not None else None
    if sidecar is not None and (sidecar.exists() or sidecar.is_relative_to(source)
                                or sidecar.is_relative_to(destination)):
        raise ValidationError('manifest must be a new external evaluator record')
    if build_manifest(source) != expected_manifest:
        raise ValidationError('source differs from finalized manifest')
    try:
        shutil.copytree(source, destination, copy_function=shutil.copy2)
        if build_manifest(destination) != expected_manifest or build_manifest(source) != expected_manifest:
            raise ValidationError('artifacts changed during checkpoint sampling')
        if sidecar is not None:
            sidecar.parent.mkdir(parents=True, exist_ok=True)
            with sidecar.open('x', encoding='utf-8', newline='\n') as stream:
                stream.write(json.dumps(expected_manifest, ensure_ascii=False, indent=2) + '\n')
    except Exception as exc:
        # Only this new, pre-checked destination belongs to the failed sampling.
        if destination.is_dir() and not destination.is_symlink():
            shutil.rmtree(destination)
        if isinstance(exc, ValidationError):
            raise
        raise ValidationError(f'checkpoint could not be completed: {exc}') from exc
    return expected_manifest


def wait_for_condition(predicate, *, timeout, interval=0.1):
    if timeout < 0 or interval <= 0:
        raise ValidationError('invalid wait timeout or interval')
    deadline = time.monotonic() + timeout
    while True:
        value = predicate()
        if value:
            return value
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValidationError('condition did not become ready before timeout')
        time.sleep(min(interval, remaining))
