"""RFC-058 §4 — password hashing parity with openpyxl.

Two algorithms covered:

* :func:`wolfxl.utils.protection.hash_password` — the legacy 16-bit
  XOR hash openpyxl emits as the ``password=`` attribute on
  ``<workbookProtection>``. Byte-equality vs ``openpyxl.utils.protection.hash_password``
  is the explicit acceptance criterion.
* :func:`wolfxl.utils.protection.hash_password_sha512` — the modern
  ECMA-376 spin hash. Tested against fixed salt + spin-count fixture
  vectors so a future refactor can't silently change the algorithm
  output.
"""

from __future__ import annotations

import openpyxl.utils.protection as op_protection
import pytest
from wolfxl.utils.protection import (
    hash_password,
    hash_password_sha512,
    verify_password_sha512,
)


# ---------------------------------------------------------------------------
# Legacy XOR hash — byte-equality with openpyxl
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "plaintext,expected_hex",
    [
        ("", "CE4B"),
        ("A", "CEC8"),
        ("hunter2", "C258"),
        ("test", "CBEB"),
        ("longer-password-with-special-chars", "2C9AEAE"),
    ],
)
def test_legacy_hash_matches_known_outputs(plaintext: str, expected_hex: str) -> None:
    """Captured from openpyxl 3.1.5; this test fires if our hash drifts."""
    assert hash_password(plaintext) == expected_hex


@pytest.mark.parametrize(
    "plaintext",
    ["", "x", "hunter2", "p@ssw0rd!", "café", "hello world", "a" * 100],
)
def test_legacy_hash_byte_equal_with_openpyxl(plaintext: str) -> None:
    """Direct comparison with openpyxl's reference implementation."""
    assert hash_password(plaintext) == op_protection.hash_password(plaintext)


# ---------------------------------------------------------------------------
# Modern SHA-512 spin hash — fixture vectors
# ---------------------------------------------------------------------------


def test_sha512_known_vector_100k_spins() -> None:
    """``hunter2`` + sequential 16-byte salt + 100k SHA-512 spins.

    Captured from a manual ECMA-376 §22.4.3.2 reference computation;
    this test fires if the algorithm or byte order ever drifts.
    """
    salt = bytes(range(16))  # 0x00..0x0F
    h, s = hash_password_sha512(
        "hunter2",
        salt=salt,
        spin_count=100_000,
        algorithm="SHA-512",
    )
    assert s == "AAECAwQFBgcICQoLDA0ODw=="
    assert h == (
        "h+JK5c0EbDUYLc54uJieGZTYMPfRl0E7nQouVOOcgG7h+YRrDPzi"
        "AHTiwuuIyxILVDS54ceeYWm4kkMntgKiqw=="
    )


def test_sha512_known_vector_1k_spins() -> None:
    """Same plaintext + salt with a small spin count for fast tests."""
    salt = bytes(range(16))
    h, _ = hash_password_sha512(
        "hunter2",
        salt=salt,
        spin_count=1000,
        algorithm="SHA-512",
    )
    assert h == (
        "lPbPmAvb9B0r7XnDW8sxxsybKibpRLbRiHLhn+Za7uwNanDZfVjR"
        "ftdq9tQfLDEdZMMUHQZ3TZavTSATeZMXmA=="
    )


def test_verify_password_round_trip_succeeds_with_correct_plaintext() -> None:
    salt = bytes(range(16))
    h, s = hash_password_sha512("seekrit", salt=salt, spin_count=1000)
    assert verify_password_sha512("seekrit", h, s, spin_count=1000) is True
    assert verify_password_sha512("wrong", h, s, spin_count=1000) is False


def test_verify_password_round_trip_with_random_salt() -> None:
    """Random-salt case: same plaintext still round-trips because salt
    is captured in the returned base64 string."""
    h, s = hash_password_sha512("seekrit", spin_count=1000)
    assert verify_password_sha512("seekrit", h, s, spin_count=1000) is True
