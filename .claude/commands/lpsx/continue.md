---
name: /lpsx:continue
description: Advance a loopspec change by reading status.nextSteps and acting on it.
---

Advance a loopspec change by one step.

1. Run `loopspec status <change-name> --json`.
2. Read `nextSteps` -- it names exactly one `loopspec` command to run next (usually `loopspec instructions <node> --change <change-name> --json`, sometimes `loopspec rollback <change-name> --json`).
3. Run that command. If it's `instructions`, do what the returned `instruction` says -- that is not always "write a file". Depending on the node it may ask you to write an artifact to `resolvedOutputPath` (or `resolvedOutputPath.pass`/`.fail` for a gate), to ask a human for a decision with your tool's interactive question facility and record their verdict, or to change code in the repository and tick off entries in a tracked task list (`taskProgress` shows what's left). Then update `state.md` per the instructions.
4. Re-run `loopspec status <change-name> --json` and repeat from step 2 until `isComplete` is `true` or a gate is `exhausted`.

If a gate is `failed`, `nextSteps` will point you at `loopspec rollback <change-name> --json` first -- run it, then continue via `/lpsx:continue`; `loopspec instructions` for the reset nodes will include `priorAttempts` explaining what failed last time.

