"""Package manifest compatibility helpers."""

from __future__ import annotations

from dataclasses import dataclass
from mimetypes import MimeTypes
import os
from typing import Any
from wolfxl._compat import _install_openpyxl_iter, _openpyxl_name_fallback
from wolfxl.xml.constants import (
    ACTIVEX,
    ARC_CONTENT_TYPES,
    ARC_APP,
    ARC_CORE,
    ARC_STYLE,
    ARC_THEME,
    CONTYPES_NS,
    CPROPS_TYPE,
    CTRL,
    STYLES_TYPE,
    THEME_TYPE,
    VBA,
)
from wolfxl.xml.functions import Element, fromstring, localname, tostring

mimetypes = MimeTypes()
mimetypes.add_type("application/xml", ".xml")
mimetypes.add_type("application/vnd.openxmlformats-package.relationships+xml", ".rels")
mimetypes.add_type("application/vnd.ms-office.vbaProject", ".bin")
mimetypes.add_type("application/vnd.openxmlformats-officedocument.vmlDrawing", ".vml")
mimetypes.add_type("image/x-emf", ".emf")


@dataclass
class FileExtension:
    Extension: str
    ContentType: str

    def to_tree(self) -> Element:
        return Element(
            "Default",
            {"Extension": self.Extension, "ContentType": self.ContentType},
        )

    @classmethod
    def from_tree(cls, node: Any) -> "FileExtension":
        return cls(Extension=node.get("Extension"), ContentType=node.get("ContentType"))


@dataclass
class Override:
    PartName: str
    ContentType: str

    def to_tree(self) -> Element:
        return Element(
            "Override",
            {"PartName": self.PartName, "ContentType": self.ContentType},
        )

    @classmethod
    def from_tree(cls, node: Any) -> "Override":
        return cls(PartName=node.get("PartName"), ContentType=node.get("ContentType"))


DEFAULT_TYPES = [
    FileExtension("rels", "application/vnd.openxmlformats-package.relationships+xml"),
    FileExtension("xml", "application/xml"),
]

DEFAULT_OVERRIDE = [
    Override("/" + ARC_STYLE, STYLES_TYPE),
    Override("/" + ARC_THEME, THEME_TYPE),
    Override("/" + ARC_CORE, "application/vnd.openxmlformats-package.core-properties+xml"),
    Override("/" + ARC_APP, "application/vnd.openxmlformats-officedocument.extended-properties+xml"),
]


class Manifest:
    """Content-types manifest with the small public surface openpyxl exposes."""

    tagname = "Types"
    path = "[Content_Types].xml"

    def __init__(
        self,
        Default: list[FileExtension] | tuple[FileExtension, ...] = (),
        Override: list[Override] | tuple[Override, ...] = (),
    ) -> None:
        self.Default = _UniqueAppendList(Default if Default else DEFAULT_TYPES)
        self.Override = _UniqueAppendList(Override if Override else DEFAULT_OVERRIDE)

    @property
    def filenames(self) -> list[str]:
        return [part.PartName for part in self.Override]

    @property
    def extensions(self) -> list[tuple[str, str]]:
        exts = {os.path.splitext(part.PartName)[-1] for part in self.Override}
        type_map = mimetypes.types_map[True]
        return [(ext[1:], type_map[ext]) for ext in sorted(exts) if ext in type_map]

    def __contains__(self, content_type: str) -> bool:
        return any(part.ContentType == content_type for part in self.Override)

    def findall(self, content_type: str):
        for part in self.Override:
            if part.ContentType == content_type:
                yield part

    def find(self, content_type: str) -> Override | None:
        try:
            return next(self.findall(content_type))
        except StopIteration:
            return None

    def append(self, obj: Any) -> None:
        self.Override.append(Override(PartName=obj.path, ContentType=obj.mime_type))

    def to_tree(self) -> Element:
        defaults = [part.Extension for part in self.Default]
        for ext, mime in self.extensions:
            if ext not in defaults:
                self.Default.append(FileExtension(ext, mime))
        root = Element("Types", {"xmlns": CONTYPES_NS})
        for default in self.Default:
            root.append(default.to_tree())
        for override in self.Override:
            root.append(override.to_tree())
        return root

    @classmethod
    def from_tree(cls, node: Any) -> "Manifest":
        defaults = []
        overrides = []
        for child in node:
            tag = localname(child)
            if tag == "Default":
                defaults.append(FileExtension.from_tree(child))
            elif tag == "Override":
                overrides.append(Override.from_tree(child))
        return cls(Default=defaults, Override=overrides)

    def _write(self, archive: Any, workbook: Any) -> None:
        self.append(workbook)
        self._write_vba(workbook)
        self._register_mimetypes(filenames=archive.namelist())
        archive.writestr(self.path, tostring(self.to_tree()))

    def _register_mimetypes(self, filenames: list[str] | tuple[str, ...]) -> None:
        for filename in filenames:
            ext = os.path.splitext(filename)[-1]
            if not ext:
                continue
            try:
                mime = mimetypes.types_map[True][ext]
            except KeyError:
                continue
            self.Default.append(FileExtension(ext[1:], mime))

    def _write_vba(self, workbook: Any) -> None:
        archive = getattr(workbook, "vba_archive", None)
        if not archive:
            return
        node = fromstring(archive.read(ARC_CONTENT_TYPES))
        manifest = Manifest.from_tree(node)
        filenames = self.filenames
        for override in manifest.Override:
            if override.PartName not in (ACTIVEX, CTRL, VBA):
                continue
            if override.PartName not in filenames:
                self.Override.append(override)


_install_openpyxl_iter(FileExtension, Override, Manifest)


class _UniqueAppendList(list):
    def __init__(self, values: Any = ()) -> None:
        super().__init__()
        self.extend(values)

    def append(self, value: Any) -> None:
        if value not in self:
            super().append(value)

    def extend(self, values: Any) -> None:
        for value in values:
            self.append(value)

__all__ = [
    "ACTIVEX",
    "ARC_CONTENT_TYPES",
    "CTRL",
    "CPROPS_TYPE",
    "DEFAULT_OVERRIDE",
    "DEFAULT_TYPES",
    "FileExtension",
    "Manifest",
    "MimeTypes",
    "Override",
    "VBA",
    "fromstring",
    "mimetypes",
    "os",
    "tostring",
]

__getattr__ = _openpyxl_name_fallback(globals())
