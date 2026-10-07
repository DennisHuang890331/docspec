---
name: dspx-propose
description: >-
  Software change proposal — turn a request into a change folder: why and what, the spec deltas
  (only the requirements and scenarios that change), design notes that cite project decisions, and
  tasks that implement each changed requirement. Use when starting any software change, feature,
  fix or refactor that alters behaviour. Replaces OpenSpec's propose. Tests are planned by the test
  role (dspx-test), not here.
license: PolyForm-Noncommercial-1.0.0
compatibility: Requires the ArtiSpec CLI (`artispec`) from the `docspec` distribution. For uv tool installs with missing PATH, use the directory printed by `uv tool dir --bin`; for a virtual environment, use its Scripts/bin directory; never reinstall merely to repair PATH (an explicitly requested upgrade is separate).
metadata:
  author: docspec
  version: "1.6"
---

Shape one software change so the engine can check it. Software records in `docspec/software/` and software change records in `docspec/changes/` are written by `artispec code …` only (a hook blocks hand edits and the seal would break); repository configuration retains its existing supported setup path.

**Input**: a request from the owner, a roadmap item, or a bug report.

**Steps**

1. **Orient** — read `artispec handover`, find this work with `artispec roadmap`, then read `artispec roadmap show <work-id>` (or `--json`). Follow its source references only where more detail is needed, including `artispec code spec show <capability> --req R<n> --json` for the requirements involved. If no work exists yet, register it as described below and inspect its summary once linked.

   Find existing changes with `artispec change` (`--all` includes history), then inspect `artispec change show <id>`. These shared queries are read-only: they do not refresh tasks, run tests, write handover or move records. Reuse the existing software change where appropriate; a document change keeps its own targets and creation rules and does not need this software proposal/design/task workflow.

   Missing information is not proof of no constraints. A superseded decision stays visible as the original reference; its replacement is not automatically authorized for this work. The summary follows recorded links only and does not run tests, refresh records or rewrite handover. Resolve missing design facts and authority through the existing information, question and ruling workflow; do not treat an action suggestion as the owner's approval.

2. **Decide with the owner first** — anything the owner must choose is recorded as a question and ruled by the owner (`artispec ruling add`; read back and wait for confirmation only if the owner was unclear; see AGENTS.md). Record facts the owner supplies with `artispec info add`. Do not write deltas that assume a choice the owner has not made.

   Check existing information, rulings and requirements for who will operate the result, their platform, how they will start it, installation restrictions, network/offline restrictions, and the delivery method. Cite existing records; ask only about missing facts or choices that affect this design. Use the existing information, ruling and requirement records, not a new mandatory form. When changing a requirement, state which existing constraints remain and which an explicit ruling supersedes; do not silently drop the others or claim the engine can prove semantic completeness.

   Keep operator setup, installed machine dependencies and the scope of network restrictions separate. Do not strengthen an installation or offline requirement beyond the owner's words. Identify the actual launch method and delivery artifact that must be demonstrated; reuse clear existing constraints and ask only when a missing distinction changes the design or verification.

3. **Create the change** — `artispec code change new <kebab-id> --why "…" --what "…" [--what …] --modified <cap>,… --new <cap>,… [--depends-on <change>]`. Keep it to one coherent piece of work; if status warns it is large, split it.

   New software changes live under `docspec/changes/`. Existing `docspec/software/changes/` containers, including archives, remain usable in place; never move them as part of a query. An explicit migration uses `artispec change migrate --dry-run` before `artispec change migrate`, checks conflicts, and preserves record contents. Do not rename the installation package `docspec`, Python package `dspx`, or managed root `docspec/`.

   Register the work at the start: reuse an existing roadmap item for the same scope and link it with `artispec roadmap link <returned-work-id> --ref swc:<id>`. If none exists, use `artispec roadmap add --title "…" --ref swc:<id>` and retain the id returned by the command. Never assume a W-id exists or add a duplicate when resuming.

4. **Design** — `artispec code change design <id> --context "…" --goal "…" --non-goal "…" --risk "…" --decision <D-id>`. Cite project decisions by id; never copy their text.

5. **Spec deltas, smallest unit** — one command per change: `artispec code change delta <id> --capability <cap> --op modify-scenario --ref R1/S2 --then "…"` (or `add-requirement` with `--statement "… SHALL …" --verification test|inspection|demonstration|analysis --scenario "title | when | then"`, `add-scenario`, `modify-requirement`, `rename-requirement`, `remove-requirement --reason`, `remove-scenario --reason`). Add `--based-on <D-id>` where a requirement follows a project decision. Many deltas: `--from deltas.yaml`. To reword a requirement or scenario this change itself adds, use `modify-requirement` / `modify-scenario` on its id — it is edited in place and keeps its id (planned tests stay linked). Wrong one altogether: `artispec code change undelta <id> --capability <cap> --ref R1/S2`. A design list item that is wrong: `artispec code change design <id> --remove-goal "<text or number>"` (also `--remove-non-goal`, `--remove-risk`, `--remove-open-question`).

6. **Tasks** — for every added or modified requirement: `artispec code task add <id> --title "…" --implements <cap>/R<n> --files <repo>:<path>,… --verify <methods> [--tests T<n>,…] [--depends-on <task>]`. Declare implementation files only; test files belong to the test role. Tests are linked after dspx-test plans them (`artispec code task set <id> <task> --tests T1,T2`).

7. **Check and hand off** — `artispec code change status <id>`; fix structural errors, invalid references and base conflicts. A `--verify test` task may have no tests yet: keep it not-started and hand the pending test planning/linking to dspx-test. Do not invent test ids or temporarily change verification to analysis. Missing planning still blocks evidence execution and archive. Update the existing roadmap item and rewrite `artispec handover write` before the test role takes over; implementation follows planning and sign-off.

**Pause if:**
- A delta would change behaviour the owner has not ruled on → ask the owner (question → ruling; read back only if unclear).
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
