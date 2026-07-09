"""
history.py
==========
Manages generation history: saving generated passwords, listing history,
deleting it, and exporting to TXT / CSV.

Security note (read this before trusting this module with real secrets)
-------------------------------------------------------------------------
True password-manager-grade encryption requires a master password that the
*user* supplies and that is never stored, plus a KDF (e.g. Argon2/PBKDF2)
to derive a key from it. That is out of scope for a portfolio project and
is called out explicitly in the README as a future improvement.

What this module actually does:
    - If the third-party ``cryptography`` package is installed, history is
      encrypted at rest with Fernet (AES-128-CBC + HMAC) using a key stored
      in ``data/history.key``. Anyone with read access to that key file can
      decrypt the history -- this protects against casual inspection of
      ``history.json`` (e.g. someone browsing your files or a cloud sync
      backup) but is NOT a substitute for a real secrets manager.
    - If ``cryptography`` is not installed, the module transparently falls
      back to plain JSON and clearly labels the file/status as
      unencrypted so the user is never given a false sense of security.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List

DATA_DIR = Path(__file__).parent / "data"
HISTORY_FILE = DATA_DIR / "history.json"
KEY_FILE = DATA_DIR / "history.key"

try:
    from cryptography.fernet import Fernet
    ENCRYPTION_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised when dependency absent
    ENCRYPTION_AVAILABLE = False


@dataclass
class HistoryEntry:
    password: str
    created_at: str
    rating: str
    entropy_bits: float
    kind: str = "password"  # password | passphrase | pin | wifi | username

    @staticmethod
    def new(password: str, rating: str, entropy_bits: float,
            kind: str = "password") -> "HistoryEntry":
        return HistoryEntry(
            password=password,
            created_at=datetime.now().isoformat(timespec="seconds"),
            rating=rating,
            entropy_bits=entropy_bits,
            kind=kind,
        )


class HistoryManager:
    """Loads, saves, and exports password generation history."""

    def __init__(self, path: Path = HISTORY_FILE, key_path: Path = KEY_FILE) -> None:
        self.path = path
        self.key_path = key_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.encrypted = ENCRYPTION_AVAILABLE
        self._fernet = self._load_or_create_key() if self.encrypted else None
        self.entries: List[HistoryEntry] = self._load()

    # ------------------------------------------------------------------
    # Key management
    # ------------------------------------------------------------------

    def _load_or_create_key(self) -> "Fernet":
        if self.key_path.exists():
            key = self.key_path.read_bytes()
        else:
            key = Fernet.generate_key()
            self.key_path.write_bytes(key)
        return Fernet(key)

    # ------------------------------------------------------------------
    # Load / save
    # ------------------------------------------------------------------

    def _load(self) -> List[HistoryEntry]:
        if not self.path.exists():
            return []
        try:
            raw = self.path.read_bytes()
            if self.encrypted:
                raw = self._fernet.decrypt(raw)
            data = json.loads(raw.decode("utf-8"))
            return [HistoryEntry(**item) for item in data]
        except Exception:
            # Corrupt, empty, or undecryptable file: start fresh rather
            # than crashing the app.
            return []

    def _save(self) -> None:
        data = json.dumps([asdict(e) for e in self.entries], indent=2).encode("utf-8")
        if self.encrypted:
            data = self._fernet.encrypt(data)
        self.path.write_bytes(data)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, entry: HistoryEntry) -> None:
        self.entries.append(entry)
        self._save()

    def add_many(self, entries: List[HistoryEntry]) -> None:
        self.entries.extend(entries)
        self._save()

    def clear(self) -> None:
        self.entries = []
        self._save()

    def all(self) -> List[HistoryEntry]:
        return list(self.entries)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_txt(self, destination: Path) -> None:
        with destination.open("w", encoding="utf-8") as fh:
            for e in self.entries:
                fh.write(f"{e.password}\n")

    def export_csv(self, destination: Path) -> None:
        with destination.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["password", "created_at", "rating", "entropy_bits", "kind"])
            for e in self.entries:
                writer.writerow([e.password, e.created_at, e.rating, e.entropy_bits, e.kind])

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        if not self.entries:
            return {"count": 0}
        ratings = [e.rating for e in self.entries]
        avg_entropy = sum(e.entropy_bits for e in self.entries) / len(self.entries)
        return {
            "count": len(self.entries),
            "average_entropy_bits": round(avg_entropy, 2),
            "weak": ratings.count("Weak"),
            "medium": ratings.count("Medium"),
            "strong": ratings.count("Strong"),
            "very_strong": ratings.count("Very Strong"),
        }
