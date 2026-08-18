"""IndexedList — list with O(1) ``index`` lookup.

openpyxl uses :class:`IndexedList` to back the shared-strings
table (``xl/sharedStrings.xml``): entries are appended in order
(stable indices) and looked up by value during cell-write to
re-use existing slots.

Wolfxl's shared-strings table lives in Rust and the Python proxy
class doesn't drive it; this module exists so user code that
imports ``openpyxl.utils.indexed_list.IndexedList`` (e.g. for
custom tables) can be migrated with a one-line import swap.

Reference: ``openpyxl.utils.indexed_list`` (openpyxl 3.1.x).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


class IndexedList(list):
    """A list with an O(1) :meth:`index` lookup via a backing dict.

    Behavior matches openpyxl's :class:`IndexedList` exactly:

    * :meth:`add` appends ``value`` if not already present and
      returns its index.
    * :meth:`index` returns the existing index of ``value``;
      raises :class:`ValueError` when absent (matches built-in
      ``list.index``).
    * Membership tests via ``in`` are O(1) after the backing dict
      has been rebuilt.
    * The ``clean`` instance attribute mirrors openpyxl's flag:
      iterable construction starts dirty and the first membership
      lookup rebuilds the table.

    Example::

        >>> il = IndexedList(["a", "b", "c"])
        >>> il.index("b")
        1
        >>> il.add("d")  # appended at end
        3
        >>> il.add("a")  # already present
        0
        >>> "c" in il
        True
    """

    clean: bool

    def __init__(self, iterable: Iterable[Any] | None = None) -> None:
        self.clean = True
        self._dict: dict[Any, int] = {}
        if iterable is not None:
            self.clean = False
            for idx, value in enumerate(iterable):
                try:
                    self._dict[value] = idx
                except TypeError:
                    pass
                list.append(self, value)

    def _rebuild_dict(self) -> None:
        self._dict = {}
        idx = 0
        for value in self:
            try:
                present = value in self._dict
            except TypeError:
                present = list.__contains__(self, value)
            if not present:
                try:
                    self._dict[value] = idx
                except TypeError:
                    pass
                idx += 1
        self.clean = True

    def add(self, value: Any) -> int:
        """Append ``value`` if absent; return its 0-based index.

        Idempotent: calling :meth:`add` with a value already in
        the list returns the existing index without modifying
        the list.
        """
        self.append(value)
        try:
            return self._dict[value]
        except TypeError:
            return list.index(self, value)

    def index(self, value: Any, *args: Any, **kwargs: Any) -> int:  # type: ignore[override]
        """Return the 0-based index of ``value``.

        O(1) via the backing dict.  Raises :class:`ValueError`
        when ``value`` isn't present, matching the standard
        ``list.index`` contract.  Optional ``start``/``stop``
        positional args are accepted for ``list.index``
        compatibility but ignored — openpyxl's IndexedList does
        the same.
        """
        if value in self:
            try:
                return self._dict[value]
            except TypeError:
                return list.index(self, value)
        raise ValueError

    def __contains__(self, value: object) -> bool:  # type: ignore[override]
        # O(1) via the backing dict, vs O(n) on plain list.
        if not self.clean:
            self._rebuild_dict()
        try:
            return value in self._dict
        except TypeError:
            return list.__contains__(self, value)

    def append(self, value: Any) -> None:
        try:
            present = value in self._dict
        except TypeError:
            present = list.__contains__(self, value)
        if not present:
            try:
                self._dict[value] = len(self)
            except TypeError:
                pass
            list.append(self, value)


__all__ = ["IndexedList"]
