"""D-039~D-043 budget recommendations and campus comparisons."""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
from statistics import median

from src import analyze_rentals as audit
from src.jurent import compare, engine
from src.jurent.data import (
    AGE_BANDS,
    APARTMENT_MAX_AREA_SQM,
    APARTMENT_MIN_AREA_SQM,
    APARTMENT_PROCESSED,
    PROCESSED,
    load_processed,
)

HOUSING_TYPES = ("oneroom", "officetel", "apartment")
PRIORITIES = ("cheap", "new", "large")
OUT = Path(__file__).resolve().parents[2] / "outputs" / "compare"
AGE_ORDER = {name: index for index, name in enumerate(AGE_BANDS)}


def _rate(rate_pct: float | None) -> float:
    rate = engine.default_rate_pct() if rate_pct is None else rate_pct
    engine.converted_monthly(0, 0, rate)
    return rate


def _validate_scope(campus: str, housing: str, min_area: float) -> None:
    if campus not in audit.CAMPUS_AREAS:
        raise ValueError("Unknown campus area")
    if housing not in HOUSING_TYPES:
        raise ValueError("Unknown housing type")
    low = APARTMENT_MIN_AREA_SQM if housing == "apartment" else audit.MIN_AREA_SQM
    high = APARTMENT_MAX_AREA_SQM if housing == "apartment" else audit.MAX_AREA_SQM
    if not math.isfinite(min_area) or not low <= min_area <= high:
        raise ValueError("Minimum area outside supported range")


def _eligible_rows(campus: str, housing: str, min_area: float, start: str) -> list[dict]:
    _validate_scope(campus, housing, min_area)
    source = APARTMENT_PROCESSED if housing == "apartment" else PROCESSED
    return [
        row for row in engine.eligible_deals(load_processed(source), campus, housing, start)
        if Fraction(str(row["면적"])) >= Fraction(str(min_area))
    ]


def recent_deals(campus: str, housing: str, min_area: float) -> list[dict]:
    """Read the unchanged D-027 processed rows for D-039's recent period."""
    return _eligible_rows(campus, housing, min_area, engine.RECENT_START)


def _median(rows: list[dict], field: str) -> Fraction:
    return median(Fraction(str(row[field])) for row in rows)


def _rounded(value: Fraction) -> float:
    return round(float(value), 2)


def _price_summary(rows: list[dict], rate: float) -> dict:
    values = [engine.converted_monthly(row["보증금"], row["월세"], rate) for row in rows]
    points = engine.quantiles(values) if values else None
    return {
        "quantiles_10k_krw": {key: points[key] for key in ("p25", "p50", "p75")} if points else None,
        "deposit_median_10k_krw": _rounded(_median(rows, "보증금")) if rows else None,
        "monthly_median_10k_krw": _rounded(_median(rows, "월세")) if rows else None,
    }


def budget_search(
    campus: str, deposit: float, monthly: float, min_area: float = 15,
    housing: str | None = None, priority: str = "cheap", rate_pct: float | None = None,
) -> dict:
    """Recommend sufficiently sampled legal-dong/type/age groups within a budget."""
    if campus not in audit.CAMPUS_AREAS or (housing is not None and housing not in HOUSING_TYPES):
        raise ValueError("Unknown campus area or housing type")
    if priority not in PRIORITIES:
        raise ValueError("Unknown priority")
    if not math.isfinite(deposit) or deposit < 0:
        raise ValueError("Deposit budget must be nonnegative")
    if not math.isfinite(monthly) or monthly < 0:
        raise ValueError("Monthly budget must be nonnegative")
    if not math.isfinite(min_area) or not 15 <= min_area <= 132:
        raise ValueError("Minimum area outside supported range")
    if housing is not None:
        _validate_scope(campus, housing, min_area)
    rate = _rate(rate_pct)
    groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for kind in (housing,) if housing else HOUSING_TYPES:
        if kind != "apartment" and min_area > audit.MAX_AREA_SQM:
            continue
        kind_min_area = max(min_area, APARTMENT_MIN_AREA_SQM) if kind == "apartment" else min_area
        for row in recent_deals(campus, kind, kind_min_area):
            groups[row["법정동"], kind, row["경과연수구간"]].append(row)

    budget_deposit = Fraction(str(deposit))
    budget_monthly = Fraction(str(monthly))
    excluded = {"sample_shortage": 0, "complex_concentration": 0, "under_25_pct": 0}
    ranked = []
    for (dong, kind, age), rows in groups.items():
        n = len(rows)
        if n < engine.MIN_SAMPLE:
            excluded["sample_shortage"] += 1
            continue
        if engine.dominant_complex(rows) is not None:
            excluded["complex_concentration"] += 1
            continue
        within = sum(
            Fraction(str(row["보증금"])) <= budget_deposit
            and Fraction(str(row["월세"])) <= budget_monthly
            for row in rows
        )
        share = Fraction(within, n)
        if share < Fraction(1, 4):
            excluded["under_25_pct"] += 1
            continue
        converted_median = median(
            engine.converted_monthly(row["보증금"], row["월세"], rate) for row in rows
        )
        area_median = _median(rows, "면적")
        typical = _price_summary(rows, rate)
        result = {
            "dong": dong, "housing_type": kind, "age_band": age, "n": n,
            "within_budget_count": within, "within_budget_pct": round(float(share * 100), 2),
            "availability_label": "쉽게 구할 수 있어요" if share >= Fraction(1, 2) else "발품 팔면 가능해요",
            **typical, "area_median_sqm": _rounded(area_median),
            "typical_terms_note": "보증금과 월세 각각의 중간값이며 한 거래의 조건은 아니에요.",
        }
        primary = {"cheap": converted_median, "new": AGE_ORDER[age], "large": -area_median}[priority]
        ranked.append(((primary, -share, -n, dong, kind, AGE_ORDER[age]), result))
    ranked.sort(key=lambda pair: pair[0])
    return {
        "input": {"campus": campus, "deposit_10k_krw": deposit,
                  "monthly_10k_krw": monthly, "min_area_sqm": min_area,
                  "housing_type": housing, "priority": priority},
        "rate_pct": rate, "data_as_of": engine.DATA_END,
        "total_combinations": len(groups), "total_deals": sum(map(len, groups.values())),
        "excluded_counts": excluded,
        "recommendations": [result for _, result in ranked],
    }


def campus_compare(rate_pct: float | None = None) -> dict:
    """Return D-043 recent area bands and annual one-room price trend."""
    rate = _rate(rate_pct)
    area_bands = []
    trend = []
    for campus in audit.CAMPUS_AREAS:
        for housing in HOUSING_TYPES:
            bands = compare.APARTMENT_BANDS if housing == "apartment" else compare.ONEROOM_BANDS
            rows = recent_deals(campus, housing, bands[0][0])
            for index, (low, high) in enumerate(bands):
                chosen = [row for row in rows if compare.in_band(
                    float(row["면적"]), low, high, index == len(bands) - 1,
                )]
                area_bands.append({
                    "campus": campus, "housing_type": housing, "area_band": f"{low}~{high}㎡",
                    "period_start": engine.RECENT_START, "period_end": engine.DATA_END,
                    "n": len(chosen), "sample_note": "표본 부족" if len(chosen) < engine.MIN_SAMPLE else "",
                    **_price_summary(chosen, rate),
                })
        all_oneroom = _eligible_rows(campus, "oneroom", 25, engine.ALL_START)
        for year in range(2021, 2027):
            chosen = [row for row in all_oneroom
                      if row["계약일"].startswith(str(year))
                      and compare.in_band(float(row["면적"]), 25, 35, False)]
            values = [engine.converted_monthly(row["보증금"], row["월세"], rate) for row in chosen]
            trend.append({
                "campus": campus, "housing_type": "oneroom", "area_band": "25~35㎡",
                "year": year, "period_start": f"{year}-01-01",
                "period_end": engine.DATA_END if year == 2026 else f"{year}-12-31",
                "partial_year": year == 2026, "n": len(chosen),
                "converted_median_10k_krw": engine.quantiles(values)["p50"] if values else None,
                "sample_note": "표본 부족" if len(chosen) < engine.MIN_SAMPLE else "",
            })
    return {"rate_pct": rate, "data_as_of": engine.DATA_END,
            "area_bands": area_bands, "yearly_trend": trend}


def write_reference_outputs() -> tuple[Path, Path, Path]:
    """Persist the fixed-rate N-034~N-036 reference calculations."""
    OUT.mkdir(parents=True, exist_ok=True)
    comparison = campus_compare(5)
    bands_path = OUT / "campus_compare.csv"
    trend_path = OUT / "campus_price_trend.csv"
    band_fields = ("campus", "housing_type", "area_band", "period_start", "period_end", "n",
                   "converted_p25_10k_krw", "converted_median_10k_krw", "converted_p75_10k_krw",
                   "deposit_median_10k_krw", "monthly_median_10k_krw", "sample_note")
    band_rows = []
    for row in comparison["area_bands"]:
        points = row["quantiles_10k_krw"] or {}
        band_rows.append({**{key: row[key] for key in band_fields if key in row},
                          "converted_p25_10k_krw": points.get("p25"),
                          "converted_median_10k_krw": points.get("p50"),
                          "converted_p75_10k_krw": points.get("p75")})
    with bands_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=band_fields)
        writer.writeheader()
        writer.writerows(band_rows)
    trend_fields = ("campus", "housing_type", "area_band", "year", "period_start", "period_end",
                    "partial_year", "n", "converted_median_10k_krw", "sample_note")
    with trend_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=trend_fields)
        writer.writeheader()
        writer.writerows(comparison["yearly_trend"])
    example = {
        "criteria": {"deposit_10k_krw": 500, "monthly_10k_krw": 35,
                     "min_area_sqm": 15, "priority": "cheap", "rate_pct": 5},
        "results": {campus: budget_search(campus, 500, 35, 15, priority="cheap", rate_pct=5)
                    for campus in audit.CAMPUS_AREAS},
    }
    example_path = OUT / "budget_example.json"
    example_path.write_text(json.dumps(example, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return bands_path, trend_path, example_path


if __name__ == "__main__":
    write_reference_outputs()
