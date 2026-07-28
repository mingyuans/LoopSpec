Create the task list that breaks down the implementation work.

**IMPORTANT: Follow the template below exactly.** Progress tracking parses
checkbox format. Tasks not using `- [ ]` won't be tracked.

Guidelines:
- Group related tasks under ## numbered headings
- Each task MUST be a checkbox: `- [ ] X.Y Task description`
- Tasks should be small enough to complete in one session
- Order tasks by dependency (what must be done first?)

Example:
```
## 1. Setup

- [ ] 1.1 Create new module structure
- [ ] 1.2 Add dependencies to package.json

## 2. Core Implementation

- [ ] 2.1 Implement data export function
- [ ] 2.2 Add CSV formatting utilities
```

Reference specs for what needs to be built, design for how to build it.
Each task should be verifiable - you know when it's done.

This tasks.md is itself read by the `security` gate that follows: make sure
any task touching authentication, authorization, external input, secrets, or
third-party dependencies is easy for a reviewer to spot.
