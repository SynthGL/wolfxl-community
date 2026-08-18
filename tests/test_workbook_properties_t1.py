"""T1 PR3 — DocumentProperties read from docProps/core.xml."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from wolfxl.packaging.core import DocumentProperties

from wolfxl import Workbook

openpyxl = pytest.importorskip("openpyxl")


@pytest.fixture()
def workbook_with_props(tmp_path: Path) -> Path:
    path = tmp_path / "metadata.xlsx"
    wb = openpyxl.Workbook()
    wb.properties.title = "Q3 Report"
    wb.properties.creator = "Alice"
    wb.properties.subject = "Revenue"
    wb.properties.description = "Quarterly revenue snapshot"
    wb.properties.keywords = "revenue, q3, 2024"
    wb.properties.lastModifiedBy = "Bob"
    wb.save(path)
    return path


def test_properties_round_trip(workbook_with_props: Path) -> None:
    wb = Workbook._from_reader(str(workbook_with_props))
    props = wb.properties
    assert isinstance(props, DocumentProperties)
    assert props.title == "Q3 Report"
    assert props.creator == "Alice"
    assert props.subject == "Revenue"
    assert props.description == "Quarterly revenue snapshot"
    assert props.keywords == "revenue, q3, 2024"
    assert props.lastModifiedBy == "Bob"
    # created/modified are datetimes (parsed from ISO 8601).
    assert props.created is None or isinstance(props.created, datetime)
    assert props.modified is None or isinstance(props.modified, datetime)


def test_properties_empty_in_write_mode() -> None:
    """A fresh Workbook() has no metadata — every field is None."""
    wb = Workbook()
    props = wb.properties
    assert isinstance(props, DocumentProperties)
    assert props.title is None
    assert props.creator is None
    assert props.created is None


def test_properties_mutable_in_write_mode() -> None:
    """Users set metadata on a fresh workbook via attribute assignment."""
    wb = Workbook()
    wb.properties.title = "My Report"
    wb.properties.creator = "Me"
    assert wb.properties.title == "My Report"
    assert wb.properties.creator == "Me"


def test_properties_cached_across_calls(workbook_with_props: Path) -> None:
    """wb.properties returns the same object each call (not a rebuild)."""
    wb = Workbook._from_reader(str(workbook_with_props))
    p1 = wb.properties
    p2 = wb.properties
    assert p1 is p2


def test_properties_setter_replaces_wholesale() -> None:
    wb = Workbook()
    wb.properties = DocumentProperties(title="Replaced", creator="X")
    assert wb.properties.title == "Replaced"
    assert wb.properties.creator == "X"
    assert wb._properties_dirty is True
