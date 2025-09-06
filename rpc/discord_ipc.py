import json
import os
import socket
import struct
import sys
from typing import Any, Optional


class DiscordIPC:
    OP_HANDSHAKE = 0
    OP_FRAME = 1
    OP_CLOSE = 2
    OP_PING = 3
    OP_PONG = 4

    MAX_IPC_PIPES = 10

    def __init__(self):
        self.connection = None
        self.pipe_name = None
        self.connected = False

    def connect(self) -> bool:
        if sys.platform == "win32":
            return self._connect_windows()
        else:
            return self._connect_unix()

    def _get_ipc_path(self, id: int) -> str:
        if sys.platform == "win32":
            return f"\\\\?\\pipe\\discord-ipc-{id}"

        env_vars = ["XDG_RUNTIME_DIR", "TMPDIR", "TMP", "TEMP"]
        prefix = next(
            (os.environ.get(var) for var in env_vars if os.environ.get(var)), "/tmp"
        )

        return f'{prefix.rstrip("/")}/discord-ipc-{id}'

    def _connect_windows(self) -> bool:
        for i in range(self.MAX_IPC_PIPES):
            pipe_name = self._get_ipc_path(i)
            try:
                self.connection = open(pipe_name, "rb+")
                self.pipe_name = pipe_name
                self.connected = True
                return True
            except FileNotFoundError:
                continue
        return False

    def _connect_unix(self) -> bool:
        for i in range(self.MAX_IPC_PIPES):
            path = self._get_ipc_path(i)
            try:
                self.connection = socket.socket(socket.AF_UNIX)
                self.connection.connect(path)
                self.pipe_name = path
                self.connected = True
                return True
            except (FileNotFoundError, ConnectionRefusedError):
                if self.connection:
                    self.connection.close()
                continue
        return False

    def disconnect(self) -> None:
        if self.connection:
            if isinstance(self.connection, socket.socket):
                self.connection.close()
            else:
                self.connection.close()
            self.connection = None
            self.connected = False

    def send(self, opcode: int, payload: dict[str, Any]) -> bool:
        if not self.connected:
            return False

        payload_bytes = json.dumps(payload).encode("utf-8")
        header = struct.pack("<II", opcode, len(payload_bytes))
        data = header + payload_bytes

        try:
            if isinstance(self.connection, socket.socket):
                self.connection.sendall(data)
            else:
                self.connection.write(data)
                self.connection.flush()
            return True
        except (BrokenPipeError, ConnectionError, OSError):
            self.connected = False
            return False

    def recv(self) -> Optional[tuple[int, dict[str, Any]]]:
        if not self.connected:
            return None

        try:
            if isinstance(self.connection, socket.socket):
                header = self.connection.recv(8)
            else:
                header = self.connection.read(8)

            if len(header) != 8:
                return None

            opcode, length = struct.unpack("<II", header)

            if isinstance(self.connection, socket.socket):
                payload_bytes = self.connection.recv(length)
            else:
                payload_bytes = self.connection.read(length)

            payload = json.loads(payload_bytes.decode("utf-8"))
            return (opcode, payload)
        except (BrokenPipeError, ConnectionError, json.JSONDecodeError, OSError):
            self.connected = False
            return None
