---
name: post-mortem
description: Write the engineering record of a fixed bug in the Clinic-calendar app — symptom, root cause, fix, validation, and how it slipped through. Audience is future-you (and future AI assistants) opening this repo months from now. Destination is a CODEX.md change-log entry plus the commit message. Use after a debug session lands a validated fix, before committing. Trigger on /post-mortem, when the user says "write the post-mortem / postmortem / RCA / root cause", "document this fix", "บันทึก fix", "เขียน change log", "write up what we did", or hands you a fixed-and-validated bug and asks for the writeup.
---

# Post-mortem

The engineering record of a bug fix. Written **after** debugging lands a real, click-tested fix, **for** future-you and any AI assistant who opens this repo cold and needs to recover the mental model fast.

Two outputs, same source material:
- A **CODEX.md change-log entry** in the existing format (commit SHA + summary + per-file insertion/deletion counts).
- A **commit message** — short subject + body that walks the cause and fix.

For the user-facing rewrite (README "Features" line, in-app help text), hand the finished post-mortem to [`management-talk`](../../productivity/management-talk/SKILL.md). They compose: post-mortem owns the engineering truth, management-talk reframes it for clinic-user-readable surfaces.

## When to invoke

- `/post-mortem`
- "write the post-mortem / postmortem / RCA / root-cause analysis"
- "document this fix" / "write up the root cause" / "close out this bug with a writeup"
- "บันทึก fix" / "เขียน change log" / "อัพเดท CODEX.md"
- After a debug session has clearly landed a validated fix, proactively offer to draft one.

## When NOT to use

- **Bug not fixed yet, or fix not validated by clicking through the app.** A post-mortem of a hypothesis is misleading. Refuse and say what's missing.
- **Trivial fix** (typo, one-line style tweak, color change). The commit message alone is the record. Don't manufacture a change-log entry for a one-liner — though it can still go into CODEX.md as a short bullet (see existing entries like `9a14f0b style: make machine cards blue`).
- **Refactor with no behavior change.** Note it in the commit, but a post-mortem implies a bug existed.

## Required inputs — refuse to draft without these

Before writing a single line, confirm all four. If any are missing, list what's missing and stop:

- [ ] **Reliable repro** existed (a click-path that triggered the failure before the fix).
- [ ] **Root cause is known** (the actual mechanism, not "probably something with sync").
- [ ] **Fix is identified** (the specific edit to `index.html` / `supabase_schema.sql`, ideally already staged or committed).
- [ ] **Fix is validated** (the original click-path now succeeds; ideally tested on the platform that originally failed — iPhone Safari, desktop Chrome, etc.).

These map directly to `debug-mantra` steps 1–4. If you came in via `debug-mantra`, the breadcrumb ledger from step 4 is your raw material — pull from it.

## Structure

Five blocks. **Symptom, Root cause, Fix, Validation are mandatory.** Why-it-slipped is conditional but usually present.

### 1. Symptom _(mandatory)_
What broke, in user terms. One or two sentences. Concrete: which screen, which action, what the user saw (or didn't see). Reference the platform if it mattered (iPhone Safari vs desktop).

### 2. Root cause _(mandatory)_
The actual bug mechanism in `index.html` (or `supabase_schema.sql`). **Code identifiers welcome and expected** — function names, the localStorage key involved, the Supabase table/column, the branch condition that was wrong. Walk the cause chain end-to-end so future-you can grep back to the offending lines. This is the most expensive section and the reason the post-mortem exists.

### 3. Fix _(mandatory)_
What changed and **why this change addresses the root cause** rather than hiding the symptom. Reference the commit SHA once it exists (or describe the staged diff). If a previous fix attempt papered over the symptom, name it and explain what was wrong — that history matters.

Include per-file insertion/deletion counts (`index.html`: X insertions, Y deletions) to match the existing CODEX.md format.

### 4. Validation _(mandatory)_
How you know the fix works. Concrete:
- Original click-path now succeeds (write the click-path).
- Tested on: which browsers / which platforms.
- Edge cases checked: empty state, fresh localStorage, logged-out, mid-month vs month-boundary, large data set, restored-from-backup state — whichever were relevant.

State coverage honestly. If you only tested on desktop Chrome, say so: *"validated on desktop Chrome; not retested on iPhone Safari."* Implying broader coverage is the failure mode that breeds repeat regressions.

### 5. Why it slipped through _(usually present)_
What allowed this bug to exist. Pick the real reason:
- New code path not exercised before this session.
- Schema/state shape changed in an earlier commit; this code wasn't updated.
- Platform-specific behavior (Safari ITP, iOS cache, RLS policy) not tested.
- Backup-JSON import path; data shape from an older version.
- Honest "I didn't think about that edge case" is a valid answer — it tells future-you what to think about next time.

If the honest answer is "no good reason — I should have caught this," say so. The point is future-you learning, not self-flagellation.

## Output flow

1. **Confirm all four required inputs are satisfied.** If any are missing, list them and stop. Do not draft.
2. **Produce two artifacts** in one chat block:
   - **CODEX.md change-log entry** in the existing format (commit SHA + one-line summary + 1–2 bullet detail lines + per-file insertion/deletion counts).
   - **Commit message** (subject ≤ 72 chars, type prefix matching existing convention — `fix:`, `feat:`, `docs:`, `style:` — then a body if the cause needs explaining).
3. **Wait for the user to confirm before editing CODEX.md or committing.** Default is print-only; the user pastes and commits.
4. **Offer the management-talk handoff:** *"Want me to update the README features list or in-app help text? I can hand this to `management-talk`."* Don't do it automatically.

## Tone

This is engineer-to-future-self. Different from `management-talk`:

- **Code identifiers are first-class.** Function names, localStorage keys, Supabase column names, branch conditions, commit SHAs — keep them all. The whole point is that you can grep your way back to the change in six months.
- **Mechanism over narrative.** Don't soften "the `renderMonth` loop reused a stale `clinic_id` from the previous iteration" into "a rendering issue." Be exact.
- **Active voice, concrete subjects, short paragraphs.**
- **No hedging.** "I think" / "maybe" / "appears to" — drop. State it or don't write it. (You did the work; you know.)
- **No advocacy.** A post-mortem records what happened and what's next. If you want to argue for a refactor, file it as a separate change-log item or TODO.

## Worked example — Supabase sync wiping patient rows

> **Symptom.** After clicking the new Supabase Refresh button, all patient entries for the current month disappeared from the calendar. Reproduced reliably on desktop Chrome — log in → switch to a month with entries → press Refresh.
>
> **Root cause.** `syncFromSupabase()` in `index.html` overwrote the local `entries` object with the server response before reconciling. When the server response had not yet populated patient rows for the active month (Supabase RLS scoping returned the row set but not the nested patient array on first fetch), the assignment `entries[monthKey] = serverEntries[monthKey]` replaced a populated client-side object with an empty one. The render loop then drew an empty month, and the next localStorage save persisted the empty state — destroying the data permanently.
>
> **Fix.** `abbed78 fix: preserve patient rows during sync` and `6fadf78 feat: add Supabase refresh button`. Sync now merges per-row instead of replacing per-month: if the server's row for a given date has no patient entries but the local row does, the local row wins. localStorage write is also deferred until after the merge completes successfully.
>
> `index.html`: 24 insertions, 8 deletions.
>
> **Validation.** Original click-path (log in → switch month → Refresh) now preserves entries on desktop Chrome and iPhone Safari. Tested with: a month full of entries, an empty month, and a month with mixed Supabase-only and local-only rows. Not retested on Android Chrome — same code path as desktop Chrome, expected to behave identically.
>
> **Why it slipped through.** The Refresh button is a new surface (`6fadf78`); before it existed, sync only ran on login, where the local state was always empty so the bug was invisible. The latent assumption "server state is always more complete than local" was true at login time and false at refresh time.

## Rules

- **Refuse to draft without all four required inputs.** A post-mortem of a hypothesis is worse than no post-mortem.
- **Never invent root cause, validation runs, or commit SHAs.** If a section's facts aren't there, ask.
- **Match the existing CODEX.md format** (commit SHA, summary line, bullet detail, per-file insertion/deletion counts). Don't redesign the change log unilaterally.
- **State validation coverage honestly.** "Tested on desktop Chrome only" is information, not a hole.
- **Wait for explicit confirmation before editing CODEX.md or running `git commit`.** Print-only output needs no approval.
- **Use the existing commit-type convention** (`fix:` / `feat:` / `docs:` / `style:`) — match what the prior commits use, don't introduce new types.
- **One iteration is normal, three is a smell.** If the user is revising for the third time, ask what section is actually wrong — don't keep tweaking blindly.
