"""SPEC-006 fixed evidence and moving service window regressions."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from src import refresh_rentals
from src.jurent import area, dataset, engine

ROOT = Path(__file__).resolve().parents[1]


def test_snapshot_service_results_equal_main_exactly():
    expected = json.loads((ROOT / "tests/fixtures/service_snapshot_main.json").read_text(encoding="utf-8"))
    assert engine.judge("효자동권", "oneroom", 25, 500, 35) == expected["judge_default"]
    assert engine.judge("효자동권", "oneroom", 25, 500, 35,
                        dong="서신동", school="전주대학교") == expected["judge_dong"]
    for campus, result in expected["budget_campus"].items():
        assert area.budget_search(campus, 500, 35, 15, priority="cheap", rate_pct=5,
                                  scope="campus") == result
    for campus, result in expected["budget_commute"].items():
        assert area.budget_search(campus, 500, 35, 15, priority="cheap", rate_pct=5,
                                  scope="commute") == result
    assert area.campus_compare(5) == expected["compare"]


def test_moving_window_and_year_boundary():
    november = dataset.RentalDataset("current", ROOT, "202611", "2026-11-16")
    assert november.recent_start == "2024-12-01"
    assert november.data_end == "2026-11-30"
    assert november.incomplete_months == ("202610", "202611")
    assert november.partial_year == 2026
    december = dataset.RentalDataset("current", ROOT, "202612", "2027-01-05")
    assert december.incomplete_months == ("202611", "202612")
    assert december.partial_year is None
    january = dataset.RentalDataset("current", ROOT, "202701", "2027-02-05")
    assert january.recent_start == "2025-02-01"
    assert january.incomplete_months == ("202612", "202701")
    assert january.partial_year == 2027


@pytest.mark.parametrize(("run_date", "end_month"), [
    (date(2026, 11, 1), "202610"),
    (date(2026, 11, 16), "202610"),
    (date(2026, 11, 30), "202610"),
    (date(2027, 1, 1), "202612"),
    (date(2027, 1, 31), "202612"),
])
def test_service_end_month_is_previous_month_at_month_boundaries(run_date, end_month):
    assert refresh_rentals.service_end_month(run_date) == end_month


def test_published_current_has_complete_monthly_summary():
    current = dataset.select("current")
    log = json.loads(refresh_rentals.REFRESH_LOG.read_text(encoding="utf-8"))["runs"][-1]
    assert log["status"] == "complete"
    assert current.end_month == log["data_end_month"]
    assert current.small_path.exists() and current.apartment_path.exists()
    assert log["d050"]["status"] == "통과"
    assert log["source_summary"]["by_month"]["202608"]["csv_retained"] > 0
    assert log["source_summary"]["by_month"]["202609"]["api_month_rows"] > 0
    assert "duplicate_true" in log["derived_columns"]["by_source"]["api_month"]
    assert current.end_month == refresh_rentals.service_end_month(date.fromisoformat(log["run_date"]))
    assert log["in_progress"]["month"] == date.fromisoformat(log["run_date"]).strftime("%Y%m")
    assert not log["in_progress"]["included_in_current"]
    assert log["in_progress"]["month"] not in log["source_summary"]["by_month"]
    assert all(row["계약일"] <= current.data_end for path in (current.small_path, current.apartment_path)
               for row in engine.load_processed(path))


def test_api_month_rebuild_and_log_append(tmp_path):
    api = {("apartment", "deokjin", "202609"): [{"NO": "1"}]}
    first, summary = refresh_rentals.merge_source_rows({}, api, "202609")
    second, _ = refresh_rentals.merge_source_rows({}, api, "202609")
    assert first == second
    assert len(first["apartment", "deokjin", 2026]) == 1
    assert summary["by_month"]["202609"]["api_month_rows"] == 1
    path = tmp_path / "log.json"
    refresh_rentals._append_log({"status": "failed"}, path)
    refresh_rentals._append_log({"status": "complete"}, path)
    assert [run["status"] for run in json.loads(path.read_text(encoding="utf-8"))["runs"]] == [
        "failed", "complete",
    ]


def test_last_three_completed_api_months_refetch(tmp_path, monkeypatch):
    calls = []

    def fake_group(kind, gu, month, _audit, *, refresh=False):
        calls.append((month, refresh))
        return [{"NO": "1"}] if month in {"202609", "202610", "202701"} else []

    monkeypatch.setattr(refresh_rentals, "_api_group", fake_group)
    monkeypatch.setattr(refresh_rentals.fetch_rtms, "SERVICES", ("apartment",))
    monkeypatch.setattr(refresh_rentals.fetch_rtms, "DISTRICTS", ("deokjin",))
    monkeypatch.setattr(refresh_rentals.fetch_rtms, "raw_path", lambda *_: tmp_path / "absent.xml")
    groups = refresh_rentals.collect_api("202612", "202701", {})
    assert ("202610", True) in calls
    assert ("202611", True) in calls
    assert ("202612", True) in calls
    assert ("202701", True) in calls
    assert groups["apartment", "deokjin", "202701"] == [{"NO": "1"}]


def test_in_progress_api_rows_are_raw_only(tmp_path, monkeypatch):
    calls = []

    def fake_group(kind, gu, month, _audit, *, refresh=False):
        calls.append((month, refresh))
        return [{"NO": "1"}] if month == "202611" else []

    monkeypatch.setattr(refresh_rentals, "_api_group", fake_group)
    monkeypatch.setattr(refresh_rentals.fetch_rtms, "SERVICES", ("apartment",))
    monkeypatch.setattr(refresh_rentals.fetch_rtms, "DISTRICTS", ("deokjin",))
    monkeypatch.setattr(refresh_rentals.fetch_rtms, "raw_path", lambda *_: tmp_path / "absent.xml")
    groups = refresh_rentals.collect_api("202610", "202611", {}, reuse_saved=True)
    assert groups["apartment", "deokjin", "202611"] == [{"NO": "1"}]
    merged, summary = refresh_rentals.merge_source_rows({}, groups, "202610")
    assert not merged.get(("apartment", "deokjin", 2026))
    assert "202611" not in summary["by_month"]
    next_month, next_summary = refresh_rentals.merge_source_rows({}, groups, "202611")
    assert len(next_month["apartment", "deokjin", 2026]) == 1
    assert next_summary["by_month"]["202611"]["api_month_rows"] == 1
    assert ("202611", False) in calls


@pytest.mark.parametrize("run_date", [date(2027, 1, 15), date(2027, 6, 15)])
def test_saved_csv_period_corrections_survive_moving_window(run_date, tmp_path, monkeypatch):
    kind, gu, year = "apartment", "wansan", 2024
    area_field = refresh_rentals.audit.AREA_COLUMNS[kind][0]

    def transaction(month, day, built_year):
        return {"NO": "1", "계약년월": month, "계약일": str(day),
                "시군구": "전북특별자치도 전주시 완산구 효자동3가",
                area_field: "59.0", "보증금(만원)": "500", "월세금(만원)": "35",
                "전월세구분": "월세", "계약구분": "신규", "번지": "101",
                "단지명": "테스트아파트", "건축년도": str(built_year),
                "층": "3", "계약기간": "-"}

    untouched = transaction("202410", 5, 2010)
    november = transaction("202411", 5, 2014)
    december = transaction("202412", 5, 2013)
    originals = {(kind, gu, year): [untouched, november, december]}
    saved = {
        "202411": [transaction("202411", 5, 2015), transaction("202411", 20, 2015)],
        "202412": [transaction("202412", 5, 2014)],
    }
    for month in saved:
        (tmp_path / f"{month}.xml").touch()
    calls = []

    def raw_path(_kind, _gu, month, _page):
        return tmp_path / f"{month}.xml"

    def fake_group(_kind, _gu, month, _audit, *, refresh=False, offline=False):
        calls.append((month, offline))
        return saved.get(month, [])

    monkeypatch.setattr(refresh_rentals.fetch_rtms, "SERVICES", (kind,))
    monkeypatch.setattr(refresh_rentals.fetch_rtms, "DISTRICTS", (gu,))
    monkeypatch.setattr(refresh_rentals.fetch_rtms, "raw_path", raw_path)
    monkeypatch.setattr(refresh_rentals, "_api_group", fake_group)
    end_month = refresh_rentals.service_end_month(run_date)
    groups = refresh_rentals.collect_api(end_month, run_date.strftime("%Y%m"), {}, reuse_saved=True)
    assert ("202411", True) in calls and ("202412", True) in calls
    assert not any(month == "202410" for month, _ in calls)
    merged, summary = refresh_rentals.merge_source_rows(originals, groups, end_month)
    rows = merged[kind, gu, year]
    assert [(row, origin) for row, origin in rows if row["계약년월"] == "202410"] == [
        (untouched, "csv"),
    ]
    assert [row["건축년도"] for row, _ in rows if row["계약년월"] == "202411"] == [
        "2015", "2015",
    ]
    assert [row["건축년도"] for row, _ in rows if row["계약년월"] == "202412"] == ["2014"]
    assert summary["by_month"]["202411"]["build_year_updated"] == 1
    assert summary["by_month"]["202411"]["api_only_added"] == 1
    assert summary["by_month"]["202412"]["build_year_updated"] == 1
    assert summary["by_month"]["202410"] == {"csv_retained": 1}


@pytest.mark.parametrize(("end_month", "first"), [
    ("202612", "202501"), ("202705", "202506"),
])
def test_recheck_window_stays_recent_even_with_older_saved_pages(end_month, first, monkeypatch):
    captured = []

    def fake_compare(**kwargs):
        captured.append(kwargs)
        return {"status": "통과"}

    monkeypatch.setattr(refresh_rentals.compare_rtms_csv, "compare", fake_compare)
    refresh_rentals.reconcile_recent(end_month)
    assert captured[0]["first"] == first
    assert captured[0]["last"] == "202608"


def test_current_bytes_unchanged_with_saved_pages(tmp_path, monkeypatch):
    if not refresh_rentals.audit.RAW.exists() or not refresh_rentals.fetch_rtms.raw_path(
            "apartment", "wansan", "202411", 1).exists():
        pytest.skip("Local raw CSV and API pages are not available")
    monkeypatch.setattr(refresh_rentals.fetch_rtms, "request_page",
                        lambda *_: pytest.fail("Current verification must not call the API"))
    before = {name: (refresh_rentals.CURRENT / name).read_bytes() for name in (
        "valid_small_monthly.csv", "valid_apartment_monthly.csv",
    )}
    fetch_audit = {"calls": 0, "pages": [], "failures": []}
    groups = refresh_rentals.collect_api("202610", "202611", fetch_audit, reuse_saved=True)
    merged, _ = refresh_rentals.merge_source_rows(refresh_rentals.csv_groups(), groups, "202610")
    small, apartment, _ = refresh_rentals.normalize_groups(merged, "202610")
    refresh_rentals._write_table(tmp_path / "valid_small_monthly.csv", small)
    refresh_rentals._write_table(tmp_path / "valid_apartment_monthly.csv", apartment)
    assert fetch_audit["calls"] == 0
    for name, content in before.items():
        assert (tmp_path / name).read_bytes() == content
        assert (refresh_rentals.CURRENT / name).read_bytes() == content


def test_failed_recheck_keeps_previous_current(tmp_path, monkeypatch):
    current = tmp_path / "current"
    current.mkdir()
    metadata = current / "metadata.json"
    metadata.write_text('{"data_end_month":"202610"}', encoding="utf-8")
    monkeypatch.setattr(refresh_rentals, "CURRENT", current)
    monkeypatch.setattr(refresh_rentals, "csv_groups", dict)
    monkeypatch.setattr(refresh_rentals, "collect_api", lambda *_, **__: {
        ("apartment", "deokjin", "202611"): [{"NO": "1"}],
    })
    monkeypatch.setattr(refresh_rentals, "today_kst", lambda: date(2026, 11, 16))
    monkeypatch.setattr(refresh_rentals, "reconcile_recent", lambda *_: (_ for _ in ()).throw(
        refresh_rentals.RefreshError("D-050 recheck failed")))
    monkeypatch.setattr(refresh_rentals, "publish_current", lambda *_: pytest.fail("must not publish"))
    recorded = []
    monkeypatch.setattr(refresh_rentals, "_append_log", recorded.append)
    with pytest.raises(refresh_rentals.RefreshError, match="D-050"):
        refresh_rentals.refresh()
    assert metadata.read_text(encoding="utf-8") == '{"data_end_month":"202610"}'
    assert recorded[0]["status"] == "failed"
