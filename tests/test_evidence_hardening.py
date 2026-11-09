"""Fixed verified values and PR-4 evidence consistency checks."""

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import pytest

from src import analyze_rentals as rentals
from src import build_dorm_capacity as dorm
from src import check_lawd_codes as lawd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "rationale"
FIXTURES = ROOT / "tests" / "fixtures"


def csv_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


@pytest.fixture(scope="module")
def counts():
    rentals.main()
    dorm.main()
    return json.loads((ROOT / "data" / "audit" / "counts.json").read_text(encoding="utf-8"))


def test_n015_field_coverage_fixed():
    coverage = json.loads((ROOT / "outputs" / "field_coverage.json").read_text(encoding="utf-8"))
    assert coverage["by_type"] == json.loads(
        (FIXTURES / "field_coverage_n015.json").read_text(encoding="utf-8")
    )


def test_n016_legacy_rows_fixed(counts):
    expected = csv_rows(FIXTURES / "monthly_share_n016.csv")
    actual = csv_rows(OUT / "monthly_share.csv")
    assert len(actual) == len(expected) + 6
    assert [{key: row[key] for key in expected[0]} for row in actual if row["variant"] != "두 단지 전 기간 제외"] == expected


def test_n017_legacy_columns_fixed_and_partial_year(counts):
    expected = csv_rows(FIXTURES / "campus_trend_n017.csv")
    actual = csv_rows(OUT / "campus_trend.csv")
    assert len(actual) == len(expected) == 12
    assert [{key: row[key] for key in expected[0]} for row in actual] == expected
    assert all(row["partial_year"] == str(int(row["year"]) == 2026).lower() for row in actual)


def test_n018_single_households_fixed():
    rows = csv_rows(OUT / "single_households.csv")
    assert [int(row["age_20s_total"]) for row in rows] == [23511, 22249, 22723, 21739, 21781]


def test_n019_campus_areas_fixed(counts):
    expected = json.loads((FIXTURES / "campus_areas_n019.json").read_text(encoding="utf-8"))
    assert counts["campus_areas"] == expected


def test_t15_same_period_bounds_and_2026(counts):
    rows = csv_rows(OUT / "campus_trend.csv")
    for row in rows:
        assert int(row["jan_oct_valid_small_monthly"]) <= int(row["valid_small_monthly"])
        assert int(row["jan_oct_city_public_rows"]) <= int(row["city_public_rows"])
        if row["year"] == "2026":
            assert row["jan_oct_valid_small_monthly"] == row["valid_small_monthly"]
            assert row["jan_oct_city_public_rows"] == row["city_public_rows"]
        if row["year"] == "2021":
            assert row["jan_oct_change_from_2021_pct"] == "0.0"
            assert row["jan_oct_city_change_from_2021_pct"] == "0.0"


def test_t16_all_year_exclusion_matches_counts(counts):
    rows = csv_rows(OUT / "monthly_share.csv")
    city = {(int(r["year"]), r["variant"]): r for r in rows if r["scope"] == "완산·덕진 전체"}
    for entry in counts["apartment_deokjin_top_two_all_years"]["by_year"]:
        year = entry["year"]
        assert int(city[year, "포함"]["total_rows"]) - int(city[year, "두 단지 전 기간 제외"]["total_rows"]) == entry["rows"]
    assert sum(entry["rows"] for entry in counts["apartment_deokjin_top_two_all_years"]["by_year"]) > 0


def test_t17_duplicate_accounting_and_baselines(counts):
    rows = csv_rows(OUT / "duplicate_sensitivity.csv")
    audits = json.loads((ROOT / "data" / "audit" / "file_audit.json").read_text(encoding="utf-8"))
    type_year_extra = defaultdict(int)
    for entry in audits:
        type_year_extra[entry["type"], entry["year"]] += entry["identical_extra_rows"]
    shares = {(r["scope"], r["year"]): r for r in csv_rows(OUT / "monthly_share.csv") if r["variant"] in {"포함", "전체"}}
    trends = {(r["scope"], r["year"]): r for r in csv_rows(OUT / "campus_trend.csv")}
    for row in rows:
        assert int(row["deduplicated_rows"]) + int(row["duplicate_extra_rows"]) == int(row["original_rows"])
        if row["record_kind"] == "주택유형·연도":
            assert int(row["duplicate_extra_rows"]) == type_year_extra[row["housing_type"], int(row["year"])]
        if row["record_kind"] == "범위·연도":
            share = shares[row["scope"], row["year"]]
            assert row["original_rows"] == share["total_rows"]
            assert row["original_monthly_rows"] == share["monthly_rows"]
            assert row["original_monthly_share_pct"] == share["monthly_share_pct"]
            if row["scope"] in rentals.CAMPUS_AREAS:
                assert row["original_valid_small_monthly"] == trends[row["scope"], row["year"]]["valid_small_monthly"]


@pytest.mark.parametrize("deposit,monthly,expected", [
    (6000, 30, "신고 비대상"), (6000.01, 30, "신고 대상"), (6000, 30.01, "신고 대상"),
])
def test_t18_threshold_boundaries(deposit, monthly, expected):
    assert rentals.reporting_category({"contract_date": "2025-06-01", "deposit": deposit, "monthly": monthly}) == expected
    assert rentals.reporting_category({"contract_date": "2021-05-31", "deposit": deposit, "monthly": monthly}) == "제도 시행 전"


def test_t18_half_year_sums_to_verified_sample(counts):
    totals = defaultdict(int)
    for row in csv_rows(OUT / "report_obligation.csv"):
        assert row["reporting_category"] in {"제도 시행 전", "신고 대상", "신고 비대상"}
        totals[row["scope"], int(row["year"])] += int(row["rows"])
    for scope, area in counts["campus_areas"].items():
        for entry in area["by_year"]:
            assert totals[scope, entry["year"]] == entry["count"]


def test_t12_dorm_source_and_difference(counts):
    rows = csv_rows(OUT / "dorm_capacity.csv")
    sources = json.loads((OUT / "dorm_capacity_sources.json").read_text(encoding="utf-8"))
    assert len(rows) == 18
    assert {r["학교명"] for r in rows} == dorm.SCHOOLS
    assert {int(r["공시연도"]) for r in rows} == set(range(2021, 2027))
    assert all(r["본분교명"] == "본교" for r in rows)
    for row in rows:
        assert int(row["기숙사 밖 재학생 수"]) == int(row["재학생수"]) - int(row["수용가능인원"])
    for source in sources["raw_files"]:
        path = dorm.RAW / source["filename"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]


def test_t2_api_audit_has_no_key():
    audit = json.loads(lawd.OUT.read_text(encoding="utf-8"))
    assert audit["status"] in {"조회 완료", "키 미활성", "확인 불가"}
    assert "serviceKey" not in lawd.OUT.read_text(encoding="utf-8")
    if audit["status"] == "조회 완료":
        assert len(audit["rows"]) == 32
        assert all(row["api_rows"] >= 0 and row["csv_rows"] >= 0 for row in audit["rows"])
        assert all(row["api_rows"] == row["csv_rows"] for row in audit["rows"] if row["lawd_code"].startswith("52"))
        assert all(row["api_rows"] == 0 for row in audit["rows"] if row["lawd_code"].startswith("45"))
