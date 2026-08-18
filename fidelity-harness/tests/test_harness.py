from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

HARNESS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HARNESS_ROOT))

import corpus  # noqa: E402  # pyright: ignore[reportMissingImports]
from engines import Engine, build_openpyxl  # noqa: E402  # pyright: ignore[reportMissingImports]
from roundtrip import _feature_losses, run, run_one  # noqa: E402  # pyright: ignore[reportMissingImports]


def test_generated_corpus_is_byte_deterministic_and_structurally_valid(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"

    fixtures = corpus.generate(first)
    corpus.generate(second)

    assert corpus.verify(first) == []
    assert corpus.verify(second) == []
    assert len(fixtures) == len(corpus.FIXTURES)
    for fixture in fixtures:
        assert (first / fixture.name).read_bytes() == (second / fixture.name).read_bytes()


def test_generator_refuses_to_clean_unmarked_directory(tmp_path: Path) -> None:
    destination = tmp_path / "user-files"
    destination.mkdir()
    owned = destination / "important.txt"
    owned.write_text("keep me", encoding="utf-8")

    with pytest.raises(RuntimeError, match="unmarked directory"):
        corpus.generate(destination)

    assert owned.read_text(encoding="utf-8") == "keep me"


def test_generator_cleans_only_owned_fixture_files(tmp_path: Path) -> None:
    destination = tmp_path / "corpus"
    corpus.generate(destination)
    unrelated = destination / "keep-me.txt"
    unrelated.write_text("user data", encoding="utf-8")

    corpus.generate(destination)

    assert unrelated.read_text(encoding="utf-8") == "user data"
    assert corpus.verify(destination) == []


def test_run_one_cannot_reuse_a_stale_output(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    corpus.generate(source_dir)
    source = source_dir / "styles.xlsx"
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    identity = Engine("identity", "1", lambda before, after: after.write_bytes(before.read_bytes()))

    def fail_without_output(_before: Path, _after: Path) -> None:
        raise RuntimeError("expected failure")

    failing = Engine("failing", "1", fail_without_output)

    first = run_one(identity, source, "test", workspace)
    second = run_one(failing, source, "test", workspace)

    assert first.status == "faithful"
    assert second.status == "error"
    assert "expected failure" in second.detail
    assert not (workspace / "out-styles.xlsx").exists()


def test_feature_loss_labels_only_specific_vanished_parts() -> None:
    assert _feature_losses(["xl/worksheets/_rels/sheet1.xml.rels"]) == []
    assert _feature_losses(["xl/worksheets/sheet1.xml"]) == []
    assert _feature_losses(["customXml/item1.xml"]) == ["custom_xml"]
    assert _feature_losses(["xl/slicers/slicer1.xml"]) == ["slicer"]


def test_openpyxl_adapter_requires_and_records_fair_preservation_settings() -> None:
    engine = build_openpyxl()

    assert engine.name == "openpyxl"
    assert engine.settings["keep_links"] is True
    assert engine.settings["rich_text"] is True
    assert engine.settings["data_only"] is False
    assert engine.settings["pillow"]


def test_report_records_sources_without_absolute_corpus_path(tmp_path: Path) -> None:
    source_dir = tmp_path / "corpus"
    corpus.generate(source_dir)
    identity = Engine("identity", "1", lambda before, after: after.write_bytes(before.read_bytes()))

    report = run(source_dir, [identity])
    encoded = json.dumps(report)

    assert str(tmp_path) not in encoded
    assert "path" not in report["corpus"]
    assert len(report["corpus"]["workbooks"]) == len(corpus.FIXTURES)
    assert all(len(item["sha256"]) == 64 for item in report["corpus"]["workbooks"])
    assert all(len(digest) == 64 for digest in report["implementation"].values())
    assert report["totals"]["identity"]["faithful"] == len(corpus.FIXTURES)


def test_checked_in_result_matches_harness_source_hashes() -> None:
    report = json.loads(
        (HARNESS_ROOT / "results" / "2026-08-18.json").read_text(encoding="utf-8")
    )

    for name, expected in report["implementation"].items():
        actual = hashlib.sha256((HARNESS_ROOT / name).read_bytes()).hexdigest()
        assert actual == expected, f"checked-in evidence is stale for {name}"
