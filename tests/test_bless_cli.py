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
            "agent_pane": None,
            "attention": None,
            "last_prompt": None,
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

    attached = runner.invoke(
        app, ["session", "attach", "chair", "2026-11-11-design", "--pane", "w1:p2"]
    )
    assert attached.exit_code == 0
    flagged = runner.invoke(
        app,
        ["session", "attention", "chair", "2026-11-11-design", "--set", "look"],
    )
    assert flagged.exit_code == 0
    row = json.loads(runner.invoke(app, ["status", "--json"]).stdout)[0]
    assert (row["agent_pane"], row["attention"]) == ("w1:p2", "look")
    cleared = runner.invoke(
        app, ["session", "attention", "chair", "2026-11-11-design", "--clear"]
    )
    assert cleared.exit_code == 0
    row = json.loads(runner.invoke(app, ["status", "--json"]).stdout)[0]
    assert row["attention"] is None

    restarted = runner.invoke(app, ["session", "restart", "chair", "2026-11-11-design"])
    assert restarted.exit_code == 0

    missing = runner.invoke(app, ["state", "missing", "--json"])
    assert missing.exit_code == 1
    assert set(json.loads(missing.stdout)) == {"error"}

    stopped = runner.invoke(app, ["session", "stop", "chair", "2026-11-11-design"])
    assert stopped.exit_code == 0


def test_prompt_add_claim_and_state_graph(tmp_path: Path, monkeypatch) -> None:
    model = tmp_path / "models" / "chair"
    (model / "log").mkdir(parents=True)
    (model / "sessions").mkdir()
    (model / "model.blend").touch()
    (model / "model.toml").write_text('name = "chair"\n')
    monkeypatch.setenv("BLESS_ROOT", str(tmp_path))
    runner = CliRunner()
    session = "chair/2026-11-11-design"
    runner.invoke(app, ["session", "start", "chair", "2026-11-11-design"])

    added = runner.invoke(
        app,
        ["prompt", "add", "--session", session, "--layer", "model"]
        + ["--text", "make a seat", "--json"],
    )
    assert added.exit_code == 0
    created = json.loads(added.stdout)
    assert created["status"] == "queued" and created["id"].startswith("p-")

    claimed = runner.invoke(
        app,
        ["prompt", "claim", created["id"], "--session", session]
        + ["--layer", "model", "--json"],
    )
    assert claimed.exit_code == 0
    assert json.loads(claimed.stdout)["id"] == created["id"]
    assert json.loads(claimed.stdout)["provenance"] == "agent"

    missing = runner.invoke(
        app,
        ["prompt", "claim", "p-nope", "--session", session, "--layer", "model"],
    )
    assert missing.exit_code != 0

    combined = runner.invoke(app, ["state", "chair", "--json", "--graph"])
    assert combined.exit_code == 0
    payload = json.loads(combined.stdout)
    assert set(payload) == {"state", "graph", "cameras", "pins"}
    assert payload["state"]["model"] == "chair"
    assert any(node["id"] == created["id"] for node in payload["graph"]["nodes"])
