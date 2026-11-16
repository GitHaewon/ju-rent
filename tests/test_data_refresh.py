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
