"""Launch a fresh or explicitly resumed Codex participant, retaining real evidence.

Run from the evaluator side. Prompts, transcripts and scoring stay outside the
participant project. Linux projects may use a Windows controller over WSL.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

from workflow_runtime import ValidationError, parse_codex_events


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--phase', required=True)
    parser.add_argument('--prompt', type=Path, required=True)
    parser.add_argument('--thread')
    parser.add_argument('--node', type=Path, required=True)
    parser.add_argument('--codex', type=Path, required=True)
    parser.add_argument('--timeout', type=int, default=1800)
    args = parser.parse_args()
    run = args.run.resolve()
    manifest_path = run / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if Path(args.phase).name != args.phase or args.phase in ('.', '..'):
        raise ValidationError('phase must be one directory name')
    phase = run / 'participants' / args.phase
    phase.mkdir(parents=True, exist_ok=False)
    project = manifest['project']
    if manifest['platform'] == 'linux' and os.name == 'nt':
        project = '\\\\wsl.localhost\\Ubuntu-24.04' + project.replace('/', '\\')
    prompt = args.prompt.read_text(encoding='utf-8')
    command = [str(args.node), str(args.codex), 'exec', '-C', project,
               '-s', 'danger-full-access', '-c', 'approval_policy="never"',
               '--dangerously-bypass-hook-trust']
    if args.thread:
        command.extend(['resume', args.thread])
    command.extend(['--json', '--skip-git-repo-check', '-o', str(phase / 'answer.txt'), '-'])
    environment = dict(os.environ)
    for name in ('CODEX_THREAD_ID', 'CODEX_SESSION_ID', 'DOCSPEC_ACTOR_ID', 'DOCSPEC_AGENT', 'PYTHONPATH'):
        environment.pop(name, None)
    environment['PYTHONUTF8'] = '1'
    launch = {'time': datetime.now(timezone.utc).isoformat(), 'phase': args.phase,
              'command': command, 'cwd': project, 'prompt': prompt,
              'prompt_sha256': hashlib.sha256(prompt.encode('utf-8')).hexdigest(),
              'resume_thread': args.thread, 'fresh': args.thread is None,
              'platform': manifest['platform'],
              'controller': sys.platform, 'timeout': args.timeout}
    (phase / 'launch.json').write_text(json.dumps(launch, ensure_ascii=False, indent=2), encoding='utf-8')
    manifest['participant_launches'].append({'phase': args.phase, 'launch': str(phase / 'launch.json'),
                                            'fresh': launch['fresh'], 'started_at': launch['time']})
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'phase': args.phase, 'state': 'launched', 'platform': manifest['platform']}), flush=True)
    # Keep raw events streamed on disk, even when the launcher times out.
    with (phase / 'events.jsonl').open('w', encoding='utf-8') as out, (phase / 'stderr.txt').open('w', encoding='utf-8') as err:
        process = None
        cleanup = None
        try:
            options = ({'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
                       if os.name == 'nt' else {'start_new_session': True})
            process = subprocess.Popen(command, cwd=project, env=environment, stdin=subprocess.PIPE,
                                       encoding='utf-8', stdout=out, stderr=err, **options)
            process.communicate(input=prompt, timeout=args.timeout)
            code, launch_error = process.returncode, None
        except subprocess.TimeoutExpired:
            code, launch_error = 124, 'participant timeout; raw history retained, completion not established'
            # Stop the owned tree before returning; killing just the Node wrapper
            # would leave its Codex child or a synthetic artifact writer alive.
            try:
                if os.name == 'nt':
                    killed = subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                            capture_output=True, encoding='utf-8', errors='replace', timeout=10)
                    cleanup = {'command': ['taskkill', '/PID', str(process.pid), '/T', '/F'],
                               'exit': killed.returncode, 'stdout': killed.stdout, 'stderr': killed.stderr,
                               'verified': killed.returncode == 0}
                else:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass  # No processes remain in this dedicated group.
                    cleanup = {'process_group': process.pid, 'signal': 'SIGKILL', 'verified': True}
                process.communicate(timeout=10)
            except (OSError, subprocess.TimeoutExpired) as exc:
                cleanup = {'verified': False, 'error': str(exc)}
        except OSError as exc:
            code, launch_error = 127, str(exc)
    acquired = parse_codex_events(phase / 'events.jsonl')
    actual = acquired['session']
    validation_errors = []
    if cleanup is not None and not cleanup.get('verified'):
        validation_errors.append('owned writer cleanup is unverified; checkpoint must not proceed')
    if actual is None:
        validation_errors.append('unique actual participant session not established')
    if args.thread is not None and actual != args.thread:
        validation_errors.append(f'resume session mismatch: expected {args.thread}, actual {actual}')
    successful_turn = False
    try:
        rows = [json.loads(line) for line in (phase / 'events.jsonl').read_text(encoding='utf-8').splitlines()
                if line.strip()]
        successful_turn = any(isinstance(row, dict) and row.get('type') == 'turn.completed' for row in rows)
        successful_turn &= not any(isinstance(row, dict) and row.get('type') in ('turn.failed', 'error') for row in rows)
    except (ValueError, OSError, UnicodeError):
        validation_errors.append('unreadable participant completion events')
    if not successful_turn:
        validation_errors.append('successful participant turn not established')
    launcher_exit = code
    if validation_errors:
        code = code or 1
    executed = bool(manifest.get('agent_workflow_executed')) or actual is not None
    manifest.update(agent_workflow_executed=executed, preparation_only=not executed)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    status = {'exit': code, 'launcher_exit': launcher_exit, 'launch_error': launch_error,
              'validation_errors': validation_errors, 'timeout_cleanup': cleanup,
              'actual_session': actual,
              'shell_acquisition': acquired['acquisition'], 'shell_events': len(acquired['events']),
              'diagnostics': acquired['diagnostics'],
              'finished_at': datetime.now(timezone.utc).isoformat()}
    (phase / 'shell-events.json').write_text(json.dumps(acquired, ensure_ascii=False, indent=2), encoding='utf-8')
    (phase / 'result.json').write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(status, ensure_ascii=False), flush=True)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
