"""Validate the supplied 2026 exports and PR-1 outputs."""

import csv
import json
from pathlib import Path

import pytest

from src import analyze_rentals as rentals

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"


@pytest.fixture(scope="module")
def counts():
    rentals.main()
    return json.loads((ROOT / "data" / "audit" / "counts.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("kind", rentals.TYPES.values())
@pytest.mark.parametrize("gu", rentals.GUS.values())
def test_2026_search_conditions_and_matching_2025_header(kind, gu):
    source = RAW / f"{kind}_{gu}_2026.csv"
    notes, fields, _ = rentals.read_csv(source)
    rentals.validate_export(source, notes, fields, kind, gu, 2026)
    _, prior_fields, _ = rentals.read_csv(RAW / f"{kind}_{gu}_2025.csv")
    assert fields == prior_fields


@pytest.mark.parametrize(
    ("correct", "wrong"),
    [
        ("2026-10-31", "2026-12-31"),
        ("아파트(전월세)", "아파트(매매)"),
        ("전주시 덕진구", "전주시 완산구"),
        ("지번주소", "도로명주소"),
        ("읍면동 : 전체", "읍면동 : 덕진동1가"),
    ],
)
def test_wrong_search_condition_fails(correct, wrong):
    source = RAW / "apartment_deokjin_2026.csv"
    notes, fields, _ = rentals.read_csv(source)
    with pytest.raises(RuntimeError, match="Wrong"):
        rentals.validate_export(source, notes.replace(correct, wrong), fields, "apartment", "deokjin", 2026)


@pytest.mark.parametrize("column", ["전용면적(㎡)", "보증금(만원)", "월세금(만원)"])
def test_missing_required_column_fails(column):
    source = RAW / "apartment_deokjin_2026.csv"
    notes, fields, _ = rentals.read_csv(source)
    with pytest.raises(RuntimeError, match="Invalid CSV columns"):
        rentals.validate_export(source, notes, [field for field in fields if field != column], "apartment", "deokjin", 2026)


def test_main_stops_on_missing_required_column(monkeypatch):
    original = rentals.read_csv

    def missing_area(path):
        notes, fields, rows = original(path)
        if path.name == "apartment_deokjin_2026.csv":
            fields = [field for field in fields if field != "전용면적(㎡)"]
        return notes, fields, rows

    monkeypatch.setattr(rentals, "read_csv", missing_area)
    with pytest.raises(RuntimeError, match="Invalid CSV columns"):
        rentals.main()


@pytest.mark.parametrize(
    ("year", "month", "partial", "recent"),
    [(2025, 10, False, False), (2026, 8, True, False), (2026, 9, True, True), (2026, 10, True, True)],
)
def test_period_flags(year, month, partial, recent):
    assert rentals.period_flags(year, month) == {"partial_year": partial, "incomplete_recent": recent}


def test_2026_months_and_manifest(counts):
    current = counts["year_2026"]
    assert current["partial_year"] is True
    assert sum(item["count"] for item in current["months"]) == current["total"]
    assert [item["month"] for item in current["months"] if item["incomplete_recent"]] == [9, 10]
    manifest = json.loads((ROOT / "data" / "audit" / "manifest.json").read_text(encoding="utf-8"))
    current_entries = [entry for entry in manifest if entry["year"] == 2026 and entry["partial_year"]]
    assert len(current_entries) == 8
    for entry in current_entries:
        _, _, rows = rentals.read_csv(RAW / entry["filename"])
        assert entry["rows"] == len(rows)


def test_contract_counts_sum_to_each_year_sample(counts):
    for entry in counts["contract_by_year"]:
        assert entry["신규"] + entry["갱신"] + entry["미기재"] == entry["total"]
        expected = counts["year_2026"]["analytic"] if entry["year"] == 2026 else counts["analytic_by_year"][str(entry["year"])]
        assert entry["total"] == expected


def test_candidate_table_contains_only_provisional_dongs(counts):
    with (ROOT / "outputs" / "campus_dong_candidates.csv").open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert {("효자동권", "효자동2가"), ("전북대권", "덕진동1가")} <= {
        (row["대학가"], row["후보_법정동"]) for row in rows
    }
    for row in rows:
        assert int(row["유효_표본_수"]) == sum(
            int(row[column]) for column in ("아파트", "연립다세대", "단독다가구", "오피스텔")
        )
        assert row["partial_year"] == str(int(row["연도"]) == 2026).lower()
    assert counts["year_2026"]["analytic"] > 0


def test_april_complex_audit_preserves_all_rows(counts):
    april = counts["apartment_deokjin_2026_april"]
    assert next(item["count"] for item in april["monthly_rows"] if item["month"] == 4) == april["april_rows"]
    assert april["top_two_complexes_rows"] == sum(item["count"] for item in april["top_complexes"][:2])
    assert april["top_two_complexes_rows"] <= april["april_rows"]


def test_verified_2026_totals_n010_n011(counts):
    assert counts["year_2026"]["total"] == 15217
    assert counts["year_2026"]["analytic"] == 1318


def test_verified_contract_distribution_n012(counts):
    assert [
        (item["year"], item["신규"], item["갱신"], item["미기재"])
        for item in counts["contract_by_year"]
    ] == [
        (2021, 231, 3, 687),
        (2022, 452, 19, 652),
        (2023, 509, 20, 515),
        (2024, 1035, 60, 124),
        (2025, 1343, 60, 89),
        (2026, 1173, 52, 93),
    ]


def test_verified_april_complex_n013(counts):
    april = counts["apartment_deokjin_2026_april"]
    assert (
        april["april_rows"],
        april["top_complex_rows"],
        april["top_complex_share_pct"],
        april["top_two_complexes_rows"],
        april["top_two_complexes_share_pct"],
    ) == (1780, 794, 44.6, 1500, 84.3)


def test_verified_candidate_table_n014(counts):
    with (ROOT / "tests" / "fixtures" / "campus_dong_candidates_verified.csv").open(
        encoding="utf-8-sig", newline=""
    ) as fh:
        expected = list(csv.DictReader(fh))
    with (ROOT / "outputs" / "campus_dong_candidates.csv").open(encoding="utf-8-sig", newline="") as fh:
        actual = list(csv.DictReader(fh))
    assert actual == expected
