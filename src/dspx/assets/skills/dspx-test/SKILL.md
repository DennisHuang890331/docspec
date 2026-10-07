---
name: dspx-test
description: >-
  Test role for a software change — plan and write tests from the spec scenarios (WHEN/THEN), from
  the outside, without reading the implementation; answer the implementer's objections. Must be run
  by a different agent than the one implementing (like an audit). Use after dspx-propose and before
  dspx-implement, and whenever an objection to a test is open.
license: PolyForm-Noncommercial-1.0.0
compatibility: Requires the ArtiSpec CLI (`artispec`) from the `docspec` distribution. For uv tool installs with missing PATH, use the directory printed by `uv tool dir --bin`; for a virtual environment, use its Scripts/bin directory; never reinstall merely to repair PATH (an explicitly requested upgrade is separate).
metadata:
  author: docspec
  version: "1.5"
---

You are the examiner, not the implementer. Your tests say what the spec promises; the implementer makes them pass. Every record goes through `artispec code …`.

**Input**: a change id whose deltas are written, or an open objection.

Different sessions may use the same AI provider. ArtiSpec records the provider and a stable session id separately: Codex uses `CODEX_THREAD_ID`; when a tool has no detected session id, the controller may supply its recorded launch id through `DOCSPEC_ACTOR_ID`. Never change that id to switch roles or impersonate the owner. A conflicting override is rejected. Legacy same-provider records without ids cannot prove independence; report that limitation instead of claiming sign-off. A child inheriting the implementer's thread id needs a genuinely separate session. Only the original test author or owner changes/removes tests, signs them, or answers objections. The implementer must not create test-role records or edit tests.

**Steps**

1. **Read the promise, not the code** — use `artispec roadmap` to find the change's existing work, then `artispec roadmap show <work-id>` (or `--json`). Find changes through `artispec change` (`--all` includes history); follow relevant sources to `artispec change show <id>` and `artispec code spec show <cap> --req R<n> --change <id>`, so tests target the proposed software behaviour. Shared change queries are read-only: no task refresh, test execution, handover write or migration. Do not apply software test/task requirements to document targets. Do not open the implementation files the tasks declare. If work is missing, register it with `artispec roadmap add --title "…" --ref swc:<id>` and keep the returned id.

   Missing information does not mean no constraints. A superseded reference does not authorize silently adopting its replacement. The summary's unsigned or needs-review tests belong to this role: inspect their scenarios and tests before signing; never treat the summary itself as a sign-off. Reading it does not run tests, refresh records or rewrite handover, and does not replace full coverage checks.

   Tests live in a registered program repo. If `artispec code repo list` does not show it, ask the main agent to register it: `artispec code repo add <name> <path> --test-command "python -m pytest -q"` (runner only; it may start with `NAME=value` environment settings; the engine appends the test locations).
2. **Plan one test per behaviour** — for every added or modified scenario verified by `test`: `artispec code testplan add <id> --location <repo>:<tests/path.py>::<test_name> --covers <cap>/R<n>/S<m>[,…] --level unit|integration|browser|real-model|e2e [--note "…"]`. The engine records you as the author.

3. **Write the tests, then sign them off** — in the program repo at the planned locations. Each test drives the WHEN and asserts the THEN, from the outside (API, UI, files), with real fixtures where the spec talks about real data. A test that cannot fail when the THEN is false is not a test. Before signing, ask of each assertion "what wrong program would still pass this?" — these slipped through in practice:
   - **Coincidental data**: the expected value also appears elsewhere (seat number equals class number, `"4" in output` matches an id like 110040). Make the values distinct and assert on the exact field or line.
   - **Loose room**: the setup has so much capacity or so few constraints that the wrong behaviour never gets a chance to happen. Make it tight enough that only the correct rule produces the result.
   - **Only half of a flow**: a confirmation is tested for "no" but never for "yes"; an update is tested for the changed item but not for the ones that must stay put.
   - **Always-true checks**: `row > 0`, "exit code 0" alone, "output is not empty".
   - **Covers the wrong scenario**: if no scenario says what the test checks, the spec is missing a scenario — tell the main agent instead of attaching it to the nearest one.
   Then run the tests you wrote; report the result, or say plainly that you did not run them.
   When they are written: `artispec code testplan sign <id>` — without test ids it signs only the tests that are unsigned or changed since they were signed, and lists each one; `--all` signs everything again. Evidence refuses tests that are unsigned or changed after sign-off, so whenever you change a test, sign it again. A planned test that covers the wrong scenario, or needs a note, is corrected in place with `artispec code testplan set <id> <T> --covers …` (same id, task links stay). Many scenarios at once (e.g. after an OpenSpec import): fill the `tests:` part of `artispec code change gaps <id> --template` and load it with `artispec code testplan add <id> --from <file>`.

4. **Link them to tasks** — tell the proposer, or run `artispec code task set <id> <task> --tests T1,T2` for the task that implements that requirement.

5. **Answer objections** — `artispec code testplan list <id>` shows open objections. Read the implementer's reason against the spec text. Then either fix the test, sign it again and `artispec code testplan respond <id> <O-id> --resolution test-fixed --reason "…"`, or keep it and `--resolution rejected --reason "<which WHEN/THEN it checks>"`. If you and the implementer still disagree, record a question for the owner (a question; see AGENTS.md).

6. **Check coverage** — `artispec code change status <id>` must show no required scenario without a planned test and no planned required test without a task implementing its requirement. A changed requirement statement also requires its existing scenarios. Re-sign when covered behaviour, covers or test location changes, as well as when test content changes. Then update the roadmap and rewrite the whole handover note for the implementer; no concurrent writes to managed records.

**Output**

```
## test — <change id>
Planned: <T-ids → scenarios>
Written: <files>
Objections: <O-id resolution, reason>
Uncovered: <none | scenarios and why>
```

**Guardrails**
- Never write or edit implementation code; never declare implementation files.
- Never weaken a test to make it pass; change it only when it misreads the spec, and say which line.
- Skips must be declared on the task (`--allow-skips yes`) with the reason in the test; an undeclared skip blocks completion by design.
- If you also implemented this change, stop: the engine flags a test written and run by the same agent.
