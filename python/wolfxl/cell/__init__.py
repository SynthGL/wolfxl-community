"""openpyxl-compatible ``wolfxl.cell`` namespace.

Re-exports the rich-text shims from :mod:`wolfxl.cell.rich_text`,
the cell-class compatibility shims (:class:`MergedCell`,
:class:`WriteOnlyCell`), :class:`IllegalCharacterError` (RFC-059 —
Pod 1E), and the array / data-table formula shims from
:mod:`wolfxl.cell.cell` (RFC-057 — Pod 1C).  The package shape
mirrors openpyxl's ``openpyxl.cell`` so existing code that imports
from ``openpyxl.cell.*`` can be redirected to ``wolfxl.cell.*`` with
one-line import swaps.

Pod 2 (RFC-060) owns the openpyxl-shaped path shims (e.g.
``wolfxl.cell.cell``) — this module exposes the classes at their
natural locations and Pod 2 builds the import paths on top.
"""

from wolfxl._cell import Cell
from wolfxl.cell import cell, read_only, rich_text, text
from wolfxl.cell._merged import MergedCell
from wolfxl.cell._write_only import WriteOnlyCell
from wolfxl.cell.read_only import ReadOnlyCell
from wolfxl.cell.cell import ArrayFormula, DataTableFormula
from wolfxl.utils.exceptions import IllegalCharacterError

__all__ = [
    "ArrayFormula",
    "Cell",
    "DataTableFormula",
    "IllegalCharacterError",
    "MergedCell",
    "ReadOnlyCell",
    "WriteOnlyCell",
    "cell",
    "read_only",
    "rich_text",
    "text",
]
