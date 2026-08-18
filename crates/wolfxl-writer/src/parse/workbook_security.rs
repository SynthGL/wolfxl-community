//! Serializers for the `<workbookProtection>` and `<fileSharing>`
//! children of `<workbook>` (RFC-058).
//!
//! Both fragments are produced from the §10 flat dict shape:
//!
//! ```text
//! WorkbookSecurity {
//!     workbook_protection: Option<WorkbookProtectionSpec>,
//!     file_sharing:        Option<FileSharingSpec>,
//! }
//! ```
//!
//! The functions below are pure data → bytes and contain no PyO3
//! types; both the native writer (`emit::workbook_xml`) and the
//! patcher (`src/wolfxl/security.rs`) consume them.

use crate::xml_escape;

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

/// `<workbookProtection>` attribute group (ECMA-376 §18.2.29).
///
/// Field names are the snake_case equivalents of the XML attribute
/// names. All hash/salt fields are pre-base64-encoded; the writer never
/// re-encodes them.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct WorkbookProtectionSpec {
    pub lock_structure: bool,
    pub lock_windows: bool,
    pub lock_revision: bool,
    pub workbook_password: Option<String>,
    pub workbook_password_character_set: Option<String>,
    pub workbook_algorithm_name: Option<String>,
    pub workbook_hash_value: Option<String>,
    pub workbook_salt_value: Option<String>,
    pub workbook_spin_count: Option<u32>,
    pub revisions_password: Option<String>,
    pub revisions_password_character_set: Option<String>,
    pub revisions_algorithm_name: Option<String>,
    pub revisions_hash_value: Option<String>,
    pub revisions_salt_value: Option<String>,
    pub revisions_spin_count: Option<u32>,
}

/// `<fileSharing>` attribute group (ECMA-376 §18.2.10).
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct FileSharingSpec {
    pub read_only_recommended: bool,
    pub user_name: Option<String>,
    pub reservation_password: Option<String>,
    pub algorithm_name: Option<String>,
    pub hash_value: Option<String>,
    pub salt_value: Option<String>,
    pub spin_count: Option<u32>,
}

/// Bundle of the two security blocks for a workbook. Either field may
/// be `None` — the corresponding XML element is suppressed.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct WorkbookSecurity {
    pub workbook_protection: Option<WorkbookProtectionSpec>,
    pub file_sharing: Option<FileSharingSpec>,
}

impl WorkbookSecurity {
    /// `True` iff at least one of the two slots is non-`None`. Used as
    /// an early-exit check by the patcher.
    pub fn is_empty(&self) -> bool {
        self.workbook_protection.is_none() && self.file_sharing.is_none()
    }
}

// ---------------------------------------------------------------------------
// Emitters
// ---------------------------------------------------------------------------

/// Emit the `<workbookProtection .../>` element. Returns an empty
/// vector when *all* attributes are at their default values (so the
/// emitter can omit the element entirely — Excel reads the absence as
/// "no protection").
pub fn emit_workbook_protection(spec: &WorkbookProtectionSpec) -> Vec<u8> {
    let any_set = spec.lock_structure
        || spec.lock_windows
        || spec.lock_revision
        || spec.workbook_password.is_some()
        || spec.workbook_password_character_set.is_some()
        || spec.workbook_algorithm_name.is_some()
        || spec.workbook_hash_value.is_some()
        || spec.workbook_salt_value.is_some()
        || spec.workbook_spin_count.is_some()
        || spec.revisions_password.is_some()
        || spec.revisions_password_character_set.is_some()
        || spec.revisions_algorithm_name.is_some()
        || spec.revisions_hash_value.is_some()
        || spec.revisions_salt_value.is_some()
        || spec.revisions_spin_count.is_some();
    if !any_set {
        return Vec::new();
    }

    let mut out = String::with_capacity(256);
    out.push_str("<workbookProtection");

    if let Some(ref h) = spec.workbook_password {
        push_attr(&mut out, "workbookPassword", h);
    }
    if let Some(ref charset) = spec.workbook_password_character_set {
        push_attr(&mut out, "workbookPasswordCharacterSet", charset);
    }
    if let Some(ref h) = spec.revisions_password {
        push_attr(&mut out, "revisionsPassword", h);
    }
    if let Some(ref charset) = spec.revisions_password_character_set {
        push_attr(&mut out, "revisionsPasswordCharacterSet", charset);
    }
    if let Some(ref algo) = spec.workbook_algorithm_name {
        push_attr(&mut out, "workbookAlgorithmName", algo);
    }
    if let Some(ref h) = spec.workbook_hash_value {
        push_attr(&mut out, "workbookHashValue", h);
    }
    if let Some(ref s) = spec.workbook_salt_value {
        push_attr(&mut out, "workbookSaltValue", s);
    }
    if let Some(n) = spec.workbook_spin_count {
        out.push_str(&format!(" workbookSpinCount=\"{n}\""));
    }
    if let Some(ref algo) = spec.revisions_algorithm_name {
        push_attr(&mut out, "revisionsAlgorithmName", algo);
    }
    if let Some(ref h) = spec.revisions_hash_value {
        push_attr(&mut out, "revisionsHashValue", h);
    }
    if let Some(ref s) = spec.revisions_salt_value {
        push_attr(&mut out, "revisionsSaltValue", s);
    }
    if let Some(n) = spec.revisions_spin_count {
        out.push_str(&format!(" revisionsSpinCount=\"{n}\""));
    }
    if spec.lock_structure {
        out.push_str(" lockStructure=\"1\"");
    }
    if spec.lock_windows {
        out.push_str(" lockWindows=\"1\"");
    }
    if spec.lock_revision {
        out.push_str(" lockRevision=\"1\"");
    }
    out.push_str("/>");
    out.into_bytes()
}

/// Emit the `<fileSharing .../>` element. Returns an empty vector when
/// nothing is configured.
pub fn emit_file_sharing(spec: &FileSharingSpec) -> Vec<u8> {
    let any_set = spec.read_only_recommended
        || spec.user_name.is_some()
        || spec.reservation_password.is_some()
        || spec.algorithm_name.is_some()
        || spec.hash_value.is_some()
        || spec.salt_value.is_some()
        || spec.spin_count.is_some();
    if !any_set {
        return Vec::new();
    }

    let mut out = String::with_capacity(192);
    out.push_str("<fileSharing");
    if spec.read_only_recommended {
        out.push_str(" readOnlyRecommended=\"1\"");
    }
    if let Some(ref u) = spec.user_name {
        push_attr(&mut out, "userName", u);
    }
    if let Some(ref h) = spec.reservation_password {
        push_attr(&mut out, "reservationPassword", h);
    }
    if let Some(ref algo) = spec.algorithm_name {
        push_attr(&mut out, "algorithmName", algo);
    }
    if let Some(ref h) = spec.hash_value {
        push_attr(&mut out, "hashValue", h);
    }
    if let Some(ref s) = spec.salt_value {
        push_attr(&mut out, "saltValue", s);
    }
    if let Some(n) = spec.spin_count {
        out.push_str(&format!(" spinCount=\"{n}\""));
    }
    out.push_str("/>");
    out.into_bytes()
}

fn push_attr(out: &mut String, key: &str, value: &str) {
    out.push(' ');
    out.push_str(key);
    out.push_str("=\"");
    out.push_str(&xml_escape::attr(value));
    out.push('"');
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_protection_yields_empty_vec() {
        assert!(emit_workbook_protection(&WorkbookProtectionSpec::default()).is_empty());
    }

    #[test]
    fn empty_sharing_yields_empty_vec() {
        assert!(emit_file_sharing(&FileSharingSpec::default()).is_empty());
    }

    #[test]
    fn lock_structure_only() {
        let spec = WorkbookProtectionSpec {
            lock_structure: true,
            ..Default::default()
        };
        let bytes = emit_workbook_protection(&spec);
        let text = String::from_utf8(bytes).unwrap();
        assert_eq!(text, "<workbookProtection lockStructure=\"1\"/>");
    }

    #[test]
    fn full_workbook_protection_attribute_order() {
        // ECMA-376 ordering: algorithm/hash/salt/spinCount/lock-flags.
        let spec = WorkbookProtectionSpec {
            lock_structure: true,
            lock_windows: false,
            lock_revision: true,
            workbook_password: Some("ABCD".into()),
            workbook_password_character_set: None,
            workbook_algorithm_name: Some("SHA-512".into()),
            workbook_hash_value: Some("HASH==".into()),
            workbook_salt_value: Some("SALT==".into()),
            workbook_spin_count: Some(100_000),
            revisions_password: None,
            revisions_password_character_set: None,
            revisions_algorithm_name: Some("SHA-512".into()),
            revisions_hash_value: Some("HASH2==".into()),
            revisions_salt_value: Some("SALT2==".into()),
            revisions_spin_count: Some(50_000),
        };
        let text = String::from_utf8(emit_workbook_protection(&spec)).unwrap();
        assert!(text.contains("workbookAlgorithmName=\"SHA-512\""));
        assert!(text.contains("workbookHashValue=\"HASH==\""));
        assert!(text.contains("workbookSaltValue=\"SALT==\""));
        assert!(text.contains("workbookSpinCount=\"100000\""));
        assert!(text.contains("revisionsHashValue=\"HASH2==\""));
        assert!(text.contains("revisionsSpinCount=\"50000\""));
        assert!(text.contains("lockStructure=\"1\""));
        assert!(!text.contains("lockWindows=\"1\""));
        assert!(text.contains("lockRevision=\"1\""));
    }

    #[test]
    fn file_sharing_full() {
        let spec = FileSharingSpec {
            read_only_recommended: true,
            user_name: Some("alice".into()),
            reservation_password: Some("ABCD".into()),
            algorithm_name: Some("SHA-512".into()),
            hash_value: Some("ABC==".into()),
            salt_value: Some("DEF==".into()),
            spin_count: Some(100_000),
        };
        let text = String::from_utf8(emit_file_sharing(&spec)).unwrap();
        assert!(text.starts_with("<fileSharing"));
        assert!(text.contains("readOnlyRecommended=\"1\""));
        assert!(text.contains("userName=\"alice\""));
        assert!(text.contains("reservationPassword=\"ABCD\""));
        assert!(text.contains("algorithmName=\"SHA-512\""));
        assert!(text.contains("hashValue=\"ABC==\""));
        assert!(text.contains("saltValue=\"DEF==\""));
        assert!(text.contains("spinCount=\"100000\""));
        assert!(text.ends_with("/>"));
    }

    #[test]
    fn user_name_with_xml_special_char_escapes() {
        let spec = FileSharingSpec {
            user_name: Some("a&b".into()),
            ..Default::default()
        };
        let text = String::from_utf8(emit_file_sharing(&spec)).unwrap();
        assert!(text.contains("userName=\"a&amp;b\""));
        assert!(!text.contains("userName=\"a&b\""));
    }

    #[test]
    fn workbook_security_is_empty() {
        assert!(WorkbookSecurity::default().is_empty());
        let s = WorkbookSecurity {
            workbook_protection: Some(WorkbookProtectionSpec::default()),
            file_sharing: None,
        };
        assert!(!s.is_empty());
    }
}
