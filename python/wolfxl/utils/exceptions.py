"""Public exception types — openpyxl-shaped hierarchy.

User code that catches openpyxl's typed exceptions (notably
``IllegalCharacterError`` and ``CellCoordinatesException``) needs
the same names from wolfxl when migrating.  We mirror openpyxl's
type names but **do not** subclass openpyxl's hierarchy — the
classes are independent.  Both ``IllegalCharacterError`` and
``CellCoordinatesException`` subclass :class:`ValueError` so
existing ``except ValueError`` callsites keep working unchanged.

The internal raise sites (``utils/cell.py``,
``wolfxl.load_workbook``, the cell value setter) chain via
``raise X(msg) from e`` so the original cause is preserved on
``__cause__`` for callers that introspect it.

Reference: ``openpyxl.utils.exceptions`` (openpyxl 3.1.x).
"""

from __future__ import annotations

import builtins
from typing import Any

try:
    from wolfxl._compat import _REAL_OPENPYXL
except Exception:  # noqa: BLE001 - fallback during unusual bootstrap paths
    _REAL_OPENPYXL = None


def _openpyxl_exception_base(name: str, fallback: type[BaseException]) -> type[BaseException]:
    exceptions_module: Any = getattr(getattr(_REAL_OPENPYXL, "utils", None), "exceptions", None)
    candidate = getattr(exceptions_module, name, None)
    return candidate if isinstance(candidate, type) else fallback


def _coordinate_exception_bases() -> tuple[type[BaseException], ...]:
    upstream = _openpyxl_exception_base("CellCoordinatesException", ValueError)
    if upstream is ValueError:
        return (ValueError,)
    return (ValueError, upstream)


class InvalidFileException(Exception):
    """Raised when :func:`wolfxl.load_workbook` is asked to open
    something that isn't a valid xlsx / xlsb / xls / encrypted
    OOXML file.

    The format detector looks at leading magic bytes; anything
    that doesn't match a known archetype surfaces as this
    exception.  Mirrors openpyxl's
    ``openpyxl.utils.exceptions.InvalidFileException``.

    Note: this is a plain :class:`Exception`, not a
    :class:`ValueError` — openpyxl's contract is the same.
    Existing wolfxl callsites that previously raised generic
    ``ValueError`` for unknown file formats are rewrapped to this
    type with ``from`` chaining for backward compatibility.
    """


class IllegalCharacterError(ValueError):
    """Raised when a cell value contains characters illegal in
    OOXML strings.

    The OOXML spec rejects the C0 control characters
    ``\\x00`` – ``\\x08``, ``\\x0B``, ``\\x0C``, ``\\x0E`` –
    ``\\x1F``, plus ``\\x7F``.  Tab (``\\x09``), newline
    (``\\x0A``), and carriage return (``\\x0D``) are allowed.
    Surrogates are also rejected because Excel's serializer
    cannot round-trip them.

    Subclasses :class:`ValueError` so callers using ``except
    ValueError`` continue to function — code that wants the more
    specific type can switch to ``except IllegalCharacterError``.
    Mirrors openpyxl's
    ``openpyxl.utils.exceptions.IllegalCharacterError``.
    """


class CellCoordinatesException(*_coordinate_exception_bases()):
    """Raised when an invalid coordinate or range string is
    parsed (e.g. ``"AAAA1"``, ``"A0"``, ``"A1:"``).

    Triggered by the
    :func:`wolfxl.utils.cell.coordinate_to_tuple`,
    :func:`wolfxl.utils.cell.range_boundaries`, and
    :func:`wolfxl.utils.cell.column_index_from_string` parsers.

    Subclasses :class:`ValueError` so existing callsites that
    catch :class:`ValueError` are unaffected.  Mirrors openpyxl's
    ``openpyxl.utils.exceptions.CellCoordinatesException``.
    """


_cached_cell_coordinates_exception = getattr(
    builtins,
    "_wolfxl_CellCoordinatesException",
    None,
)
if isinstance(_cached_cell_coordinates_exception, type):
    CellCoordinatesException = _cached_cell_coordinates_exception
else:
    builtins._wolfxl_CellCoordinatesException = CellCoordinatesException


class ReadOnlyWorkbookException(Exception):
    """Raised when user code tries to mutate a workbook that was
    opened with ``read_only=True``.

    Wolfxl's read-only mode (Sprint Ι Pod-β) returns immutable
    cell proxies — assigning to ``cell.value`` raises this type.
    Mirrors openpyxl's
    ``openpyxl.utils.exceptions.ReadOnlyWorkbookException``.

    Note: kept as a plain :class:`Exception` (not
    :class:`RuntimeError`) for openpyxl name parity even though
    wolfxl's existing read-only setter raises ``RuntimeError``
    today.  Future patches may transition the read-only setter
    to raise this type directly.
    """


class WorkbookAlreadySaved(Exception):
    """Raised when :meth:`Workbook.save` is called twice on a
    write-only workbook.

    Wolfxl doesn't expose a separate write-only mode (the native
    writer streams internally), but the type exists for
    drop-in-import parity with openpyxl's
    ``openpyxl.utils.exceptions.WorkbookAlreadySaved``.  User
    code that catches this exception can be migrated unchanged.
    """


class NamedRangeException(Exception):
    """Compatibility name retained from openpyxl's exception surface."""


class SheetTitleException(Exception):
    """Raised for invalid worksheet title operations."""


__all__ = [
    "CellCoordinatesException",
    "IllegalCharacterError",
    "InvalidFileException",
    "NamedRangeException",
    "ReadOnlyWorkbookException",
    "SheetTitleException",
    "WorkbookAlreadySaved",
]
