"""W4E.P5 regression: ``Hyperlink.is_internal`` is the source-of-truth flag.

Before the fix the emitter used ``target.starts_with('#')`` to decide
internal vs external. That worked for the happy path but had a footgun:
any caller that explicitly set ``internal=False`` while passing a
``target`` of ``"#anchor"`` (or just any payload that started with ``#``)
would be silently re-routed to the internal-location code path,
swallowing the relationship and producing a broken external link.

The fix moves routing to an explicit ``is_internal: bool`` field. These
tests pin the new contract on the native writer:

1. URLs with ``#`` fragments stay external (the canonical bug example).
2. ``internal=True`` produces a ``location=`` attribute and zero rels.
3. ``internal=False`` produces an ``r:id=`` attribute and one external
   relationship.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest


def _save_hyperlink(
    tmp_path: Path, payload: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    monkeypatch.setenv("WOLFXL_TEST_EPOCH", "0")
    import wolfxl
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.cell(row=1, column=1, value="probe")
    wb._rust_writer.add_hyperlink(ws.title, payload)
    out = tmp_path / "out.xlsx"
    wb.save(str(out))
    return out


def _read_part(path: Path, name: str) -> str:
    with zipfile.ZipFile(path) as zf:
        return zf.read(name).decode("utf-8")


def test_fragment_url_stays_external_native(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``https://example.com/page#section`` — ``#`` is mid-string. Even if
    the caller forgot ``internal=False`` (it defaults to false anyway), the
    URL must round-trip as an external relationship, not a sheet location."""
    out = _save_hyperlink(
        tmp_path,
        {
            "cell": "A1",
            "target": "https://example.com/page#section",
            "display": "Frag URL",
        },
        monkeypatch,
    )
    sheet = _read_part(out, "xl/worksheets/sheet1.xml")
    rels = _read_part(out, "xl/worksheets/_rels/sheet1.xml.rels")
    assert "r:id=" in sheet, f"expected external r:id in sheet1: {sheet[:500]}"
    assert "location=" not in sheet, (
        f"unexpected location attr (URL fragment misclassified): {sheet[:500]}"
    )
    assert "https://example.com/page#section" in rels, (
        f"external rel missing from rels:\n{rels[:500]}"
    )
    assert 'TargetMode="External"' in rels


def test_internal_target_uses_location(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``internal=True`` -> ``<hyperlink location="Sheet1!B2"/>`` with
    no relationship. Caller may pass ``Sheet1!B2`` or ``#Sheet1!B2`` —
    both forms are accepted and emit identically."""
    out = _save_hyperlink(
        tmp_path,
        {"cell": "A1", "target": "Sheet!B2", "internal": True},
        monkeypatch,
    )
    sheet = _read_part(out, "xl/worksheets/sheet1.xml")
    assert 'location="Sheet!B2"' in sheet, (
        f"expected location attr: {sheet[:500]}"
    )
    assert "r:id=" not in sheet, f"unexpected r:id for internal: {sheet[:500]}"
    # No external rels file (or empty if it exists).
    try:
        rels = _read_part(out, "xl/worksheets/_rels/sheet1.xml.rels")
    except KeyError:
        rels = ""
    assert "hyperlink" not in rels.lower(), (
        f"internal link should not produce external rel:\n{rels[:500]}"
    )


def test_internal_target_strips_legacy_hash_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backwards-compat: callers passing ``internal=True`` with a stray
    ``#`` prefix on the target — the convention under the old prefix-
    sniffing implementation — still work. The pyclass strips the leading
    ``#`` before storing in the model."""
    out = _save_hyperlink(
        tmp_path,
        {"cell": "A1", "target": "#Sheet!C3", "internal": True},
        monkeypatch,
    )
    sheet = _read_part(out, "xl/worksheets/sheet1.xml")
    assert 'location="Sheet!C3"' in sheet, (
        f"expected stripped location attr: {sheet[:500]}"
    )
    assert "#Sheet" not in sheet, (
        f"raw # prefix leaked into output: {sheet[:500]}"
    )
