# LoopSpec manual

> Scope: index of the English manual - what each page covers and who it is for.
> Audience: humans and LLM agents; start here.
> Language: **English** · [中文](../zh/README.md)

LoopSpec is a CLI for plan-driven, gated delivery with LLM agents. For each Change, an agent drafts one Plan for the whole task from reusable Fragments and Profiles; a human confirms it; the agent then executes the confirmed graph node by node, with code Gates bound to review evidence and a final assurance check over the full Git diff.

## Pages

| Page | Covers | For |
| --- | --- | --- |
| [Overview](overview.md) | The two hierarchies (Change, Plan, Revision; Node, Fragment, Profile, Plan), the derived statuses, the disk layout and the glossary. | Everyone, first read. |
| [Workflow composition](workflow-composition.md) | Writing Fragments, Profiles and Plan requests; `on_fail` and how it is pushed down into Gates; code evidence and assurance. | Authors of workflows and agents that plan. |
| [Plan reference](plan-reference.md) | `plan.yaml`, `.workflow.yaml` and rework records field by field, with a complete example; revision and replanning rules. | Anyone reading or reviewing a Plan. |
| [Configuration](configuration.md) | `config.yaml` and assurance rule files, field by field; what is checked live. | Setting up a project. |
| [CLI reference](cli-reference.md) | Every command and option, JSON output, and every error code. | Looking up a command. |
| [Agent protocol](agent-protocol.md) | The loop an agent runs: planning, confirmation, execution, rework, revision, replanning and what an interruption leaves behind. | LLM agents and the people prompting them. |
| [Release notes](release-notes.md) | What changed in 2.0.0 and how to upgrade from 1.x. | Upgrading users. |

## Quick orientation

```bash
loopspec init ./loopspec --tools claude
loopspec change new AFD1111
loopspec profile show bugfix
# write changes/AFD1111/plans/request.yaml for the whole task, then:
loopspec plan validate -c AFD1111 -f changes/AFD1111/plans/request.yaml
loopspec plan create -c AFD1111 -f changes/AFD1111/plans/request.yaml
loopspec plan show -c AFD1111 -p 001
# show it to a human and wait for explicit confirmation, then:
loopspec plan approve -c AFD1111 -p 001 --digest "<shown digest>"
loopspec change status AFD1111
```

Where to go for a specific question:

- *What does this command do?* - [CLI reference](cli-reference.md)
- *How do I write a Fragment or a Plan request?* - [Workflow composition](workflow-composition.md)
- *What is in `plan.yaml`?* - [Plan reference](plan-reference.md)
- *What can I put in `config.yaml`?* - [Configuration](configuration.md)
- *What should my agent do next?* - [Agent protocol](agent-protocol.md)
- *What does this term mean?* - [Overview glossary](overview.md#glossary)
