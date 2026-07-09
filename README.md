# 🔐 Secure Password Generator

A modern, cryptographically secure password generator with a Tkinter GUI —
built in Python with security best practices, a strength/entropy meter,
encrypted local history, and a handful of extra generators (passphrases,
PINs, Wi-Fi keys, usernames, QR codes).

> **Status note:** this project was built and unit-tested in a headless,
> network-restricted environment that does not have Tkinter, `qrcode`, or
> `pyperclip` installed. The core logic (`generator.py`, `strength.py`,
> `settings.py`, `history.py`) was fully executed and passes **41 automated
> tests**. The GUI (`gui.py`) compiles cleanly and was written and reviewed
> carefully, but **has not been visually run** — install the dependencies
> below and run it locally before you trust it end-to-end. See
> [Known Limitations](#known-limitations--future-improvements).

---

## Features

### Password Generation
- Adjustable length: **4–128 characters** (slider)
- Toggle uppercase / lowercase / numbers / symbols
- Exclude visually similar characters (`O`, `0`, `I`, `l`, `1`)
- Exclude ambiguous symbols (brackets, quotes, backslashes, etc.)
- "No repeated characters" mode
- Generate **1–20 passwords** at once
- Guarantees at least one character from every selected category

### Strength Analysis
- Live **Weak / Medium / Strong / Very Strong** rating
- Visual strength meter (color-coded progress bar)
- Estimated entropy (bits), calculated from the actual character pool used
- Estimated crack time under two threat models: a fast offline attack
  (10¹⁰ guesses/sec) and a rate-limited online attack (10 guesses/sec)

### Clipboard & QR
- One-click **Copy** (via `pyperclip`, with an automatic Tkinter clipboard
  fallback if `pyperclip` isn't installed)
- Confirmation message in the status bar after copying
- **Show QR** button to render the password as a scannable QR code
  (requires `qrcode` + `Pillow`)

### History & Save
- Save generated passwords to a local history file
- History is **encrypted at rest with Fernet (AES)** via the `cryptography`
  package, using a locally-stored key (`data/history.key`)
- If `cryptography` isn't installed, the app **transparently falls back to
  plain JSON** and clearly labels the history tab as unencrypted — it never
  silently pretends to be more secure than it is
- Delete/clear history with a confirmation prompt
- Export history to **TXT** or **CSV**

### Settings
- Remembers last password length, last selected options, and theme
- Persisted to `data/settings.json`

### Extra Generators
- **Passphrase generator** ("correct horse battery staple" style)
- **PIN generator** (3–12 digits)
- **Pronounceable / memorable password mode** (lower entropy per
  character — clearly labeled as a memorability/security trade-off)
- **Random username generator**
- **Random Wi-Fi password generator** (WPA2/WPA3-compliant length range)
- **Password statistics** tab (counts by rating, average entropy)

### UI
- Clean, tabbed Tkinter interface: Password / Passphrase-PIN-WiFi / History / Statistics
- Light and dark theme, toggleable, remembered between sessions
- Status bar for confirmations and errors
- Friendly, specific error messages (never a raw traceback)

---

## Screenshots

_This build environment has no display, so screenshots are placeholders._
See [`screenshots/README.txt`](screenshots/README.txt) for exact steps to
generate real ones after running the app locally.

| Password tab | History tab |
|---|---|
| _add `screenshots/main_dark.png`_ | _add `screenshots/history_tab.png`_ |

---

## Installation

```bash
git clone <your-repo-url>
cd PasswordGenerator
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Requirements
- Python 3.10+ (developed against 3.12)
- Tkinter (bundled with most Python installers; on Debian/Ubuntu:
  `sudo apt install python3-tk`)
- See `requirements.txt` for third-party packages (`pyperclip`, `qrcode[pil]`,
  `cryptography`). All three are **optional** — the app degrades gracefully
  if any are missing (see [Known Limitations](#known-limitations--future-improvements)).

## How to Run

```bash
python main.py
```

## Running Tests

```bash
python -m unittest discover -s tests -v
```

41 tests cover password generation (length bounds, character-class
selection, exclusion filters, no-repeat mode, uniqueness), entropy/strength
rating, settings persistence (including corrupt-file recovery), history
persistence/export/stats, and clipboard round-tripping (skips gracefully
when no clipboard is available, e.g. in CI).

---

## Folder Structure

```
PasswordGenerator/
│
├── main.py              # Entry point — run this
├── gui.py                # Tkinter GUI (all screens, theme, wiring)
├── generator.py           # Core secrets-based generation engine
├── strength.py            # Entropy calculation + strength rating
├── settings.py             # JSON settings persistence
├── history.py              # Encrypted history persistence + export
├── requirements.txt
├── README.md
├── LICENSE
├── assets/                 # Icons / static assets (empty, ready to use)
├── data/
│   ├── settings.json        # Sample settings file (auto-created if missing)
│   └── history.json          # Sample empty history (auto-created if missing)
├── screenshots/
│   └── README.txt             # How to generate real screenshots
└── tests/
    ├── test_generator.py
    ├── test_strength.py
    ├── test_settings_history.py
    └── test_clipboard.py
```

---

## Module Overview

- **`generator.py`** — All randomness that matters security-wise goes
  through `secrets.SystemRandom`, never `random`. Builds character pools
  per selected option, applies exclusion filters, guarantees category
  coverage, and supports a "no repeated characters" constraint (with a
  clear error if the requested length exceeds the available unique pool).
  Also generates passphrases, PINs, pronounceable passwords, usernames,
  and Wi-Fi keys.
- **`strength.py`** — Estimates entropy as `length × log2(pool_size)`
  (the standard approximation for randomly generated passwords), maps
  entropy to a Weak/Medium/Strong/Very Strong rating, and estimates crack
  time under two attack-speed assumptions.
- **`settings.py`** — Small JSON-backed key/value store for UI
  preferences. Recovers to defaults automatically if the file is missing
  or corrupted.
- **`history.py`** — Persists generated passwords. Encrypts the file with
  Fernet (AES) when `cryptography` is available; falls back to plain JSON
  otherwise, and always reports its actual encryption status to the UI
  rather than assuming. Also handles TXT/CSV export and history stats.
- **`gui.py`** — Tkinter presentation layer. Contains zero business logic
  of its own — it only calls into the four modules above and renders
  their output.
- **`main.py`** — Thin entry point with a friendly error if Tkinter isn't
  installed.

---

## Security Notes (read this)

- Password/PIN/passphrase/Wi-Fi-key generation uses `secrets`, which is
  seeded from the OS CSPRNG (`os.urandom`) — **not** `random`, which is a
  Mersenne Twister and is not safe for security-sensitive values.
- History encryption uses a key stored **on the same machine**
  (`data/history.key`). This protects the history file from casual
  inspection (e.g., someone browsing your files or a cloud backup seeing
  raw passwords) but is **not equivalent to a real password manager**:
  anyone with access to both `history.json` and `history.key` can decrypt
  everything. A production-grade tool would derive the key from a
  user-supplied master password via a slow KDF (Argon2id/PBKDF2) and never
  store the key at rest.
- Entropy/crack-time figures are estimates based on character-pool size.
  They assume the password was generated uniformly at random (true for
  everything this tool produces) — they are **not** a general-purpose
  password auditor for arbitrary human-chosen passwords (a tool like
  `zxcvbn` would be needed for that).

---

## Known Limitations & Future Improvements

- **GUI is untested in this environment** — Tkinter isn't installed in the
  sandbox this project was built in, so `gui.py` compiles and was reviewed
  carefully but has not been visually run or clicked through. Test it
  locally first, especially the QR window and file-export dialogs.
- Passphrase word list is a small, curated 74-word list for portability —
  swap in the full [EFF long word list](https://www.eff.org/dice) (7,776
  words) for stronger passphrases.
- History encryption key is stored locally, not derived from a user
  master password (see Security Notes above).
- No automated GUI tests (e.g. via `pytest-tkinter` or similar) — only the
  business-logic layer has automated tests.
- Potential future features: master-password-protected vault mode,
  password breach checking via the HaveIBeenPwned k-anonymity API,
  auto-clear clipboard after N seconds, CLI mode, browser extension.

---

## License

MIT — see [LICENSE](LICENSE).

## Author

**[Your Name Here]** — replace with your name, GitHub handle, and contact
info before publishing.
