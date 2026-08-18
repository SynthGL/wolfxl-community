"""``openpyxl.utils.formulas`` — Excel function name catalog.

openpyxl exposes a frozen ``FORMULAE`` set of every Excel-recognised
function name (``"SUM"``, ``"VLOOKUP"``, ``"XLOOKUP"``, ...) so callers
can validate user-supplied formula strings against the canonical list.

Wolfxl's calc engine has its own function registry under
:mod:`wolfxl.calc._functions`; this module exposes that catalogue under
the openpyxl-shaped name.  Names are uppercased to match openpyxl.

Pod 2 (RFC-060).
"""

from __future__ import annotations

from wolfxl._compat import _openpyxl_name_fallback

try:
    from wolfxl.calc._functions import _BUILTINS as _FUNCTIONS
    FORMULAE: frozenset[str] = frozenset(name.upper() for name in _FUNCTIONS)
except Exception:  # pragma: no cover — defensive: calc engine optional at import.
    FORMULAE = frozenset()


def validate(formula: str) -> bool:
    """Check that a formula uses known Excel function names."""
    assert formula.startswith("=")
    tokenized = Tokenizer(formula)
    for token in tokenized.items:
        if token.type == "FUNC" and token.subtype == "OPEN":
            name = token.value[:-1]
            if not token.value.startswith("_xlfn.") and name not in FORMULAE:
                raise ValueError(
                    f"Unknown function {token.value} in {formula}. "
                    "The function may need a prefix"
                )
    return True


class Tokenizer:
    """Lazy wrapper for openpyxl's utility-module tokenizer export."""

    def __new__(cls, formula: str):  # noqa: D102
        from wolfxl.formula.tokenizer import Tokenizer as FormulaTokenizer

        return FormulaTokenizer(formula)


__all__ = ["FORMULAE", "Tokenizer", "validate"]

__getattr__ = _openpyxl_name_fallback(globals())
