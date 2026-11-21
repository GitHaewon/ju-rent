"""Freeze reviewed planned bus intervals from local, uncommitted raw responses."""

from __future__ import annotations

import csv
from pathlib import Path
from xml.etree import ElementTree as ET

from src.jurent.commute import planned_average_interval

ROOT = Path(__file__).resolve().parents[1]
GW_ROUTE_INFO = ROOT / "data/raw/bus/route_2_info.xml"
TAGO_RAW = ROOT / "data/raw/bus/tago"
OUTPUT = ROOT / "outputs/bus/route_intervals.csv"


def build() -> list[dict[str, str | int]]:
    if not GW_ROUTE_INFO.exists():
        raise FileNotFoundError(GW_ROUTE_INFO)
    rows: list[dict[str, str | int]] = []
    for row in ET.fromstring(GW_ROUTE_INFO.read_bytes()).findall(".//list"):
        route = row.findtext("brtStdid")
        if not route:
            continue
        route_id = f"JUB{route}"
        tago_path = TAGO_RAW / f"route_info_{route_id}.xml"
        if not tago_path.exists():
            continue
        tago = ET.fromstring(tago_path.read_bytes()).find(".//item")
        if tago is None or tago.findtext("routeid") != route_id:
            continue
        first, last = row.findtext("brtFirstTime"), row.findtext("brtLastTime")
        if ((first or "").zfill(4) != (tago.findtext("startvehicletime") or "").zfill(4)
                or (last or "").zfill(4) != (tago.findtext("endvehicletime") or "").zfill(4)):
            continue
        value = planned_average_interval(first, last, row.findtext("BCount"))
        if value is not None:
            rows.append({
                "route_id": route_id,
                "weekday_interval_min": value,
                "source": "전주시 GW 운행횟수 + 국토교통부 TAGO 동일방향 첫차·막차 대조",
                "as_of": "2026-11-13",
            })
    rows.sort(key=lambda item: str(item["route_id"]))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["route_id", "weekday_interval_min", "source", "as_of"])
        writer.writeheader()
        writer.writerows(rows)
    return rows


if __name__ == "__main__":
    print(f"고정 배차 간격 {len(build())}개 노선 저장")
