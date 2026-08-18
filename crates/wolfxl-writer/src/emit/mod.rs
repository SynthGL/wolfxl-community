//! OOXML part emitters. One module per file inside the xlsx ZIP.
//!
//! Each module exposes a function that takes the relevant slice of the
//! [`crate::model`] and returns the serialized bytes for its part.
//!
//! | Module | Emits |
//! |--------|-------|
//! | [`content_types`] | `[Content_Types].xml` |
//! | [`rels`] | `_rels/.rels`, `xl/_rels/workbook.xml.rels`, `xl/worksheets/_rels/sheetN.xml.rels` |
//! | [`doc_props`] | `docProps/core.xml`, `docProps/app.xml` |
//! | [`workbook_xml`] | `xl/workbook.xml` |
//! | [`styles_xml`] | `xl/styles.xml` |
//! | [`shared_strings_xml`] | `xl/sharedStrings.xml` |
//! | [`sheet_xml`] | `xl/worksheets/sheetN.xml` |
//! | [`comments_xml`] | `xl/comments/commentsN.xml` |
//! | [`drawings_vml`] | `xl/drawings/vmlDrawingN.vml` |
//! | [`tables_xml`] | `xl/tables/tableN.xml` |

pub mod calc_chain_xml;
pub mod charts;
pub mod columns;
pub mod comments_xml;
pub mod conditional_formats;
pub mod content_types;
pub mod data_validations;
pub mod dimension;
pub mod doc_props;
pub mod drawing_refs;
pub mod drawings;
pub mod drawings_vml;
pub mod hyperlinks;
pub mod merges;
pub mod page_breaks;
pub mod persons_xml;
pub mod rels;
pub mod shared_strings_xml;
pub mod sheet_data;
pub mod sheet_format;
pub(crate) mod sheet_rel_ids;
pub mod sheet_setup;
pub mod sheet_views;
pub mod sheet_xml;
pub mod styles_xml;
pub mod table_parts;
pub mod tables_xml;
pub mod threaded_comments_xml;
pub mod workbook_xml;
