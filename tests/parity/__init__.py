"""WolfXL <-> openpyxl parity harness.

This package enforces a contract: every openpyxl API SynthGL depends on must
behave identically when imported from wolfxl. See ``openpyxl_surface.py`` for
the precise contract, and ``KNOWN_GAPS.md`` for any gaps that are tracked
rather than fixed immediately.
"""
