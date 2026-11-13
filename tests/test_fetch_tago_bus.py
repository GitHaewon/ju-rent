"""Check the TAGO raw-byte cache without calling an external API."""

import json

import pytest

from src import fetch_tago_bus as bus


def test_raw_content_cached_without_key_and_korean_name_survives(tmp_path):
    secret = "test-secret-123"
    env = tmp_path / ".env"
    env.write_text(f"DATA_GO_KR_SERVICE_KEY={secret}\n", encoding="utf-8")
    raw = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<response><body><items><item><nodeid>JUB1</nodeid>'
        '<nodenm>전주대학교</nodenm><gpslati>35.8</gpslati>'
        '<gpslong>127.1</gpslong></item></items><totalCount>1</totalCount>'
        '</body></response>'
    ).encode()
    calls = []

    class FakeResponse:
        def __init__(self):
            self.content = raw
            self.status_code = 200
            self.headers = {"content-type": "application/xml"}

    def fake_get(url, *, params, timeout):
        calls.append((url, params, timeout))
        return FakeResponse()

    kwargs = {"raw_dir": tmp_path / "raw", "env_file": env, "get": fake_get}
    first, meta, cached = bus.fetch_raw("stops", "stops_35010", {"cityCode": "35010"}, **kwargs)
    second, _, cached_second = bus.fetch_raw("stops", "stops_35010", {"cityCode": "35010"}, **kwargs)

    assert (first, second) == (raw, raw)
    assert cached is False and cached_second is True
    assert len(calls) == 1
    assert calls[0][1]["serviceKey"] == secret
    assert (tmp_path / "raw/stops_35010.xml").read_bytes() == raw
    assert bus.inspect_xml(raw)["names_with_replacement"] == 0
    assert bus.inspect_xml(raw)["fields"] == ["gpslati", "gpslong", "nodeid", "nodenm"]
    assert meta["xml_declaration"] == '<?xml version="1.0" encoding="UTF-8"'
    assert secret not in (tmp_path / "raw/stops_35010.meta.json").read_text(encoding="utf-8")
    assert json.loads((tmp_path / "raw/call_log.json").read_text(encoding="utf-8")) == ["stops_35010"]


def test_cache_name_and_parameters_are_not_reused_for_other_requests(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "city.xml").write_bytes(b"<response />")
    (raw_dir / "city.meta.json").write_text(
        json.dumps({"operation": "city_codes", "parameters": {}}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="different request"):
        bus.fetch_raw("stops", "city", {"cityCode": "35010"}, raw_dir=raw_dir)
    with pytest.raises(ValueError, match="Unsafe cache name"):
        bus.fetch_raw("city_codes", "../outside", {}, raw_dir=raw_dir)
    with pytest.raises(ValueError, match="service key"):
        bus.fetch_raw("city_codes", "safe", {"serviceKey": "inline"}, raw_dir=raw_dir)
