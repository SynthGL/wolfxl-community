"""Backend dispatcher — always returns NativeWorkbook (W5+).

The ``WOLFXL_WRITER`` environment variable is deprecated and ignored.
Setting it emits a :class:`DeprecationWarning` so callers can clean up
their environment. The legacy ``rust_xlsxwriter``-backed oracle and the
``DualWorkbook`` fan-out wrapper were removed in W5.
"""
from __future__ import annotations

import os
import warnings
from typing import Any

from . import _rust  # type: ignore[attr-defined]


def make_writer() -> Any:
    """Construct the write-mode backend. Always returns ``NativeWorkbook``."""
    if os.environ.get("WOLFXL_WRITER"):
        warnings.warn(
            "The WOLFXL_WRITER environment variable is deprecated and ignored. "
            "wolfxl always uses the native writer as of W5. Remove the variable "
            "from your environment.",
            DeprecationWarning,
            stacklevel=2,
        )
    return _rust.NativeWorkbook()
