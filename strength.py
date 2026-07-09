"""
strength.py
===========
Password strength estimation: Shannon-style entropy based on character-pool
size, a strength rating (Weak / Medium / Strong / Very Strong), and a rough
offline-attack crack-time estimate.

The entropy model here is the standard "pool size" approximation:

    entropy_bits = length * log2(pool_size)

This is a reasonable, widely-used estimate for *randomly generated*
passwords (which is what this tool produces). It is NOT a substitute for
a real pattern-aware estimator like zxcvbn for arbitrary human-chosen
passwords -- that is out of scope for this project but noted in the
README as a future improvement.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from generator import UPPERCASE, LOWERCASE, DIGITS, SYMBOLS


@dataclass
class StrengthResult:
    entropy_bits: float
    pool_size: int
    rating: str          # Weak / Medium / Strong / Very Strong
    score_percent: int    # 0-100, for a progress-bar style meter
    crack_time_offline: str  # fast offline attack (1e10 guesses/sec)
    crack_time_online: str   # throttled online attack (10 guesses/sec)


# Guess-rate assumptions (guesses per second)
OFFLINE_FAST_GPS = 1e10   # e.g. GPU cluster cracking a leaked hash
ONLINE_THROTTLED_GPS = 10  # e.g. a rate-limited login form


def estimate_pool_size(password: str) -> int:
    """Infer the character pool size actually used by a password."""
    pool = 0
    if any(c in UPPERCASE for c in password):
        pool += len(UPPERCASE)
    if any(c in LOWERCASE for c in password):
        pool += len(LOWERCASE)
    if any(c in DIGITS for c in password):
        pool += len(DIGITS)
    if any(c in SYMBOLS for c in password):
        pool += len(SYMBOLS)
    # Fallback: any character outside the known pools still counts as
    # contributing at least its own presence to the pool.
    other = set(c for c in password
                if c not in UPPERCASE + LOWERCASE + DIGITS + SYMBOLS)
    pool += len(other)
    return max(pool, 1)


def calculate_entropy(password: str) -> float:
    """Return the estimated entropy of ``password`` in bits."""
    pool_size = estimate_pool_size(password)
    if not password:
        return 0.0
    return len(password) * math.log2(pool_size)


def _format_duration(seconds: float) -> str:
    """Convert a seconds value into a human-friendly duration string."""
    if seconds < 1:
        return "instantly"

    units = [
        ("century", 60 * 60 * 24 * 365 * 100),
        ("year", 60 * 60 * 24 * 365),
        ("day", 60 * 60 * 24),
        ("hour", 60 * 60),
        ("minute", 60),
        ("second", 1),
    ]
    plurals = {
        "century": "centuries", "year": "years", "day": "days",
        "hour": "hours", "minute": "minutes", "second": "seconds",
    }
    for name, unit_seconds in units:
        value = seconds / unit_seconds
        if value >= 1:
            if value > 1_000_000_000_000:
                return "trillions of years"
            rounded = round(value, 1) if value < 100 else int(value)
            label = name if rounded == 1 else plurals[name]
            return f"~{rounded:,} {label}"
    return "instantly"


def estimate_crack_time(entropy_bits: float, guesses_per_second: float) -> str:
    """Rough time to exhaust half the keyspace at a given guess rate."""
    if entropy_bits <= 0:
        return "instantly"
    total_combinations = 2 ** entropy_bits
    seconds = (total_combinations / 2) / guesses_per_second
    return _format_duration(seconds)


def rate_strength(entropy_bits: float) -> tuple[str, int]:
    """Map entropy (bits) to a (rating, score_percent) pair.

    Thresholds follow common industry rules of thumb:
        < 28 bits  -> Weak
        28-59 bits -> Medium
        60-79 bits -> Strong
        >= 80 bits -> Very Strong
    """
    if entropy_bits < 28:
        return "Weak", min(100, int(entropy_bits / 28 * 25))
    if entropy_bits < 60:
        return "Medium", 25 + int((entropy_bits - 28) / (60 - 28) * 25)
    if entropy_bits < 80:
        return "Strong", 50 + int((entropy_bits - 60) / (80 - 60) * 25)
    return "Very Strong", min(100, 75 + int((entropy_bits - 80) / 40 * 25))


def analyze_password(password: str) -> StrengthResult:
    """Full strength analysis for ``password``."""
    entropy_bits = calculate_entropy(password)
    pool_size = estimate_pool_size(password)
    rating, score = rate_strength(entropy_bits)
    return StrengthResult(
        entropy_bits=round(entropy_bits, 2),
        pool_size=pool_size,
        rating=rating,
        score_percent=score,
        crack_time_offline=estimate_crack_time(entropy_bits, OFFLINE_FAST_GPS),
        crack_time_online=estimate_crack_time(entropy_bits, ONLINE_THROTTLED_GPS),
    )
