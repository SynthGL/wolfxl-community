"""`ProjectedPieChart` — pie-of-pie / bar-of-pie.

Maps to ``<c:ofPieChart>``. Carries an ``of_pie_type`` (``"bar"`` or
``"pie"``), ``split_type`` selector, and ``split_pos`` /
``second_pie_size`` per the OOXML spec.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wolfxl._compat import _install_openpyxl_iter, _resolve_openpyxl_class

from ._chart import ChartBase, _install_chart_type_xml_methods
from .axis import ChartLines
from .label import DataLabelList


_VALID_OF_PIE_TYPE = ("bar", "pie")
_VALID_SPLIT_TYPE = ("auto", "pos", "percent", "val", "cust")


@dataclass
class CustomSplit:
    secondPiePt: list[int] | tuple[int, ...] = ()  # noqa: N815


class ProjectedPieChart(ChartBase):
    """`<c:ofPieChart>` — bar-of-pie / pie-of-pie."""

    tagname = "ofPieChart"
    _series_type = "pie"

    def __init__(
        self,
        of_pie_type: str = "pie",
        ofPieType: str | None = None,  # noqa: N803
        gapWidth: int | None = None,  # noqa: N803
        split_type: str = "auto",
        splitType: str | None = None,  # noqa: N803
        split_pos: int | None = None,
        splitPos: int | None = None,  # noqa: N803
        custSplit: CustomSplit | None = None,  # noqa: N803
        second_pie_size: int | None = None,
        secondPieSize: int | None = None,  # noqa: N803
        serLines: ChartLines | None = None,  # noqa: N803
        ser: list[Any] | tuple[Any, ...] = (),
        dLbls: DataLabelList | None = None,
        varyColors: bool | None = True,
        firstSliceAng: int = 0,
        **kw: Any,
    ) -> None:
        if ofPieType is not None:
            of_pie_type = ofPieType
        if splitType is not None:
            split_type = splitType
        if splitPos is not None:
            split_pos = splitPos
        if secondPieSize is not None:
            second_pie_size = secondPieSize
        if second_pie_size is None:
            second_pie_size = 75
        if of_pie_type not in _VALID_OF_PIE_TYPE:
            raise ValueError(
                f"of_pie_type={of_pie_type!r} not in {_VALID_OF_PIE_TYPE}"
            )
        if split_type not in _VALID_SPLIT_TYPE:
            raise ValueError(
                f"split_type={split_type!r} not in {_VALID_SPLIT_TYPE}"
            )
        if second_pie_size is not None and not (5 <= second_pie_size <= 200):
            raise ValueError(
                f"second_pie_size={second_pie_size} must be in [5, 200]"
            )
        if not (0 <= firstSliceAng <= 360):
            raise ValueError(f"firstSliceAng={firstSliceAng} must be in [0, 360]")

        self.of_pie_type = of_pie_type
        self.ofPieType = of_pie_type
        self.gapWidth = gapWidth
        self.split_type = split_type
        self.splitType = split_type
        self.split_pos = split_pos
        self.splitPos = split_pos
        self.custSplit = custSplit
        self.second_pie_size = second_pie_size
        self.secondPieSize = second_pie_size
        self.serLines = ChartLines() if serLines is None else serLines
        self.firstSliceAng = firstSliceAng
        self.dLbls = dLbls
        self.vary_colors = varyColors
        super().__init__(**kw)
        self.ser = list(ser)

    @property
    def first_slice_ang(self) -> int:
        return self.firstSliceAng

    @first_slice_ang.setter
    def first_slice_ang(self, v: int) -> None:
        if not (0 <= v <= 360):
            raise ValueError(f"first_slice_ang={v} must be in [0, 360]")
        self.firstSliceAng = v

    def _chart_type_specific_keys(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "of_pie_type": self.of_pie_type,
            "split_type": self.split_type,
            "first_slice_ang": self.firstSliceAng,
        }
        if self.gapWidth is not None:
            d["gap_width"] = self.gapWidth
        if self.split_pos is not None:
            d["split_pos"] = self.split_pos
        if self.second_pie_size is not None:
            d["second_pie_size"] = self.second_pie_size
        if self.dLbls is not None:
            from .series import _dlbls_to_snake
            d["data_labels"] = _dlbls_to_snake(self.dLbls.to_dict())
        return d


_PROJECTED_PIE_XML_MODEL_NAMES = ("CustomSplit",)


def _xml_model_names(cls: type) -> tuple[str, ...]:
    return tuple(getattr(cls, "__attrs__", ())) + tuple(getattr(cls, "__elements__", ()))


def _to_openpyxl_model(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_to_openpyxl_model(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_to_openpyxl_model(item) for item in value)

    cls = value.__class__
    upstream_cls = _resolve_openpyxl_class(cls.__module__, cls.__name__)
    if upstream_cls is None or cls is upstream_cls:
        return value

    names = _xml_model_names(upstream_cls)
    if not names:
        return value

    kwargs: dict[str, Any] = {}
    for name in names:
        if hasattr(value, name):
            kwargs[name] = _to_openpyxl_model(getattr(value, name))
    return upstream_cls(**kwargs)


def _from_openpyxl_projected_pie_model(native_cls: type, value: Any) -> Any:
    names = _xml_model_names(value.__class__)
    kwargs: dict[str, Any] = {}
    for name in names:
        if hasattr(value, name):
            kwargs[name] = _to_native_projected_pie_model(getattr(value, name))
    return native_cls(**kwargs)


def _to_native_projected_pie_model(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_to_native_projected_pie_model(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_to_native_projected_pie_model(item) for item in value)

    native_cls = globals().get(value.__class__.__name__)
    if (
        not isinstance(native_cls, type)
        or native_cls.__name__ not in _PROJECTED_PIE_XML_MODEL_NAMES
    ):
        return value
    upstream_cls = _resolve_openpyxl_class(__name__, native_cls.__name__)
    if upstream_cls is None or not isinstance(value, upstream_cls):
        return value
    return _from_openpyxl_projected_pie_model(native_cls, value)


def _projected_pie_to_tree(
    self: Any,
    tagname: str | None = None,
    idx: int | None = None,
    namespace: str | None = None,
):
    upstream = _to_openpyxl_model(self)
    return upstream.to_tree(tagname=tagname, idx=idx, namespace=namespace)


def _projected_pie_from_tree(cls: type, node: Any) -> Any:
    upstream_cls = _resolve_openpyxl_class(__name__, cls.__name__)
    if upstream_cls is None:
        raise AttributeError("from_tree")
    return _from_openpyxl_projected_pie_model(cls, upstream_cls.from_tree(node))


def _projected_pie_eq(self: Any, other: Any) -> bool:
    if type(self) is not type(other):
        return False
    return _to_openpyxl_model(self) == _to_openpyxl_model(other)


def _install_projected_pie_xml_methods(*classes: type) -> None:
    for cls in classes:
        if not hasattr(cls, "to_tree"):
            cls.to_tree = _projected_pie_to_tree  # type: ignore[attr-defined]
        if "from_tree" not in cls.__dict__:
            cls.from_tree = classmethod(_projected_pie_from_tree)  # type: ignore[attr-defined]
        cls.__eq__ = _projected_pie_eq  # type: ignore[attr-defined]


_install_chart_type_xml_methods(ProjectedPieChart)
_install_openpyxl_iter(CustomSplit)
_install_projected_pie_xml_methods(CustomSplit)

__all__ = ["CustomSplit", "ProjectedPieChart"]
