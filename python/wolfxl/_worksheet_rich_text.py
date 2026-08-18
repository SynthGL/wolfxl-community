"""Rich-text payload helpers for worksheet flush paths."""

from __future__ import annotations

from typing import Any


def cellrichtext_to_runs_payload(crt: Any) -> list[tuple[str, dict[str, Any] | None]]:
    """Convert a ``CellRichText`` into Rust-side ``(text, font)`` runs."""
    out: list[tuple[str, dict[str, Any] | None]] = []
    for item in crt:
        if isinstance(item, str):
            out.append((item, None))
            continue
        font = item.font
        d: dict[str, Any] = {}
        if font.b is not None:
            d["b"] = bool(font.b)
        if font.i is not None:
            d["i"] = bool(font.i)
        if font.strike is not None:
            d["strike"] = bool(font.strike)
        if font.u is not None:
            d["u"] = font.u
        if font.sz is not None:
            d["sz"] = float(font.sz)
        if font.color is not None:
            d["color"] = font.color
        if font.rFont is not None:
            d["rFont"] = font.rFont
        if font.family is not None:
            d["family"] = int(font.family)
        if font.charset is not None:
            d["charset"] = int(font.charset)
        if font.vertAlign is not None:
            d["vertAlign"] = font.vertAlign
        if font.scheme is not None:
            d["scheme"] = font.scheme
        out.append((item.text, d if d else None))
    return out


def runs_payload_to_cellrichtext(payload: Any) -> Any:
    """Convert Rust-side rich-text run payloads into ``CellRichText``.

    Args:
        payload: Iterable of ``(text, font_dict)`` entries returned by the
            Rust reader, or ``None`` when the cell has no rich-text runs.

    Returns:
        A ``CellRichText`` object for non-empty payloads, otherwise ``None``.
    """
    if payload is None:
        return None

    from wolfxl.cell.rich_text import CellRichText, InlineFont, TextBlock

    out = CellRichText()
    for entry in payload:
        text, font_dict = entry[0], entry[1]
        if font_dict is None:
            out.append(text)
            continue
        out.append(
            TextBlock(
                InlineFont(
                    rFont=font_dict.get("rFont"),
                    charset=font_dict.get("charset"),
                    family=font_dict.get("family"),
                    b=font_dict.get("b"),
                    i=font_dict.get("i"),
                    strike=font_dict.get("strike"),
                    color=font_dict.get("color"),
                    sz=font_dict.get("sz"),
                    u=font_dict.get("u"),
                    vertAlign=font_dict.get("vertAlign"),
                    scheme=font_dict.get("scheme"),
                ),
                text,
            )
        )
    return out
