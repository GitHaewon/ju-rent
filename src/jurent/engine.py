"""D-026~D-029 contract comparison calculations, independent of the UI."""

from __future__ import annotations

import math
import tomllib
from fractions import Fraction
from functools import lru_cache
from pathlib import Path

import numpy as np

from src import analyze_rentals as audit
from src.jurent.data import PROCESSED, age_band, load_processed

ROOT = Path(__file__).resolve().parents[2]
SETTINGS = ROOT / "config" / "settings.toml"
RECENT_START = "2024-11-01"
ALL_START = "2021-01-01"
DATA_END = "2026-10-31"
MIN_SAMPLE = 30
WARNINGS = [
    "실거래 자료에는 관리비가 포함되지 않습니다.",
    "대학가 법정동 범위는 캠퍼스 도보권의 대리범위입니다.",
    "실거래는 과거 계약이며 현재 공실·호가가 아닙니다.",
    "2026년 최근 2개월은 신고 미반영으로 불완전할 수 있습니다.",
]


@lru_cache(maxsize=1)
def settings() -> dict:
    with SETTINGS.open("rb") as fh:
        return tomllib.load(fh)["rent_conversion"]


def default_rate_pct(config: dict | None = None) -> float:
    values = config or settings()
    return min(values["legal_cap_pct"], values["base_rate_pct"] + values["legal_spread_pct"])


def converted_monthly(
    deposit: float | str, monthly: float | str, rate_pct: float | str,
) -> Fraction:
    """Return an exact comparable monthly amount in ten-thousand KRW."""
    try:
        exact_deposit = Fraction(str(deposit))
        exact_monthly = Fraction(str(monthly))
        exact_rate = Fraction(str(rate_pct))
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("Amounts and rate must be finite numbers") from exc
    if exact_deposit < 0 or exact_monthly < 0:
        raise ValueError("Amounts must be nonnegative")
    config = settings()
    if not Fraction(str(config["user_min_pct"])) <= exact_rate <= Fraction(str(config["user_max_pct"])):
        raise ValueError("Conversion rate outside allowed range")
    return exact_monthly + exact_deposit * exact_rate / 1200


def percentile_rank(value: Fraction, values: list[Fraction]) -> Fraction:
    if not values:
        raise ValueError("Comparison sample is empty")
    return Fraction(100, len(values)) * (
        sum(item < value for item in values) + Fraction(sum(item == value for item in values), 2)
    )


def label_for_percentile(percentile: Fraction | float) -> str:
    if percentile < 25:
        return "저렴한 편"
    if percentile < 75:
        return "보통"
    if percentile < 90:
        return "비싼 편"
    return "많이 비싼 편"


def select_similar(rows: list[dict], campus: str, housing_type: str, area: float) -> tuple[list[dict], str, str]:
    """Apply D-028 expansions in order; preserve all NO-only duplicate rows."""
    same_group = [
        row for row in rows
        if row["대학가"] == campus and row["주택유형"] == housing_type
        and row["계약구분"] in {"신규", "미기재"}
        and ALL_START <= row["계약일"] <= DATA_END
    ]
    steps = (("기본", 5, RECENT_START), ("면적 ±10㎡", 10, RECENT_START),
             ("기간 확대", 10, ALL_START))
    exact_area = Fraction(str(area))
    for name, tolerance, start in steps:
        selected = [
            row for row in same_group
            if row["계약일"] >= start
            and abs(Fraction(str(row["면적"])) - exact_area) <= tolerance
        ]
        if len(selected) >= MIN_SAMPLE or name == "기간 확대":
            return selected, name, start
    raise AssertionError("Unreachable expansion state")


def quantiles(values: list[Fraction]) -> dict[str, float]:
    points = np.percentile([float(value) for value in values], [25, 50, 75, 90], method="linear")
    return dict(zip(("p25", "p50", "p75", "p90"), (round(float(v), 2) for v in points), strict=True))


def judge(
    campus: str,
    housing_type: str,
    area: float,
    deposit: float,
    monthly: float,
    construction_year: int | None = None,
    rate_pct: float | None = None,
    data_path: Path = PROCESSED,
) -> dict:
    """Return the complete UI-ready contract judgment without any LLM input."""
    config = settings()
    if campus not in audit.CAMPUS_AREAS or housing_type not in audit.TYPES.values():
        raise ValueError("Unknown campus area or housing type")
    if not math.isfinite(area) or not audit.MIN_AREA_SQM <= area <= audit.MAX_AREA_SQM:
        raise ValueError("Area is outside the D-011 sample range")
    if not math.isfinite(deposit) or deposit < 0 or not math.isfinite(monthly) or monthly <= 0:
        raise ValueError("Deposit must be nonnegative and monthly rent positive")
    if construction_year is not None and (
        isinstance(construction_year, bool) or not isinstance(construction_year, int)
        or not 1800 <= construction_year <= 2026
    ):
        raise ValueError("Invalid construction year")
    applied_rate = default_rate_pct(config) if rate_pct is None else rate_pct
    if not math.isfinite(applied_rate) or not config["user_min_pct"] <= applied_rate <= config["user_max_pct"]:
        raise ValueError("Conversion rate outside allowed range")
    amount = converted_monthly(deposit, monthly, applied_rate)
    selected, step, start = select_similar(load_processed(data_path), campus, housing_type, area)
    values = [converted_monthly(r["보증금"], r["월세"], applied_rate) for r in selected]
    sufficient = len(values) >= MIN_SAMPLE
    rank = percentile_rank(amount, values) if sufficient else None
    input_band = age_band(2026 - construction_year) if construction_year is not None else None
    band_rows = [r for r in selected if r["경과연수구간"] == input_band] if input_band else []
    band_values = [converted_monthly(r["보증금"], r["월세"], applied_rate) for r in band_rows]
    band_rank = percentile_rank(amount, band_values) if len(band_values) >= MIN_SAMPLE else None
    histogram_counts, histogram_edges = np.histogram(
        [float(value) for value in values], bins=20,
    ) if values else ([], [])
    return {
        "input": {
            "campus": campus, "housing_type": housing_type, "area_sqm": area,
            "deposit_10k_krw": deposit, "monthly_10k_krw": monthly,
            "construction_year": construction_year,
        },
        "rate_pct": applied_rate,
        "rate_basis": {"base_rate_pct": config["base_rate_pct"],
                       "base_rate_date": config["base_rate_date"],
                       "legal_spread_pct": config["legal_spread_pct"],
                       "legal_cap_pct": config["legal_cap_pct"],
                       "basis_note": "법정 전환율 상한을 비교 기준으로 사용하며 시장 전환율이 아닙니다."},
        "converted_monthly_10k_krw": round(float(amount), 2),
        "n": len(selected), "step": step,
        "comparison_period": {"start": start, "end": DATA_END},
        "quantiles_10k_krw": quantiles(values) if sufficient else None,
        "histogram_10k_krw": [
            {"left": round(float(left), 2), "right": round(float(right), 2), "count": int(count)}
            for left, right, count in zip(histogram_edges[:-1], histogram_edges[1:], histogram_counts, strict=True)
        ],
        "percentile": round(float(rank), 2) if rank is not None else None,
        "label": label_for_percentile(rank) if rank is not None else "표본 부족",
        "age_band_result": {
            "band": input_band, "n": len(band_rows),
            "percentile": round(float(band_rank), 2) if band_rank is not None else None,
            "label": label_for_percentile(band_rank) if band_rank is not None else "표본 부족",
        } if input_band else None,
        "warnings": WARNINGS.copy(), "data_as_of": DATA_END,
    }
