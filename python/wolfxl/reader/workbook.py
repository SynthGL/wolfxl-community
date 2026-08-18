"""Workbook reader compatibility."""

from __future__ import annotations

from warnings import warn

from wolfxl import Workbook
from wolfxl._compat import _make_serialisable
from wolfxl._external_links import ExternalLink as CacheDefinition
from wolfxl.utils.datetime import CALENDAR_MAC_1904
from wolfxl.workbook.defined_name import DefinedNameList
from wolfxl.packaging.relationship import get_dependents, get_rel, get_rels_path
from wolfxl.packaging.workbook import WorkbookPackage
from wolfxl.workbook.external_link.external import read_external_link
from wolfxl.worksheet.print_settings import PrintArea, PrintTitles
from wolfxl.xml.functions import fromstring

RecordList = _make_serialisable("RecordList")


class WorkbookParser:
    """Parse workbook-level package metadata from an OOXML archive.

    This mirrors openpyxl's private workbook parser surface for tests and
    compatibility callers. It does not create worksheets; it fills workbook
    metadata such as views, defined names, security, links, and sheet records.
    """

    _rels = None

    def __init__(
        self,
        archive,  # noqa: ANN001
        workbook_part_name: str | None = None,
        keep_links: bool = True,
    ) -> None:
        """Create a parser for ``workbook.xml`` inside ``archive``."""
        self.archive = archive
        self.workbook_part_name = workbook_part_name
        self.defined_names = DefinedNameList()
        self.keep_links = keep_links
        self.sheets = []
        self.wb = Workbook()

    @property
    def rels(self):
        """Workbook relationships keyed by relationship id."""
        if self._rels is None:
            self._rels = get_dependents(
                self.archive,
                get_rels_path(self.workbook_part_name),
            ).to_dict()
        return self._rels

    def parse(self) -> Workbook:
        """Read workbook metadata into a new ``Workbook`` instance."""
        src = self.archive.read(self.workbook_part_name)
        package = WorkbookPackage.from_tree(fromstring(src))
        if package.properties and package.properties.date1904:
            self.wb.epoch = CALENDAR_MAC_1904

        self.wb.code_name = getattr(package.properties, "codeName", None)
        self.wb.active = package.active
        self.wb.views = package.bookViews
        self.sheets = package.sheets
        self.wb.calculation = package.calcPr
        self.caches = getattr(package, "pivotCaches", [])

        if not self.keep_links:
            package.externalReferences = []
        for ext_ref in package.externalReferences:
            rel = self.rels.get(ext_ref.id)
            if rel is not None:
                self.wb._external_links.append(  # noqa: SLF001
                    read_external_link(self.archive, rel.Target)
                )

        if package.definedNames:
            self.defined_names = package.definedNames
        self.wb.security = package.workbookProtection
        return self.wb

    def find_sheets(self):
        """Yield valid sheet records paired with their workbook relationship."""
        for sheet in self.sheets:
            if not sheet.id:
                warn(
                    f"File contains an invalid specification for {sheet.name}. "
                    "This will be removed"
                )
                continue
            yield sheet, self.rels[sheet.id]

    def assign_names(self) -> None:
        """Assign parsed defined names to the workbook or target worksheet."""
        for idx, names in self.defined_names.by_sheet().items():
            if idx == "global":
                workbook_names = self.wb.defined_names
                for name, defn in names.items():
                    dict.__setitem__(workbook_names, name, defn)
                continue

            try:
                sheet = self.wb.worksheets[idx]
            except (IndexError, KeyError):
                warn(f"Defined names for sheet index {idx} cannot be located")
                continue

            for name, defn in names.items():
                reserved = defn.is_reserved
                if reserved is None:
                    dict.__setitem__(sheet.defined_names, name, defn)
                elif reserved == "Print_Titles":
                    titles = PrintTitles.from_string(defn.value)
                    sheet._print_title_rows = str(titles.rows) if titles.rows else None  # noqa: SLF001
                    sheet._print_title_cols = str(titles.cols) if titles.cols else None  # noqa: SLF001
                    sheet._print_titles_dirty = False  # noqa: SLF001
                elif reserved == "Print_Area":
                    try:
                        print_area = PrintArea.from_string(defn.value)
                        sheet._print_area = ",".join(  # noqa: SLF001
                            str(rng) for rng in sorted(print_area.ranges, key=str)
                        )
                    except Exception:
                        warn(f"Print area cannot be set to Defined name: {defn.value}.")

    @property
    def pivot_caches(self):
        """Return pivot cache relationships keyed by cache id."""
        caches = {}
        for cache_ref in getattr(self, "caches", []):
            cache = get_rel(self.archive, self.rels, id=cache_ref.id)
            if getattr(cache, "deps", None):
                records = get_rel(self.archive, cache.deps, cache.id)
                cache.records = records
            caches[cache_ref.cacheId] = cache
        return caches


def load_workbook(*args, **kwargs):  # noqa: ANN002, ANN003
    from wolfxl import load_workbook as _load_workbook

    return _load_workbook(*args, **kwargs)


__all__ = [
    "CALENDAR_MAC_1904",
    "CacheDefinition",
    "DefinedNameList",
    "PrintArea",
    "PrintTitles",
    "RecordList",
    "Workbook",
    "WorkbookPackage",
    "WorkbookParser",
    "fromstring",
    "get_dependents",
    "get_rel",
    "get_rels_path",
    "load_workbook",
    "read_external_link",
    "warn",
]
