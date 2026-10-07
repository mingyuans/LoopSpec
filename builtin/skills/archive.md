---
name: loopspec-archive
description: Archive one completed LoopSpec change after rechecking its state and evidence.
---

When the user requests archiving, preview with `loopspec change archive <change-name> --dry-run`, then run `loopspec change archive <change-name>`.

Archiving rechecks code Gate evidence and full-diff assurance first. A stale PASS is not completion: go back to `/lpsx:continue` or the `loopspec-continue` skill and redo the necessary checks.

An unplanned Change or a draft Plan is not complete and cannot be archived as complete. Do not approve a draft or confirm a revision merely to make the change eligible; obtain a genuine human decision through the planning lifecycle first.

Use `--force` only when the user explicitly asks to abandon this change; say plainly that it is archived unfinished, never that it is completed. Archiving moves the change directory with all of its Plans, artifacts, and rework records, not business code.
