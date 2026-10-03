import sqlite3

import pytest

from mcp_incident_server.approve import main
from mcp_incident_server.server import Incidents


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
