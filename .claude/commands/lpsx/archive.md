---
name: /lpsx:archive
description: Archive a single completed loopspec change.
---

Archive a completed loopspec change.

Run `loopspec archive <change-name> --json`. Add `--dry-run` first if you want to preview the destination before moving anything. The change must be complete, or you must pass `--exhausted`/`--include-pending-failures` for the applicable edge cases.

