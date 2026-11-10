"""Reproducible evidence for the combined one-room and apartment comparisons."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from src import analyze_rentals as audit
from src.jurent import engine
from src.jurent.data import APARTMENT_PROCESSED, PROCESSED, load_processed

OUT = Path(__file__).resolve().parents[2] / "outputs" / "compare"
ONEROOM_BANDS = ((15, 25), (25, 35), (35, 45))
APARTMENT_BANDS = ((40, 65), (65, 90), (90, 132))
FIELDS = ("대학가", "주택유형", "면적구간", "기간시작", "기간끝", "환산율_pct", "건수",
          "p25_만원", "중앙값_만원", "p75_만원", "sample_note")
SMALL_APARTMENT_EVIDENCE = OUT / "small_apartment_concentration.json"


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
                    "sample_note": "표본 부족" if len(chosen) < engine.MIN_SAMPLE else "",
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
    write_small_apartment_evidence()
    return destinations[0][0], destinations[1][0]


def write_small_apartment_evidence() -> Path:
    """Reproduce both renewal definitions behind D-034 from the D-011 table."""
    eligible = [
        row for row in load_processed(PROCESSED)
        if row["대학가"] in audit.CAMPUS_AREAS
        and row["주택유형"] == "apartment"
        and engine.RECENT_START <= row["계약일"] <= engine.DATA_END
        and 15 <= float(row["면적"]) <= 45
    ]
    variants = {}
    for label, rows in (
        ("갱신 포함", eligible),
        ("갱신 제외", [row for row in eligible if row["계약구분"] != "갱신"]),
    ):
        counts = Counter(row["단지명"] for row in rows if row["단지명"])
        top_name, top_count = min(counts.items(), key=lambda item: (-item[1], item[0]))
        humancia = {name: count for name, count in sorted(counts.items()) if "휴먼시아" in name}
        variants[label] = {
            "rows": len(rows), "top_complex": top_name, "top_complex_rows": top_count,
            "humancia_complexes": humancia, "humancia_rows": sum(humancia.values()),
        }
    OUT.mkdir(parents=True, exist_ok=True)
    SMALL_APARTMENT_EVIDENCE.write_text(
        json.dumps(variants, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    return SMALL_APARTMENT_EVIDENCE


if __name__ == "__main__":
    write_outputs()
