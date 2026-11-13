"""Check direction, 20-stop inclusion, minimum, and route aggregation."""

import csv
import json
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
    row = bus.aggregate_commute(options, {"a": 15, "b": None, "c": 25}, details)[0]
    assert row["min_stop_count"] == 2
    assert row["direct_route_count"] == 2
    assert row["weekday_interval_min"] == "배차 정보 없음"
    assert row["known_min_interval_min"] == 15
    assert row["interval_status"] == "일부 노선 미기재"
    assert row["routes_missing_interval"] == "b"


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
