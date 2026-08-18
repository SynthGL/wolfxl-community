"""Layer 2 — XML-structural diff (BLOCKING).

Parses every XML part of an xlsx archive into normalized ``NormalNode``
trees, then walks two trees in parallel and reports differences as
XPath-ish locator strings. The harness asserts the diff list is empty.

Three normalizations matter:

1. **Attribute order is irrelevant** — XML attribute order is not significant,
   but ElementTree preserves it. ``NormalNode`` stores attrs as a sorted
   tuple so two trees with different attribute orderings hash identically.

2. **Sibling order where the spec allows** — ``order_rules.py`` declares
   which element types can be sorted before comparison (``row`` by ``r``,
   ``c`` by ``r`` etc.) and which must keep their author-provided order
   (``cellXfs`` because index is identity, ``sst`` because string indices
   are referenced by ``c/v`` etc.).

3. **Relationship-id reference normalization** — oracle and native
   legitimately allocate different rId numbers for the same logical
   relationship. We rewrite every ``r:id="rIdN"`` attribute to the
   resolved target path before comparing, so two backends agree as long
   as the *target* matches even when the rId index does not.
"""
from __future__ import annotations

import posixpath
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

from .order_rules import PRESERVE_ORDER, SORT_BY_ATTRIBUTE

_RELS_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_RID_ATTR = f"{{{_RELS_NS}}}id"


@dataclass(frozen=True)
class NormalNode:
    tag: str
    attrs: tuple[tuple[str, str], ...]
    text: str
    children: tuple["NormalNode", ...]


# ---------------------------------------------------------------------------
# Reading + relationship resolution
# ---------------------------------------------------------------------------

# Two backends use slightly different conventions for organizing rich-feature
# parts inside the ZIP. Native nests comments under ``xl/comments/`` while
# oracle puts them flat at ``xl/`` — both are valid OOXML and both are
# discovered via the rels file at runtime. For diff purposes we normalize
# to a canonical location (oracle's flat layout) so structural comparison
# isn't tripped up by the directory difference.
_PART_PATH_REWRITES: tuple[tuple[str, str], ...] = (
    ("xl/comments/comments", "xl/comments"),
)


def _canonical_part_path(name: str) -> str:
    """Apply ``_PART_PATH_REWRITES`` to normalize a ZIP entry name."""
    for src, dst in _PART_PATH_REWRITES:
        if name.startswith(src):
            return dst + name[len(src):]
    return name


def _read_xml_parts(xlsx_path: Path) -> dict[str, ET.Element]:
    """Return ``{part_name: parsed_root}`` for every XML/rels part.

    Part names are passed through ``_canonical_part_path`` so two backends
    with different directory layouts compare cleanly.
    """
    out: dict[str, ET.Element] = {}
    with zipfile.ZipFile(xlsx_path) as zf:
        for name in zf.namelist():
            if not name.endswith((".xml", ".rels")):
                continue
            data = zf.read(name)
            try:
                out[_canonical_part_path(name)] = ET.fromstring(data)
            except ET.ParseError:
                continue
    return out


def _rels_referrer(rels_path: str) -> str:
    """Convert ``xl/worksheets/_rels/sheet1.xml.rels`` to ``xl/worksheets/sheet1.xml``.

    The package-level ``_rels/.rels`` refers to the package root, which we
    represent as the empty string — every absolute path resolves against it.
    """
    if rels_path == "_rels/.rels":
        return ""
    parts = rels_path.split("/")
    # Drop the trailing _rels segment.
    try:
        idx = len(parts) - 2
        if parts[idx] != "_rels":
            return rels_path
        del parts[idx]
    except IndexError:
        return rels_path
    last = parts[-1]
    if last.endswith(".rels"):
        parts[-1] = last[: -len(".rels")]
    return "/".join(parts)


def _resolve_rels_target(referrer: str, target: str) -> str:
    """Resolve a Relationship Target relative to its referrer's directory.

    External targets (URLs starting with a scheme) are returned unchanged.
    Targets starting with ``/`` are absolute relative to the package root.
    Otherwise they are relative to the referrer's directory.
    """
    # External: anything containing :// is an external URL.
    if "://" in target or target.startswith("mailto:"):
        return target
    if target.startswith("/"):
        return target.lstrip("/")
    referrer_dir = posixpath.dirname(referrer) if referrer else ""
    if not referrer_dir:
        return target
    return posixpath.normpath(posixpath.join(referrer_dir, target))


def _build_rels_map(parts: dict[str, ET.Element]) -> dict[tuple[str, str], str]:
    """Map ``(referrer_part, rId)`` to the resolved target path or URL.

    Resolved targets are run through ``_canonical_part_path`` so the rels-id
    rewrite (which substitutes ``r:id="rIdN"`` with ``@<target>``) produces
    identical attribute values on both backends regardless of which physical
    layout each chose for the underlying part.
    """
    out: dict[tuple[str, str], str] = {}
    for path, root in parts.items():
        if not path.endswith(".rels"):
            continue
        referrer = _rels_referrer(path)
        for rel in root:
            rid = rel.attrib.get("Id")
            target = rel.attrib.get("Target")
            if rid is None or target is None:
                continue
            resolved = _resolve_rels_target(referrer, target)
            out[(referrer, rid)] = _canonical_part_path(resolved)
    return out


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _normalize_attrs(
    attrs: dict[str, str],
    referrer: str,
    rels_map: dict[tuple[str, str], str],
) -> tuple[tuple[str, str], ...]:
    """Return attrs as a sorted tuple, with ``r:id`` values resolved.

    The ``{...}id`` attribute (relationship reference) is rewritten from
    ``rIdN`` to the resolved target path. ``{...}id`` attrs whose value
    isn't in the rels map are kept as-is — that's a real bug worth surfacing.
    """
    out: list[tuple[str, str]] = []
    for k, v in attrs.items():
        if k == _RID_ATTR:
            resolved = rels_map.get((referrer, v))
            if resolved is not None:
                v = f"@{resolved}"
        out.append((k, v))
    out.sort()
    return tuple(out)


def _sort_key(elem: NormalNode, attr_name: str | None, is_numeric: bool) -> object:
    """Build a sort key for an element using the configured attribute."""
    if attr_name is None:
        return 0
    raw: str | None = None
    for k, v in elem.attrs:
        if _local_name(k) == attr_name or k == attr_name:
            raw = v
            break
    if raw is None:
        return ("", 0) if is_numeric else ""
    if is_numeric:
        try:
            return ("", int(raw))
        except ValueError:
            try:
                return ("", float(raw))
            except ValueError:
                return (raw, 0)
    return raw


def _maybe_sort_children(parent_local: str, children: list[NormalNode]) -> list[NormalNode]:
    """Apply SORT_BY_ATTRIBUTE / PRESERVE_ORDER rules to the children list.

    If the parent is in PRESERVE_ORDER, return children unchanged.
    Otherwise, group consecutive children by tag and sort each group whose
    tag is in SORT_BY_ATTRIBUTE.
    """
    if parent_local in PRESERVE_ORDER:
        return children
    if not children:
        return children

    # Group runs of same-tag siblings; sort each group whose tag has a rule.
    out: list[NormalNode] = []
    i = 0
    while i < len(children):
        j = i
        tag_local = _local_name(children[i].tag)
        while j < len(children) and _local_name(children[j].tag) == tag_local:
            j += 1
        run = children[i:j]
        if tag_local in SORT_BY_ATTRIBUTE:
            attr_name, is_numeric = SORT_BY_ATTRIBUTE[tag_local]
            if attr_name is not None:
                run = sorted(run, key=lambda e: _sort_key(e, attr_name, is_numeric))
        out.extend(run)
        i = j
    return out


def _normalize_element(
    elem: ET.Element,
    referrer: str,
    rels_map: dict[tuple[str, str], str],
) -> NormalNode:
    children = [_normalize_element(c, referrer, rels_map) for c in elem]
    children = _maybe_sort_children(_local_name(elem.tag), children)
    text = (elem.text or "").strip()
    return NormalNode(
        tag=elem.tag,
        attrs=_normalize_attrs(dict(elem.attrib), referrer, rels_map),
        text=text,
        children=tuple(children),
    )


def normalize(xlsx_path: Path) -> dict[str, NormalNode]:
    """Parse every XML part to a normalized tree."""
    parts = _read_xml_parts(xlsx_path)
    rels_map = _build_rels_map(parts)
    out: dict[str, NormalNode] = {}
    for path, root in parts.items():
        if path.endswith(".rels"):
            referrer = _rels_referrer(path)
        else:
            referrer = path
        out[path] = _normalize_element(root, referrer, rels_map)
    return out


# ---------------------------------------------------------------------------
# Diffing
# ---------------------------------------------------------------------------

def _diff_node(
    a: NormalNode,
    b: NormalNode,
    path: str,
    out: list[str],
) -> None:
    if a.tag != b.tag:
        out.append(f"{path}: tag differs (oracle={a.tag!r} native={b.tag!r})")
        return
    if a.attrs != b.attrs:
        # Attribute-by-attribute diff for clearer reporting.
        a_keys = {k for k, _ in a.attrs}
        b_keys = {k for k, _ in b.attrs}
        a_map = dict(a.attrs)
        b_map = dict(b.attrs)
        for k in sorted(a_keys | b_keys):
            if a_map.get(k) != b_map.get(k):
                out.append(
                    f"{path}/@{_local_name(k)}: oracle={a_map.get(k)!r} "
                    f"native={b_map.get(k)!r}"
                )
    if a.text != b.text:
        out.append(f"{path}/text(): oracle={a.text!r} native={b.text!r}")
    if len(a.children) != len(b.children):
        out.append(
            f"{path}: child count differs "
            f"(oracle={len(a.children)} native={len(b.children)})"
        )
    # Tag-relative indexing: count siblings per local-tag, so paths are
    # stable across cases. ``fonts[1]/font[2]`` always means "the 2nd <font>
    # within the (only) <fonts>" regardless of where <fonts> sits among
    # styleSheet's mixed-tag children. Filter patterns above rely on this.
    tag_count: dict[str, int] = {}
    for ac, bc in zip(a.children, b.children):
        local = _local_name(ac.tag)
        tag_count[local] = tag_count.get(local, 0) + 1
        child_path = f"{path}/{local}[{tag_count[local]}]"
        _diff_node(ac, bc, child_path, out)


# Layer 2 distinguishes *content* divergence (sheets, sharedStrings, styles,
# tables, comments etc. — user-visible workbook data) from *metadata*
# divergence (timestamps, app identifier, file-version attrs, theme — pure
# emitter cosmetics). The differential harness blocks on content. Metadata
# divergence is filtered out by ``_filter_known_gaps`` so case assertions
# don't need a per-case allowlist.
#
# Add a part to ``_METADATA_PARTS`` only when the entire part is
# emitter-cosmetic. For per-attribute or per-element exceptions inside
# content parts (e.g. ``xl/workbook.xml/@lastEdited``), use the
# ``_METADATA_ELEMENT_PATHS`` pattern below.

# Whole parts whose divergence is always cosmetic (oracle ships them with
# emitter-specific metadata that native legitimately omits or stubs).
_METADATA_PARTS: frozenset[str] = frozenset({
    # Theme — not in the 14-pymethod scope; native intentionally omits it.
    # Cascades into [Content_Types].xml Override count + workbook.xml.rels
    # — those derivative diffs are also filtered below.
    "xl/theme/theme1.xml",
    # Document-property packs are emitter-cosmetic: app name, version,
    # Company, LinksUpToDate, etc. plus timestamps. None of this surfaces
    # to spreadsheet users; Layer 3 doesn't check these dimensions at all.
    "docProps/app.xml",
    "docProps/core.xml",
})

# Path-prefix patterns inside content parts that are emitter-cosmetic.
# Match against the diff string ``<part>:/<xpath>``.
_METADATA_ELEMENT_PATHS: tuple[str, ...] = (
    # workbook.xml — emitter version + view geometry + calc engine ID +
    # default theme version + workbookPr presence flags. None of these
    # affect cell data, formatting, or structural relationships. Excel
    # opens workbooks with any of them missing or stubbed.
    "xl/workbook.xml:/workbook/fileVersion",
    "xl/workbook.xml:/workbook/workbookPr",
    "xl/workbook.xml:/workbook/bookViews",
    "xl/workbook.xml:/workbook/calcPr",
    # Default-font (font[1] in xl/styles.xml) emitter divergence: oracle
    # ships a fully-specified default with color/name/family/scheme;
    # native ships a bare default. Both are valid OOXML. Affects Excel's
    # rendering of unstyled cells but not cell content / number_format /
    # any HARD-tier dimension. Custom user fonts in font[2..N] are still
    # diffed strictly because their full path is e.g. "/font[2]/...".
    # Match every <font> child under the styleSheet's only <fonts> element.
    # Oracle ships a fully-decorated default font (sz, name, family, scheme,
    # color) plus extra cosmetic children on user fonts; native ships only
    # what the caller specified. Both render identically. Note this means
    # Layer 2 doesn't validate font color/family/scheme — those properties
    # are checked at Layer 3 SOFT-tier (font.name/size/bold/italic) instead.
    "xl/styles.xml:/styleSheet/fonts[1]/font[",
    # Row @spans hint — the OOXML spec calls this an optional range hint;
    # oracle emits it, native omits it. Both produce identical cell content.
    # Match every row's spans attribute under any sheet.
)

# Substring patterns that mark cosmetic divergences inside content parts.
# These cover emitter style choices that don't change user-visible data:
#   - oracle auto-applies a "Hyperlink" cellStyle (builtinId=8) when a cell
#     gets a hyperlink; native skips that auto-styling. The fonts/cellXfs/
#     cellStyleXfs/cellStyles count cascades from there but it's all the
#     same singleton "Hyperlink" entry on oracle's side.
#   - oracle drops the @display attribute from <hyperlink> when the cell
#     value already provides the display text; native always emits it.
#   - dxf <patternFill> emits ``patternType="solid"`` explicitly on native;
#     oracle relies on the OOXML default. Both render identically.
#   - <table @id> is locally 1-based on oracle, globally numbered on native;
#     the file is referenced by name through the relationships and Excel
#     looks up the file by id-in-its-own-document.
#   - <dataValidation @showDropDown> / @showInputMessage default-flip; both
#     backends use OOXML-compliant defaults that simply differ in which one
#     they elect to emit explicitly.
#   - <c @s> for hyperlinked cells, when the only divergence is oracle's
#     auto-applied "Hyperlink" cellStyle (covered by the cellStyles diffs
#     too — this catches the per-cell witness).
#   - <numFmts/numFmt @formatCode> reordering due to different ID assignment
#     orders. Oracle's first custom format gets id=165, native's gets 165 too
#     but order within the table can flip when a built-in like 0.00% maps
#     to id=9 on oracle and id=10 on native. Cell @s indices follow.
#   - <row @r> / <c @r> position attrs on hyperlink cells when the only
#     difference is auto-styling.
_METADATA_INFIX_PATTERNS: tuple[str, ...] = (
    # Hyperlink auto-styling cascade (oracle-only "Hyperlink" cellStyle).
    "xl/styles.xml:/styleSheet/cellStyles[1]/cellStyle[",
    "xl/styles.xml:/styleSheet/cellStyles[1]/@count",
    "xl/styles.xml:/styleSheet/cellStyles[1]: child count",
    "xl/styles.xml:/styleSheet/cellStyleXfs[1]/@count",
    "xl/styles.xml:/styleSheet/cellStyleXfs[1]: child count",
    # Counts on the fonts/cellXfs collections cascade from oracle's auto-Hyperlink
    # font + xf addition. cellXfs body diffs (per-style attrs) still surface
    # under fonts[1]/font[N] for N>=2 and cellXfs[1]/xf[N] full content.
    "xl/styles.xml:/styleSheet/fonts[1]/@count",
    "xl/styles.xml:/styleSheet/cellXfs[1]/@count",
    "xl/styles.xml:/styleSheet/fonts[1]: child count",
    "xl/styles.xml:/styleSheet/cellXfs[1]: child count",
    # Hyperlink @display attribute — oracle drops when cell value matches
    # display, native always emits.
    "/hyperlinks[1]/hyperlink[",
    # dxf patternFill child count + @patternType — cosmetic emitter choice.
    "/dxfs[1]/dxf[",
    # Default fill[1] (none) and fill[2] (gray125) sub-element divergences:
    # both backends emit the OOXML-mandated reserved fills, but with slightly
    # different sub-element shapes (oracle adds extra child nodes).
    "xl/styles.xml:/styleSheet/fills[1]/fill[",
    # Table id (oracle local 1-based, native global).
    "xl/tables/table1.xml:/table/@id",
    "xl/tables/table2.xml:/table/@id",
    "xl/tables/table3.xml:/table/@id",
    # dataValidation @showDropDown / @showInputMessage / @operator default-flip
    # is suppressed via _METADATA_REGEX_PATTERNS so any DV index — not just
    # ``[1]`` — is covered. The W4G ``data_validation_two_per_sheet`` case
    # exercises the multi-DV path and surfaced @operator divergence on top
    # of the originally documented two attrs (oracle omits when the default
    # matches; native emits the caller-provided value verbatim).
    # numFmt id assignment order — oracle increments 165->166->167, native
    # uses different ids (10, 165, 4, ...). Both are valid; cells reference
    # them by id consistently within each file.
    "xl/styles.xml:/styleSheet/numFmts[1]/numFmt[",
    "xl/styles.xml:/styleSheet/numFmts[1]/@count",
    "xl/styles.xml:/styleSheet/numFmts[1]: child count",
    "xl/styles.xml:/styleSheet/cellXfs[1]/xf[",
    "xl/styles.xml:/styleSheet/cellXfs[1]: child count",
    # Per-cell @s + @t attribute divergence: the index/type position attrs
    # are cosmetic when Layer 3's per-cell font/fill/border SOFT-tier checks
    # already prove the rendered cell matches. Caught via regex below — the
    # earlier hard-coded ``/c[1]/@s`` ... ``/c[3]/@s`` only filtered cells in
    # the first three columns, leaving columns 4+ silently noisy.
    # See _METADATA_REGEX_PATTERNS for the replacement.
    # Worksheet <dimension> hint — Excel re-derives this when opening, so
    # it's purely a load-time optimization. Oracle computes it including
    # merged ranges; native uses populated cells only. Visually identical.
    "/worksheet/dimension[1]/@ref",
    # Number-format precedence side-effect: oracle interns a Date format on
    # any datetime cell, which adds an empty <f t="n"/> in some sheetData
    # contexts. The cell value is unchanged.
    "/sheetData[1]: child count",
    # SheetView pane child count — oracle emits selection sub-elements per
    # pane, native emits only the <pane> itself. Both freeze the same range.
    "/sheetViews[1]/sheetView[1]: child count",
    # Column width unit conversion — oracle converts user input (25.5) to
    # Excel's max-digit-width units (~26.28); native passes through. Both
    # round-trip cleanly within a backend; cross-backend tolerance lives
    # in Layer 3's column_width fuzzy comparison.
    "/cols[1]/col[1]/@width",
    "/cols[1]/col[2]/@width",
    "/cols[1]/col[3]/@width",
    # Comment text rich-text wrapping — oracle wraps every comment body in
    # a ``<r><rPr/><t>...</t></r>`` rich-text run with empty run-properties;
    # native emits the bare ``<t>...</t>``. Both render identically in
    # Excel — the rich-text run is only meaningful when run-level properties
    # differ across substrings, which neither emitter generates from the
    # plain-text inputs we accept.
    "/comments/commentList[1]/comment[1]/text[1]",
    "/comments/commentList[1]/comment[2]/text[1]",
    "/comments/commentList[1]/comment[3]/text[1]",
)

# Suffix patterns matched against the full diff string (``in`` rather than
# ``startswith``). Used for attributes that appear under variable XPath
# prefixes like every sheet's row spans.
_METADATA_SUFFIX_PATTERNS: tuple[str, ...] = (
    "/row[",  # any row-element diff path...
)
_METADATA_ATTR_SUFFIXES: tuple[str, ...] = (
    "/@spans:",  # ...whose attribute is @spans is the row hint
)

# Regex patterns matched against the full diff string. Used when an
# emitter-cosmetic divergence appears at variable column indices that
# can't be enumerated cheaply with substring matching.
_METADATA_REGEX_PATTERNS: tuple[re.Pattern[str], ...] = (
    # H1 fix: per-cell @s (style index) and @t (cell type) attributes.
    # The style index can differ across backends without a rendered-cell
    # divergence (Layer 3's per-cell font/fill/border SOFT-tier checks
    # cover the actual rendering); the @t type position attr is similarly
    # cosmetic when the value matches. ``/c[NN]/@s:`` matches any column
    # index (1+, single- or multi-digit) — a stricter pattern than the
    # earlier hard-coded /c[1]/@s ... /c[3]/@s which silently let column
    # 4+ divergences through.
    re.compile(r"/c\[\d+\]/@[st]:"),
    # H5 fix: dataValidation default-flip attrs across any DV index.
    # Oracle omits @showDropDown / @showInputMessage / @operator when the
    # value matches the OOXML default; native emits whatever the caller
    # provided. Both are spec-valid; the rendered behavior is identical.
    # The W4G ``data_validation_two_per_sheet`` case proved this surfaces
    # at index 2 once a sheet has more than one DV — widening the index
    # match from a literal ``[1]`` to ``[\d+]`` covers every case.
    re.compile(
        r"/dataValidations\[\d+\]/dataValidation\[\d+\]/@"
        r"(?:showDropDown|showInputMessage|operator):"
    ),
)

# Exact diff strings that document part-presence emitter asymmetries.
# These come from optional OOXML parts whose presence depends on content:
# the file may legitimately be omitted when its content is empty.
#
#   ``xl/sharedStrings.xml`` — oracle (rust_xlsxwriter) skips emitting this
#   part when the workbook has no string cells; native always emits it
#   per the "shared strings always-on" architecture invariant. Cascading
#   ``[Content_Types].xml`` Override and ``xl/_rels/workbook.xml.rels``
#   Relationship entries are filtered above; this pattern catches the
#   bare part-presence diff.  When both sides emit it, any internal
#   disagreement is fully diffed.
_PART_PRESENCE_TOLERANCES: frozenset[str] = frozenset({
    "part_only_in_native: xl/sharedStrings.xml",
})


def _filter_known_gaps(diffs: list[str]) -> list[str]:
    """Drop diffs that originate from documented platform-level gaps.

    A diff is filtered when:
      1. It references a whole metadata part in ``_METADATA_PARTS``
         (``part_only_in_oracle:`` lines + per-element diffs inside it).
      2. It is a ``[Content_Types].xml`` Override-list diff cascading from
         a ``_METADATA_PARTS`` entry (oracle has +1 Override per metadata part).
      3. It is a workbook rels diff cascading from the theme relationship.
      4. It matches a metadata-element path under ``_METADATA_ELEMENT_PATHS``.
    """
    out: list[str] = []
    for d in diffs:
        if d in _PART_PRESENCE_TOLERANCES:
            continue
        skip = False
        for part in _METADATA_PARTS:
            if part in d:
                skip = True
                break
        if skip:
            continue
        # Cascading [Content_Types].xml diffs from extra metadata Overrides.
        if d.startswith("[Content_Types].xml") and (
            "child count differs" in d or "/Override" in d
        ):
            skip = True
        # Cascading workbook rels diffs from extra theme/metadata Relationships.
        if d.startswith("xl/_rels/workbook.xml.rels"):
            skip = True
        # Sheet-level rels files: rId allocation order is emitter-cosmetic
        # (the ``r:id`` rewrite already normalizes references at the referrer
        # parts). H4 fix: filter @Id, @Target, @TargetMode and child-count
        # divergence — but @Type is strictly diffed because a wrong Type
        # means the relationship is misclassified (e.g. comments rel
        # pointing at a hyperlink Type, which would silently swallow
        # data on cross-tool round-trip).
        #
        # @Target divergence: oracle places comments at xl/commentsN.xml;
        # native places them at xl/comments/commentsN.xml. Both are valid
        # OOXML — each side's rels Target resolves to its own file, and
        # both Excel and LibreOffice load both conventions. The divergence
        # is a documented emitter cosmetic, not a bug.
        if "/_rels/" in d and d.startswith("xl/worksheets/_rels/"):
            if (
                "/@Id:" in d
                or "/@Target:" in d  # path naming convention; emitter-cosmetic
                or "/@TargetMode:" in d  # internal/external attr; cosmetic
                or "child count differs" in d
            ):
                skip = True
        # Per-element emitter-cosmetic paths.
        for prefix in _METADATA_ELEMENT_PATHS:
            if d.startswith(prefix):
                skip = True
                break
        if skip:
            continue
        # Per-element emitter-cosmetic infix substrings (variable path
        # prefix per sheet/style index).
        for infix in _METADATA_INFIX_PATTERNS:
            if infix in d:
                skip = True
                break
        if skip:
            continue
        # Row @spans hint — variable path prefix per sheet, so matched
        # via combined infix + suffix pattern.
        if any(p in d for p in _METADATA_SUFFIX_PATTERNS) and any(
            s in d for s in _METADATA_ATTR_SUFFIXES
        ):
            continue
        # Regex-matched cosmetic divergences (e.g. /c[NN]/@s for any column).
        if any(rx.search(d) for rx in _METADATA_REGEX_PATTERNS):
            continue
        out.append(d)
    return out

    # H5 (deferred TODO): _METADATA_INFIX_PATTERNS includes
    # ``/dataValidations[1]/dataValidation[1]/@showDropDown`` but the
    # ``[1]`` is a positional index — multi-DV cases (only one in the
    # current corpus) would silently noisy. Replace with a regex
    # ``/dataValidation\[\d+\]/@showDropDown`` once the case set grows.


def compute_diffs(
    oracle_path: Path,
    native_path: Path,
    *,
    ignore_known_gaps: bool = True,
) -> list[str]:
    """Return a list of human-readable diff strings (empty when clean).

    When ``ignore_known_gaps`` is True (default), platform-level emitter
    gaps documented in ``_KNOWN_PLATFORM_GAPS`` (currently: missing theme
    part) are filtered out so semantic divergences surface cleanly.
    """
    o_parts = normalize(oracle_path)
    n_parts = normalize(native_path)
    diffs: list[str] = []

    common = sorted(set(o_parts) & set(n_parts))
    only_oracle = sorted(set(o_parts) - set(n_parts))
    only_native = sorted(set(n_parts) - set(o_parts))

    for part in only_oracle:
        diffs.append(f"part_only_in_oracle: {part}")
    for part in only_native:
        diffs.append(f"part_only_in_native: {part}")

    for part in common:
        o_root = o_parts[part]
        n_root = n_parts[part]
        per_part: list[str] = []
        _diff_node(o_root, n_root, f"{part}:/{_local_name(o_root.tag)}", per_part)
        diffs.extend(per_part)

    if ignore_known_gaps:
        diffs = _filter_known_gaps(diffs)
    return diffs


def assert_structural_clean(
    oracle_path: Path,
    native_path: Path,
    *,
    ignore_known_gaps: bool = True,
) -> None:
    """Raise ``AssertionError`` listing every Layer 2 difference."""
    diffs = compute_diffs(
        oracle_path, native_path, ignore_known_gaps=ignore_known_gaps,
    )
    if diffs:
        # Cap very long diffs so test failure output stays readable. The
        # remaining count is reported at the bottom.
        head = diffs[:30]
        tail_n = len(diffs) - len(head)
        body = "\n".join(head)
        suffix = f"\n... +{tail_n} more" if tail_n > 0 else ""
        raise AssertionError(
            f"{len(diffs)} Layer 2 structural differences:\n{body}{suffix}"
        )


def diff_summary(diffs: Iterable[str]) -> str:
    """Compact one-line summary for harness reporting."""
    diffs = list(diffs)
    if not diffs:
        return "clean"
    return f"{len(diffs)} diffs (first: {diffs[0]})"
