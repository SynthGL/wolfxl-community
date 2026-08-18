"""Structural-op stub tests.

Pin the contract for the structural ops that openpyxl exposes but wolfxl
has not yet implemented. Until the corresponding RFCs ship, each call
must raise ``NotImplementedError`` with a message that points at the
right RFC.

RFC-035 ships in 1.1 — ``copy_worksheet`` now works in modify mode (see
``test_copy_worksheet_smoke.py``). The write-mode path is still tracked
as a stub raising ``NotImplementedError`` per RFC-035 §3 OQ-a.

RFC-036 (``Workbook.move_sheet``), RFC-034 (``Worksheet.move_range``),
and RFC-030 / 031 (``insert_rows`` / ``delete_rows`` / ``insert_cols``
/ ``delete_cols``) all shipped in WolfXL 1.1.
"""

from __future__ import annotations

import pytest

import wolfxl

# All worksheet-level structural-op stubs have shipped (RFC-030, 031, 034).
WORKSHEET_STUBS: list[tuple[str, tuple, str]] = []

# RFC-035 ships in 1.1 — copy_worksheet now works in modify mode.
# Write-mode is still stubbed pending RFC-035 §3 OQ-a follow-up;
# coverage for that path lives in test_copy_worksheet_smoke.py.
WORKBOOK_STUBS: list[tuple[str, str]] = []


def _fresh_active() -> tuple[wolfxl.Workbook, wolfxl.Worksheet]:
    """Return ``(workbook, active_sheet)`` with a non-None active sheet."""
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    return wb, ws


@pytest.mark.parametrize(("method", "args", "rfc"), WORKSHEET_STUBS)
def test_worksheet_stub_raises_with_rfc_pointer(
    method: str, args: tuple, rfc: str
) -> None:
    _wb, ws = _fresh_active()
    fn = getattr(ws, method)
    with pytest.raises(NotImplementedError, match=rfc):
        fn(*args)


@pytest.mark.parametrize(("method", "_rfc"), WORKBOOK_STUBS)
def test_workbook_stubs_mention_workaround(method: str, _rfc: str) -> None:
    """Every stub message should include the openpyxl workaround pointer."""
    wb, ws = _fresh_active()
    fn = getattr(wb, method)
    args: tuple = (ws,) if method == "copy_worksheet" else (ws, 1)
    with pytest.raises(NotImplementedError, match="wolfxl.load_workbook"):
        fn(*args)


@pytest.mark.parametrize(("method", "args", "_rfc"), WORKSHEET_STUBS)
def test_worksheet_stubs_mention_workaround(
    method: str, args: tuple, _rfc: str
) -> None:
    _wb, ws = _fresh_active()
    fn = getattr(ws, method)
    with pytest.raises(NotImplementedError, match="wolfxl.load_workbook"):
        fn(*args)
