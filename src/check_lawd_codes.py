"""Compare official RTMS API region-code results with retained CSV exports."""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "outputs" / "audit" / "lawd_code_check.json"
SERVICES = {
    "apartment": "RTMSDataSvcAptRent",
    "multifamily": "RTMSDataSvcRHRent",
    "detached_multiunit": "RTMSDataSvcSHRent",
    "officetel": "RTMSDataSvcOffiRent",
}
MONTHS = ("202312", "202402")
CODES = {"wansan": ("45111", "52111"), "deokjin": ("45113", "52113")}


def load_key() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8-sig").splitlines():
        if line.startswith("DATA_GO_KR_SERVICE_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get("DATA_GO_KR_SERVICE_KEY", "")


def csv_count(kind: str, gu: str, month: str) -> int:
    from src.analyze_rentals import read_csv

    _, _, rows = read_csv(RAW / f"{kind}_{gu}_{month[:4]}.csv")
    return sum(row.get("계약년월") == month for row in rows)


def api_count(service: str, key: str, code: str, month: str) -> int:
    endpoint = f"https://apis.data.go.kr/1613000/{service}/get{service}"
    params = urlencode({"serviceKey": key, "LAWD_CD": code, "DEAL_YMD": month,
                        "pageNo": 1, "numOfRows": 1})
    try:
        with urlopen(f"{endpoint}?{params}", timeout=20) as response:
            content = response.read()
    except HTTPError as exc:
        if exc.code in {401, 403}:
            raise PermissionError("키 미활성") from None
        raise RuntimeError(f"API HTTP {exc.code}") from None
    except URLError:
        raise RuntimeError("API network unavailable") from None
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        raise RuntimeError("API returned non-XML content") from None
    result_code = root.findtext(".//resultCode")
    if result_code not in {"00", "000"}:
        message = root.findtext(".//resultMsg", "")
        if result_code in {"01", "03", "12", "20", "22", "30"} or "SERVICE_KEY" in message or "SERVICE KEY" in message:
            raise PermissionError("키 미활성")
        raise RuntimeError(f"API result code {result_code}")
    count = root.findtext(".//totalCount")
    if count is None:
        raise RuntimeError("API totalCount missing")
    return int(count)


def main() -> None:
    key = load_key()
    if not key:
        raise RuntimeError(".env API key missing")
    result = {
        "source": "https://www.data.go.kr/data/15126474/openapi.do",
        "checked_on": date.today().isoformat(),
        "months": list(MONTHS), "rows": [], "status": "진행 중",
    }
    try:
        for month in MONTHS:
            for kind, service in SERVICES.items():
                for gu, codes in CODES.items():
                    expected = csv_count(kind, gu, month)
                    for code in codes:
                        count = api_count(service, key, code, month)
                        result["rows"].append({
                            "month": month, "housing_type": kind, "gu": gu, "lawd_code": code,
                            "api_rows": count, "csv_rows": expected,
                            "difference": count - expected,
                        })
    except PermissionError:
        result["status"] = "키 미활성"
    except RuntimeError as exc:
        result["status"] = "확인 불가"
        result["reason"] = str(exc)
    else:
        result["status"] = "조회 완료"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(result["status"])


if __name__ == "__main__":
    main()
