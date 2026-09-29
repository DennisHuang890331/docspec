---
name: dspx-verify
description: >-
  Verify and finish a software change — confirm the engine's checks, review that the tests really
  prove each WHEN/THEN, get the owner's acceptance where a requirement needs human eyes, then
  archive so the spec deltas merge into the main specs. Use when every task of a change looks done,
  or before telling the owner a change is finished. Replaces OpenSpec's verify and archive.
license: PolyForm-Noncommercial-1.0.0
compatibility: Requires the docspec CLI (installed via uv tool; not on PATH in a fresh shell — run it from the dir printed by `uv tool dir --bin`, never reinstall).
metadata:
  author: docspec
  version: "1.0"
---

Finish a change honestly: the engine checks the links and evidence; you check that the tests mean what the spec says. Prefer an agent other than the implementer for step 3.

**Input**: a change id.

**Steps**

1. **Engine checks** — `docspec code archive <id> --dry-run`. It lists every blocker: unfinished tasks, missing acceptance, draft or superseded decisions, unarchived prerequisites, spec conflicts, open impact flags. Fix each through the owning skill (implement, test, propose, govern); do not work around one.

2. **Evidence review** — `docspec code evidence list <id>`. For each test run: the planned tests all ran, counts are plausible, no suspicious skips, the environment matches the target (GPU, libraries). For each waiver, read the quoted ruling next to it: it must really be about that task.

3. **Semantic review** — for each changed scenario, read its WHEN/THEN (`docspec code spec show …`) and the test that covers it. Does the test fail if the THEN is false? If not, raise it with the test role (dspx-test) and stop here.

4. **Owner acceptance** — requirements verified by `inspection` or `demonstration` need the owner: show them the result, read back what they confirmed, then `docspec code evidence accept <id> <task> --read-back "…" --confirmed "<their reply>"`. An owner-ruled exception is `docspec code evidence waive <id> <task> --ruling <RL-id> --reopen-when "…"`.

5. **Archive** — `docspec code archive <id>`. Read its output: specs updated, tests that no longer verify a changed scenario (tell the test role), active changes on the same capability (they must re-check their deltas).

6. **Regression and status** — `docspec code test` runs every test the specs cite and names the scenario each failure affects. Then `docspec brief` and tell the owner in plain words what is finished and what needs them.

**Output**

```
## verify — <change id>
Engine: <archive blockers, or none>
Evidence: <runs reviewed, concerns>
Semantic review: <scenarios whose tests do not prove the THEN>
Owner: <acceptances recorded / waivers>
Archived: <yes → specs updated, baseline> | <no → what blocks>
```

**Guardrails**
- Never archive past a blocker, and never mark or edit anything by hand.
- A green run is not proof: a test that cannot fail proves nothing.
- The owner's acceptance is their reply, verbatim; never confirm on their behalf.
