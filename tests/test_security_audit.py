import json

from mewcode.engine.security.audit import AuditLog


def test_audit_log_writes_redacted_json_line(tmp_path):
    log = AuditLog(tmp_path)
    log.append({"tool": "WriteFile", "decision": "allow", "api_key": "secret"})

    saved = json.loads(log.path.read_text(encoding="utf-8"))
    assert saved == {"tool": "WriteFile", "decision": "allow"}
