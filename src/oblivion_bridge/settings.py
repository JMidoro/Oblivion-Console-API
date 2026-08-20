from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_MAILBOX_DIR = (
    Path.home()
    / "Documents"
    / "My Games"
    / "Oblivion Remastered"
    / "Saved"
    / "CompanionBridge"
)


def _positive_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    value = float(raw_value)
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _port(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    value = int(raw_value)
    if not 1 <= value <= 65535:
        raise ValueError(f"{name} must be between 1 and 65535")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    mailbox_dir: Path = DEFAULT_MAILBOX_DIR
    timeout_seconds: float = 60.0
    poll_interval_seconds: float = 0.05
    port: int = 8765

    @classmethod
    def from_environment(cls) -> Settings:
        mailbox_value = os.getenv("OBLIVION_BRIDGE_MAILBOX_DIR")
        mailbox_dir = (
            Path(mailbox_value).expanduser()
            if mailbox_value
            else DEFAULT_MAILBOX_DIR
        )
        return cls(
            mailbox_dir=mailbox_dir,
            timeout_seconds=_positive_float(
                "OBLIVION_BRIDGE_TIMEOUT_SECONDS", 60.0
            ),
            poll_interval_seconds=_positive_float(
                "OBLIVION_BRIDGE_POLL_INTERVAL_SECONDS", 0.05
            ),
            port=_port("OBLIVION_BRIDGE_PORT", 8765),
        )
