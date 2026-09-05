//! Reproducible writer hot-path benchmark.
//!
//! Example:
//! `cargo run --release -p wolfxl-writer --example writer_hotpaths -- numeric 10000 20 15 out.xlsx`

use std::alloc::{GlobalAlloc, Layout, System};
use std::io::Cursor;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Instant;

use wolfxl_writer::model::cell::{FormulaResult, WriteCell, WriteCellValue};
use wolfxl_writer::model::format::{FontSpec, FormatSpec};
use wolfxl_writer::{emit_xlsx_to, Workbook, Worksheet};

struct CountingAllocator;

static ALLOCATIONS: AtomicU64 = AtomicU64::new(0);
static ALLOCATED_BYTES: AtomicU64 = AtomicU64::new(0);

unsafe impl GlobalAlloc for CountingAllocator {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        ALLOCATIONS.fetch_add(1, Ordering::Relaxed);
        ALLOCATED_BYTES.fetch_add(layout.size() as u64, Ordering::Relaxed);
        unsafe { System.alloc(layout) }
    }

    unsafe fn alloc_zeroed(&self, layout: Layout) -> *mut u8 {
        ALLOCATIONS.fetch_add(1, Ordering::Relaxed);
        ALLOCATED_BYTES.fetch_add(layout.size() as u64, Ordering::Relaxed);
        unsafe { System.alloc_zeroed(layout) }
    }

    unsafe fn realloc(&self, ptr: *mut u8, layout: Layout, new_size: usize) -> *mut u8 {
        ALLOCATIONS.fetch_add(1, Ordering::Relaxed);
        ALLOCATED_BYTES.fetch_add(new_size as u64, Ordering::Relaxed);
        unsafe { System.realloc(ptr, layout, new_size) }
    }

    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        unsafe { System.dealloc(ptr, layout) }
    }
}

#[global_allocator]
static GLOBAL: CountingAllocator = CountingAllocator;

#[derive(Clone, Copy)]
enum Workload {
    Numeric,
    RepeatedStrings,
    UniqueStrings,
    EscapedStrings,
    StyledNumbers,
    Formulas,
}

impl Workload {
    fn parse(value: &str) -> Self {
        match value {
            "numeric" => Self::Numeric,
            "repeated-strings" => Self::RepeatedStrings,
            "unique-strings" => Self::UniqueStrings,
            "escaped-strings" => Self::EscapedStrings,
            "styled-numbers" => Self::StyledNumbers,
            "formulas" => Self::Formulas,
            _ => panic!(
                "unknown workload {value:?}; expected numeric, repeated-strings, unique-strings, escaped-strings, styled-numbers, or formulas"
            ),
        }
    }
}

fn build_workbook(workload: Workload, rows: u32, cols: u32) -> Workbook {
    let mut workbook = Workbook::new();
    let style_id = matches!(workload, Workload::StyledNumbers).then(|| {
        workbook.styles.intern_format(&FormatSpec {
            font: Some(FontSpec {
                bold: true,
                ..Default::default()
            }),
            ..Default::default()
        })
    });
    let sheets: usize = std::env::var("WOLFXL_BENCH_SHEETS")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(1);
    for sheet_idx in 0..sheets {
        let mut sheet = Worksheet::new(&format!("Data{sheet_idx}"));
        for row in 1..=rows {
            let mut cells = Vec::with_capacity(cols as usize);
            for col in 1..=cols {
                let index = (u64::from(row) - 1) * u64::from(cols) + u64::from(col) - 1;
                let value = match workload {
                    Workload::Numeric => WriteCellValue::Number(index as f64),
                    Workload::RepeatedStrings => {
                        WriteCellValue::String(format!("category-{:03}", index % 128))
                    }
                    Workload::UniqueStrings => {
                        WriteCellValue::String(format!("unique-{index:010}-abcdefghijklmnop"))
                    }
                    Workload::EscapedStrings => {
                        WriteCellValue::String(format!("unique & <{index:010}> abcdefghijklmnop"))
                    }
                    Workload::StyledNumbers => WriteCellValue::Number(index as f64),
                    Workload::Formulas => WriteCellValue::Formula {
                        expr: format!("{}+{}", row, col),
                        result: Some(FormulaResult::Number(f64::from(row + col))),
                    },
                };
                let mut cell = WriteCell::new(value);
                cell.style_id = style_id;
                cells.push(cell);
            }
            sheet
                .append_dense_row(row, 1, cells)
                .expect("benchmark coordinates are valid and ordered");
        }
        workbook.add_sheet(sheet);
    }
    workbook
}

fn percentile<T: Copy>(sorted: &[T], numerator: usize, denominator: usize) -> T {
    let index = (sorted.len() * numerator)
        .div_ceil(denominator)
        .saturating_sub(1);
    sorted[index.min(sorted.len() - 1)]
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    assert_eq!(
        args.len(),
        6,
        "usage: writer_hotpaths WORKLOAD ROWS COLS ROUNDS OUTPUT.xlsx"
    );
    let workload = Workload::parse(&args[1]);
    let rows: u32 = args[2].parse().expect("ROWS must be an integer");
    let cols: u32 = args[3].parse().expect("COLS must be an integer");
    let rounds: usize = args[4].parse().expect("ROUNDS must be an integer");
    assert!(rounds > 0, "ROUNDS must be positive");

    if std::env::var_os("WOLFXL_SHEET_EMIT_THREADS").is_none() {
        std::env::set_var("WOLFXL_SHEET_EMIT_THREADS", "1");
    }
    if std::env::var_os("WOLFXL_ZIP_THREADS").is_none() {
        std::env::set_var("WOLFXL_ZIP_THREADS", "1");
    }
    if std::env::var_os("WOLFXL_TEST_EPOCH").is_none() {
        std::env::set_var("WOLFXL_TEST_EPOCH", "0");
    }

    let mut timings = Vec::with_capacity(rounds);
    let mut allocation_counts = Vec::with_capacity(rounds);
    let mut allocated_bytes = Vec::with_capacity(rounds);
    let mut final_output = Vec::new();

    for round in 0..=rounds {
        let mut workbook = build_workbook(workload, rows, cols);
        ALLOCATIONS.store(0, Ordering::Relaxed);
        ALLOCATED_BYTES.store(0, Ordering::Relaxed);
        let started = Instant::now();
        let mut output = Cursor::new(Vec::new());
        emit_xlsx_to(&mut workbook, &mut output).expect("workbook emission succeeds");
        let elapsed = started.elapsed().as_nanos();
        let allocations = ALLOCATIONS.load(Ordering::Relaxed);
        let bytes = ALLOCATED_BYTES.load(Ordering::Relaxed);
        if round > 0 {
            println!(
                "sample,{},{elapsed},{allocations},{bytes},{}",
                round,
                output.get_ref().len()
            );
            timings.push(elapsed);
            allocation_counts.push(allocations);
            allocated_bytes.push(bytes);
        }
        final_output = output.into_inner();
    }

    timings.sort_unstable();
    allocation_counts.sort_unstable();
    allocated_bytes.sort_unstable();
    let mean = timings.iter().sum::<u128>() as f64 / timings.len() as f64;
    let variance = timings
        .iter()
        .map(|&value| {
            let delta = value as f64 - mean;
            delta * delta
        })
        .sum::<f64>()
        / timings.len() as f64;
    let cv = variance.sqrt() / mean;
    println!("metric,value");
    println!("workload,{}", args[1]);
    println!("cells,{}", u64::from(rows) * u64::from(cols));
    println!("rounds,{rounds}");
    println!("median_ns,{}", percentile(&timings, 1, 2));
    println!("min_ns,{}", timings[0]);
    println!("p95_ns,{}", percentile(&timings, 95, 100));
    println!("cv,{cv:.6}");
    println!(
        "median_allocations,{}",
        percentile(&allocation_counts, 1, 2)
    );
    println!(
        "median_allocated_bytes,{}",
        percentile(&allocated_bytes, 1, 2)
    );
    println!("output_bytes,{}", final_output.len());
    if let Ok(status) = std::fs::read_to_string("/proc/self/status") {
        if let Some(line) = status.lines().find(|line| line.starts_with("VmHWM:")) {
            println!("peak_rss_kib,{}", line.split_whitespace().nth(1).unwrap());
        }
    }
    std::fs::write(&args[5], final_output).expect("benchmark output can be written");
}
