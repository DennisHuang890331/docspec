---
name: dspx-publish
description: >-
  Ship a docspec document — only when the human explicitly pulls the trigger. Confirms the engine gate,
  runs the one irreversible publish (promote byte-for-byte, freeze a read-only snapshot, bump the
  version, log the changelog), then independently verifies the frozen artifact. Unlike apply it authors
  nothing — it gates and freezes already-finished content.
license: PolyForm-Noncommercial-1.0.0
compatibility: Requires the docspec CLI (installed via uv tool; not on PATH in a fresh shell — run it from the dir printed by `uv tool dir --bin`, never reinstall).
metadata:
  author: docspec
  version: "2.0"
---

Freeze it. Publish is the one irreversible action in docspec: it turns a working draft into an immutable, versioned snapshot. Because it cannot be undone, the human pulls the trigger — you run the mechanics, in order, and stop if any gate fails. `docspec guide` carries the exact publish sequence, flags, and paths — read them there, don't reconstruct from memory.

**Input**: an article the human has explicitly told you to publish. No explicit trigger → do not proceed.

**Steps**

1. **Confirm the document converged** — `docspec status <article>`: every leaf written and **none `stale-*`**; the `apply` copy-prep pass has run; `factcheck` has run at least once and its findings are triaged. "Every section drafted" is NOT "ready to ship" — the most common failure is declaring victory after apply and skipping factcheck. A document that never went through apply + factcheck is not publish-ready; say so and route back, don't pull the trigger.

2. **Gate** — `docspec check` (references resolve, structure intact) and `docspec lint` (cleanliness: no leaked machinery, no `[TBD]`/placeholder, no leftover `[!WARNING]`) both pass with **zero ERROR**. `docspec publish` re-runs these itself — it doesn't trust that apply ran. lint WARN findings (prose-drift, cross-document number/term consistency) are advisory — surface them, they do NOT block. Open **audit** findings don't block either; shipping over one is the human's call, not a gate.

3. **Migrating an existing project (first publish only)** — if it carries pre-docspec published versions and a revision history, do NOT run the first publish until the **Migration onboarding** recipe (projected by `docspec guide`) has been walked: the legacy versions registered into the freeze net, the history pre-seeded, and the first version seeded to continue the pre-docspec numbering. Restarting the numbering over a project already at a higher version breaks the chain — walk the recipe, then publish.

4. **Publish** — `docspec publish <article> --level <major|minor|patch> --note "<one line>"`. One irreversible shot: the engine gates, promotes the locked content **byte-for-byte**, strips the frontmatter + all invisible markers, freezes the read-only snapshot under `archive/`, bumps semver, and appends one changelog row. No rewrite, no edit, no "one last polish" at promotion — that content was finished by `apply`. Turning the snapshot into a typeset PDF is `release`'s separate, later concern.

5. **Self-verify with bash — do NOT just trust the engine** — at the exact snapshot path `docspec publish` printed (confirm the file EXISTS first — a missing file greps to nothing too, a false pass), grep for residual machinery (`dspx:section`, `{#`, `[TBD]`, `<!--`). It must print NOTHING. A match = the snapshot is contaminated = treat the publish as failed, report it, do not hand it off. Only then report the new version + snapshot path to the human.

**Pause if:**
- Any gate fails → stop and report. Do NOT "fix and continue" — return to `apply`.
- No explicit human trigger, or the document hasn't been through apply + factcheck.

**Output**

```
## publish gate — <article>
- status: all leaves written, none stale ✓
- check + lint: 0 ERROR (N WARN surfaced, advisory) ✓
- apply/factcheck run + triaged ✓   - human trigger: confirmed ✓
Published v<X.Y.Z> → docs/archive/<article>_v<X.Y.Z>.md
Self-verify (bash grep of the printed path): no residual markers ✓
```

**Guardrails**
- Never publish on your own initiative or without an explicit human trigger — this is the only hard boundary in the workflow.
- Promote byte-for-byte — never rewrite or edit at promotion.
- Always bash-grep the frozen snapshot yourself — engine-stripped is not enough; confirm it independently before it passes.
- Never touch, overwrite, or delete anything inside any `archive/` folder — published snapshots are immutable history; to change content, edit `_latest.md` and publish a NEW version. (A PreToolUse hook and a lint ERROR back this up.)
- One changelog line per publish; the version lives in the filename + changelog, never as a status banner stamped into the prose.
