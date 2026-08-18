"""W4E.P4 regression: ``contentStatus`` round-trips through the native writer.

Before W4E.P4 the native writer silently dropped ``contentStatus`` because
``DocProperties`` had no field for it. The fix adds
``DocProperties.content_status`` and emits ``<cp:contentStatus>`` between
``<cp:category>`` and ``<dcterms:created>`` per the OOXML core-properties
schema.
"""
from __future__ import annotations

import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest


def _save_with_status(tmp_path: Path, status: str) -> Path:
    env = {**os.environ, "WOLFXL_TEST_EPOCH": "0"}
    out = tmp_path / "out.xlsx"
    script = "\n".join(
        [
            "import wolfxl",
            "wb = wolfxl.Workbook()",
            f"wb._rust_writer.set_properties({{'contentStatus': {status!r}}})",
            f"wb.save({str(out)!r})",
        ]
    )
    subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return out


def test_content_status_emitted_in_core_props(tmp_path: Path) -> None:
    """The native writer must emit
    ``<cp:contentStatus>Draft</cp:contentStatus>`` in ``docProps/core.xml``
    when ``contentStatus`` is set."""
    out = _save_with_status(tmp_path, "Draft")
    with zipfile.ZipFile(out) as zf:
        core = zf.read("docProps/core.xml").decode("utf-8")
    assert "<cp:contentStatus>Draft</cp:contentStatus>" in core, (
        f"core.xml missing contentStatus:\n{core[:500]}"
    )


def test_content_status_omitted_when_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without ``contentStatus`` in the props dict, the writer must not
    emit the element. Guards against accidental empty element emission."""
    monkeypatch.setenv("WOLFXL_TEST_EPOCH", "0")
    import wolfxl
    wb = wolfxl.Workbook()
    wb._rust_writer.set_properties({"title": "no status"})
    out = tmp_path / "out.xlsx"
    wb.save(str(out))
    with zipfile.ZipFile(out) as zf:
        core = zf.read("docProps/core.xml").decode("utf-8")
    assert "<cp:contentStatus" not in core, (
        f"core.xml has unexpected contentStatus:\n{core[:500]}"
    )
