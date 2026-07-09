"""Tests for clipboard behavior.

pyperclip requires a display/clipboard provider and is not reliably
available in headless CI environments, so this test skips gracefully
when no clipboard mechanism is reachable instead of failing the build.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import pyperclip
    PYPERCLIP_AVAILABLE = True
except ImportError:
    PYPERCLIP_AVAILABLE = False


class TestClipboard(unittest.TestCase):
    @unittest.skipUnless(PYPERCLIP_AVAILABLE, "pyperclip not installed")
    def test_copy_and_paste_roundtrip(self) -> None:
        try:
            pyperclip.copy("Test-Password-123!")
            result = pyperclip.paste()
        except pyperclip.PyperclipException:
            self.skipTest("No clipboard mechanism available in this environment")
            return
        self.assertEqual(result, "Test-Password-123!")


if __name__ == "__main__":
    unittest.main()
