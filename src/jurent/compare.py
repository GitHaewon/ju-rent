"""Reproducible evidence for the combined one-room and apartment comparisons."""

from __future__ import annotations

import csv
from pathlib import Path

from src import analyze_rentals as audit
from src.jurent import engine
from src.jurent.data import APARTMENT_PROCESSED, PROCESSED, load_processed

OUT = Path(__file__).resolve().parents[2] / "outputs" / "compare"
ONEROOM_BANDS = ((15, 25), (25, 35), (35, 45))
APARTMENT_BANDS = ((40, 65), (65, 90), (90, 132))
FIELDS = ("대학가", "주택유형", "면적구간", "기간시작", "기간끝", "환산율_pct", "건수",
          "p25_만원", "중앙값_만원", "p75_만원")


def in_band(area: float, low: int, high: int, final: bool) -> bool:
    return low <= area <= high if final else low <= area < high


def summarize(rows: list[dict], bands: tuple[tuple[int, int], ...], kinds: tuple[str, ...]) -> list[dict]:
    result = []
    for campus in audit.CAMPUS_AREAS:
        for index, (low, high) in enumerate(bands):
            for kind in kinds:
                chosen = [row for row in rows
                          if row["대학가"] == campus
                          and row["주택유형"] in (engine.ONEROOM_TYPES if kind == "oneroom" else {kind})
                          and engine.RECENT_START <= row["계약일"] <= engine.DATA_END
                          and row["계약구분"] in {"신규", "미기재"}
                          and in_band(float(row["면적"]), low, high, index == len(bands) - 1)]
                values = [engine.converted_monthly(row["보증금"], row["월세"], 5) for row in chosen]
                points = engine.quantiles(values) if values else {}
                result.append({
                    "대학가": campus, "주택유형": kind, "면적구간": f"{low}~{high}㎡",
                    "기간시작": engine.RECENT_START, "기간끝": engine.DATA_END,
                    "환산율_pct": 5, "건수": len(chosen),
                    "p25_만원": points.get("p25", ""),
                    "중앙값_만원": points.get("p50", ""),
                    "p75_만원": points.get("p75", ""),
                })
    return result


def write_outputs() -> tuple[Path, Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    destinations = (
        (OUT / "oneroom_pool_check.csv", summarize(
            load_processed(PROCESSED), ONEROOM_BANDS,
            ("detached_multiunit", "multifamily", "oneroom"),
        )),
        (OUT / "apartment_check.csv", summarize(
            load_processed(APARTMENT_PROCESSED), APARTMENT_BANDS, ("apartment",),
        )),
    )
    for path, rows in destinations:
        with path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    return destinations[0][0], destinations[1][0]


if __name__ == "__main__":
    write_outputs()
