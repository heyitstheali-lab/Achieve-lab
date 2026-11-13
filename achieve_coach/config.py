"""Settings stored in ~/.achieve-coach/config.json."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

CONFIG_DIR = Path.home() / ".achieve-coach"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class Config:
    api_key: str = ""
    model: str = "claude-opus-5-5"
    effort: str = "medium"
    hotkey: str = "<ctrl>+<shift>+h"
    monitor: int = 1
    always_on_top: bool = True

    def effective_api_key(self) -> str:
        """The ANTHROPIC_API_KEY environment variable wins over the saved key."""
        return os.environ.get("ANTHROPIC_API_KEY") or self.api_key


def load() -> Config:
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return Config()
    known = {k: v for k, v in data.items() if k in Config.__dataclass_fields__}
    return Config(**known)


def save(cfg: Config) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(asdict(cfg), indent=2), encoding="utf-8")
    try:
        os.chmod(CONFIG_FILE, 0o600)  # the file holds your API key
    except OSError:
        pass
