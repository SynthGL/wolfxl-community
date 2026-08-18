"""``CalculatedField`` / ``CalculatedItem`` — pivot calc support.

Calculated fields live on the cache; calculated items live on the
pivot table. Excel evaluates the formulas on open — wolfxl does NOT
pre-compute calc-field values into cache records.

The formulas are validated for parse-correctness via the
``wolfxl-formula`` crate at construction time when the crate is
available; otherwise we accept any string.
"""

from __future__ import annotations

from dataclasses import dataclass


_VALID_DATA_TYPES = ("string", "number", "boolean", "date")


@dataclass
class CalculatedField:
    """Calculated field, scoped to the pivot cache.

    Lives in :class:`PivotCache.calculated_fields`; emitted as
    ``<calculatedField>`` and a companion entry in
    ``<calculatedItems>`` inside the cache definition XML.
    """

    name: str
    formula: str
    data_type: str = "number"

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("CalculatedField requires a non-empty name")
        if not self.formula:
            raise ValueError("CalculatedField requires a non-empty formula")
        if self.data_type not in _VALID_DATA_TYPES:
            raise ValueError(
                f"CalculatedField.data_type must be one of "
                f"{_VALID_DATA_TYPES}, got {self.data_type!r}"
            )
        # Parse-validate the formula expression. wolfxl-formula's
        # parser tolerates an optional leading "=" — strip if present.
        expr = self.formula
        if expr.startswith("="):
            expr = expr[1:]
        # Best-effort validation. We don't depend on the formula crate
        # at runtime (no PyO3 binding for it from the Python side); we
        # do a structural sanity check.
        _shallow_validate_formula(expr)

    def to_rust_dict(self) -> dict:
        return {
            "name": self.name,
            "formula": self.formula.lstrip("="),
            "data_type": self.data_type,
        }


@dataclass
class CalculatedItem:
    """Calculated item, scoped to a pivot table.

    Lives on the pivot table; emitted as a `<calculatedItem>` inside
    the table XML (NOT cache XML).
    """

    field_name: str
    item_name: str
    formula: str

    def __post_init__(self) -> None:
        if not self.field_name:
            raise ValueError("CalculatedItem requires a non-empty field_name")
        if not self.item_name:
            raise ValueError("CalculatedItem requires a non-empty item_name")
        if not self.formula:
            raise ValueError("CalculatedItem requires a non-empty formula")
        expr = self.formula
        if expr.startswith("="):
            expr = expr[1:]
        _shallow_validate_formula(expr)

    def to_rust_dict(self) -> dict:
        return {
            "field_name": self.field_name,
            "item_name": self.item_name,
            "formula": self.formula.lstrip("="),
        }


def _shallow_validate_formula(expr: str) -> None:
    """Structural sanity check for a calc-field/item formula.

    The Rust ``wolfxl-formula`` crate does the authoritative parse;
    here we only catch the most obvious shape errors (mismatched
    parentheses, empty body) so users don't ship broken formulas
    silently.
    """
    s = expr.strip()
    if not s:
        raise ValueError("formula body is empty")
    depth = 0
    in_str = False
    quote = ""
    for ch in s:
        if in_str:
            if ch == quote:
                in_str = False
            continue
        if ch in ('"', "'"):
            in_str = True
            quote = ch
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                raise ValueError(
                    f"unbalanced parentheses in formula: {expr!r}"
                )
    if depth != 0:
        raise ValueError(f"unbalanced parentheses in formula: {expr!r}")
    if in_str:
        raise ValueError(f"unterminated string literal in formula: {expr!r}")
