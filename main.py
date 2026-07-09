"""
main.py
=======
Entry point for the Secure Password Generator desktop application.

Run with:
    python main.py
"""

from __future__ import annotations

import sys


def main() -> None:
    try:
        from gui import run
    except ImportError as e:
        print(
            "Failed to start the GUI. Make sure Tkinter is installed "
            "(it ships with most standard Python installers; on Linux you "
            f"may need `sudo apt install python3-tk`).\nDetails: {e}",
            file=sys.stderr,
        )
        sys.exit(1)

    run()


if __name__ == "__main__":
    main()
