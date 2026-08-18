"""Parity tests for pandas dataframe helpers.

openpyxl's ``dataframe_to_rows`` is the compatibility oracle. These tests keep
WolfXL aligned for the dataframe layouts common in ``ws.append(...)`` flows.
"""

from __future__ import annotations

from datetime import date, datetime
from math import isnan
from typing import Any

import pytest

np = pytest.importorskip("numpy")
pd = pytest.importorskip("pandas")
openpyxl_dataframe = pytest.importorskip("openpyxl.utils.dataframe")

from wolfxl.utils.dataframe import dataframe_to_rows as wolfxl_dataframe_to_rows


def _normalise_nan(value: Any) -> Any:
    if isinstance(value, float) and isnan(value):
        return ("nan",)
    if isinstance(value, np.floating) and np.isnan(value):
        return ("nan",)
    return value


def _normalise_rows(rows: list[Any]) -> list[list[Any]]:
    return [[_normalise_nan(value) for value in list(row)] for row in rows]


def _assert_dataframe_to_rows_parity(df: Any) -> None:
    for index in (False, True):
        for header in (False, True):
            expected = list(
                openpyxl_dataframe.dataframe_to_rows(
                    df,
                    index=index,
                    header=header,
                )
            )
            actual = list(
                wolfxl_dataframe_to_rows(
                    df,
                    index=index,
                    header=header,
                )
            )
            assert _normalise_rows(actual) == _normalise_rows(expected), (
                f"mismatch for index={index}, header={header}"
            )


def test_dataframe_to_rows_matches_openpyxl_for_index_header_combinations() -> None:
    df = pd.DataFrame({"amount": [1, 2], "count": [3, 4]})

    _assert_dataframe_to_rows_parity(df)


def test_dataframe_to_rows_matches_openpyxl_for_named_index() -> None:
    df = pd.DataFrame(
        {"amount": [10, 20]},
        index=pd.Index(["row-a", "row-b"], name="row_id"),
    )

    _assert_dataframe_to_rows_parity(df)


def test_dataframe_to_rows_matches_openpyxl_for_multiindex_columns() -> None:
    df = pd.DataFrame(
        [[1, 2, 3], [4, 5, 6]],
        columns=pd.MultiIndex.from_tuples(
            [
                ("QoE", "revenue"),
                ("QoE", "ebitda"),
                ("NWC", "inventory"),
            ]
        ),
    )

    _assert_dataframe_to_rows_parity(df)


def test_dataframe_to_rows_matches_openpyxl_for_multiindex_index() -> None:
    df = pd.DataFrame(
        {"amount": [10, 20, 30]},
        index=pd.MultiIndex.from_tuples(
            [
                ("FY24", "Q1"),
                ("FY24", "Q2"),
                ("FY25", "Q1"),
            ],
            names=["year", "quarter"],
        ),
    )

    _assert_dataframe_to_rows_parity(df)


def test_dataframe_to_rows_matches_openpyxl_for_multiindex_columns_and_index() -> None:
    df = pd.DataFrame(
        [[1, 2], [3, 4], [5, 6]],
        columns=pd.MultiIndex.from_tuples(
            [
                ("QoE", "revenue"),
                ("QoE", "ebitda"),
            ]
        ),
        index=pd.MultiIndex.from_tuples(
            [
                ("FY24", "Q1"),
                ("FY24", "Q2"),
                ("FY25", "Q1"),
            ],
            names=["year", "quarter"],
        ),
    )

    _assert_dataframe_to_rows_parity(df)


def test_dataframe_to_rows_matches_openpyxl_for_none_nan_and_dates() -> None:
    df = pd.DataFrame(
        {
            "none": [None, "present"],
            "nan": [float("nan"), np.nan],
            "date": [date(2024, 1, 2), datetime(2024, 1, 3, 4, 5)],
            "timestamp": [pd.Timestamp("2024-01-04"), np.datetime64("2024-01-05")],
        }
    )

    _assert_dataframe_to_rows_parity(df)


def test_dataframe_to_rows_matches_openpyxl_for_numpy_datetime_headers() -> None:
    df = pd.DataFrame(
        [[100, 200]],
        columns=pd.Index([np.datetime64("2024-01-01"), "plain"]),
    )

    _assert_dataframe_to_rows_parity(df)
