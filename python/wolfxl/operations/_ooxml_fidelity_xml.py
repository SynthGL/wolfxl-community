"""Cached ZIP part reads and namespace-agnostic XML accessors.

Internal to the OOXML fidelity audit. The public surface stays
``wolfxl.operations._ooxml_fidelity``.
"""

from __future__ import annotations

import zipfile
from typing import Iterable
from xml.etree import ElementTree


def _read_part_bytes_or_none(archive: zipfile.ZipFile, part: str) -> bytes | None:
    cache = getattr(archive, "_wolfxl_ooxml_bytes_cache", None)
    if cache is None:
        cache = {}
        setattr(archive, "_wolfxl_ooxml_bytes_cache", cache)
    if part in cache:
        return cache[part]
    try:
        payload = archive.read(part)
    except KeyError:
        cache[part] = None
        return None
    cache[part] = payload
    return payload


def _part_contains_any(
    archive: zipfile.ZipFile,
    part: str,
    markers: Iterable[bytes],
) -> bool:
    payload = _read_part_bytes_or_none(archive, part)
    if payload is None:
        return False
    return any(marker in payload for marker in markers)


def _read_xml_or_none(archive: zipfile.ZipFile, part: str) -> ElementTree.Element | None:
    cache = getattr(archive, "_wolfxl_ooxml_xml_cache", None)
    if cache is None:
        cache = {}
        setattr(archive, "_wolfxl_ooxml_xml_cache", cache)
    if part in cache:
        return cache[part]
    payload = _read_part_bytes_or_none(archive, part)
    if payload is None:
        cache[part] = None
        return None
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError:
        cache[part] = None
        return None
    cache[part] = root
    return root


def _nodes_by_local(root: ElementTree.Element, name: str) -> list[ElementTree.Element]:
    return [node for node in root.iter() if _local_name(node.tag) == name]


def _first_node_by_local(root: ElementTree.Element, name: str) -> ElementTree.Element | None:
    for node in root.iter():
        if _local_name(node.tag) == name:
            return node
    return None


def _children_by_local(root: ElementTree.Element, name: str) -> list[ElementTree.Element]:
    return [node for node in root if _local_name(node.tag) == name]


def _first_child_by_local(root: ElementTree.Element, name: str) -> ElementTree.Element | None:
    for node in root:
        if _local_name(node.tag) == name:
            return node
    return None


def _texts_by_local(root: ElementTree.Element, name: str) -> list[str]:
    return [text for node in _nodes_by_local(root, name) if (text := _text(node))]


def _vals_by_path(root: ElementTree.Element, names: tuple[str, ...]) -> list[str]:
    return [
        val
        for node in root.iter()
        if _local_name(node.tag) in names and (val := _attr(node, "val")) is not None
    ]


def _extension_fingerprints(
    root: ElementTree.Element, interesting_names: frozenset[str]
) -> list[object]:
    out: list[object] = []
    for ext in _nodes_by_local(root, "ext"):
        if any(_local_name(node.tag) in interesting_names for node in ext.iter()):
            out.append(_xml_tree_fingerprint(ext))
    return out


def _xml_extensions(root: ElementTree.Element) -> list[object]:
    return [_xml_tree_fingerprint(node) for node in _nodes_by_local(root, "ext")]


def _xml_tree_fingerprint(node: ElementTree.Element) -> object:
    return (
        _local_name(node.tag),
        _all_stable_attrs(node),
        _text(node),
        [_xml_tree_fingerprint(child) for child in list(node)],
    )


def _all_stable_attrs(node: ElementTree.Element | None) -> tuple[tuple[str, str], ...]:
    if node is None:
        return tuple()
    return tuple(sorted((_local_name(key), value) for key, value in node.attrib.items()))


def _relationship_id(node: ElementTree.Element) -> str | None:
    for key, value in node.attrib.items():
        if key.endswith("}id") or key == "id":
            return value
    return None


def _stable_attrs(
    node: ElementTree.Element | None, names: Iterable[str]
) -> tuple[tuple[str, str | None], ...]:
    if node is None:
        return tuple((name, None) for name in names)
    return tuple((name, _attr(node, name)) for name in names)


def _attr(node: ElementTree.Element | None, name: str) -> str | None:
    if node is None:
        return None
    for key, value in node.attrib.items():
        if _local_name(key) == name:
            return value
    return None


def _text(node: ElementTree.Element) -> str | None:
    value = (node.text or "").strip()
    return value or None


def _local_name(name: str) -> str:
    return name.rsplit("}", 1)[-1] if "}" in name else name
