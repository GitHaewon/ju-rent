"""Check that the migrated RTMS exports reproduce the original audit."""

import hashlib
import json
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
    assert sorted(manifest, key=lambda entry: entry["filename"]) == sorted(
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
    subprocess.run(
        [sys.executable, str(ROOT / "src" / "analyze_rentals.py")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    actual = json.loads((AUDIT / "counts.json").read_text(encoding="utf-8"))
    assert actual == expected
