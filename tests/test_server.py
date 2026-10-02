import hashlib
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


def test_closed_incident_cannot_receive_approved_note(tmp_path):
    repo = Incidents(str(tmp_path / "incidents.db"))
    with sqlite3.connect(repo.path) as db:
        db.execute("INSERT INTO incidents(id,title) VALUES (7,'API latency')")
    token = repo.approve_note(7, "Rollback completed", "reviewer")
    with sqlite3.connect(repo.path) as db:
        db.execute("UPDATE incidents SET status='closed' WHERE id=7")
    with pytest.raises(ValueError, match="open incident"):
        repo.add_note(7, "Rollback completed", "reviewer", token)
    with pytest.raises(ValueError, match="open incident"):
        repo.approve_note(7, "Another note", "reviewer")
    with sqlite3.connect(repo.path) as db:
        assert db.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 0


@pytest.mark.parametrize("body", [" ", "\t\n"])
def test_blank_notes_cannot_be_approved_or_added(tmp_path, body):
    repo = Incidents(str(tmp_path / "incidents.db"))
    with sqlite3.connect(repo.path) as db:
        db.execute("INSERT INTO incidents(id,title) VALUES (7,'API latency')")
        # A preexisting approval must not bypass validation at the write boundary.
        db.execute("INSERT INTO approvals VALUES (?,?,?,?,0)", (
            hashlib.sha256(b"legacy-token").hexdigest(), 7,
            hashlib.sha256(body.encode()).hexdigest(), "reviewer"))
    with pytest.raises(ValueError, match="note length and actor"):
        repo.approve_note(7, body, "reviewer")
    with pytest.raises(ValueError, match="note length and actor"):
        repo.add_note(7, body, "reviewer", "legacy-token")
    with sqlite3.connect(repo.path) as db:
        assert db.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 0
        assert db.execute("SELECT used FROM approvals").fetchone()[0] == 0


def test_note_write_failure_does_not_consume_approval(tmp_path):
    repo = Incidents(str(tmp_path / "incidents.db"))
    with sqlite3.connect(repo.path) as db:
        db.execute("INSERT INTO incidents(id,title) VALUES (7,'API latency')")
        db.execute("CREATE TRIGGER fail_note BEFORE INSERT ON notes "
                   "BEGIN SELECT RAISE(ABORT, 'note storage unavailable'); END")
    token = repo.approve_note(7, "Rollback completed", "reviewer")
    with pytest.raises(sqlite3.IntegrityError, match="note storage unavailable"):
        repo.add_note(7, "Rollback completed", "reviewer", token)
    with sqlite3.connect(repo.path) as db:
        assert db.execute("SELECT used FROM approvals").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 0
        db.execute("DROP TRIGGER fail_note")
    assert repo.add_note(7, "Rollback completed", "reviewer", token) > 0
    with pytest.raises(ValueError, match="reused"):
        repo.add_note(7, "Rollback completed", "reviewer", token)


@pytest.mark.parametrize("incident_id,actor", [(8, "reviewer"), (7, "other-reviewer")])
def test_approval_is_bound_to_incident_and_actor(tmp_path, incident_id, actor):
    repo = Incidents(str(tmp_path / "incidents.db"))
    with sqlite3.connect(repo.path) as db:
        db.executemany("INSERT INTO incidents(id,title) VALUES (?,?)",
                       [(7, "API latency"), (8, "Database latency")])
    token = repo.approve_note(7, "Rollback completed", "reviewer")
    with pytest.raises(ValueError, match="mismatched approval"):
        repo.add_note(incident_id, "Rollback completed", actor, token)
    with sqlite3.connect(repo.path) as db:
        assert db.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 0
        assert db.execute("SELECT used FROM approvals").fetchone()[0] == 0
    repo.add_note(7, "Rollback completed", "reviewer", token)
    with sqlite3.connect(repo.path) as db:
        assert db.execute("SELECT incident_id,body,actor FROM notes").fetchall() == [
            (7, "Rollback completed", "reviewer")]


def test_list_open_is_ordered_bounded_and_read_only(tmp_path):
    repo = Incidents(str(tmp_path / "incidents.db"))
    with sqlite3.connect(repo.path) as db:
        db.executemany("INSERT INTO incidents(id,title,status) VALUES (?,?,?)", [
            (key, f"Incident {key}", "closed" if key == 1 else "open")
            for key in range(106, 0, -1)
        ])
        before = {table: db.execute(f"SELECT * FROM {table}").fetchall()
                  for table in ("incidents", "notes", "approvals")}
    assert repo.list_open() == [
        {"id": key, "title": f"Incident {key}", "status": "open"}
        for key in range(2, 102)
    ]
    with sqlite3.connect(repo.path) as db:
        for table, rows in before.items():
            assert db.execute(f"SELECT * FROM {table}").fetchall() == rows
