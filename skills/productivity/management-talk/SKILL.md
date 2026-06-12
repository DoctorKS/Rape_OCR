---
name: management-talk
description: Rewrite engineer-to-future-self content (CODEX.md change-log entries, commit messages, debugging notes) for the user-facing surfaces of the Clinic-calendar app — the bilingual Thai/English README, in-app help text, tooltips, and any message a clinic-using doctor will actually read. Strips code identifiers, keeps product/feature names, translates mechanism into plain Thai/English. Trigger when the user asks to "update the README", "เขียน README", "เขียนคำอธิบายให้ผู้ใช้", "อธิบายแบบไม่ technical", "rewrite for the user", "add a feature line to README", or asks for in-app text / tooltip / help copy based on an engineering change.
---

# Management Talk (User-Facing Talk)

Take engineer-to-future-self content and reshape it for the people who actually use the app — clinic doctors reading the **README** or in-app help. The audience reads feature names but not code. They want to know *what it does for them*, in the same bilingual Thai/English voice the existing README uses.

Same translation rules apply across every user-facing surface in this repo. Pick the shape that matches where the text is going.

## When to invoke

- "update the README" / "add this to the README" / "เขียน README"
- "rewrite this for the user" / "อธิบายแบบไม่ technical" / "ทำให้คนทั่วไปอ่านเข้าใจ"
- "write the in-app help / tooltip / placeholder / button label"
- "ทำ help text" / "เขียน tooltip" / "เพิ่ม feature line"
- Any time engineering content (a post-mortem, a commit message, a CODEX.md entry) needs to flow into a surface a doctor-user will read.

If the destination is unclear after the trigger, ask one short question — *"README features section, or in-app help text?"* — and stop.

## Audience — who reads this

A doctor running clinic shifts who uses the app on iPhone and desktop. Comfortable with: clinic names, procedure names, drug trade names, the terms ค่านั่ง / DF / เวรเหมา / การันตี, basic web app concepts (login, sync, backup). Not comfortable with: code, function names, localStorage internals, Supabase RLS, commit SHAs.

They want: *what does this do for me, when does it help, what do I need to click.* They do not want: how the change works at the function level.

## Voice and tone

Match the existing README. Look at it before drafting.

**Bilingual Thai/English, Thai-primary.** The pattern in this repo is Thai headline / Thai-or-English detail, often with English in parentheses as a cross-reference (`📅 ปฏิทินรายเดือน · Monthly Calendar`). Don't switch to English-only.

**Keep.** App-internal feature names users see (`ค่านั่ง`, `DF หัตถการ`, `DF เครื่อง`, `เวรเหมา`, `การันตี`, `คอร์ส`, `ปฏิทินรายเดือน`), platform names users will recognize (`iPhone`, `Safari`, `Supabase`, `localStorage` when explaining backup risk).

**Strip.** JavaScript function names (`renderMonth`, `syncFromSupabase`, `savePatientRow`), localStorage key names (`entries`, `clinics_v2`), file paths (`index.html`, `supabase_schema.sql`), commit SHAs (`6fadf78`), CSS class names, branch conditions, code expressions.

**Translate.** Mechanism into one or two sentences of plain cause-and-effect. Not *"the `syncFromSupabase` function overwrote local rows when the server returned an empty patient array"* but *"ก่อนหน้านี้ ปุ่ม Refresh อาจทำให้ข้อมูลคนไข้ของเดือนปัจจุบันหายไปถ้า sync มาในจังหวะที่ Supabase ยังไม่ส่งข้อมูลคนไข้ครบ — ตอนนี้แก้แล้ว ข้อมูลในเครื่องจะถูกเก็บไว้เสมอ"*. Translate without lying — a sync race stays a sync race; a data-loss bug stays a data-loss bug.

**Don't over-strip.** Users of this app are doctors — they handle nuance. `localStorage`, `cloud sync`, `backup JSON`, `RLS / data scoping` are fine in the README; they appear there already.

**Bias toward** short paragraphs, emoji section markers (matching README style), tables when content is comparative, bullets when content is enumerative.

**Avoid:**

- Telling the user what to feel (*"this exciting new feature"*) — describe what it does, let them feel what they feel.
- Hedging that isn't really hedging (*"may sometimes help with"*). State it.
- Apologizing for past bugs in user-facing text. The fix is the apology. (A separate "Important Notes" line about backup is fine — that's a warning, not an apology.)
- Engineering-process minutiae. Users don't care that you bisected commits or used DevTools.

## Channel shapes

Same content, different shell. Pick the one that matches the destination.

### README feature line / section

Match the existing structure:

- Emoji + Thai headline + English subhead, e.g. `### 💾 Backup & Restore`.
- Bullets for sub-features, short clauses.
- Bold for the term users will look for; back-ticks for app-visible labels they'll see on screen.
- One concrete example per non-obvious feature.

Length: a feature gets 2–6 bullets. A whole section gets a short intro line + the bullets.

### Important Notes / warning line

For warnings (data loss risks, platform quirks, ITP wipes), match the existing `⚠️ หมายเหตุสำคัญ` section:

- Lead with the consequence in Thai (*"การสูญหายของข้อมูล — localStorage จะหายถ้า:"*).
- Bullet the specific triggers.
- End with the actionable mitigation (*"แนะนำ: Export JSON สำรองไว้เป็นประจำ"*).

### In-app help text / tooltip / placeholder

Lives inside `index.html` as user-visible strings. Constraints are tighter:

- Thai-primary, English only when it's a term the user already sees on screen.
- Under ~15 words for a tooltip; under ~40 for help text inside a modal.
- Imperative or descriptive, never instructional ceremony (*"กรอกชื่อคลินิก"* not *"กรุณากรอกชื่อคลินิกของท่านในช่องด้านล่างนี้"*).
- If it's a placeholder, write what would go in the field, not what to do (`เช่น คลินิก ABC` beats `กรอกชื่อ`).

### Commit message body (user-readable framing)

When the commit will be public-ish or you want the body readable without code context. Keep the engineering subject line (`fix:` / `feat:` / `docs:` from the post-mortem) but the body is plain language: *what changed for the user, and why.* No function names. One paragraph.

## Source material

The input is one of:

1. **A CODEX.md change-log entry** — reuse the per-change summary, drop the file/insertion counts.
2. **A post-mortem block** from this session — pull the *Symptom* and *Fix* sections; drop *Root cause* and *Why it slipped*.
3. **The current conversation** — if you just produced engineering content and the user says *"now in the README"* / *"now as a tooltip,"* reuse what's in context.

If the source is ambiguous, ask one question and stop.

## Output flow

1. **Confirm the channel** if not stated (README section, warning line, in-app text, commit body).
2. **Produce the draft** as a single chat block, formatted the way it would render in its destination.
3. **Default is print-only.** The user pastes it into `README.md` or `index.html` themselves.
4. **If the user asks you to edit the file directly:** do it, but show the diff first and wait for confirmation before saving. Especially careful with `README.md` — it's the canonical doc.
5. **One iteration is normal, three is a smell.** If the user is on the third revision, ask what specific framing or word choice is wrong — don't keep tweaking blindly.

## Worked example — same fix, three surfaces

**Source (post-mortem):**

> Symptom: After clicking the Supabase Refresh button, patient entries for the current month disappeared.
> Root cause: `syncFromSupabase()` overwrote local rows before the server response was fully populated…
> Fix: per-row merge; local wins if server row has no patient entries…
> Validation: tested on desktop Chrome and iPhone Safari…

### As a README feature line (add to the Backup & Restore section)

> - **🔄 Refresh จาก cloud** — กดปุ่ม Refresh เพื่อดึงข้อมูลล่าสุดจาก Supabase โดยข้อมูลคนไข้ในเครื่องจะถูกเก็บไว้เสมอ ไม่ทับโดยข้อมูล cloud ที่ยังโหลดไม่ครบ

### As an "Important Notes" warning line

> *(no addition needed — the bug is fixed and the existing localStorage warning still applies. Don't manufacture a warning to advertise a fix.)*

### As an in-app tooltip on the Refresh button

> ดึงข้อมูลล่าสุดจาก Supabase · ข้อมูลในเครื่องจะถูกเก็บไว้

### As a commit-message body

> Refresh ทับข้อมูลคนไข้ของเดือนปัจจุบันถ้า Supabase ตอบกลับมาก่อนที่ patient rows จะโหลดเสร็จ ตอนนี้ merge ทีละ row และเก็บข้อมูลในเครื่องไว้ถ้า cloud ส่งมาว่าง.

What changed across surfaces: same fact, different shape. README is feature-framed (what the user gets). Tooltip is action-framed (what the button does, what's safe). Commit body is cause-framed (what was wrong, what's now true). None of them mention `syncFromSupabase` or per-row merge logic.

## Rules

- **Never invent facts** to make the rewrite cleaner. If the post-mortem says "tested on desktop Chrome only," the README line doesn't claim cross-platform support.
- **Never strip a feature name a user will look for** during de-jargoning (`ค่านั่ง`, `DF`, `การันตี`, `เวรเหมา`, `Supabase`, `Backup JSON`). They're the bridge between the README and the in-app UI.
- **Don't add user-facing copy for bugs that are just fixed.** A fix doesn't need an announcement; the absence of the bug is the announcement. (Exception: when the fix changes user behavior — e.g., a new button — then yes, document it.)
- **Match existing voice and section structure** in README.md. Don't redesign the README to fit your draft; fit your draft to the README.
- **For Thai/English mix, default to Thai-primary** unless the surface is already English-only (e.g., the `File Structure` block).
- **Show the diff before editing `README.md` or `index.html` directly.** Print-only output needs no approval.
- **Stay out of advocacy.** This skill produces user-facing copy, not feature pitches. If the user wants a "what's new" announcement, confirm before reframing.
