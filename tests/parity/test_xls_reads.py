"""Sprint Κ Pod-γ — legacy ``.xls`` read parity vs ``pandas + calamine``.

Mirrors ``test_xlsb_reads.py`` but for BIFF8 ``.xls`` files generated via
LibreOffice headless from openpyxl-built source xlsx fixtures.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import wolfxl

pd = pytest.importorskip("pandas")
pytest.importorskip("python_calamine")

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "xls"


def _all_fixtures() -> list[Path]:
    return sorted(FIXTURES_DIR.glob("*.xls"))


_FIXTURES = _all_fixtures()


pytestmark = pytest.mark.skipif(
    not _FIXTURES,
    reason="No .xls fixtures present (Sprint Κ Pod-γ)",
)


def _coerce(v: object) -> object:
    import datetime as _dt

    if v is None:
        return None
    if isinstance(v, float) and v != v:  # NaN  # noqa: PLR0124
        return None
    # See test_xlsb_reads._coerce — time-only cells diverge between
    # wolfxl (datetime with epoch root) and pandas+calamine (datetime.time).
    if isinstance(v, _dt.datetime) and v.year < 1901:
        return v.time()
    return v


@pytest.mark.parametrize("fixture", _FIXTURES, ids=lambda p: p.name)
def test_xls_values_match_pandas_calamine(fixture: Path) -> None:
    """wolfxl.load_workbook reads same cell values as pandas+calamine.

    ``data_only=True`` matches pandas+calamine's behaviour, which
    returns cached formula results rather than formula strings.
    """
    wb = wolfxl.load_workbook(str(fixture), data_only=True)
    df = pd.read_excel(
        str(fixture), engine="calamine", sheet_name=None, header=None,
    )

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        if sheet_name not in df:
            assert all(
                cell.value is None
                for row in ws.iter_rows()
                for cell in row
            ), f"{fixture.name}: {sheet_name!r} unique to wolfxl with content"
            continue

        df_sheet = df[sheet_name]
        for row in ws.iter_rows():
            for cell in row:
                cv = _coerce(cell.value)
                if cv is None:
                    continue
                if (cell.row - 1) >= df_sheet.shape[0]:
                    continue
                if (cell.column - 1) >= df_sheet.shape[1]:
                    continue
                df_value = _coerce(df_sheet.iat[cell.row - 1, cell.column - 1])
                if df_value is None:
                    continue
                if isinstance(cv, (int, float)) and isinstance(
                    df_value, (int, float)
                ):
                    assert abs(float(cv) - float(df_value)) < 1e-9, (
                        f"{fixture.name}!{sheet_name}!{cell.coordinate}: "
                        f"wolfxl={cv} pandas={df_value}"
                    )
                else:
                    assert cv == df_value or str(cv) == str(df_value), (
                        f"{fixture.name}!{sheet_name}!{cell.coordinate}: "
                        f"wolfxl={cv!r} pandas={df_value!r}"
                    )


def test_xls_modify_raises() -> None:
    fixture = _FIXTURES[0]
    with pytest.raises(NotImplementedError, match="transcribe"):
        wolfxl.load_workbook(str(fixture), modify=True)


def test_xls_read_only_raises() -> None:
    fixture = _FIXTURES[0]
    with pytest.raises(NotImplementedError, match="xlsx-only"):
        wolfxl.load_workbook(str(fixture), read_only=True)


def test_xls_password_raises() -> None:
    fixture = _FIXTURES[0]
    with pytest.raises(NotImplementedError, match="xlsx-only"):
        wolfxl.load_workbook(str(fixture), password="anything")


def test_xls_cell_font_raises() -> None:
    fixture = _FIXTURES[0]
    wb = wolfxl.load_workbook(str(fixture))
    ws = wb.active
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is not None:
                with pytest.raises(NotImplementedError, match="xlsx-only"):
                    _ = cell.font
                return
    pytest.fail("no non-empty cells in fixture")


def test_xls_from_bytes() -> None:
    fixture = _FIXTURES[0]
    data = fixture.read_bytes()
    wb_bytes = wolfxl.load_workbook(data)
    wb_path = wolfxl.load_workbook(str(fixture))
    assert wb_bytes.sheetnames == wb_path.sheetnames


def test_xls_classify_format() -> None:
    """``wolfxl.classify_file_format`` reports 'xls' for this fixture
    both as a path and as bytes.

    Note: ``wolfxl.classify_format`` (without ``_file_``) is the
    SynthGL number-format archetype classifier; the file-format
    detector is the separate ``classify_file_format`` symbol.
    """
    fixture = _FIXTURES[0]
    fmt_path = wolfxl.classify_file_format(str(fixture))
    assert fmt_path == "xls", f"path -> {fmt_path!r}"
    fmt_bytes = wolfxl.classify_file_format(fixture.read_bytes())
    assert fmt_bytes == "xls", f"bytes -> {fmt_bytes!r}"
