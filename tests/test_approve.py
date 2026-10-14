import sqlite3

import pytest

from mcp_incident_server.approve import main
from mcp_incident_server.server import Incidents


@pytest.mark.parametrize("problem", ["directory", "parent_file", "invalid_database"])
def test_database_errors_are_usage_errors_without_token(tmp_path, monkeypatch, capsys, problem):
    path = tmp_path / "incidents.db"
    if problem == "directory":
        path.mkdir()
    elif problem == "parent_file":
        path.write_text("not a directory")
        path = path / "incidents.db"
    else:
        path.write_text("not a SQLite database")
    monkeypatch.setattr("sys.argv", ["approve", "--db", str(path), "--incident-id", "7",
                                    "--body", "Rollback completed", "--actor", "reviewer"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert f"cannot open database {path}" in captured.err
    assert "Traceback" not in captured.err


@pytest.mark.parametrize("body,actor", [("", "reviewer"), ("   ", "reviewer"),
                                      ("x" * 1001, "reviewer"), ("Valid note", ""),
                                      ("Valid note", " ")])
def test_invalid_approval_arguments_do_not_create_database(tmp_path, monkeypatch, capsys, body, actor):
    path = tmp_path / "incidents.db"
    monkeypatch.setattr("sys.argv", ["approve", "--db", str(path), "--incident-id", "7",
                                    "--body", body, "--actor", actor])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    assert "note length and actor are required" in capsys.readouterr().err
    assert not path.exists()


def test_valid_operator_approval_can_be_consumed(tmp_path, monkeypatch, capsys):
    path = tmp_path / "incidents.db"
    repo = Incidents(str(path))
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO incidents(id,title) VALUES (7,'API latency')")
    monkeypatch.setattr("sys.argv", ["approve", "--db", str(path), "--incident-id", "7",
                                    "--body", "Rollback completed", "--actor", "reviewer"])
    main()
    token = capsys.readouterr().out.strip()
    assert repo.add_note(7, "Rollback completed", "reviewer", token) > 0


@pytest.mark.parametrize("status", [None, "closed"])
def test_unavailable_incident_is_usage_error_without_approval(tmp_path, monkeypatch, capsys, status):
    path = tmp_path / "incidents.db"
    Incidents(str(path))
    with sqlite3.connect(path) as db:
        if status is not None:
            db.execute("INSERT INTO incidents(id,title,status) VALUES (7,'API latency',?)",
                       (status,))
    monkeypatch.setattr("sys.argv", ["approve", "--db", str(path), "--incident-id", "7",
                                    "--body", "Rollback completed", "--actor", "reviewer"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "open incident not found" in captured.err
    assert "Traceback" not in captured.err
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM approvals").fetchone()[0] == 0


@pytest.mark.parametrize("incident_id", [-(2**63) - 1, 2**63])
def test_out_of_range_id_is_usage_error_before_database_creation(
    tmp_path, monkeypatch, capsys, incident_id,
):
    path = tmp_path / "incidents.db"
    monkeypatch.setattr("sys.argv", ["approve", "--db", str(path),
                                    "--incident-id", str(incident_id),
                                    "--body", "Recovery confirmed", "--actor", "reviewer"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "signed 64-bit integer" in captured.err
    assert not path.exists()
