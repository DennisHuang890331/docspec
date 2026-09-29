---
name: dspx-implement
description: >-
  Implement a software change task by task — write the code a task declares, then let the engine
  run the planned tests and record evidence; the engine marks the task complete, never you. Use
  after dspx-propose and dspx-test, whenever work on a change's tasks starts or resumes. Replaces
  OpenSpec's apply.
license: PolyForm-Noncommercial-1.0.0
compatibility: Requires the docspec CLI (installed via uv tool; not on PATH in a fresh shell — run it from the dir printed by `uv tool dir --bin`, never reinstall).
metadata:
  author: docspec
  version: "1.0"
---

Make the planned tests pass by changing the program, one task at a time. There is no command to tick a task: evidence completes it.

**Input**: a change id (and optionally a task id).

**Steps**

1. **Orient** — `docspec code change status <id>` lists tasks with their derived status and what is missing. Pick a task whose `depends-on` are done. `docspec code spec show <cap> --req R<n>` for the requirement it implements.

2. **Change only what the task declares** — imported tasks (OpenSpec) may lack links: `docspec code change gaps <id> --template`, fill the `tasks:` part, `docspec code task set <id> --from <file>`. Then edit the files in the task's `files`. If you must touch another file, first `docspec code task set <id> <task> --files …` so the evidence covers it. Do not edit test files; they belong to the test role.

3. **Run the evidence** — `docspec code evidence run <id> <task>`. The engine builds the command itself (the repo's `test-command` in `docspec/software/config.yaml`, the planned tests, the repo root), records counts, commit and environment, and marks the task done only if every planned test ran and passed, none was skipped without being declared, and every test is still the version the test role signed off. Read the per-test result it prints. Custom commands are not accepted; a different runner is a config change.

4. **When a test fails** — fix the program and run again. Never edit a test, even one you think is wrong ("changed after the test role signed it off" means someone did). If you believe the test misreads the spec, raise it: `docspec code testplan object <id> <T-id> --reason "<which WHEN/THEN it gets wrong>"`, then continue with other tasks until the test role answers.

5. **Non-test verification** — for `inspection` or `demonstration`: `docspec code evidence add <id> <task> --type inspection --subject "<what you looked at: screenshot path, size, scale>" --conclusion "…" --result pass|fail`. When the owner must accept it, show them, read back what they saw, and after they confirm: `docspec code evidence accept <id> <task> --read-back "…" --confirmed "<their reply>"`.

6. **After edits to finished work** — if a file changes after its evidence, the task falls back to needs-rerun on the next `change status`; run the evidence again.

7. **Report** — `docspec code change status <id>` until every task is done; then hand to dspx-verify.

**Pause if:**
- The spec is wrong or incomplete for what the owner wants → back to dspx-propose (and dspx-govern if the owner must decide).
- An environment check fails (missing GPU, library, path pollution) → report it; do not declare skips to get around it.

**Output**

```
## implement — <change id>
Tasks: <task → derived status, evidence id>
Failing: <tests and why>
Objections raised: <O-ids>
Next: <task or dspx-verify>
```

**Guardrails**
- Never edit `docspec/software/` by hand and never claim a task is done yourself.
- Never edit, skip or delete a planned test to get green; object instead.
- Keep each change to what the task says; unrelated fixes get their own change.
