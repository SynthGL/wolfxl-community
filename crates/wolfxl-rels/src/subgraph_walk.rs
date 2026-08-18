//! Walk the OOXML rels subgraph rooted at a single worksheet part.
//!
//! Per RFC-035 §5.3 the sheet-copy planner needs the **full set of parts
//! reachable from a source sheet** so it can clone every ancillary part
//! (tables, comments, VML, drawings) and rewrite the rels graph for the
//! destination sheet in one pass. This module owns that walk so the
//! planner stays focused on the mutation/cloning bookkeeping.
//!
//! # Scope
//!
//! - Inputs: a parsed [`RelsGraph`] for the source sheet's `_rels` file
//!   (every direct edge from the sheet) and the source sheet's part path
//!   (e.g. `xl/worksheets/sheet3.xml`).
//! - Output: a [`SheetSubgraph`] containing every reachable part path and
//!   the rels edges, in source-document order.
//! - `External` rels (hyperlinks, OLE links by URL) contribute their target
//!   to neither `reachable_parts` (it is not a ZIP entry) nor
//!   `nested_rels`. They DO appear in `sheet_rels` so a planner can clone
//!   them onto the destination's rels file verbatim.
//!
//! # Nested rels
//!
//! Drawings have their own rels file (`xl/drawings/_rels/drawing<N>.xml.rels`
//! → image targets). The basic [`walk_sheet_subgraph`] does NOT recurse —
//! it only sees what is reachable through one level of rels. Use
//! [`walk_sheet_subgraph_with_nested`] to supply a resolver closure that
//! parses each ancillary part's `_rels` (when present) so the walk
//! returns transitive reachability.

use std::collections::BTreeSet;

use crate::{RelsGraph, TargetMode};

/// All parts reachable from a single source sheet via its rels graph,
/// plus a copy of the sheet's edges and any nested edges discovered by
/// the resolver-aware variant.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct SheetSubgraph {
    /// Every part path (ZIP entry) reachable from the source sheet via
    /// `<Relationship>` edges, including the sheet itself. Sorted by
    /// source-document order, deduplicated. External-mode edges
    /// (hyperlinks, etc.) are NOT included.
    pub reachable_parts: Vec<String>,

    /// `(rId, target_path)` for each direct edge in the source sheet's
    /// rels file. `target_path` is the ABSOLUTE ZIP-relative path
    /// resolved from the sheet's location plus the rel's `Target`.
    /// External-mode edges keep their `Target` verbatim (treated as
    /// opaque URI per OPC §15.2).
    pub sheet_rels: Vec<(String, String)>,

    /// `(parent_part, rId, target_path)` for every edge of every
    /// reachable ancillary part that has a rels file (e.g. drawing
    /// → image). Always empty for [`walk_sheet_subgraph`]; populated
    /// only by [`walk_sheet_subgraph_with_nested`].
    pub nested_rels: Vec<(String, String, String)>,
}

/// Walk the sheet's rels graph one level deep.
///
/// Includes `sheet_part` itself in `reachable_parts` (cloning the
/// subgraph requires cloning the sheet too). Each `Internal` rel
/// contributes its resolved target. `External` rels populate
/// `sheet_rels` only.
///
/// `nested_rels` is always empty for this entry point — use
/// [`walk_sheet_subgraph_with_nested`] when you need transitive
/// reachability (e.g. drawing → image).
pub fn walk_sheet_subgraph(rels: &RelsGraph, sheet_part: &str) -> SheetSubgraph {
    walk_sheet_subgraph_with_nested(rels, sheet_part, |_part: &str| None)
}

/// Walk the sheet's rels graph, recursing into each reachable
/// ancillary part's `_rels` file via the supplied resolver.
///
/// `resolve_nested(part_path)` is called once for every reachable
/// non-sheet part. It should return the parsed [`RelsGraph`] for that
/// part's `_rels` file (e.g. `xl/drawings/_rels/drawing1.xml.rels`),
/// or `None` if the part has no rels file. Targets reachable through
/// the resolver bubble into `reachable_parts` and `nested_rels`.
///
/// Recursion terminates because each part is only visited once
/// (deduped via `reachable_parts`).
pub fn walk_sheet_subgraph_with_nested(
    rels: &RelsGraph,
    sheet_part: &str,
    mut resolve_nested: impl FnMut(&str) -> Option<RelsGraph>,
) -> SheetSubgraph {
    let mut subgraph = SheetSubgraph::default();
    let mut seen: BTreeSet<String> = BTreeSet::new();

    // The sheet itself is always in the subgraph (we have to clone it).
    subgraph.reachable_parts.push(sheet_part.to_string());
    seen.insert(sheet_part.to_string());

    // Walk one level: the sheet's own rels.
    let sheet_dir = parent_dir(sheet_part);
    let mut frontier: Vec<(String, RelsGraph)> = Vec::new();
    for rel in rels.iter() {
        let target_path = match rel.mode {
            TargetMode::Internal => resolve_relative(&sheet_dir, &rel.target),
            TargetMode::External => rel.target.clone(),
        };
        subgraph
            .sheet_rels
            .push((rel.id.0.clone(), target_path.clone()));
        if rel.mode == TargetMode::Internal && seen.insert(target_path.clone()) {
            subgraph.reachable_parts.push(target_path.clone());
            // Defer resolver call to a second pass so we don't borrow
            // the closure recursively while iterating `rels`.
            if let Some(nested_graph) = resolve_nested(&target_path) {
                frontier.push((target_path, nested_graph));
            }
        }
    }

    // Walk the frontier breadth-first via the resolver.
    while let Some((parent_part, nested_graph)) = frontier.pop() {
        let parent_dir_path = parent_dir(&parent_part);
        for rel in nested_graph.iter() {
            let target_path = match rel.mode {
                TargetMode::Internal => resolve_relative(&parent_dir_path, &rel.target),
                TargetMode::External => rel.target.clone(),
            };
            subgraph
                .nested_rels
                .push((parent_part.clone(), rel.id.0.clone(), target_path.clone()));
            if rel.mode == TargetMode::Internal && seen.insert(target_path.clone()) {
                subgraph.reachable_parts.push(target_path.clone());
                if let Some(nested) = resolve_nested(&target_path) {
                    frontier.push((target_path, nested));
                }
            }
        }
    }

    subgraph
}

/// Return the directory portion of a part path. `xl/worksheets/sheet1.xml`
/// → `xl/worksheets`. The empty string for paths with no `/`.
fn parent_dir(part_path: &str) -> String {
    match part_path.rfind('/') {
        Some(idx) => part_path[..idx].to_string(),
        None => String::new(),
    }
}

/// Resolve a ZIP-relative `Target` value (which OPC defines as a URI
/// reference resolved against the part owning the rels file) into an
/// absolute ZIP path.
///
/// Handles `..` segments and `./` segments. Does NOT URL-decode (OPC
/// targets are not percent-encoded in any case the patcher cares
/// about).
fn resolve_relative(base_dir: &str, target: &str) -> String {
    // Absolute ZIP target (rare but legal): leading "/" means "from
    // the package root". Strip the slash.
    if let Some(stripped) = target.strip_prefix('/') {
        return stripped.to_string();
    }

    let mut segments: Vec<&str> = if base_dir.is_empty() {
        Vec::new()
    } else {
        base_dir.split('/').collect()
    };
    for part in target.split('/') {
        match part {
            "" | "." => {}
            ".." => {
                segments.pop();
            }
            other => segments.push(other),
        }
    }
    segments.join("/")
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{rt, RelsGraph, TargetMode};

    fn rels_with(entries: &[(&str, &str, TargetMode)]) -> RelsGraph {
        let mut g = RelsGraph::new();
        for (rel_type, target, mode) in entries {
            g.add(rel_type, target, *mode);
        }
        g
    }

    #[test]
    fn empty_rels_yields_only_sheet() {
        let g = RelsGraph::new();
        let sub = walk_sheet_subgraph(&g, "xl/worksheets/sheet1.xml");
        assert_eq!(sub.reachable_parts, vec!["xl/worksheets/sheet1.xml"]);
        assert!(sub.sheet_rels.is_empty());
        assert!(sub.nested_rels.is_empty());
    }

    #[test]
    fn one_table_one_comments_one_vml_one_hyperlink() {
        let g = rels_with(&[
            (rt::TABLE, "../tables/table1.xml", TargetMode::Internal),
            (rt::COMMENTS, "../comments1.xml", TargetMode::Internal),
            (
                rt::VML_DRAWING,
                "../drawings/vmlDrawing1.vml",
                TargetMode::Internal,
            ),
            (rt::HYPERLINK, "https://example.com", TargetMode::External),
        ]);
        let sub = walk_sheet_subgraph(&g, "xl/worksheets/sheet1.xml");

        assert_eq!(
            sub.reachable_parts,
            vec![
                "xl/worksheets/sheet1.xml".to_string(),
                "xl/tables/table1.xml".to_string(),
                "xl/comments1.xml".to_string(),
                "xl/drawings/vmlDrawing1.vml".to_string(),
            ]
        );

        assert_eq!(sub.sheet_rels.len(), 4);
        assert_eq!(sub.sheet_rels[0].0, "rId1");
        assert_eq!(sub.sheet_rels[0].1, "xl/tables/table1.xml");
        // External hyperlink: target is verbatim (not resolved as a path).
        assert_eq!(sub.sheet_rels[3].1, "https://example.com");
        // External rels are NOT in reachable_parts (they're not ZIP entries).
        assert!(!sub.reachable_parts.contains(&"https://example.com".into()));
    }

    #[test]
    fn external_only_rels_does_not_pollute_reachable_parts() {
        let g = rels_with(&[
            (rt::HYPERLINK, "mailto:a@b.com", TargetMode::External),
            (rt::HYPERLINK, "https://x.com", TargetMode::External),
        ]);
        let sub = walk_sheet_subgraph(&g, "xl/worksheets/sheet9.xml");
        assert_eq!(sub.reachable_parts, vec!["xl/worksheets/sheet9.xml"]);
        assert_eq!(sub.sheet_rels.len(), 2);
    }

    #[test]
    fn duplicate_target_appears_once_in_reachable_parts() {
        // Two table rels happen to point at the same part (degenerate).
        let g = rels_with(&[
            (rt::TABLE, "../tables/table1.xml", TargetMode::Internal),
            (rt::TABLE, "../tables/table1.xml", TargetMode::Internal),
        ]);
        let sub = walk_sheet_subgraph(&g, "xl/worksheets/sheet1.xml");
        // Both edges in sheet_rels.
        assert_eq!(sub.sheet_rels.len(), 2);
        // Only one entry in reachable_parts (deduped).
        let count = sub
            .reachable_parts
            .iter()
            .filter(|p| *p == "xl/tables/table1.xml")
            .count();
        assert_eq!(count, 1);
    }

    #[test]
    fn nested_resolver_finds_drawing_image() {
        // Sheet → drawing1, then drawing1 → image1.
        let sheet_rels = rels_with(&[(
            rt::DRAWING,
            "../drawings/drawing1.xml",
            TargetMode::Internal,
        )]);
        let drawing_rels = rels_with(&[(rt::IMAGE, "../media/image1.png", TargetMode::Internal)]);
        let sub =
            walk_sheet_subgraph_with_nested(&sheet_rels, "xl/worksheets/sheet1.xml", |part| {
                if part == "xl/drawings/drawing1.xml" {
                    Some(drawing_rels.clone())
                } else {
                    None
                }
            });
        assert_eq!(
            sub.reachable_parts,
            vec![
                "xl/worksheets/sheet1.xml".to_string(),
                "xl/drawings/drawing1.xml".to_string(),
                "xl/media/image1.png".to_string(),
            ]
        );
        assert_eq!(sub.nested_rels.len(), 1);
        assert_eq!(sub.nested_rels[0].0, "xl/drawings/drawing1.xml");
        assert_eq!(sub.nested_rels[0].2, "xl/media/image1.png");
    }

    #[test]
    fn nested_walk_terminates_on_cycle() {
        // Hand-crafted cycle: drawing1 → drawing1 (degenerate).
        let sheet_rels = rels_with(&[(
            rt::DRAWING,
            "../drawings/drawing1.xml",
            TargetMode::Internal,
        )]);
        let cyclic = rels_with(&[(rt::DRAWING, "drawing1.xml", TargetMode::Internal)]);
        let sub =
            walk_sheet_subgraph_with_nested(&sheet_rels, "xl/worksheets/sheet1.xml", |part| {
                if part == "xl/drawings/drawing1.xml" {
                    Some(cyclic.clone())
                } else {
                    None
                }
            });
        // No infinite loop — the resolver was called twice (both for
        // drawing1 — once from the sheet's edge, once from the cycle's
        // edge), but `reachable_parts` deduplication stops re-walks.
        assert_eq!(
            sub.reachable_parts
                .iter()
                .filter(|p| **p == "xl/drawings/drawing1.xml")
                .count(),
            1
        );
    }

    #[test]
    fn absolute_target_with_leading_slash_resolves_to_root() {
        // Some files use absolute targets (rare; e.g. some chart parts).
        let g = rels_with(&[(rt::TABLE, "/xl/tables/table1.xml", TargetMode::Internal)]);
        let sub = walk_sheet_subgraph(&g, "xl/worksheets/sheet1.xml");
        assert_eq!(sub.sheet_rels[0].1, "xl/tables/table1.xml");
        assert!(sub.reachable_parts.contains(&"xl/tables/table1.xml".into()));
    }

    #[test]
    fn multi_dotdot_resolves_correctly() {
        // ../../foo/bar.xml from xl/worksheets/sheet1.xml → foo/bar.xml.
        let g = rels_with(&[(rt::IMAGE, "../../foo/bar.xml", TargetMode::Internal)]);
        let sub = walk_sheet_subgraph(&g, "xl/worksheets/sheet1.xml");
        assert_eq!(sub.sheet_rels[0].1, "foo/bar.xml");
    }

    #[test]
    fn sheet_in_subdir_resolves_relative_target() {
        // A sheet that lives at a deeper nest still resolves correctly.
        let g = rels_with(&[(rt::TABLE, "../../tables/table1.xml", TargetMode::Internal)]);
        let sub = walk_sheet_subgraph(&g, "xl/worksheets/sub/sheet1.xml");
        assert_eq!(sub.sheet_rels[0].1, "xl/tables/table1.xml");
    }

    #[test]
    fn rels_path_for_helper_unchanged() {
        // The walker shares parent_dir/resolve_relative with rels_path_for
        // semantics — quick sanity check that we wired in the right module.
        assert_eq!(
            crate::rels_path_for("xl/worksheets/sheet1.xml"),
            Some("xl/worksheets/_rels/sheet1.xml.rels".into())
        );
    }
}
