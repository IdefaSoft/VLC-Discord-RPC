import os
import uuid
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Optional, Any

from .discord_ipc import DiscordIPC

__all__ = [
    "DiscordRPC",
    "ActivityType",
    "Timestamp",
    "Asset",
    "Party",
    "Button",
    "Activity",
]


class DiscordRPC:
    def __init__(self, client_id: str):
        self.client_id = client_id
        self.ipc = DiscordIPC()
        self.connected = False

    def connect(self) -> bool:
        if not self.ipc.connect():
            return False

        nonce = str(uuid.uuid4())
        payload = {"v": 1, "client_id": self.client_id, "nonce": nonce}

        self.ipc.send(self.ipc.OP_HANDSHAKE, payload)
        response = self.ipc.recv()

        if not response:
            self.ipc.disconnect()
            return False

        opcode, data = response

        if (
            opcode != self.ipc.OP_FRAME
            or data.get("cmd") != "DISPATCH"
            or data.get("evt") != "READY"
        ):
            self.ipc.disconnect()
            return False

        self.connected = True
        return True

    def disconnect(self) -> None:
        if self.connected:
            payload = {}
            self.ipc.send(self.ipc.OP_CLOSE, payload)
            self.ipc.disconnect()
            self.connected = False

    def set_activity(self, activity: Optional[dict[str, Any]]) -> bool:
        if not self.connected and (activity is None or not self.connect()):
            return False

        nonce = str(uuid.uuid4())
        payload = {
            "cmd": "SET_ACTIVITY",
            "args": {"pid": os.getpid(), "activity": activity},
            "nonce": nonce,
        }

        self.ipc.send(self.ipc.OP_FRAME, payload)
        response = self.ipc.recv()

        if not response:
            self.connected = False
            return False

        opcode, data = response
        return (
            opcode == self.ipc.OP_FRAME
            and data.get("cmd") == "SET_ACTIVITY"
            and data.get("nonce") == nonce
        )

    def clear_activity(self) -> bool:
        return self.set_activity(None)


class ActivityType(Enum):
    PLAYING = 0
    STREAMING = 1
    LISTENING = 2
    WATCHING = 3
    COMPETING = 5


@dataclass
class Timestamp:
    start: Optional[int] = None
    end: Optional[int] = None

    def to_dict(self) -> dict[str, int]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class Asset:
    large_image: Optional[str] = None
    large_text: Optional[str] = None
    small_image: Optional[str] = None
    small_text: Optional[str] = None

    def to_dict(self) -> dict[str, str]:
        return {k: v for k, v in asdict(self).items() if v}


@dataclass
class Button:
    label: str
    url: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class Activity:
    details: Optional[str] = None
    state: Optional[str] = None
    activity_type: ActivityType = ActivityType.PLAYING
    timestamps: Optional[Timestamp] = None
    assets: Optional[Asset] = None
    buttons: Optional[list[Button]] = None

    def to_dict(self) -> dict[str, Any]:
        result = {"type": self.activity_type.value}

        for field in ["details", "state"]:
            if getattr(self, field):
                result[field] = getattr(self, field)

        for field in ["timestamps", "assets"]:
            if (obj := getattr(self, field)) and (obj_dict := obj.to_dict()):
                result[field] = obj_dict

        if self.buttons:
            result["buttons"] = [btn.to_dict() for btn in self.buttons[:2]]

        return result
