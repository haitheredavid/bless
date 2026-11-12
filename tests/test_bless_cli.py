import json
from pathlib import Path

from typer.testing import CliRunner

from blend.bless_cli import app


def test_session_cli_lifecycle(tmp_path: Path, monkeypatch) -> None:
    model = tmp_path / "models" / "chair"
    model.mkdir(parents=True)
    (model / "model.blend").touch()
    (model / "model.toml").write_text('name = "chair"\n')
    monkeypatch.setenv("BLESS_ROOT", str(tmp_path))
    runner = CliRunner()

    started = runner.invoke(app, ["session", "start", "chair", "2026-11-11-design"])
    assert started.exit_code == 0

    status = runner.invoke(app, ["status", "--json"])
    assert status.exit_code == 0
    rows = json.loads(status.stdout)
    assert rows == [
        {
            "model": "chair",
            "session": "2026-11-11-design",
            "status": "starting",
            "port": None,
            "pid": None,
            "last_ping_at": None,
            "last_snapshot": None,
        }
    ]

    config = runner.invoke(app, ["mcp-config", "chair", "2026-11-11-design"])
    assert config.exit_code == 0
    assert config.stdout.strip() == str(
        tmp_path / ".bless" / "sessions" / "chair" / "2026-11-11-design.mcp.json"
    )

    state = runner.invoke(app, ["state", "chair", "--json"])
    assert state.exit_code == 0
    payload = json.loads(state.stdout)
    assert payload["model"] == "chair"
    assert payload["latest_snapshot"] is None
    assert payload["pins"] == []
    assert payload["cameras"] == []

    restarted = runner.invoke(app, ["session", "restart", "chair", "2026-11-11-design"])
    assert restarted.exit_code == 0

    missing = runner.invoke(app, ["state", "missing", "--json"])
    assert missing.exit_code == 1
    assert set(json.loads(missing.stdout)) == {"error"}

    stopped = runner.invoke(app, ["session", "stop", "chair", "2026-11-11-design"])
    assert stopped.exit_code == 0
