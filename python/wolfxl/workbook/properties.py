"""``openpyxl.workbook.properties`` — :class:`CalcProperties` and
:class:`WorkbookProperties` dataclasses (RFC-065).

These two dataclasses back ``wb.calc_properties`` and
``wb.workbook_properties`` respectively. They carry the per-workbook
calc-engine flags (``<calcPr>``) and the workbook-wide configuration
(``<workbookPr>``); both are spliced into ``xl/workbook.xml`` by the
patcher's Phase 2.5q (workbook security drain, extended for RFC-065).

Field names mirror openpyxl exactly (camelCase XML attributes) so
existing user code that pokes at ``wb.calc_properties.calcId`` keeps
working unchanged. Only the ``to_rust_dict`` boundary uses snake_case
to match the §10 contract carried across the PyO3 wall.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wolfxl._compat import _iter_openpyxl_attrs, _openpyxl_name_fallback
from wolfxl.xml.functions import Element


@dataclass
class CalcProperties:
    """`<calcPr>` element (CT_CalcPr §18.2.2).

    Backs ``wb.calc_properties``. Field defaults match the values Excel
    writes for a freshly-created workbook (``calcId=124519``,
    ``calcMode="auto"``, etc.).
    """

    __attrs__ = (
        "calcId",
        "calcMode",
        "fullCalcOnLoad",
        "refMode",
        "iterate",
        "iterateCount",
        "iterateDelta",
        "fullPrecision",
        "calcCompleted",
        "calcOnSave",
        "concurrentCalc",
        "concurrentManualCount",
        "forceFullCalc",
    )

    calcId: int = 124519             # noqa: N815 — openpyxl XML name
    calcMode: str | None = None      # noqa: N815 — auto | autoNoTable | manual
    fullCalcOnLoad: bool | None = True  # noqa: N815
    refMode: str | None = None       # noqa: N815 — A1 | R1C1
    iterate: bool | None = None
    iterateCount: int | None = None  # noqa: N815
    iterateDelta: float | None = None  # noqa: N815
    fullPrecision: bool | None = None  # noqa: N815
    calcCompleted: bool | None = None  # noqa: N815
    calcOnSave: bool | None = None   # noqa: N815
    concurrentCalc: bool | None = None  # noqa: N815
    concurrentManualCount: int | None = None  # noqa: N815
    forceFullCalc: bool | None = None  # noqa: N815

    def __iter__(self):
        yield from _iter_openpyxl_attrs(self, self.__attrs__)

    def to_tree(
        self,
        tagname: str | None = None,
        idx: int | None = None,  # noqa: ARG002 - openpyxl signature
        namespace: str | None = None,  # noqa: ARG002 - openpyxl signature
    ) -> Any:
        node = Element(tagname or "calcPr")
        for name, value in self:
            node.set(name, value)
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "CalcProperties":
        kwargs: dict[str, Any] = {}
        defaults = cls()
        for name in cls.__attrs__:
            value = node.get(name)
            if value is None:
                continue
            default = getattr(defaults, name)
            if isinstance(default, bool) or name in {
                "fullCalcOnLoad",
                "iterate",
                "fullPrecision",
                "calcCompleted",
                "calcOnSave",
                "concurrentCalc",
                "forceFullCalc",
            }:
                kwargs[name] = value.lower() in {"1", "true"}
            elif isinstance(default, int) or name in {
                "calcId",
                "iterateCount",
                "concurrentManualCount",
            }:
                kwargs[name] = int(value)
            elif isinstance(default, float) or name == "iterateDelta":
                kwargs[name] = float(value)
            else:
                kwargs[name] = value
        return cls(**kwargs)

    def to_rust_dict(self) -> dict[str, Any]:
        """Return the §10 snake_case dict consumed by the Rust patcher."""
        return {
            "calc_id": self.calcId,
            "calc_mode": self.calcMode,
            "full_calc_on_load": self.fullCalcOnLoad,
            "ref_mode": self.refMode,
            "iterate": self.iterate,
            "iterate_count": self.iterateCount,
            "iterate_delta": self.iterateDelta,
            "full_precision": self.fullPrecision,
            "calc_completed": self.calcCompleted,
            "calc_on_save": self.calcOnSave,
            "concurrent_calc": self.concurrentCalc,
            "concurrent_manual_count": self.concurrentManualCount,
            "force_full_calc": self.forceFullCalc,
        }


@dataclass
class WorkbookProperties:
    """`<workbookPr>` element (CT_WorkbookPr §18.2.28).

    Backs ``wb.workbook_properties``. Carries the date1904 epoch flag,
    VBA codeName, and a handful of UI / compatibility toggles that
    Excel persists in the workbook part.
    """

    date1904: bool = False
    dateCompatibility: bool = True            # noqa: N815
    showObjects: str = "all"                  # noqa: N815 — all|placeholders|none
    showBorderUnselectedTables: bool = True   # noqa: N815
    filterPrivacy: bool = False               # noqa: N815
    promptedSolutions: bool = False           # noqa: N815
    showInkAnnotation: bool = True            # noqa: N815
    backupFile: bool = False                  # noqa: N815
    saveExternalLinkValues: bool = True       # noqa: N815
    updateLinks: str = "userSet"              # noqa: N815
    codeName: str | None = None               # noqa: N815
    hidePivotFieldList: bool = False          # noqa: N815
    showPivotChartFilter: bool = False        # noqa: N815
    allowRefreshQuery: bool = False           # noqa: N815
    publishItems: bool = False                # noqa: N815
    checkCompatibility: bool = False          # noqa: N815
    autoCompressPictures: bool = True         # noqa: N815
    refreshAllConnections: bool = False       # noqa: N815
    defaultThemeVersion: int = 124226         # noqa: N815

    def __iter__(self):
        yield from _iter_openpyxl_attrs(self)

    def to_tree(self) -> Any:
        node = Element("workbookPr")
        defaults = type(self)()
        for name, value in self.__dict__.items():
            if value is None or value == getattr(defaults, name):
                continue
            node.set(name, _xml_value(value))
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "WorkbookProperties":
        kwargs = {}
        defaults = cls()
        for name, default in defaults.__dict__.items():
            value = node.get(name)
            if value is None:
                continue
            if isinstance(default, bool):
                kwargs[name] = value in {"1", "true", "True"}
            elif isinstance(default, int):
                kwargs[name] = int(value)
            else:
                kwargs[name] = value
        return cls(**kwargs)

    def to_rust_dict(self) -> dict[str, Any]:
        """Return the §10 snake_case dict consumed by the Rust patcher."""
        return {
            "date1904": self.date1904,
            "date_compatibility": self.dateCompatibility,
            "show_objects": self.showObjects,
            "show_border_unselected_tables": self.showBorderUnselectedTables,
            "filter_privacy": self.filterPrivacy,
            "prompted_solutions": self.promptedSolutions,
            "show_ink_annotation": self.showInkAnnotation,
            "backup_file": self.backupFile,
            "save_external_link_values": self.saveExternalLinkValues,
            "update_links": self.updateLinks,
            "code_name": self.codeName,
            "hide_pivot_field_list": self.hidePivotFieldList,
            "show_pivot_chart_filter": self.showPivotChartFilter,
            "allow_refresh_query": self.allowRefreshQuery,
            "publish_items": self.publishItems,
            "check_compatibility": self.checkCompatibility,
            "auto_compress_pictures": self.autoCompressPictures,
            "refresh_all_connections": self.refreshAllConnections,
            "default_theme_version": self.defaultThemeVersion,
        }


@dataclass
class FileVersion:
    tagname = "fileVersion"
    __attrs__ = ("appName", "lastEdited", "lowestEdited", "rupBuild", "codeName")

    appName: str | None = None  # noqa: N815
    lastEdited: str | None = None  # noqa: N815
    lowestEdited: str | None = None  # noqa: N815
    rupBuild: str | None = None  # noqa: N815
    codeName: str | None = None  # noqa: N815

    def __iter__(self):
        yield from _iter_openpyxl_attrs(self, self.__attrs__)

    def to_tree(self, tagname: str | None = None, **kw: Any) -> Any:  # noqa: ARG002
        node = Element(tagname or self.tagname)
        for name, value in self:
            node.set(name, value)
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "FileVersion":
        return cls(**{name: node.get(name) for name in cls.__attrs__})


__all__ = ["CalcProperties", "FileVersion", "WorkbookProperties"]

__getattr__ = _openpyxl_name_fallback(globals())


def _xml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)
