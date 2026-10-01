"""MCP façade over a constrained incident repository. Run over stdio."""
from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("incident-ops")


class Incidents:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS incidents (id INTEGER PRIMARY KEY, title TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open')")
            db.execute("CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, incident_id INTEGER NOT NULL, body TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            db.execute("CREATE TABLE IF NOT EXISTS approvals (token_hash TEXT PRIMARY KEY, incident_id INTEGER, body_hash TEXT, actor TEXT, used INTEGER NOT NULL DEFAULT 0)")

    def list_open(self) -> list[dict]:
        with sqlite3.connect(self.path) as db:
            rows = db.execute("SELECT id,title,status FROM incidents WHERE status='open' ORDER BY id LIMIT 100").fetchall()
        return [dict(zip(("id", "title", "status"), row)) for row in rows]

    def approve_note(self, incident_id: int, body: str, actor: str) -> str:
        """Called by the operator CLI, never exposed as an MCP tool."""
        if not (1 <= len(body) <= 1000) or not body.strip() or not actor.strip():
            raise ValueError("note length and actor are required")
        token = secrets.token_urlsafe(32)
        with sqlite3.connect(self.path) as db:
            if not db.execute("SELECT 1 FROM incidents WHERE id=? AND status='open'", (incident_id,)).fetchone():
                raise ValueError("open incident not found")
            db.execute("INSERT INTO approvals VALUES (?,?,?,?,0)", (
                hashlib.sha256(token.encode()).hexdigest(), incident_id,
                hashlib.sha256(body.encode()).hexdigest(), actor))
        return token

    def add_note(self, incident_id: int, body: str, actor: str, approval_token: str) -> int:
        if not (1 <= len(body) <= 1000) or not body.strip() or not actor.strip():
            raise ValueError("note length and actor are required")
        with sqlite3.connect(self.path, timeout=10) as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM incidents WHERE id=? AND status='open'", (incident_id,)).fetchone():
                raise ValueError("open incident not found")
            changed = db.execute("UPDATE approvals SET used=1 WHERE token_hash=? AND incident_id=? AND body_hash=? AND actor=? AND used=0", (
                hashlib.sha256(approval_token.encode()).hexdigest(), incident_id,
                hashlib.sha256(body.encode()).hexdigest(), actor)).rowcount
            if changed != 1:
                raise ValueError("missing, reused, or mismatched approval")
            cursor = db.execute("INSERT INTO notes(incident_id,body,actor) VALUES (?,?,?)", (incident_id, body, actor))
            return int(cursor.lastrowid)


def repo() -> Incidents:
    return Incidents(os.getenv("PORTFOLIO_DB", "incidents.db"))


@mcp.tool()
def list_open_incidents() -> list[dict]:
    """List at most 100 open incidents. Read-only."""
    return repo().list_open()


@mcp.tool()
def add_incident_note(incident_id: int, body: str, actor: str, approval_token: str) -> dict:
    """Add an audit-attributed note with a single-use approval token."""
    return {"note_id": repo().add_note(incident_id, body, actor, approval_token)}


if __name__ == "__main__":
    mcp.run(transport="stdio")
