"""``openpyxl.styles.numbers`` — number-format helpers + the builtin catalog.

Wolfxl's ``is_date_format`` lives at :mod:`wolfxl.utils.numbers`; this module
re-exports it under the openpyxl-shaped path and bundles the canonical
``BUILTIN_FORMATS`` mapping (numFmtId → format string) verbatim from
openpyxl 3.1.x's catalog.

Pod 2 (RFC-060).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from wolfxl._compat import _OpenpyxlSerialisable, _install_openpyxl_iter
from wolfxl.descriptors.base import String as _StringDescriptor
from wolfxl.utils.numbers import is_date_format

# openpyxl 3.1.x ``openpyxl/styles/numbers.py`` — frozen dict of every
# builtin (Excel-reserved) numFmtId → format-string mapping.  Indexes 0..49
# come from the spec; the rest are openpyxl additions for the formats Excel
# emits in practice.
BUILTIN_FORMATS = {
    0: "General",
    1: "0",
    2: "0.00",
    3: "#,##0",
    4: "#,##0.00",
    5: '"$"#,##0_);("$"#,##0)',
    6: '"$"#,##0_);[Red]("$"#,##0)',
    7: '"$"#,##0.00_);("$"#,##0.00)',
    8: '"$"#,##0.00_);[Red]("$"#,##0.00)',
    9: "0%",
    10: "0.00%",
    11: "0.00E+00",
    12: "# ?/?",
    13: "# ??/??",
    14: "mm-dd-yy",
    15: "d-mmm-yy",
    16: "d-mmm",
    17: "mmm-yy",
    18: "h:mm AM/PM",
    19: "h:mm:ss AM/PM",
    20: "h:mm",
    21: "h:mm:ss",
    22: "m/d/yy h:mm",
    37: "#,##0_);(#,##0)",
    38: "#,##0_);[Red](#,##0)",
    39: "#,##0.00_);(#,##0.00)",
    40: "#,##0.00_);[Red](#,##0.00)",
    41: r'_(* #,##0_);_(* \(#,##0\);_(* "-"_);_(@_)',
    42: r'_("$"* #,##0_);_("$"* \(#,##0\);_("$"* "-"_);_(@_)',
    43: r'_(* #,##0.00_);_(* \(#,##0.00\);_(* "-"??_);_(@_)',
    44: r'_("$"* #,##0.00_)_("$"* \(#,##0.00\)_("$"* "-"??_)_(@_)',
    45: "mm:ss",
    46: "[h]:mm:ss",
    47: "mmss.0",
    48: "##0.0E+0",
    49: "@",
}

# Per-purpose convenience constants — openpyxl exposes these as the
# canonical strings users assign to ``cell.number_format``.
FORMAT_GENERAL = BUILTIN_FORMATS[0]
FORMAT_TEXT = BUILTIN_FORMATS[49]
FORMAT_NUMBER = BUILTIN_FORMATS[1]
FORMAT_NUMBER_00 = BUILTIN_FORMATS[2]
FORMAT_NUMBER_COMMA_SEPARATED1 = BUILTIN_FORMATS[4]
FORMAT_NUMBER_COMMA_SEPARATED2 = "#,##0.00_-"
FORMAT_PERCENTAGE = BUILTIN_FORMATS[9]
FORMAT_PERCENTAGE_00 = BUILTIN_FORMATS[10]
FORMAT_DATE_YYYYMMDD2 = "yyyy-mm-dd"
FORMAT_DATE_YYMMDD = "yy-mm-dd"
FORMAT_DATE_YYMMDDSLASH = "yy/mm/dd@"
FORMAT_DATE_DDMMYY = "dd/mm/yy"
FORMAT_DATE_DMYSLASH = "d/m/y"
FORMAT_DATE_DMYMINUS = "d-m-y"
FORMAT_DATE_DMMINUS = "d-m"
FORMAT_DATE_MYMINUS = "m-y"
FORMAT_DATE_XLSX14 = BUILTIN_FORMATS[14]
FORMAT_DATE_XLSX15 = BUILTIN_FORMATS[15]
FORMAT_DATE_XLSX16 = BUILTIN_FORMATS[16]
FORMAT_DATE_XLSX17 = BUILTIN_FORMATS[17]
FORMAT_DATE_XLSX22 = BUILTIN_FORMATS[22]
FORMAT_DATE_DATETIME = "yyyy-mm-dd h:mm:ss"
FORMAT_DATE_TIME1 = BUILTIN_FORMATS[18]
FORMAT_DATE_TIME2 = BUILTIN_FORMATS[19]
FORMAT_DATE_TIME3 = BUILTIN_FORMATS[20]
FORMAT_DATE_TIME4 = BUILTIN_FORMATS[21]
FORMAT_DATE_TIME5 = BUILTIN_FORMATS[45]
FORMAT_DATE_TIME6 = BUILTIN_FORMATS[21]
FORMAT_DATE_TIME7 = "i:s.S"
FORMAT_DATE_TIME8 = "h:mm:ss@"
FORMAT_DATE_TIMEDELTA = "[hh]:mm:ss"
FORMAT_CURRENCY_USD_SIMPLE = '"$"#,##0.00_-'
FORMAT_CURRENCY_USD = '$#,##0_-'
FORMAT_CURRENCY_EUR_SIMPLE = '[$EUR ]#,##0.00_-'

BUILTIN_FORMATS_MAX_SIZE = 164
BUILTIN_FORMATS_REVERSE = {value: key for key, value in BUILTIN_FORMATS.items()}
COLORS = r"\[(BLACK|BLUE|CYAN|GREEN|MAGENTA|RED|WHITE|YELLOW)\]"
LITERAL_GROUP = r'".*?"'
LOCALE_GROUP = r"\[(?!hh?\]|mm?\]|ss?\])[^\]]*\]"
STRIP_RE = re.compile(f"{LITERAL_GROUP}|{LOCALE_GROUP}")
TIMEDELTA_RE = re.compile(
    r"\[hh?\](:mm(:ss(\.0*)?)?)?|\[mm?\](:ss(\.0*)?)?|\[ss?\](\.0*)?",
    re.IGNORECASE,
)


def builtin_format_code(index: int) -> str | None:
    return BUILTIN_FORMATS.get(index)


def builtin_format_id(fmt: str) -> int | None:
    return BUILTIN_FORMATS_REVERSE.get(fmt)


def is_builtin(fmt: str) -> bool:
    return fmt in BUILTIN_FORMATS_REVERSE


def is_timedelta_format(fmt: str | None) -> bool:
    if fmt is None:
        return False
    fmt = fmt.split(";")[0]
    return TIMEDELTA_RE.search(fmt) is not None


def is_datetime(fmt: str | None) -> str | None:
    """Return ``"date"``, ``"time"``, or ``"datetime"`` for date formats."""
    if not is_date_format(fmt):
        return None

    DATE = TIME = False
    if fmt is not None and any((x in fmt for x in "dy")):
        DATE = True
    if fmt is not None and any((x in fmt for x in "hs")):
        TIME = True

    if DATE and TIME:
        return "datetime"
    if DATE:
        return "date"
    return "time"


class NumberFormatDescriptor(_StringDescriptor):
    def __set__(self, instance: Any, value: Any) -> None:
        if value is None:
            value = FORMAT_GENERAL
        super().__set__(instance, value)


@dataclass
class NumberFormat:
    numFmtId: int | None = None  # noqa: N815
    formatCode: str | None = None  # noqa: N815


@dataclass
class NumberFormatList:
    numFmt: list[NumberFormat] = field(default_factory=list)  # noqa: N815
    count: int | None = None

    def __post_init__(self) -> None:
        if self.count is None:
            self.count = len(self.numFmt)


Integer = Sequence = Serialisable = String = _OpenpyxlSerialisable


_install_openpyxl_iter(NumberFormat, NumberFormatList)

__all__ = [
    "BUILTIN_FORMATS",
    "BUILTIN_FORMATS_MAX_SIZE",
    "BUILTIN_FORMATS_REVERSE",
    "COLORS",
    "FORMAT_CURRENCY_EUR_SIMPLE",
    "FORMAT_CURRENCY_USD",
    "FORMAT_CURRENCY_USD_SIMPLE",
    "FORMAT_DATE_DATETIME",
    "FORMAT_DATE_DDMMYY",
    "FORMAT_DATE_DMMINUS",
    "FORMAT_DATE_DMYMINUS",
    "FORMAT_DATE_DMYSLASH",
    "FORMAT_DATE_MYMINUS",
    "FORMAT_DATE_TIME1",
    "FORMAT_DATE_TIME2",
    "FORMAT_DATE_TIME3",
    "FORMAT_DATE_TIME4",
    "FORMAT_DATE_TIME5",
    "FORMAT_DATE_TIME6",
    "FORMAT_DATE_TIME7",
    "FORMAT_DATE_TIME8",
    "FORMAT_DATE_TIMEDELTA",
    "FORMAT_DATE_XLSX14",
    "FORMAT_DATE_XLSX15",
    "FORMAT_DATE_XLSX16",
    "FORMAT_DATE_XLSX17",
    "FORMAT_DATE_XLSX22",
    "FORMAT_DATE_YYMMDD",
    "FORMAT_DATE_YYMMDDSLASH",
    "FORMAT_DATE_YYYYMMDD2",
    "FORMAT_GENERAL",
    "FORMAT_NUMBER",
    "FORMAT_NUMBER_00",
    "FORMAT_NUMBER_COMMA_SEPARATED1",
    "FORMAT_NUMBER_COMMA_SEPARATED2",
    "FORMAT_PERCENTAGE",
    "FORMAT_PERCENTAGE_00",
    "FORMAT_TEXT",
    "Integer",
    "LITERAL_GROUP",
    "LOCALE_GROUP",
    "NumberFormat",
    "NumberFormatDescriptor",
    "NumberFormatList",
    "STRIP_RE",
    "Sequence",
    "Serialisable",
    "String",
    "TIMEDELTA_RE",
    "builtin_format_code",
    "builtin_format_id",
    "is_builtin",
    "is_date_format",
    "is_datetime",
    "is_timedelta_format",
    "re",
]
