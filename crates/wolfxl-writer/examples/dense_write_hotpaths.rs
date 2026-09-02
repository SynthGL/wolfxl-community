//! Direct sparse-vs-dense worksheet storage and emission benchmark.

use std::alloc::{GlobalAlloc, Layout, System};
use std::hint::black_box;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Instant;

use wolfxl_writer::emit::sheet_data;
use wolfxl_writer::intern::SstBuilder;
use wolfxl_writer::model::{WriteCell, WriteCellValue};
use wolfxl_writer::Worksheet;

struct CountingAllocator;

static ALLOCATION_CALLS: AtomicU64 = AtomicU64::new(0);
static ALLOCATED_BYTES: AtomicU64 = AtomicU64::new(0);

unsafe impl GlobalAlloc for CountingAllocator {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        ALLOCATION_CALLS.fetch_add(1, Ordering::Relaxed);
        ALLOCATED_BYTES.fetch_add(layout.size() as u64, Ordering::Relaxed);
        unsafe { System.alloc(layout) }
    }

    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        unsafe { System.dealloc(ptr, layout) }
    }

    unsafe fn realloc(&self, ptr: *mut u8, layout: Layout, new_size: usize) -> *mut u8 {
        ALLOCATION_CALLS.fetch_add(1, Ordering::Relaxed);
        ALLOCATED_BYTES.fetch_add(new_size as u64, Ordering::Relaxed);
        unsafe { System.realloc(ptr, layout, new_size) }
    }
}

#[global_allocator]
static GLOBAL: CountingAllocator = CountingAllocator;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let mode = args.get(1).map(String::as_str).unwrap_or("dense");
    let rows: u32 = args.get(2).and_then(|v| v.parse().ok()).unwrap_or(20_000);
    let cols: u32 = args.get(3).and_then(|v| v.parse().ok()).unwrap_or(20);
    let rounds: u32 = args.get(4).and_then(|v| v.parse().ok()).unwrap_or(25);

    run(mode, rows, cols, false);
    for sample in 0..rounds {
        let (elapsed, allocations, bytes, output_bytes, checksum) = run(mode, rows, cols, true);
        println!(
            "sample,{mode},{sample},{elapsed},{allocations},{bytes},{output_bytes},{checksum}"
        );
    }
}

fn run(mode: &str, rows: u32, cols: u32, measured: bool) -> (u128, u64, u64, usize, u64) {
    if measured {
        ALLOCATION_CALLS.store(0, Ordering::Relaxed);
        ALLOCATED_BYTES.store(0, Ordering::Relaxed);
    }
    let started = Instant::now();
    let mut sheet = Worksheet::new("S");
    for row in 1..=rows {
        if mode == "dense" {
            let cells = (1..=cols)
                .map(|col| WriteCell::new(WriteCellValue::Number((row * col) as f64)))
                .collect();
            sheet.append_dense_row(row, 1, cells).unwrap();
        } else {
            for col in 1..=cols {
                sheet.set_cell(
                    row,
                    col,
                    WriteCell::new(WriteCellValue::Number((row * col) as f64)),
                );
            }
        }
    }
    let mut sst = SstBuilder::default();
    let mut xml = String::new();
    sheet_data::emit(&mut xml, &sheet, &mut sst);
    let elapsed = started.elapsed().as_nanos();
    let allocations = ALLOCATION_CALLS.load(Ordering::Relaxed);
    let bytes = ALLOCATED_BYTES.load(Ordering::Relaxed);
    let checksum = xml
        .as_bytes()
        .iter()
        .fold(0xcbf29ce484222325_u64, |hash, byte| {
            (hash ^ u64::from(*byte)).wrapping_mul(0x100000001b3)
        });
    black_box(&xml);
    (elapsed, allocations, bytes, xml.len(), checksum)
}
