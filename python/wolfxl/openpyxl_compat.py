"""Runtime import aliasing for openpyxl-shaped programs.

This module supports the smallest possible migration for existing openpyxl
programs:

    import wolfxl; wolfxl.install_as_openpyxl()

After that line, later ``import openpyxl`` and ``from openpyxl.styles import
Font`` imports resolve to WolfXL modules inside the current Python process.
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.util
import sys
from types import ModuleType
from typing import Any

__all__ = ["install_as_openpyxl", "uninstall_as_openpyxl"]


def install_as_openpyxl(*, force: bool = True) -> ModuleType:
    """Expose WolfXL under the ``openpyxl`` import name for this process.

    Args:
        force: Replace existing ``openpyxl`` entries in ``sys.modules``. This
            is the default because user programs often import optional helpers
            before their main workbook code. Already-bound local variables from
            an earlier real ``openpyxl`` import cannot be rewritten.

    Returns:
        The top-level :mod:`wolfxl` module, also installed as ``openpyxl``.

    Raises:
        RuntimeError: If ``openpyxl`` is already imported and ``force=False``.
    """
    import wolfxl

    existing = sys.modules.get("openpyxl")
    if existing is not None and existing is not wolfxl and not force:
        raise RuntimeError(
            "openpyxl is already imported; call install_as_openpyxl(force=True) "
            "before importing openpyxl-shaped modules"
        )

    if force:
        _remove_openpyxl_modules()

    _install_finder()
    sys.modules["openpyxl"] = wolfxl
    _alias_loaded_wolfxl_modules(force=True)
    return wolfxl


def uninstall_as_openpyxl() -> None:
    """Remove WolfXL's runtime ``openpyxl`` alias from this process."""
    _remove_finder()
    for name, module in list(sys.modules.items()):
        if _is_openpyxl_name(name) and _module_is_wolfxl(module):
            del sys.modules[name]


class _OpenpyxlAliasFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Import hook that maps future ``openpyxl.*`` imports to ``wolfxl.*``."""

    def find_spec(
        self,
        fullname: str,
        path: object | None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        if not _is_openpyxl_name(fullname):
            return None

        mapped_name = _wolfxl_name(fullname)
        mapped_spec = importlib.util.find_spec(mapped_name)
        if mapped_spec is None:
            return None

        is_package = mapped_spec.submodule_search_locations is not None
        spec = importlib.util.spec_from_loader(
            fullname,
            self,
            origin=mapped_spec.origin,
            is_package=is_package,
        )
        if spec is not None and is_package:
            spec.submodule_search_locations = list(
                mapped_spec.submodule_search_locations or []
            )
        return spec

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> ModuleType:
        module = importlib.import_module(_wolfxl_name(spec.name))
        sys.modules[spec.name] = module
        _attach_to_parent(spec.name, module)
        return module

    def exec_module(self, module: ModuleType) -> None:
        return None


def _install_finder() -> None:
    if not any(isinstance(finder, _OpenpyxlAliasFinder) for finder in sys.meta_path):
        sys.meta_path.insert(0, _OpenpyxlAliasFinder())


def _remove_finder() -> None:
    sys.meta_path[:] = [
        finder for finder in sys.meta_path if not isinstance(finder, _OpenpyxlAliasFinder)
    ]


def _remove_openpyxl_modules() -> None:
    for name in list(sys.modules):
        if _is_openpyxl_name(name):
            del sys.modules[name]


def _alias_loaded_wolfxl_modules(*, force: bool) -> None:
    for name, module in list(sys.modules.items()):
        if not _is_wolfxl_name(name):
            continue
        alias = "openpyxl" + name[len("wolfxl") :]
        if force or alias not in sys.modules:
            sys.modules[alias] = module
            _attach_to_parent(alias, module)


def _attach_to_parent(fullname: str, module: ModuleType) -> None:
    if "." not in fullname:
        return
    parent_name, child_name = fullname.rsplit(".", 1)
    parent = sys.modules.get(parent_name)
    if parent is not None:
        setattr(parent, child_name, module)


def _is_openpyxl_name(name: str) -> bool:
    return name == "openpyxl" or name.startswith("openpyxl.")


def _is_wolfxl_name(name: str) -> bool:
    return name == "wolfxl" or name.startswith("wolfxl.")


def _wolfxl_name(openpyxl_name: str) -> str:
    return "wolfxl" + openpyxl_name[len("openpyxl") :]


def _module_is_wolfxl(module: Any) -> bool:
    module_name = getattr(module, "__name__", "")
    return isinstance(module_name, str) and _is_wolfxl_name(module_name)
