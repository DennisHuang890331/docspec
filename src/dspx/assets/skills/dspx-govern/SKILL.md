---
name: dspx-govern
description: >-
  Project governance for the main agent — record what the owner must decide, transcribe the owner's
  rulings, keep project-level decisions current, run the single project roadmap, review impact, and
  hand over with a one-page status. Use when the owner makes or is asked for a decision, when a
  direction changes, when checking progress, before handing over, or at the start of a session to
  see where things stand. Unlike develop it does not shape a document; it governs the whole project.
license: PolyForm-Noncommercial-1.0.0
compatibility: Requires the docspec CLI (installed via uv tool; not on PATH in a fresh shell — run it from the dir printed by `uv tool dir --bin`, never reinstall).
metadata:
  author: docspec
  version: "1.0"
---

Keep the project's authority straight. The owner is the only source of rulings; you read them back and record, never rule. Every record goes through docspec commands — never edit `docspec/governance/` or `docs/project/` by hand (a hook blocks it and the seal would break).

**Input**: a session start, an owner ruling, a direction change, a progress check, or a handover.

**Steps**

1. **Orient first** — `docspec brief` (one page: next steps, pending approvals, open questions, items needing review, recent rulings, progress). Read it before anything else; drill down only with filtered queries (`docspec decision list --json`, `docspec roadmap --json`, `docspec trace <id>`), never by reading whole files.

2. **Ask, don't assume** — when the owner must decide something, record it: `docspec question add --title "…" --body "<plain words, the options>"`. If the owner says they did not understand, `docspec question explain <id>` and explain again in plain language.

3. **Read back, then record** — when the owner rules, restate it in plain words in the conversation ("I'll record: …. Is that right?") and WAIT. Only after the owner confirms: `docspec ruling add --quote "<the owner's exact words>" --read-back "<your restatement>" --confirmed "<the owner's confirming reply>" [--answers <Q-id>] [--supersedes <RL-id>] [--provisional]`. If they correct you, restate again. If the owner later says a ruling was recorded wrong: `docspec ruling reject <id> --reason "<their words>"`, then review `docspec impact`.

4. **Keep decisions whole** — `docspec decision add --title … --statement "<the complete current text>" --based-on <RL-id>`; to change one, add a new decision with `--supersedes <D-id>` whose statement is the **full merged text** (never "the later one wins where they conflict"). `docspec decision activate <id>` needs at least one ruling behind it that has not been rejected. Document sections that must follow a project decision point to it with `realizes: [gov:<id>]`.

5. **Review impact** — after a supersede, withdrawal or rejected ruling, `docspec impact`. For each suspect flag: look at the item, fix it or explain why it still holds, then `docspec impact clear <S-id> --reason "…"`. For each listed document section: review the prose against the new decision, then repoint its `realizes` to the successor (via develop/apply).

6. **Run the roadmap** — `docspec roadmap` shows milestones (checkpoint vs deliverable) and derived status. Add work with `docspec roadmap add --title … --milestone <M-id> --ref change:<id>|doc:<section>|gov:<id>|swc:<software change>`; link work as it starts (`roadmap link`); close ref-less small work with `roadmap done <id> --note`; record an owner-ruled exception with `roadmap waive <id> --ruling <RL-id> --note … --reopen-when …`. Never hand-write a status: it is derived.

7. **Hand over** — `docspec brief --write` regenerates `docs/project/status.md`, `design.md` and `pending.md`. Tell the owner, in plain words, which questions are waiting for them.

**Pause if:**
- The owner's words are ambiguous → record a question, ask, wait.
- The owner has not confirmed your read-back → do not record the ruling; ask again.

**Output**

```
## govern — <what happened>
Recorded: <questions / rulings (with the owner's confirming reply) / decisions>
Impact: <suspects raised or cleared, sections to review>
Roadmap: <items added / linked / closed>
For the owner: <plain-language list of what needs them, ids in brackets>
```

**Guardrails**
- Quote the owner verbatim; your interpretation goes in its own field, never into the quote.
- Never rule or confirm on the owner's behalf; `--confirmed` holds the owner's actual reply, never your own words.
- Talk to the owner in plain language: say what a thing is first, put ids in brackets.
- Section-level normative decisions stay in the document tree (develop); only cross-cutting project decisions live here.
