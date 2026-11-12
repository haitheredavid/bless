import json
from pathlib import Path

import pytest

from blend.sessions import (
    SessionRecord,
    allocate_port,
    list_records,
    new_record,
    read_record,
    write_mcp_config,
    write_record,
)
from blend.supervisor import Supervisor


def record(
    tmp_path: Path, model: str = "chair", session: str = "2026-11-11-first"
) -> SessionRecord:
    blend = tmp_path / "models" / model / "model.blend"
    blend.parent.mkdir(parents=True, exist_ok=True)
    blend.touch()
    return new_record(model, session, blend)


def test_record_round_trip_atomic_and_listing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    item = record(tmp_path)
    replaced = []
    from blend import sessions

    original = sessions.os.replace

    def observed(source, destination):
        replaced.append((Path(source), Path(destination)))
        original(source, destination)

    monkeypatch.setattr(sessions.os, "replace", observed)
    path = write_record(item, tmp_path)

    assert replaced and replaced[0][1] == path
    assert not replaced[0][0].exists()
    assert read_record(item.model, item.session, tmp_path) == item
    assert list_records(tmp_path) == [item]
    payload = json.loads(path.read_text())
    assert payload["schema"] == 1
    assert set(payload) == {
        "schema",
        "model",
        "session",
        "desired",
        "status",
        "port",
        "pid",
        "blend",
        "mcp_config",
        "started_at",
        "updated_at",
        "last_ping_at",
        "restarts",
        "last_error",
        "last_snapshot",
        "agent_pane",
        "attention",
    }


def test_allocate_port_skips_held_and_listening(tmp_path: Path) -> None:
    held = record(tmp_path)
    held.port = 9877
    assert allocate_port([held], lambda port: port == 9878) == 9879


def test_allocate_port_ignores_stopped_record(tmp_path: Path) -> None:
    stopped = record(tmp_path)
    stopped.port = 9877
    stopped.desired = "stopped"
    assert allocate_port([stopped], lambda _port: False) == 9877


def test_allocate_port_exhaustion() -> None:
    with pytest.raises(RuntimeError, match="no free Bless port"):
        allocate_port([], lambda _port: True, first=9900, last=9901)


def test_supervisor_honors_explicit_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from blend import supervisor as supervisor_module

    item = record(tmp_path)
    item.pid = 123
    item.port = 9877
    item.status = "restarting"
    item.last_error = "restart requested"
    terminated = []
    launched = []
    monkeypatch.setattr(supervisor_module, "process_alive", lambda _pid: True)
    monkeypatch.setattr(
        supervisor_module, "terminate", lambda pid: terminated.append(pid)
    )
    instance = Supervisor(tmp_path)
    monkeypatch.setattr(
        instance,
        "_launch",
        lambda target, records: launched.append((target.pid, records)),
    )

    instance._tick_record(item, [item])

    assert terminated == [123]
    assert launched == [(None, [item])]
    assert item.restarts == 1
    assert item.last_error is None


def test_mcp_config_contract(tmp_path: Path) -> None:
    path = write_mcp_config("chair", "2026-11-11-first", 9879, tmp_path)
    assert json.loads(path.read_text()) == {
        "mcpServers": {
            "blender": {
                "type": "stdio",
                "command": "uvx",
                "args": ["mcp-for-blender==2.2.7", "--port", "9879"],
            }
        }
    }
