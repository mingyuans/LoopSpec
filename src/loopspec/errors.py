"""Exception types and error codes.

Every user-facing error carries a machine-readable `code`, a human-readable
`message`, and an actionable `fix` suggestion, matching the CLI's unified
`{error, message, fix}` JSON contract.
"""

from __future__ import annotations


class LoopspecError(Exception):
    """Base class for all errors that map to the CLI's unified error contract."""

    code: str = "error"

    def __init__(self, message: str, fix: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.fix = fix or ""

    def to_dict(self) -> dict[str, str]:
        return {"error": self.code, "message": self.message, "fix": self.fix}


class SchemaNotFoundError(LoopspecError):
    code = "schema_not_found"


class SchemaSelectionRequiredError(LoopspecError):
    code = "schema_selection_required"


class SchemaValidationError(LoopspecError):
    code = "schema_invalid"


class ConfigValidationError(LoopspecError):
    code = "config_invalid"


class TemplateLoadError(LoopspecError):
    code = "template_not_found"


class InstructionLoadError(LoopspecError):
    code = "instruction_not_found"


class ChangeNotFoundError(LoopspecError):
    code = "change_not_found"


class ChangeExistsError(LoopspecError):
    code = "change_exists"


class InvalidChangeNameError(LoopspecError):
    code = "invalid_change_name"


class NodeNotFoundError(LoopspecError):
    code = "node_not_found"


class GateOutputConflictError(LoopspecError):
    code = "gate_output_conflict"


class NoFailedGateError(LoopspecError):
    code = "no_failed_gate"


class RetriesExhaustedError(LoopspecError):
    code = "retries_exhausted"


class ArchiveConflictError(LoopspecError):
    code = "archive_conflict"


class ArchiveUnsafeError(LoopspecError):
    code = "archive_unsafe"
