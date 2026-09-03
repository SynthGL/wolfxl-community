"""Phase timing and progress emission for the OOXML package fidelity audit.

Internal to the OOXML fidelity audit. The public surface stays
``wolfxl.operations._ooxml_fidelity``.
"""

from __future__ import annotations

import sys
import time


def _run_audit_phase(
    progress_label: str | None,
    timings: dict[str, float] | None,
    phase: str,
    func,
):
    _emit_audit_progress(progress_label, phase, "", "start")
    start = time.perf_counter()
    try:
        return func()
    finally:
        if timings is not None:
            timings[phase] = round(time.perf_counter() - start, 6)
        _emit_audit_progress(progress_label, phase, "", "done")


def _emit_audit_progress(
    progress_label: str | None,
    phase_prefix: str,
    phase: str,
    event: str,
) -> None:
    if progress_label is None:
        return
    label = phase_prefix if not phase else f"{phase_prefix}.{phase}"
    print(f"[{progress_label}] audit {label} {event}", file=sys.stderr, flush=True)
