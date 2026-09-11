Implement the approved plan: turn `tasks.md` into real code changes, then record
what happened.

This is a gate: you must write to exactly one of the two output paths - the
implementation report (pass) or the blocked report (fail). Do not write both.

## The loop

1. **Read every file in `contextFiles`** - proposal, specs, design, tasks, the
   security verdict, the approval verdict. Do not work from filenames or from
   memory; the design is what constrains the implementation.
2. **Find the pending work** in `taskProgress`: every entry with `done: false`,
   in the order the task list declares them (the order encodes dependencies).
3. **Implement one task at a time.** Keep each change minimal and scoped to that
   task - do not opportunistically refactor neighbouring code.
4. **Tick the checkbox immediately** after finishing a task: change `- [ ]` to
   `- [x]` in `tasks.md` before starting the next one. Do not batch this up at
   the end; the checkbox state is how this node's progress survives an
   interrupted session.
5. **Run the project's tests and checks** (this project: `make test`, `make
   lint`) and record what they actually printed - including failures. Never
   report a test run you did not perform.
6. **Write the report** once every checkbox is ticked, using the pass template.

This node is only `done` when every checkbox in `tasks.md` is ticked. Writing the
report while tasks are still pending leaves the node `ready`, keeps
`isComplete` false, and blocks `loopspec archive` - so finish the work rather
than declaring it finished.

## When to stop instead

Write the fail output, not the report, if:

- a task is ambiguous enough that implementing it would be guessing
- the design has a hard flaw that surfaced only once you started building
- a task's premise does not hold, or two requirements contradict each other

A FAIL rolls the change back and redoes `design` and `tasks`, with your blocking
issues handed to them as `priorAttempts`. Two rounds of this and the gate
escalates to a human, because reworking an implementation is expensive.

**Record the code changes you already made** in the fail output. Rollback only
archives artifact files inside the change directory - it does not revert a single
line of code. Without that record, the next round plans against a working tree
whose actual state nobody has written down.

## Report honestly

The report is the only account of what this change did to the codebase. List the
files you touched, the real test output, and any place you deviated from the
design along with why. A report that overstates what was built is worse than a
fail verdict, because it ends the loop.
