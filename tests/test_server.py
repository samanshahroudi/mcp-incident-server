import sqlite3

import pytest

from mcp_incident_server.server import Incidents


def test_approval_bound_and_single_use(tmp_path):
    repo = Incidents(str(tmp_path / "incidents.db"))
    with sqlite3.connect(repo.path) as db:
        db.execute("INSERT INTO incidents(id,title) VALUES (7,'API latency')")
    token = repo.approve_note(7, "Rollback completed", "reviewer")
    with pytest.raises(ValueError):
        repo.add_note(7, "Different note", "reviewer", token)
    assert repo.add_note(7, "Rollback completed", "reviewer", token) > 0
    with pytest.raises(ValueError):
        repo.add_note(7, "Rollback completed", "reviewer", token)
    with pytest.raises(ValueError):
        repo.add_note(99, "A valid note", "reviewer", "invalid")
