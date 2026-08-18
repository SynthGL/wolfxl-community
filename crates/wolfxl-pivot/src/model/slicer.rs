//! `Slicer` — sheet-scoped slicer presentation (RFC-061 §2.1, §10.2).
//!
//! Mirrors openpyxl's slicer table model. One `Slicer` represents an
//! entry inside `xl/slicers/slicer{N}.xml`; references a `SlicerCache`
//! by name and is anchored to a worksheet via a graphic-frame.

/// A slicer presentation. Sheet-scoped — the `<x14:slicerList>` on
/// the owning sheet's `<extLst>` carries one rel per slicer.
///
/// RFC-061 §10.2 contract.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Slicer {
    /// Unique within the slicer presentation file (e.g.
    /// `"Slicer_region1"`).
    pub name: String,
    /// Backreference to the slicer cache by name.
    pub cache_name: String,
    pub caption: String,
    /// Row height in EMU. Default Excel value is 204.
    pub row_height: u32,
    pub column_count: u32,
    pub show_caption: bool,
    /// Slicer style name, e.g. `"SlicerStyleLight1"`. `None` →
    /// inherit theme.
    pub style: Option<String>,
    pub locked: bool,
    /// A1-style anchor cell (top-left of the slicer's graphic
    /// frame).
    pub anchor: String,
}

impl Slicer {
    pub fn new(
        name: impl Into<String>,
        cache_name: impl Into<String>,
        anchor: impl Into<String>,
    ) -> Self {
        Self {
            name: name.into(),
            cache_name: cache_name.into(),
            caption: String::new(),
            row_height: 204,
            column_count: 1,
            show_caption: true,
            style: None,
            locked: true,
            anchor: anchor.into(),
        }
    }

    /// RFC-061 §10.2 validation.
    pub fn validate(&self) -> Result<(), String> {
        if self.name.is_empty() {
            return Err("Slicer requires a non-empty name".into());
        }
        if self.cache_name.is_empty() {
            return Err("Slicer requires a non-empty cache_name".into());
        }
        if self.anchor.is_empty() {
            return Err("Slicer requires a non-empty anchor".into());
        }
        if self.column_count == 0 {
            return Err("Slicer column_count must be ≥ 1".into());
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn defaults() {
        let s = Slicer::new("Slicer_region1", "Slicer_region", "H2");
        assert_eq!(s.row_height, 204);
        assert_eq!(s.column_count, 1);
        assert!(s.show_caption);
        assert!(s.locked);
        assert_eq!(s.style, None);
    }

    #[test]
    fn validate_empty_name_rejects() {
        let mut s = Slicer::new("", "cache", "A1");
        assert!(s.validate().is_err());
        s = Slicer::new("name", "", "A1");
        assert!(s.validate().is_err());
        s = Slicer::new("name", "cache", "");
        assert!(s.validate().is_err());
    }

    #[test]
    fn validate_zero_columns_rejects() {
        let mut s = Slicer::new("name", "cache", "A1");
        s.column_count = 0;
        assert!(s.validate().is_err());
    }

    #[test]
    fn validate_happy() {
        let s = Slicer::new("Slicer_region1", "Slicer_region", "H2");
        assert!(s.validate().is_ok());
    }
}
