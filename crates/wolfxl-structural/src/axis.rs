//! `Axis` enum + unified `ShiftPlan` type for the structural rewrites.
//!
//! Designed as the single seam shared between RFC-030 (rows) and
//! RFC-031 (cols): RFC-031's only API delta is constructing
//! `ShiftPlan { axis: Axis::Col, .. }` instead of `Axis::Row`.

/// Which axis a structural shift operates on.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Axis {
    /// Row shift — affects `<row r="">`, the row part of `<c r="">`,
    /// and the row component of every `ref` / `sqref`.
    Row,
    /// Col shift — affects the col-letter part of `<c r="">` and
    /// the col component of every `ref` / `sqref`.
    Col,
}

impl Axis {
    /// True if this axis is `Row`.
    pub fn is_row(self) -> bool {
        matches!(self, Axis::Row)
    }
    /// True if this axis is `Col`.
    pub fn is_col(self) -> bool {
        matches!(self, Axis::Col)
    }
}

/// Plan for a single structural shift (insert OR delete) on one axis.
///
/// `idx` is 1-based; `n` is the signed delta — positive = insert
/// (rows/cols at `>= idx` shift by `+n`); negative = delete (rows/cols
/// in `[idx, idx + |n|)` are removed and rows/cols at `>= idx + |n|`
/// shift by `n`).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct ShiftPlan {
    /// Row or col axis.
    pub axis: Axis,
    /// 1-based index where shifting begins.
    pub idx: u32,
    /// Signed shift count (positive = insert; negative = delete).
    pub n: i32,
}

impl ShiftPlan {
    /// Construct an insert plan: `n` positive new units at `idx`.
    pub fn insert(axis: Axis, idx: u32, n: u32) -> Self {
        Self {
            axis,
            idx,
            n: n as i32,
        }
    }
    /// Construct a delete plan: `n` units removed starting at `idx`.
    pub fn delete(axis: Axis, idx: u32, n: u32) -> Self {
        Self {
            axis,
            idx,
            n: -(n as i32),
        }
    }

    /// True if this plan inserts (n > 0).
    pub fn is_insert(self) -> bool {
        self.n > 0
    }
    /// True if this plan deletes (n < 0).
    pub fn is_delete(self) -> bool {
        self.n < 0
    }
    /// True if this plan is a no-op (n == 0).
    pub fn is_noop(self) -> bool {
        self.n == 0
    }
    /// Absolute shift magnitude.
    pub fn abs_n(self) -> u32 {
        self.n.unsigned_abs()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn axis_is_helpers() {
        assert!(Axis::Row.is_row());
        assert!(!Axis::Row.is_col());
        assert!(Axis::Col.is_col());
        assert!(!Axis::Col.is_row());
    }

    #[test]
    fn shift_plan_constructors() {
        let p = ShiftPlan::insert(Axis::Row, 5, 3);
        assert_eq!(p.idx, 5);
        assert_eq!(p.n, 3);
        assert!(p.is_insert());
        assert!(!p.is_delete());

        let d = ShiftPlan::delete(Axis::Col, 2, 4);
        assert_eq!(d.idx, 2);
        assert_eq!(d.n, -4);
        assert!(d.is_delete());
        assert_eq!(d.abs_n(), 4);
    }

    #[test]
    fn shift_plan_noop() {
        let p = ShiftPlan {
            axis: Axis::Row,
            idx: 1,
            n: 0,
        };
        assert!(p.is_noop());
        assert!(!p.is_insert());
        assert!(!p.is_delete());
    }
}
