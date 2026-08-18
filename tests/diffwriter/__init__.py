"""Differential test harness for wolfxl's native xlsx writer.

Three diffing layers run against every case:

1. **Byte-level**: unzip both files, canonicalize XML (W3C c14n 2.0), strip
   fuzzy elements (timestamps, app name), SHA-256 each part.
2. **XML-structural**: parse to `lxml.etree`, normalize attribute order,
   sort where spec permits (rows by ``r``, cells by ``r``, ...), tree-diff.
3. **Semantic**: reuse ``tests/parity/_scoring.py`` HARD/SOFT/INFO tiers
   on both parsed workbooks.

Layer 1 is a "gold star" target (~80%). Layers 2 and 3 are ship gates.

A fourth optional layer runs LibreOffice ``soffice --headless --convert-to``
for a real-world smoke test (nightly only).
"""
