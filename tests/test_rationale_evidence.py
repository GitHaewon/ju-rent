"""Regression and cross-output checks for SPEC-001 PR-3."""

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import pytest

from src import analyze_rentals as rentals
from src import build_single_households as households

ROOT = Path(__file__).resolve().parents[1]


def csv_rows(filename):
    with (ROOT / "outputs" / "rationale" / filename).open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


@pytest.fixture(scope="module")
def counts():
    rentals.main()
    households.main()
    return json.loads((ROOT / "data" / "audit" / "counts.json").read_text(encoding="utf-8"))


def test_d017_mapping_exact_and_gu_scoped():
    assert rentals.CAMPUS_AREAS == {
        "효자동권": {"gu": "wansan", "dongs": ("효자동2가", "효자동3가")},
        "전북대권": {"gu": "deokjin", "dongs": ("덕진동1가", "금암동")},
    }
    assert rentals.campus_area_of({"gu": "deokjin", "dong": "금암동"}) == "전북대권"
    assert rentals.campus_area_of({"gu": "wansan", "dong": "금암동"}) is None
    assert rentals.campus_area_of({"gu": "deokjin", "dong": "팔복동1가"}) is None


def test_t14_campus_counts_match_verified_candidate_rows(counts):
    candidate_rows = csv_rows("../campus_dong_candidates.csv")
    for scope, area in counts["campus_areas"].items():
        assert area["total_valid_small_monthly"] == sum(entry["count"] for entry in area["by_year"])
        assert area["total_valid_small_monthly"] == sum(area["by_type"].values())
        for entry in area["by_year"]:
            assert entry["count"] == sum(entry["by_type"].values())
            matches = [
                row for row in candidate_rows
                if row["대학가"] == scope and row["후보_법정동"] in area["dongs"]
                and int(row["연도"]) == entry["year"]
            ]
            assert len(matches) == len(area["dongs"])
            assert entry["count"] == sum(int(row["유효_표본_수"]) for row in matches)
        addresses = area["address_concentration"]
        assert addresses["address_present_rows"] + addresses["address_missing_rows"] == area["total_valid_small_monthly"]
        assert addresses["top3_rows"] == sum(item["count"] for item in addresses["top3"])
        assert len(addresses["top3"]) == 3
    assert [entry["count"] for entry in counts["campus_areas"]["효자동권"]["by_year"][:5]] == [
        921, 1123, 1044, 1219, 1492,
    ]
    assert counts["campus_areas"]["효자동권"]["by_year"][-1]["count"] == 1318


def test_t9_city_totals_and_n013_exclusion(counts):
    rows = csv_rows("monthly_share.csv")
    city = {(int(row["year"]), row["variant"]): row for row in rows if row["scope"] == "완산·덕진 전체"}
    baseline_year_totals = defaultdict(int)
    for entry in counts["year_gu"]:
        baseline_year_totals[entry["year"]] += entry["count"]
    for year in rentals.YEARS:
        included = city[(year, "포함")]
        excluded = city[(year, "상위 두 단지 제외")]
        expected = counts["year_2026"]["total"] if year == 2026 else baseline_year_totals[year]
        assert int(included["total_rows"]) == expected
        assert int(included["monthly_rows"]) <= expected
        assert included["partial_year"] == str(year == 2026).lower()
        expected_exclusion = counts["apartment_deokjin_2026_april"]["top_two_complexes_rows"] if year == 2026 else 0
        assert int(included["total_rows"]) - int(excluded["total_rows"]) == expected_exclusion
    assert counts["apartment_deokjin_2026_april"]["top_two_complexes_rows"] == 1500


def test_t10_matches_verified_n002_n004_and_t14(counts):
    rows = csv_rows("campus_trend.csv")
    verified_city = [21256, 23666, 21083, 19594, 18545, 15217]
    verified_hyo = [921, 1123, 1044, 1219, 1492, 1318]
    for scope in rentals.CAMPUS_AREAS:
        subset = [row for row in rows if row["scope"] == scope]
        assert len(subset) == len(verified_city)
        assert [int(row["city_public_rows"]) for row in subset] == verified_city
        assert [int(row["valid_small_monthly"]) for row in subset] == [
            entry["count"] for entry in counts["campus_areas"][scope]["by_year"]
        ]
        assert subset[0]["change_from_2021_pct"] == "0.0"
    assert [int(row["valid_small_monthly"]) for row in rows if row["scope"] == "효자동권"] == verified_hyo


def test_t11_official_zip_hashes_and_20s_totals(counts):
    rows = csv_rows("single_households.csv")
    metadata = json.loads((ROOT / "outputs" / "rationale" / "single_households_sources.json").read_text(encoding="utf-8"))
    assert metadata["table_id"] == "DT_1PL1502"
    assert len(rows) == len(metadata["raw_files"]) == 5
    for row, source in zip(rows, metadata["raw_files"], strict=True):
        assert int(row["year"]) == source["year"]
        assert row["region"] == "전주시" and row["region_code"] == "35010"
        assert int(row["age_20s_total"]) == int(row["age_20_to_24"]) + int(row["age_25_to_29"])
        path = ROOT / "data" / "raw" / "kosis" / source["filename"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]
    assert [int(row["age_20s_total"]) for row in rows] == [23511, 22249, 22723, 21739, 21781]
