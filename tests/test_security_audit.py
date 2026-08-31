from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json

import pytest

from mewcode.engine.security.audit import AuditLog, REDACTED, redact_sensitive


def test_audit_log_writes_structured_timestamped_json_line(tmp_path):
    log = AuditLog(tmp_path)
    original = {
        "event_type": "executed",
        "tool_name": "WriteFile",
        "decision": "allow",
        "input": {"content": "private"},
        "config": {"api_key": "secret", "nested": {"TOKEN": "nested-secret"}},
        "items": [{"password": "list-secret"}],
    }

    saved = log.append(original)
    persisted = json.loads(log.path.read_text(encoding="utf-8"))

    assert saved == persisted
    assert saved["tool_name"] == "WriteFile"
    assert saved["tool"] == "WriteFile"  # backwards-compatible alias
    assert saved["event_type"] == "executed"
    datetime.fromisoformat(saved["timestamp"].replace("Z", "+00:00"))
    assert "input" not in saved
    assert "config" not in saved
    assert original["config"]["api_key"] == "secret"


def test_recursive_redaction_handles_nested_dicts_and_lists_without_mutation():
    original = {
        "Config": {
            "API_KEY": "abc",
            "nested": {"token": "xyz", "safe": "kept"},
        },
        "items": [{"Authorization": "Bearer value"}, {"safe": 1}],
        "normal": "unchanged",
    }

    redacted = redact_sensitive(original)

    assert redacted["Config"]["API_KEY"] == REDACTED
    assert redacted["Config"]["nested"]["token"] == REDACTED
    assert redacted["items"][0]["Authorization"] == REDACTED
    assert redacted["items"][1]["safe"] == 1
    assert redacted["normal"] == "unchanged"
    assert original["Config"]["API_KEY"] == "abc"
    assert original["Config"]["nested"]["token"] == "xyz"


def test_audit_log_rotates_when_size_limit_is_reached(tmp_path):
    log = AuditLog(tmp_path, max_file_bytes=180)
    for index in range(3):
        log.append({"event_type": "executed", "tool_name": "ReadFile", "request_id": str(index)})

    rotated = log.path.with_name("audit.jsonl.1")
    assert rotated.exists()
    assert log.path.exists()
    for path in (rotated, log.path):
        for line in path.read_text(encoding="utf-8").splitlines():
            json.loads(line)


def test_audit_log_concurrent_appends_are_valid_jsonl(tmp_path):
    log = AuditLog(tmp_path, max_file_bytes=None)

    def append(index: int) -> None:
        log.append({"event_type": "executed", "tool_name": "ReadFile", "request_id": str(index)})

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(append, range(100)))

    lines = log.path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 100
    assert len({json.loads(line)["request_id"] for line in lines}) == 100


def test_audit_log_rejects_invalid_rotation_size(tmp_path):
    with pytest.raises(ValueError):
        AuditLog(tmp_path, max_file_bytes=0)
