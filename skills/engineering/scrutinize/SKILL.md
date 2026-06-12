---
name: scrutinize
description: Outsider-perspective end-to-end review of a proposed change to the Clinic-calendar app — a plan, a diff, a staged edit, or a design idea. First questions intent and whether a simpler approach would achieve the same goal, then traces the actual code path through `index.html` to verify the change does what it claims. Output is concise, actionable, and every call carries its rationale. Trigger on /scrutinize and proactively whenever the user asks to review, audit, sanity-check, "ดูให้หน่อย", or get a second opinion on a plan, diff, design, or proposed edit.
---

# Scrutinize

Stand outside the change and ask whether it should exist at all, then verify it actually does what it claims end-to-end. Especially valuable on a solo project — you have no other reviewer; this skill is the second pair of eyes.

## Operating stance

- **Outsider.** Forget who wrote it and why they think it's right. Read the artifact cold, as if you'd never seen the codebase.
- **End-to-end, not diff-local.** The diff is the entry point, not the scope. Follow the call graph through real code paths in `index.html`.
- **Actionable, concise, with rationale.** Every finding states *what to change*, *why*, and *what evidence* led you there. No filler, no restating the diff back.

## Workflow

Run these in order. Do not skip ahead.

### 1. Intent — what is this actually trying to do?

- State the goal in one sentence, in your own words. If you cannot, the change is underspecified — say so and stop.
- Ask: **is there a simpler, smaller, or more elegant way to achieve the same goal?** Consider:
  - **Doing nothing** (is the problem real, or a phantom from a single bad data point?).
  - **Reusing something that already exists** in `index.html` instead of adding a new function or duplicate state path.
  - **A smaller change** that solves 90% of the goal with 10% of the risk (e.g., a one-line guard vs. a new state machine).
  - **Solving it at a different layer** — CSS vs JS, schema vs runtime, Supabase RLS vs client check, README documentation vs new feature.
- If a better alternative exists, name it explicitly with rationale. This is the most valuable thing you can output — surface it before the line-by-line review.

This step matters extra on a single-file app: every new function, key, or modal lives in the same `index.html` and compounds with everything else. A change avoided is a change that can't break.

### 2. Trace — walk the actual code path

- For each behavior the change claims, trace the path end-to-end through the real code, not just the lines in the diff:
  - **Entry point** (button click handler, page-load hook, `addEventListener`) → **call sites** → **branches taken** → **state mutated** (localStorage keys, Supabase tables, in-memory `entries` / `clinics` / `machines`) → **render side effect** (which DOM update, which month/clinic view refreshes).
  - Include the unchanged code on either side of the diff. Bugs hide at the seams — a new field that the save function writes but the load function never reads, a render call that runs before state is committed, a Supabase write that races the local update.
- For a plan or design doc: trace the proposed flow against the existing `index.html`. Where does it touch reality? What does it assume that isn't true (e.g., assumes `entries[monthKey]` always exists, but it's `undefined` for an empty month)?
- Note every place the trace surprises you (unexpected branch, dead code reached, state you didn't know existed). Surprises are signal.

### 3. Verify — does it actually do what it claims?

For each claim the change/plan makes, answer:

- **Does the traced code path actually produce that behavior?** Walk it explicitly. *"It claims X. Path: button → `handler()` → mutates `entries[m][d]` → calls `renderMonth(m)`. At `renderMonth`, [observation]. Therefore [holds / doesn't hold]."*
- **What inputs / states would break it?** Edge cases this app actually has:
  - **Empty / undefined**: a month with no entries, a clinic with no machines, a patient with zero procedures, a user with no Supabase session.
  - **Boundary**: month-end (Feb 28 vs 29, 31-day vs 30-day), midnight crossing during a save.
  - **Platform**: iPhone Safari (ITP, cache, touch vs click), desktop Chrome, Android Chrome.
  - **State divergence**: logged in vs logged out, localStorage vs Supabase out of sync, restored-from-backup-JSON state with a stale schema.
  - **Concurrency**: rapid taps, modal open while sync runs, navigating away mid-save.
- **What does it silently change?** Performance (large data set rendering), error handling (does a Supabase failure now lose data instead of falling back to local?), data shape (new field that older backup JSONs won't have), in-app text the user reads.
- **How was it verified?** There's no test suite — verification is clicking through the app. Did the user actually click the relevant path, or did they only inspect the code? Did they test on the platform that actually exhibits the bug?

### 4. Report

Output one tight section per finding. Order by severity (blocker → major → nit). For each:

- **Finding** — one sentence, specific. Cite `index.html:<line>` or the function name when applicable.
- **Why it matters** — the consequence to the user (lost entries, wrong totals, iPhone-only break), not the principle.
- **Evidence** — the trace step or input that exposes it.
- **Suggested change** — concrete, minimal.

Close with a one-line verdict: ship / fix-then-ship / rework / reject — with the single biggest reason.

## Operating rules

- **No rubber-stamps.** "LGTM" is not an output. If you genuinely find nothing, say what you traced and what you checked, so the user can judge whether your review covered the surface they cared about.
- **Cite or it didn't happen.** Every claim about the code references a specific function, line, or click-path. No vague "this might break under load."
- **Distinguish claim from verification.** "The change says X" and "I traced X and confirmed / refuted it" are different — keep them separate in the output.
- **One simpler-alternative pass is mandatory.** Even on small changes, spend one breath asking if the whole thing is necessary. Skip only if the user explicitly says "don't question scope."
- **Don't pad with style nits when there's a structural problem.** If step 1 or step 2 surfaces a real issue, lead with it; defer nits or drop them.
- **Backup-JSON compatibility is a recurring blind spot.** Any change that adds, renames, or removes a field in `entries` / `clinics` / `machines` needs a question: *what happens when an older backup JSON is imported?* Flag it every time.
- **Supabase ↔ localStorage symmetry is a recurring blind spot.** Any state-write change needs a question: *does the same change run on both code paths, and do they end up in the same shape?*
- **No flattery, no hedging.** "This is a great change but..." adds nothing. State the finding.
