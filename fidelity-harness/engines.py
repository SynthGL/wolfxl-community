#!/usr/bin/env python3
"""Engine adapters for the round-trip fidelity harness.

An engine does exactly one thing: open a workbook and save it somewhere else,
changing nothing. That is the whole contract.

    round_trip(source, target) -> None

The contract is deliberately load-then-save rather than load-modify-save.
A library that rebuilds the whole package on save is not a broken adapter,
it is the behaviour under measurement. Every adapter must open the workbook
with that library's strongest available preservation settings, and must
declare those settings in `notes` so a reader can check the configuration
was fair rather than a strawman.

Adding your own engine requires no fork. Write a module exposing a
zero-argument factory that returns an Engine, then point the harness at it:

    python3 roundtrip.py corpus --engine mypackage.harness:build

Run `python3 engines.py` to print the engines available in this environment.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

MACRO_SUFFIXES = frozenset({".xlsm", ".xltm"})


class EngineUnavailable(RuntimeError):
    """Raised when an engine's library is not installed."""


class WorkbookUnsupported(RuntimeError):
    """Raised when an engine cannot open a workbook at all.

    This is reported as `unsupported` rather than as lost fidelity. Refusing
    to open a file is a different failure from opening it and silently
    discarding half of it, and the harness must not conflate the two.
    """


@dataclass(frozen=True)
class Engine:
    """One measurable save path."""

    name: str
    version: str
    round_trip: Callable[[Path, Path], None]
    notes: str = ""
    settings: dict[str, object] = field(default_factory=dict)


def _require(module_name: str, engine_name: str):
    try:
        return importlib.import_module(module_name)
    except ImportError as error:  # pragma: no cover - environment dependent
        raise EngineUnavailable(
            f"{engine_name} needs `{module_name}`; install it with `pip install {module_name}`"
        ) from error


def build_openpyxl() -> Engine:
    """openpyxl, configured for maximum preservation.

    Every preservation flag openpyxl exposes is switched on. `keep_vba` is
    applied only to macro-enabled suffixes because openpyxl raises on it for
    plain .xlsx. If a part is missing after this round trip, it is missing
    because openpyxl does not model it, not because the harness asked for a
    lossy save.
    """
    openpyxl = _require("openpyxl", "openpyxl")
    try:
        pillow = importlib.import_module("PIL")
    except ImportError as error:
        raise EngineUnavailable(
            "openpyxl comparisons require Pillow so images are not silently dropped; "
            "install it with `pip install Pillow`"
        ) from error

    settings: dict[str, object] = {
        "keep_vba": "auto (True for .xlsm/.xltm)",
        "keep_links": True,
        "rich_text": True,
        "data_only": False,
        "pillow": getattr(pillow, "__version__", "unknown"),
    }

    def round_trip(source: Path, target: Path) -> None:
        kwargs: dict[str, object] = {
            "keep_links": True,
            "rich_text": True,
            "data_only": False,
        }
        if source.suffix.lower() in MACRO_SUFFIXES:
            kwargs["keep_vba"] = True
        try:
            workbook = openpyxl.load_workbook(source, **kwargs)
        except TypeError:
            # Older openpyxl without rich_text.
            kwargs.pop("rich_text", None)
            settings["rich_text"] = "unsupported by this openpyxl version"
            workbook = openpyxl.load_workbook(source, **kwargs)
        except Exception as error:
            raise WorkbookUnsupported(f"openpyxl could not open the workbook: {error}") from error
        try:
            workbook.save(target)
        finally:
            # keep_vba retains a ZipFile on the workbook. openpyxl's normal
            # close path can leave that wrapper pointing at an already-closed
            # file, which then emits a noisy exception from ZipFile.__del__.
            vba_archive = getattr(workbook, "vba_archive", None)
            if vba_archive is not None:
                vba_archive.close()
                workbook.vba_archive = None
            close = getattr(workbook, "close", None)
            if callable(close):
                close()

    return Engine(
        name="openpyxl",
        version=getattr(openpyxl, "__version__", "unknown"),
        round_trip=round_trip,
        notes=(
            "Full-DOM read and rewrite. Opened with every preservation flag openpyxl "
            "exposes, so any loss here reflects the parts openpyxl does not model."
        ),
        settings=settings,
    )


def build_wolfxl_modify() -> Engine:
    """WolfXL in modify mode, which patches the package in place."""
    wolfxl = _require("wolfxl", "wolfxl modify mode")

    def round_trip(source: Path, target: Path) -> None:
        try:
            workbook = wolfxl.load_workbook(source, modify=True)
        except Exception as error:
            raise WorkbookUnsupported(f"wolfxl could not open the workbook: {error}") from error
        try:
            workbook.save(target)
        finally:
            close = getattr(workbook, "close", None)
            if callable(close):
                close()

    return Engine(
        name="wolfxl-modify",
        version=getattr(wolfxl, "__version__", "unknown"),
        round_trip=round_trip,
        notes="Surgical package patching. Parts that were not edited are carried over.",
        settings={"modify": True},
    )




BUILTIN_ENGINES: dict[str, Callable[[], Engine]] = {
    "openpyxl": build_openpyxl,
    "wolfxl": build_wolfxl_modify,
    "wolfxl-modify": build_wolfxl_modify,
}


def load_engine(spec: str) -> Engine:
    """Resolve an engine from a builtin name or a `module:factory` path."""
    if spec in BUILTIN_ENGINES:
        return BUILTIN_ENGINES[spec]()
    if ":" not in spec:
        known = ", ".join(sorted(BUILTIN_ENGINES))
        raise EngineUnavailable(
            f"unknown engine {spec!r}; use one of [{known}] or a `module:factory` path"
        )
    module_name, _, factory_name = spec.partition(":")
    try:
        module = importlib.import_module(module_name)
    except ImportError as error:
        raise EngineUnavailable(f"cannot import engine module {module_name!r}: {error}") from error
    try:
        factory = getattr(module, factory_name)
    except AttributeError as error:
        raise EngineUnavailable(
            f"{module_name!r} has no attribute {factory_name!r}"
        ) from error
    engine = factory()
    if not isinstance(engine, Engine):
        raise EngineUnavailable(
            f"{spec} returned {type(engine).__name__}, expected an engines.Engine"
        )
    return engine


def available_engines() -> list[tuple[str, str]]:
    """Report which builtin engines can actually run here, newest first."""
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for spec, factory in BUILTIN_ENGINES.items():
        try:
            engine = factory()
        except EngineUnavailable as error:
            out.append((spec, f"unavailable: {error}"))
            continue
        if engine.name in seen:
            out.append((spec, f"alias of {engine.name}"))
            continue
        seen.add(engine.name)
        out.append((spec, f"{engine.name} {engine.version}"))
    return out


if __name__ == "__main__":
    for spec, status in available_engines():
        print(f"{spec:<16} {status}")
