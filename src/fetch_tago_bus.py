"""Cache exact TAGO response bytes for the SPEC-005 bus data audit.

Usage: python src/fetch_tago_bus.py OPERATION CACHE_NAME [key=value ...]
The cache is intentionally under data/raw/ and is excluded from commits.
"""

import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/bus/tago"
BASE_URL = "https://apis.data.go.kr/1613000"
OPERATIONS = {
    "city_codes": "BusRouteInfoInqireService/getCtyCodeList",
    "stops": "BusSttnInfoInqireService/getSttnNoList",
    "routes": "BusRouteInfoInqireService/getRouteNoList",
    "route_info": "BusRouteInfoInqireService/getRouteInfoIem",
    "route_stops": "BusRouteInfoInqireService/getRouteAcctoThrghSttnList",
    "stop_routes": "BusSttnInfoInqireService/getSttnThrghRouteList",
}


def load_service_key(env_file=None):
    """Read the only secret from .env without returning it in metadata."""
    path = env_file or ROOT / ".env"
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.startswith("DATA_GO_KR_SERVICE_KEY="):
            key = line.split("=", 1)[1].strip().strip('"').strip("'")
            if key:
                return key
    raise ValueError("DATA_GO_KR_SERVICE_KEY is missing")


def fetch_raw(operation, cache_name, parameters, *, raw_dir=None, env_file=None, get=None):
    """Fetch once; save response.content unchanged and reuse the named cache."""
    if operation not in OPERATIONS:
        raise ValueError("Unknown TAGO operation")
    if not re.fullmatch(r"[A-Za-z0-9_]+", cache_name):
        raise ValueError("Unsafe cache name")
    if "serviceKey" in parameters:
        raise ValueError("Pass the service key only through .env")

    target = raw_dir or RAW
    target.mkdir(parents=True, exist_ok=True)
    body_file = target / f"{cache_name}.xml"
    meta_file = target / f"{cache_name}.meta.json"

    if body_file.exists():
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        if meta["operation"] != operation or meta["parameters"] != parameters:
            raise ValueError("Cache name belongs to a different request")
        return body_file.read_bytes(), meta, True

    request = get or httpx.get
    response = request(
        f"{BASE_URL}/{OPERATIONS[operation]}",
        params={"serviceKey": load_service_key(env_file), **parameters},
        timeout=45,
    )
    raw = response.content
    body_file.write_bytes(raw)
    meta = {
        "operation": operation,
        "parameters": parameters,
        "http_status": response.status_code,
        "content_type": response.headers.get("content-type"),
        "xml_declaration": raw.split(b"?>", 1)[0].decode("ascii", errors="replace")
        if raw.startswith(b"<?xml")
        else None,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "raw_file": body_file.name,
    }
    meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ledger_file = target / "call_log.json"
    ledger = json.loads(ledger_file.read_text(encoding="utf-8")) if ledger_file.exists() else []
    ledger.append(cache_name)
    ledger_file.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return raw, meta, False


def inspect_xml(raw):
    """Report available fields and whether the raw XML contains damaged names."""
    root = ET.fromstring(raw)
    items = root.findall(".//item")
    names = [item.findtext("nodenm") for item in items]
    return {
        "result_code": root.findtext(".//resultCode"),
        "total_count": root.findtext(".//totalCount"),
        "rows_in_response": len(items),
        "fields": sorted({child.tag for item in items for child in item}),
        "names_with_replacement": sum("\ufffd" in name for name in names if name),
    }


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) < 2:
        raise SystemExit("Usage: fetch_tago_bus.py OPERATION CACHE_NAME [key=value ...]")
    parameters = dict(part.split("=", 1) for part in args[2:])
    raw, meta, cached = fetch_raw(args[0], args[1], parameters)
    print(json.dumps({"cached": cached, "metadata": meta, "inspection": inspect_xml(raw)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
