# Contributing to WolfXL Community

Thank you for helping improve WolfXL Community. This document explains what
kinds of changes this repository accepts and the certification every commit
needs.

## Scope of this repository

WolfXL Community is the maintained 2.0 generation. It receives:

- Correctness fixes
- Security fixes
- Documentation and benchmark reproducibility improvements
- Test coverage for existing 2.0 behavior

New engines, expanded compatibility work, and production operations ship in
WolfXL Commercial and are not developed in this repository. If you are unsure
whether a change fits, open an issue first and ask before writing code.

## Licensing of contributions

WolfXL Community is licensed under the [MIT License](LICENSE). By submitting a
contribution you agree that:

1. Your contribution is licensed under the same MIT License as the project
   (inbound = outbound).
2. Because the MIT License permits commercial use and sublicensing, your
   contribution may also be incorporated, with its copyright notice preserved,
   into commercial WolfXL editions maintained by SynthGL, Inc.

There is no copyright assignment. You retain the copyright to your
contribution.

## Developer Certificate of Origin

Every commit must be signed off under the
[Developer Certificate of Origin 1.1](https://developercertificate.org/). The
sign-off certifies that you wrote the change or otherwise have the right to
submit it under the project license.

Add the sign-off with:

```bash
git commit -s
```

which appends a line like:

```text
Signed-off-by: Your Name <your-email@example.com>
```

to the commit message. The name and email must identify a real point of
contact; anonymous or pseudonymous sign-offs that cannot be reached are not
accepted. Pull requests containing commits without a valid `Signed-off-by`
line will not be merged.

## Development setup

Prerequisites: a supported CPython, Rust, and `maturin`.

```bash
python -m pip install maturin pytest defusedxml openpyxl Pillow
maturin develop
pytest tests/test_community_distribution.py -q
```

Run the openpyxl parity tests when touching API-visible behavior:

```bash
pytest tests/parity -q
```

## Pull requests

- Keep each pull request to one logical change.
- Include a test that fails without the fix for any behavior change.
- Benchmark claims must come from the committed harness in `benchmarks/` with
  raw results included; see `benchmarks/README.md` for the reproduction
  procedure.
- Do not update generated chart assets by hand; regenerate them with
  `benchmarks/render_charts.py` from committed results JSON.
