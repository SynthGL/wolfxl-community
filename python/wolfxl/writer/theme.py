"""``openpyxl.writer.theme`` compatibility."""

from __future__ import annotations

theme_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Office Theme"/>
"""


def write_theme() -> str:
    return theme_xml


__all__ = ["theme_xml", "write_theme"]
