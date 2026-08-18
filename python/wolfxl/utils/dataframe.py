"""openpyxl-compatible ``dataframe_to_rows`` helper.

Accepts a pandas DataFrame and yields rows suitable for ``ws.append()``.
Pandas is imported lazily so that ``import wolfxl.utils.dataframe`` works
without pandas installed - only calling dataframe helpers triggers
the import.
"""

from __future__ import annotations

from collections.abc import Iterator
from itertools import accumulate
import operator
from typing import TYPE_CHECKING, Any

from wolfxl.compat.product import prod

try:  # pragma: no cover - depends on optional test/runtime environment
    import numpy  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover
    numpy = None  # type: ignore[assignment]

if TYPE_CHECKING:
    import pandas as pd  # type: ignore[import-untyped]  # pragma: no cover - type-only


def dataframe_to_rows(
    df: pd.DataFrame,
    index: bool = True,
    header: bool = True,
) -> Iterator[list[Any]]:
    """Yield rows from a pandas DataFrame, matching openpyxl's helper.

    - ``header=True`` yields a header row first (column labels); when
      the DataFrame has a MultiIndex on columns, each level is yielded
      as a separate header row.
    - ``index=True`` prepends the row index to each data row; with a
      MultiIndex index, each index level becomes its own leading column.
    - ``index=True`` yields the index name row before the data rows, matching
      openpyxl's layout convention.
    """
    import pandas as pd  # type: ignore[import-untyped]
    import numpy as np  # type: ignore[import-untyped]

    if header:
        if df.columns.nlevels > 1:
            rows = expand_index(df.columns, header=True)
        else:
            rows = [list(df.columns.values)]

        for row in rows:
            normalized_row = []
            for value in row:
                if isinstance(value, np.datetime64):
                    value = pd.Timestamp(value)
                normalized_row.append(value)
            if index:
                normalized_row = [None] * df.index.nlevels + normalized_row
            yield normalized_row

    if index:
        yield df.index.names

    expanded: Iterator[list[Any]] = ([value] for value in df.index)
    if df.index.nlevels > 1:
        expanded = expand_index(df.index)

    for df_index, values in zip(expanded, df.itertuples(index=False)):
        row = list(values)
        if index:
            yield df_index + row
        else:
            yield row


def expand_index(index: Any, header: bool = False) -> Iterator[list[Any]]:
    """Expand a pandas Index or MultiIndex using openpyxl's sparse layout.

    Repeated MultiIndex labels are emitted as ``None`` until an earlier level
    changes. Column headers are transposed so each MultiIndex level becomes its
    own output row.
    """
    values = list(index.values)
    previous_value = [None] * len(values[0])
    result = []

    for value in values:
        row = [None] * len(value)
        prior_change = False
        for idx, (current_member, previous_member) in enumerate(
            zip(value, previous_value)
        ):
            if current_member != previous_member or prior_change:
                row[idx] = current_member
                prior_change = True

        previous_value = value

        if not header:
            yield row
        else:
            result.append(row)

    if header:
        for row in zip(*result):
            yield list(row)


def worksheet_to_dataframe(
    ws: Any,
    *,
    header: bool = True,
    min_row: int | None = None,
    max_row: int | None = None,
    min_col: int | None = None,
    max_col: int | None = None,
) -> pd.DataFrame:
    """Materialize worksheet values as a pandas DataFrame.

    Pandas is imported lazily. When ``header=True``, the first row in
    the requested range becomes the DataFrame columns.
    """
    import pandas as pd  # type: ignore[import-untyped]

    rows = list(
        ws.iter_rows(
            min_row=min_row,
            max_row=max_row,
            min_col=min_col,
            max_col=max_col,
            values_only=True,
        )
    )
    if not rows:
        return pd.DataFrame()
    if header:
        columns = list(rows[0])
        return pd.DataFrame(rows[1:], columns=columns)
    return pd.DataFrame(rows)


__all__ = [
    "accumulate",
    "dataframe_to_rows",
    "expand_index",
    "numpy",
    "operator",
    "prod",
    "worksheet_to_dataframe",
]
