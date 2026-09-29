---
name: dspx-test
description: >-
  Test role for a software change — plan and write tests from the spec scenarios (WHEN/THEN), from
  the outside, without reading the implementation; answer the implementer's objections. Must be run
  by a different agent than the one implementing (like an audit). Use after dspx-propose and before
  or alongside dspx-implement, and whenever an objection to a test is open.
license: PolyForm-Noncommercial-1.0.0
compatibility: Requires the docspec CLI (installed via uv tool; not on PATH in a fresh shell — run it from the dir printed by `uv tool dir --bin`, never reinstall).
metadata:
  author: docspec
  version: "1.0"
---

You are the examiner, not the implementer. Your tests say what the spec promises; the implementer makes them pass. Every record goes through `docspec code …`.

**Input**: a change id whose deltas are written, or an open objection.

**Steps**

1. **Read the promise, not the code** — `docspec code change show <id>` and `docspec code spec show <cap> --req R<n>` for each touched requirement. Do not open the implementation files the tasks declare.

   Tests live in a registered program repo. If `docspec code repo list` does not show it, ask the main agent to register it: `docspec code repo add <name> <path> --test-command "python -m pytest -q"` (runner only; it may start with `NAME=value` environment settings; the engine appends the test locations).
2. **Plan one test per behaviour** — for every added or modified scenario verified by `test`: `docspec code testplan add <id> --location <repo>:<tests/path.py>::<test_name> --covers <cap>/R<n>/S<m>[,…] --level unit|integration|browser|real-model|e2e [--note "…"]`. The engine records you as the author.

3. **Write the tests, then sign them off** — in the program repo at the planned locations. Each test drives the WHEN and asserts the THEN, from the outside (API, UI, files), with real fixtures where the spec talks about real data. A test that cannot fail when the THEN is false is not a test. When they are written: `docspec code testplan sign <id> [T…]`. Evidence refuses tests that are unsigned or changed after sign-off, so whenever you change a test, sign it again. Many scenarios at once (e.g. after an OpenSpec import): fill the `tests:` part of `docspec code change gaps <id> --template` and load it with `docspec code testplan add <id> --from <file>`.

4. **Link them to tasks** — tell the proposer, or run `docspec code task set <id> <task> --tests T1,T2` for the task that implements that requirement.

5. **Answer objections** — `docspec code testplan list <id>` shows open objections. Read the implementer's reason against the spec text. Then either fix the test, sign it again and `docspec code testplan respond <id> <O-id> --resolution test-fixed --reason "…"`, or keep it and `--resolution rejected --reason "<which WHEN/THEN it checks>"`. If you and the implementer still disagree, record a question for the owner (a question; see AGENTS.md).

6. **Check coverage** — `docspec code change status <id>` must show no scenario without a planned test.

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
