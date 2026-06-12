---
name: session-review
description: End-of-work recap and self-audit of everything Claude actually did in this session — files touched, why, and what might be wrong. Fires proactively when a unit of work finishes (fix applied, feature landed, doc round complete, user signals satisfaction). Re-reads the files (does not recap from memory), flags inconsistencies / missed follow-ups / un-stripped debug probes / drift between related files, and ends with a verdict: clean / needs follow-up / broken. Also fires on /session-review or when the user says "review what you did", "what did you change", "สรุปที่ทำไป", "ตรวจงานหน่อย", "check งานที่ทำ". Use after every coherent unit of work — this is the safety net that catches what `explain-before-edit` gated past.
---

# Session Review

The end-of-work safety net. After a unit of work lands, stop, re-read the files you actually touched, recap what changed, and audit yourself critically against the current file state — not against memory of what you intended to do. Memory is the failure mode this skill exists to catch.

## When to invoke

Fire proactively when a **unit of work** has clearly finished:

- A bug fix has been applied and the repro now passes.
- A feature has been implemented and the user has tried it (or said "looks good").
- A round of doc / skill / README updates is complete.
- The user signals satisfaction: *"thanks"* / *"perfect"* / *"ok done"* / *"ดีแล้ว"* / *"พอแล้ว"* / *"จบ"*.
- The conversation is about to shift to a new topic and the previous topic produced edits.

Also fire on explicit invocation:

- `/session-review`
- "review what you did" / "what did you change" / "summarize what just happened"
- "สรุปที่ทำไป" / "ตรวจงานหน่อย" / "check งานที่ทำ" / "ดูที่แก้ไปอีกที"

## When NOT to fire

- **No edits actually landed.** A pure-conversation turn (questions, planning, drafts that weren't applied) has nothing to review. Say so and stop.
- **Mid-debug, no fix yet.** If the breadcrumb ledger is still open, this is `debug-mantra`'s turf, not review's.
- **The user already saw and approved the work piece-by-piece** *and* explicitly said "no need to recap." Honor it.
- **A single trivial edit** (color swap, typo). Inline confirmation is enough; don't manufacture a full audit.

## The two-section output

### 1. Recap — what actually happened

Numbered list, in order of application. For each entry:

- **File** — `index.html`, `README.md`, `CODEX.md`, `.claude/skills/.../SKILL.md`, `supabase_schema.sql`, etc.
- **What changed** — function / section / heading. Be specific (`renderMonth()`, the "Backup & Restore" section, the `confirmDeleteClinic` helper). Not "various edits."
- **Why** — one line. Pulled from the original user request or the `explain-before-edit` preview that gated it.

Order by application order, not by importance. The user wants the story of the session.

### 2. Self-audit — what might be wrong

**Re-read every file in the recap before writing this section.** Do not audit from memory. The whole point of this skill is that memory is unreliable; the file on disk is the truth.

For each touched file, check these classes of failure. Skip categories that don't apply, but check every category that does.

#### Drift between files

The single-file HTML app + sidecar markdown means changes often need to land in two places to stay consistent:

- New feature added to `index.html` → README "Features" section should mention it. If it doesn't, flag.
- New column / table touched in `supabase_schema.sql` → `index.html` Supabase calls and `entries`/`clinics` shape should match. Mismatch is a blocker.
- New feature → CODEX.md change-log entry should exist (matching the existing format).
- Skill cross-references — if you edited one of `.claude/skills/**/SKILL.md` and it references other skills by path, verify those paths still resolve.

#### Half-done work

- Function defined but never called, or called but never defined.
- Modal markup added but no JS wired to open/close it.
- New state field written but never read (or vice versa).
- Comments / `TODO` / `FIXME` left in the change.
- `[DBG-xxxx]` console.log probes from `debug-mantra` not stripped. Single grep — if any survive, flag every one.
- Imports / script tags referenced but not added.

#### Step-vs-disk mismatch

If an `explain-before-edit` preview was approved with N steps, the disk should reflect N steps. Compare:

- Were all N steps actually applied?
- Were any *extra* steps applied that the user didn't approve? (This is the worst failure mode — sneaking in "while I was there" changes.)
- Was a step partially applied (e.g., HTML markup added but the matching JS handler skipped)?

#### Backup-JSON and Supabase compatibility

For any change to the shape of `entries` / `clinics` / `machines`:

- What happens if a user imports an older backup JSON missing the new field? Is there a default or migration?
- Does the same shape appear in both the localStorage path and the Supabase path? If not, sync will produce a divergent state.

#### Platform coverage

- iPhone Safari specifically tested for the changed click-path? If not and the change touches UI, flag as "untested on the platform users actually run."
- Behavior under empty state (no entries, no clinics, no Supabase login)?

#### Documentation hygiene

- README still accurate (no stale feature list, no broken file paths)?
- CODEX.md change log updated for any landed commit?
- Skill descriptions still match what the skill actually does, if you edited a skill?

#### Output each finding as

- **Severity** — 🔴 blocker / 🟡 major / 🔵 nit.
- **Finding** — one sentence, file + line / function when applicable.
- **Where to look** — the specific spot to verify.
- **Suggested fix** — concrete, minimal. (Don't apply it. Surface it.)

If a category check passes cleanly, don't pad the output by listing the categories you checked — only mention what you actually checked when audit finds nothing, so the user can judge coverage.

### Verdict — one line

End with exactly one of:

- ✅ **Clean.** Recap shows N changes, audit found nothing across {categories checked}.
- ⚠️ **Needs follow-up.** N items: {one-line list}. Nothing broken, but the session isn't really done until these land.
- ❌ **Broken.** N items at blocker severity: {one-line list}. Do not commit / push this state.

## Operating rules

- **Re-read the files. Don't recap from memory.** This is the single rule that makes this skill worth running. If you skip the re-read, you're just summarizing your own intentions — which is exactly the failure mode you're meant to catch.
- **Audit your own work critically.** No self-defense. If you misread an instruction earlier in the session and now the disk reflects the misread, the audit catches it — don't rationalize it.
- **Don't audit drafts that weren't applied.** Only audit what actually landed on disk. Discarded drafts and previewed-but-not-approved changes are not in scope.
- **Don't grade the user.** "User should have asked for X" is not a finding. Findings are about the code and docs, not the brief.
- **Lead with blockers.** If audit finds a 🔴, surface it at the top of the audit section — don't bury it after a tidy recap.
- **If audit is clean, say what you checked.** "✅ Clean. Re-read `index.html` and `README.md`; verified the new function is called from the button handler, the README features section mentions it, and no `[DBG-]` probes survived." Empty rubber-stamps are not allowed.
- **Honor session-level opt-outs.** If the user has said "no recaps this session," skip the proactive fire. Still respond if invoked explicitly.
- **One iteration is normal, three is a smell.** If the user keeps disagreeing with the audit, ask which finding specifically is wrong — don't keep re-grading the same files.

## Pairing with the rest of the engineering set

This skill is the session-level safety net. The single-change tools each have their own scope:

```
debug-mantra   → diagnose a single bug
scrutinize     → review a single plan / diff before applying
explain-before-edit → preview gate on each edit
post-mortem    → record a single fixed bug into CODEX.md + commit
management-talk → translate a single change into README / in-app text
session-review → recap + audit across everything the session did
```

If `session-review` finds an issue, the right tool to fix it is one of the others — not this skill. This skill surfaces, it doesn't fix.

## Worked example

User: *"ดีแล้ว"* after a session that landed a delete-confirmation modal.

> **Recap.**
> 1. `index.html` — added `confirmDeleteClinic(id)` helper. Why: gate destructive clinic-delete behind a modal so single misfires on iPhone don't wipe history.
> 2. `index.html` — changed clinic-row delete button `onclick` to call `confirmDeleteClinic(id)` instead of `deleteClinic(id)` directly.
> 3. `index.html` — added `<div id="confirmDeleteModal">` markup near the existing patient-edit modal. Cancel + Confirm buttons.
>
> **Audit.** Re-read `index.html`.
>
> - 🟡 **Major. README features list not updated.** `README.md` "Clinic Management" section still says "เพิ่ม / แก้ไข / ลบ คลินิกได้ไม่จำกัด" with no mention of the new confirmation step. Look at `README.md` line ~17. Suggest a one-line addition or call `management-talk` to draft it.
> - 🔵 **Nit. CODEX.md change-log entry not yet written.** If you're about to commit this, add the `feat: add clinic delete confirmation modal` entry first to keep the log format consistent. `post-mortem` can draft it.
> - 🔵 **Nit. iPhone Safari path not explicitly tested.** Touch behavior on the Confirm button hasn't been verified on the platform users actually run from the home screen.
>
> Checked: function defined and called (✓), no `[DBG-]` probes (✓), no half-wired modal (✓), no schema shape change so backup-JSON / Supabase compatibility N/A.
>
> **Verdict: ⚠️ Needs follow-up.** 1 major (README drift), 2 nits (CODEX.md entry, iPhone test). Code is correct; the session isn't really done until docs catch up.

What this audit did that a memory-based recap wouldn't have: noticed `README.md` was *not* in the touched-files list, which itself is the finding. The recap is the easy part; the audit is the value.

## Rules

- **Re-read the files actually changed before writing the audit section.** Non-negotiable.
- **Don't fabricate findings to look thorough.** If audit is clean, say so and name what you checked.
- **Don't bury blockers.** A 🔴 finding goes at the top.
- **Never apply fixes from inside this skill.** Surface them; route to the right skill (`post-mortem`, `management-talk`, `explain-before-edit`-then-edit).
- **Match the existing verdict vocabulary** (✅ / ⚠️ / ❌). Three-state, no fourth option.
