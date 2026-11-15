"""Offline checks for the raw RTMS collector, export conversion, and D-050 gate."""

from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from src import analyze_rentals as rentals
from src import compare_rtms_csv, fetch_rtms, rtms_to_rows


def response(items: list[dict[str, str]], total: int) -> bytes:
    root = ET.Element("response")
    ET.SubElement(ET.SubElement(root, "header"), "resultCode").text = "00"
    body = ET.SubElement(root, "body")
    ET.SubElement(body, "totalCount").text = str(total)
    container = ET.SubElement(body, "items")
    for values in items:
        item = ET.SubElement(container, "item")
        for key, value in values.items():
            ET.SubElement(item, key).text = value
    return ET.tostring(root, encoding="utf-8")


def audit() -> dict:
    return {"calls": 0, "pages": [], "failures": []}


def test_pages_are_stored_byte_for_byte_and_reused_offline(tmp_path, monkeypatch):
    pages = [response([{"dealDay": "1"}], 2), response([{"dealDay": "2"}], 2)]
    calls = []
    monkeypatch.setattr(fetch_rtms, "load_key", lambda: "secret-key")

    def request(kind, gu, month, page, key):
        calls.append(page)
        assert key == "secret-key"
        return pages[page - 1]

    monkeypatch.setattr(fetch_rtms, "request_page", request)
    first = audit()
    assert len(fetch_rtms.fetch_group("apartment", "wansan", "202501", first, root=tmp_path)) == 2
    assert calls == [1, 2]
    assert first["calls"] == 2
    for page, original in enumerate(pages, 1):
        assert fetch_rtms.raw_path("apartment", "wansan", "202501", page, tmp_path).read_bytes() == original
    monkeypatch.setattr(fetch_rtms, "request_page", lambda *args: pytest.fail("Cached page was refetched"))
    monkeypatch.setattr(fetch_rtms, "load_key", lambda: pytest.fail("Cache read requested a key"))
    second = audit()
    assert len(fetch_rtms.fetch_group("apartment", "wansan", "202501", second, root=tmp_path)) == 2
    assert second["calls"] == 0
    assert all(page["cached"] for page in second["pages"])


def test_api_failure_records_only_safe_code_and_never_writes_key(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(fetch_rtms, "load_key", lambda: "secret-key")
    bad = b"<response><header><resultCode>22</resultCode><resultMsg>error</resultMsg></header></response>"
    monkeypatch.setattr(fetch_rtms, "request_page", lambda *args: bad)
    log = audit()
    with pytest.raises(fetch_rtms.FetchError, match="API result code 22"):
        fetch_rtms.fetch_group("apartment", "wansan", "202501", log, root=tmp_path)
    assert log["calls"] == 1
    assert log["failures"][0]["reason"] == "API result code 22"
    assert "secret-key" not in json.dumps(log) + capsys.readouterr().out
    assert not list(tmp_path.rglob("*.xml"))


def test_converter_matches_csv_columns_amounts_blank_contract_and_d011_area():
    item = {"sggCd": "52111", "umdNm": "효자동2가", "dealYear": "2025", "dealMonth": "1",
            "dealDay": "3", "deposit": " 1,000 ", "monthlyRent": " 30 ", "totalFloorAr": "15.00",
            "buildYear": "2017", "contractType": " ", "contractTerm": "25.01~27.01"}
    row = rtms_to_rows.convert_item(item, "detached_multiunit", "wansan", "202501", 1)
    assert list(row) == list(rtms_to_rows.csv_columns("detached_multiunit"))
    assert (row["보증금(만원)"], row["월세금(만원)"], row["계약구분"]) == ("1,000", "30", "-")
    assert rentals.contract_label(row["계약구분"]) == "미기재"
    assert (row["계약년월"], row["계약일"], row["계약기간"]) == ("202501", "3", "202501~202701")
    assert (row["전월세구분"], row["번지"]) == ("월세", "")
    assert rentals.area_with_basis("detached_multiunit", row) == (15.0, "계약")
    for value, expected in (("14.99", False), ("15", True), ("45", True), ("45.01", False)):
        row["계약면적(㎡)"] = value
        area, _ = rentals.area_with_basis("detached_multiunit", row)
        assert rentals.valid_small_monthly({"area": area, "deposit": rentals.number(row["보증금(만원)"]),
                                             "monthly": rentals.number(row["월세금(만원)"]),
                                             "tenure": row["전월세구분"]}) is expected
    assert rtms_to_rows.convert_item({**item, "totalFloorAr": "43.915"},
                                     "detached_multiunit", "wansan", "202501", 1)["계약면적(㎡)"] == "43.92"
    assert rtms_to_rows.convert_item({**item, "totalFloorAr": "33.185"},
                                     "detached_multiunit", "wansan", "202501", 1)["계약면적(㎡)"] == "33.19"
    apartment = {**item, "excluUseAr": "45", "aptNm": "테스트단지", "monthlyRent": "0"}
    converted = rtms_to_rows.convert_item(apartment, "apartment", "wansan", "202501", 1)
    assert rentals.area_with_basis("apartment", converted) == (45.0, "전용")
    assert converted["전월세구분"] == "전세"
    assert converted["단지명"] == "테스트단지"


def test_full_gate_records_other_field_mismatch_after_all_months(tmp_path, monkeypatch):
    old = {month: {"계약년월": month, "계약일": "1", "시군구": "전북특별자치도 전주시 완산구 효자동2가",
                   "전용면적(㎡)": "15", "보증금(만원)": "500", "월세금(만원)": "29",
                   "전월세구분": "월세", "계약구분": "-", "건축년도": "2020"}
           for month in ("202501", "202502")}
    monkeypatch.setattr(compare_rtms_csv.audit, "read_csv", lambda path: ("", [], list(old.values())))
    monkeypatch.setattr(fetch_rtms, "SERVICES", {"apartment": "test"})
    monkeypatch.setattr(fetch_rtms, "DISTRICTS", {"wansan": "52111"})
    calls = []

    def fetch(kind, gu, month, log, **kwargs):
        calls.append((kind, gu, month))
        return [{}]

    monkeypatch.setattr(compare_rtms_csv.fetch_rtms, "fetch_group", fetch)
    monkeypatch.setattr(compare_rtms_csv.rtms_to_rows, "convert_item", lambda item, kind, gu, month, number:
                        {**old[month], "월세금(만원)": "30"} if month == "202501" else old[month])
    monkeypatch.setattr(compare_rtms_csv, "scope_counts", lambda *args: {})
    out = tmp_path / "result.json"
    result = compare_rtms_csv.compare(first="202501", last="202502", raw_root=tmp_path, out=out)
    assert result["status"] == "불일치"
    assert calls == [("apartment", "wansan", "202501"), ("apartment", "wansan", "202502")]
    assert len(result["checked"]) == 2
    assert result["other_field_failures"][0]["month"] == "202501"
    assert [row["field"] for row in result["other_field_failures"][0]["differing_fields"]] == ["월세"]
    assert json.loads(out.read_text(encoding="utf-8"))["checked"][0]["csv_only_rows"] == 1


def test_build_year_one_percent_boundary_and_complex_grouping(monkeypatch):
    monkeypatch.setattr(fetch_rtms, "SERVICES", {"apartment": "test"})
    monkeypatch.setattr(fetch_rtms, "DISTRICTS", {"wansan": "52111"})

    def row(index, year):
        return {"계약년월": "202501", "계약일": "1", "시군구": "전북특별자치도 전주시 완산구 평화동1가",
                "전용면적(㎡)": "38.64", "보증금(만원)": str(index), "월세금(만원)": "30",
                "전월세구분": "월세", "계약구분": "신규", "건축년도": year,
                "번지": "123", "단지명": "한단지"}

    csv_rows = [row(index, "1992") for index in range(100)]
    for changed in (1, 2):
        api_rows = [row(index, "1991" if index < changed else "1992") for index in range(100)]
        diff = compare_rtms_csv.differences(csv_rows, api_rows, "apartment")
        changes = compare_rtms_csv.build_year_changes(csv_rows, api_rows, "apartment")
        result = {"period": ["202501", "202501"], "checked": [
            {"month": "202501", "housing_type": "apartment", "gu": "wansan", **diff,
             "valid_scope_counts": {}}
        ]}
        compare_rtms_csv.summarize(result, [
            {"month": "202501", "housing_type": "apartment", "gu": "wansan", **change}
            for change in changes
        ])
        assert diff["transaction_csv_only_rows"] == diff["transaction_api_only_rows"] == 0
        assert result["summary"]["build_year_changed_rows"] == changed
        assert result["status"] == ("통과" if changed == 1 else "불일치")
        assert result["build_year_by_complex"][0]["단지명"] == "한단지"
        assert result["build_year_by_complex"][0]["changed_rows"] == changed


def test_chunked_fetch_log_accumulates_call_counts(tmp_path, monkeypatch):
    def fetch(kind, gu, month, log, **kwargs):
        log["calls"] += 1
        return []

    monkeypatch.setattr(fetch_rtms, "fetch_group", fetch)
    path = tmp_path / "log.json"
    fetch_rtms.run("202501", "202501", ["apartment"], ["wansan"], root=tmp_path, log=path)
    fetch_rtms.run("202502", "202502", ["apartment"], ["wansan"], root=tmp_path, log=path)
    logged = json.loads(path.read_text(encoding="utf-8"))
    assert logged["baseline_saved_pages"] == 0
    assert logged["total_calls"] == 2
    assert [run["calls"] for run in logged["runs"]] == [1, 1]


def test_month_range_and_missing_offline_page(tmp_path):
    assert fetch_rtms.month_range("202512", "202601") == ["202512", "202601"]
    with pytest.raises(ValueError):
        fetch_rtms.month_range("202513", "202601")
    with pytest.raises(fetch_rtms.FetchError, match="Saved response missing"):
        fetch_rtms.fetch_group("apartment", "wansan", "202501", audit(), offline=True, root=Path(tmp_path))
