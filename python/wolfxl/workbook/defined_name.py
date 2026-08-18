"""openpyxl.workbook.defined_name compatibility.

T1 makes ``DefinedName`` a real dataclass.  Read access comes through
``wb.defined_names`` — that returns a :class:`DefinedNameDict` whose
values are ``DefinedName`` objects instead of bare strings.

Breaking change from T0: callers that did ``wb.defined_names["X"]`` and
expected a string must now do ``wb.defined_names["X"].value`` (or
``.attr_text`` for openpyxl parity). See CHANGELOG for the 1-line
migration.

RFC-021 — modify-mode defined-name mutation — accepts ``attr_text`` as
an alias for ``value`` to match openpyxl's canonical attribute name
(`openpyxl.workbook.defined_name.DefinedName.attr_text`). Supplying
both with conflicting values raises ``TypeError``; supplying neither
also raises ``TypeError``.

Phase 2 (G22) extends the dataclass to cover the full ECMA-376
``definedName`` attribute surface that openpyxl exposes: ``customMenu``,
``description``, ``help``, ``statusBar``, ``shortcutKey``, ``function``,
``functionGroupId``, ``vbProcedure``, ``xlm``, ``publishToServer``,
``workbookParameter``. Each is reachable via the openpyxl camelCase
spelling AND the wolfxl snake_case spelling.
"""

from __future__ import annotations

from collections import defaultdict
import inspect as _inspect
import re
from typing import TYPE_CHECKING, Any
from xml.etree import ElementTree as ET

from wolfxl._compat import _openpyxl_name_fallback
from wolfxl.compat.strings import safe_string
from wolfxl.formula.tokenizer import Tokenizer
from wolfxl.utils.cell import SHEETRANGE_RE
from wolfxl.xml.functions import Element

if TYPE_CHECKING:
    from wolfxl.workbook import DefinedNameDict

RESERVED = frozenset(
    {
        "Print_Area",
        "_FilterDatabase",
        "Sheet_Title",
        "Criteria",
        "Consolidate_Area",
        "Print_Titles",
        "Extract",
    }
)
RESERVED_REGEX = re.compile("^_xlnm\\.(?P<name>{0})".format("|".join(RESERVED)))


class DefinedName:
    """A workbook-scoped or sheet-scoped name range.

    ``value`` holds the ``refers_to`` expression (``Sheet1!$A$1:$A$10``
    or an external reference). ``localSheetId`` is ``None`` for
    workbook-scoped names or the 0-based sheet index for sheet-scoped
    ones. ``hidden=True`` marks internal names Excel uses for print
    areas and table ranges.

    ``attr_text`` is an openpyxl-compat alias for ``value`` accepted on
    construction; ``DefinedName(name="X", attr_text="Sheet1!A1")`` is
    equivalent to ``DefinedName(name="X", value="Sheet1!A1")``.

    The remaining ECMA-376 ``definedName`` attributes are exposed via
    snake_case fields with openpyxl camelCase aliases:

    - ``custom_menu`` (``customMenu``) — string, custom menu text.
    - ``description`` (``description``) — string, free-text description.
    - ``help`` (``help``) — string, help text.
    - ``status_bar`` (``statusBar``) — string, status-bar prompt.
    - ``shortcut_key`` (``shortcutKey``) — single-character keyboard
      shortcut.
    - ``function`` (``function``) — bool, marks the name as a function.
    - ``function_group_id`` (``functionGroupId``) — int, function group
      identifier.
    - ``vb_procedure`` (``vbProcedure``) — bool, marks as a VB procedure.
    - ``xlm`` (``xlm``) — bool, marks as an Excel 4.0 macro.
    - ``publish_to_server`` (``publishToServer``) — bool.
    - ``workbook_parameter`` (``workbookParameter``) — bool.
    """

    __slots__ = (
        "name",
        "value",
        "comment",
        "localSheetId",
        "hidden",
        "custom_menu",
        "description",
        "help",
        "status_bar",
        "shortcut_key",
        "function",
        "function_group_id",
        "vb_procedure",
        "xlm",
        "publish_to_server",
        "workbook_parameter",
        "idx_base",
        "namespace",
        "tagname",
    )

    def __init__(
        self,
        name: str | None = None,
        value: str | None = None,
        *args: Any,
        comment: str | None = None,
        localSheetId: int | None = None,  # noqa: N803 - openpyxl public API
        hidden: bool | None = None,
        attr_text: str | None = None,
        custom_menu: str | None = None,
        customMenu: str | None = None,  # noqa: N803 - openpyxl alias
        description: str | None = None,
        help: str | None = None,  # noqa: A002 - openpyxl public API
        status_bar: str | None = None,
        statusBar: str | None = None,  # noqa: N803 - openpyxl alias
        shortcut_key: str | None = None,
        shortcutKey: str | None = None,  # noqa: N803 - openpyxl alias
        function: bool | None = None,
        function_group_id: int | None = None,
        functionGroupId: int | None = None,  # noqa: N803 - openpyxl alias
        vb_procedure: bool | None = None,
        vbProcedure: bool | None = None,  # noqa: N803 - openpyxl alias
        xlm: bool | None = None,
        publish_to_server: bool | None = None,
        publishToServer: bool | None = None,  # noqa: N803 - openpyxl alias
        workbook_parameter: bool | None = None,
        workbookParameter: bool | None = None,  # noqa: N803 - openpyxl alias
    ) -> None:
        if args:
            if len(args) > 14:
                raise TypeError(
                    f"DefinedName expected at most 16 positional arguments, got {len(args) + 2}"
                )
            openpyxl_args = (value, *args)
            (
                comment,
                customMenu,
                description,
                help,
                statusBar,
                localSheetId,
                hidden,
                function,
                vbProcedure,
                xlm,
                functionGroupId,
                shortcutKey,
                publishToServer,
                workbookParameter,
                attr_text,
            ) = openpyxl_args + (None,) * (15 - len(openpyxl_args))
            value = attr_text
        if value is not None and attr_text is not None and value != attr_text:
            raise TypeError(
                "DefinedName: pass either 'value' or 'attr_text', not both with conflicting values"
            )
        self.name: str = "" if name is None else name
        self.value: Any = value if value is not None else attr_text
        self.comment: str | None = comment
        self.localSheetId: int | None = localSheetId  # noqa: N815
        self.hidden: bool | None = hidden

        self.custom_menu: str | None = _pick_alias(
            "custom_menu", custom_menu, "customMenu", customMenu
        )
        self.description: str | None = description
        self.help: str | None = help
        self.status_bar: str | None = _pick_alias(
            "status_bar", status_bar, "statusBar", statusBar
        )
        self.shortcut_key: str | None = _pick_alias(
            "shortcut_key", shortcut_key, "shortcutKey", shortcutKey
        )
        self.function: bool | None = function
        self.function_group_id: int | None = _pick_alias(
            "function_group_id", function_group_id, "functionGroupId", functionGroupId
        )
        self.vb_procedure: bool | None = _pick_alias(
            "vb_procedure", vb_procedure, "vbProcedure", vbProcedure
        )
        self.xlm: bool | None = xlm
        self.publish_to_server: bool | None = _pick_alias(
            "publish_to_server", publish_to_server, "publishToServer", publishToServer
        )
        self.workbook_parameter: bool | None = _pick_alias(
            "workbook_parameter",
            workbook_parameter,
            "workbookParameter",
            workbookParameter,
        )
        self.idx_base = 0
        self.namespace = None
        self.tagname = "definedName"

    @property
    def attr_text(self) -> str:
        """openpyxl alias for ``.value``."""
        return self.value

    @attr_text.setter
    def attr_text(self, v: str) -> None:
        self.value = v

    @property
    def type(self) -> str:  # noqa: A003 - openpyxl public API
        """Best-effort openpyxl-compatible defined-name value category."""
        text = "" if self.value is None else str(self.value)
        token = Tokenizer("=" + text).items[0]
        if token.type == "OPERAND":
            return token.subtype
        return token.type

    @property
    def is_external(self) -> bool:
        return re.compile(r"^\[\d+\].*").match(str(self.value)) is not None

    @property
    def is_reserved(self) -> str | None:
        prefix = "_xlnm."
        if self.name.startswith(prefix):
            return self.name[len(prefix):]
        return None

    @property
    def destinations(self) -> Any:
        """Yield ``(sheet_name, range)`` pairs for range-like names."""
        if self.type != "RANGE":
            return iter(())
        return self._iter_destinations()

    def _iter_destinations(self) -> Any:
        for part in Tokenizer("=" + str(self.value)).items:
            if part.subtype != "RANGE":
                continue
            match = SHEETRANGE_RE.match(part.value)
            if match is None:
                continue
            sheet = match.group("notquoted") or match.group("quoted")
            yield sheet, match.group("cells")

    @classmethod
    def from_tree(cls, node: Any) -> "DefinedName":
        """Build a defined name from an openpyxl-shaped XML element."""
        attrs = dict(getattr(node, "attrib", {}))
        name = attrs.pop("name")
        attr_text = getattr(node, "text", None) or ""
        return cls(
            name=name,
            attr_text=attr_text,
            comment=attrs.get("comment"),
            localSheetId=_optional_int(attrs.get("localSheetId")),
            hidden=_optional_bool(attrs.get("hidden")),
            customMenu=attrs.get("customMenu"),
            description=attrs.get("description"),
            help=attrs.get("help"),
            statusBar=attrs.get("statusBar"),
            shortcutKey=attrs.get("shortcutKey"),
            function=_optional_bool(attrs.get("function")),
            functionGroupId=_optional_int(attrs.get("functionGroupId")),
            vbProcedure=_optional_bool(attrs.get("vbProcedure")),
            xlm=_optional_bool(attrs.get("xlm")),
            publishToServer=_optional_bool(attrs.get("publishToServer")),
            workbookParameter=_optional_bool(attrs.get("workbookParameter")),
        )

    def to_tree(self, tagname: str | None = None, _idx: int | None = None) -> Any:
        """Return an openpyxl-compatible ``<definedName>`` XML element."""
        node = Element(tagname or self.tagname)
        node.set("name", self.name)
        _set_optional(node, "comment", self.comment)
        _set_optional(node, "customMenu", self.custom_menu)
        _set_optional(node, "description", self.description)
        _set_optional(node, "help", self.help)
        _set_optional(node, "statusBar", self.status_bar)
        _set_optional_int(node, "localSheetId", self.localSheetId)
        _set_optional_bool(node, "hidden", self.hidden)
        _set_optional_bool(node, "function", self.function)
        _set_optional_bool(node, "vbProcedure", self.vb_procedure)
        _set_optional_bool(node, "xlm", self.xlm)
        _set_optional_int(node, "functionGroupId", self.function_group_id)
        _set_optional(node, "shortcutKey", self.shortcut_key)
        _set_optional_bool(node, "publishToServer", self.publish_to_server)
        _set_optional_bool(node, "workbookParameter", self.workbook_parameter)
        if self.value is not None:
            node.text = safe_string(self.value)
        return node

    def __iter__(self):
        for key in (
            "name",
            "comment",
            "customMenu",
            "description",
            "help",
            "statusBar",
            "localSheetId",
            "hidden",
            "function",
            "vbProcedure",
            "xlm",
            "functionGroupId",
            "shortcutKey",
            "publishToServer",
            "workbookParameter",
        ):
            value = getattr(self, key)
            if value is None:
                continue
            if key == "name" and value in RESERVED:
                value = "_xlnm." + value
            yield key, safe_string(value)

    @property
    def customMenu(self) -> str | None:  # noqa: N802 - openpyxl alias
        return self.custom_menu

    @customMenu.setter
    def customMenu(self, v: str | None) -> None:  # noqa: N802
        self.custom_menu = v

    @property
    def statusBar(self) -> str | None:  # noqa: N802 - openpyxl alias
        return self.status_bar

    @statusBar.setter
    def statusBar(self, v: str | None) -> None:  # noqa: N802
        self.status_bar = v

    @property
    def shortcutKey(self) -> str | None:  # noqa: N802 - openpyxl alias
        return self.shortcut_key

    @shortcutKey.setter
    def shortcutKey(self, v: str | None) -> None:  # noqa: N802
        self.shortcut_key = v

    @property
    def functionGroupId(self) -> int | None:  # noqa: N802 - openpyxl alias
        return self.function_group_id

    @functionGroupId.setter
    def functionGroupId(self, v: int | None) -> None:  # noqa: N802
        self.function_group_id = v

    @property
    def vbProcedure(self) -> bool | None:  # noqa: N802 - openpyxl alias
        return self.vb_procedure

    @vbProcedure.setter
    def vbProcedure(self, v: bool | None) -> None:  # noqa: N802
        self.vb_procedure = v

    @property
    def publishToServer(self) -> bool | None:  # noqa: N802 - openpyxl alias
        return self.publish_to_server

    @publishToServer.setter
    def publishToServer(self, v: bool | None) -> None:  # noqa: N802
        self.publish_to_server = v

    @property
    def workbookParameter(self) -> bool | None:  # noqa: N802 - openpyxl alias
        return self.workbook_parameter

    @workbookParameter.setter
    def workbookParameter(self, v: bool | None) -> None:  # noqa: N802
        self.workbook_parameter = v

    def __repr__(self) -> str:
        bits = [f"name={self.name!r}", f"value={self.value!r}"]
        if self.localSheetId is not None:
            bits.append(f"localSheetId={self.localSheetId}")
        if self.hidden:
            bits.append("hidden=True")
        if self.comment is not None:
            bits.append(f"comment={self.comment!r}")
        for attr in (
            "custom_menu",
            "description",
            "help",
            "status_bar",
            "shortcut_key",
            "function",
            "function_group_id",
            "vb_procedure",
            "xlm",
            "publish_to_server",
            "workbook_parameter",
        ):
            v = getattr(self, attr)
            if v is not None and v is not False:
                bits.append(f"{attr}={v!r}")
        return f"DefinedName({', '.join(bits)})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, DefinedName):
            return NotImplemented
        return all(
            getattr(self, attr) == getattr(other, attr) for attr in self.__slots__
        )

    def __hash__(self) -> int:
        return hash(
            (
                self.name,
                self.value,
                self.localSheetId,
                self.hidden,
                self.custom_menu,
                self.description,
                self.help,
                self.status_bar,
                self.shortcut_key,
                self.function,
                self.function_group_id,
                self.vb_procedure,
                self.xlm,
                self.publish_to_server,
                self.workbook_parameter,
            )
        )


class _DeletedDefinedName:
    """Internal save-queue sentinel for ``del wb.defined_names[name]``."""

    __slots__ = ("name", "localSheetId", "delete")

    def __init__(
        self,
        name: str,
        localSheetId: int | None = None,  # noqa: N803 - mirrors DefinedName
    ) -> None:
        self.name = name
        self.localSheetId = localSheetId  # noqa: N815
        self.delete = True


DefinedName.__signature__ = _inspect.Signature(
    [
        _inspect.Parameter("name", _inspect.Parameter.POSITIONAL_OR_KEYWORD, default=None),
        _inspect.Parameter("comment", _inspect.Parameter.POSITIONAL_OR_KEYWORD, default=None),
        _inspect.Parameter("customMenu", _inspect.Parameter.POSITIONAL_OR_KEYWORD, default=None),
        _inspect.Parameter("description", _inspect.Parameter.POSITIONAL_OR_KEYWORD, default=None),
        _inspect.Parameter("help", _inspect.Parameter.POSITIONAL_OR_KEYWORD, default=None),
        _inspect.Parameter("statusBar", _inspect.Parameter.POSITIONAL_OR_KEYWORD, default=None),
        _inspect.Parameter("localSheetId", _inspect.Parameter.POSITIONAL_OR_KEYWORD, default=None),
        _inspect.Parameter("hidden", _inspect.Parameter.POSITIONAL_OR_KEYWORD, default=None),
        _inspect.Parameter("function", _inspect.Parameter.POSITIONAL_OR_KEYWORD, default=None),
        _inspect.Parameter("vbProcedure", _inspect.Parameter.POSITIONAL_OR_KEYWORD, default=None),
        _inspect.Parameter("xlm", _inspect.Parameter.POSITIONAL_OR_KEYWORD, default=None),
        _inspect.Parameter("functionGroupId", _inspect.Parameter.POSITIONAL_OR_KEYWORD, default=None),
        _inspect.Parameter("shortcutKey", _inspect.Parameter.POSITIONAL_OR_KEYWORD, default=None),
        _inspect.Parameter("publishToServer", _inspect.Parameter.POSITIONAL_OR_KEYWORD, default=None),
        _inspect.Parameter("workbookParameter", _inspect.Parameter.POSITIONAL_OR_KEYWORD, default=None),
        _inspect.Parameter("attr_text", _inspect.Parameter.POSITIONAL_OR_KEYWORD, default=None),
    ]
)


def _pick_alias(
    snake_name: str,
    snake_value: Any,
    camel_name: str,
    camel_value: Any,
) -> Any:
    """Return whichever alias the caller supplied, raising on conflict.

    `None` from either side means "not supplied" — Python `None` is the
    sentinel for "leave default" since none of these ECMA-376 attrs have
    a meaningful `None` value at rest.
    """
    if snake_value is not None and camel_value is not None and snake_value != camel_value:
        raise TypeError(
            f"DefinedName: pass either {snake_name!r} or {camel_name!r}, "
            "not both with conflicting values"
        )
    return snake_value if snake_value is not None else camel_value


def _optional_bool(value: str | bool | None) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    return value not in {"0", "false", "False"}


def _optional_int(value: str | int | None) -> int | None:
    if value is None:
        return None
    return int(value)


def _set_optional(node: ET.Element, key: str, value: str | None) -> None:
    if value is not None:
        node.set(key, value)


def _set_optional_int(node: ET.Element, key: str, value: int | None) -> None:
    if value is not None:
        node.set(key, str(value))


def _set_optional_bool(node: ET.Element, key: str, value: bool | None) -> None:
    if value is not None:
        node.set(key, "1" if value else "0")


class DefinedNameList(list):
    """openpyxl-shaped list-of-:class:`DefinedName`.

    openpyxl 3.0 used a ``DefinedNameList`` — newer releases moved to
    a dict.  Wolfxl exposes both shapes for import-compat parity:
    :class:`DefinedNameList` here, :class:`~wolfxl.workbook.DefinedNameDict`
    in :mod:`wolfxl.workbook` (the real container backing
    ``wb.defined_names``).

    Pod 2 (RFC-060 §2.6).
    """

    tagname = "definedNames"

    def __init__(self, definedName=()):  # type: ignore[no-untyped-def]  # noqa: N803
        super().__init__(definedName or ())

    @property
    def definedName(self):  # type: ignore[no-untyped-def]  # noqa: N802
        return self

    @definedName.setter
    def definedName(self, value):  # type: ignore[no-untyped-def]  # noqa: N802
        self[:] = list(value or ())

    @classmethod
    def from_tree(cls, node):  # type: ignore[no-untyped-def]
        return cls(
            definedName=[
                DefinedName.from_tree(child)
                for child in list(node)
                if getattr(child, "tag", "").rsplit("}", 1)[-1] == "definedName"
            ]
        )

    def by_sheet(self):  # type: ignore[no-untyped-def]
        from wolfxl.workbook import DefinedNameDict

        names = defaultdict(DefinedNameDict)
        for defn in self.definedName:
            if defn.localSheetId is None:
                if defn.name in {
                    "_xlnm.Print_Titles",
                    "_xlnm.Print_Area",
                    "_xlnm._FilterDatabase",
                }:
                    continue
                names["global"][defn.name] = defn
            else:
                names[int(defn.localSheetId)][defn.name] = defn
        return names


def __getattr__(name: str):  # type: ignore[no-untyped-def]
    """Lazy re-export to dodge a circular ``wolfxl.workbook`` import."""
    if name == "DefinedNameDict":
        from wolfxl.workbook import DefinedNameDict as _D
        return _D
    return _openpyxl_name_fallback(globals())(name)


__all__ = [
    "DefinedName",
    "DefinedNameDict",
    "DefinedNameList",
    "RESERVED",
    "RESERVED_REGEX",
    "SHEETRANGE_RE",
]
