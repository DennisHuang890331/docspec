---
name: dspx-publish
description: Use only when the human explicitly pulls the trigger to ship a docspec document. Confirms the engine gate, runs the one irreversible publish (promote, freeze a read-only snapshot, bump version, log the changelog), then independently verifies the frozen artifact. Unlike edit/draft it authors nothing — it gates and freezes already-finished content.
---

## STEP 0 — do this FIRST, every time
> **If `docspec` is not found** — it IS installed (via `uv tool`); your shell's PATH just predates the install (a freshly-launched or sandboxed agent shell). Don't conclude it's missing: run the binary directly from the uv tools bin dir (normally `~/.local/bin/docspec`, Windows `%USERPROFILE%\.local\bin\docspec.exe`; `uv tool dir --bin` prints it), or restart your terminal so the install's PATH update takes effect.

Run `docspec guide` and `docspec instructions publish <section>` before acting. The mechanics —
the file model, field names, formats, read/write aperture, filing rules, the graduation/retire
transactions — live there, projected live from the schema; assume they may have changed since this
file was written. **This skill gives you only STANCE** (judgment and attitude — what to do, what
never to do). Don't restate mechanics or guess field names from memory. The engine gates
(`docspec check` / `ready` / `publish`) are your backstop: file something wrong and they refuse and
tell you exactly what's missing.

---

Freeze it. Publish is the one irreversible action in docspec: it turns a working draft into an immutable, versioned snapshot. Because it cannot be undone, the human pulls the trigger — you run the mechanics, in order, and stop if any gate fails.

**IMPORTANT:** This is the only hard boundary in the workflow. Once a snapshot is frozen it is read-only forever. Never publish on your own initiative; never publish without the human's explicit trigger. (Open *audit* findings do NOT block — see Gate.)

**Frozen archive/ is immutable.** Published snapshots live under the `archive/` folder (`docs/archive/<article>_v<N>.md`). **Never edit, overwrite, or delete anything inside any `archive/` folder** — it is published history. To change content, edit `docs/<article>_latest.md` and publish a new version. The engine backs this up three ways: this rule, a `PreToolUse` hook that blocks writes to `archive/`, and a `docspec lint` ERROR that re-hashes every frozen snapshot against `docspec/.freeze.yaml` and fails if any was tampered with (works on Drive/OneDrive where OS read-only fails).

---

## Gate (must pass before anything else)

- **Engine green (the deterministic hard gate)** — `docspec check` (references resolve, structure intact) and `docspec lint` (deliverable cleanliness: no leaked machinery, no `[TBD]`/placeholder/`[!WARNING]`) both pass **with zero ERROR**. `docspec publish` re-runs these itself — it does not trust that `apply` was run. **lint WARN findings (e.g. prose-drift, cross-document number-consistency, glossary term identity) are advisory — surface them to the human, but they do NOT block; only an ERROR aborts.**
- `dspx-apply` finished with no open copy-edit/proofread findings.
- **Open audit findings do NOT block** — audit is non-blocking by design; `docspec publish` only **warns** if findings are still `open` and proceeds. Whether to ship over an open finding is the human's judgment, not an engine gate.
- The human has explicitly said to publish.

If any gate fails, stop and report. Do not "fix and continue" — return to `apply`.

---

## Migrating an existing project (first publish only)

If this project existed before docspec — it carries pre-docspec published versions and an
existing revision history — do NOT run the first publish until the **migration onboarding
recipe** has been walked: the legacy versions registered into the freeze net, the existing
revision history pre-seeded, and the first version seeded to continue the pre-docspec
numbering instead of restarting from scratch. The recipe (exact commands, flags, and paths)
is projected by `docspec guide` under "Migration onboarding" — read it there, don't
reconstruct it from memory. A first publish that restarts the numbering over a project whose
history already reached a higher version breaks the version chain: stop, walk the recipe,
then publish.

---

## Sequence

`docspec publish <article>` is one irreversible shot — the engine runs the whole internal sequence (gate → promote verbatim → strip + freeze → semver bump → changelog row); the exact steps, flags, and paths are in `docspec guide`. Two stances govern how you stand to it:

- **Converge the WHOLE document before you pull the trigger — "every section drafted" is NOT "ready to ship".** The loop is develop → apply → factcheck → publish, and the single most common failure is declaring victory after apply and skipping factcheck. Before you ask the human for the publish trigger, confirm the document has actually CONVERGED: (1) `docspec status` shows every leaf written and **none `stale-*`** (no pending re-render or alignment); (2) the **`apply`** copy-prep pass has run and `docspec lint` is clean (no leaked machinery, no `[TBD]`/placeholder, no leftover `[!WARNING]`); (3) **`factcheck`** has run at least once and its findings are triaged (open *audit* findings are non-blocking and shipping over them is the human's call — but they must be *seen and decided*, not skipped); (4) the byline/front matter is real or an obvious reserved placeholder, not a fabricated name. A document that never went through apply+factcheck is not publish-ready no matter how many sections are drafted — say so and route back, don't pull the trigger.
- **Publish is the CONTENT gate, and the engine authors nothing.** The deliverable was written by `apply` *before* you publish; thin-engine rule means publish promotes the locked content **byte-for-byte** — no rewrite, no edit, no "one last polish" at promotion. Turning the frozen snapshot into a typeset PDF is a *separate, later* concern for the **`release`** skill, which never touches content.
- **★Self-verify with bash — do NOT just trust the engine.** After `docspec publish` returns, independently grep the frozen snapshot for residual markers/machinery (`dspx:section`, `{#`, `[TBD]`, `<!--`) — it must print NOTHING. **Use the exact snapshot path `docspec publish` printed (don't assume the layout) and confirm the file exists first** — a missing file greps to nothing too, a false pass. Only then is the publish "passed"; if anything matches, the snapshot is contaminated — treat the publish as failed, report it, and do not hand the snapshot off. Then report the new version and snapshot path to the human.

**The frozen snapshot is PURE CONTENT — no frontmatter, no markers, no banner.** Version/status metadata lives in the filename + changelog only. `docspec publish` strips the working copy's YAML frontmatter (the section hash bookkeeping) and all invisible markers from the snapshot, so a reader opening it sees only the document. The version IS the snapshot filename; the record IS the changelog. (This is the publish-side of the same rule `apply` enforces: docspec machinery stays out of the deliverable.)

---

## Guardrails

**Do**
- Verify the edit gate is clean before running `docspec publish`.
- Let `docspec publish` promote the locked content as a byte-for-byte copy — never hand-edit at promotion.
- **Always bash-grep the frozen snapshot for residual markers/machinery after publish** — engine-stripped is not enough; you confirm it independently before it passes.
- Keep every published snapshot read-only and immutable.
- Write exactly one changelog line per publish.

**Don't**
- Don't publish without an explicit human trigger.
- Don't rewrite or edit during promotion.
- Don't publish with an unresolved **edit/proofread** finding or `[TBD]`/placeholder. (Open **audit** findings are non-blocking — shipping over one is the human's call, not a gate.)
- Don't mutate a previously published snapshot — `docspec publish` again to bump instead.
- Don't stamp version/status banners into the snapshot body — filename + changelog carry the version; the prose stays clean.

---

## Example

Human: "Edit's clean, ship it."

> **Publish gate — `handbook/_latest.md`**
> - Edit/proofread: 0 open findings ✓
> - Placeholders/`[TBD]`/`[!WARNING]`: none ✓
> - lint: 0 ERROR (1 WARN drift — advisory, surfaced) ✓
> - Human trigger: confirmed ✓
>
> Running `docspec publish handbook --level minor --note "expanded the eligibility section; tightened the summary"`:
> 1. Gate — `docspec check` + `docspec lint` clean (0 ERROR).
> 2. Promote — locked content copied verbatim.
> 3. Freeze — read-only snapshot written.
> 4. Bump — `1.0.0 → 1.1.0` (minor), per-section source hash stamped (semver; the snapshot IS the version).
> 5. Changelog — appends `| 1.1.0 | 2026-06-18 | Minor | expanded the eligibility section; tightened the summary |`.
>
> Published. `_latest` continues as the live working copy; `v1.1.0` is frozen under `archive/`.

Gate first, verbatim promotion, immutable snapshot, one changelog line — then it's done and undoable by nothing.
