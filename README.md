# MCP incident operations server

## The problem

An MCP server can expose backend capabilities to many agent clients. That makes the tool contract and its security boundary more important than the framework used by the client. This stdio server exposes one bounded read tool and one validated write tool over a local incident database.

## Architecture and how it works

`MCP client → FastMCP tool schema → repository validation → SQLite`

`list_open_incidents` returns at most 100 records. `add_incident_note` checks note length, actor, incident existence, and a single-use approval token bound to the exact note. A local operator issues that token through `approve.py`; the approval method is not an MCP tool. SQL parameters prevent injection. The server never takes an arbitrary SQL query or file path from the model. `server.py` contains both the MCP façade and an independently testable repository class.

## Run and example

From `portfolio`, seed a local incident:

```bash
python -c "import sqlite3; db=sqlite3.connect('incidents.db'); db.execute('insert into incidents(id,title) values (?,?)',(7,'API latency')); db.commit()"
python -m 04_mcp_incident_server.approve --db incidents.db --incident-id 7 --body 'Rollback completed' --actor reviewer
PORTFOLIO_DB=incidents.db python -m 04_mcp_incident_server.server
```

The last command speaks MCP over stdio, so it waits for an MCP client and does not show a text menu. Configure an MCP client to launch `python -m 04_mcp_incident_server.server` with `PORTFOLIO_DB` set. Call `list_open_incidents`, then `add_incident_note` with `incident_id=7`, `body='Rollback completed'`, `actor='reviewer'`, and the approval token printed by the operator command. The token is consumed once.

## Concepts and choices

MCP is the interoperability layer; validation and authorization remain application responsibilities. Stdio avoids exposing an unauthenticated network service in this demo. The repository is tested without an MCP client, while the decorator creates discoverable typed tools.

## Trade-offs, limitations, and next production steps

The approval token is bound to the proposed note but is still a bearer secret. Anyone with local shell access can run the operator command, so this is a demonstration of the control flow rather than production authentication. A real service needs authenticated approvers, roles, expiry, token delivery outside model context, per-tool scopes, audit event IDs, rate limits, and MCP protocol integration tests. Keep secrets out of tool responses and traces. A remote MCP transport would also need TLS and authentication.

## Interview preparation

Explain tool discovery, why MCP does not grant trust, the difference between read and write permissions, why arbitrary filesystem/SQL tools are dangerous, and where approval must be enforced for a production tool server.
