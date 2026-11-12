"""Foreground supervisor for one GUI Blender process per Bless session."""

import os
import signal
import subprocess
import time
from collections import defaultdict, deque
from pathlib import Path

from blend.bridge import Bridge, BridgeError
from blend.config import get_settings
from blend.sessions import (
    SessionRecord,
    allocate_port,
    bless_root,
    list_records,
    now_iso,
    read_record,
    write_mcp_config,
    write_record,
)

POLL_SECONDS = 2.0
PING_FAILURES = 3
FAST_FAILURE_SECONDS = 30.0
FAST_FAILURE_LIMIT = 5


def process_alive(pid: int | None) -> bool:
    if pid is None:
        return False
    try:
        waited, _status = os.waitpid(pid, os.WNOHANG)
        if waited == pid:
            return False
    except ChildProcessError:
        pass  # not our child (e.g. supervisor restarted); probe it below
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def ping(port: int) -> bool:
    client = Bridge(port=port, host="127.0.0.1", timeout=0.75, connect_timeout=0.25)
    try:
        client.send("ping")
        return True
    except (BridgeError, OSError, TimeoutError):
        return False
    finally:
        client.close()


def terminate(pid: int | None, timeout: float = 5.0) -> None:
    if not process_alive(pid):
        return
    assert pid is not None
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if not process_alive(pid):
            return
        time.sleep(0.1)
    os.kill(pid, signal.SIGKILL)


class Supervisor:
    def __init__(self, root: Path | None = None):
        self.root = (root or bless_root()).resolve()
        self.stopping = False
        self.ping_failures: dict[tuple[str, str], int] = defaultdict(int)
        self.fast_failures: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    @property
    def pid_path(self) -> Path:
        return self.root / ".bless" / "supervisor.pid"

    def _claim(self) -> None:
        self.pid_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            old_pid = int(self.pid_path.read_text().strip())
        except (FileNotFoundError, ValueError):
            old_pid = None
        if process_alive(old_pid):
            raise RuntimeError(f"Bless supervisor already running as pid {old_pid}")
        self.pid_path.unlink(missing_ok=True)
        fd = os.open(self.pid_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(fd, "w") as stream:
            stream.write(f"{os.getpid()}\n")

    def _write(self, record: SessionRecord) -> None:
        """Persist runtime fields without clobbering UI-owned agent_pane/attention."""
        try:
            fresh = read_record(record.model, record.session, self.root)
        except (FileNotFoundError, ValueError):
            pass
        else:
            record.agent_pane = fresh.agent_pane
            record.attention = fresh.attention
        write_record(record, self.root)

    def _release(self) -> None:
        try:
            if int(self.pid_path.read_text().strip()) == os.getpid():
                self.pid_path.unlink()
        except (FileNotFoundError, ValueError):
            pass

    def _signal(self, _signum, _frame) -> None:
        self.stopping = True

    def run(self) -> None:
        self._claim()
        previous = {
            sig: signal.signal(sig, self._signal)
            for sig in (signal.SIGINT, signal.SIGTERM)
        }
        try:
            while not self.stopping:
                self.tick()
                end = time.monotonic() + POLL_SECONDS
                while not self.stopping and time.monotonic() < end:
                    time.sleep(0.1)
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
            self._release()

    def tick(self) -> None:
        records = list_records(self.root)
        for record in records:
            try:
                self._tick_record(record, records)
            except Exception as exc:  # noqa: BLE001 - isolate one bad record
                record.last_error = str(exc)
                record.status = "failed"
                self._write(record)

    def _tick_record(self, record: SessionRecord, records: list[SessionRecord]) -> None:
        key = (record.model, record.session)
        alive = process_alive(record.pid)
        if record.desired == "stopped":
            if alive:
                terminate(record.pid)
            record.pid = None
            record.port = None
            record.status = "stopped"
            record.last_error = None
            self._write(record)
            self.ping_failures.pop(key, None)
            self.fast_failures.pop(key, None)
            return

        if record.status == "failed":
            return
        if (
            alive
            and record.status == "restarting"
            and record.last_error == "restart requested"
        ):
            terminate(record.pid)
            record.pid = None
            record.restarts += 1
            record.last_error = None
            self.ping_failures[key] = 0
            self._launch(record, records)
            return
        if not alive:
            if record.pid is None and record.status == "starting":
                self.fast_failures.pop(key, None)
            if record.pid is not None:
                self._note_fast_failure(record, key)
                if record.status == "failed":
                    self._write(record)
                    return
                record.restarts += 1
                record.status = "restarting"
            self._launch(record, records)
            return

        assert record.port is not None
        if ping(record.port):
            self.ping_failures[key] = 0
            record.status = "ready"
            record.last_ping_at = now_iso()
            record.last_error = None
            self._write(record)
            return

        self.ping_failures[key] += 1
        if record.status == "ready" and self.ping_failures[key] >= PING_FAILURES:
            record.status = "hung"
            record.last_error = f"ping failed {PING_FAILURES} consecutive times"
            self._write(record)
            terminate(record.pid)
            record.pid = None
            record.restarts += 1
            record.status = "restarting"
            self.ping_failures[key] = 0
            self._launch(record, records)

    def _note_fast_failure(self, record: SessionRecord, key: tuple[str, str]) -> None:
        now = time.monotonic()
        failures = self.fast_failures[key]
        failures.append(now)
        while failures and now - failures[0] > FAST_FAILURE_SECONDS:
            failures.popleft()
        if len(failures) >= FAST_FAILURE_LIMIT:
            record.status = "failed"
            record.last_error = (
                f"Blender exited {len(failures)} times within {FAST_FAILURE_SECONDS:g}s"
            )

    def _launch(self, record: SessionRecord, records: list[SessionRecord]) -> None:
        blend = Path(record.blend)
        if not blend.is_file():
            raise FileNotFoundError(f"blend file does not exist: {blend}")
        if record.port is None:
            record.port = allocate_port(records)
        config = write_mcp_config(
            record.model, record.session, record.port, root=self.root
        )
        record.mcp_config = str(config.resolve())
        startup = self.root / "blender_scripts" / "bless_startup.py"
        env = os.environ.copy()
        env["BLESS_PORT"] = str(record.port)
        process = subprocess.Popen(
            [str(get_settings().blender_bin), str(blend), "--python", str(startup)],
            cwd=self.root,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        record.pid = process.pid
        record.status = "starting" if record.restarts == 0 else "restarting"
        record.started_at = now_iso()
        record.last_error = None
        self._write(record)


def run_supervisor(root: Path | None = None) -> None:
    """Run until SIGINT/SIGTERM; Blender children intentionally remain alive."""
    Supervisor(root).run()
