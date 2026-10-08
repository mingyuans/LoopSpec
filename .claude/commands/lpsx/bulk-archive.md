---
name: /lpsx:bulk-archive
description: Archive every completed LoopSpec change in bulk without bypassing stale evidence or unfinished work.
---

When the user requests bulk archiving, run `loopspec change archive --all --dry-run`, inspect `archived` and `skipped`, then run `loopspec change archive --all` and verify the result.

Use `--older-than <days>` to restrict by age. Every candidate is checked like a single archive: unplanned changes, draft Plans, unfinished changes, and stale evidence are skipped. Never approve drafts, confirm revisions, or use `--force` to make changes eligible. Archiving does not commit business code or modify unrelated tool configuration.

