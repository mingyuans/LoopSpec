# Fragments, Profiles and Plans

> Scope: what Fragments, Profiles and Plans are, the problem each one solves, how they work together, and what changing each one affects.
> Audience: newcomers to LoopSpec, workflow authors and agents that plan; field details live in Workflow composition and the Plan reference.
> Language: **English** · [中文](../zh/fragment-profile-plan.md)

## In one sentence each

- **A Fragment is a part**: a reusable set of steps (nodes) with its own instructions, templates and Gate rules, such as "backend tests" or "security review".
- **A Profile is an assembly drawing**: a template that arranges Fragments into a `flow` with dependencies, such as `bugfix` or `large-feature`, to adopt or copy while planning.
- **A Plan is this job's work order**: the execution graph one Change settles on for the whole task. A human confirms it, it is frozen, and the CLI executes only that.

Fragments and Profiles belong to the project: they live in the workflow home and every Change can use them. A Plan belongs to one Change: it lives in that Change's directory and serves only that piece of work.

## Side by side

| Aspect | Fragment | Profile | Plan |
| --- | --- | --- | --- |
| Problem it solves | How one kind of work is done and accepted, written once and reused everywhere | Which Fragments a kind of task usually needs, and in what order | Which nodes this piece of work runs, in what order, and where a failure sends the work back |
| File | `fragments/<name>/fragment.yaml` plus resources in that directory | `profiles/<name>.yaml` | `changes/<change>/plans/<NNN>/plan.yaml` |
| Main content | `nodes`: artifact nodes, Gate nodes and `use` references to other Fragments | `flow`: Fragment instances with `requires` and `on_fail`, plus `guidance` for whoever plans | `meta` (status, revision, digest) and `spec` (the requested `flow` plus the compiled leaf `nodes`) |
| Written by | Workflow authors, or synced from a team repository with `registry update` | Workflow authors, or synced through the registry | The agent writes a request, `plan create` compiles it; after confirmation the CLI maintains it |
| Executed directly | No; only once instantiated into a Plan | No; it is a template to adopt, adapt or ignore | Yes; the CLI advances only the confirmed Plan's `spec.nodes` |
| Needs human confirmation | No (review it as project code) | No (review it as project code) | Yes: a draft is approved only after a human confirms it; revisions and replacements need consent too |
| Lifetime | Long-lived, evolves with the project | Long-lived, evolves with the project | draft, then approved, then archived; a Change has at most one open Plan at a time |
| Granularity | One capability (for example one test Gate) | One shape of task (for example a bug fix) | The complete graph of one concrete task |
| Commands | `fragment list / show / validate` | `profile list / show / validate / save` | `plan validate / create / show / approve / archive / rollback` |

## How they work together

```text
fragments/                 profiles/                 changes/<change>/plans/
  requirements/  -+          bugfix.yaml  -- based_on --+
  backend-code/   | use      large-feature.yaml         |
  backend-tests/  +------->   (flow templates)          v
  security-review/|                                 request.yaml (the agent's flow for the whole task)
  ...            -+                                     | plan create: compile against current Fragments
                                                        v
                                                    001/plan.yaml (draft -> human confirms -> approved)
                                                        | the CLI executes spec.nodes only
                                                        v
                                                    artifacts/, .gates/, .attempts/
```

1. **Pick a template**: the agent uses `profile list` and `profile show` to find a Profile close to the task, for example `bugfix` for a bug fix.
2. **Write the request**: under the Change's `plans/` directory the agent writes one request for the whole task. `based_on` records which Profile it started from; the `flow` can be copied as is, gain or lose instances, or change dependencies. A Profile is never merged in automatically: the `flow` in the request is the whole flow.
3. **Compile a draft**: `plan create` expands every `flow` instance into leaf nodes using the current Fragment definitions, pushes `on_fail` down into every Gate and computes the `digest`.
4. **Human confirmation**: only after a human has seen the scope, graph, rework targets and `digest` shown by `plan show` and explicitly agreed does the agent run `plan approve`. Approval recompiles the draft and refuses a digest that does not match.
5. **Execution**: from then on the CLI follows only this Plan's `spec.nodes`: it hands out node instructions, records Gate evidence, reworks through each Gate's own `on_fail`, and finally lets the assurance node check the full diff.

## Example: how bugfix becomes a Plan

The `flow` of the `bugfix` Profile has only four instances:

```yaml
flow:
- {id: requirements, use: requirements}
- {id: be, use: backend-implementation, requires: [requirements]}
- {id: qa, use: qa-testing, requires: [be], on_fail: {reset: [be], max_retries: 3}}
- {id: assurance, use: change-assurance, requires: [qa]}
```

`backend-implementation` is itself a Fragment that references other Fragments (`backend-code`, `backend-tests`, `security-review`, `backend-pr-review`). After compilation the Plan's `spec.nodes` holds seven leaf nodes, each id prefixed with its instance name:

```text
requirements/proposal -> be/code/implement -> be/tests/check -> be/security/check
  -> be/review/check -> qa/test -> assurance/check
```

The `on_fail: {reset: [be]}` on the `qa` instance becomes the rework target of the `qa/test` Gate: `be/code/implement` and the three Gates inside `be`. The `on_fail` that `backend-implementation` declares for each of its Gates is pushed down as well, so every Gate in `plan.yaml` carries its own explicit rework scope.

## What a change affects

| You change | Effect on an approved Plan | Effect on Plans created later |
| --- | --- | --- |
| A Fragment's node structure (nodes, `requires`, `gate`, `on_fail`) | The approved graph does not change. A draft is recompiled by `plan approve`, and a changed digest is refused (`plan_changed`): run `plan create` again and get a new confirmation | Compiled with the new structure |
| A Fragment's instructions or templates | Live: a node reads the current files when it runs | Same |
| Assurance rules (the rule file `config.yaml` points to) | Live: the assurance node judges by the current rules (a code Gate's `evidence.paths` are written into the Plan and do not follow) | Same |
| A Profile | None: a Plan does not reference a Profile's content; `based_on` is only a record | Only requests written from it afterwards |
| The Plan (the task's scope changed) | Small adjustments go through a revision (a request with `base_revision`, approved with `plan approve -f` after consent); if the task itself changed, archive the Plan with consent and plan again | Not applicable |

## Which one to change

- **The team changed how a kind of work is done** (for example tests need one more check, or a review template needs a new item): change the Fragment's instructions or templates.
- **The usual process for a kind of task changed** (for example bug fixes should also start with a design): change or add a Profile.
- **Only this task needs a different process**: leave the Profile alone, adjust the `flow` in this request, and have a human confirm the Plan as usual.
- **The Plan stops fitting during execution**: revise or replace the Plan; never edit `plan.yaml` by hand.

Related pages: fields and authoring rules in [Workflow composition](workflow-composition.md), `plan.yaml` field by field in the [Plan reference](plan-reference.md), terms in the [Overview](overview.md).
