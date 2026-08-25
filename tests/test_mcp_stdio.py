import sys

import pytest

from mewcode.engine.mcp import McpServerConfig, McpServerManager, StdioMcpClient
from mewcode.engine.tools import ToolContext, ToolRegistry


SERVER = (
    "import json,sys; "
    "\nfor line in sys.stdin:"
    "\n m=json.loads(line); method=m.get('method');"
    "\n if 'id' not in m: continue"
    "\n result={'tools':[{'name':'echo','description':'Echo','inputSchema':{'type':'object'}}]} if method=='tools/list' else {'protocolVersion':'2025-06-18'} if method=='initialize' else {'content':[{'type':'text','text':'ok'}]}"
    "\n print(json.dumps({'jsonrpc':'2.0','id':m['id'],'result':result}),flush=True)"
)


@pytest.mark.asyncio
async def test_stdio_client_initializes_discovers_and_calls_tool():
    client = StdioMcpClient(McpServerConfig("fake", [sys.executable, "-c", SERVER]))
    await client.start()

    assert (await client.list_tools())[0]["name"] == "echo"
    assert (await client.call_tool("echo", {"value": "hi"}))["content"][0]["text"] == "ok"

    await client.close()


@pytest.mark.asyncio
async def test_manager_registers_server_scoped_tools(tmp_path):
    registry = ToolRegistry(ToolContext.detect(tmp_path))
    manager = McpServerManager([McpServerConfig("fake", [sys.executable, "-c", SERVER])])

    assert await manager.connect_and_register("fake", registry) == 1
    assert registry.get("mcp__fake__echo") is not None
    assert manager.status["fake"] == "ready"

    await manager.close()
