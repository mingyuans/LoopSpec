---
name: /lpsx:bulk-archive
description: Archive every completed LoopSpec change in bulk without bypassing stale evidence or unfinished work.
---

When the user requests bulk archiving, archive in two steps. Run `loopspec change archive --all`, inspect `changes` and `skipped`; it archives nothing and returns one `archiveId` with the `memoryReview` instructions and each change's `inputs`. Review memory across all listed changes with the memory maintenance procedure of the `loopspec-archive` skill, reading the inputs before they are deleted, then run `loopspec change archive --confirm <archiveId> --memory updated|none --note "<what changed in memory, or why nothing was reusable>"` and verify `archived`. Choose `updated` only if you changed memory topics; the CLI checks this and records the outcome in every change's `state.md`. If confirming stops part way, rerun the same `--confirm` command: finished changes are skipped. On `archive_ticket_stale`, start again from the first step.

Use `--older-than <days>` to restrict by age. Every candidate is checked like a single archive: unplanned changes, draft Plans, unfinished changes, and stale evidence are skipped. Never approve drafts, confirm revisions, or use `--force` to make changes eligible. Archiving does not commit business code or modify unrelated tool configuration.

