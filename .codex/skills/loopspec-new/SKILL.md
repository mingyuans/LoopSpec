---
name: loopspec-new
description: Create a new loopspec change and see its first step.
---

Create a new loopspec change.

1. Derive a concise kebab-case `<change-name>` from the requirement. Before creating it, inspect existing change names and reuse the canonical name when the same work item already exists (especially the same ticket key); do not add a schema or role suffix such as `-be` or `-prd`.
2. Run `loopspec new <change-name> --json` (add `--schema <name>` if the project has multiple candidate schemas and the command asks you to pick one). The command also resolves unambiguous existing names and returns the canonical name in `changeName`.
3. Run `loopspec status <changeName> --json` using the returned canonical name to see the first ready node and its `nextSteps`.
4. Continue with `/lpsx:continue` to drive the rest of the loop.
