"""
generator.py
============
Cryptographically secure generation engine for the Secure Password Generator.

All randomness for anything security-relevant (passwords, PINs, Wi-Fi keys)
uses Python's `secrets` module, which is backed by the OS CSPRNG
(``os.urandom``). The `random` module is intentionally NOT used for any
value that is meant to be unguessable -- it is a Mersenne Twister PRNG and
is not safe for security purposes, even though it appears in the project's
tech stack for utility tasks (e.g. shuffling non-secret display lists).

Classes
-------
PasswordGenerator
    Generates passwords, passphrases, PINs, usernames, and Wi-Fi keys.

Exceptions
----------
GeneratorError
    Raised for invalid configuration (e.g. no character set selected,
    length too short for the "no repeated characters" constraint, etc).
"""

from __future__ import annotations

import secrets
import string
from dataclasses import dataclass, field
from typing import List

# ---------------------------------------------------------------------------
# Character pools
# ---------------------------------------------------------------------------

UPPERCASE = string.ascii_uppercase
LOWERCASE = string.ascii_lowercase
DIGITS = string.digits
SYMBOLS = "!@#$%^&*_-+=?"  # curated, safely-typeable symbol set

# Characters that are easy to visually confuse with one another.
SIMILAR_CHARS = "O0Il1"

# Symbols that render ambiguously in some fonts / are awkward in some
# systems (brackets, quotes, backslashes, etc).
AMBIGUOUS_SYMBOLS = "{}[]()/\\'\"`~,;:.<>|"

# A small, curated word list for the passphrase generator
# (an "EFF-style" word list -- short on purpose to keep the project
# self-contained; swap in the full EFF long list for production use).
WORDLIST: List[str] = [
    "anchor", "banjo", "canyon", "delta", "ember", "falcon", "granite",
    "harbor", "indigo", "jungle", "kayak", "lumber", "meadow", "nectar",
    "oasis", "piston", "quartz", "raptor", "silver", "timber", "umbra",
    "velvet", "walnut", "xenon", "yonder", "zephyr", "amber", "boulder",
    "cactus", "drift", "eagle", "forge", "glacier", "hollow", "ivory",
    "jasper", "knight", "lagoon", "marble", "nomad", "onyx", "prairie",
    "quiver", "ridge", "summit", "thicket", "urban", "valley", "willow",
    "yeoman", "zenith", "alpine", "basalt", "cedar", "dusk", "echo",
    "frost", "grove", "haven", "island", "jade", "keel", "lantern",
    "mint", "north", "orbit", "pebble", "quest", "river", "stone",
    "tundra", "utopia", "vapor", "wander", "yield", "zircon",
]

VOWELS = "aeiou"
CONSONANTS = "".join(c for c in string.ascii_lowercase if c not in VOWELS)


class GeneratorError(ValueError):
    """Raised when generation parameters are invalid."""


@dataclass
class PasswordOptions:
    """Configuration for a single password generation request."""

    length: int = 16
    use_upper: bool = True
    use_lower: bool = True
    use_digits: bool = True
    use_symbols: bool = True
    exclude_similar: bool = False
    exclude_ambiguous: bool = False
    no_repeat: bool = False
    count: int = 1
    charset_override: str = field(default="")  # used internally after filtering


class PasswordGenerator:
    """Generates secure passwords and related secrets.

    All methods that produce secret material use ``secrets.SystemRandom``
    (or the ``secrets`` module functions directly), which draws from the
    operating system's cryptographically secure random source.
    """

    def __init__(self) -> None:
        self._rng = secrets.SystemRandom()

    # ------------------------------------------------------------------
    # Password generation
    # ------------------------------------------------------------------

    def _build_pools(self, opts: PasswordOptions) -> List[str]:
        """Return a list of character pools, one per selected category."""
        pools: List[str] = []
        if opts.use_upper:
            pools.append(UPPERCASE)
        if opts.use_lower:
            pools.append(LOWERCASE)
        if opts.use_digits:
            pools.append(DIGITS)
        if opts.use_symbols:
            pools.append(SYMBOLS)

        if not pools:
            raise GeneratorError("At least one character type must be selected.")

        if opts.exclude_similar:
            pools = [self._strip(p, SIMILAR_CHARS) for p in pools]
        if opts.exclude_ambiguous:
            pools = [self._strip(p, AMBIGUOUS_SYMBOLS) for p in pools]

        # Drop pools that became empty after filtering
        pools = [p for p in pools if p]
        if not pools:
            raise GeneratorError(
                "All characters in the selected categories were excluded by "
                "your filters. Relax 'exclude similar' / 'exclude ambiguous'."
            )
        return pools

    @staticmethod
    def _strip(pool: str, remove: str) -> str:
        return "".join(c for c in pool if c not in remove)

    def generate_password(self, opts: PasswordOptions) -> str:
        """Generate a single password according to ``opts``.

        Guarantees at least one character from every selected category
        (upper/lower/digits/symbols) when the length allows it.
        """
        if opts.length < 4 or opts.length > 128:
            raise GeneratorError("Password length must be between 4 and 128.")

        pools = self._build_pools(opts)
        combined = "".join(pools)

        if opts.no_repeat:
            if opts.length > len(set(combined)):
                raise GeneratorError(
                    "Cannot generate a password of this length without repeated "
                    f"characters: only {len(set(combined))} unique characters "
                    "are available in the selected character set."
                )
            # Guarantee category coverage, then fill the rest uniquely.
            unique_pool = list(dict.fromkeys(combined))  # preserve order, dedupe
            guaranteed = [self._rng.choice(list(set(p))) for p in pools]
            remaining_pool = [c for c in unique_pool if c not in guaranteed]
            self._rng.shuffle(remaining_pool)
            fill = remaining_pool[: opts.length - len(guaranteed)]
            password_chars = guaranteed + fill
        else:
            guaranteed = [self._rng.choice(p) for p in pools]
            fill_count = opts.length - len(guaranteed)
            fill = [self._rng.choice(combined) for _ in range(fill_count)]
            password_chars = guaranteed + fill

        self._rng.shuffle(password_chars)
        return "".join(password_chars[: opts.length])

    def generate_many(self, opts: PasswordOptions) -> List[str]:
        """Generate ``opts.count`` passwords (1-20)."""
        if not (1 <= opts.count <= 20):
            raise GeneratorError("Password count must be between 1 and 20.")
        return [self.generate_password(opts) for _ in range(opts.count)]

    # ------------------------------------------------------------------
    # Passphrases ("correct horse battery staple")
    # ------------------------------------------------------------------

    def generate_passphrase(
        self, word_count: int = 4, separator: str = "-", capitalize: bool = True,
        include_number: bool = True,
    ) -> str:
        if word_count < 3 or word_count > 10:
            raise GeneratorError("Passphrase word count must be between 3 and 10.")
        words = [secrets.choice(WORDLIST) for _ in range(word_count)]
        if capitalize:
            words = [w.capitalize() for w in words]
        if include_number:
            words.append(str(secrets.randbelow(90) + 10))  # 2-digit number
        return separator.join(words)

    # ------------------------------------------------------------------
    # PIN generator
    # ------------------------------------------------------------------

    def generate_pin(self, length: int = 6) -> str:
        if length < 3 or length > 12:
            raise GeneratorError("PIN length must be between 3 and 12.")
        return "".join(str(secrets.randbelow(10)) for _ in range(length))

    # ------------------------------------------------------------------
    # Pronounceable ("memorable") password mode
    # ------------------------------------------------------------------

    def generate_pronounceable(self, length: int = 10, capitalize: bool = True,
                                trailing_number: bool = True) -> str:
        """Generate a pronounceable password using alternating consonant/vowel
        syllables. NOTE: pronounceable passwords have lower entropy per
        character than fully random ones -- they trade some strength for
        memorability and should be used for lower-stakes accounts only.
        """
        if length < 4 or length > 64:
            raise GeneratorError("Pronounceable password length must be 4-64.")
        chars = []
        use_consonant = True
        while len("".join(chars)) < length:
            pool = CONSONANTS if use_consonant else VOWELS
            chars.append(secrets.choice(pool))
            use_consonant = not use_consonant
        result = "".join(chars)[:length]
        if capitalize:
            result = result.capitalize()
        if trailing_number:
            result += str(secrets.randbelow(90) + 10)
        return result

    # ------------------------------------------------------------------
    # Username generator
    # ------------------------------------------------------------------

    def generate_username(self) -> str:
        adjectives = ["Swift", "Silent", "Crimson", "Lunar", "Rapid", "Hidden",
                      "Bold", "Arctic", "Solar", "Quiet"]
        nouns = ["Falcon", "Otter", "Comet", "Phoenix", "Badger", "Raven",
                 "Tiger", "Cobra", "Wolf", "Hawk"]
        adj = secrets.choice(adjectives)
        noun = secrets.choice(nouns)
        number = secrets.randbelow(900) + 100
        return f"{adj}{noun}{number}"

    # ------------------------------------------------------------------
    # Wi-Fi password generator
    # ------------------------------------------------------------------

    def generate_wifi_password(self, length: int = 20) -> str:
        """WPA2/WPA3 keys support 8-63 printable ASCII characters. We
        default to a long, fully-random alphanumeric+symbol key.
        """
        if length < 8 or length > 63:
            raise GeneratorError("Wi-Fi password length must be between 8 and 63.")
        opts = PasswordOptions(
            length=length, use_upper=True, use_lower=True,
            use_digits=True, use_symbols=True, exclude_ambiguous=True,
        )
        return self.generate_password(opts)
