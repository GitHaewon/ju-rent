"""SPEC-004 PR-1 boundaries, grouping, sorting and API regression."""

from __future__ import annotations

import csv
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api import main
from src.jurent import area, engine

client = TestClient(main.app)


def deal(dong: str, age: str, deposit: str, monthly: str, area_sqm: str = "25",
         complex_name: str = "") -> dict:
    return {"법정동": dong, "경과연수구간": age, "보증금": deposit,
            "월세": monthly, "면적": area_sqm, "단지명": complex_name, "번지": "1"}


def patched_deals(monkeypatch, rows: list[dict]) -> None:
    monkeypatch.setattr(area, "recent_deals", lambda _campus, _housing, _minimum: rows)


def test_recent_deals_reuses_processed_period_tenure_and_apartment_bounds():
    for housing, minimum in (("oneroom", 15), ("officetel", 15), ("apartment", 40)):
        rows = area.recent_deals("효자동권", housing, minimum)
        kinds = engine.ONEROOM_TYPES if housing == "oneroom" else {housing}
        assert all(row["대학가"] == "효자동권" and row["주택유형"] in kinds
                   and row["계약구분"] in {"신규", "미기재"}
                   and engine.RECENT_START <= row["계약일"] <= engine.DATA_END
                   and Fraction(row["면적"]) >= minimum for row in rows)
        if housing == "apartment":
            assert all(40 <= Fraction(row["면적"]) <= 132 for row in rows)
    with pytest.raises(ValueError):
        area.recent_deals("효자동권", "apartment", 39.99)
    with pytest.raises(ValueError):
        area.recent_deals("효자동권", "oneroom", 45.01)


def test_recent_filter_includes_exact_period_edges_and_excludes_renewals(monkeypatch):
    rows = [
        {"대학가": "효자동권", "주택유형": "multifamily", "계약구분": "신규",
         "계약일": day, "면적": "15"}
        for day in ("2024-10-31", "2024-11-01", "2026-10-31", "2026-11-01")
    ]
    rows += [{**rows[1], "계약구분": "갱신"}, {**rows[1], "대학가": "전북대권"},
             {**rows[1], "면적": "14.99"}]
    monkeypatch.setattr(area, "load_processed", lambda _path: rows)
    chosen = area.recent_deals("효자동권", "oneroom", 15)
    assert [row["계약일"] for row in chosen] == ["2024-11-01", "2026-10-31"]


def test_exact_budget_and_25_50_percent_edges(monkeypatch):
    rows = []
    for dong, inside in (("반반동", 20), ("사분동", 10), ("미달동", 9)):
        rows += [deal(dong, "5년 미만", "500", "35") for _ in range(inside)]
        rows += [deal(dong, "5년 미만", "500.0001", "35") for _ in range(20 - inside)]
        rows += [deal(dong, "5년 미만", "500", "35.0001") for _ in range(20)]
    patched_deals(monkeypatch, rows)
    result = area.budget_search("효자동권", 500, 35, housing="oneroom")
    cards = {card["dong"]: card for card in result["recommendations"]}
    assert result["total_combinations"] == 3
    assert result["total_deals"] == 120
    assert result["excluded_counts"] == {
        "sample_shortage": 0, "complex_concentration": 0, "under_25_pct": 1,
    }
    assert cards["반반동"]["within_budget_count"] == 20
    assert cards["반반동"]["within_budget_pct"] == 50
    assert cards["반반동"]["availability_label"] == "쉽게 구할 수 있어요"
    assert cards["사분동"]["within_budget_count"] == 10
    assert cards["사분동"]["within_budget_pct"] == 25
    assert cards["사분동"]["availability_label"] == "발품 팔면 가능해요"
    assert "미달동" not in cards


def test_exclusion_counts_partition_every_combination(monkeypatch):
    rows = []
    cases = (("추천동", 30, 15, 0), ("발품동", 40, 10, 0),
             ("예산밖동", 40, 9, 0), ("적은동", 29, 29, 0),
             ("쏠림동", 40, 20, 20))
    for dong, count, inside, named in cases:
        rows += [deal(dong, "미기재", "0", "30" if i < inside else "40",
                      complex_name="한 건물" if i < named else "") for i in range(count)]
    patched_deals(monkeypatch, rows)
    result = area.budget_search("효자동권", 500, 35, housing="oneroom")
    assert result["total_combinations"] == 5
    assert result["total_deals"] == sum(item[1] for item in cases)
    assert result["excluded_counts"] == {
        "sample_shortage": 1, "complex_concentration": 1, "under_25_pct": 1,
    }
    assert sum(result["excluded_counts"].values()) + len(result["recommendations"]) == 5
    assert {card["dong"] for card in result["recommendations"]} == {"추천동", "발품동"}


def test_under_30_is_sample_shortage_even_when_one_building_has_half(monkeypatch):
    rows = [deal("적은동", "5년 미만", "500", "35",
                 complex_name="한 건물" if index < 20 else "") for index in range(29)]
    patched_deals(monkeypatch, rows)
    result = area.budget_search("효자동권", 500, 35, housing="oneroom")
    assert result["total_combinations"] == 1
    assert result["recommendations"] == []
    assert result["excluded_counts"] == {
        "sample_shortage": 1, "complex_concentration": 0, "under_25_pct": 0,
    }


@pytest.mark.parametrize(
    "priority,order", [
        ("cheap", ["큰동률동", "동률동", "작은동", "신축동"]),
        ("new", ["신축동", "큰동률동", "동률동", "작은동"]),
        ("large", ["큰동률동", "동률동", "신축동", "작은동"]),
    ],
)
def test_three_sort_orders_and_share_then_count_ties(monkeypatch, priority, order):
    rows = []
    for dong, age, size, count, inside, outside_monthly in (
        ("작은동", "5~9년", "20", 30, 15, "30"),
        ("동률동", "5~9년", "30", 30, 20, "30"),
        ("큰동률동", "5~9년", "30", 45, 30, "30"),
        ("신축동", "5년 미만", "25", 30, 15, "65"),
    ):
        rows += [deal(dong, age, "0", "35", size) for _ in range(inside)]
        rows += [deal(dong, age, "1200" if outside_monthly == "30" else "0",
                      outside_monthly, size) for _ in range(count - inside)]
    patched_deals(monkeypatch, rows)
    result = area.budget_search("효자동권", 500, 35, housing="oneroom", priority=priority)
    assert [card["dong"] for card in result["recommendations"]] == order
    assert result["excluded_counts"] == dict.fromkeys(result["excluded_counts"], 0)


def test_real_group_totals_equal_recent_deals_and_apartment_starts_at_40():
    result = area.budget_search("효자동권", 500, 35)
    assert result["total_deals"] == sum(
        len(area.recent_deals("효자동권", kind, 40 if kind == "apartment" else 15))
        for kind in area.HOUSING_TYPES
    )
    assert sum(result["excluded_counts"].values()) + len(result["recommendations"]) == result["total_combinations"]
    apartment = area.budget_search("효자동권", 500, 35, 40, housing="apartment")
    assert apartment["total_deals"] == len(area.recent_deals("효자동권", "apartment", 40))
    assert client.post("/api/budget", json={"campus": "효자동권", "deposit": 500,
                                            "monthly": 35, "housing": "apartment"}).json()["input"]["min_area_sqm"] == 40


def test_campus_compare_and_fixed_rate_outputs_are_reproducible():
    result = area.campus_compare(5)
    assert len(result["area_bands"]) == 18
    assert len(result["yearly_trend"]) == 12
    assert Counter(row["campus"] for row in result["area_bands"]) == {"효자동권": 9, "전북대권": 9}
    assert all(row["sample_note"] == ("표본 부족" if row["n"] < engine.MIN_SAMPLE else "")
               for row in result["area_bands"] + result["yearly_trend"])
    assert all(row["period_end"] == "2026-10-31" and row["partial_year"]
               for row in result["yearly_trend"] if row["year"] == 2026)
    assert all(row["period_end"].endswith("12-31") and not row["partial_year"]
               for row in result["yearly_trend"] if row["year"] < 2026)
    paths = area.write_reference_outputs()
    first = [path.read_bytes() for path in paths]
    area.write_reference_outputs()
    assert [path.read_bytes() for path in paths] == first
    with paths[0].open(encoding="utf-8-sig", newline="") as fh:
        assert len(list(csv.DictReader(fh))) == 18
    with paths[1].open(encoding="utf-8-sig", newline="") as fh:
        assert len(list(csv.DictReader(fh))) == 12
    examples = json.loads(paths[2].read_text(encoding="utf-8"))
    assert set(examples["results"]) == {"효자동권", "전북대권"}
    assert examples["results"]["효자동권"]["total_combinations"] == 21
    assert examples["results"]["전북대권"]["total_combinations"] == 21


def test_api_passthrough_and_korean_input_errors():
    payload = {"campus": "전북대권", "deposit": 500, "monthly": 35,
               "min_area": 15, "priority": "cheap", "rate_pct": 5}
    response = client.post("/api/budget", json=payload)
    assert response.status_code == 200
    assert response.json() == area.budget_search("전북대권", 500, 35, 15, priority="cheap", rate_pct=5)
    response = client.get("/api/compare", params={"rate_pct": 5})
    assert response.status_code == 200
    assert response.json() == area.campus_compare(5)
    for change in ({"deposit": -1}, {"monthly": -0.01}, {"min_area": 14.99},
                   {"min_area": 132.01}, {"housing": "apartment", "min_area": 39.99},
                   {"housing": "unknown"}, {"priority": "unknown"}, {"rate_pct": 10.01}):
        invalid = client.post("/api/budget", json={**payload, **change})
        assert invalid.status_code == 422
        assert "주세요" in invalid.json()["detail"]
    invalid_compare = client.get("/api/compare", params={"rate_pct": 1.99})
    assert invalid_compare.status_code == 422
    assert "주세요" in invalid_compare.json()["detail"]


@pytest.mark.parametrize("rate", [2, 10])
def test_conversion_rate_edges_are_allowed(rate):
    result = area.campus_compare(rate)
    assert result["rate_pct"] == rate


def test_old_judge_and_n033_keep_fixed_results():
    result = engine.judge("효자동권", "detached_multiunit", 25, 500, 35)
    assert (result["n"], result["step"], result["percentile"]) == (1225, "기본", 76.9)
    path = Path(__file__).parents[1] / "outputs" / "compare" / "small_apartment_concentration.json"
    evidence = json.loads(path.read_text(encoding="utf-8"))
    assert (evidence["갱신 포함"]["rows"], evidence["갱신 포함"]["top_complex_rows"],
            evidence["갱신 포함"]["humancia_rows"]) == (245, 98, 104)
