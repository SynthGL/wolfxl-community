"""openpyxl.compat.product compatibility."""

from __future__ import annotations

import functools
import math
import operator
from collections.abc import Iterable
from typing import Any


def prod(values: Iterable[Any]) -> Any:
    return math.prod(values)


def product(values: Iterable[Any]) -> Any:
    return functools.reduce(operator.mul, values)


__all__ = ["functools", "operator", "prod", "product"]
