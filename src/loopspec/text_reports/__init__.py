"""Hand-written text reports for every workflow command (the default output).

Each command has its own renderer; `--json` prints the same payload as JSON
instead. See `loopspec.text_format` for the text contract they all follow.
"""

from __future__ import annotations

from . import catalog, change, gate, memory, node, plan, registry
from .common import Report

RENDERERS: dict[str, Report] = {
    "memory list": memory.LIST,
    "memory show": memory.SHOW,
    "change new": change.NEW,
    "change next": change.NEXT,
    "change history": change.HISTORY,
    "change artifacts": change.ARTIFACTS,
    "change archive": change.ARCHIVE,
    "plan validate": plan.VALIDATE,
    "plan create": plan.CREATE,
    "plan show": plan.SHOW,
    "plan list": plan.LIST,
    "plan approve": plan.APPROVE,
    "plan archive": plan.ARCHIVE,
    "plan rollback": plan.ROLLBACK,
    "node instructions": node.INSTRUCTIONS,
    "state add": gate.STATE_ADD,
    "gate begin": gate.BEGIN,
    "gate record": gate.RECORD,
    "fragment list": catalog.FRAGMENT_LIST,
    "fragment show": catalog.FRAGMENT_SHOW,
    "fragment validate": catalog.FRAGMENT_VALIDATE,
    "profile list": catalog.PROFILE_LIST,
    "profile show": catalog.PROFILE_SHOW,
    "profile validate": catalog.PROFILE_VALIDATE,
    "profile save": catalog.PROFILE_SAVE,
    "registry update": registry.UPDATE,
    "registry apply": registry.APPLY,
}

__all__ = ["RENDERERS", "Report"]
