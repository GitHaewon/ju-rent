"""Boundary cases for the D-011 sample and D-012 monthly bins."""

import pytest

from src.analyze_rentals import (
    YEARS,
    analytic,
    area_with_basis,
    contract_label,
    monthly_bin,
)


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("apartment", (20.0, "전용")),
        ("multifamily", (20.0, "전용")),
        ("officetel", (20.0, "전용")),
        ("detached_multiunit", (30.0, "계약")),
    ],
)
def test_area_basis_follows_housing_type(kind, expected):
    row = {"전용면적(㎡)": "20", "계약면적(㎡)": "30"}
    assert area_with_basis(kind, row) == expected


@pytest.mark.parametrize(
    ("kind", "row", "basis"),
    [
        ("apartment", {"계약면적(㎡)": "30"}, "전용"),
        ("detached_multiunit", {"전용면적(㎡)": "20"}, "계약"),
    ],
)
def test_missing_required_area_does_not_fall_back(kind, row, basis):
    assert area_with_basis(kind, row) == (None, basis)


@pytest.mark.parametrize(
    ("area", "expected"),
    [(14.99, False), (15, True), (45, True), (45.01, False)],
)
def test_area_boundaries(area, expected):
    row = {
        "dong": "효자동2가",
        "area": area,
        "deposit": 0,
        "monthly": 30,
        "tenure": "월세",
    }
    assert analytic(row) is expected


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("deposit", -0.01),
        ("monthly", 0),
        ("tenure", "전세"),
        ("dong", "효자동1가"),
    ],
)
def test_other_sample_exclusions(field, value):
    row = {
        "dong": "효자동2가",
        "area": 15,
        "deposit": 0,
        "monthly": 30,
        "tenure": "월세",
    }
    row[field] = value
    assert analytic(row) is False


@pytest.mark.parametrize(
    ("monthly", "expected"),
    [
        (19.99, "under_20"),
        (20, "20_to_29"),
        (29, "20_to_29"),
        (30, "30_to_39"),
        (39.99, "30_to_39"),
        (40, "40_to_49"),
        (49.99, "40_to_49"),
        (50, "50_plus"),
    ],
)
def test_monthly_bin_lower_bounds_inclusive(monthly, expected):
    assert monthly_bin(monthly) == expected


@pytest.mark.parametrize("value", ["-", "", " - "])
def test_missing_contract_is_labeled(value):
    assert contract_label(value) == "미기재"


@pytest.mark.parametrize("value", ["신규", "갱신"])
def test_known_contract_is_preserved(value):
    assert contract_label(value) == value


@pytest.mark.parametrize("year", [2020, 2021, 2025, 2026])
def test_analysis_years(year):
    assert (year in YEARS) is (2021 <= year <= 2025)
