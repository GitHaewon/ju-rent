"""Check that the migrated RTMS exports reproduce the original audit."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "data" / "audit"
RAW = ROOT / "data" / "raw"
BASELINE = ROOT / "tests" / "fixtures" / "counts_before_migration.json"
MANIFEST_BASELINE = ROOT / "tests" / "fixtures" / "manifest_before_migration.json"


def test_raw_exports_match_manifest():
    manifest = json.loads((AUDIT / "manifest.json").read_text(encoding="utf-8"))
    original = json.loads(MANIFEST_BASELINE.read_text(encoding="utf-8"))
    baseline = [entry for entry in manifest if entry["year"] <= 2025]
    assert sorted(baseline, key=lambda entry: entry["filename"]) == sorted(
        original, key=lambda entry: entry["filename"]
    )
    assert {path.name for path in RAW.glob("*.csv")} == {
        entry["filename"] for entry in manifest
    }
    for entry in manifest:
        source = RAW / entry["filename"]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == entry["sha256"]


def test_rerun_matches_original_counts():
    expected = json.loads(BASELINE.read_text(encoding="utf-8"))
    # D-011 preserves the original sample; Q-002 only renames missing contracts.
    for key in ("analytic_by_contract", "analytic_2025_contract"):
        expected[key]["미기재"] = expected[key].pop("-")
    expected["jeonju_detached_lot_masking"] = {
        "masked": expected["detached_masked_lot"],
        "total": expected["detached_rows"],
    }
    expected["analytic_by_area_basis"] = {"전용": 863, "계약": 4936}
    subprocess.run(
        [sys.executable, str(ROOT / "src" / "analyze_rentals.py")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    actual = json.loads((AUDIT / "counts.json").read_text(encoding="utf-8"))
    assert {key: actual[key] for key in expected} == expected
    # N-001 and N-002 are marked verified in NUMBERS.md.
    assert actual["total"] == 104144
    assert [
        sum(item["count"] for item in actual["year_gu"] if item["year"] == year)
        for year in range(2021, 2026)
    ] == [21256, 23666, 21083, 19594, 18545]
