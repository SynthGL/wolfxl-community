"""Shared helpers for audited openpyxl compatibility tests."""

from __future__ import annotations

import importlib
import pkgutil


ALLOWED_UPSTREAM_IMPORT_ERRORS = [
    "openpyxl.utils.dataframe: ModuleNotFoundError: No module named 'numpy'",
]


def iter_importable_openpyxl_modules(*, include_root: bool = False) -> list[str]:
    roots = [
        "cell",
        "chart",
        "chartsheet",
        "comments",
        "descriptors",
        "drawing",
        "formatting",
        "packaging",
        "reader",
        "styles",
        "utils",
        "workbook",
        "worksheet",
        "writer",
        "xml",
    ]
    modules = ["openpyxl"] if include_root else []
    upstream_import_errors: list[str] = []
    for root in roots:
        pkgname = f"openpyxl.{root}"
        try:
            pkg = importlib.import_module(pkgname)
        except Exception as exc:  # noqa: BLE001 - optional upstream deps can fail import
            upstream_import_errors.append(f"{pkgname}: {type(exc).__name__}: {exc}")
            continue
        root_modules = [pkgname]
        if hasattr(pkg, "__path__"):
            root_modules.extend(
                m.name for m in pkgutil.walk_packages(pkg.__path__, pkgname + ".")
            )
        for module in sorted(set(root_modules)):
            try:
                importlib.import_module(module)
            except Exception as exc:  # noqa: BLE001 - see assertion below
                upstream_import_errors.append(
                    f"{module}: {type(exc).__name__}: {exc}"
                )
                continue
            modules.append(module)

    unexpected_errors = [
        error for error in upstream_import_errors
        if error not in ALLOWED_UPSTREAM_IMPORT_ERRORS
    ]
    assert unexpected_errors == []
    return modules


def iter_package_wide_openpyxl_modules(*, include_root: bool = True) -> list[str]:
    """Return every upstream openpyxl module that imports in this environment."""
    import openpyxl

    modules = ["openpyxl"] if include_root else []
    upstream_import_errors: list[str] = []
    for module in pkgutil.walk_packages(openpyxl.__path__, openpyxl.__name__ + "."):
        try:
            importlib.import_module(module.name)
        except Exception as exc:  # noqa: BLE001 - aggregate optional dependency failures
            upstream_import_errors.append(f"{module.name}: {type(exc).__name__}: {exc}")
        else:
            modules.append(module.name)

    unexpected_errors = [
        error for error in upstream_import_errors
        if error not in ALLOWED_UPSTREAM_IMPORT_ERRORS
    ]
    assert unexpected_errors == []
    return sorted(set(modules))
