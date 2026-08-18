"""Tests root package.

Promoted from a namespace package (PEP 420) to a regular package so that
``tests.parity._scoring`` can be imported by absolute name from sibling test
packages — the differential writer harness in ``tests/diffwriter/`` reuses
the parity scorer for Layer 3 semantic comparison.
"""
