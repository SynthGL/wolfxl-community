"""Built-in named styles exposed by openpyxl."""

from __future__ import annotations

from xml.etree.ElementTree import fromstring

from wolfxl.styles import NamedStyle

normal = NamedStyle(name="Normal", builtinId=0)
comma = NamedStyle(name="Comma", builtinId=3)
comma_0 = NamedStyle(name="Comma [0]", builtinId=6)
currency = NamedStyle(name="Currency", builtinId=4)
currency_0 = NamedStyle(name="Currency [0]", builtinId=7)
percent = NamedStyle(name="Percent", builtinId=5)
calculation = NamedStyle(name="Calculation", builtinId=22)
total = NamedStyle(name="Total", builtinId=25)
note = NamedStyle(name="Note", builtinId=10)
warning = NamedStyle(name="Warning Text", builtinId=11)
title = NamedStyle(name="Title", builtinId=15)
headline_1 = NamedStyle(name="Heading 1", builtinId=16)
headline_2 = NamedStyle(name="Heading 2", builtinId=17)
headline_3 = NamedStyle(name="Heading 3", builtinId=18)
headline_4 = NamedStyle(name="Heading 4", builtinId=19)
input = NamedStyle(name="Input", builtinId=20)  # noqa: A001
output = NamedStyle(name="Output", builtinId=21)
check_cell = NamedStyle(name="Check Cell", builtinId=23)
linked_cell = NamedStyle(name="Linked Cell", builtinId=24)
explanatory = NamedStyle(name="Explanatory Text", builtinId=53)
good = NamedStyle(name="Good", builtinId=26)
bad = NamedStyle(name="Bad", builtinId=27)
neutral = NamedStyle(name="Neutral", builtinId=28)
accent_1 = NamedStyle(name="Accent1", builtinId=29)
accent_1_20 = NamedStyle(name="20% - Accent1", builtinId=30)
accent_1_40 = NamedStyle(name="40% - Accent1", builtinId=31)
accent_1_60 = NamedStyle(name="60% - Accent1", builtinId=32)
accent_2 = NamedStyle(name="Accent2", builtinId=33)
accent_2_20 = NamedStyle(name="20% - Accent2", builtinId=34)
accent_2_40 = NamedStyle(name="40% - Accent2", builtinId=35)
accent_2_60 = NamedStyle(name="60% - Accent2", builtinId=36)
accent_3 = NamedStyle(name="Accent3", builtinId=37)
accent_3_20 = NamedStyle(name="20% - Accent3", builtinId=38)
accent_3_40 = NamedStyle(name="40% - Accent3", builtinId=39)
accent_3_60 = NamedStyle(name="60% - Accent3", builtinId=40)
accent_4 = NamedStyle(name="Accent4", builtinId=41)
accent_4_20 = NamedStyle(name="20% - Accent4", builtinId=42)
accent_4_40 = NamedStyle(name="40% - Accent4", builtinId=43)
accent_4_60 = NamedStyle(name="60% - Accent4", builtinId=44)
accent_5 = NamedStyle(name="Accent5", builtinId=45)
accent_5_20 = NamedStyle(name="20% - Accent5", builtinId=46)
accent_5_40 = NamedStyle(name="40% - Accent5", builtinId=47)
accent_5_60 = NamedStyle(name="60% - Accent5", builtinId=48)
accent_6 = NamedStyle(name="Accent6", builtinId=49)
accent_6_20 = NamedStyle(name="20% - Accent6", builtinId=50)
accent_6_40 = NamedStyle(name="40% - Accent6", builtinId=51)
accent_6_60 = NamedStyle(name="60% - Accent6", builtinId=52)
hyperlink = NamedStyle(name="Hyperlink", builtinId=8)
followed_hyperlink = NamedStyle(name="Followed Hyperlink", builtinId=9)
pandas_highlight = NamedStyle(name="Pandas", builtinId=None, customBuiltin=True)

styles = [
    normal,
    comma,
    comma_0,
    currency,
    currency_0,
    percent,
    calculation,
    total,
    note,
    warning,
    title,
    headline_1,
    headline_2,
    headline_3,
    headline_4,
    input,
    output,
    check_cell,
    linked_cell,
    explanatory,
    good,
    bad,
    neutral,
    accent_1,
    accent_1_20,
    accent_1_40,
    accent_1_60,
    accent_2,
    accent_2_20,
    accent_2_40,
    accent_2_60,
    accent_3,
    accent_3_20,
    accent_3_40,
    accent_3_60,
    accent_4,
    accent_4_20,
    accent_4_40,
    accent_4_60,
    accent_5,
    accent_5_20,
    accent_5_40,
    accent_5_60,
    accent_6,
    accent_6_20,
    accent_6_40,
    accent_6_60,
    hyperlink,
    followed_hyperlink,
]

__all__ = [name for name in list(globals()) if not name.startswith("_")]
