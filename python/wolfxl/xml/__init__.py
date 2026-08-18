"""XML backend flags compatible with ``openpyxl.xml``."""

from __future__ import annotations

import os

from wolfxl._compat import _openpyxl_name_fallback


def _lxml_available() -> bool:
    try:
        from lxml.etree import LXML_VERSION
    except ImportError:
        return False
    return LXML_VERSION >= (3, 3, 1, 0)


def _defusedxml_available() -> bool:
    try:
        import defusedxml  # noqa: F401
    except ImportError:
        return False
    return True


LXML = _lxml_available() and os.environ.get("OPENPYXL_LXML", "True") == "True"
DEFUSEDXML = (
    _defusedxml_available()
    and os.environ.get("OPENPYXL_DEFUSEDXML", "True") == "True"
)

lxml_available = _lxml_available
defusedxml_available = _defusedxml_available
lxml_env_set = "OPENPYXL_LXML" in os.environ
defusedxml_env_set = "OPENPYXL_DEFUSEDXML" in os.environ

__all__ = [
    "DEFUSEDXML",
    "LXML",
    "defusedxml_available",
    "defusedxml_env_set",
    "lxml_available",
    "lxml_env_set",
]

__getattr__ = _openpyxl_name_fallback(globals())
