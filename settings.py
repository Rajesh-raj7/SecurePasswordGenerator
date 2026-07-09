"""
settings.py
===========
Persists user preferences (last-used length, selected options, theme) to a
local JSON file at ``data/settings.json``. Not security-sensitive, so plain
JSON is appropriate here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

DATA_DIR = Path(__file__).parent / "data"
SETTINGS_FILE = DATA_DIR / "settings.json"

DEFAULT_SETTINGS: Dict[str, Any] = {
    "length": 16,
    "use_upper": True,
    "use_lower": True,
    "use_digits": True,
    "use_symbols": True,
    "exclude_similar": False,
    "exclude_ambiguous": False,
    "no_repeat": False,
    "count": 1,
    "theme": "dark",
}


class SettingsManager:
    """Loads and saves application settings as JSON."""

    def __init__(self, path: Path = SETTINGS_FILE) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.settings: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if not self.path.exists():
            self._write(DEFAULT_SETTINGS)
            return dict(DEFAULT_SETTINGS)
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            merged = dict(DEFAULT_SETTINGS)
            merged.update(data)
            return merged
        except (json.JSONDecodeError, OSError):
            # Corrupt or unreadable file -- fall back to defaults rather
            # than crashing the app.
            self._write(DEFAULT_SETTINGS)
            return dict(DEFAULT_SETTINGS)

    def _write(self, data: Dict[str, Any]) -> None:
        with self.path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        return self.settings.get(key, default)

    def update(self, **kwargs: Any) -> None:
        self.settings.update(kwargs)
        self._write(self.settings)

    def reset(self) -> None:
        self.settings = dict(DEFAULT_SETTINGS)
        self._write(self.settings)
