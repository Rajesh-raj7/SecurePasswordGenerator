"""Tests for settings.py and history.py, including invalid-input handling.

Each test uses a temporary directory so it never touches the real
data/settings.json or data/history.json used by the running application.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from settings import SettingsManager, DEFAULT_SETTINGS
from history import HistoryManager, HistoryEntry


class TestSettingsManager(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tmpdir.name) / "settings.json"

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_defaults_created_on_first_run(self) -> None:
        mgr = SettingsManager(path=self.path)
        self.assertEqual(mgr.get("length"), DEFAULT_SETTINGS["length"])
        self.assertTrue(self.path.exists())

    def test_update_persists_across_instances(self) -> None:
        mgr = SettingsManager(path=self.path)
        mgr.update(length=24, theme="light")
        mgr2 = SettingsManager(path=self.path)
        self.assertEqual(mgr2.get("length"), 24)
        self.assertEqual(mgr2.get("theme"), "light")

    def test_corrupt_file_falls_back_to_defaults(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("{not valid json", encoding="utf-8")
        mgr = SettingsManager(path=self.path)
        self.assertEqual(mgr.get("length"), DEFAULT_SETTINGS["length"])

    def test_reset(self) -> None:
        mgr = SettingsManager(path=self.path)
        mgr.update(length=99)
        mgr.reset()
        self.assertEqual(mgr.get("length"), DEFAULT_SETTINGS["length"])


class TestHistoryManager(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tmpdir.name) / "history.json"
        self.key_path = Path(self.tmpdir.name) / "history.key"

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_add_and_reload(self) -> None:
        mgr = HistoryManager(path=self.path, key_path=self.key_path)
        mgr.add(HistoryEntry.new("Abc123!@#", "Strong", 55.0))
        mgr2 = HistoryManager(path=self.path, key_path=self.key_path)
        self.assertEqual(len(mgr2.all()), 1)
        self.assertEqual(mgr2.all()[0].password, "Abc123!@#")

    def test_clear(self) -> None:
        mgr = HistoryManager(path=self.path, key_path=self.key_path)
        mgr.add(HistoryEntry.new("pw1", "Weak", 10.0))
        mgr.clear()
        self.assertEqual(mgr.all(), [])

    def test_export_txt_and_csv(self) -> None:
        mgr = HistoryManager(path=self.path, key_path=self.key_path)
        mgr.add(HistoryEntry.new("pw1", "Weak", 10.0))
        mgr.add(HistoryEntry.new("pw2", "Strong", 60.0))

        txt_path = Path(self.tmpdir.name) / "out.txt"
        csv_path = Path(self.tmpdir.name) / "out.csv"
        mgr.export_txt(txt_path)
        mgr.export_csv(csv_path)

        self.assertIn("pw1", txt_path.read_text())
        self.assertIn("pw2", txt_path.read_text())
        csv_content = csv_path.read_text()
        self.assertIn("password,created_at,rating,entropy_bits,kind", csv_content)

    def test_stats_empty(self) -> None:
        mgr = HistoryManager(path=self.path, key_path=self.key_path)
        self.assertEqual(mgr.stats(), {"count": 0})

    def test_stats_counts_ratings(self) -> None:
        mgr = HistoryManager(path=self.path, key_path=self.key_path)
        mgr.add(HistoryEntry.new("pw1", "Weak", 10.0))
        mgr.add(HistoryEntry.new("pw2", "Weak", 12.0))
        mgr.add(HistoryEntry.new("pw3", "Very Strong", 100.0))
        stats = mgr.stats()
        self.assertEqual(stats["count"], 3)
        self.assertEqual(stats["weak"], 2)
        self.assertEqual(stats["very_strong"], 1)

    def test_corrupt_history_file_falls_back_to_empty(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(b"not a valid fernet token or json")
        mgr = HistoryManager(path=self.path, key_path=self.key_path)
        self.assertEqual(mgr.all(), [])


if __name__ == "__main__":
    unittest.main()
