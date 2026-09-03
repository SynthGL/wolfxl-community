"""Canonical JSON command adapter for verified workbook operations."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping, NoReturn, Sequence
from zipfile import BadZipFile

from wolfxl.comparison import WorkbookComparison, WorkbookIdentity
from . import guard

EXIT_SUCCESS = 0
EXIT_INTERNAL_ERROR = 1
EXIT_INVALID_REQUEST = 2
EXIT_OPERATION_FAILED = 5


class OperationError(Exception):
    def __init__(
        self,
        category: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.message = message
        self.details = dict(details) if details else {}

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "category": self.category,
            "message": self.message,
        }
        if self.details:
            payload["details"] = dict(self.details)
        return payload


class _JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        del message
        raise OperationError(
            "invalid_request",
            "CLI arguments are invalid.",
            details={"field": "arguments"},
        )


def _parser() -> argparse.ArgumentParser:
    parser = _JsonArgumentParser(
        prog="wolfxl-ops",
        description="Inspect, compare, and guard workbooks against OOXML regressions.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    guard_parser = commands.add_parser(
        "guard",
        help="compare two workbooks against a bounded Guard policy",
    )
    guard_parser.add_argument(
        "before_pos",
        nargs="?",
        type=Path,
        metavar="BEFORE",
        help="baseline workbook path",
    )
    guard_parser.add_argument(
        "after_pos",
        nargs="?",
        type=Path,
        metavar="AFTER",
        help="compared workbook path",
    )
    guard_parser.add_argument("--before", type=Path, help="baseline workbook path")
    guard_parser.add_argument("--after", type=Path, help="compared workbook path")
    guard_parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="output JSON report path; omitted skips writing report file",
    )
    guard_parser.add_argument(
        "--policy",
        type=Path,
        default=None,
        help="Guard policy JSON path; omitted selects the Guard default policy",
    )

    guard_bundle_parser = commands.add_parser(
        "guard-bundle",
        help="write a privacy-safe support bundle for a Guard comparison",
    )
    guard_bundle_parser.add_argument("before_pos", nargs="?", type=Path, metavar="BEFORE")
    guard_bundle_parser.add_argument("after_pos", nargs="?", type=Path, metavar="AFTER")
    guard_bundle_parser.add_argument("--before", type=Path)
    guard_bundle_parser.add_argument("--after", type=Path)
    guard_bundle_parser.add_argument("--output", type=Path, required=True)
    guard_bundle_parser.add_argument("--policy", type=Path, default=None)

    compare_parser = commands.add_parser(
        "compare",
        help="compare two workbooks in memory without writing a report file",
    )
    compare_parser.add_argument(
        "before_pos",
        nargs="?",
        type=Path,
        metavar="BEFORE",
        help="baseline workbook path",
    )
    compare_parser.add_argument(
        "after_pos",
        nargs="?",
        type=Path,
        metavar="AFTER",
        help="compared workbook path",
    )
    compare_parser.add_argument("--before", type=Path, help="baseline workbook path")
    compare_parser.add_argument("--after", type=Path, help="compared workbook path")
    compare_parser.add_argument(
        "--policy",
        type=Path,
        default=None,
        help="Guard policy JSON path; omitted selects the Guard default policy",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one command and emit exactly one canonical JSON document."""
    parser = _parser()
    try:
        arguments = parser.parse_args(argv)
        if arguments.command == "guard":
            payload, exit_code = _run_guard_command(arguments)
        elif arguments.command == "guard-bundle":
            payload, exit_code = _run_guard_bundle_command(arguments)
        elif arguments.command == "compare":
            payload, exit_code = _run_compare_command(arguments)
        else:
            raise OperationError(
                "invalid_request",
                f"Unknown command: {arguments.command}",
                details={"command": arguments.command},
            )
    except OperationError as error:
        payload = _error_document(error)
        exit_code = _error_exit_code(error.category)
    except Exception as error:
        payload = _error_document(
            OperationError(
                "internal_error",
                "Internal error during operation execution.",
                details={"exception": type(error).__name__},
            )
        )
        exit_code = EXIT_INTERNAL_ERROR

    print(_canonical_json(payload))
    return exit_code


def _run_guard_command(arguments: argparse.Namespace) -> tuple[dict[str, Any], int]:
    before = arguments.before or arguments.before_pos
    after = arguments.after or arguments.after_pos
    if before is None or after is None:
        raise OperationError(
            "invalid_request",
            "Both before and after workbooks must be specified.",
            details={"field": "workbooks"},
        )
    try:
        policy = None if arguments.policy is None else guard.load_guard_policy(arguments.policy)
        report = guard.run_guard(
            before=before,
            after=after,
            output=arguments.output,
            policy=policy,
        )
    except (guard.GuardInputError, BadZipFile) as exc:
        raise OperationError(
            "invalid_request",
            str(exc),
        ) from exc
    except OSError as exc:
        raise OperationError(
            "cannot_scan",
            "Workbook Guard input or output could not be read or written.",
            details={"exception": type(exc).__name__},
        ) from exc

    payload = {
        "schema_version": guard.SCHEMA_VERSION,
        "status": report["status"],
        "issue_count": report["fidelity_audit"]["issue_count"],
        "output": arguments.output.name if arguments.output else None,
    }
    exit_code = EXIT_SUCCESS if report["status"] == "passed" else EXIT_OPERATION_FAILED
    return payload, exit_code


def _run_guard_bundle_command(arguments: argparse.Namespace) -> tuple[dict[str, Any], int]:
    before = arguments.before or arguments.before_pos
    after = arguments.after or arguments.after_pos
    if before is None or after is None:
        raise OperationError(
            "invalid_request",
            "Both before and after workbooks must be specified.",
            details={"field": "workbooks"},
        )
    try:
        bundle = guard.run_guard_support_bundle(
            before=before,
            after=after,
            output=arguments.output,
            policy=arguments.policy,
        )
    except (guard.GuardInputError, BadZipFile) as exc:
        raise OperationError(
            "invalid_request",
            str(exc),
        ) from exc
    except OSError as exc:
        raise OperationError(
            "cannot_scan",
            "Workbook Guard support bundle could not be written.",
            details={"exception": type(exc).__name__},
        ) from exc
    return bundle, int(bundle["exit_status"]["code"])


def _run_compare_command(arguments: argparse.Namespace) -> tuple[dict[str, Any], int]:
    before = arguments.before or arguments.before_pos
    after = arguments.after or arguments.after_pos
    if before is None or after is None:
        raise OperationError(
            "invalid_request",
            "Both before and after workbooks must be specified.",
            details={"field": "workbooks"},
        )
    try:
        policy = None if arguments.policy is None else guard.load_guard_policy(arguments.policy)
        comparison = guard.compare_workbooks(before, after, policy=policy)
    except (guard.GuardInputError, BadZipFile) as exc:
        raise OperationError("invalid_request", str(exc), details={"field": "workbooks"}) from exc
    except (TypeError, ValueError) as exc:
        raise OperationError("invalid_request", str(exc), details={"field": "policy"}) from exc
    except OSError as exc:
        raise OperationError(
            "cannot_scan",
            "Workbook comparison inputs could not be read.",
            details={"exception": type(exc).__name__},
        ) from exc

    result = comparison.to_dict()
    return (
        _workflow_document("compare", str(result["status"]), result),
        EXIT_SUCCESS if bool(result["passed"]) else EXIT_OPERATION_FAILED,
    )


def _workflow_document(
    command: str,
    status: str,
    result: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "command": command,
        "status": status,
        "result": dict(result),
    }


def _error_document(error: OperationError) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "error",
        "error": error.to_dict(),
    }


def _error_exit_code(category: str) -> int:
    if category == "invalid_request":
        return EXIT_INVALID_REQUEST
    if category == "internal_error":
        return EXIT_INTERNAL_ERROR
    return EXIT_OPERATION_FAILED


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


__all__ = [
    "EXIT_INTERNAL_ERROR",
    "EXIT_INVALID_REQUEST",
    "EXIT_OPERATION_FAILED",
    "EXIT_SUCCESS",
    "main",
]
