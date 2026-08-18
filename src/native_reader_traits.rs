//! Style-resolution trait shared between native XLSX and XLSB backends.
//!
//! Per-feature reader modules (`native_reader_sheet_data`,
//! `native_reader_styles`) take any `B: NativeStyleResolver` so they can run
//! generic record/format dispatch without knowing whether the underlying book
//! is xlsx-flavoured or xlsb-flavoured.

use wolfxl_reader::{
    AlignmentInfo, BorderInfo, FillInfo, FontInfo, NativeXlsbBook as NativeXlsbReaderBook,
    NativeXlsxBook as NativeReaderBook, ProtectionInfo,
};

pub(crate) trait NativeStyleResolver {
    fn number_format_for_style_id(&self, style_id: u32) -> Option<&str>;
    fn border_for_style_id(&self, style_id: u32) -> Option<&BorderInfo>;
    fn font_for_style_id(&self, style_id: u32) -> Option<&FontInfo>;
    fn fill_for_style_id(&self, style_id: u32) -> Option<&FillInfo>;
    fn alignment_for_style_id(&self, style_id: u32) -> Option<&AlignmentInfo>;
    fn protection_for_style_id(&self, style_id: u32) -> Option<&ProtectionInfo>;
    fn named_style_for_style_id(&self, style_id: u32) -> Option<&str>;
    fn date1904(&self) -> bool;
}

impl NativeStyleResolver for NativeReaderBook {
    fn number_format_for_style_id(&self, style_id: u32) -> Option<&str> {
        self.number_format_for_style_id(style_id)
    }

    fn border_for_style_id(&self, style_id: u32) -> Option<&BorderInfo> {
        self.border_for_style_id(style_id)
    }

    fn font_for_style_id(&self, style_id: u32) -> Option<&FontInfo> {
        self.font_for_style_id(style_id)
    }

    fn fill_for_style_id(&self, style_id: u32) -> Option<&FillInfo> {
        self.fill_for_style_id(style_id)
    }

    fn alignment_for_style_id(&self, style_id: u32) -> Option<&AlignmentInfo> {
        self.alignment_for_style_id(style_id)
    }

    fn protection_for_style_id(&self, style_id: u32) -> Option<&ProtectionInfo> {
        self.protection_for_style_id(style_id)
    }

    fn named_style_for_style_id(&self, style_id: u32) -> Option<&str> {
        self.named_style_for_style_id(style_id)
    }

    fn date1904(&self) -> bool {
        self.date1904()
    }
}

impl NativeStyleResolver for NativeXlsbReaderBook {
    fn number_format_for_style_id(&self, style_id: u32) -> Option<&str> {
        self.number_format_for_style_id(style_id)
    }

    fn border_for_style_id(&self, style_id: u32) -> Option<&BorderInfo> {
        self.border_for_style_id(style_id)
    }

    fn font_for_style_id(&self, style_id: u32) -> Option<&FontInfo> {
        self.font_for_style_id(style_id)
    }

    fn fill_for_style_id(&self, style_id: u32) -> Option<&FillInfo> {
        self.fill_for_style_id(style_id)
    }

    fn alignment_for_style_id(&self, style_id: u32) -> Option<&AlignmentInfo> {
        self.alignment_for_style_id(style_id)
    }

    fn protection_for_style_id(&self, _style_id: u32) -> Option<&ProtectionInfo> {
        None
    }

    fn named_style_for_style_id(&self, _style_id: u32) -> Option<&str> {
        // XLSB does not yet plumb cellStyles through; return None until the
        // BIFF12 parser learns BrtBeginStyles + BrtBeginStyleSheet.
        None
    }

    fn date1904(&self) -> bool {
        self.date1904()
    }
}
