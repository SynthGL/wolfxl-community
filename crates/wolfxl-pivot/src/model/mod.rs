//! Typed OOXML pivot-cache + pivot-table model. Mirrors the §10
//! contracts of RFC-047 / RFC-048 / RFC-049. PyO3-free — the Python
//! `to_rust_dict()` and the PyO3 binding in `src/wolfxl/` together
//! convert the dict shape to these structs.

pub mod cache;
pub mod records;
pub mod table;
// RFC-061 sub-features.
pub mod slicer;
pub mod slicer_cache;
