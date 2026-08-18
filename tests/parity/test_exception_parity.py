"""RFC-059 §4 (Sprint Ο Pod-1E): exception type-name parity.

Wolfxl's typed exceptions mirror openpyxl's by name but do
**not** subclass openpyxl's hierarchy — the classes are
independent.  These tests pin the contract:

1. The wolfxl class names match openpyxl's spelling.
2. ``IllegalCharacterError`` and ``CellCoordinatesException``
   subclass :class:`ValueError` (matches openpyxl).
3. ``InvalidFileException``, ``ReadOnlyWorkbookException``, and
   ``WorkbookAlreadySaved`` are plain :class:`Exception`
   (matches openpyxl).
4. ``isinstance(e, openpyxl.X)`` is False (independence).

If openpyxl is not installed, the comparison cases skip — the
naming/structure assertions still run.
"""

from __future__ import annotations

import pytest

from wolfxl.utils import exceptions as wolf_exc


def test_class_names_match_openpyxl_spelling() -> None:
    """The five public type names must match openpyxl exactly."""
    expected = {
        "InvalidFileException",
        "IllegalCharacterError",
        "CellCoordinatesException",
        "ReadOnlyWorkbookException",
        "WorkbookAlreadySaved",
    }
    actual = {name for name in dir(wolf_exc) if not name.startswith("_")}
    missing = expected - actual
    assert not missing, f"missing exception types: {missing}"


def test_value_error_subclasses_match_openpyxl_contract() -> None:
    """``IllegalCharacterError`` and ``CellCoordinatesException``
    subclass :class:`ValueError`; the rest are plain
    :class:`Exception`."""
    assert issubclass(wolf_exc.IllegalCharacterError, ValueError)
    assert issubclass(wolf_exc.CellCoordinatesException, ValueError)
    assert not issubclass(wolf_exc.InvalidFileException, ValueError)
    assert not issubclass(wolf_exc.ReadOnlyWorkbookException, ValueError)
    assert not issubclass(wolf_exc.WorkbookAlreadySaved, ValueError)


def test_isinstance_against_openpyxl_is_false() -> None:
    """Wolfxl's classes are independent — an instance of
    ``wolfxl.utils.exceptions.IllegalCharacterError`` is NOT an
    instance of ``openpyxl.utils.exceptions.IllegalCharacterError``."""
    openpyxl_exc = pytest.importorskip("openpyxl.utils.exceptions")
    e = wolf_exc.IllegalCharacterError("x")
    assert not isinstance(e, openpyxl_exc.IllegalCharacterError)


def test_openpyxl_class_names_align() -> None:
    """The class *names* match openpyxl 1:1 even though the types
    are distinct — supports drop-in import migration."""
    openpyxl_exc = pytest.importorskip("openpyxl.utils.exceptions")
    for name in (
        "InvalidFileException",
        "IllegalCharacterError",
        "CellCoordinatesException",
        "ReadOnlyWorkbookException",
        "WorkbookAlreadySaved",
    ):
        assert hasattr(openpyxl_exc, name), (
            f"openpyxl missing {name}; parity drift"
        )
        assert hasattr(wolf_exc, name)


def test_value_error_subclassing_is_intentionally_wider_than_openpyxl() -> None:
    """Wolfxl deliberately subclasses :class:`ValueError` for the
    two coordinate-style exceptions even when openpyxl doesn't.

    Background: wolfxl previously raised generic ``ValueError`` at
    these sites, so existing user code does ``except ValueError``.
    Subclassing keeps that backward-compat working.  The
    name-level migration target (``except
    IllegalCharacterError``) is unaffected.
    """
    openpyxl_exc = pytest.importorskip("openpyxl.utils.exceptions")
    # Wolfxl's contract: both coordinate-style types subclass
    # ValueError so existing 'except ValueError' callsites keep
    # working.  This is intentionally wider than openpyxl's
    # contract on the same names.
    assert issubclass(wolf_exc.IllegalCharacterError, ValueError)
    assert issubclass(wolf_exc.CellCoordinatesException, ValueError)
    # Plain-Exception types match openpyxl's contract directly.
    for name in (
        "InvalidFileException",
        "ReadOnlyWorkbookException",
        "WorkbookAlreadySaved",
    ):
        wolf_cls = getattr(wolf_exc, name)
        op_cls = getattr(openpyxl_exc, name)
        assert issubclass(wolf_cls, ValueError) == issubclass(
            op_cls, ValueError
        ), f"{name}: ValueError-subclass mismatch vs openpyxl"
