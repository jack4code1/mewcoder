"""Structured, redacted audit storage for controlled operations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
from typing import Any


REDACTED = "[REDACTED]"
DEFAULT_MAX_FILE_BYTES = 5 * 1024 * 1024

# COSEC: Keep raw tool arguments and credential-like fields out of local audit records.
# ``input`` is included for backwards compatibility with the old top-level
# filter. Audit records should contain summaries rather than raw tool input.
_SENSITIVE_FIELDS = {
    "input",
    "password",
    "passwd",
    "secret",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "token",
    "authorization",
    "cookie",
}


def utc_timestamp() -> str:
    """Return a stable UTC ISO-8601 timestamp for one audit event."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def redact_sensitive(value: Any, *, _field_name: str | None = None) -> Any:
    """Return a recursively redacted copy without mutating the input."""
    # COSEC: Recursively redact a copy so tool execution receives the original input unchanged.
    if _field_name is not None and _field_name.lower() in _SENSITIVE_FIELDS:
        return REDACTED
    if isinstance(value, Mapping):
        return {
            key: redact_sensitive(item, _field_name=str(key))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return [redact_sensitive(item) for item in value]
    return value


def _event_type(entry: Mapping[str, Any]) -> str:
    explicit = entry.get("event_type")
    if isinstance(explicit, str) and explicit:
        return explicit
    decision = str(entry.get("decision", ""))
    reason = str(entry.get("reason", ""))
    if decision == "require_approval":
        return "approval_required"
    if decision == "approved":
        return "approved"
    if decision == "allow" and entry.get("status") == "executed":
        return "executed"
    if decision == "deny":
        return {
            "approval_denied": "rejected",
            "approval_cancelled": "cancelled",
            "approval_timed_out": "timeout",
        }.get(reason, "rejected")
    return "permission_decision"


@dataclass(frozen=True)
class AuditEvent:
    """Canonical event shape used by both in-memory and JSONL audit records."""

    event_type: str
    timestamp: str
    tool_name: str | None = None
    source: str | None = None
    operation: str | None = None
    risk: str | None = None
    agent: str | None = None
    caller: str | None = None
    request_id: str | None = None
    approval_request_id: str | None = None
    task_id: str | None = None
    session_id: str | None = None
    permission: str | None = None
    decision: str | None = None
    authorization_scope: str | None = None
    resource_summary: str | None = None
    status: str | None = None
    is_error: bool | None = None
    error_reason: str | None = None
    reason: str | None = None

    @classmethod
    def from_entry(cls, entry: Mapping[str, Any]) -> "AuditEvent":
        request_id = entry.get("request_id")
        approval_request_id = entry.get("approval_request_id")
        tool_name = entry.get("tool_name") or entry.get("tool")
        scope = entry.get("authorization_scope") or entry.get("scope")
        return cls(
            event_type=_event_type(entry),
            timestamp=str(entry.get("timestamp") or utc_timestamp()),
            tool_name=tool_name if isinstance(tool_name, str) else None,
            source=entry.get("source") if isinstance(entry.get("source"), str) else None,
            operation=entry.get("operation") if isinstance(entry.get("operation"), str) else None,
            risk=entry.get("risk") if isinstance(entry.get("risk"), str) else None,
            agent=entry.get("agent") if isinstance(entry.get("agent"), str) else None,
            caller=entry.get("caller") if isinstance(entry.get("caller"), str) else None,
            request_id=request_id if isinstance(request_id, str) else None,
            approval_request_id=(
                approval_request_id if isinstance(approval_request_id, str) else None
            ),
            task_id=entry.get("task_id") if isinstance(entry.get("task_id"), str) else None,
            session_id=entry.get("session_id") if isinstance(entry.get("session_id"), str) else None,
            permission=entry.get("permission") if isinstance(entry.get("permission"), str) else None,
            decision=entry.get("decision") if isinstance(entry.get("decision"), str) else None,
            authorization_scope=scope if isinstance(scope, str) else None,
            resource_summary=(
                entry.get("resource_summary")
                if isinstance(entry.get("resource_summary"), str)
                else None
            ),
            status=entry.get("status") if isinstance(entry.get("status"), str) else None,
            is_error=entry.get("is_error") if isinstance(entry.get("is_error"), bool) else None,
            error_reason=entry.get("error_reason") if isinstance(entry.get("error_reason"), str) else None,
            reason=entry.get("reason") if isinstance(entry.get("reason"), str) else None,
        )

    def to_dict(self) -> dict[str, Any]:
        values = {
            "event_type": self.event_type,
            "timestamp": self.timestamp,
        }
        optional = {
            "tool_name": self.tool_name,
            "source": self.source,
            "operation": self.operation,
            "risk": self.risk,
            "agent": self.agent,
            "caller": self.caller,
            "request_id": self.request_id,
            "approval_request_id": self.approval_request_id,
            "task_id": self.task_id,
            "session_id": self.session_id,
            "permission": self.permission,
            "decision": self.decision,
            "authorization_scope": self.authorization_scope,
            "resource_summary": self.resource_summary,
            "status": self.status,
            "is_error": self.is_error,
            "error_reason": self.error_reason,
            "reason": self.reason,
        }
        values.update({key: value for key, value in optional.items() if value is not None})
        # Preserve the old dictionary key for callers that still read it.
        if self.tool_name is not None:
            values["tool"] = self.tool_name
        if self.authorization_scope is not None:
            values["scope"] = self.authorization_scope
        return values


def prepare_audit_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize, timestamp, and redact one event for all audit consumers."""
    return redact_sensitive(AuditEvent.from_entry(entry).to_dict())


class AuditLog:
    """Append-only local JSONL audit log with bounded size and thread safety."""

    def __init__(self, workspace: Path, max_file_bytes: int | None = DEFAULT_MAX_FILE_BYTES) -> None:
        if max_file_bytes is not None and (
            isinstance(max_file_bytes, bool)
            or not isinstance(max_file_bytes, int)
            or max_file_bytes <= 0
        ):
            raise ValueError("max_file_bytes must be a positive integer or None")
        self.path = workspace / ".mewcode" / "audit.jsonl"
        self.max_file_bytes = max_file_bytes
        self._lock = threading.RLock()

    @staticmethod
    def prepare(entry: Mapping[str, Any]) -> dict[str, Any]:
        return prepare_audit_entry(entry)

    def append(self, entry: Mapping[str, Any]) -> dict[str, Any]:
        safe = self.prepare(entry)
        line = json.dumps(safe, ensure_ascii=False, default=str) + "\n"
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._rotate_if_needed()
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line)
                handle.flush()
        return safe

    def _rotate_if_needed(self) -> None:
        if self.max_file_bytes is None or not self.path.exists():
            return
        if self.path.stat().st_size < self.max_file_bytes:
            return
        rotated = self.path.with_name(f"{self.path.name}.1")
        self.path.replace(rotated)
