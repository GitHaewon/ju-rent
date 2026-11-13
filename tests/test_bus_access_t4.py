"""Check direction, 20-stop inclusion, minimum, and route aggregation."""

import csv
import json
import statistics
import xml.etree.ElementTree as ET

from src import build_bus_access as bus


def test_direction_and_exact_20_stop_limit():
    dong = {"origin": "52111137"}
    campus = {"전주대학교": {"campus"}}
    at_limit = ["origin", *[f"mid{i}" for i in range(19)], "campus"]
    past_limit = ["origin", *[f"mid{i}" for i in range(20)], "campus"]
    options = bus.direct_options("route1", "100", at_limit, dong, campus)
    assert [(row["emd_cd"], row["stop_count"]) for row in options] == [("52111137", 20)]
    assert bus.direct_options("route1", "100", past_limit, dong, campus) == []
    assert bus.direct_options("route1", "100", ["campus", "origin"], dong, campus) == []


def test_same_route_multiple_origin_stops_uses_minimum():
    options = bus.direct_options(
        "route1",
        "100",
        ["far", "mid", "near", "campus"],
        {"far": "52111137", "near": "52111137"},
        {"전주대학교": {"campus"}},
    )
    assert len(options) == 1
    assert options[0]["stop_count"] == 1
    assert options[0]["origin_stop_id"] == "near"


def test_missing_interval_is_not_presented_as_shortest():
    options = [
        {"campus": "전주대학교", "emd_cd": "52111137", "route_id": "a", "route_no": "100", "stop_count": 3, "origin_stop_id": "one", "campus_stop_id": "school"},
        {"campus": "전주대학교", "emd_cd": "52111137", "route_id": "b", "route_no": "100", "stop_count": 2, "origin_stop_id": "two", "campus_stop_id": "school"},
        {"campus": "전주대학교", "emd_cd": "52111137", "route_id": "c", "route_no": "200", "stop_count": 4, "origin_stop_id": "three", "campus_stop_id": "school"},
    ]
    details = {"52111137": {"emd_nm": "삼천동1가", "gu": "완산구"}}
    boarding = [
        {"campus": "전주대학교", "emd_cd": "52111137", "origin_stop_id": "two", "stop_count": 2},
        {"campus": "전주대학교", "emd_cd": "52111137", "origin_stop_id": "one", "stop_count": 3},
        {"campus": "전주대학교", "emd_cd": "52111137", "origin_stop_id": "three", "stop_count": 4},
    ]
    row = bus.aggregate_commute(options, {"a": 15, "b": None, "c": 25}, details, boarding)[0]
    assert row["min_stop_count"] == 2
    assert row["median_stops"] == 3
    assert row["boarding_stops"] == 3
    assert row["direct_route_count"] == 2
    assert row["weekday_interval_min"] == "배차 정보 없음"
    assert row["known_min_interval_min"] == 15
    assert row["interval_status"] == "일부 노선 미기재"
    assert row["routes_missing_interval"] == "b"


def test_boarding_stop_median_even_and_over_20_does_not_change_eligibility():
    options = [{
        "campus": "전북대학교", "emd_cd": "52111142", "route_id": "r", "route_no": "100",
        "stop_count": 2, "origin_stop_id": "near", "campus_stop_id": "school",
    }]
    details = {"52111142": {"emd_nm": "효자동3가", "gu": "완산구"}}
    boarding = [
        {"campus": "전북대학교", "emd_cd": "52111142", "origin_stop_id": stop, "stop_count": count}
        for stop, count in (("near", 2), ("far", 25))
    ]
    row = bus.aggregate_commute(options, {"r": 15}, details, boarding)[0]
    assert (row["min_stop_count"], row["median_stops"], row["boarding_stops"]) == (2, 13.5, 2)
    boarding.append({"campus": "전북대학교", "emd_cd": "52111142", "origin_stop_id": "middle", "stop_count": 9})
    row = bus.aggregate_commute(options, {"r": 15}, details, boarding)[0]
    assert (row["min_stop_count"], row["median_stops"], row["boarding_stops"]) == (2, 9, 3)


def test_boarding_options_use_each_stop_once_and_school_direction():
    campus = {"전북대학교": {"school"}}
    dong = {"far": "52111142", "near": "52111142"}
    route = ["far", *[f"mid{i}" for i in range(19)], "near", "school"]
    rows = bus.boarding_options_for_route("r", "100", route, dong, campus)
    assert {(row["origin_stop_id"], row["stop_count"]) for row in rows} == {("far", 21), ("near", 1)}
    assert bus.boarding_options_for_route("r", "100", ["school", "far"], dong, campus) == []


def test_boarding_stop_uses_shortest_route_across_variants(tmp_path):
    def route_file(name, stops):
        root = ET.Element("response")
        ET.SubElement(root, "resultCode").text = "00"
        for order, stop_id in enumerate(stops, 1):
            item = ET.SubElement(root, "item")
            ET.SubElement(item, "nodeord").text = str(order)
            ET.SubElement(item, "nodeid").text = stop_id
        path = tmp_path / f"{name}.xml"
        path.write_bytes(ET.tostring(root, encoding="utf-8"))
        return path

    mapped = [
        {"stop_id": "far", "emd_cd": "52111142"},
        {"stop_id": "near", "emd_cd": "52111142"},
    ]
    paths = {
        "long": route_file("long", ["far", "middle", "near", "school"]),
        "short": route_file("short", ["far", "middle", "school"]),
    }
    boarding = bus.calculate_boarding_stops(
        mapped, paths, {"long": "100", "short": "200"}, {"전북대학교": {"school"}}
    )
    assert [(row["origin_stop_id"], row["stop_count"], row["route_id"]) for row in boarding] == [
        ("near", 1, "long"), ("far", 2, "short")
    ]


def test_excluded_campus_stop_is_not_used_as_destination(tmp_path):
    excluded = "JUB305032613"
    confirmed = "JUB305032181"
    mapped = [{"stop_id": "origin", "emd_cd": "52111137"}]

    def route_file(name, nodes):
        root = ET.Element("response")
        ET.SubElement(root, "resultCode").text = "00"
        for order, node in enumerate(nodes, 1):
            item = ET.SubElement(root, "item")
            ET.SubElement(item, "nodeord").text = str(order)
            ET.SubElement(item, "nodeid").text = node
        path = tmp_path / f"{name}.xml"
        path.write_bytes(ET.tostring(root, encoding="utf-8"))
        return path

    paths = {
        "excluded_only": route_file("excluded_only", ["origin", excluded]),
        "with_confirmed": route_file("with_confirmed", ["origin", excluded, confirmed]),
    }
    options = bus.calculate_direct_options(mapped, paths, {"excluded_only": "1", "with_confirmed": "2"})
    assert [(row["route_id"], row["campus_stop_id"], row["stop_count"]) for row in options] == [
        ("with_confirmed", confirmed, 2)
    ]


def test_saved_commute_results_use_only_confirmed_destination_ids():
    preliminary = json.loads(
        (bus.AUDIT_DIR / "bus_direct_options_preliminary.json").read_text(encoding="utf-8")
    )
    with (bus.OUTPUT_DIR / "commute_access.csv").open(encoding="utf-8", newline="") as handle:
        final_rows = list(csv.DictReader(handle))
    for row in [*preliminary["options"], *final_rows]:
        assert row["campus_stop_id"] in bus.CONFIRMED_CAMPUS_STOP_IDS[row["campus"]]


def test_saved_medians_match_boarding_stop_audit():
    with (bus.AUDIT_DIR / "bus_boarding_stops.csv").open(encoding="utf-8", newline="") as handle:
        boarding = list(csv.DictReader(handle))
    with (bus.OUTPUT_DIR / "commute_access.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    by_pair = {}
    for stop in boarding:
        by_pair.setdefault((stop["campus"], stop["emd_cd"]), []).append(int(stop["stop_count"]))
    for row in rows:
        counts = by_pair[(row["campus"], row["emd_cd"])]
        assert int(row["boarding_stops"]) == len(counts)
        assert float(row["median_stops"]) == statistics.median(counts)
        assert int(row["min_stop_count"]) == min(counts) <= 20


def test_saved_example_sequences_match_commute_results():
    examples = json.loads((bus.AUDIT_DIR / "bus_commute_examples.json").read_text(encoding="utf-8"))
    with (bus.OUTPUT_DIR / "commute_access.csv").open(encoding="utf-8", newline="") as handle:
        rows = {(row["campus"], row["emd_cd"]): row for row in csv.DictReader(handle)}
    assert len(examples) == 3
    for example in examples:
        row = rows[(example["campus"], example["emd_cd"])]
        assert len(example["ordered_stop_names"]) == example["min_stop_count"] + 1
        assert example["route_no"] in row["direct_route_numbers"].split(",")
        assert example["min_stop_count"] == int(row["min_stop_count"])
        assert example["median_stops"] == float(row["median_stops"])
        assert example["boarding_stops"] == int(row["boarding_stops"])
