//! Test-only helpers shared across modules.
//!
//! Anything that mutates process state (env vars, cwd, etc.) must be
//! serialized — Rust runs tests in the same crate concurrently, so a
//! per-module `Mutex<()>` is not enough. Any module that touches
//! `WOLFXL_TEST_EPOCH` must go through [`EpochGuard`].

use std::sync::Mutex;

/// Process-wide lock for `WOLFXL_TEST_EPOCH` mutation. Every test that
/// reads or writes the env var must hold this lock — including tests
/// that only *read* it indirectly (e.g. anything that calls
/// `current_timestamp_iso8601`).
pub(crate) static ENV_LOCK: Mutex<()> = Mutex::new(());

/// RAII guard that sets `WOLFXL_TEST_EPOCH` for the duration of a test,
/// then restores the prior value (or removes it) on drop. Holds
/// [`ENV_LOCK`] so concurrent tests cannot race on the env var.
pub(crate) struct EpochGuard {
    prev: Option<String>,
    _lock: std::sync::MutexGuard<'static, ()>,
}

impl EpochGuard {
    /// Set `WOLFXL_TEST_EPOCH` to `value` and return a guard that
    /// restores the prior state on drop.
    pub(crate) fn set(value: &str) -> Self {
        let _lock = ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let prev = std::env::var("WOLFXL_TEST_EPOCH").ok();
        // SAFETY: env mutation is serialized by ENV_LOCK; the guard is
        // dropped before returning to the test harness.
        unsafe {
            std::env::set_var("WOLFXL_TEST_EPOCH", value);
        }
        Self { prev, _lock }
    }
}

impl Drop for EpochGuard {
    fn drop(&mut self) {
        unsafe {
            match &self.prev {
                Some(v) => std::env::set_var("WOLFXL_TEST_EPOCH", v),
                None => std::env::remove_var("WOLFXL_TEST_EPOCH"),
            }
        }
    }
}
