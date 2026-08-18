"""RFC-058 §3 — ``WorkbookProtection`` class.

Pure-Python coverage of the WorkbookProtection container: field
defaults, password setters/getters, the SHA-512 spin hash round-trip,
and the §10 dict serialisation. End-to-end save-time XML coverage
lives in :mod:`tests.parity.test_workbook_security_parity`.
"""

from __future__ import annotations

import base64

import pytest
from wolfxl.workbook.protection import WorkbookProtection


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_default_construction_has_all_locks_off() -> None:
    wp = WorkbookProtection()
    assert wp.lock_structure is None
    assert wp.lock_windows is None
    assert wp.lock_revision is None
    assert wp.workbook_password is None
    assert wp.workbook_hash_value is None
    assert wp.revisions_password is None
    assert wp.revisions_hash_value is None


def test_kwargs_set_lock_flags() -> None:
    wp = WorkbookProtection(
        lock_structure=True,
        lock_windows=True,
        lock_revision=True,
    )
    assert wp.lock_structure is True
    assert wp.lock_windows is True
    assert wp.lock_revision is True


def test_camel_case_kwargs_match_snake_case() -> None:
    snake = WorkbookProtection(
        workbook_password="seekrit",
        lock_structure=True,
        lock_windows=True,
        lock_revision=True,
    )
    camel = WorkbookProtection(
        workbookPassword="seekrit",
        lockStructure=True,
        lockWindows=True,
        lockRevision=True,
    )
    assert snake.lock_structure is camel.lock_structure is True
    assert snake.lock_windows is camel.lock_windows is True
    assert snake.lock_revision is camel.lock_revision is True
    assert snake.check_workbook_password("seekrit") is True
    assert camel.check_workbook_password("seekrit") is True


def test_camel_case_properties_alias_snake_case() -> None:
    wp = WorkbookProtection(lock_structure=True)
    assert wp.lockStructure is True
    wp.lockStructure = False
    assert wp.lock_structure is False
    wp.workbookPassword = "ABCD"
    assert wp.workbook_password == "ABCD"


# ---------------------------------------------------------------------------
# Workbook password
# ---------------------------------------------------------------------------


def test_set_workbook_password_matches_openpyxl_legacy_hash_default() -> None:
    wp = WorkbookProtection()
    wp.set_workbook_password("hunter2")
    assert wp.workbook_password == "C258"
    assert wp.workbook_algorithm_name is None
    assert wp.workbook_hash_value is None
    assert wp.workbook_salt_value is None
    assert wp.workbook_spin_count is None


def test_check_workbook_password_round_trip_correct() -> None:
    wp = WorkbookProtection()
    wp.set_workbook_password("hunter2")
    assert wp.check_workbook_password("hunter2") is True


def test_check_workbook_password_rejects_wrong() -> None:
    wp = WorkbookProtection()
    wp.set_workbook_password("hunter2")
    assert wp.check_workbook_password("guess") is False
    assert wp.check_workbook_password("") is False


def test_check_workbook_password_returns_false_when_unset() -> None:
    wp = WorkbookProtection()
    assert wp.check_workbook_password("anything") is False


def test_constructor_workbook_password_routes_through_setter() -> None:
    wp = WorkbookProtection(workbook_password="seekrit")
    assert wp.workbook_password is not None
    assert wp.workbook_password != "seekrit"
    assert wp.check_workbook_password("seekrit") is True


# ---------------------------------------------------------------------------
# Revisions password
# ---------------------------------------------------------------------------


def test_set_revisions_password_round_trip() -> None:
    wp = WorkbookProtection()
    wp.set_revisions_password("review-only")
    assert wp.revisions_password is not None
    assert wp.revisions_algorithm_name is None
    assert wp.revisions_spin_count is None
    assert wp.check_revisions_password("review-only") is True
    assert wp.check_revisions_password("wrong") is False


def test_two_passwords_independent() -> None:
    wp = WorkbookProtection()
    wp.set_workbook_password("structure-pw")
    wp.set_revisions_password("revisions-pw")
    assert wp.check_workbook_password("structure-pw") is True
    assert wp.check_workbook_password("revisions-pw") is False
    assert wp.check_revisions_password("revisions-pw") is True
    assert wp.check_revisions_password("structure-pw") is False


# ---------------------------------------------------------------------------
# §10 dict serialisation
# ---------------------------------------------------------------------------


def test_to_dict_returns_full_shape() -> None:
    wp = WorkbookProtection(
        lock_structure=True,
        lock_windows=True,
        workbook_password="hunter2",
    )
    d = wp.to_dict()
    expected_keys = {
        "lock_structure",
        "lock_windows",
        "lock_revision",
        "workbook_password",
        "workbook_password_character_set",
        "workbook_algorithm_name",
        "workbook_hash_value",
        "workbook_salt_value",
        "workbook_spin_count",
        "revisions_password",
        "revisions_password_character_set",
        "revisions_algorithm_name",
        "revisions_hash_value",
        "revisions_salt_value",
        "revisions_spin_count",
    }
    assert set(d) == expected_keys
    assert d["lock_structure"] is True
    assert d["lock_windows"] is True
    assert d["lock_revision"] is False
    assert d["workbook_password"] is not None
    assert d["workbook_algorithm_name"] is None
    assert d["workbook_spin_count"] is None


def test_to_dict_empty_protection_has_none_hash_fields() -> None:
    wp = WorkbookProtection(lock_structure=True)
    d = wp.to_dict()
    assert d["workbook_algorithm_name"] is None
    assert d["workbook_hash_value"] is None
    assert d["workbook_salt_value"] is None
    assert d["workbook_spin_count"] is None
    assert d["lock_structure"] is True


# ---------------------------------------------------------------------------
# Custom spin count / salt for fixture tests
# ---------------------------------------------------------------------------


def test_custom_spin_count_and_explicit_salt_are_deterministic() -> None:
    salt = b"\x00" * 16
    wp1 = WorkbookProtection()
    wp1.set_workbook_password("pw", salt=salt, spin_count=1000)
    wp2 = WorkbookProtection()
    wp2.set_workbook_password("pw", salt=salt, spin_count=1000)
    # Same plaintext + same salt + same spin count ⇒ same hash bytes.
    assert wp1.workbook_hash_value == wp2.workbook_hash_value
    assert wp1.workbook_salt_value == wp2.workbook_salt_value
    assert wp1.workbook_spin_count == 1000
    base64.b64decode(wp1.workbook_hash_value)  # raises if bad
    base64.b64decode(wp1.workbook_salt_value)
    # The check still works with the custom spin count round-trip.
    assert wp1.check_workbook_password("pw") is True


def test_unsupported_algorithm_raises_value_error() -> None:
    wp = WorkbookProtection()
    with pytest.raises(ValueError, match="Unsupported algorithm"):
        wp.set_workbook_password("pw", algorithm="MD5")
