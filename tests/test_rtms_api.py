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
    apartment = {**item, "excluUseAr": "45", "aptNm": "테스트단지", "monthlyRent": "0"}
    converted = rtms_to_rows.convert_item(apartment, "apartment", "wansan", "202501", 1)
    assert rentals.area_with_basis("apartment", converted) == (45.0, "전용")
    assert converted["전월세구분"] == "전세"
    assert converted["단지명"] == "테스트단지"


def test_mismatch_gate_stops_at_first_month_and_names_fields(tmp_path, monkeypatch):
    old = {"계약년월": "202501", "계약일": "1", "시군구": "전북특별자치도 전주시 완산구 효자동2가",
           "전용면적(㎡)": "15", "보증금(만원)": "500", "월세금(만원)": "29",
           "전월세구분": "월세", "계약구분": "-", "건축년도": "2020"}
    new = {**old, "월세금(만원)": "30"}
    monkeypatch.setattr(compare_rtms_csv.audit, "read_csv", lambda path: ("", [], [old]))
    calls = []

    def fetch(kind, gu, month, log, **kwargs):
        calls.append((kind, gu, month))
        return [{}]

    monkeypatch.setattr(compare_rtms_csv.fetch_rtms, "fetch_group", fetch)
    monkeypatch.setattr(compare_rtms_csv.rtms_to_rows, "convert_item", lambda *args: new)
    monkeypatch.setattr(compare_rtms_csv, "scope_counts", lambda *args: {})
    out = tmp_path / "result.json"
    result = compare_rtms_csv.compare(first="202501", last="202502", raw_root=tmp_path, out=out)
    assert result["status"] == "불일치"
    assert calls == [("apartment", "wansan", "202501")]
    assert result["first_mismatch"]["month"] == "202501"
    assert [row["field"] for row in result["first_mismatch"]["differing_fields"]] == ["월세"]
    assert json.loads(out.read_text(encoding="utf-8"))["checked"][0]["csv_only_rows"] == 1


def test_month_range_and_missing_offline_page(tmp_path):
    assert fetch_rtms.month_range("202512", "202601") == ["202512", "202601"]
    with pytest.raises(ValueError):
        fetch_rtms.month_range("202513", "202601")
    with pytest.raises(fetch_rtms.FetchError, match="Saved response missing"):
        fetch_rtms.fetch_group("apartment", "wansan", "202501", audit(), offline=True, root=Path(tmp_path))
