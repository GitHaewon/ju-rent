"""SPEC-002 PR-1 data, fixed evidence and contract judgment checks."""

import csv
import hashlib
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path

import pytest

from src import analyze_rentals as audit
from src.jurent import data, engine

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


@pytest.fixture(scope="module")
def prepared():
    audit.main()
    data.build_processed()
    return json.loads((ROOT / "data" / "audit" / "counts.json").read_text(encoding="utf-8"))


def test_n020_to_n025_fixed(prepared):
    lawd = json.loads((ROOT / "outputs" / "audit" / "lawd_code_check.json").read_text(encoding="utf-8"))
    lawd_expected = json.loads((FIXTURES / "lawd_code_check_n020.json").read_text(encoding="utf-8"))
    assert lawd["rows"] == lawd_expected["rows"]
    assert read_csv(ROOT / "outputs" / "rationale" / "dorm_capacity.csv") == read_csv(FIXTURES / "dorm_capacity_n021.csv")
    trend_expected = read_csv(FIXTURES / "campus_trend_n022.csv")
    trend = read_csv(ROOT / "outputs" / "rationale" / "campus_trend.csv")
    assert [{key: row[key] for key in trend_expected[0]} for row in trend] == trend_expected
    assert read_csv(ROOT / "outputs" / "rationale" / "monthly_share.csv") == read_csv(FIXTURES / "monthly_share_n023.csv")
    duplicate_expected = read_csv(FIXTURES / "duplicate_sensitivity_n024.csv")
    duplicate = read_csv(ROOT / "outputs" / "rationale" / "duplicate_sensitivity.csv")
    assert [
        {key: row[key] for key in duplicate_expected[0]}
        for row in duplicate if row["record_kind"] != "범위·연도·1~10월"
    ] == duplicate_expected
    assert read_csv(ROOT / "outputs" / "rationale" / "report_obligation.csv") == read_csv(
        FIXTURES / "report_obligation_n025.csv"
    )
    assert [row["rows"] for row in prepared["apartment_deokjin_top_two_all_years"]["by_year"]] == [
        43, 814, 21, 649, 1, 1508,
    ]


def test_n026_to_n028_fixed(prepared):
    assert read_csv(ROOT / "outputs" / "rationale" / "campus_trend.csv") == read_csv(
        FIXTURES / "campus_trend_n026.csv"
    )
    assert read_csv(ROOT / "outputs" / "rationale" / "duplicate_sensitivity.csv") == read_csv(
        FIXTURES / "duplicate_sensitivity_n027.csv"
    )
    expected = json.loads((FIXTURES / "valid_small_monthly_audit_n028.json").read_text(encoding="utf-8"))
    actual = json.loads(data.PROCESSED_AUDIT.read_text(encoding="utf-8"))
    assert {key: actual[key] for key in expected} == expected
    assert actual["negative_age_values"] == {"-1": 320}
    assert actual["negative_age_by_type"]["apartment"] == 318


def test_t0_new_period_outputs(prepared):
    trend = read_csv(ROOT / "outputs" / "rationale" / "campus_trend.csv")
    processed = read_csv(data.PROCESSED)
    jan_aug_valid = Counter(
        (r["대학가"], r["계약일"][:4]) for r in processed
        if r["대학가"] and int(r["계약일"][5:7]) <= 8
    )
    jan_aug_city = Counter()
    for path in sorted(data.RAW.glob("*.csv")):
        _, _, raw_rows = audit.read_csv(path)
        jan_aug_city[path.stem.rsplit("_", 1)[-1]] += sum(
            int(r["계약년월"][4:]) <= 8 for r in raw_rows
        )
    for row in trend:
        assert int(row["jan_aug_valid_small_monthly"]) <= int(row["jan_oct_valid_small_monthly"])
        assert int(row["jan_aug_city_public_rows"]) <= int(row["jan_oct_city_public_rows"])
        assert int(row["jan_aug_valid_small_monthly"]) == jan_aug_valid[row["scope"], row["year"]]
        assert int(row["jan_aug_city_public_rows"]) == jan_aug_city[row["year"]]
        if row["year"] == "2021":
            assert row["jan_aug_change_from_2021_pct"] == "0.0"
            assert row["jan_aug_city_change_from_2021_pct"] == "0.0"
    duplicate = read_csv(ROOT / "outputs" / "rationale" / "duplicate_sensitivity.csv")
    annual = {(r["scope"], r["year"]): r for r in duplicate if r["record_kind"] == "범위·연도"}
    period = [r for r in duplicate if r["record_kind"] == "범위·연도·1~10월"]
    assert len(period) == 18
    for row in period:
        assert int(row["deduplicated_rows"]) + int(row["duplicate_extra_rows"]) == int(row["original_rows"])
        assert int(row["original_rows"]) <= int(annual[row["scope"], row["year"]]["original_rows"])
        if row["year"] == "2026":
            legacy_keys = [key for key in row if key not in {
                "record_kind", "original_valid_change_from_2021_pct",
                "deduplicated_valid_change_from_2021_pct",
            }]
            assert {key: row[key] for key in legacy_keys} == {
                key: annual[row["scope"], row["year"]][key] for key in legacy_keys
            }
    hyo = {(r["year"], r["scope"]): r for r in period}
    for row in trend:
        scope = row["scope"]
        year = row["year"]
        assert int(hyo[year, scope]["original_valid_small_monthly"]) == int(row["jan_oct_valid_small_monthly"])
        baseline = int(hyo["2021", scope]["deduplicated_valid_small_monthly"])
        expected_change = round(100 * (int(hyo[year, scope]["deduplicated_valid_small_monthly"]) / baseline - 1), 2)
        assert float(hyo[year, scope]["deduplicated_valid_change_from_2021_pct"]) == expected_change


def test_reporting_start_boundary():
    row = {"deposit": 6001, "monthly": 30}
    assert audit.reporting_category({**row, "contract_date": "2021-05-31"}) == "제도 시행 전"
    assert audit.reporting_category({**row, "contract_date": "2021-06-01"}) == "신고 대상"


def test_t1_processed_filter_counts_and_columns(prepared):
    path = data.PROCESSED
    assert path.stat().st_size <= 5_000_000
    rows = read_csv(path)
    assert set(rows[0]) == set(data.COLUMNS)
    assert all(15 <= float(row["면적"]) <= 45 and float(row["보증금"]) >= 0
               and float(row["월세"]) > 0 for row in rows)
    assert all(row["계약구분"] in {"신규", "갱신", "미기재"} for row in rows)
    assert all(row["면적기준"] == ("계약" if row["주택유형"] == "detached_multiunit" else "전용")
               for row in rows)
    actual = Counter(row["계약일"][:4] for row in rows if row["대학가"] == "효자동권")
    assert [actual[str(year)] for year in range(2021, 2027)] == [921, 1123, 1044, 1219, 1492, 1318]
    assert all(row["경과연수구간"] in data.AGE_BANDS for row in rows)
    assert all(row["완전중복여부"] in {"true", "false"} for row in rows)
    summary = json.loads(data.PROCESSED_AUDIT.read_text(encoding="utf-8"))
    assert summary["total_rows"] == len(rows)
    assert summary["processed_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert summary["negative_age_rows"] == sum(row["경과연수"] != "" and int(row["경과연수"]) < 0 for row in rows)
    assert all(row["incomplete_recent"] == str(row["계약일"][:7] in {"2026-09", "2026-10"}).lower()
               for row in rows)


@pytest.mark.parametrize("age,expected", [(None, "미기재"), (4, "5년 미만"), (5, "5~9년"),
                                           (9, "5~9년"), (10, "10~19년"), (19, "10~19년"),
                                           (20, "20년 이상")])
def test_age_band_boundaries(age, expected):
    assert data.age_band(age) == expected


def test_d031_minus_one_age_band():
    assert data.age_band(-1) == "5년 미만"


def test_t2_conversion_rate_and_limits(prepared):
    assert engine.default_rate_pct() == 5.0
    assert round(float(engine.converted_monthly(500, 35, 5)), 2) == 37.08
    for invalid in (1.99, 10.01):
        with pytest.raises(ValueError):
            engine.converted_monthly(500, 35, invalid)
        with pytest.raises(ValueError):
            engine.judge("효자동권", "detached_multiunit", 25, 500, 35, rate_pct=invalid)
    assert engine.judge("효자동권", "detached_multiunit", 25, 500, 35, rate_pct=2)["rate_pct"] == 2
    assert engine.judge("효자동권", "detached_multiunit", 25, 500, 35, rate_pct=10)["rate_pct"] == 10
    assert engine.judge("효자동권", "detached_multiunit", 25, 500, 35)["rate_basis"]["base_rate_date"] == "2026-10-22"


def similar_row(date_text="2026-01-01", area=25, contract="신규", kind="detached_multiunit"):
    return {"계약일": date_text, "대학가": "효자동권", "법정동": "효자동2가",
            "주택유형": kind, "면적": str(area), "계약구분": contract}


def test_t3_expansion_order_and_contract_type_exclusions():
    rows = [similar_row() for _ in range(29)]
    rows += [similar_row(area=35)]
    rows += [similar_row(contract="갱신") for _ in range(10)]
    rows += [similar_row(kind="apartment") for _ in range(10)]
    selected, step, start = engine.select_similar(rows, "효자동권", "detached_multiunit", 25)
    assert (len(selected), step, start) == (30, "면적 ±10㎡", engine.RECENT_START)
    selected, step, start = engine.select_similar(rows[:29] + [similar_row(date_text="2022-01-01")],
                                                   "효자동권", "detached_multiunit", 25)
    assert (len(selected), step, start) == (30, "기간 확대", engine.ALL_START)
    selected, step, _ = engine.select_similar(rows[:29], "효자동권", "detached_multiunit", 25)
    assert (len(selected), step) == (29, "기간 확대")


def test_t3_area_date_and_campus_boundaries():
    rows = [similar_row(date_text="2024-11-01", area=30) for _ in range(30)]
    rows += [similar_row(date_text="2024-10-31", area=25)]
    rows += [similar_row(date_text="2024-11-01", area=30.01)]
    rows += [{**similar_row(), "대학가": "전북대권"}]
    selected, step, start = engine.select_similar(rows, "효자동권", "detached_multiunit", 25)
    assert (len(selected), step, start) == (30, "기본", "2024-11-01")


def test_fractional_area_expansion_boundaries():
    rows = [similar_row(area=29.7) for _ in range(30)]
    rows += [similar_row(area=29.69)]
    selected, step, _ = engine.select_similar(rows, "효자동권", "detached_multiunit", 34.7)
    assert (len(selected), step) == (30, "기본")
    assert all(row["면적"] == "29.7" for row in selected)
    rows = [similar_row(area=34.7) for _ in range(29)] + [similar_row(area=24.7)]
    selected, step, _ = engine.select_similar(rows, "효자동권", "detached_multiunit", 34.7)
    assert (len(selected), step) == (30, "면적 ±10㎡")


def test_t4_tie_rank_label_boundaries_and_linear_quantiles():
    assert engine.percentile_rank(30, [20, 30, 30, 40]) == 50.0
    assert [engine.label_for_percentile(value) for value in (24.999, 25, 75, 75.001, 90, 90.001)] == [
        "저렴한 편", "보통", "비싼 편", "비싼 편", "많이 비싼 편", "많이 비싼 편",
    ]
    assert [engine.label_for_percentile(Fraction(value)) for value in (25, 75, 90)] == [
        "보통", "비싼 편", "많이 비싼 편",
    ]
    assert engine.quantiles([0, 10, 20, 30]) == {"p25": 7.5, "p50": 15.0, "p75": 22.5, "p90": 27.0}


@pytest.mark.parametrize("rate,first,second", [
    (5, (500, 45), (6500, 20)),
    (2, (500, 45), (6500, 35)),
    (10, (500, 65), (6500, 15)),
])
def test_distinct_deposits_exactly_tie(rate, first, second):
    left = engine.converted_monthly(*first, rate)
    right = engine.converted_monthly(*second, rate)
    assert isinstance(left, Fraction) and left == right
    assert engine.percentile_rank(right, [left, right]) == Fraction(50)


def test_judge_exact_tie_with_different_source_amounts(tmp_path: Path):
    path = tmp_path / "tied.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=data.COLUMNS)
        writer.writeheader()
        for deposit, monthly in [(500, 45)] * 15 + [(6500, 20)] * 15:
            writer.writerow({"계약일": "2026-01-01", "대학가": "효자동권",
                             "주택유형": "detached_multiunit", "면적": 42,
                             "계약구분": "신규", "보증금": deposit, "월세": monthly,
                             "경과연수구간": "5~9년"})
    result = engine.judge("효자동권", "detached_multiunit", 42, 6500, 20,
                          construction_year=2020, rate_pct=5, data_path=path)
    assert result["percentile"] == 50.0 and result["label"] == "보통"
    assert result["age_band_result"]["percentile"] == 50.0


@pytest.mark.parametrize("area,deposit,monthly,expected_rank,expected_label", [
    (42, 6500, 20, 65.54, "보통"),
    (35, 6500, 25, 91.13, "많이 비싼 편"),
    (33, 6500, 15, 76.28, "비싼 편"),
])
def test_reviewed_real_sample_judgments(prepared, area, deposit, monthly, expected_rank, expected_label):
    result = engine.judge("효자동권", "detached_multiunit", area, deposit, monthly)
    assert result["percentile"] == expected_rank
    assert result["label"] == expected_label


def test_t5_result_json_and_age_band_shortage(prepared):
    result = engine.judge("효자동권", "detached_multiunit", 25, 500, 35, construction_year=2020)
    json.dumps(result, ensure_ascii=False)
    assert result["converted_monthly_10k_krw"] == 37.08
    assert result["n"] >= engine.MIN_SAMPLE and result["comparison_period"]["start"] == engine.RECENT_START
    assert result["age_band_result"]["band"] == "5~9년"
    assert len(result["warnings"]) >= 3
    assert result["data_as_of"] == "2026-10-31"


@pytest.mark.parametrize("area", [14.99, 45.01])
def test_input_area_outside_d011_rejected(area):
    with pytest.raises(ValueError):
        engine.judge("효자동권", "apartment", area, 500, 35)


def test_t5_insufficient_sample_returns_no_judgment(tmp_path: Path):
    path = tmp_path / "few.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=data.COLUMNS)
        writer.writeheader()
        writer.writerow({"계약일": "2026-01-01", "대학가": "효자동권", "주택유형": "apartment",
                         "면적": 25, "계약구분": "신규", "보증금": 500, "월세": 35})
    result = engine.judge("효자동권", "apartment", 25, 500, 35, data_path=path)
    assert result["n"] == 1 and result["step"] == "기간 확대"
    assert result["label"] == "표본 부족" and result["percentile"] is None
    assert result["quantiles_10k_krw"] is None
