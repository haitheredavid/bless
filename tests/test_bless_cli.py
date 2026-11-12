import json
from pathlib import Path

from typer.testing import CliRunner

from blend.bless_cli import app


def test_session_cli_lifecycle(tmp_path: Path, monkeypatch) -> None:
    model = tmp_path / "models" / "chair"
    model.mkdir(parents=True)
    (model / "model.blend").touch()
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

    stopped = runner.invoke(app, ["session", "stop", "chair", "2026-11-11-design"])
    assert stopped.exit_code == 0
