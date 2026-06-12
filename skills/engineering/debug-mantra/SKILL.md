---
name: debug-mantra
description: Four-mantra debugging discipline for the Clinic-calendar single-file HTML app — reproduce, trace the fail path, falsify the hypothesis, cross-reference every breadcrumb. Recite the mantra block verbatim at the start of any debugging session, then apply the four steps in order before proposing any fix. Trigger on /debug-mantra and proactively whenever debugging starts — user reports a bug, says something is broken/throwing/failing/ไม่ทำงาน/พัง/error, asks to debug/diagnose/investigate, or pastes a stack trace, console error, or screenshot of broken behavior.
---

# Debug Mantra

Four-step discipline for any debug session. Recite verbatim, then apply in order.

## Recite this — verbatim, as the first thing in your first response

> **Mantra:**
> 1. **First is reproducibility.** Can the issue be reproduced reliably?
> 2. **Know the fail path.** DevTools first; then source trace + state enumeration; then in-code instrumentation.
> 3. **Question your hypothesis.** What would disprove it?
> 4. **Every run is a breadcrumb.** Cross-reference all of them.

Then begin work.

---

## 1. Reproduce reliably

Build a runnable repro before anything else. For this app the repro is a click-path: which browser, what month, which clinic, logged in or not, fresh localStorage or carried-over.

- **Reliable repro** → write it down as a numbered click-path the user can replay. Capture: browser (Safari iOS / Chrome desktop / etc.), URL state, login state, whether localStorage was pre-seeded with a backup JSON, and the exact action that triggers the failure.
- **Flaky repro** → narrow the timing window before debugging. Try: throttle the network in DevTools, force a Supabase round-trip, switch between months/clinics quickly, log out / log in to flip session state.
- **No repro at all** → stop. Ask the user for: a screenshot, the **console log** (DevTools → Console), the **localStorage dump** (DevTools → Application → Local Storage → copy as JSON), and the steps they took. Do **not** proceed to hypothesise.

### Reproducibility traps in this app

- **Safari ITP wipes localStorage** after ~7 days of inactivity. A bug that "only happens after I don't use it for a week" is often state loss, not a logic bug. Check whether the user's localStorage is empty before assuming code broke.
- **Supabase session vs localStorage state can diverge.** A logged-in user might be reading from cloud while a logged-out user reads from local. Confirm which path the failing run was on.
- **Cached `index.html`.** iPhone Safari caches aggressively. A "the fix didn't work" report often means the old HTML is still served. Confirm a hard reload (or version bump) before redebugging.
- **Backup JSON shape drift.** An imported `.json` from an older app version may be missing fields the current code expects. If the bug only reproduces after import, suspect schema, not logic.

Target: a deterministic 1-minute repro the user (or you) can run from a known starting state.

## 2. Know the fail path

Once reproducible, find *where* the code breaks and *what stops it from breaking*. Try in this order — escalate only when the prior tactic fails.

1. **Browser DevTools first.** Open Console (errors, stack traces) and the Sources tab (set a breakpoint at the suspected handler — `addPatient`, `savePatientRow`, `syncFromSupabase`, the month-render function, etc.). One breakpoint beats ten `console.log`s. For iPhone bugs, attach Safari Web Inspector over USB — same tooling.
2. **Source trace + state enumeration.** With `index.html` open, grep the function names from the stack trace or the visible UI strings. List every piece of state that can influence the outcome:
   - **localStorage keys** (clinics, entries by month, machine list, settings, auth tokens).
   - **Supabase session** (logged in / out, which user_id, RLS scope).
   - **UI state** (current month, selected clinic, open modal, form values not yet saved).
   - **Branch conditions** in the handler — guarantee logic, %-vs-fixed DF, single-stream vs multi-row procedure rendering.
   Flip one at a time and watch the failure move.
3. **In-code instrumentation.** If DevTools and source-reading don't crack it, add `console.log('[DBG-a4f2]', label, value)` at suspected sites and dump relevant state. Tag every probe with a unique prefix so cleanup is a single grep before commit. Let the trace show where reality diverges from your model.

## 3. Falsify the hypothesis

When a candidate root cause surfaces, scrutinise it **before** patching.

- Does it actually explain the symptom end-to-end? Walk it through the click-path you wrote in step 1.
- What is the simplest **proof**? What is the cleanest **disproof**?
- Run the **disproof first**. If the hypothesis survives, it's real. If it dies, you saved yourself from chasing a phantom.
- Generate 3–5 ranked hypotheses, not one. Single-hypothesis thinking anchors on the first plausible idea — especially in a single-file app where everything looks adjacent.

Worked examples of cheap disproofs in this app:
- "It's a sync bug" → log out, wipe Supabase, retry from pure localStorage. If it still breaks → not sync.
- "It's a guarantee-logic bug" → set the clinic's guarantee to 0 and retry. If it still breaks → not guarantee.
- "It's a month-boundary bug" → reproduce in the middle of the month. If it still breaks → not boundary.

## 4. Every run is a breadcrumb

Maintain a running **ledger** of every experiment in this session. Each entry: what changed, what happened, what it ruled in or out. In a single-file app it's easy to forget you already tried something three iterations ago — write it down.

- When a new hypothesis surfaces, walk the ledger. Does it hold for **every** prior observation, not just the most recent?
- If any past run contradicts it, the hypothesis is wrong or incomplete — refine or discard.
- When in doubt, design the **single experiment** whose outcome makes the cause certain. Run that next, instead of churning on adjacent runs.
- Update the ledger after every run. It is your memory across the session and the raw material for the post-mortem.

---

## Operating rules

- Recite the mantra block **once** per debug session, in your first response. Do not re-recite mid-session.
- Recite **verbatim**. Never paraphrase, shorten, or skip lines of the recital.
- If the user says "skip the mantra" → skip the recital but still apply the four steps silently.
- Apply the four steps **in order**:
  - Do not propose a fix before #1 is satisfied (reliable repro exists).
  - Do not start testing hypotheses before #2 has narrowed the fail path.
  - Do not commit to a hypothesis before #3 has tried to disprove it.
  - Do not declare a hypothesis correct until #4 confirms it against every prior breadcrumb.
- If you catch yourself proposing a fix without a reliable repro, stop and return to step 1.
- Before handing the user a fix, remove every `[DBG-xxxx]` probe you added (single grep over `index.html`).
- The mantra is a constraint **you** carry through the session — not advice to deliver back to the user.
- Once the fix is validated, the breadcrumb ledger is the raw material for [`post-mortem`](../post-mortem/SKILL.md) — offer to write the CODEX.md change-log entry from it.
