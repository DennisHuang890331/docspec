---
name: dspx-verify
description: >-
  Verify and finish a software change — confirm the engine's checks, review that the tests really
  prove each WHEN/THEN, get the owner's acceptance where a requirement needs human eyes, then
  archive so the spec deltas merge into the main specs. Use when every task of a change looks done,
  or before telling the owner a change is finished. Replaces OpenSpec's verify and archive.
license: PolyForm-Noncommercial-1.0.0
compatibility: Requires the ArtiSpec CLI (`artispec`) from the `docspec` distribution. For uv tool installs with missing PATH, use the directory printed by `uv tool dir --bin`; for a virtual environment, use its Scripts/bin directory; never reinstall merely to repair PATH (an explicitly requested upgrade is separate).
metadata:
  author: docspec
  version: "1.6"
---

Finish a change honestly: the engine checks the links and evidence; you check that the tests mean what the spec says. Prefer an agent other than the implementer for step 3.

**Input**: a change id.

**Steps**

Find the existing work with `artispec roadmap`, then read `artispec roadmap show <work-id>` (or `--json`). Open its source records where needed before the checks below. Missing information does not mean no constraints; a superseded reference stays visible and does not authorize applying its replacement. Route unsigned or needs-review tests to the test role. An unfrozen document still needs an explicit owner request to freeze. Reading the summary does not run tests, refresh records or rewrite handover, and is not a substitute for full verification.

Use `artispec change` for active changes across both domains (`--all` includes history), then `artispec change show <id>` to confirm the domain and recorded state. These queries do not refresh tasks, run tests, write handover or move records. This verification workflow applies to software; sharing `docspec/changes/` does not impose software tasks/tests on document targets. Legacy software containers remain operable in their existing location.

1. **Engine checks** — `artispec code archive <id> --dry-run`. It lists every blocker: unfinished tasks, missing current evidence or owner acceptance, invalid decision basis, unarchived prerequisites, spec conflicts, open impact flags. Route each to the owning role (dspx-implement, dspx-test, dspx-propose), or record the owner's ruling through the governance commands described in AGENTS.md. Never clear a flag as a substitute for restoring valid authority or evidence.

2. **Evidence review** — `artispec code evidence list <id>`. For each test run: the planned tests all ran, counts are plausible, no suspicious skips, the environment matches the target (GPU, libraries). For each waiver, read the quoted ruling next to it: it must really be about that task.

   Match evidence to the recorded platform, launch method, permissions, installation and network restrictions. A headless test does not by itself demonstrate the delivered GUI; tests on one OS do not prove another. Exercise only the conditions the requirements call for and state any uncovered scope, using existing verification/waiver rules rather than strengthening requirements or treating an environment failure as a pass. Take the validation copy from the finished delivery artifact after its author stops editing, and check that it matches that artifact; development-source tests alone do not prove the installed package or portable build.

3. **Semantic review** — for each changed scenario, read its WHEN/THEN (`artispec code spec show …`) and the test that covers it. Does the test fail if the THEN is false? If not, raise it with the test role (dspx-test) and stop here.

4. **Owner acceptance** — requirements verified by `inspection` or `demonstration` need the owner to accept the current result: `artispec code evidence accept <id> <task> --read-back "<what they accepted>" --confirmed "<their reply>"`. Reuse a clear acceptance of this version; clarify only if unclear. After related content changes, an old acceptance or a new agent inspection is insufficient. An owner-ruled exception is `artispec code evidence waive <id> <task> --ruling <RL-id> --reopen-when "…"`; its authority and scope must still be valid.

   Acceptance applies only to the recorded version and verification scope. If the change includes document delivery, its current content must already be frozen when that delivery is accepted. A historical acceptance remains historical; follow the current diagnostics rather than rewriting old evidence or assuming it covers a changed result.

   For a delivery with documents, compare the latest document's claims about readiness, pending verification and supported conditions with the current evidence. A difference needs an explicit correction and, when the owner requests it, a new frozen version. Preserve earlier snapshots; do not silently update them or make either domain's completion depend on the other. This comparison supports the delivery review and adds no engine gate.

5. **Archive** — `artispec code archive <id>`. Read its output: specs updated, tests that no longer verify a changed scenario (tell the test role), active changes on the same capability (they must re-check their deltas).

6. **Regression and status** — `artispec code test` runs every test the specs cite and names the scenario each failure affects. Then `artispec code change status <id>` and `artispec roadmap`, and tell the owner in plain words what is finished, what is verified, and what needs them.

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
