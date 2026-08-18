"""Password hashing helpers — RFC-058 + RFC-055 (workbook + sheet security).

Two algorithms live side-by-side:

* :func:`hash_password` — the legacy XOR-based 16-bit hash that openpyxl
  emits as the ``password=`` attribute on ``<sheetProtection>``,
  ``<workbookProtection>``, ``<fileSharing reservationPassword>``, etc.
  Implementation is byte-for-byte identical to openpyxl 3.1.x's
  ``openpyxl.utils.protection.hash_password`` so round-trip parity tests
  pass without divergence.

* :func:`hash_password_sha512` — the modern ECMA-376 spin-hash algorithm
  used by ``hashValue`` / ``saltValue`` / ``spinCount`` /
  ``algorithmName`` attribute groups (Excel 2013+ defaults). Returns
  base64-encoded ``(hash, salt)`` so callers can plug them into the
  Office hash-block attributes.

The legacy hash function is a straight port of openpyxl's algorithm,
released under its MIT license. The SHA-512 helper is original.
"""

from __future__ import annotations

import base64
import hashlib
import os


# ---------------------------------------------------------------------------
# Legacy 16-bit XOR hash (openpyxl-compatible)
# ---------------------------------------------------------------------------


def hash_password(plaintext_password: str = "") -> str:
    """Compute the legacy ECMA-376 16-bit hash of ``plaintext_password``.

    Returns an uppercase hex string with no ``0x`` prefix. Empty input
    returns ``""`` so callers can use the result directly as
    ``password=...`` attribute value where "no password" is the literal
    empty string. The algorithm matches openpyxl 3.1.x's
    ``openpyxl.utils.protection.hash_password`` byte-for-byte for
    non-empty input (e.g. ``"hunter2"`` → ``"C258"``).

    See http://blogs.msdn.com/b/ericwhite/archive/2008/02/23/the-legacy-hashing-algorithm-in-open-xml.aspx
    for the algorithm rationale.
    """
    password = 0x0000
    for idx, char in enumerate(plaintext_password, 1):
        value = ord(char) << idx
        rotated_bits = value >> 15
        value &= 0x7FFF
        password ^= value | rotated_bits
    password ^= len(plaintext_password)
    password ^= 0xCE4B
    return str(hex(password)).upper()[2:]


def check_password(plaintext: str, expected_hash: str) -> bool:
    """Verify ``plaintext`` matches a previously-stored legacy hash.

    Returns False on empty/None input regardless of the stored hash —
    "no password supplied" never matches a stored protection.
    """
    if not plaintext:
        return False
    return hash_password(plaintext) == (expected_hash or "").upper()


# ---------------------------------------------------------------------------
# Modern SHA-512 spin-hash (ECMA-376 §22.4.3.2)
# ---------------------------------------------------------------------------


_SUPPORTED_ALGORITHMS = {
    "SHA-512": hashlib.sha512,
    "SHA-384": hashlib.sha384,
    "SHA-256": hashlib.sha256,
    "SHA-1": hashlib.sha1,
}


def hash_password_sha512(
    plaintext: str,
    *,
    salt: bytes | None = None,
    spin_count: int = 100_000,
    algorithm: str = "SHA-512",
) -> tuple[str, str]:
    """Compute the modern ECMA-376 spin-hash of ``plaintext``.

    Returns ``(hash_b64, salt_b64)`` where each value is base64 encoded
    and ready to plug into ``hashValue``/``saltValue`` attributes.

    The algorithm follows ECMA-376 Part 1 §22.4.3.2 (Office Open XML
    encryption):

      1. ``H₀ = sha(salt || password_utf16le)``
      2. For ``i ∈ [0, spin_count)``: ``Hᵢ₊₁ = sha(Hᵢ || iter_le32(i))``
      3. Final hash is ``H_{spin_count}``.

    ``salt`` defaults to a fresh 16 random bytes from :func:`os.urandom`.
    Pass an explicit ``salt`` to make the output deterministic for
    fixture tests.

    Raises ``ValueError`` for an unknown algorithm or a non-positive
    ``spin_count``.
    """
    if algorithm not in _SUPPORTED_ALGORITHMS:
        raise ValueError(
            f"Unsupported algorithm {algorithm!r}; "
            f"supported: {sorted(_SUPPORTED_ALGORITHMS)}"
        )
    if spin_count <= 0:
        raise ValueError(f"spin_count must be positive, got {spin_count}")

    if salt is None:
        salt = os.urandom(16)
    if not isinstance(salt, (bytes, bytearray, memoryview)):
        raise TypeError("salt must be bytes-like")
    salt_bytes = bytes(salt)

    sha = _SUPPORTED_ALGORITHMS[algorithm]
    h = sha(salt_bytes + plaintext.encode("utf-16-le")).digest()
    for i in range(spin_count):
        h = sha(h + i.to_bytes(4, "little")).digest()

    return base64.b64encode(h).decode("ascii"), base64.b64encode(salt_bytes).decode("ascii")


def verify_password_sha512(
    plaintext: str,
    hash_value: str,
    salt_value: str,
    *,
    spin_count: int = 100_000,
    algorithm: str = "SHA-512",
) -> bool:
    """Return ``True`` iff ``plaintext`` round-trips against ``hash_value``.

    ``hash_value`` and ``salt_value`` must be base64 strings as produced
    by :func:`hash_password_sha512`. ``spin_count`` and ``algorithm``
    must match the values used at hash time.
    """
    salt = base64.b64decode(salt_value)
    expected, _ = hash_password_sha512(
        plaintext,
        salt=salt,
        spin_count=spin_count,
        algorithm=algorithm,
    )
    return expected == hash_value


__all__ = [
    "hash_password",
    "check_password",
    "hash_password_sha512",
    "verify_password_sha512",
]
