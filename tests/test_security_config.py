import pytest

from mewcode.config import get_security_config
from mewcode.tui.app import MewCodeApp


def test_security_config_has_safe_defaults_without_mutating_input():
    config = {"security": {"enabled": True}}

    resolved = get_security_config(config)

    assert resolved == {"enabled": True, "approval_timeout_seconds": 300}
    assert config == {"security": {"enabled": True}}


def test_security_config_rejects_non_positive_approval_timeout():
    with pytest.raises(ValueError, match="approval_timeout_seconds"):
        get_security_config({"security": {"approval_timeout_seconds": 0}})


def test_default_application_configuration_creates_execution_gateway():
    app = MewCodeApp()

    assert app.execution_gateway is not None
