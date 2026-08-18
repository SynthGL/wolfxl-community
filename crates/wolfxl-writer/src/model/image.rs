//! Image (drawing) data.
//!
//! Each [`SheetImage`] is one image queued via Python's
//! ``ws.add_image(img, "B5")``. The native writer's emit layer consumes
//! the worksheet's `Vec<SheetImage>` to produce
//! `xl/media/imageN.<ext>`, `xl/drawings/drawingN.xml`, and the rels +
//! content-types entries that wire them up.

/// One image attached to a worksheet.
#[derive(Debug, Clone)]
pub struct SheetImage {
    /// Raw image bytes (verbatim; written into `xl/media/imageN.<ext>`).
    pub data: Vec<u8>,
    /// Lowercase extension token: `"png"`, `"jpeg"`, `"gif"`, `"bmp"`.
    pub ext: String,
    /// Pixel width parsed by the Python sniffer.
    pub width_px: u32,
    /// Pixel height.
    pub height_px: u32,
    /// Anchor — one of three flavours. `OneCell` is the default Excel
    /// shape for `ws.add_image(img, "B5")`.
    pub anchor: ImageAnchor,
}

/// Anchor flavour. Coordinates inside `OneCell` and `TwoCell` are
/// 0-based to match OOXML's `<xdr:from>` / `<xdr:to>` element shapes;
/// `Absolute` uses raw EMU.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ImageAnchor {
    /// Pin top-left to one cell; image extent comes from pixel dims
    /// (writer converts px to EMU at 9525 EMU/px).
    OneCell {
        from_col: u32,
        from_row: u32,
        from_col_off: i64,
        from_row_off: i64,
    },
    /// Anchor at two cells; image stretches between them.
    TwoCell {
        from_col: u32,
        from_row: u32,
        from_col_off: i64,
        from_row_off: i64,
        to_col: u32,
        to_row: u32,
        to_col_off: i64,
        to_row_off: i64,
        edit_as: String,
    },
    /// Pure EMU position + extent.
    Absolute {
        x_emu: i64,
        y_emu: i64,
        cx_emu: i64,
        cy_emu: i64,
    },
}

impl ImageAnchor {
    /// Construct a one-cell anchor from a 0-based (col, row) pair.
    pub fn one_cell(col: u32, row: u32) -> Self {
        ImageAnchor::OneCell {
            from_col: col,
            from_row: row,
            from_col_off: 0,
            from_row_off: 0,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn one_cell_helper_zeros_offsets() {
        let a = ImageAnchor::one_cell(1, 4);
        match a {
            ImageAnchor::OneCell {
                from_col,
                from_row,
                from_col_off,
                from_row_off,
            } => {
                assert_eq!(from_col, 1);
                assert_eq!(from_row, 4);
                assert_eq!(from_col_off, 0);
                assert_eq!(from_row_off, 0);
            }
            _ => panic!("expected OneCell"),
        }
    }
}
