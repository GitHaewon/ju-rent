"""Check the read-only construction-year coverage audit."""

import json
from pathlib import Path

from src import audit_field_coverage as audit

ROOT = Path(__file__).resolve().parents[1]


def test_missing_column_and_blank_values(monkeypatch, tmp_path):
    monkeypatch.setattr(audit, "RAW", tmp_path)
    monkeypatch.setattr(audit, "YEARS", [2021])
    monkeypatch.setattr(audit, "GUS", {"완산": "wansan", "덕진": "deokjin"})
    for gu in ("wansan", "deokjin"):
        (tmp_path / f"detached_multiunit_{gu}_2021.csv").touch()

    def fake_read_csv(path):
        if "wansan" in path.name:
            return "", ["건축년도"], [{"건축년도": "2001"}, {"건축년도": "-"}, {"건축년도": ""}]
        return "", ["NO"], [{"NO": "1"}]

    monkeypatch.setattr(audit, "read_csv", fake_read_csv)
    assert audit.coverage_for_type("detached_multiunit") == {
        "files": 2,
        "files_with_column": 1,
        "column_in_all_files": False,
        "rows": 4,
        "missing_rows": 3,
        "missing_rate_pct": 75.0,
    }


def test_generated_coverage_accounts_for_all_public_rows():
    audit.main()
    result = json.loads((ROOT / "outputs" / "field_coverage.json").read_text(encoding="utf-8"))
    counts = json.loads((ROOT / "data" / "audit" / "counts.json").read_text(encoding="utf-8"))
    assert sum(item["rows"] for item in result["by_type"].values()) == (
        counts["total"] + counts["year_2026"]["total"]
    )
    for item in result["by_type"].values():
        assert item["files_with_column"] <= item["files"]
        assert 0 <= item["missing_rows"] <= item["rows"]
