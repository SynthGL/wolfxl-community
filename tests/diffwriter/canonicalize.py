"""Layer 1 — byte-canonical diff (gold-star, non-blocking).

For every part of an xlsx archive, parses the XML to ``ElementTree``,
strips fuzzy elements / attributes per ``fuzzy_elements.json`` (timestamps,
app name etc.), then runs the stdlib W3C C14N 1.1 canonicalizer
(``xml.etree.ElementTree.canonicalize``). The canonical bytes are SHA-256'd.

Comparing the per-part hash map across two xlsx files tells the harness
which parts canonicalize identically. ``lxml`` (with C14N 2.0) would be
slightly stricter, but stdlib is sufficient for our gold-star target — the
known divergences (default-namespace folding, attribute ordering at the
parent level) only matter when the structural diff (Layer 2) would already
have surfaced a real mismatch. Layer 1 is INFORMATIONAL — failures collect
as warnings, not test failures.

Non-XML parts (binary like ``xl/media/*.png``) are hashed as-is.
"""
from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Mapping
from xml.etree import ElementTree as ET

_FUZZY_PATH = Path(__file__).parent / "fuzzy_elements.json"

# Common OOXML namespace prefixes -> URIs. Selectors in fuzzy_elements.json
# use the prefix form (``dcterms:created``); ElementTree stores expanded
# Clark notation (``{http://...}created``). This map lets us translate.
_NSMAP = {
    "dc":      "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
    "cp":      "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "vt":      "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes",
    "xsi":     "http://www.w3.org/2001/XMLSchema-instance",
}


def _load_fuzzy() -> dict[str, list[str]]:
    if not _FUZZY_PATH.exists():
        return {}
    raw = json.loads(_FUZZY_PATH.read_text())
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def _expand_selector(selector: str) -> tuple[str, bool]:
    """Translate a selector to ``(name, is_attr)``.

    ``@foo`` -> attribute ``foo`` on root.
    ``prefix:local`` -> element with Clark-notation tag ``{ns}local``.
    ``local`` -> bare element local name.
    """
    if selector.startswith("@"):
        return selector[1:], True
    if ":" in selector:
        prefix, local = selector.split(":", 1)
        ns = _NSMAP.get(prefix)
        if ns is None:
            return local, False
        return f"{{{ns}}}{local}", False
    return selector, False


def _strip_fuzzy(root: ET.Element, part_name: str, fuzzy: dict[str, list[str]]) -> None:
    """Remove every selector in the fuzzy map matching ``part_name`` or '*'."""
    selectors = list(fuzzy.get(part_name, [])) + list(fuzzy.get("*", []))
    if not selectors:
        return

    for sel in selectors:
        target, is_attr = _expand_selector(sel)
        if is_attr:
            root.attrib.pop(target, None)
            continue
        # Element strip: remove every descendant whose local name matches.
        # We compare on local name (stripping ``{ns}`` if present) so a
        # selector like ``dcterms:created`` matches even when the doc
        # declared a different prefix.
        target_local = target.rsplit("}", 1)[-1] if "}" in target else target
        for parent in list(root.iter()):
            for child in list(parent):
                child_local = child.tag.rsplit("}", 1)[-1] if "}" in child.tag else child.tag
                if child.tag == target or child_local == target_local:
                    parent.remove(child)


def _canonicalize_xml(data: bytes, part_name: str, fuzzy: dict[str, list[str]]) -> bytes:
    """Parse ``data``, strip fuzzy elements, return W3C-canonical bytes."""
    root = ET.fromstring(data)
    _strip_fuzzy(root, part_name, fuzzy)
    serialized = ET.tostring(root, encoding="unicode")
    canon = ET.canonicalize(serialized)
    return canon.encode("utf-8")


_VML_NS_RE = re.compile(rb"\sxmlns(?::\w+)?=[\"'][^\"']+[\"']")


def _hash_vml(data: bytes) -> bytes:
    """VML files (``vmlDrawing*.vml``) ship as well-formed XML but vary in
    cosmetic namespace declaration order across emitters. For Layer 1 we
    strip every ``xmlns`` declaration before hashing so cosmetic ordering
    doesn't trigger a false mismatch. This is gold-star treatment — Layer 2
    re-checks structurally with full namespaces."""
    return _VML_NS_RE.sub(b"", data)


def canonical_part_hashes(
    xlsx_path: Path,
    fuzzy: dict[str, list[str]] | None = None,
) -> Mapping[str, str]:
    """Return ``{part_path: sha256(canonical_bytes)}`` for every part of an xlsx."""
    if fuzzy is None:
        fuzzy = _load_fuzzy()

    out: dict[str, str] = {}
    with zipfile.ZipFile(xlsx_path) as zf:
        for name in sorted(zf.namelist()):
            data = zf.read(name)
            if name.endswith((".xml", ".rels")):
                try:
                    canon = _canonicalize_xml(data, name, fuzzy)
                except ET.ParseError:
                    canon = data
            elif name.endswith(".vml"):
                canon = _hash_vml(data)
            else:
                canon = data
            out[name] = hashlib.sha256(canon).hexdigest()
    return out


def compare_canonical(
    oracle_path: Path,
    native_path: Path,
) -> list[str]:
    """Return a list of part paths whose canonical hashes differ.

    Returned list includes parts present on only one side. Empty list means
    every part canonicalizes identically (gold-star achieved).
    """
    o_hashes = canonical_part_hashes(oracle_path)
    n_hashes = canonical_part_hashes(native_path)
    mismatches: list[str] = []
    for part in sorted(set(o_hashes) | set(n_hashes)):
        o_hash = o_hashes.get(part)
        n_hash = n_hashes.get(part)
        if o_hash != n_hash:
            mismatches.append(part)
    return mismatches
