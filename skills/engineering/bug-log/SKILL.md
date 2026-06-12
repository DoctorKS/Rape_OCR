---
name: bug-log
description: Use whenever a bug is found, investigated, reproduced, or fixed in this repo; ensures bug_log.txt is updated with concise evidence, cause, fix, and verification.
---

# Bug Log

When work in this repo uncovers a bug, update `bug_log.txt` before finishing the turn.

## Workflow

1. Confirm the bug from evidence: screenshot, command output, failing test, user report, or code path.
2. Add a short entry to `bug_log.txt`.
3. Include:
   - date
   - status: found, fixed, partial, or needs-data
   - affected area
   - symptom
   - root cause when known
   - fix or next action
   - verification command/result when available
4. If the bug affects OCR behavior, include the image filename or pattern name when safe.
5. Keep patient-identifying text out of the log. Refer to images by filename only.

## Entry Template

```text
YYYY-MM-DD - [status] area
- Symptom:
- Cause:
- Fix/next:
- Verification:
```
