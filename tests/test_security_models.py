from mewcode.engine.security import (
    ExecutionRequest,
    OperationKind,
    PermissionDecision,
    RiskLevel,
)
from mewcode.engine.tools import (
    BashTool,
    EditFileTool,
    GlobTool,
    GrepTool,
    ReadFileTool,
    WriteFileTool,
)


def test_execution_request_has_safe_defaults():
    request = ExecutionRequest(tool_name="ReadFile", input={"path": "README.md"})

    assert request.source == "agent"
    assert request.operation is OperationKind.READ
    assert request.risk is RiskLevel.LOW
    assert PermissionDecision.REQUIRE_APPROVAL.value == "require_approval"


def test_builtin_tools_declare_operation_and_risk_metadata():
    assert (ReadFileTool.operation_kind, ReadFileTool.risk_level) == (
        OperationKind.READ,
        RiskLevel.LOW,
    )
    assert (GlobTool.operation_kind, GlobTool.risk_level) == (OperationKind.READ, RiskLevel.LOW)
    assert (GrepTool.operation_kind, GrepTool.risk_level) == (OperationKind.READ, RiskLevel.LOW)
    assert (WriteFileTool.operation_kind, WriteFileTool.risk_level) == (
        OperationKind.WRITE,
        RiskLevel.MODERATE,
    )
    assert (EditFileTool.operation_kind, EditFileTool.risk_level) == (
        OperationKind.WRITE,
        RiskLevel.MODERATE,
    )
    assert (BashTool.operation_kind, BashTool.risk_level) == (
        OperationKind.COMMAND,
        RiskLevel.HIGH,
    )
