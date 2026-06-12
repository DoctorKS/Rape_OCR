# Engineering skills

- **[debug-mantra](./debug-mantra/SKILL.md)** — Four-mantra debugging discipline for the Clinic-calendar app: reproduce → trace the fail path → falsify → cross-reference breadcrumbs. Browser DevTools first; localStorage / Supabase / iOS Safari ITP as the real surfaces.
- **[post-mortem](./post-mortem/SKILL.md)** — Record a fixed bug as a CODEX.md change-log entry + commit message. Audience is future-you opening this repo cold; code identifiers welcome.
- **[scrutinize](./scrutinize/SKILL.md)** — Outsider-perspective review of a plan or proposed edit to `index.html`. Questions intent first, then traces the actual click-path; flags backup-JSON and Supabase ↔ localStorage drift as recurring blind spots.
- **[explain-before-edit](./explain-before-edit/SKILL.md)** — Force a four-block preview (what / why / step-by-step / diagram) and an explicit approval gate before any code edit. ASCII tree for structure changes, Mermaid for flow changes.
- **[session-review](./session-review/SKILL.md)** — End-of-work recap + self-audit. Re-reads the files actually touched (not memory), flags drift / half-done work / un-stripped probes / stale docs. Verdict: ✅ clean / ⚠️ needs follow-up / ❌ broken.
