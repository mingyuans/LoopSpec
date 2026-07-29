# LoopSpec manual

> Scope: index of the English manual — what each page covers and who it is for.
> Audience: humans and LLM agents; start here.
> Language: **English** · [中文](../zh/README.md)

LoopSpec is a CLI for gated artifact workflows: you declare a YAML graph of documents a change must
produce, an agent generates them one at a time, and gate nodes can send the work back with a recorded
reason.

## Pages

| Page | Covers | For |
| --- | --- | --- |
| [Overview](overview.md) | What LoopSpec is, the problem it solves, the core model (nodes, artifacts, gates, rollback, filesystem-derived state), and the glossary the rest of the manual uses. | Everyone, first read. |
| [CLI reference](cli-reference.md) | Every command and option, every `--json` response field, worked response examples, the failure contract, and all 15 error codes. | Anyone looking up a flag or a response shape. |
| [Configuration](configuration.md) | Every `config.yaml` field with type, requiredness, default and validation rules; how a schema is resolved for new versus existing changes; four worked examples. | Setting up or debugging a project. |
| [Schema reference](schema-reference.md) | Every `schema.yaml` field, the schema directory layout, `tracks` and gate semantics, all load-time checks with their error codes, and a complete minimal schema. | Writing or repairing a workflow. |
| [Agent protocol](agent-protocol.md) | The status/instructions loop, the rollback branch, which response field to read at each step, and the behaviours agents get wrong. | LLM agents, and people prompting them. |
| [secure-spec-driven](workflows/secure-spec-driven.md) | The built-in workflow: its seven nodes, what each must produce, and why each gate resets what it resets. | Working a change through the default flow. |

## Quick orientation

Getting started:

```bash
loopspec init ./loopspec
loopspec new add-payment --json
loopspec status add-payment --json
```

`status` names the single next command on every turn. Follow it, write the artifact
`loopspec instructions` describes, and come back to `status` — that is the whole loop. See
[Agent protocol](agent-protocol.md) for the details and
[CLI reference](cli-reference.md) for everything else.

Where to go for a specific question:

- *What does this flag do?* — [CLI reference](cli-reference.md)
- *What can I put in `config.yaml`?* — [Configuration](configuration.md)
- *How do I write my own workflow?* — [Schema reference](schema-reference.md)
- *What should my agent do next?* — [Agent protocol](agent-protocol.md)
- *What is this node supposed to produce?* — [secure-spec-driven](workflows/secure-spec-driven.md)
- *What does this term mean?* — [Overview glossary](overview.md#glossary)
