"""SPEC-005 PR-2 regression and school-specific commute behavior."""

import json
from pathlib import Path
from statistics import median
from xml.etree import ElementTree

from fastapi.testclient import TestClient

from api import main
from src import analyze_rentals
from src.collect_tago_routes import missing_nodeord
from src.jurent import area, commute, engine

ROOT = Path(__file__).resolve().parents[1]
CLIENT = TestClient(main.app)


def test_campus_scope_reproduces_verified_n036_and_default_judge():
    old = json.loads((ROOT / "outputs/compare/budget_example.json").read_text(encoding="utf-8"))
    for campus, expected in old["results"].items():
        actual = area.budget_search(campus, 500, 35, 15, scope="campus", rate_pct=5)
        assert actual == expected
    assert (old["results"]["효자동권"]["total_combinations"],
            len(old["results"]["효자동권"]["recommendations"])) == (21, 6)
    assert (old["results"]["전북대권"]["total_combinations"],
            len(old["results"]["전북대권"]["recommendations"])) == (21, 7)
    args = ("효자동권", "oneroom", 25, 500, 35)
    assert engine.judge(*args) == engine.judge(*args, dong=None)
    request = {"campus": "효자동권", "housing_type": "oneroom", "area": 25,
               "deposit": 500, "monthly": 35}
    assert CLIENT.post("/api/judge", json=request).json() == engine.judge(*args, dataset="current")


def test_commute_priority_school_scope_and_price_baseline():
    for campus, school in (("효자동권", "전주대학교"),
                           ("효자동권", "전주비전대학교"),
                           ("전북대권", "전북대학교")):
        result = area.budget_search(campus, 500, 35, 15, priority="commute", school=school)
        assert result["input"]["school"] == school
        order = [(not card["commute"]["campus_area"],
                  card["commute"]["min_stops"] or 0,
                  card["commute"]["median_stops"] or 0)
                 for card in result["recommendations"]]
        assert order == sorted(order)
        baseline = {}
        for kind in area.HOUSING_TYPES:
            rows = area.recent_deals(campus, kind, 40 if kind == "apartment" else 15)
            for age in {row["경과연수구간"] for row in rows}:
                same_age = [row for row in rows if row["경과연수구간"] == age]
                if len(same_age) >= engine.MIN_SAMPLE:
                    baseline[kind, age] = median(
                        engine.converted_monthly(row["보증금"], row["월세"], 5) for row in same_age
                    )
        for card in result["recommendations"]:
            assert card["dong"] in analyze_rentals.CAMPUS_AREAS[campus]["dongs"] or card["dong"] in {
                row["dong"] for row in commute.commute_rows(campus, school)
            }
            reference = baseline.get((card["housing_type"], card["age_band"]))
            if reference is None:
                assert card["campus_price_difference_10k_krw"] is None
            else:
                expected = round(card["quantiles_10k_krw"]["p50"] - float(reference), 2)
                assert abs(card["campus_price_difference_10k_krw"] - expected) < 0.011


def test_campus_age_baseline_requires_30_and_never_mix_ages():
    def row(age, monthly):
        return {"경과연수구간": age, "보증금": "500", "월세": str(monthly)}

    rows = [row("20년 이상", 20) for _ in range(29)]
    rows += [row("10~19년", 50) for _ in range(30)]
    baselines = area._campus_age_medians(rows, 5)
    assert "20년 이상" not in baselines
    assert baselines["10~19년"] == engine.converted_monthly("500", "50", 5)
    rows.append(row("20년 이상", 20))
    assert area._campus_age_medians(rows, 5)["20년 이상"] == engine.converted_monthly("500", "20", 5)


def test_dong_judgment_filters_only_selected_dong_and_keeps_shortage_and_concentration():
    dong = "서신동"
    args = ("효자동권", "oneroom", 25, 500, 35)
    result = engine.judge(*args, dong=dong, school="전주대학교")
    rows, _, _ = engine.select_similar(engine.load_processed(engine.PROCESSED),
                                       "효자동권", "oneroom", 25, dong)
    assert rows and all(row["법정동"] == dong for row in rows)
    assert result["n"] == len(rows)
    original = engine.load_processed
    def synthetic(_source):
        base = {"법정동": dong, "대학가": "전북대권", "주택유형": "multifamily",
                "계약구분": "신규", "계약일": "2026-01-01", "면적": "25",
                "보증금": "500", "월세": "35", "경과연수구간": "미기재",
                "단지명": "", "번지": "1"}
        return [dict(base) for _ in range(29)] + [dict(base, 법정동="효자동3가") for _ in range(80)]
    engine.load_processed = synthetic
    try:
        assert engine.judge(*args, dong=dong, school="전주대학교")["label"] == "표본 부족"
        def concentrated(_source):
            rows = synthetic(_source)
            rows.insert(0, dict(rows[0]))
            return [dict(row, 단지명="한 건물") if i < 20 else row
                    for i, row in enumerate(rows)]
        engine.load_processed = concentrated
        assert engine.judge(*args, dong=dong, school="전주대학교")["label"] == "판단 보류"
    finally:
        engine.load_processed = original


def test_meta_adjacent_interval_and_reference_output():
    meta = CLIENT.get("/api/meta").json()
    assert meta["schools_by_campus"]["효자동권"] == ["전주대학교", "전주비전대학교"]
    assert {"인후동2가", "송천동1가"} <= {
        row["dong"] for row in meta["commute_by_school"]["전북대학교"] if row["campus_adjacent"]
    }
    counts = meta["commute_deal_counts_by_school"]
    for campus, schools in commute.SCHOOLS_BY_CAMPUS.items():
        for school in schools:
            for kind in area.HOUSING_TYPES:
                expected = {}
                for row in area.commute_deals(campus, school, kind, 40 if kind == "apartment" else 15,
                                              dataset="current"):
                    expected[row["법정동"]] = expected.get(row["법정동"], 0) + 1
                for bus in commute.commute_rows(campus, school):
                    assert counts[school][kind].get(bus["dong"], 0) == expected.get(bus["dong"], 0)
    path = area.write_commute_reference_output()
    before = path.read_bytes()
    area.write_commute_reference_output()
    assert path.read_bytes() == before
    example = json.loads(before)
    assert (example["results"]["효자동권"]["total_combinations"],
            len(example["results"]["효자동권"]["recommendations"])) == (223, 44)
    assert (example["results"]["전북대권"]["total_combinations"],
            len(example["results"]["전북대권"]["recommendations"])) == (280, 52)


def test_saved_bus_schedule_average_requires_valid_trip_count(tmp_path, monkeypatch):
    from src import build_route_intervals

    assert commute.planned_average_interval("0550", "2250", "46") == round(1020 / 45)
    for values in (("0550", "2250", ""), ("0550", "2250", "1"),
                   ("2500", "2250", "46"), ("2250", "0550", "46")):
        assert commute.planned_average_interval(*values) is None
    route_id = "JUB305001153"
    tago_dir = tmp_path / "tago"
    tago_dir.mkdir()
    (tago_dir / f"route_info_{route_id}.xml").write_text(
        f"<response><item><routeid>{route_id}</routeid><startvehicletime>0550</startvehicletime>"
        "<endvehicletime>2250</endvehicletime></item></response>", encoding="utf-8",
    )
    gw = tmp_path / "route_info.xml"
    fixed = tmp_path / "route_intervals.csv"
    monkeypatch.setattr(build_route_intervals, "GW_ROUTE_INFO", gw)
    monkeypatch.setattr(build_route_intervals, "TAGO_RAW", tago_dir)
    monkeypatch.setattr(build_route_intervals, "OUTPUT", fixed)
    monkeypatch.setattr(commute, "ROUTE_INTERVALS", fixed)
    try:
        for trips, expected in (("0", {}), ("46", {route_id: round(1020 / 45)})):
            gw.write_text(
                f"<response><list><brtStdid>305001153</brtStdid><brtFirstTime>550</brtFirstTime>"
                f"<brtLastTime>2250</brtLastTime><TCount>46</TCount><BCount>{trips}</BCount>"
                "</list></response>", encoding="utf-8",
            )
            build_route_intervals.build()
            commute.planned_intervals_by_route.cache_clear()
            assert commute.planned_intervals_by_route() == expected
            monkeypatch.setattr(build_route_intervals, "GW_ROUTE_INFO", tmp_path / "raw-hidden.xml")
            commute.planned_intervals_by_route.cache_clear()
            assert commute.planned_intervals_by_route() == expected
            monkeypatch.setattr(build_route_intervals, "GW_ROUTE_INFO", gw)
    finally:
        commute.planned_intervals_by_route.cache_clear()


def test_split_manifests_survive_rental_analysis():
    rental = ROOT / "data/audit/manifest.json"
    bus = ROOT / "data/audit/bus_manifest.json"
    before = rental.read_bytes(), bus.read_bytes()
    assert len(json.loads(before[0])) == 48
    assert len(json.loads(before[1])) == 423
    analyze_rentals.main()
    assert (rental.read_bytes(), bus.read_bytes()) == before


def test_nodeord_gap_audit_records_cached_route_without_changing_call_count():
    audit = json.loads((ROOT / "data/audit/bus_route_stops_audit.json").read_text(encoding="utf-8"))
    assert audit["nodeord_checked_route_count"] == 180
    assert audit["missing_nodeord_by_route"] == {"JUB305001019": [5]}
    assert audit["new_api_calls"] == 179
    items = ElementTree.fromstring("<items><item><nodeord>1</nodeord></item>"
                                   "<item><nodeord>3</nodeord></item></items>")
    assert missing_nodeord(items) == [2]
