"""Build SPEC-005 bus stop and direct commute data from cached official sources."""

import csv
import hashlib
import json
import math
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import shapefile
from pyproj import CRS, Geod, Transformer
from shapely.geometry import Point, shape
from shapely.validation import make_valid

ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_DIR = ROOT / "data/raw/boundary"
STOPS_XML = ROOT / "data/raw/bus/tago/stops_city_35010.xml"
OUTPUT_DIR = ROOT / "outputs/bus"
DOCS_DIR = ROOT / "docs/bus"
AUDIT_DIR = ROOT / "data/audit"
TAGO_RAW = ROOT / "data/raw/bus/tago"
JEONJU_GU = {"52111": "완산구", "52113": "덕진구"}
CAMPUS_PATTERNS = {
    "전주대학교": ("전주대",),
    "전주비전대학교": ("전주비전대", "비전대"),
    "전북대학교": ("전북대",),
}
CONFIRMED_CAMPUS_STOP_IDS = {
    "전주대학교": frozenset({
        "JUB305032181", "JUB305032182", "JUB305032694", "JUB305032695",
        "JUB305032696", "JUB305032697", "JUB305100609", "JUB305100630",
        "JUB305100650", "JUB305100651", "JUB305032180", "JUB305032179",
    }),
    "전주비전대학교": frozenset({
        "JUB305032463", "JUB305100516", "JUB305100526", "JUB305100527",
        "JUB305100517", "JUB305100501", "JUB305100532", "JUB305100536",
        "JUB305100494",
    }),
    "전북대학교": frozenset({
        "JUB305032080", "JUB305032481", "JUB305032817", "JUB305032818",
        "JUB306101027", "JUB306101035", "JUB306101044", "JUB306101049",
        "JUB306101051", "JUB306101056", "JUB306101070", "JUB306101079",
        "JUB306132039", "JUB316032081", "JUB306101020", "JUB306032082",
        "JUB312302214",
    }),
}
EXCLUDED_CAMPUS_STOP_REASONS = {
    "전주대학교": {
        "JUB305032613": "대성동 소재 전주 대성초교로 이름만 겹침, 약 8km",
        "JUB305032614": "대성동 소재 전주 대성초교로 이름만 겹침, 약 8km",
        "JUB305100425": "전주 대성초교 주변 아파트 정류소, 약 8km",
        "JUB305100428": "전주 대성초교 주변 아파트 정류소, 약 8km",
    },
    "전주비전대학교": {},
    "전북대학교": dict.fromkeys((
        "JUB306101069", "JUB305032375", "JUB306101057", "JUB306101046",
        "JUB305032582", "JUB305032581", "JUB306101050", "JUB306101053",
        "JUB306101017", "JUB305032816", "JUB305032815", "JUB306101113",
    ), "캠퍼스 밖, 반경 규칙으로만 포함"),
}
CAMPUS_AREA_CODES = {
    "전주대학교": {"52111141", "52111142"},
    "전주비전대학교": {"52111141", "52111142"},
    "전북대학교": {"52113105", "52113107"},
}


@dataclass(frozen=True)
class Boundary:
    code: str
    name: str
    geometry: object


def source_file(path):
    """Return a secret-free source fingerprint for output audits."""
    return {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def load_boundaries(zip_path):
    """Read EUC-KR SHP and project metadata; select only Jeonju gu codes."""
    with ZipFile(zip_path) as archive:
        stem = next(name[:-4] for name in archive.namelist() if name.lower().endswith(".shp"))
        cpg = archive.read(stem + ".cpg").decode("ascii").strip().upper()
        if cpg not in {"EUC-KR", "CP949"}:
            raise ValueError(f"Unexpected DBF encoding: {cpg}")
        prj = archive.read(stem + ".prj").decode("ascii")
        crs = CRS.from_wkt(prj)
        if not crs.is_projected or "5186" not in prj:
            raise ValueError("Boundary PRJ must declare projected EPSG:5186")
        reader = shapefile.Reader(
            shp=BytesIO(archive.read(stem + ".shp")),
            shx=BytesIO(archive.read(stem + ".shx")),
            dbf=BytesIO(archive.read(stem + ".dbf")),
            encoding="euc-kr" if cpg == "EUC-KR" else "cp949",
        )
        fields = {field[0] for field in reader.fields[1:]}
        if not {"EMD_CD", "EMD_NM"} <= fields:
            raise ValueError("Boundary DBF is missing EMD_CD or EMD_NM")
        boundaries = []
        repaired = 0
        for entry in reader.iterShapeRecords():
            record = entry.record.as_dict()
            code = str(record["EMD_CD"]).strip()
            if code[:5] not in JEONJU_GU:
                continue
            geometry = shape(entry.shape.__geo_interface__)
            if not geometry.is_valid:
                geometry = make_valid(geometry)
                repaired += 1
            boundaries.append(Boundary(code, record["EMD_NM"].strip(), geometry))
    if not boundaries:
        raise ValueError("No Jeonju legal-dong boundaries found")
    boundaries.sort(key=lambda item: item.code)
    return boundaries, crs, repaired


def read_stops(path):
    """Read cached TAGO stop IDs, Korean names, and WGS84 coordinates."""
    root = ET.fromstring(path.read_bytes())
    if root.findtext(".//resultCode") != "00":
        raise ValueError("TAGO stop response is not successful")
    stops = []
    for item in root.findall(".//item"):
        name = item.findtext("nodenm") or ""
        if not name or "\ufffd" in name:
            raise ValueError("TAGO stop name missing or damaged")
        stop_id = item.findtext("nodeid")
        lon, lat = float(item.findtext("gpslong")), float(item.findtext("gpslati"))
        if not stop_id or not (math.isfinite(lon) and math.isfinite(lat)):
            raise ValueError("TAGO stop ID or coordinates invalid")
        stops.append({"stop_id": stop_id, "stop_name": name, "longitude": lon, "latitude": lat})
    if len({stop["stop_id"] for stop in stops}) != len(stops):
        raise ValueError("TAGO stop IDs are not unique")
    return sorted(stops, key=lambda stop: stop["stop_id"])


def assign_stops(stops, boundaries, crs):
    """Use exact legal-dong polygons, including boundary points, after CRS conversion."""
    transform = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    result = []
    for stop in stops:
        x, y = transform.transform(stop["longitude"], stop["latitude"])
        matches = [boundary for boundary in boundaries if boundary.geometry.covers(Point(x, y))]
        row = dict(stop)
        if len(matches) == 1:
            boundary = matches[0]
            row.update(emd_cd=boundary.code, emd_nm=boundary.name, gu=JEONJU_GU[boundary.code[:5]], method="point_in_legal_dong_boundary")
        elif not matches:
            row.update(emd_cd="", emd_nm="", gu="", method="outside_jeonju_boundary")
        else:
            row.update(emd_cd="", emd_nm="", gu="", method="ambiguous_boundary_overlap")
        result.append(row)
    return result


def write_stops_by_dong(rows, output_dir, source_audit):
    """Write all stops, including outside stops, plus mapping method counts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_file = output_dir / "stops_by_dong.csv"
    fields = ["stop_id", "stop_name", "longitude", "latitude", "emd_cd", "emd_nm", "gu", "method"]
    with csv_file.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    counts = {method: sum(row["method"] == method for row in rows) for method in ("point_in_legal_dong_boundary", "outside_jeonju_boundary", "ambiguous_boundary_overlap")}
    audit = {"source": source_audit, "stop_count": len(rows), "method_counts": counts, "scope_emd_cd_prefixes": sorted(JEONJU_GU)}
    (output_dir / "stops_by_dong_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return audit


def build_t2():
    archives = list(BOUNDARY_DIR.glob("LSMD_ADM_SECT_UMD_*.zip"))
    if len(archives) != 1:
        raise ValueError("Expected exactly one Jeonju legal-dong boundary ZIP")
    archive = archives[0]
    boundaries, crs, repaired = load_boundaries(archive)
    rows = assign_stops(read_stops(STOPS_XML), boundaries, crs)
    audit = write_stops_by_dong(rows, OUTPUT_DIR, {"boundary": source_file(archive), "stops": source_file(STOPS_XML), "boundary_crs": crs.name, "boundary_geometries_repaired": repaired, "selected_boundary_count": len(boundaries)})
    print(json.dumps(audit, ensure_ascii=True))


def campus_candidates(stops, patterns=CAMPUS_PATTERNS, radius_m=300.0):
    """Include name matches and every stop within radius of a name match."""
    geod = Geod(ellps="WGS84")
    candidates = []
    for campus, tokens in patterns.items():
        seeds = [stop for stop in stops if any(token in stop["stop_name"] for token in tokens)]
        for stop in stops:
            if not seeds:
                continue
            nearby = []
            for seed in seeds:
                _, _, distance = geod.inv(
                    stop["longitude"], stop["latitude"], seed["longitude"], seed["latitude"]
                )
                nearby.append((distance, seed["stop_id"], seed))
            distance, _, nearest = min(nearby)
            if distance <= radius_m + 1e-6:
                candidates.append(
                    {
                        "campus": campus,
                        **stop,
                        "seed_stop_id": nearest["stop_id"],
                        "seed_stop_name": nearest["stop_name"],
                        "distance_m": round(distance, 1),
                        "selection": "학교명 정류소" if stop["stop_id"] in {seed["stop_id"] for seed in seeds} else "기준 정류소 300m 이내",
                        "status": "후보",
                    }
                )
    return sorted(candidates, key=lambda row: (row["campus"], row["distance_m"], row["stop_id"]))


def review_campus_candidates(rows):
    """Apply the human-confirmed ID list and reject unreviewed candidates."""
    reviewed = []
    for row in rows:
        campus, stop_id = row["campus"], row["stop_id"]
        confirmed = CONFIRMED_CAMPUS_STOP_IDS[campus]
        excluded = EXCLUDED_CAMPUS_STOP_REASONS[campus]
        if stop_id in confirmed:
            status = "확정"
        elif stop_id in excluded:
            status = f"제외({excluded[stop_id]})"
        else:
            raise ValueError(f"Unreviewed campus stop: {campus} {stop_id}")
        reviewed.append({**row, "status": status})
    for campus, confirmed in CONFIRMED_CAMPUS_STOP_IDS.items():
        observed = {row["stop_id"] for row in reviewed if row["campus"] == campus}
        if observed != confirmed | set(EXCLUDED_CAMPUS_STOP_REASONS[campus]):
            raise ValueError(f"Campus review IDs do not match cached candidates: {campus}")
    return reviewed


def write_campus_candidates(rows, output_dir=OUTPUT_DIR, docs_dir=DOCS_DIR):
    """Write machine-readable candidates and the human-reviewed Markdown table."""
    output_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)
    fields = ["campus", "stop_id", "stop_name", "longitude", "latitude", "seed_stop_id", "seed_stop_name", "distance_m", "selection", "status"]
    with (output_dir / "campus_stops_candidates.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# SPEC-005 D-044 · 캠퍼스 정류장 확인 결과",
        "",
        "TAGO 전주시 정류소 목록(2026-11-13 확인)에서 학교명 포함 정류소와 각 정류소 반경 300m 이내 정류소를 후보로 뽑았다. 사용자가 지도로 확인한 정류소 ID를 `src/build_bus_access.py`의 확정 목록에 고정했다. **T4에는 확정 ID만 사용한다.**",
        "전주비전대학교는 TAGO에 `전주비전대` 표기가 없어 후보 추출 때 `비전대`를 별칭으로 사용했다. 전주대성초교는 대성동의 전주 대성초교로 이름만 겹치며 캠퍼스에서 약 8km 떨어져 제외했다. 반경 규칙으로 들어온 캠퍼스 밖 정류소도 제외했다.",
        "",
    ]
    for campus in CAMPUS_PATTERNS:
        selected = [row for row in rows if row["campus"] == campus]
        lines.extend(
            [
                f"## {campus} · 확정 {sum(row['status'] == '확정' for row in selected)}곳 / 제외 {sum(row['status'].startswith('제외') for row in selected)}곳",
                "",
                "| 정류소 ID | 이름 | 경도 | 위도 | 기준 정류소 ID·이름 | 거리(m) | 근거 | 상태 |",
                "|---|---|---:|---:|---|---:|---|---|",
            ]
        )
        for row in selected:
            lines.append(
                f"| {row['stop_id']} | {row['stop_name']} | {row['longitude']:.7f} | {row['latitude']:.7f} | {row['seed_stop_id']} {row['seed_stop_name']} | {row['distance_m']:.1f} | {row['selection']} | {row['status']} |"
            )
        if not selected:
            lines.append("| - | 후보 없음 | - | - | - | - | - | 후보 |")
        lines.append("")
    lines.extend(["원자료: `data/raw/bus/tago/stops_city_35010.xml`; 산출: `src/build_bus_access.py`, `outputs/bus/campus_stops_candidates.csv`.", ""])
    (docs_dir / "campus_stops.md").write_text("\n".join(lines), encoding="utf-8")


def build_t3():
    rows = review_campus_candidates(campus_candidates(read_stops(STOPS_XML)))
    write_campus_candidates(rows)
    print(json.dumps({campus: {"confirmed": sum(row["campus"] == campus and row["status"] == "확정" for row in rows), "excluded": sum(row["campus"] == campus and row["status"].startswith("제외") for row in rows)} for campus in CAMPUS_PATTERNS}, ensure_ascii=True))


def load_route_numbers(path):
    root = ET.fromstring(path.read_bytes())
    if root.findtext(".//resultCode") != "00":
        raise ValueError("TAGO route list is not successful")
    return {item.findtext("routeid"): item.findtext("routeno") for item in root.findall(".//item")}


def read_route_stops(path):
    """Keep sequence positions, since nodeord can differ from a simple index."""
    root = ET.fromstring(path.read_bytes())
    if root.findtext(".//resultCode") != "00":
        raise ValueError(f"TAGO route stops are not successful: {path.name}")
    items = root.findall(".//item")
    return [item.findtext("nodeid") for item in sorted(items, key=lambda item: int(item.findtext("nodeord")))]


def direct_options(route_id, route_no, stop_ids, dong_by_stop, campus_stop_ids, max_stops=20):
    """Count only later campus stops in the same route variant's travel order."""
    options = {}
    for campus, targets in campus_stop_ids.items():
        for target_index, target_id in enumerate(stop_ids):
            if target_id not in targets:
                continue
            for origin_index in range(max(0, target_index - max_stops), target_index):
                origin_id = stop_ids[origin_index]
                dong = dong_by_stop.get(origin_id)
                if not dong or origin_id == target_id:
                    continue
                count = target_index - origin_index
                key = (campus, dong, route_id)
                current = options.get(key)
                if current is None or (count, origin_id, target_id) < (
                    current["stop_count"], current["origin_stop_id"], current["campus_stop_id"]
                ):
                    options[key] = {
                        "campus": campus,
                        "emd_cd": dong,
                        "route_id": route_id,
                        "route_no": route_no,
                        "stop_count": count,
                        "origin_stop_id": origin_id,
                        "campus_stop_id": target_id,
                    }
    return list(options.values())


def calculate_direct_options(mapped_stops, route_paths, route_numbers, campus_stop_ids=CONFIRMED_CAMPUS_STOP_IDS):
    dong_by_stop = {row["stop_id"]: row["emd_cd"] for row in mapped_stops if row["emd_cd"]}
    options = []
    for route_id, path in route_paths.items():
        route_no = route_numbers.get(route_id)
        if not route_no:
            raise ValueError(f"Route ID missing from TAGO route list: {route_id}")
        options.extend(direct_options(route_id, route_no, read_route_stops(path), dong_by_stop, campus_stop_ids))
    return sorted(options, key=lambda row: (row["campus"], row["emd_cd"], row["stop_count"], row["route_id"]))


def build_t4_preliminary():
    mapped = list(csv.DictReader((OUTPUT_DIR / "stops_by_dong.csv").open(encoding="utf-8", newline="")))
    reviewed = list(csv.DictReader((OUTPUT_DIR / "campus_stops_candidates.csv").open(encoding="utf-8", newline="")))
    for campus, confirmed in CONFIRMED_CAMPUS_STOP_IDS.items():
        in_csv = {row["stop_id"] for row in reviewed if row["campus"] == campus and row["status"] == "확정"}
        if in_csv != confirmed:
            raise ValueError(f"Confirmed stop CSV differs from fixed IDs: {campus}")
    route_ids = json.loads((AUDIT_DIR / "bus_route_discovery.json").read_text(encoding="utf-8"))["route_ids"]
    route_paths = {route_id: TAGO_RAW / f"route_stops_{route_id}.xml" for route_id in route_ids}
    options = calculate_direct_options(mapped, route_paths, load_route_numbers(TAGO_RAW / "routes_city_35010.xml"))
    route_ids = sorted({row["route_id"] for row in options})
    audit = {"max_stop_count_inclusive": 20, "campus_stop_ids_status": "확정", "confirmed_stop_count_by_campus": {campus: len(ids) for campus, ids in CONFIRMED_CAMPUS_STOP_IDS.items()}, "direct_route_ids": route_ids, "direct_route_variant_count": len(route_ids), "dong_campus_pairs": len({(row["campus"], row["emd_cd"]) for row in options}), "options": options}
    (AUDIT_DIR / "bus_direct_options_preliminary.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in audit.items() if not isinstance(value, list)}, ensure_ascii=True))


def read_route_interval(path):
    root = ET.fromstring(path.read_bytes())
    if root.findtext(".//resultCode") != "00":
        raise ValueError(f"TAGO route-info response is not successful: {path.name}")
    items = root.findall(".//item")
    if len(items) != 1:
        raise ValueError(f"Expected one TAGO route-info item: {path.name}")
    value = items[0].findtext("intervaltime")
    if value is None or not value.strip():
        return None
    interval = float(value)
    return int(interval) if interval > 0 and interval.is_integer() else None


def aggregate_commute(options, intervals, dong_details):
    """Group direction-safe route variants by campus and legal-dong code."""
    grouped = {}
    for option in options:
        grouped.setdefault((option["campus"], option["emd_cd"]), []).append(option)
    rows = []
    for (campus, code), variants in grouped.items():
        variants.sort(key=lambda row: (row["stop_count"], row["route_no"], row["route_id"]))
        best = variants[0]
        known = [intervals[row["route_id"]] for row in variants if intervals[row["route_id"]] is not None]
        missing = sorted({row["route_id"] for row in variants if intervals[row["route_id"]] is None})
        details = dong_details[code]
        rows.append(
            {
                "campus": campus,
                "emd_cd": code,
                "emd_nm": details["emd_nm"],
                "gu": details["gu"],
                "campus_area": "캠퍼스 주변" if code in CAMPUS_AREA_CODES[campus] else "통학권 후보",
                "min_stop_count": best["stop_count"],
                "direct_route_count": len({row["route_no"] for row in variants}),
                "direct_route_numbers": ",".join(sorted({row["route_no"] for row in variants})),
                "direct_route_variant_count": len(variants),
                "weekday_interval_min": min(known) if known and not missing else "배차 정보 없음",
                "known_min_interval_min": min(known) if known else "",
                "interval_status": "완전" if not missing else "일부 노선 미기재",
                "routes_missing_interval": ",".join(missing),
                "origin_stop_id": best["origin_stop_id"],
                "campus_stop_id": best["campus_stop_id"],
                "basis_date": "2026-11-13",
                "campus_stops_status": "확정",
            }
        )
    return sorted(rows, key=lambda row: (row["campus"], row["min_stop_count"], row["emd_cd"]))


def write_commute_dong_list(rows, docs_dir=DOCS_DIR):
    """Publish the confirmed-stop legal-dong list ordered by stop count."""
    docs_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# SPEC-005 D-045 · 캠퍼스별 통학권 동 후보",
        "",
        "`outputs/bus/commute_access.csv`를 최소 정류장 수 순으로 정리했다. **사람이 확정한 캠퍼스 정류소 ID만** 사용했다. 동→캠퍼스 직행 수치는 N-037 미검증이다.",
        "배차 값이 없는 직행 노선이 하나라도 있으면 최단 평일 배차 간격은 `배차 정보 없음`으로 표시한다. 캠퍼스 주변 동(D-017)은 아래 통학권 동 목록에서 제외했다.",
        "",
    ]
    for campus in CAMPUS_PATTERNS:
        selected = [row for row in rows if row["campus"] == campus and row["campus_area"] != "캠퍼스 주변"]
        lines.extend(
            [
                f"## {campus} · 통학권 동 후보 {len(selected)}곳",
                "",
                "| 법정동 코드 | 동 | 최소 정류장 수 | 직행 노선 수 | 최단 평일 배차 간격(분) | 상태 |",
                "|---|---|---:|---:|---:|---|",
            ]
        )
        for row in selected:
            interval = row["weekday_interval_min"]
            lines.append(
                f"| {row['emd_cd']} | {row['emd_nm']} | {row['min_stop_count']} | {row['direct_route_count']} | {interval} | 후보·미검증 |"
            )
        lines.append("")
    lines.extend(["원자료와 판정 방법: `data/raw/bus/tago/`, `outputs/bus/stops_by_dong.csv`, `outputs/bus/commute_access.csv`.", ""])
    (docs_dir / "commute_dongs.md").write_text("\n".join(lines), encoding="utf-8")


def build_t4():
    preliminary = json.loads((AUDIT_DIR / "bus_direct_options_preliminary.json").read_text(encoding="utf-8"))
    options = preliminary["options"]
    route_ids = preliminary["direct_route_ids"]
    intervals = {route_id: read_route_interval(TAGO_RAW / f"route_info_{route_id}.xml") for route_id in route_ids}
    mapped = list(csv.DictReader((OUTPUT_DIR / "stops_by_dong.csv").open(encoding="utf-8", newline="")))
    dong_details = {row["emd_cd"]: {"emd_nm": row["emd_nm"], "gu": row["gu"]} for row in mapped if row["emd_cd"]}
    rows = aggregate_commute(options, intervals, dong_details)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fields = ["campus", "emd_cd", "emd_nm", "gu", "campus_area", "min_stop_count", "direct_route_count", "direct_route_numbers", "direct_route_variant_count", "weekday_interval_min", "known_min_interval_min", "interval_status", "routes_missing_interval", "origin_stop_id", "campus_stop_id", "basis_date", "campus_stops_status"]
    with (OUTPUT_DIR / "commute_access.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    write_commute_dong_list(rows)
    audit = {
        "basis_date": "2026-11-13",
        "campus_stop_ids_status": "확정",
        "confirmed_stop_count_by_campus": {campus: len(ids) for campus, ids in CONFIRMED_CAMPUS_STOP_IDS.items()},
        "max_stop_count_inclusive": 20,
        "pair_count": len(rows),
        "by_campus": {campus: {"pairs": sum(row["campus"] == campus for row in rows), "commute_dongs_excluding_campus_area": len({row["emd_cd"] for row in rows if row["campus"] == campus and row["campus_area"] != "캠퍼스 주변"})} for campus in CAMPUS_PATTERNS},
        "pairs_with_incomplete_interval": sum(row["interval_status"] != "완전" for row in rows),
        "source": {"stop_mapping": source_file(OUTPUT_DIR / "stops_by_dong.csv"), "campus_candidates": source_file(OUTPUT_DIR / "campus_stops_candidates.csv"), "direct_options": source_file(AUDIT_DIR / "bus_direct_options_preliminary.json")},
    }
    (OUTPUT_DIR / "commute_access_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=True))


if __name__ == "__main__":
    if sys.argv[1:] == ["t2"]:
        build_t2()
    elif sys.argv[1:] == ["t3"]:
        build_t3()
    elif sys.argv[1:] == ["t4_preliminary"]:
        build_t4_preliminary()
    elif sys.argv[1:] == ["t4"]:
        build_t4()
    else:
        raise SystemExit("Usage: build_bus_access.py t2|t3|t4_preliminary|t4")
