"""Collect only TAGO routes serving provisional campus stop candidates."""

import csv
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

from src.fetch_tago_bus import fetch_raw

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "outputs/bus/campus_stops_candidates.csv"
DISCOVERY = ROOT / "data/audit/bus_route_discovery.json"
ROUTE_STOPS_AUDIT = ROOT / "data/audit/bus_route_stops_audit.json"
DIRECT_PRELIM = ROOT / "data/audit/bus_direct_options_preliminary.json"
ROUTE_INFO_AUDIT = ROOT / "data/audit/bus_route_info_audit.json"
CITY_CODE = "35010"
PAGE_SIZE = "1000"


def response_items(raw):
    root = ET.fromstring(raw)
    code = root.findtext(".//resultCode")
    items = root.findall(".//item")
    total = int(root.findtext(".//totalCount") or 0)
    if code not in {"00", "03"}:
        raise ValueError(f"TAGO resultCode={code}")
    if total > len(items):
        raise ValueError("TAGO response was paginated despite requested page size")
    return items


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def collect_stop_routes():
    candidates = list(csv.DictReader(CANDIDATES.open(encoding="utf-8", newline="")))
    stop_ids = sorted({row["stop_id"] for row in candidates})
    route_ids = set()
    empty_stops = []
    calls = 0
    with httpx.Client(timeout=45) as client:
        for index, stop_id in enumerate(stop_ids, 1):
            raw, _, cached = fetch_raw(
                "stop_routes",
                f"stop_routes_{stop_id}",
                {"cityCode": CITY_CODE, "nodeid": stop_id, "numOfRows": PAGE_SIZE, "pageNo": "1"},
                get=client.get,
            )
            calls += not cached
            items = response_items(raw)
            if not items:
                empty_stops.append(stop_id)
            route_ids.update(item.findtext("routeid") for item in items if item.findtext("routeid"))
            if index % 20 == 0 or index == len(stop_ids):
                print(f"stop routes {index}/{len(stop_ids)}; new API calls {calls}", flush=True)
    data = {"candidate_stop_count": len(stop_ids), "route_ids": sorted(route_ids), "route_variant_count": len(route_ids), "stops_without_routes": empty_stops, "new_api_calls": calls}
    write_json(DISCOVERY, data)
    return data


def collect_route_stops():
    route_ids = json.loads(DISCOVERY.read_text(encoding="utf-8"))["route_ids"]
    empty_routes = []
    calls = 0
    with httpx.Client(timeout=45) as client:
        for index, route_id in enumerate(route_ids, 1):
            raw, _, cached = fetch_raw(
                "route_stops",
                f"route_stops_{route_id}",
                {"cityCode": CITY_CODE, "routeId": route_id, "numOfRows": PAGE_SIZE, "pageNo": "1"},
                get=client.get,
            )
            calls += not cached
            items = response_items(raw)
            if not items:
                empty_routes.append(route_id)
            for item in items:
                if not item.findtext("nodeid") or not item.findtext("nodeord"):
                    raise ValueError(f"Route stop lacks node ID or order: {route_id}")
            if index % 20 == 0 or index == len(route_ids):
                print(f"route stops {index}/{len(route_ids)}; new API calls {calls}", flush=True)
    data = {"route_variant_count": len(route_ids), "routes_without_stops": empty_routes, "new_api_calls": calls}
    write_json(ROUTE_STOPS_AUDIT, data)
    return data


def collect_route_info():
    route_ids = json.loads(DIRECT_PRELIM.read_text(encoding="utf-8"))["direct_route_ids"]
    missing_intervals = []
    calls = 0
    with httpx.Client(timeout=45) as client:
        for index, route_id in enumerate(route_ids, 1):
            raw, _, cached = fetch_raw(
                "route_info",
                f"route_info_{route_id}",
                {"cityCode": CITY_CODE, "routeId": route_id},
                get=client.get,
            )
            calls += not cached
            items = response_items(raw)
            if len(items) != 1:
                raise ValueError(f"Expected one route-info item: {route_id}")
            interval = items[0].findtext("intervaltime")
            if not interval or not interval.strip() or float(interval) <= 0:
                missing_intervals.append(route_id)
            if index % 20 == 0 or index == len(route_ids):
                print(f"route info {index}/{len(route_ids)}; new API calls {calls}", flush=True)
    data = {"direct_route_variant_count": len(route_ids), "routes_without_valid_interval": missing_intervals, "new_api_calls": calls}
    write_json(ROUTE_INFO_AUDIT, data)
    return data


def main():
    actions = {"stop_routes": collect_stop_routes, "route_stops": collect_route_stops, "route_info": collect_route_info}
    if len(sys.argv) != 2 or sys.argv[1] not in actions:
        raise SystemExit("Usage: collect_tago_routes.py stop_routes|route_stops|route_info")
    result = actions[sys.argv[1]]()
    print(json.dumps({key: value for key, value in result.items() if not isinstance(value, list)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
