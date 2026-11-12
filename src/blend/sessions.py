"""Durable Bless runtime records and deterministic port allocation."""

import json
import os
import re
import socket
import tempfile
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

PORT_MIN = 9877
PORT_MAX = 9976
SESSION_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9][a-z0-9-]*$")
MODEL_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def bless_root() -> Path:
    """Repository root used for runtime state (BLESS_ROOT overrides the contract default)."""
    return Path(os.environ.get("BLESS_ROOT", "~/projects/bless")).expanduser().resolve()


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class SessionRecord(BaseModel):
    model_config = ConfigDict(
        extra="forbid", populate_by_name=True, serialize_by_alias=True
    )

    schema_version: Literal[1] = Field(1, alias="schema")
    model: str
    session: str
    desired: Literal["running", "stopped"]
    status: Literal["starting", "ready", "hung", "restarting", "stopped", "failed"]
    port: int | None
    pid: int | None
    blend: str
    mcp_config: str | None
    started_at: str | None
    updated_at: str
    last_ping_at: str | None
    restarts: int
    last_error: str | None
    last_snapshot: str | None
    agent_pane: str | None = None
    attention: str | None = None

    @property
    def schema(self) -> Literal[1]:  # ty: ignore[invalid-property-type-override]
        """Contract spelling while avoiding Pydantic's deprecated schema() method."""
        return self.schema_version

    @field_validator("model")
    @classmethod
    def valid_model(cls, value: str) -> str:
        if not MODEL_RE.fullmatch(value):
            raise ValueError("model must be a lowercase slug")
        return value

    @field_validator("session")
    @classmethod
    def valid_session(cls, value: str) -> str:
        return validate_session_name(value)


def validate_session_name(session: str) -> str:
    if not SESSION_RE.fullmatch(session):
        raise ValueError("session must be a session-note stem YYYY-MM-DD-<slug>")
    return session


def record_path(model: str, session: str, root: Path | None = None) -> Path:
    return (root or bless_root()) / ".bless" / "sessions" / model / f"{session}.json"


def mcp_config_path(model: str, session: str, root: Path | None = None) -> Path:
    return (
        (root or bless_root()) / ".bless" / "sessions" / model / f"{session}.mcp.json"
    )


def read_record(model: str, session: str, root: Path | None = None) -> SessionRecord:
    path = record_path(model, session, root)
    return SessionRecord.model_validate_json(path.read_text())


def write_record(record: SessionRecord, root: Path | None = None) -> Path:
    """Atomically replace a record with a complete, fsynced JSON document."""
    path = record_path(record.model, record.session, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    record.updated_at = now_iso()
    data = json.dumps(record.model_dump(by_alias=True), separators=(",", ":")) + "\n"
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise
    return path


def update_agent_fields(
    model: str,
    session: str,
    root: Path | None = None,
    *,
    agent_pane: str | None = None,
    attention: str | None = None,
    clear_attention: bool = False,
) -> SessionRecord:
    """Set the UI-owned fields (agent pane, attention) on a fresh copy of the record."""
    record = read_record(model, session, root)
    if agent_pane is not None:
        record.agent_pane = agent_pane
    if clear_attention:
        record.attention = None
    elif attention is not None:
        record.attention = attention
    write_record(record, root)
    return record


def list_records(root: Path | None = None) -> list[SessionRecord]:
    directory = (root or bless_root()) / ".bless" / "sessions"
    if not directory.exists():
        return []
    paths = [
        path
        for path in directory.glob("*/*.json")
        if not path.name.endswith(".mcp.json")
    ]
    records = [SessionRecord.model_validate_json(path.read_text()) for path in paths]
    return sorted(records, key=lambda item: (item.model, item.session))


def tcp_listening(port: int, host: str = "127.0.0.1") -> bool:
    """Bind-test whether a port is unavailable, including non-listening owners."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind((host, port))
    except OSError:
        return True
    finally:
        probe.close()
    return False


def allocate_port(
    records: Iterable[SessionRecord],
    is_listening: Callable[[int], bool] = tcp_listening,
    first: int = PORT_MIN,
    last: int = PORT_MAX,
) -> int:
    """Choose the lowest port neither reserved by a running record nor listening."""
    held = {r.port for r in records if r.desired == "running" and r.port is not None}
    for port in range(first, last + 1):
        if port not in held and not is_listening(port):
            return port
    raise RuntimeError(f"no free Bless port in {first}-{last}")


def write_mcp_config(
    model: str, session: str, port: int, root: Path | None = None
) -> Path:
    path = mcp_config_path(model, session, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "mcpServers": {
            "blender": {
                "type": "stdio",
                "command": "uvx",
                "args": ["mcp-for-blender==2.2.7", "--port", str(port)],
            }
        }
    }
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(payload, stream, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise
    return path


def new_record(model: str, session: str, blend: Path) -> SessionRecord:
    validate_session_name(session)
    stamp = now_iso()
    return SessionRecord(
        model=model,
        session=session,
        desired="running",
        status="starting",
        port=None,
        pid=None,
        blend=str(blend.resolve()),
        mcp_config=None,
        started_at=None,
        updated_at=stamp,
        last_ping_at=None,
        restarts=0,
        last_error=None,
        last_snapshot=None,
    )
