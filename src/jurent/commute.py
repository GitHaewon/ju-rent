"""Read the reviewed SPEC-005 bus access table for product features."""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

from src import analyze_rentals as audit

ROOT = Path(__file__).resolve().parents[2]
ACCESS = ROOT / "outputs/bus/commute_access.csv"
STOPS = ROOT / "outputs/bus/stops_by_dong.csv"
CAMPUS_STOPS = ROOT / "outputs/bus/campus_stops_candidates.csv"
SCHOOLS_BY_CAMPUS = {
    "효자동권": ("전주대학교", "전주비전대학교"),
    "전북대권": ("전북대학교",),
}


def choose_school(campus: str, school: str | None = None) -> str:
    if campus not in audit.CAMPUS_AREAS:
        raise ValueError("Unknown campus area")
    choices = SCHOOLS_BY_CAMPUS[campus]
    selected = choices[0] if school is None else school
    if selected not in choices:
        raise ValueError("Unknown school for campus area")
    return selected


@lru_cache(maxsize=1)
def access_by_school() -> dict[str, tuple[dict, ...]]:
    with ACCESS.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    with STOPS.open(encoding="utf-8", newline="") as handle:
        dong_by_stop = {row["stop_id"]: row["emd_cd"] for row in csv.DictReader(handle)}
    with CAMPUS_STOPS.open(encoding="utf-8", newline="") as handle:
        adjacent = {
            (row["campus"], dong_by_stop[row["stop_id"]])
            for row in csv.DictReader(handle)
            if row["status"] == "확정" and dong_by_stop.get(row["stop_id"])
        }
    result = {}
    for school in {name for choices in SCHOOLS_BY_CAMPUS.values() for name in choices}:
        selected = []
        for row in rows:
            if row["campus"] != school:
                continue
            interval = row["weekday_interval_min"]
            selected.append({
                "dong": row["emd_nm"],
                "emd_cd": row["emd_cd"],
                "campus_area": row["campus_area"] == "캠퍼스 주변",
                "campus_adjacent": (school, row["emd_cd"]) in adjacent and row["campus_area"] != "캠퍼스 주변",
                "min_stops": int(row["min_stop_count"]),
                "median_stops": float(row["median_stops"]),
                "boarding_stops": int(row["boarding_stops"]),
                "direct_routes": int(row["direct_route_count"]),
                "interval_min": None if interval == "배차 정보 없음" else int(interval),
            })
        result[school] = tuple(sorted(
            selected, key=lambda item: (item["campus_area"] is False, item["min_stops"],
                                        item["median_stops"], item["emd_cd"]),
        ))
    return result


def commute_rows(campus: str, school: str | None = None, include_campus: bool = False) -> list[dict]:
    selected = choose_school(campus, school)
    return [
        row for row in access_by_school()[selected]
        if include_campus or not row["campus_area"]
    ]


def commute_by_dong(campus: str, school: str | None = None) -> dict[str, dict]:
    return {row["dong"]: row for row in commute_rows(campus, school, include_campus=True)}
