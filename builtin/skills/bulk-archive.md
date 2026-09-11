---
name: loopspec-bulk-archive
description: Archive all eligible loopspec changes at once.
---

Archive every eligible loopspec change in one pass.

Run `loopspec bulk-archive --json` (add `--dry-run` to preview candidates first, `--older-than <days>` to restrict by age, `--exhausted` to include retry-exhausted changes). Review the `candidates`/`moved` list in the response before trusting it ran.
