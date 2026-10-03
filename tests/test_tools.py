"""Exercise the registered FastMCP tools as a client-facing boundary."""
import asyncio
import json
import sqlite3

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from mcp_incident_server.server import Incidents, mcp


def test_tool_discovery_and_approved_note_dispatch(tmp_path, monkeypatch):
    path = tmp_path / "incidents.db"
    monkeypatch.setenv("PORTFOLIO_DB", str(path))
    repo = Incidents(str(path))
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO incidents(id,title) VALUES (7,'API latency')")
    token = repo.approve_note(7, "Rollback completed", "reviewer")

    async def exercise_tools():
        tools = {tool.name: tool for tool in await mcp.list_tools()}
        # Approval issuance must remain outside the agent's discoverable tools.
        assert set(tools) == {"list_open_incidents", "add_incident_note"}
        assert tools["list_open_incidents"].annotations.readOnlyHint is True
        assert tools["list_open_incidents"].annotations.openWorldHint is False
        note_annotations = tools["add_incident_note"].annotations
        assert note_annotations.readOnlyHint is False
        assert note_annotations.destructiveHint is False
        assert note_annotations.idempotentHint is False
        assert note_annotations.openWorldHint is False
        assert set(tools["add_incident_note"].inputSchema["required"]) == {
            "incident_id", "body", "actor", "approval_token"}
        _, listed = await mcp.call_tool("list_open_incidents", {})
        assert listed == {"result": [{"id": 7, "title": "API latency", "status": "open"}]}
        arguments = {"incident_id": 7, "body": "Rollback completed", "actor": "reviewer"}
        with pytest.raises(ToolError, match="approval_token"):
            await mcp.call_tool("add_incident_note", arguments)
        with pytest.raises(ToolError, match="mismatched approval"):
            await mcp.call_tool("add_incident_note", {**arguments, "approval_token": "invalid"})
        result = await mcp.call_tool("add_incident_note", {**arguments, "approval_token": token})
        assert json.loads(result[0].text) == {"note_id": 1}
        with pytest.raises(ToolError, match="reused"):
            await mcp.call_tool("add_incident_note", {**arguments, "approval_token": token})

    asyncio.run(exercise_tools())
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT incident_id,body,actor FROM notes").fetchall() == [
            (7, "Rollback completed", "reviewer")]
        assert db.execute("SELECT used FROM approvals").fetchall() == [(1,)]
