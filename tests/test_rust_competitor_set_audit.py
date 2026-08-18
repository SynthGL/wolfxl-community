from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts_dir))
    script = scripts_dir / "audit_rust_competitor_set.py"
    spec = importlib.util.spec_from_file_location("audit_rust_competitor_set", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


audit = _load_module()


def _required_competitor_cases() -> list[tuple[str, str]]:
    cases_by_family = {
        "plain_value_write": "write_cell_by_cell_plain",
        "high_cardinality_string_write": "write_unique_strings_plain",
        "formula_write": "write_formulas_plain",
        "styled_value_write": "write_styled_values",
        "multi_sheet_write": "write_multi_sheet_plain",
        "plain_value_read": "read_values_plain",
        "formula_text_read": "read_formula_text",
        "existing_workbook_modify": "modify_existing_workbook_plain",
    }
    return [
        (competitor, cases_by_family[family])
        for competitor in audit.DEFAULT_RUST_COMPETITORS
        for family in audit.DEFAULT_RUST_COMPETITOR_REQUIRED_CASE_FAMILIES[competitor]
    ]


def test_required_competitor_set_matches_sota_gate() -> None:
    assert audit.required_competitor_ids() == audit.DEFAULT_RUST_COMPETITORS


def test_competitor_set_report_has_no_blockers_when_required_gate_matches() -> None:
    report = audit.build_report(fetch_metadata=None)

    assert report["ready"] is True
    assert report["main_rust_competitor_set_ready"] is True
    assert report["generated_at"] == report["metadata"]["timestamp_utc"]
    assert report["git_sha"] == report["metadata"]["git_head_sha"]
    assert report["blockers"] == []
    assert report["missing_from_sota_gate"] == []
    assert report["status_counts"]["required"] == len(audit.DEFAULT_RUST_COMPETITORS)
    assert report["metadata"]["discovery_min_downloads"] == audit.DISCOVERY_MIN_DOWNLOADS
    assert report["metadata"]["discovery_min_recent_downloads"] == (
        audit.DISCOVERY_MIN_RECENT_DOWNLOADS
    )
    required_by_id = {
        package["id"]: package
        for package in report["packages"]
        if package["gate_status"] == "required"
    }
    assert required_by_id["xlsxwriter"]["aliases"] == ("xlsxwriter-rs",)


def test_competitor_set_discovery_queries_cover_excel_package_synonyms() -> None:
    assert {
        "xls",
        "xlsb",
        "xlsx",
        "excel",
        "spreadsheet",
        "xlsm",
        "workbook",
        "ooxml",
        "openxml",
        "libxlsxwriter",
    } <= set(audit.DISCOVERY_QUERIES)


def test_pypi_discovery_name_terms_cover_pyxl_variants() -> None:
    assert "pyxl" in audit.PYPI_DISCOVERY_NAME_TERMS
    assert audit._pypi_candidate_priority("super-rust-pyxl", set()) > 0


def test_pypi_discovery_name_terms_cover_legacy_xls_and_openxml_names() -> None:
    assert {
        "xls",
        "workbook",
        "ooxml",
        "openxml",
    } <= set(audit.PYPI_DISCOVERY_NAME_TERMS)
    assert audit._pypi_candidate_priority("FastXlsToCsv", set()) > 0
    assert audit._pypi_candidate_priority("workbook-rs", set()) > 0
    assert audit._pypi_candidate_priority("python-openxml-rs", set()) > 0


def test_pypi_discovery_cross_index_competitor_allowlist_is_explicit() -> None:
    assert audit.PYPI_DISCOVERY_CROSS_INDEX_COMPETITOR_IDS == ("fastexcel",)


def test_pypi_metadata_uses_pypistats_recent_downloads(monkeypatch) -> None:
    calls = []
    fetch_kwargs = []

    def fake_fetch_json(url: str, timeout: float, **kwargs) -> dict[str, object]:
        calls.append(url)
        fetch_kwargs.append(kwargs)
        if url.startswith("https://pypi.org/"):
            return {
                "info": {
                    "version": "0.1.0",
                    "summary": "Fast XLSX package",
                    "home_page": "https://example.com/fastxlsx",
                    "project_urls": {"Source": "https://example.com/src"},
                },
                "releases": {
                    "0.1.0": [
                        {"upload_time_iso_8601": "2026-01-01T00:00:00Z"}
                    ]
                },
            }
        return {
            "data": {"last_month": 12_345},
            "package": "fastxlsx",
            "type": "recent_downloads",
        }

    monkeypatch.setattr(audit, "_fetch_json", fake_fetch_json)
    monkeypatch.setattr(audit, "sleep", lambda seconds: None)

    metadata = audit._fetch_pypi_metadata("fastxlsx", timeout=1.0)

    assert metadata["version"] == "0.1.0"
    assert metadata["downloads"] is None
    assert metadata["recent_downloads"] == 12_345
    assert metadata["recent_downloads_source"] == "pypistats.org"
    assert metadata["recent_downloads_period"] == "last_month"
    assert metadata["recent_downloads_error"] is None
    assert len(calls) == 2
    assert fetch_kwargs[1]["attempts"] == audit.PYPISTATS_RETRY_COUNT
    assert fetch_kwargs[1]["backoff_seconds"] == audit.PYPISTATS_RETRY_BACKOFF_SECONDS


def test_load_pypi_recent_download_cache_reads_prior_report(tmp_path: Path) -> None:
    prior_report = tmp_path / "rust-competitor-set.json"
    prior_report.write_text(
        json.dumps(
            {
                "packages": [
                    {
                        "id": "fastxlsx",
                        "package": "fastxlsx",
                        "source": "pypi",
                        "registry": {
                            "recent_downloads": 1234,
                            "recent_downloads_source": "pypistats.org",
                            "recent_downloads_period": "last_month",
                        },
                    },
                    {
                        "id": "calamine",
                        "package": "calamine",
                        "source": "crates.io",
                        "registry": {"recent_downloads": 9999},
                    },
                ]
            }
        )
    )

    cache = audit.load_pypi_recent_download_cache(prior_report)

    assert set(cache) == {"fastxlsx"}
    assert cache["fastxlsx"]["recent_downloads"] == 1234
    assert cache["fastxlsx"]["recent_downloads_cached"] is True
    assert cache["fastxlsx"]["recent_downloads_cache_report"] == str(prior_report)


def test_cached_pypi_metadata_skips_pypistats(monkeypatch, tmp_path: Path) -> None:
    calls = []
    prior_report = tmp_path / "rust-competitor-set.json"
    cache = {
        "fastxlsx": {
            "recent_downloads": 1234,
            "recent_downloads_source": "pypistats.org",
            "recent_downloads_period": "last_month",
            "recent_downloads_cached": True,
            "recent_downloads_cache_report": str(prior_report),
        }
    }

    def fake_fetch_pypi_metadata(
        package: str,
        timeout: float,
        *,
        fetch_recent_downloads: bool = True,
    ) -> dict[str, object]:
        calls.append((package, timeout, fetch_recent_downloads))
        return {
            "version": "0.2.0",
            "downloads": None,
            "recent_downloads": None,
            "recent_downloads_source": None,
            "recent_downloads_period": None,
            "recent_downloads_error": None,
            "description": "Fast XLSX package",
        }

    monkeypatch.setattr(audit, "_fetch_pypi_metadata", fake_fetch_pypi_metadata)

    package = audit.CompetitorPackage(
        id="fastxlsx",
        package="fastxlsx",
        source="pypi",
        gate_status="watchlist",
        compare_scope="Rust-backed XLSX reads and writes.",
        reason="test",
    )
    metadata = audit.fetch_package_metadata_with_pypi_recent_download_cache(
        package,
        recent_download_cache=cache,
        timeout=1.0,
    )

    assert calls == [("fastxlsx", 1.0, False)]
    assert metadata["version"] == "0.2.0"
    assert metadata["recent_downloads"] == 1234
    assert metadata["recent_downloads_cached"] is True
    assert metadata["recent_downloads_cache_report"] == str(prior_report)


def test_pypi_discovery_skips_pypistats_recent_download_fanout(monkeypatch) -> None:
    def fake_fetch_json(url: str, timeout: float, **kwargs) -> dict[str, object]:
        if "pypistats.org" in url:
            raise AssertionError("discovery should not call PyPI Stats")
        if url == audit.PYPI_SIMPLE_API:
            return {"projects": [{"name": "fastxlsx"}]}
        return {
            "info": {
                "version": "0.1.0",
                "summary": "Fast XLSX package built with Rust",
                "home_page": None,
                "project_urls": {},
            },
            "releases": {"0.1.0": []},
        }

    monkeypatch.setattr(audit, "_fetch_json", fake_fetch_json)
    monkeypatch.setattr(audit, "sleep", lambda seconds: None)

    payload = audit.fetch_pypi_discovery(candidate_limit=1, timeout=1.0)

    assert payload["hits"][0]["id"] == "fastxlsx"
    assert payload["hits"][0]["recent_downloads"] is None


def test_competitor_set_report_blocks_when_required_gate_is_missing_package() -> None:
    report = audit.build_report(
        fetch_metadata=None,
        required_benchmark_competitors=("calamine",),
    )

    assert report["ready"] is False
    assert report["main_rust_competitor_set_ready"] is False
    assert "rust_xlsxwriter" in report["missing_from_sota_gate"]
    assert report["blockers"]


def test_competitor_set_report_includes_watchlist_packages() -> None:
    report = audit.build_report(fetch_metadata=None)
    watchlist = {
        package["id"]
        for package in report["packages"]
        if package["gate_status"] == "watchlist"
    }

    assert {
        "excelstream",
        "zavora-xlsx",
        "polars_excel_writer",
        "xlsxwriter-rs",
        "office_oxide",
        "rlsx",
        "xlsx_reader",
        "excel-rs",
        "excelize",
        "mr_xlsx",
        "simple-xlsx-writer",
        "xlsx_group_write",
        "fastxlsx",
        "rustpy-xlsxwriter",
        "rustypyxl",
        "excelsior-fast",
        "py-excel-rs",
        "python-calamine-reducto",
        "pyfastexcel",
        "fastexcel-rw",
        "fastexcel-keye",
        "formualizer-workbook",
        "logisheets_workbook",
        "sheetkit",
        "sheetkit-core",
        "ooxml",
        "ooxml-sml",
        "ooxmlsdk",
        "excel-kit",
        "draviavemal-openxml_office",
    } <= watchlist


def test_competitor_set_report_tracks_exact_xlsx_reader_name() -> None:
    report = audit.build_report(fetch_metadata=None)

    package = next(
        package for package in report["packages"] if package["id"] == "xlsx_reader"
    )

    assert package["gate_status"] == "watchlist"
    assert package["package"] == "xlsx_reader"
    assert package["aliases"] == ("xlsx-reader",)
    assert "data-only reader" in package["reason"]


def test_competitor_set_report_reviews_pypi_watchlist_promotion_risk() -> None:
    report = audit.build_report(fetch_metadata=None)
    reviews = {row["id"]: row for row in report["watchlist_promotion_reviews"]}
    pypi_watchlist = {
        "fastxlsx",
        "rustpy-xlsxwriter",
        "rustypyxl",
        "excelsior-fast",
        "py-excel-rs",
        "python-calamine-reducto",
        "pyfastexcel",
        "fastexcel-rw",
        "fastexcel-keye",
    }

    assert pypi_watchlist <= set(reviews)
    assert report["watchlist_promotion_review_ready"] is True
    assert report["watchlist_packages_requiring_promotion"] == []
    assert set(pypi_watchlist) <= set(report["watchlist_promotion_adoption_missing"])
    assert report["watchlist_promotion_adoption_complete"] is False
    assert "watchlist packages without adoption data" in (
        report["watchlist_promotion_adoption_caveat"]
    )
    assert all(not reviews[package]["promotion_needed_now"] for package in pypi_watchlist)
    assert all(
        reviews[package]["adoption_evidence_available"] is False
        for package in pypi_watchlist
    )
    assert all(
        reviews[package]["promotion_rule_status"] == "adoption_evidence_unavailable"
        or reviews[package]["promotion_rule_status"] == "not_high_risk"
        or reviews[package]["promotion_rule_status"] == "positioning_handled"
        for package in pypi_watchlist
    )
    assert reviews["fastxlsx"]["related_required_competitors"] == [
        "calamine",
        "rust_xlsxwriter",
    ]
    assert reviews["fastxlsx"]["performance_positioned"] is False
    assert reviews["fastxlsx"]["positioning_handling"] == "covered_by_required_lanes"
    assert reviews["python-calamine-reducto"]["related_required_competitors"] == [
        "python-calamine",
        "calamine",
    ]
    assert (
        reviews["python-calamine-reducto"]["positioning_handling"]
        == "covered_by_required_lanes"
    )
    assert reviews["xlsxwriter-rs"]["related_required_competitors"] == ["xlsxwriter"]
    assert "Exact crates.io package name" in reviews["xlsxwriter-rs"]["basis"]
    assert "main fastexcel reader lane" in reviews["fastexcel-rw"]["basis"]
    assert reviews["fastexcel-rw"]["performance_positioned"] is True
    assert reviews["fastexcel-rw"]["positioning_handling"] == "covered_by_required_lanes"
    assert reviews["fastexcel-keye"]["positioning_handling"] == "covered_by_required_lanes"
    assert "benchmark proxy" in reviews["fastexcel-keye"]["basis"]


def test_broad_high_risk_watchlist_stays_watchlist_below_promotion_threshold() -> None:
    def fake_fetch(package: audit.CompetitorPackage) -> dict[str, object]:
        if package.id == "office_oxide":
            return {
                "version": "0.1.2",
                "downloads": 35_055,
                "recent_downloads": 35_055,
                "description": "Fast Office processing library for DOCX, XLSX, and PPTX",
            }
        return {
            "version": "1.2.3",
            "downloads": 10,
            "recent_downloads": 2,
            "description": f"{package.id} description",
        }

    report = audit.build_report(fetch_metadata=fake_fetch)
    review = {
        row["id"]: row for row in report["watchlist_promotion_reviews"]
    }["office_oxide"]

    assert report["main_rust_competitor_set_ready"] is True
    assert report["watchlist_packages_requiring_promotion"] == []
    assert report["watchlist_promotion_adoption_complete"] is True
    assert report["watchlist_promotion_adoption_caveat"] is None
    assert review["promotion_needed_now"] is False
    assert review["objective_promotion_needed_now"] is False
    assert (
        review["promotion_rule_status"]
        == "positioning_handled_below_objective_adoption_threshold"
    )
    assert review["adoption_evidence_available"] is True
    assert review["broad_excel_scope"] is True
    assert review["performance_positioned"] is True
    assert review["positioning_handling_required"] is True
    assert review["positioning_handling_ready"] is True
    assert review["positioning_handling"] == "benchmark_lane"


def test_broad_performance_watchlist_blocks_without_handling(monkeypatch) -> None:
    review = dict(audit.WATCHLIST_PROMOTION_REVIEWS["office_oxide"])
    review.pop("positioning_handling", None)
    review.pop("positioning_handling_source", None)
    reviews = dict(audit.WATCHLIST_PROMOTION_REVIEWS)
    reviews["office_oxide"] = review
    monkeypatch.setattr(audit, "WATCHLIST_PROMOTION_REVIEWS", reviews)

    def fake_fetch(package: audit.CompetitorPackage) -> dict[str, object]:
        if package.id == "office_oxide":
            return {
                "version": "0.1.2",
                "downloads": 35_055,
                "recent_downloads": 35_055,
                "description": "Fast Office processing library for DOCX, XLSX, and PPTX",
            }
        return {
            "version": "1.2.3",
            "downloads": 10,
            "recent_downloads": 2,
            "description": f"{package.id} description",
        }

    report = audit.build_report(fetch_metadata=fake_fetch)
    review = {
        row["id"]: row for row in report["watchlist_promotion_reviews"]
    }["office_oxide"]

    assert report["main_rust_competitor_set_ready"] is False
    assert "office_oxide" in report["watchlist_packages_requiring_promotion"]
    assert review["promotion_rule_status"] == "positioning_handling_required"
    assert review["performance_positioned"] is True
    assert review["positioning_handling_required"] is True
    assert review["positioning_handling_ready"] is False


def test_broad_performance_watchlist_passes_with_documented_handling() -> None:
    def fake_fetch(package: audit.CompetitorPackage) -> dict[str, object]:
        descriptions = {
            "fastexcel-keye": "Fastexcel fork with fast XLSX read/write style support",
            "rust-excel-core": (
                "Read, write, and modify Excel files with best-in-class performance"
            ),
        }
        return {
            "version": "1.2.3",
            "downloads": 100,
            "recent_downloads": 25,
            "description": descriptions.get(package.id, f"{package.id} description"),
        }

    report = audit.build_report(fetch_metadata=fake_fetch)
    reviews = {row["id"]: row for row in report["watchlist_promotion_reviews"]}

    assert report["main_rust_competitor_set_ready"] is True
    assert report["watchlist_packages_requiring_promotion"] == []

    fastexcel_keye = reviews["fastexcel-keye"]
    assert fastexcel_keye["broad_excel_scope"] is True
    assert fastexcel_keye["performance_positioned"] is True
    assert fastexcel_keye["promotion_rule_status"] == "positioning_handled"
    assert fastexcel_keye["positioning_handling_required"] is True
    assert fastexcel_keye["positioning_handling_ready"] is True
    assert fastexcel_keye["positioning_handling"] == "covered_by_required_lanes"

    rust_excel_core = reviews["rust-excel-core"]
    assert rust_excel_core["broad_excel_scope"] is True
    assert rust_excel_core["performance_positioned"] is True
    assert rust_excel_core["promotion_rule_status"] == "positioning_handled"
    assert rust_excel_core["positioning_handling_required"] is True
    assert rust_excel_core["positioning_handling_ready"] is True
    assert rust_excel_core["positioning_handling"] == "covered_by_required_lanes"
    assert rust_excel_core["related_required_competitors"] == [
        "calamine",
        "rust_xlsxwriter",
        "umya-spreadsheet",
    ]


def test_broad_high_risk_watchlist_blocks_after_promotion_threshold() -> None:
    def fake_fetch(package: audit.CompetitorPackage) -> dict[str, object]:
        if package.id == "office_oxide":
            return {
                "version": "0.1.2",
                "downloads": 300_000,
                "recent_downloads": 60_000,
                "description": "Fast Office processing library for DOCX, XLSX, and PPTX",
            }
        return {
            "version": "1.2.3",
            "downloads": 10,
            "recent_downloads": 2,
            "description": f"{package.id} description",
        }

    report = audit.build_report(fetch_metadata=fake_fetch)
    review = {
        row["id"]: row for row in report["watchlist_promotion_reviews"]
    }["office_oxide"]

    assert report["main_rust_competitor_set_ready"] is False
    assert "office_oxide" in report["watchlist_packages_requiring_promotion"]
    assert review["promotion_needed_now"] is True
    assert review["objective_promotion_needed_now"] is True
    assert review["promotion_rule_status"] == "required_by_objective_rule"
    assert "watchlist promotion review says these packages now need required lanes:" in (
        report["blockers"][0]
    )


def test_high_adoption_watchlist_packages_get_attention_rows() -> None:
    def fake_fetch(package: audit.CompetitorPackage) -> dict[str, object]:
        if package.id == "simple_excel_writer":
            return {
                "version": "0.2.0",
                "downloads": 179_631,
                "recent_downloads": 16_280,
                "description": "Simple XLS and XLSX writer",
            }
        if package.id == "python-calamine-reducto":
            return {
                "version": "0.7.13",
                "recent_downloads": 47_565,
                "description": "Python bindings around calamine with style helpers",
            }
        return {
            "version": "1.2.3",
            "downloads": 10,
            "recent_downloads": 2,
            "description": f"{package.id} description",
        }

    report = audit.build_report(fetch_metadata=fake_fetch)
    attention = {
        row["id"]: row for row in report["watchlist_adoption_attention_reviews"]
    }
    promotion_reviews = {
        row["id"]: row for row in report["watchlist_promotion_reviews"]
    }

    assert report["watchlist_adoption_attention_review_count"] == 2
    assert set(attention) == {"python-calamine-reducto", "simple_excel_writer"}
    assert attention["simple_excel_writer"]["promotion_needed_now"] is False
    assert attention["simple_excel_writer"]["promotion_rule_status"] == "not_high_risk"
    assert attention["simple_excel_writer"]["max_promotion_ratio"] > 0.6
    assert promotion_reviews["simple_excel_writer"]["performance_positioned"] is False
    assert attention["python-calamine-reducto"]["related_required_competitors"] == [
        "python-calamine",
        "calamine",
    ]


def test_exact_xlsxwriter_rs_package_is_visible_but_not_required() -> None:
    report = audit.build_report(fetch_metadata=None)
    package = next(row for row in report["packages"] if row["id"] == "xlsxwriter-rs")

    assert package["package"] == "xlsxwriter-rs"
    assert package["source"] == "crates.io"
    assert package["gate_status"] == "watchlist"
    assert package["compare_scope"] == "Legacy exact-name Rust bindings to libxlsxwriter."
    assert "maintained xlsxwriter crate" in package["reason"]
    assert "xlsxwriter-rs" not in report["required_competitors"]
    assert report["required_competitor_aliases"]["xlsxwriter"] == ["xlsxwriter-rs"]
    assert report["requested_competitor_name_resolution_ready"] is True
    assert report["requested_competitor_name_resolution_blockers"] == []
    resolution = report["requested_competitor_name_resolutions"][0]
    assert resolution["requested_name"] == "xlsxwriter-rs"
    assert resolution["resolves_to_competitor"] == "xlsxwriter"
    assert resolution["benchmarked_package"] == "xlsxwriter"
    assert resolution["benchmarked_version"] is None
    assert resolution["benchmark_required_for_resolution"] is False
    assert resolution["benchmark_requirement_satisfied"] is True
    assert resolution["exact_package_gate_status"] == "watchlist"
    assert resolution["exact_package_version"] is None
    assert resolution["exact_package_decision"] == "remain_watchlist"
    assert resolution["requirement_satisfied"] is True


def test_widened_rust_discovery_followup_hits_are_classified() -> None:
    def fake_discovery(query: str) -> list[dict[str, object]]:
        if query == "libxlsxwriter":
            return [
                {
                    "id": "libxlsxwriter-sys",
                    "version": "0.5.5",
                    "downloads": 1_092_076,
                    "recent_downloads": 75_760,
                    "description": "Low-level bindings to libxlsxwriter",
                },
                {
                    "id": "libxlsxwriter-sys-cs",
                    "version": "0.5.4",
                    "downloads": 1_613,
                    "recent_downloads": 54,
                    "description": "Forked low-level bindings to libxlsxwriter",
                },
            ]
        if query == "spreadsheet":
            return [
                {
                    "id": "karo",
                    "version": "0.2.0",
                    "downloads": 4_616,
                    "recent_downloads": 6,
                    "description": "Spreadsheet export",
                }
            ]
        if query == "xlsb":
            return [
                {
                    "id": "rxlsb",
                    "version": "0.1.0",
                    "downloads": 49,
                    "recent_downloads": 49,
                    "description": "XLSB reader and writer",
                },
                {
                    "id": "xlsb-writer",
                    "version": "0.1.0",
                    "downloads": 47,
                    "recent_downloads": 47,
                    "description": "XLSB writer",
                },
            ]
        if query == "xls":
            return [
                {
                    "id": "xlrd",
                    "version": "0.1.0",
                    "downloads": 591,
                    "recent_downloads": 21,
                    "description": "BIFF8 XLS reader",
                },
                {
                    "id": "wolfxl-core",
                    "version": "0.1.0",
                    "downloads": 1_002,
                    "recent_downloads": 50,
                    "description": "WolfXL core package",
                },
            ]
        return []

    report = audit.build_report(fetch_metadata=None, fetch_discovery=fake_discovery)
    packages = {row["id"]: row for row in report["packages"]}

    assert report["main_rust_competitor_set_ready"] is True
    assert report["unclassified_discovery_hits"] == []
    assert report["unclassified_relevant_below_threshold_hits"] == []
    assert packages["libxlsxwriter-sys"]["gate_status"] == "out_of_scope"
    assert "required xlsxwriter lane" in packages["libxlsxwriter-sys"]["reason"]
    assert packages["libxlsxwriter-sys-cs"]["gate_status"] == "out_of_scope"
    assert packages["wolfxl-core"]["gate_status"] == "out_of_scope"
    assert packages["karo"]["gate_status"] == "watchlist"
    assert packages["rxlsb"]["gate_status"] == "watchlist"
    assert packages["xlsb-writer"]["gate_status"] == "watchlist"
    assert packages["xlrd"]["gate_status"] == "watchlist"


def test_exact_xlsxwriter_rs_package_blocks_if_promotion_needed(monkeypatch) -> None:
    reviews = dict(audit.WATCHLIST_PROMOTION_REVIEWS)
    reviews["xlsxwriter-rs"] = {
        **reviews["xlsxwriter-rs"],
        "promotion_needed_now": True,
        "decision": "promote_required_lane",
    }
    monkeypatch.setattr(audit, "WATCHLIST_PROMOTION_REVIEWS", reviews)

    report = audit.build_report(fetch_metadata=None)

    assert report["main_rust_competitor_set_ready"] is False
    assert report["requested_competitor_name_resolution_ready"] is False
    assert report["requested_competitor_name_resolution_blockers"] == ["xlsxwriter-rs"]
    assert "requested Rust competitor names are not fully resolved" in " ".join(
        report["blockers"]
    )
    resolution = report["requested_competitor_name_resolutions"][0]
    assert resolution["exact_package_promotion_needed_now"] is True
    assert resolution["requirement_satisfied"] is False


def test_office_oxide_watchlist_reason_reflects_api_probe_boundary() -> None:
    report = audit.build_report(fetch_metadata=None)
    office_oxide = next(
        package for package in report["packages"] if package["id"] == "office_oxide"
    )

    assert office_oxide["gate_status"] == "watchlist"
    assert "simple XLSX read, write, and edit APIs" in office_oxide["compare_scope"]
    assert "broader Excel-specific behavior" in office_oxide["reason"]


def test_umya_spreadsheet_required_cases_include_read_write_and_modify() -> None:
    cases = {
        case
        for competitor, case in _required_competitor_cases()
        if competitor == "umya-spreadsheet"
    }

    assert cases == {
        "read_values_plain",
        "write_cell_by_cell_plain",
        "modify_existing_workbook_plain",
    }


def test_competitor_set_report_blocks_unclassified_discovery_hits() -> None:
    def fake_discovery(query: str) -> list[dict[str, object]]:
        assert query in audit.DISCOVERY_QUERIES
        if query != "xlsx":
            return []
        return [
            {
                "id": "new-fast-xlsx",
                "version": "1.0.0",
                "downloads": 5000,
                "recent_downloads": 100,
                "description": "Fast XLSX reader and writer",
            }
        ]

    report = audit.build_report(fetch_metadata=None, fetch_discovery=fake_discovery)

    assert report["main_rust_competitor_set_ready"] is False
    assert report["unclassified_discovery_hits"][0]["id"] == "new-fast-xlsx"
    assert "current crates.io discovery found unclassified Excel-related packages:" in report["blockers"][0]


def test_competitor_set_discovery_treats_office_and_xls_file_hits_as_relevant() -> None:
    def fake_discovery(query: str) -> list[dict[str, object]]:
        if query == "xls":
            return [
                {
                    "id": "new-xls-parser",
                    "version": "1.0.0",
                    "downloads": 5000,
                    "recent_downloads": 100,
                    "description": "Parse XLS files into typed records",
                },
                {
                    "id": "xlsynth-driver",
                    "version": "1.0.0",
                    "downloads": 5000,
                    "recent_downloads": 100,
                    "description": "Binary that integrates XLS capabilities into hardware synthesis",
                },
            ]
        if query == "workbook":
            return [
                {
                    "id": "new-office-parser",
                    "version": "1.0.0",
                    "downloads": 5000,
                    "recent_downloads": 100,
                    "description": "High-performance parser for Microsoft Office files",
                }
            ]
        return []

    report = audit.build_report(fetch_metadata=None, fetch_discovery=fake_discovery)
    rows = {
        row["id"]: row
        for result in report["discovery_results"]
        for row in result["results"]
    }

    assert report["main_rust_competitor_set_ready"] is False
    assert rows["new-xls-parser"]["relevant_to_excel_library"] is True
    assert rows["new-office-parser"]["relevant_to_excel_library"] is True
    assert rows["xlsynth-driver"]["relevant_to_excel_library"] is False
    assert {row["id"] for row in report["unclassified_discovery_hits"]} == {
        "new-xls-parser",
        "new-office-parser",
    }


def test_office_and_legacy_xls_discovery_hits_are_classified() -> None:
    def fake_discovery(query: str) -> list[dict[str, object]]:
        if query == "xls":
            return [
                {
                    "id": "madato",
                    "version": "0.8.0",
                    "downloads": 236_802,
                    "recent_downloads": 9_373,
                    "description": "A library and command line tool for reading and writing tabular data (XLS, ODS, CSV, YAML)",
                },
                {
                    "id": "xml-xls-parser",
                    "version": "0.1.0",
                    "downloads": 1762,
                    "recent_downloads": 6,
                    "description": "Parse XLS files as XML",
                },
                {
                    "id": "oca-parser-xls",
                    "version": "3.0.0",
                    "downloads": 11_906,
                    "recent_downloads": 13,
                    "description": "Command line tool for parsing XLS file into OCA",
                },
                {
                    "id": "xlsynth",
                    "version": "0.52.1",
                    "downloads": 607_855,
                    "recent_downloads": 158_011,
                    "description": "Accelerated Hardware Synthesis (XLS/XLSynth) via Rust",
                },
                {
                    "id": "oletools_rs",
                    "version": "0.1.0",
                    "downloads": 33,
                    "recent_downloads": 19,
                    "description": "Rust port of oletools - analysis tools for Microsoft Office files",
                },
            ]
        if query == "xlsb":
            return [
                {
                    "id": "litchi",
                    "version": "0.0.1",
                    "downloads": 2403,
                    "recent_downloads": 2069,
                    "description": "High-performance parser for Microsoft Office, OpenDocument, and Apple iWork file formats with unified API",
                }
            ]
        return []

    report = audit.build_report(fetch_metadata=None, fetch_discovery=fake_discovery)
    packages = {row["id"]: row for row in report["packages"]}

    assert report["main_rust_competitor_set_ready"] is True
    assert report["unclassified_discovery_hits"] == []
    assert packages["madato"]["gate_status"] == "watchlist"
    assert packages["litchi"]["gate_status"] == "watchlist"
    assert packages["xml-xls-parser"]["gate_status"] == "out_of_scope"
    assert packages["oca-parser-xls"]["gate_status"] == "out_of_scope"
    assert packages["xlsynth"]["gate_status"] == "out_of_scope"
    assert packages["oletools_rs"]["gate_status"] == "out_of_scope"


def test_litchi_watchlist_has_documented_non_promotion_decision() -> None:
    def fake_fetch(package: audit.CompetitorPackage) -> dict[str, object]:
        if package.id == "litchi":
            return {
                "version": "0.0.1",
                "downloads": 2403,
                "recent_downloads": 2069,
                "description": (
                    "High-performance parser for Microsoft Office, OpenDocument, "
                    "and Apple iWork file formats"
                ),
            }
        return {
            "version": "1.2.3",
            "downloads": 10,
            "recent_downloads": 2,
            "description": f"{package.id} description",
        }

    report = audit.build_report(fetch_metadata=fake_fetch, fetch_discovery=None)
    review = next(
        row for row in report["watchlist_promotion_reviews"] if row["id"] == "litchi"
    )

    assert review["broad_excel_scope"] is True
    assert review["performance_positioned"] is True
    assert review["positioning_handling"] == "documented_exclusion"
    assert review["positioning_handling_ready"] is True
    assert review["promotion_needed_now"] is False


def test_competitor_set_discovery_accepts_classified_hits() -> None:
    def fake_discovery(query: str) -> list[dict[str, object]]:
        if query != "xlsx":
            return []
        return [
            {
                "id": "rust_xlsxwriter",
                "version": "0.95.0",
                "downloads": 2_000_000,
                "recent_downloads": 700_000,
                "description": "A Rust library for writing Excel xlsx files",
            },
            {
                "id": "xlsx-handlebars",
                "version": "0.2.2",
                "downloads": 1547,
                "recent_downloads": 41,
                "description": "A Rust library for processing XLSX files with Handlebars templates",
            },
        ]

    report = audit.build_report(fetch_metadata=None, fetch_discovery=fake_discovery)

    assert report["main_rust_competitor_set_ready"] is True
    assert report["unclassified_discovery_hits"] == []
    rows = next(
        result["results"]
        for result in report["discovery_results"]
        if result["query"] == "xlsx"
    )
    assert rows[0]["gate_status"] == "required"
    assert rows[1]["gate_status"] == "watchlist"


def test_competitor_set_discovery_surfaces_below_threshold_unknowns() -> None:
    def fake_discovery(query: str) -> list[dict[str, object]]:
        if query != "xlsx":
            return []
        return [
            {
                "id": "tiny-xlsx-helper",
                "version": "0.1.0",
                "downloads": 10,
                "recent_downloads": 2,
                "description": "Tiny XLSX helper",
            }
        ]

    report = audit.build_report(fetch_metadata=None, fetch_discovery=fake_discovery)

    assert report["main_rust_competitor_set_ready"] is True
    assert report["unclassified_discovery_hits"] == []
    assert report["unclassified_relevant_below_threshold_hits"][0]["id"] == (
        "tiny-xlsx-helper"
    )


def test_competitor_set_pypi_discovery_blocks_unclassified_rust_backed_hits() -> None:
    def fake_pypi_discovery() -> list[dict[str, object]]:
        return [
            {
                "id": "new-rust-xlsx",
                "display_name": "new-rust-xlsx",
                "version": "1.0.0",
                "description": "Rust-backed XLSX reader and writer using PyO3",
            }
        ]

    report = audit.build_report(
        fetch_metadata=None,
        fetch_pypi_discovery_func=fake_pypi_discovery,
    )

    assert report["main_rust_competitor_set_ready"] is False
    assert report["metadata"]["pypi_discovery_fetched"] is True
    assert report["unclassified_pypi_discovery_hits"][0]["id"] == "new-rust-xlsx"
    assert (
        "current PyPI discovery found unclassified Rust-backed Excel-related packages:"
        in report["blockers"][0]
    )


def test_competitor_set_records_pypi_discovery_summary() -> None:
    def fake_pypi_discovery() -> dict[str, object]:
        return {
            "hits": [
                {
                    "id": "fastxlsx",
                    "display_name": "fastxlsx",
                    "version": "0.2.0",
                    "description": "Rust-backed XLSX reads and writes",
                }
            ],
            "summary": {
                "simple_project_count": 600_000,
                "candidate_pool_count": 37,
                "selected_candidate_count": 1,
                "candidate_limit": audit.PYPI_DISCOVERY_CANDIDATE_LIMIT,
                "candidate_limit_reached": False,
                "skipped_candidate_count": 0,
                "name_terms": list(audit.PYPI_DISCOVERY_NAME_TERMS),
                "rust_hint_terms": list(audit.PYPI_DISCOVERY_RUST_HINT_TERMS),
            },
        }

    report = audit.build_report(
        fetch_metadata=None,
        fetch_pypi_discovery_func=fake_pypi_discovery,
    )

    summary = report["pypi_discovery_summary"]
    assert summary["simple_project_count"] == 600_000
    assert summary["candidate_pool_count"] == 37
    assert summary["candidate_limit_reached"] is False
    assert report["pypi_discovery_results"][0]["summary"] == summary
    assert "Candidate pool" in audit.format_markdown_report(report)


def test_competitor_set_pypi_discovery_accepts_classified_hits() -> None:
    def fake_pypi_discovery() -> list[dict[str, object]]:
        return [
            {
                "id": "fastxlsx",
                "display_name": "fastxlsx",
                "version": "0.2.0",
                "description": "Rust-backed XLSX reads and writes",
            }
        ]

    report = audit.build_report(
        fetch_metadata=None,
        fetch_pypi_discovery_func=fake_pypi_discovery,
    )

    assert report["main_rust_competitor_set_ready"] is True
    assert report["unclassified_pypi_discovery_hits"] == []
    rows = report["pypi_discovery_results"][0]["results"]
    assert rows[0]["gate_status"] == "watchlist"
    assert rows[0]["rust_backed_candidate"] is True


def test_competitor_set_pypi_discovery_does_not_cross_classify_name_collision() -> None:
    def fake_pypi_discovery() -> list[dict[str, object]]:
        return [
            {
                "id": "xlsxwriter",
                "display_name": "XlsxWriter",
                "version": "3.2.9",
                "description": "A Python module for creating Excel XLSX files.",
            },
            {
                "id": "fastexcel",
                "display_name": "fastexcel",
                "version": "0.20.2",
                "description": "A fast excel file reader for Python, written in Rust",
            },
        ]

    report = audit.build_report(
        fetch_metadata=None,
        fetch_pypi_discovery_func=fake_pypi_discovery,
    )
    rows = {row["id"]: row for row in report["pypi_discovery_results"][0]["results"]}

    assert report["main_rust_competitor_set_ready"] is True
    assert rows["xlsxwriter"]["classified"] is False
    assert rows["xlsxwriter"]["gate_status"] is None
    assert rows["xlsxwriter"]["rust_backed_candidate"] is False
    assert rows["fastexcel"]["classified"] is True
    assert rows["fastexcel"]["gate_status"] == "required"
    assert rows["fastexcel"]["rust_backed_candidate"] is True
    assert report["unclassified_pypi_discovery_hits"] == []


def test_competitor_set_pypi_discovery_classifies_calamine_named_hits() -> None:
    def fake_pypi_discovery() -> list[dict[str, object]]:
        return [
            {
                "id": "calamine-tablib",
                "display_name": "calamine-tablib",
                "version": "0.1.0",
                "description": "Tablib adapter using calamine",
            }
        ]

    report = audit.build_report(
        fetch_metadata=None,
        fetch_pypi_discovery_func=fake_pypi_discovery,
    )

    assert report["main_rust_competitor_set_ready"] is True
    assert report["unclassified_pypi_discovery_hits"] == []
    rows = report["pypi_discovery_results"][0]["results"]
    assert rows[0]["relevant_to_excel_library"] is True
    assert rows[0]["gate_status"] == "out_of_scope"


def test_competitor_set_report_attaches_registry_metadata() -> None:
    def fake_fetch(package: audit.CompetitorPackage) -> dict[str, object]:
        return {
            "version": "1.2.3",
            "downloads": 10,
            "recent_downloads": 2,
            "description": f"{package.id} description",
        }

    report = audit.build_report(fetch_metadata=fake_fetch)

    assert report["metadata"]["registry_metadata_fetched"] is True
    assert report["packages"][0]["registry"]["version"] == "1.2.3"
    assert report["metadata_error_competitors"] == []


def test_competitor_set_report_blocks_when_registry_metadata_fails() -> None:
    def fake_fetch(package: audit.CompetitorPackage) -> dict[str, object]:
        if package.id == "calamine":
            raise OSError("registry unavailable")
        return {
            "version": "1.2.3",
            "downloads": 10,
            "recent_downloads": 2,
        }

    report = audit.build_report(fetch_metadata=fake_fetch)

    assert report["main_rust_competitor_set_ready"] is False
    assert report["metadata_error_competitors"] == ["calamine"]
    assert "live registry metadata could not be fetched for: calamine" in report["blockers"]


def test_competitor_set_report_uses_discovery_metadata_fallback() -> None:
    def fake_fetch(package: audit.CompetitorPackage) -> dict[str, object]:
        if package.id == "calamine":
            raise OSError("registry unavailable")
        return {
            "version": "1.2.3",
            "downloads": 10,
            "recent_downloads": 2,
        }

    def fake_discovery(query: str) -> list[dict[str, object]]:
        if query != "xlsx":
            return []
        return [
            {
                "id": "calamine",
                "version": "0.35.0",
                "downloads": 8_000_000,
                "recent_downloads": 2_000_000,
                "description": "An Excel/OpenDocument Spreadsheet reader in pure Rust",
            }
        ]

    report = audit.build_report(
        fetch_metadata=fake_fetch,
        fetch_discovery=fake_discovery,
    )
    calamine = next(row for row in report["packages"] if row["id"] == "calamine")

    assert report["main_rust_competitor_set_ready"] is True
    assert report["metadata_error_competitors"] == []
    assert report["direct_metadata_error_competitors"] == ["calamine"]
    assert report["metadata_fallback_competitors"] == ["calamine"]
    assert calamine["registry"]["version"] == "0.35.0"
    assert calamine["registry_source"] == "crates_io_search_fallback"


def test_fetch_json_retries_transient_timeout(monkeypatch) -> None:
    calls = []

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"ok": true}'

    def fake_urlopen(request: object, *, timeout: float) -> FakeResponse:
        calls.append((request, timeout))
        if len(calls) == 1:
            raise TimeoutError("temporary crates.io timeout")
        return FakeResponse()

    monkeypatch.setattr(audit, "urlopen", fake_urlopen)
    monkeypatch.setattr(audit, "sleep", lambda _: None)

    assert audit._fetch_json("https://example.test/crates", 1.0) == {"ok": True}
    assert len(calls) == 2


def test_fetch_json_raises_after_retry_budget(monkeypatch) -> None:
    calls = []

    def fake_urlopen(request: object, *, timeout: float) -> object:
        calls.append((request, timeout))
        raise TimeoutError("still down")

    monkeypatch.setattr(audit, "urlopen", fake_urlopen)
    monkeypatch.setattr(audit, "sleep", lambda _: None)

    try:
        audit._fetch_json(
            "https://example.test/crates",
            1.0,
            attempts=2,
        )
    except TimeoutError as exc:
        assert str(exc) == "still down"
    else:
        raise AssertionError("expected TimeoutError")
    assert len(calls) == 2


def test_competitor_set_report_blocks_stale_benchmark_versions(tmp_path: Path) -> None:
    benchmark = tmp_path / "rust-benchmark.json"
    benchmark.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "competitor": competitor,
                        "competitor_version": "2.0.0" if competitor == "calamine" else "1.2.3",
                    }
                    for competitor in audit.DEFAULT_RUST_COMPETITORS
                ]
            }
        )
    )

    def fake_fetch(package: audit.CompetitorPackage) -> dict[str, object]:
        return {
            "version": "3.0.0" if package.id == "calamine" else "1.2.3",
            "downloads": 10,
            "recent_downloads": 2,
        }

    report = audit.build_report(fetch_metadata=fake_fetch, benchmark=benchmark)

    assert report["main_rust_competitor_set_ready"] is False
    assert report["benchmark_present"] is True
    assert report["missing_from_benchmark"] == []
    assert report["missing_benchmark_versions"] == []
    assert report["stale_benchmark_versions"] == [
        {
            "competitor": "calamine",
            "benchmark_version": "2.0.0",
            "registry_version": "3.0.0",
        }
    ]
    assert "Rust competitor benchmark uses stale resolved versions for:" in report["blockers"][0]


def test_competitor_set_report_blocks_missing_benchmark_competitor(tmp_path: Path) -> None:
    benchmark = tmp_path / "rust-benchmark.json"
    benchmark.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "competitor": "calamine",
                        "competitor_version": "0.35.0",
                    }
                ]
            }
        )
    )

    report = audit.build_report(fetch_metadata=None, benchmark=benchmark)

    assert report["main_rust_competitor_set_ready"] is False
    assert report["benchmark_competitors"] == ["calamine"]
    assert "rust_xlsxwriter" in report["missing_from_benchmark"]
    assert any(
        blocker.startswith(
            "supplied Rust competitor benchmark is missing required competitors:"
        )
        for blocker in report["blockers"]
    )


def test_competitor_set_report_blocks_missing_benchmark_versions(tmp_path: Path) -> None:
    benchmark = tmp_path / "rust-benchmark.json"
    benchmark.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "competitor": competitor,
                        **(
                            {}
                            if competitor == "calamine"
                            else {"competitor_version": "1.2.3"}
                        ),
                    }
                    for competitor in audit.DEFAULT_RUST_COMPETITORS
                ]
            }
        )
    )

    report = audit.build_report(fetch_metadata=None, benchmark=benchmark)

    assert report["main_rust_competitor_set_ready"] is False
    assert report["missing_from_benchmark"] == []
    assert report["missing_benchmark_versions"] == ["calamine"]
    assert (
        "supplied Rust competitor benchmark is missing resolved versions for: calamine"
        in report["blockers"]
    )


def test_competitor_set_report_summarizes_required_version_evidence(
    tmp_path: Path,
) -> None:
    benchmark = tmp_path / "rust-benchmark.json"
    benchmark.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "competitor": competitor,
                        "competitor_version": f"{competitor}-version",
                        "competitor_api_surface": (
                            "python_binding_api"
                            if competitor in {"fastexcel", "python-calamine"}
                            else "direct_rust_api"
                        ),
                        "case": case,
                    }
                    for competitor, case in _required_competitor_cases()
                ]
            }
        )
    )

    report = audit.build_report(fetch_metadata=None, benchmark=benchmark)
    evidence_by_competitor = {
        row["competitor"]: row
        for row in report["required_competitor_version_evidence"]
    }

    assert set(evidence_by_competitor) == set(audit.DEFAULT_RUST_COMPETITORS)
    assert all(row["version_captured"] for row in evidence_by_competitor.values())
    assert evidence_by_competitor["calamine"]["benchmark_version"] == "calamine-version"
    assert evidence_by_competitor["calamine"]["benchmark_api_surfaces"] == [
        "direct_rust_api"
    ]
    assert evidence_by_competitor["fastexcel"]["benchmark_api_surfaces"] == [
        "python_binding_api"
    ]
    assert report["benchmark_competitor_api_surfaces"]["python-calamine"] == [
        "python_binding_api"
    ]
    assert evidence_by_competitor["xlsxwriter"]["aliases"] == ["xlsxwriter-rs"]
    assert report["required_competitor_aliases"] == {
        "xlsxwriter": ["xlsxwriter-rs"]
    }


def test_competitor_set_cli_can_write_report(tmp_path: Path, capsys) -> None:
    output = tmp_path / "rust-competitor-set.json"

    audit.main(["--no-fetch", "--output", str(output)])
    payload = json.loads(output.read_text())
    printed = json.loads(capsys.readouterr().out)

    assert payload["main_rust_competitor_set_ready"] is True
    assert printed["required_competitors"] == payload["required_competitors"]


def test_markdown_report_summarizes_required_and_watchlist_packages() -> None:
    report = audit.build_report(fetch_metadata=None)

    markdown = audit.format_markdown_report(report)

    assert "# WolfXL Rust Competitor Set Audit" in markdown
    assert "- Ready: `true`" in markdown
    assert "- Discovery threshold: `top 50 per query;" in markdown
    assert "## Required Benchmark Competitors" in markdown
    assert "| calamine | crates.io |" in markdown
    assert "| rust_xlsxwriter | crates.io |" in markdown
    assert "| xlsxwriter | crates.io | xlsxwriter-rs |" in markdown
    assert "## Watchlist Packages" in markdown
    assert "| rustypyxl | pypi |" in markdown
    assert "## Watchlist Promotion Review" in markdown
    assert "## Watchlist Adoption Attention" in markdown
    assert "| Packages reviewed | 0 |" in markdown
    assert (
        "| fastxlsx | pypi | medium | no | not_high_risk |  |  | yes | no | no | covered_by_required_lanes | "
        "calamine, rust_xlsxwriter |"
    ) in markdown
    assert "| office_oxide | crates.io | high | no | adoption_evidence_unavailable |" in markdown
    assert "| benchmark_lane | calamine, umya-spreadsheet |" in markdown
    assert "## Claim Boundary" in markdown


def test_markdown_report_summarizes_supplied_benchmark_coverage(tmp_path: Path) -> None:
    benchmark = tmp_path / "rust-benchmark.json"
    benchmark.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "competitor": competitor,
                        "competitor_version": "1.2.3",
                        "case": case,
                    }
                    for competitor, case in _required_competitor_cases()
                ]
            }
        )
    )

    report = audit.build_report(fetch_metadata=None, benchmark=benchmark)
    markdown = audit.format_markdown_report(report)

    assert "## Supplied Benchmark Coverage" in markdown
    assert "| Missing competitors | none |" in markdown
    assert "| Missing resolved versions | none |" in markdown
    assert (
        "| Required versions captured | rust_xlsxwriter, xlsxwriter, calamine, "
        "umya-spreadsheet, fastexcel, python-calamine |"
    ) in markdown
    assert "| Missing required case families | 0 |" in markdown


def test_competitor_set_report_blocks_missing_required_case_families(
    tmp_path: Path,
) -> None:
    benchmark = tmp_path / "rust-benchmark.json"
    benchmark.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "case": "write_cell_by_cell_plain",
                        "competitor": "rust_xlsxwriter",
                        "competitor_version": "0.95.0",
                    }
                ]
            }
        )
    )

    report = audit.build_report(
        fetch_metadata=None,
        benchmark=benchmark,
        required_benchmark_competitors=("rust_xlsxwriter",),
    )

    assert report["main_rust_competitor_set_ready"] is False
    assert report["missing_required_case_family_count"] == 1
    assert report["missing_required_case_families"] == [
        {
            "competitor": "rust_xlsxwriter",
            "missing_case_families": [
                "high_cardinality_string_write",
                "formula_write",
                "styled_value_write",
                "multi_sheet_write",
            ],
            "observed_cases": ["write_cell_by_cell_plain"],
        }
    ]
    assert any(
        blocker.startswith(
            "supplied Rust competitor benchmark is missing required case families for:"
        )
        for blocker in report["blockers"]
    )


def test_competitor_set_case_family_gate_does_not_cross_count_plain_terms(
    tmp_path: Path,
) -> None:
    benchmark = tmp_path / "rust-benchmark.json"
    benchmark.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "case": "write_multi_sheet_plain",
                        "competitor": "rust_xlsxwriter",
                        "competitor_version": "0.95.0",
                    }
                ]
            }
        )
    )

    report = audit.build_report(
        fetch_metadata=None,
        benchmark=benchmark,
        required_benchmark_competitors=("rust_xlsxwriter",),
    )

    assert report["missing_required_case_families"] == [
        {
            "competitor": "rust_xlsxwriter",
            "missing_case_families": [
                "plain_value_write",
                "high_cardinality_string_write",
                "formula_write",
                "styled_value_write",
            ],
            "observed_cases": ["write_multi_sheet_plain"],
        }
    ]


def test_markdown_report_includes_blockers_and_discovery_summary() -> None:
    def fake_discovery(query: str) -> list[dict[str, object]]:
        if query != "xlsx":
            return []
        return [
            {
                "id": "new-fast-xlsx",
                "version": "1.0.0",
                "downloads": 5000,
                "recent_downloads": 100,
                "description": "Fast XLSX reader and writer",
            }
        ]

    report = audit.build_report(fetch_metadata=None, fetch_discovery=fake_discovery)

    markdown = audit.format_markdown_report(report)

    assert "## Blockers" in markdown
    assert "new-fast-xlsx" in markdown
    assert "| crates.io | xlsx | 1 | 1 |" in markdown
    assert "## Unclassified Discovery Hits" in markdown


def test_markdown_report_includes_below_threshold_unknowns() -> None:
    def fake_discovery(query: str) -> list[dict[str, object]]:
        if query != "xlsx":
            return []
        return [
            {
                "id": "tiny-xlsx-helper",
                "version": "0.1.0",
                "downloads": 10,
                "recent_downloads": 2,
                "description": "Tiny XLSX helper",
            }
        ]

    report = audit.build_report(fetch_metadata=None, fetch_discovery=fake_discovery)
    markdown = audit.format_markdown_report(report)

    assert "## Low-Adoption Unclassified Relevant Hits" in markdown
    assert "tiny-xlsx-helper" in markdown


def test_competitor_set_cli_can_write_markdown_report(tmp_path: Path, capsys) -> None:
    output = tmp_path / "rust-competitor-set.json"
    markdown_output = tmp_path / "rust-competitor-set.md"

    audit.main(
        [
            "--no-fetch",
            "--output",
            str(output),
            "--markdown-output",
            str(markdown_output),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["main_rust_competitor_set_ready"] is True
    assert output.exists()
    assert markdown_output.read_text().startswith("# WolfXL Rust Competitor Set Audit")
