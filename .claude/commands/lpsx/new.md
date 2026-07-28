---
name: /lpsx:new
description: Create a new loopspec change and see its first step.
---

Create a new loopspec change.

1. Run `loopspec new <change-name> --json` (add `--schema <name>` if the project has multiple candidate schemas and the command asks you to pick one).
2. Run `loopspec status <change-name> --json` to see the first ready node and its `nextSteps`.
3. Continue with `/lpsx:continue` to drive the rest of the loop.

