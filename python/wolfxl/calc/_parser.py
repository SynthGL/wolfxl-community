"""Formula parser: regex-based reference extraction + optional formulas lib."""

from __future__ import annotations

import re
from typing import Any

from wolfxl._utils import a1_to_rowcol, rowcol_to_a1

# ---------------------------------------------------------------------------
# Regex patterns for Excel formula reference extraction
# ---------------------------------------------------------------------------

# Single cell ref: A1, $A$1, $A1, A$1 (with optional sheet prefix)
_SHEET_PREFIX = r"(?:'([^']+)'!|([A-Za-z0-9_]+)!)"
_CELL_REF = r"\$?([A-Z]{1,3})\$?(\d+)"
_SINGLE_REF_RE = re.compile(
    rf"(?:{_SHEET_PREFIX})?{_CELL_REF}",
    re.IGNORECASE,
)

# Range: A1:B5 (with optional sheet prefix, applied to start only)
_RANGE_REF_RE = re.compile(
    rf"(?:{_SHEET_PREFIX})?{_CELL_REF}\s*:\s*{_CELL_REF}",
    re.IGNORECASE,
)

# Function names: SUM(...), VLOOKUP(...)
_FUNC_RE = re.compile(r"([A-Z][A-Z0-9_.]+)\s*\(", re.IGNORECASE)

# Strings in formulas (to skip refs inside string literals)
_STRING_RE = re.compile(r'"[^"]*"')


def _strip_strings(formula: str) -> str:
    """Remove string literals so refs inside quotes aren't matched."""
    return _STRING_RE.sub("", formula)


# ---------------------------------------------------------------------------
# Reference extraction
# ---------------------------------------------------------------------------


def parse_references(formula: str, current_sheet: str = "Sheet1") -> list[str]:
    """Extract all single cell references from a formula.

    Returns canonical "SheetName!A1" strings (no dollar signs, unquoted).
    Does NOT include range references - use parse_range_references for those.
    """
    clean = _strip_strings(formula)
    refs: list[str] = []
    seen: set[str] = set()

    # First extract ranges so we can skip their individual refs
    range_spans: list[tuple[int, int]] = []
    for m in _RANGE_REF_RE.finditer(clean):
        range_spans.append((m.start(), m.end()))

    for m in _SINGLE_REF_RE.finditer(clean):
        # Skip if this match is inside a range match
        pos = m.start()
        in_range = any(s <= pos < e for s, e in range_spans)
        if in_range:
            continue

        sheet = m.group(1) or m.group(2) or current_sheet
        col_str = m.group(3).upper()
        row_str = m.group(4)
        canonical = f"{sheet}!{col_str}{row_str}"
        if canonical not in seen:
            refs.append(canonical)
            seen.add(canonical)

    return refs


def parse_range_references(formula: str, current_sheet: str = "Sheet1") -> list[str]:
    """Extract all range references from a formula.

    Returns canonical "SheetName!A1:B5" strings.
    """
    clean = _strip_strings(formula)
    ranges: list[str] = []
    seen: set[str] = set()

    for m in _RANGE_REF_RE.finditer(clean):
        sheet = m.group(1) or m.group(2) or current_sheet
        start_col = m.group(3).upper()
        start_row = m.group(4)
        end_col = m.group(5).upper()
        end_row = m.group(6)
        canonical = f"{sheet}!{start_col}{start_row}:{end_col}{end_row}"
        if canonical not in seen:
            ranges.append(canonical)
            seen.add(canonical)

    return ranges


def parse_functions(formula: str) -> list[str]:
    """Extract all function names used in a formula."""
    clean = _strip_strings(formula)
    funcs: list[str] = []
    seen: set[str] = set()
    for m in _FUNC_RE.finditer(clean):
        name = m.group(1).upper()
        if name not in seen:
            funcs.append(name)
            seen.add(name)
    return funcs


# ---------------------------------------------------------------------------
# Range expansion
# ---------------------------------------------------------------------------


def expand_range(range_ref: str) -> list[str]:
    """Expand a range like "A1:A5" into individual cell refs ["A1", "A2", ..., "A5"].

    The range_ref can be with or without sheet prefix.
    Returns refs in the same format as input (with or without sheet).
    """
    sheet: str | None = None
    ref_part = range_ref

    # Check for sheet prefix
    if "!" in range_ref:
        sheet, ref_part = range_ref.rsplit("!", 1)
        sheet = sheet.strip("'")

    parts = ref_part.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid range: {range_ref!r}")

    start_row, start_col = a1_to_rowcol(parts[0].replace("$", ""))
    end_row, end_col = a1_to_rowcol(parts[1].replace("$", ""))

    # Normalize order
    r_min, r_max = min(start_row, end_row), max(start_row, end_row)
    c_min, c_max = min(start_col, end_col), max(start_col, end_col)

    cells: list[str] = []
    for r in range(r_min, r_max + 1):
        for c in range(c_min, c_max + 1):
            ref = rowcol_to_a1(r, c)
            if sheet is not None:
                cells.append(f"{sheet}!{ref}")
            else:
                cells.append(ref)

    return cells


def range_shape(range_ref: str) -> tuple[int, int]:
    """Return ``(n_rows, n_cols)`` for a range reference like ``A1:C3``.

    The *range_ref* may include a sheet prefix (``Sheet1!A1:C3``).
    """
    ref_part = range_ref
    if "!" in range_ref:
        _, ref_part = range_ref.rsplit("!", 1)

    parts = ref_part.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid range: {range_ref!r}")

    start_row, start_col = a1_to_rowcol(parts[0].replace("$", ""))
    end_row, end_col = a1_to_rowcol(parts[1].replace("$", ""))
    # Use min/max for consistency with expand_range()
    n_rows = max(start_row, end_row) - min(start_row, end_row) + 1
    n_cols = max(start_col, end_col) - min(start_col, end_col) + 1
    return (n_rows, n_cols)


# ---------------------------------------------------------------------------
# All-references extraction (combines singles + expanded ranges)
# ---------------------------------------------------------------------------


def all_references(formula: str, current_sheet: str = "Sheet1") -> list[str]:
    """Extract all cell references (single + range-expanded) from a formula.

    Returns canonical "SheetName!A1" strings with ranges fully expanded.
    """
    refs: list[str] = []
    seen: set[str] = set()

    # Single refs (excluding those inside ranges)
    for ref in parse_references(formula, current_sheet):
        if ref not in seen:
            refs.append(ref)
            seen.add(ref)

    # Expand ranges
    for rng in parse_range_references(formula, current_sheet):
        for ref in expand_range(rng):
            if ref not in seen:
                refs.append(ref)
                seen.add(ref)

    return refs


# ---------------------------------------------------------------------------
# FormulaParser: optional formulas lib integration
# ---------------------------------------------------------------------------

_formulas_available: bool | None = None


def _check_formulas() -> bool:
    global _formulas_available
    if _formulas_available is None:
        try:
            import formulas  # noqa: F401

            _formulas_available = True
        except ImportError:
            _formulas_available = False
    return _formulas_available


class FormulaParser:
    """Parses Excel formulas for reference extraction and optional compilation.

    The compile() method tries the `formulas` library first. If unavailable,
    returns None and the evaluator falls back to builtin function dispatch.
    """

    def __init__(self) -> None:
        self._use_formulas = _check_formulas()

    def parse_refs(self, formula: str, current_sheet: str = "Sheet1") -> list[str]:
        """Extract all cell references from a formula (always works)."""
        return all_references(formula, current_sheet)

    def compile(self, formula: str) -> Any | None:
        """Try to compile a formula into a callable.

        Returns a compiled function or None if compilation fails.
        The compiled function is not used in the current implementation -
        we rely on builtin dispatch instead for determinism.
        """
        if not self._use_formulas:
            return None
        try:
            import formulas as fm

            result = fm.Parser().ast(formula)
            if result and len(result) > 1:
                return result[1].compile()
        except Exception:
            pass
        return None
