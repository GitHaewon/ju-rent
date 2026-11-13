"""Check the 300 m campus candidate boundary and naming alias."""

from pyproj import Geod

from src import build_bus_access as bus


def stop(stop_id, name, lon, lat):
    return {"stop_id": stop_id, "stop_name": name, "longitude": lon, "latitude": lat}


def test_300m_exactly_included_and_farther_stop_excluded():
    geod = Geod(ellps="WGS84")
    lon, lat = 127.1, 35.8
    at_300_lon, at_300_lat, _ = geod.fwd(lon, lat, 90, 300)
    past_300_lon, past_300_lat, _ = geod.fwd(lon, lat, 90, 300.1)
    rows = bus.campus_candidates(
        [
            stop("seed", "전주대학교", lon, lat),
            stop("boundary", "근처", at_300_lon, at_300_lat),
            stop("outside", "멀리", past_300_lon, past_300_lat),
        ],
        patterns={"전주대학교": ("전주대",)},
    )
    assert {row["stop_id"] for row in rows} == {"seed", "boundary"}
    assert all(row["status"] == "후보" for row in rows)
    assert next(row for row in rows if row["stop_id"] == "boundary")["seed_stop_id"] == "seed"


def test_vision_university_name_alias_is_candidate():
    rows = bus.campus_candidates([stop("vision", "비전대학교", 127.1, 35.8)])
    assert [(row["campus"], row["stop_id"]) for row in rows] == [("전주비전대학교", "vision")]


def test_human_review_fixed_ids_and_exclusions():
    expected = {
        "전주대학교": {
            "JUB305032181", "JUB305032182", "JUB305032694", "JUB305032695",
            "JUB305032696", "JUB305032697", "JUB305100609", "JUB305100630",
            "JUB305100650", "JUB305100651", "JUB305032180", "JUB305032179",
        },
        "전주비전대학교": {
            "JUB305032463", "JUB305100516", "JUB305100526", "JUB305100527",
            "JUB305100517", "JUB305100501", "JUB305100532", "JUB305100536",
            "JUB305100494",
        },
        "전북대학교": {
            "JUB305032080", "JUB305032481", "JUB305032817", "JUB305032818",
            "JUB306101027", "JUB306101035", "JUB306101044", "JUB306101049",
            "JUB306101051", "JUB306101056", "JUB306101070", "JUB306101079",
            "JUB306132039", "JUB316032081", "JUB306101020", "JUB306032082",
            "JUB312302214",
        },
    }
    assert bus.CONFIRMED_CAMPUS_STOP_IDS == expected
    assert {"JUB305032613", "JUB305032614", "JUB305100425", "JUB305100428"} == set(
        bus.EXCLUDED_CAMPUS_STOP_REASONS["전주대학교"]
    )
    assert set(bus.EXCLUDED_CAMPUS_STOP_REASONS["전북대학교"]) == {
        "JUB306101069", "JUB305032375", "JUB306101057", "JUB306101046",
        "JUB305032582", "JUB305032581", "JUB306101050", "JUB306101053",
        "JUB306101017", "JUB305032816", "JUB305032815", "JUB306101113",
    }
    rows = [
        {"campus": campus, "stop_id": stop_id}
        for campus, confirmed in bus.CONFIRMED_CAMPUS_STOP_IDS.items()
        for stop_id in confirmed | set(bus.EXCLUDED_CAMPUS_STOP_REASONS[campus])
    ]
    reviewed = bus.review_campus_candidates(rows)
    assert sum(row["status"] == "확정" for row in reviewed) == 38
    assert sum(row["status"].startswith("제외(") for row in reviewed) == 16
    assert all(
        set(bus.EXCLUDED_CAMPUS_STOP_REASONS[campus]).isdisjoint(confirmed)
        for campus, confirmed in bus.CONFIRMED_CAMPUS_STOP_IDS.items()
    )
