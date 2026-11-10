"""D-034~D-037 source, pool, concentration and negotiation boundaries."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path

import pytest

from src.jurent import compare, data, engine


def make_row(*, kind="detached_multiunit", area=25, monthly=30, deposit=0,
             complex_name="", contract="신규", campus="효자동권") -> dict:
    return {"계약일": "2026-01-01", "대학가": campus, "주택유형": kind,
            "면적": area, "계약구분": contract, "보증금": deposit,
            "월세": monthly, "단지명": complex_name, "경과연수구간": "5~9년"}


def save_rows(path: Path, rows: list[dict]) -> Path:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=data.COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_processed_column_added_without_changing_old_counts():
    rows = data.load_processed()
    assert len(rows) == 26738
    assert list(rows[0])[-1] == "단지명"
    assert all(row["단지명"] == "" for row in rows if row["주택유형"] == "detached_multiunit")
    assert any(row["단지명"] for row in rows if row["주택유형"] == "apartment")
    old_bytes = io.StringIO(newline="")
    writer = csv.DictWriter(old_bytes, fieldnames=data.COLUMNS[:-1], extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    assert hashlib.sha256(old_bytes.getvalue().encode("utf-8-sig")).hexdigest() == (
        "7f1305efadb8d5bf0f6676b9537e4968437cdc93c0b0d79921e9b8eef2e1de4b"
    )
    audit = json.loads(data.PROCESSED_AUDIT.read_text(encoding="utf-8"))
    assert audit["total_rows"] == len(rows)
    assert audit["negative_age_rows"] == 320


@pytest.mark.parametrize("area,allowed", [(39.99, False), (40, True), (132, True), (132.01, False)])
def test_apartment_filter_area_edges(area, allowed):
    item = {"type": "apartment", "area": area, "deposit": 0, "monthly": 1, "tenure": "월세"}
    assert data.valid_apartment_monthly(item) is allowed
    assert not data.valid_apartment_monthly({**item, "deposit": -1})
    assert not data.valid_apartment_monthly({**item, "monthly": 0})
    assert not data.valid_apartment_monthly({**item, "monthly": float("nan")})
    assert not data.valid_apartment_monthly({**item, "tenure": "전세"})


def test_apartment_processed_audit_and_date_range():
    rows = data.load_processed(data.APARTMENT_PROCESSED)
    summary = json.loads(data.APARTMENT_AUDIT.read_text(encoding="utf-8"))
    assert list(rows[0]) == list(data.COLUMNS)
    assert len(rows) == summary["total_rows"] == 24965
    assert summary["by_year"] == {"2021": 3175, "2022": 4769, "2023": 4311,
                                  "2024": 4451, "2025": 3970, "2026": 4289}
    assert Counter(row["계약일"][:4] for row in rows) == summary["by_year"]
    assert all(row["주택유형"] == "apartment" and row["면적기준"] == "전용"
               and 40 <= float(row["면적"]) <= 132 and row["단지명"] for row in rows)
    assert all("2021-01-01" <= row["계약일"] <= "2026-10-31" for row in rows)


def test_oneroom_pool_is_both_types_and_uses_existing_area_basis():
    rows = [make_row() for _ in range(15)] + [make_row(kind="multifamily") for _ in range(15)]
    rows += [make_row(kind="officetel") for _ in range(10)]
    rows += [make_row(kind="multifamily", contract="갱신") for _ in range(10)]
    selected, step, _ = engine.select_similar(rows, "효자동권", "oneroom", 25)
    assert len(selected) == 30 and step == "기본"
    assert Counter(row["주택유형"] for row in selected) == {
        "detached_multiunit": 15, "multifamily": 15,
    }
    actual = data.load_processed()
    assert all(row["면적기준"] == ("계약" if row["주택유형"] == "detached_multiunit" else "전용")
               for row in actual if row["주택유형"] in engine.ONEROOM_TYPES)


def test_legacy_type_samples_keep_their_previous_selection_and_percentile():
    expected = {
        "detached_multiunit": (1225, "기본", 76.9,
                               {"p25": 30.83, "p50": 31.25, "p75": 36.25, "p90": 46.17}),
        "multifamily": (13, "기간 확대", None, None),
        "officetel": (130, "기본", 0.0,
                       {"p25": 54.17, "p50": 59.17, "p75": 64.17, "p90": 68.33}),
    }
    for kind, (count, step, percentile, points) in expected.items():
        result = engine.judge("효자동권", kind, 25, 500, 35)
        assert (result["n"], result["step"], result["percentile"],
                result["quantiles_10k_krw"]) == (count, step, percentile, points)


def test_apartment_below_40_does_not_calculate_and_edges_are_supported():
    result = engine.judge("효자동권", "apartment", 39.99, 500, 35)
    assert result["label"] == "제공 안 함" and result["reason"] == engine.SMALL_APARTMENT_REASON
    assert result["converted_monthly_10k_krw"] is None
    assert result["percentile"] is None and result["hint"] is None
    assert result["quantiles_10k_krw"] is None and result["histogram_10k_krw"] == []
    assert engine.judge("효자동권", "apartment", 40, 500, 35)["n"] > 0
    assert engine.judge("효자동권", "apartment", 132, 500, 35)["n"] > 0
    with pytest.raises(ValueError):
        engine.judge("효자동권", "apartment", 132.01, 500, 35)


def test_exact_half_of_all_transactions_holds_even_with_unnamed_homes(tmp_path):
    rows = [make_row(complex_name="한 단지") for _ in range(15)] + [make_row() for _ in range(15)]
    result = engine.judge("효자동권", "oneroom", 25, 0, 40,
                          data_path=save_rows(tmp_path / "half.csv", rows))
    assert result["label"] == "판단 보류"
    assert result["complex_concentration"] == {"name": "한 단지", "count": 15, "share_pct": 50.0}
    assert result["reason"] == "비교 거래 30건 중 15건이 한 단지 한 건물이에요"
    assert result["percentile"] is not None and result["quantiles_10k_krw"] is not None
    assert result["hint"] is None
    rows[14]["단지명"] = ""
    result = engine.judge("효자동권", "oneroom", 25, 0, 40,
                          data_path=save_rows(tmp_path / "below.csv", rows))
    assert result["label"] != "판단 보류"
    assert result["complex_concentration"] is None


def test_negotiation_rejudges_one_man_won_steps_and_stops_at_30(tmp_path):
    rows = ([make_row(monthly=30) for _ in range(20)]
            + [make_row(monthly=40) for _ in range(5)]
            + [make_row(monthly=50) for _ in range(5)])
    path = save_rows(tmp_path / "prices.csv", rows)
    result = engine.judge("효자동권", "oneroom", 25, 0, 40, data_path=path)
    assert result["label"] == "비싼 편"
    assert result["percentile"] == 75.0
    assert result["hint"] == {"difference_from_median_10k_krw": 10.0,
                              "monthly_reduction_10k_krw": 1}
    lower = engine.judge("효자동권", "oneroom", 25, 0, 39, data_path=path)
    assert lower["label"] == "보통"
    rows_at_30 = [make_row(monthly=30) for _ in range(30)]
    max_path = save_rows(tmp_path / "max_reduction.csv", rows_at_30)
    at_limit = engine.judge("효자동권", "oneroom", 25, 0, 60, data_path=max_path)
    assert at_limit["hint"]["monthly_reduction_10k_krw"] == 30
    result = engine.judge("효자동권", "oneroom", 25, 100_000, 50, data_path=path)
    assert result["label"] == "많이 비싼 편"
    assert result["hint"]["monthly_reduction_10k_krw"] is None


def test_evidence_outputs_keep_pools_and_area_bands_separate():
    oneroom, apartment = compare.write_outputs()
    with oneroom.open(encoding="utf-8-sig", newline="") as fh:
        pool = list(csv.DictReader(fh))
    with apartment.open(encoding="utf-8-sig", newline="") as fh:
        apartments = list(csv.DictReader(fh))
    assert len(pool) == 18 and len(apartments) == 6
    for campus in ("효자동권", "전북대권"):
        for band in ("15~25㎡", "25~35㎡", "35~45㎡"):
            group = {row["주택유형"]: int(row["건수"]) for row in pool
                     if row["대학가"] == campus and row["면적구간"] == band}
            assert group["oneroom"] == group["detached_multiunit"] + group["multifamily"]
    assert all(row["기간시작"] == engine.RECENT_START and row["기간끝"] == engine.DATA_END
               and row["환산율_pct"] == "5" for row in pool + apartments)
