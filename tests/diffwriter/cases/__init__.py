"""Hand-authored cases for the differential writer harness.

Each module exports ``CASES: list[tuple[str, Callable[[Workbook], None]]]``.
The harness driver in ``tests/diffwriter/test_cases.py`` discovers every
case across this package, parameterizes a pytest test per case, and runs
the 3-layer diff between oracle and native outputs.

Cases are scoped tightly: each one exercises one OOXML construct. Keep
them small (~30 LOC) — comprehensive feature coverage comes from the count
of cases, not the depth of any single one.
"""
from __future__ import annotations


# Case IDs whose Layer 4 (LibreOffice headless smoke) round-trip is expected
# to fail and should be marked ``xfail`` rather than blocking the layer.
# Populate as known LibreOffice-side incompatibilities surface — the test
# scaffolding consults this dict so the case still runs (proving we still
# emit *something*) but the assertion is non-fatal.
#
# Format: ``case_id: human-readable reason``. The reason should point at
# either an upstream LO bug, an OOXML edge case LO mishandles, or an
# explicit "this is by design" note.
_SOFFICE_XFAIL_CASES: dict[str, str] = {
    # case_id: reason (empty until a known LO failure surfaces)
}
