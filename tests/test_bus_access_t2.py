"""Validate legal-dong code filtering and projected point assignment."""

import json
from zipfile import ZipFile

import shapefile
from pyproj import CRS, Transformer

from src import build_bus_access as bus


def square(x, y, radius):
    return [
        [x - radius, y - radius],
        [x - radius, y + radius],
        [x + radius, y + radius],
        [x + radius, y - radius],
        [x - radius, y - radius],
    ]


def make_boundary_zip(tmp_path):
    stem = tmp_path / "districts"
    x, y = Transformer.from_crs("EPSG:4326", "EPSG:5186", always_xy=True).transform(127.13, 35.84)
    with shapefile.Writer(str(stem), shapeType=shapefile.POLYGON, encoding="euc-kr") as writer:
        writer.field("EMD_CD", "C", size=8)
        writer.field("EMD_NM", "C", size=100)
        for code, name, dx in (
            ("52113107", "금암동", 0),
            ("52130131", "금암동", 0),
            ("52111142", "효자동3가", 3000),
        ):
            writer.poly([square(x + dx, y, 500)])
            writer.record(code, name)
    stem.with_suffix(".cpg").write_text("EUC-KR\n", encoding="ascii")
    stem.with_suffix(".prj").write_text(CRS.from_epsg(5186).to_wkt(version="WKT1_GDAL"), encoding="ascii")
    archive = tmp_path / "boundaries.zip"
    with ZipFile(archive, "w") as z:
        for suffix in (".shp", ".shx", ".dbf", ".cpg", ".prj"):
            z.write(stem.with_suffix(suffix), arcname="districts" + suffix)
    return archive, x, y


def test_same_named_other_city_excluded_and_wgs84_transformed(tmp_path):
    archive, x, y = make_boundary_zip(tmp_path)
    boundaries, crs, repaired = bus.load_boundaries(archive)
    assert repaired == 0
    assert {boundary.code for boundary in boundaries} == {"52113107", "52111142"}
    assert crs.is_projected
    lon2, lat2 = Transformer.from_crs(crs, "EPSG:4326", always_xy=True).transform(x + 3000, y)
    stops = [
        {"stop_id": "one", "stop_name": "금암동", "longitude": 127.13, "latitude": 35.84},
        {"stop_id": "two", "stop_name": "효자동", "longitude": lon2, "latitude": lat2},
        {"stop_id": "outside", "stop_name": "시외", "longitude": 128.0, "latitude": 35.84},
    ]
    rows = bus.assign_stops(stops, boundaries, crs)
    assert [(row["emd_cd"], row["method"]) for row in rows] == [
        ("52113107", "point_in_legal_dong_boundary"),
        ("52111142", "point_in_legal_dong_boundary"),
        ("", "outside_jeonju_boundary"),
    ]
    audit = bus.write_stops_by_dong(rows, tmp_path / "out", {"test": "fixture"})
    assert audit["method_counts"]["outside_jeonju_boundary"] == 1
    assert json.loads((tmp_path / "out/stops_by_dong_audit.json").read_text(encoding="utf-8")) == audit
