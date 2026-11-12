"""Client for the blender-mcp add-on's socket bridge (the one the agent's MCP server uses).

Protocol: send one JSON object {"type": ..., "params": {...}}; Blender runs it on its main
thread and answers with one JSON object {"status": "success"|"error", ...}, unframed, so
the reply is read until it parses. The add-on serves each connection on its own thread,
so `blend repl` and the agent can be connected at the same time.
"""

import json
import socket
import time

PORT = 9876


class BridgeError(RuntimeError):
    pass


def listening(port: int = PORT, host: str = "localhost") -> bool:
    try:
        socket.create_connection((host, port), timeout=0.5).close()
    except OSError:
        return False
    return True


def wait_listening(port: int = PORT, seconds: float = 90.0) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if listening(port):
            return True
        time.sleep(0.5)
    return False


class Bridge:
    def __init__(
        self,
        port: int = PORT,
        host: str = "localhost",
        timeout: float = 600,
        connect_timeout: float = 5,
    ):
        self.addr = (host, port)
        self.timeout = timeout
        self.connect_timeout = connect_timeout
        self.sock: socket.socket | None = None

    def close(self) -> None:
        if self.sock is not None:
            self.sock.close()
            self.sock = None

    def send(self, kind: str, **params) -> dict:
        """Run one add-on command and return its result; BridgeError on failure."""
        if self.sock is None:
            try:
                self.sock = socket.create_connection(
                    self.addr, timeout=self.connect_timeout
                )
            except OSError as e:
                raise BridgeError(f"no Blender on port {self.addr[1]}: {e}") from e
            self.sock.settimeout(self.timeout)
        try:
            self.sock.sendall(json.dumps({"type": kind, "params": params}).encode())
            reply = self._read()
        except BaseException:
            self.close()  # a half-read reply would corrupt the next one
            raise
        if reply.get("status") == "error":
            raise BridgeError(reply.get("message", "unknown error"))
        return reply.get("result", {})

    def _read(self) -> dict:
        if self.sock is None:
            raise BridgeError("Blender socket is not connected")
        sock = self.sock
        buf = b""
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                raise BridgeError("Blender closed the connection")
            buf += chunk
            try:
                return json.loads(buf.decode())
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue  # partial reply

    def execute(self, code: str) -> str:
        """Run Python in Blender; returns what it printed."""
        return self.send("execute_code", code=code).get("result", "")
