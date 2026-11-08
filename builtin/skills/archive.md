---
name: loopspec-archive
description: Archive one completed LoopSpec change after rechecking its state and evidence.
---

Before archiving, check that the change-level `state.md` records the background and the important decisions; if they are missing, add them with `loopspec state add --section background` or `--section decision` (with `--actor` and `--by` naming who actually decided) from the conversation and the Plan artifacts first. For an open question that is still listed, add a new record saying whether it was resolved, handed over, or deliberately left open, and never claim it resolved without a basis. If a command fails with `state_section_missing` or `state_section_ambiguous`, show the actual path and error, check whether the file still uses an old template or was edited by hand, and ask the human to tidy it; do not retry blindly, append to the end of the file, map headings yourself, or rewrite history.

When the user requests archiving, preview with `loopspec change archive <change-name> --dry-run`, then run `loopspec change archive <change-name>`.

Archiving rechecks code Gate evidence and full-diff assurance first. A stale PASS is not completion: go back to `/lpsx:continue` or the `loopspec-continue` skill and redo the necessary checks.

An unplanned Change or a draft Plan is not complete and cannot be archived as complete. Do not approve a draft or confirm a revision merely to make the change eligible; obtain a genuine human decision through the planning lifecycle first.

Use `--force` only when the user explicitly asks to abandon this change; say plainly that it is archived unfinished, never that it is completed. Archiving moves the change directory with all of its Plans, artifacts, and rework records, not business code.
