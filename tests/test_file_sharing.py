"""RFC-058 §3 — ``FileSharing`` class.

Pure-Python coverage of the FileSharing container: defaults, the
reservation password setter, and dict serialisation.
"""

from __future__ import annotations

from wolfxl.workbook.protection import FileSharing


def test_default_construction_is_off() -> None:
    fs = FileSharing()
    assert fs.read_only_recommended is None
    assert fs.user_name is None
    assert fs.reservation_password is None
    assert fs.hash_value is None


def test_kwargs_set_visible_fields() -> None:
    fs = FileSharing(read_only_recommended=True, user_name="alice")
    assert fs.read_only_recommended is True
    assert fs.user_name == "alice"
    assert fs.reservation_password is None  # not yet hashed


def test_set_reservation_password_populates_hash_fields() -> None:
    fs = FileSharing()
    fs.set_reservation_password("alice-pw")
    assert fs.algorithm_name == "SHA-512"
    assert fs.hash_value is not None
    assert fs.salt_value is not None
    assert fs.spin_count == 100_000
    # Legacy short-hash on reservation_password (matches openpyxl).
    assert fs.reservation_password is not None
    assert fs.reservation_password != "alice-pw"


def test_check_reservation_password_round_trip() -> None:
    fs = FileSharing()
    fs.set_reservation_password("alice-pw")
    assert fs.check_reservation_password("alice-pw") is True
    assert fs.check_reservation_password("bob-pw") is False


def test_constructor_reservation_password_stores_openpyxl_hash() -> None:
    fs = FileSharing(reservation_password="ABCD")
    assert fs.reservation_password == "ABCD"
    assert fs.hash_value is None


def test_to_dict_returns_six_keys() -> None:
    fs = FileSharing(read_only_recommended=True, user_name="alice")
    fs.set_reservation_password("pw")
    d = fs.to_dict()
    assert set(d) == {
        "read_only_recommended",
        "user_name",
        "reservation_password",
        "algorithm_name",
        "hash_value",
        "salt_value",
        "spin_count",
    }
    assert d["read_only_recommended"] is True
    assert d["user_name"] == "alice"
    assert d["algorithm_name"] == "SHA-512"
    assert d["spin_count"] == 100_000
