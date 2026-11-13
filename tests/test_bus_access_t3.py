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
