---
name: dspx-implement
description: >-
  Implement a software change task by task — write the code a task declares, then let the engine
  run the planned tests and record evidence; the engine marks the task complete, never you. Use
  after dspx-propose and dspx-test, whenever work on a change's tasks starts or resumes. Replaces
  OpenSpec's apply.
license: PolyForm-Noncommercial-1.0.0
compatibility: Requires the ArtiSpec CLI (`artispec`) from the `docspec` distribution. For uv tool installs with missing PATH, use the directory printed by `uv tool dir --bin`; for a virtual environment, use its Scripts/bin directory; never reinstall merely to repair PATH (an explicitly requested upgrade is separate).
metadata:
  author: docspec
  version: "1.6"
---

Make the planned tests pass by changing the program, one task at a time. There is no command to tick a task: evidence completes it.

**Input**: a change id (and optionally a task id).

**Steps**

Keep your actual stable session identity. A test-role agent may use the same AI provider in a different session; provider labels alone do not establish authorship. Codex uses `CODEX_THREAD_ID`. Without a detected session id, the controller may supply a recorded launch id through `DOCSPEC_ACTOR_ID`; never invent or change an id to evade author checks. An inherited implementer thread id does not make a child independent. Legacy same-provider records without ids remain conservative and are not automatically reassigned. Only the original test author or owner may change/remove/sign tests or answer objections.

1. **Orient** — read `artispec handover`, find this change's work with `artispec roadmap`, then read `artispec roadmap show <work-id>` (or `--json`). If none exists, register it with `artispec roadmap add --title "…" --ref swc:<id>` and retain its returned id. Open the referenced original records only where needed: `artispec code change status <id>` lists tasks with their derived status, and `artispec code spec show <cap> --req R<n> --change <id>` gives the proposed requirement. Pick a task whose `depends-on` are done.

   Discover changes with `artispec change` (`--all` includes history), then read `artispec change show <id>` before operating on the reported software change. Shared queries do not refresh tasks, run tests, write handover or migrate records. New containers use `docspec/changes/`; legacy `docspec/software/changes/` remains usable without moving it. Document changes retain their own targets and completion rules.

   Missing information does not mean no constraints; a superseded reference does not authorize applying its replacement. Send unsigned or needs-review tests to the test role; do not sign them yourself. The summary is read-only: it does not run tests, refresh records or rewrite handover, and it never replaces the evidence needed for completion.

2. **Change only what the task declares** — imported tasks (OpenSpec) may lack links: `artispec code change gaps <id> --template`, fill the `tasks:` part, `artispec code task set <id> --from <file>`. Then edit the files in the task's `files`. If you must touch another file, first `artispec code task set <id> <task> --files …` so the evidence covers it. Do not edit test files; they belong to the test role.

3. **Run the evidence** — `artispec code evidence run <id> <task>`. The engine builds the command itself (the repo's `test-command` in `docspec/software/config.yaml`, the planned tests, the repo root), records counts, commit and environment, and marks the task done only if every planned test ran and passed, none was skipped without being declared, and every test is still the version the test role signed off. Read the per-test result it prints. Custom commands are not accepted; a different runner is a config change.

4. **When a test fails** — fix the program and run again. Never edit a test, even one you think is wrong ("changed after the test role signed it off" means someone did). If you believe the test misreads the spec, raise it: `artispec code testplan object <id> <T-id> --reason "<which WHEN/THEN it gets wrong>"`, then continue with other tasks until the test role answers.

5. **Non-test verification** — for `inspection` or `demonstration`: `artispec code evidence add <id> <task> --type inspection --subject "<what you looked at: screenshot path, size, scale>" --conclusion "…" --result pass|fail`. When owner acceptance is required, show the current result and record their acceptance with `artispec code evidence accept <id> <task> --read-back "<what they accepted>" --confirmed "<their reply>"`. If they already clearly accepted this version, use that reply; request clarification only when unclear. Agent inspection never substitutes for owner acceptance of changed content.

6. **After edits to finished work** — related requirement behaviour, test plans, policy or declared file changes invalidate old evidence. Review the reason from `change status`, send changed test promises to the test role for sign-off, then rerun evidence. Old evidence lacking verification scope must be renewed; never replace its scope with current values.

7. **Report** — `artispec code change status <id>` until every task is done; update the same roadmap work and rewrite the whole handover note before handing to dspx-verify.

   Technical handoff describes interfaces, files and how to reproduce the result, with links to its tests and evidence. Current task progress, sign-off and verification status come from the CLI; do not keep a second mutable progress checklist in the handoff document. Summaries retain historical fingerprints and original-record entry points, not a new copy of signed contracts.

**Pause if:**
- The spec is wrong or incomplete for what the owner wants → back to dspx-propose (and a question for the owner if they must decide).
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
- Never edit managed software records in `docspec/software/` or `docspec/changes/` by hand and never claim a task is done yourself.
- Never edit, skip or delete a planned test to get green; object instead.
- Keep each change to what the task says; unrelated fixes get their own change.
