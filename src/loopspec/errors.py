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


class ConfigValidationError(LoopspecError):
    code = "config_invalid"


class BuiltinSkillError(LoopspecError):
    """A bundled `builtin/skills/*.md` file is missing or unreadable.

    Not a user authoring error like the ones around it: it means the resources
    that shipped with this install are broken, so the fix points at the install
    rather than at the project.
    """

    code = "builtin_skill_invalid"


class WorkflowError(LoopspecError):
    """新工作流的结构化错误；消息不包含原始配置或代码内容。"""

    def __init__(self, code: str, message: str, fix: str = "检查配置并重新校验计划。") -> None:
        super().__init__(message, fix)
        self.code = code


class UpdateInvalidVersionError(LoopspecError):
    """A version from `--version` or from a release's checksums.txt is malformed."""

    code = "update_invalid_version"

    def __init__(self, message: str, fix: str | None = None) -> None:
        super().__init__(message, fix or "Pass a release version such as 2.1.0.")


class UpdateFetchFailedError(LoopspecError):
    code = "update_fetch_failed"

    def __init__(self, message: str, fix: str | None = None) -> None:
        super().__init__(
            message,
            fix
            or "Check the network and that the release exists, or re-run install.sh: "
            "curl -fsSL https://raw.githubusercontent.com/mingyuans/LoopSpec/main/install.sh | sh",
        )


class UpdateVerifyFailedError(LoopspecError):
    """The downloaded wheel does not match its release's checksums.txt."""

    code = "update_verify_failed"

    def __init__(self, message: str, fix: str | None = None) -> None:
        super().__init__(
            message, fix or "Nothing was installed. Retry later, or report it if it persists."
        )


class UpdateInstallerMissingError(LoopspecError):
    code = "update_installer_missing"

    def __init__(self, message: str, fix: str | None = None) -> None:
        super().__init__(
            message, fix or "Install uv (https://docs.astral.sh/uv/) or pipx, then re-run."
        )


class UpdateInstallFailedError(LoopspecError):
    code = "update_install_failed"

    def __init__(self, message: str, fix: str | None = None) -> None:
        super().__init__(message, fix or "Read the installer output above and re-run.")
