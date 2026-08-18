//! Property test — random `(rel_type, target, mode)` triples → `add` →
//! `serialize` → `parse` and assert structural equality.
//!
//! Catches escape-handling regressions (RFC-010 §6 "Property test"). 1000
//! iterations as specified in the RFC.

use proptest::prelude::*;
use wolfxl_rels::{RelsGraph, TargetMode};

// Pool of relationship types — we sample a known constant so the test
// doesn't accidentally produce a corrupt URI.
fn rel_type_strategy() -> impl Strategy<Value = String> {
    prop::sample::select(vec![
        wolfxl_rels::rt::HYPERLINK.to_string(),
        wolfxl_rels::rt::COMMENTS.to_string(),
        wolfxl_rels::rt::TABLE.to_string(),
        wolfxl_rels::rt::IMAGE.to_string(),
        wolfxl_rels::rt::WORKSHEET.to_string(),
        wolfxl_rels::rt::OLE_OBJECT.to_string(),
    ])
}

// Targets are "any printable ASCII", explicitly including the five
// XML-escapable characters & < > " '. Empty string is a legal target.
fn target_strategy() -> impl Strategy<Value = String> {
    prop::collection::vec(any::<char>(), 0..40)
        .prop_map(|chars| chars.into_iter().filter(|c| !c.is_control()).collect())
}

fn mode_strategy() -> impl Strategy<Value = TargetMode> {
    prop_oneof![Just(TargetMode::Internal), Just(TargetMode::External)]
}

proptest! {
    #![proptest_config(ProptestConfig {
        cases: 1000,
        // Don't let proptest spend forever on shrinks for trivial cases.
        max_shrink_iters: 200,
        ..Default::default()
    })]

    #[test]
    fn add_serialize_parse_round_trips(
        triples in prop::collection::vec(
            (rel_type_strategy(), target_strategy(), mode_strategy()),
            0..16
        )
    ) {
        let mut g = RelsGraph::new();
        for (rt_uri, target, mode) in &triples {
            g.add(rt_uri, target, *mode);
        }
        let bytes = g.serialize();
        let g2 = RelsGraph::parse(&bytes)
            .map_err(|e| TestCaseError::fail(format!("parse failed: {e}")))?;
        prop_assert_eq!(g, g2, "structural round-trip failure");
    }
}
