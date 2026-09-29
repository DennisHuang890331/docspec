---
name: dspx-propose
description: >-
  Software change proposal — turn a request into a change folder: why and what, the spec deltas
  (only the requirements and scenarios that change), design notes that cite project decisions, and
  tasks that implement each changed requirement. Use when starting any software change, feature,
  fix or refactor that alters behaviour. Replaces OpenSpec's propose. Tests are planned by the test
  role (dspx-test), not here.
license: PolyForm-Noncommercial-1.0.0
compatibility: Requires the docspec CLI (installed via uv tool; not on PATH in a fresh shell — run it from the dir printed by `uv tool dir --bin`, never reinstall).
metadata:
  author: docspec
  version: "1.0"
---

Shape one software change so the engine can check it. Every file under `docspec/software/` is written by `docspec code …` only (a hook blocks hand edits and the seal would break).

**Input**: a request from the owner, a roadmap item, or a bug report.

**Steps**

1. **Orient** — `docspec brief`, then `docspec code spec list` and `docspec code spec show <capability> --req R<n> --json` for just the requirements involved. Check `docspec decision list --json` for project decisions that bind this work.

2. **Decide with the owner first** — anything the owner must choose goes through dspx-govern (question → read-back → ruling → decision). Do not write deltas that assume an unconfirmed choice.

3. **Create the change** — `docspec code change new <kebab-id> --why "…" --what "…" [--what …] --modified <cap>,… --new <cap>,… [--depends-on <change>]`. Keep it to one coherent piece of work; if status warns it is large, split it.

4. **Design** — `docspec code change design <id> --context "…" --goal "…" --non-goal "…" --risk "…" --decision <D-id>`. Cite project decisions by id; never copy their text.

5. **Spec deltas, smallest unit** — one command per change: `docspec code change delta <id> --capability <cap> --op modify-scenario --ref R1/S2 --then "…"` (or `add-requirement` with `--statement "… SHALL …" --verification test|inspection|demonstration|analysis --scenario "title | when | then"`, `add-scenario`, `modify-requirement`, `rename-requirement`, `remove-requirement --reason`, `remove-scenario --reason`). Add `--based-on <D-id>` where a requirement follows a project decision. Many deltas: `--from deltas.yaml`. Wrong one: `docspec code change undelta <id> --capability <cap> --ref R1/S2`.

6. **Tasks** — for every added or modified requirement: `docspec code task add <id> --title "…" --implements <cap>/R<n> --files <repo>:<path>,… --verify <methods> [--tests T<n>,…] [--depends-on <task>]`. Declare implementation files only; test files belong to the test role. Tests are linked after dspx-test plans them (`docspec code task set <id> <task> --tests T1,T2`).

7. **Check and hand off** — `docspec code change status <id>`; fix every ✗. Link the roadmap: `docspec roadmap link <W-id> --ref swc:<id>`. Hand the change to the test role (dspx-test) before implementation starts.

**Pause if:**
- A delta would change behaviour the owner has not ruled on → ask via dspx-govern.
- `change status` reports a base conflict → another change moved the spec; re-read it and rewrite the delta.

**Output**

```
## propose — <change id>
Why: <one line>
Deltas: <cap/R/S … per capability>
Decisions cited: <D-ids>
Tasks: <n> (implements …)
Next: test role plans tests for <scenarios>; then dspx-implement
```

**Guardrails**
- Never mark anything done: completion is written by the engine from evidence.
- Statements use SHALL or MUST; every requirement keeps at least one scenario.
- Requirements the owner must look at (screens, layout) use `inspection` or `demonstration`, not `test` alone.
- Talk to the owner in plain language; ids go in brackets.
