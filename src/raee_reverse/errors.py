"""Structured errors. An error is never a successful verification."""

from __future__ import annotations


class RrlError(Exception):
    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "details": self.details}


class DeterministicTaskError(RrlError):
    def __init__(self, message: str, **details: object) -> None:
        super().__init__("E_DETERMINISTIC", message, **details)


class InfraTaskError(RrlError):
    def __init__(self, message: str, **details: object) -> None:
        super().__init__("E_INFRA", message, **details)


class CancelledTask(RrlError):
    def __init__(self, message: str = "cancelled", **details: object) -> None:
        super().__init__("E_CANCELLED", message, **details)
