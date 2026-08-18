//! Integration test — `tier2/13_hyperlinks.xlsx` has three external
//! hyperlinks on sheet2; verify that after parse, no `(Target, Type)` pair is
//! duplicated, and that `find_by_target` correctly identifies an existing
//! match (the predicate a future `set_hyperlink` call will use to dedupe).

use std::fs::File;
use std::io::Read;
use std::path::PathBuf;

use wolfxl_rels::{rt, RelsGraph, TargetMode};

fn fixtures_dir() -> PathBuf {
    let manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    manifest
        .parent()
        .and_then(|p| p.parent())
        .expect("workspace root")
        .join("tests/fixtures")
}

fn read_zip_entry(xlsx: &PathBuf, name: &str) -> Option<Vec<u8>> {
    let f = File::open(xlsx).ok()?;
    let mut zip = zip::ZipArchive::new(f).ok()?;
    let mut entry = zip.by_name(name).ok()?;
    let mut buf = Vec::new();
    entry.read_to_end(&mut buf).ok()?;
    Some(buf)
}

#[test]
fn hyperlinks_fixture_has_no_duplicate_targets() {
    let xlsx = fixtures_dir().join("tier2/13_hyperlinks.xlsx");
    if !xlsx.exists() {
        eprintln!("fixture {} not found, skipping", xlsx.display());
        return;
    }
    let bytes = read_zip_entry(&xlsx, "xl/worksheets/_rels/sheet2.xml.rels")
        .expect("sheet2 rels entry must exist");
    let g = RelsGraph::parse(&bytes).expect("parse");
    assert_eq!(g.len(), 3, "fixture has three hyperlinks");

    // No (Target, Type) pair appears twice.
    let mut seen = std::collections::HashSet::new();
    for r in g.iter() {
        let key = (r.target.clone(), r.rel_type.clone(), r.mode);
        assert!(
            seen.insert(key.clone()),
            "duplicate (Target, Type, Mode) pair: {:?}",
            key
        );
    }

    // find_by_target round-trip: every existing target must be findable by
    // its own (Target, Mode) pair, and the returned id must be the original.
    for r in g.iter() {
        let found = g
            .find_by_target(&r.target, r.mode)
            .expect("must find existing target");
        assert_eq!(found.id, r.id);
        assert_eq!(found.rel_type, rt::HYPERLINK);
        assert_eq!(found.mode, TargetMode::External);
    }
}

#[test]
fn no_op_save_cycle_preserves_target_uniqueness() {
    // Simulate the "no-op patch+save" cycle from RFC-010 §6 test 11. We
    // don't actually have a patcher hook yet (RFC-022 wires it up), so we
    // demonstrate the property at the graph layer: parse → serialize →
    // parse must not introduce duplicates.
    let xlsx = fixtures_dir().join("tier2/13_hyperlinks.xlsx");
    if !xlsx.exists() {
        return;
    }
    let bytes = read_zip_entry(&xlsx, "xl/worksheets/_rels/sheet2.xml.rels").unwrap();
    let g1 = RelsGraph::parse(&bytes).unwrap();
    let g2 = RelsGraph::parse(&g1.serialize()).unwrap();
    assert_eq!(g1.len(), g2.len());
    let mut targets: Vec<_> = g2
        .iter()
        .map(|r| (&r.target, &r.rel_type, r.mode))
        .collect();
    targets.sort();
    targets.dedup();
    assert_eq!(targets.len(), g2.len(), "no duplicates after round-trip");
}
