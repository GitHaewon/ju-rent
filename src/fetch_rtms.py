"""Fetch official RTMS rental XML by housing type, district, and contract month."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/rtms_api"
FETCH_LOG = ROOT / "outputs/audit/rtms_fetch_log.json"
ENV = ROOT / ".env"
SERVICES = {
    "apartment": "RTMSDataSvcAptRent",
    "multifamily": "RTMSDataSvcRHRent",
    "detached_multiunit": "RTMSDataSvcSHRent",
    "officetel": "RTMSDataSvcOffiRent",
}
DISTRICTS = {"wansan": "52111", "deokjin": "52113"}
PAGE_SIZE = 1000
FIRST_MONTH = "202501"
LAST_MONTH = "202608"


class FetchError(RuntimeError):
    """An RTMS response failed validation; messages never include credentials."""


def load_key(path: Path = ENV) -> str:
    """Read the decoding key only from the local, ignored .env file."""
    if not path.exists():
        raise FetchError(".env key missing")
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.startswith("DATA_GO_KR_SERVICE_KEY="):
            key = line.split("=", 1)[1].strip().strip('"').strip("'")
            if key:
                return key
    raise FetchError(".env key missing")


def month_range(first: str, last: str) -> list[str]:
    for value in (first, last):
        if len(value) != 6 or not value.isascii() or not value.isdigit() or not 1 <= int(value[4:]) <= 12:
            raise ValueError("Months must be YYYYMM")
    start, end = int(first[:4]) * 12 + int(first[4:]) - 1, int(last[:4]) * 12 + int(last[4:]) - 1
    if start > end:
        raise ValueError("First month is after last month")
    return [f"{index // 12:04d}{index % 12 + 1:02d}" for index in range(start, end + 1)]


def raw_path(kind: str, gu: str, month: str, page: int, root: Path = RAW) -> Path:
    return root / month / f"{kind}_{gu}_p{page:04d}.xml"


def request_page(kind: str, gu: str, month: str, page: int, key: str) -> bytes:
    service = SERVICES[kind]
    endpoint = f"https://apis.data.go.kr/1613000/{service}/get{service}"
    query = urlencode({"serviceKey": key, "LAWD_CD": DISTRICTS[gu], "DEAL_YMD": month,
                       "pageNo": page, "numOfRows": PAGE_SIZE})
    try:
        with urlopen(f"{endpoint}?{query}", timeout=30) as response:
            payload = response.read()
    except HTTPError as exc:
        raise FetchError(f"HTTP {exc.code}") from None
    except (URLError, TimeoutError):
        raise FetchError("Network or time-out error") from None
    if key.encode() in payload or query.split("serviceKey=", 1)[1].split("&", 1)[0].encode() in payload:
        raise FetchError("Credential appeared in response")
    return payload


def parse_page(payload: bytes) -> tuple[list[dict[str, str]], int]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        raise FetchError("Non-XML response") from None
    code = root.findtext(".//resultCode")
    if code not in {"00", "000"}:
        raise FetchError(f"API result code {code or 'missing'}")
    total_text = root.findtext(".//totalCount")
    try:
        total = int(total_text) if total_text is not None else -1
    except ValueError:
        total = -1
    if total < 0:
        raise FetchError("Invalid totalCount")
    items = [{child.tag: (child.text or "") for child in item} for item in root.findall(".//item")]
    return items, total


def fetch_group(kind: str, gu: str, month: str, audit: dict, *, refresh: bool = False,
                offline: bool = False, root: Path = RAW) -> list[dict[str, str]]:
    """Reuse saved pages; fetch only absent pages unless refresh is requested."""
    if kind not in SERVICES or gu not in DISTRICTS:
        raise ValueError("Invalid type, district, or month")
    month_range(month, month)
    items: list[dict[str, str]] = []
    page = 1
    expected_total = None
    while True:
        path = raw_path(kind, gu, month, page, root)
        if path.exists() and not refresh:
            payload = path.read_bytes()
            cached = True
        else:
            if offline:
                raise FetchError("Saved response missing")
            audit["calls"] += 1
            try:
                key = load_key()
                payload = request_page(kind, gu, month, page, key)
                page_items, total = parse_page(payload)
            except FetchError as exc:
                audit["failures"].append({"kind": kind, "gu": gu, "month": month,
                                          "page": page, "reason": str(exc)})
                raise
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_bytes(payload)
            temporary.replace(path)
            cached = False
        if cached:
            page_items, total = parse_page(payload)
        if expected_total is None:
            expected_total = total
        elif total != expected_total:
            raise FetchError("totalCount changed during pagination")
        items.extend(page_items)
        audit["pages"].append({"kind": kind, "gu": gu, "month": month, "page": page,
                               "cached": cached, "rows": len(page_items)})
        if len(items) >= total:
            if len(items) != total:
                raise FetchError("Page rows exceed totalCount")
            return items
        if not page_items or page >= 1000:
            raise FetchError("Pagination ended before totalCount")
        page += 1


def run(first: str = FIRST_MONTH, last: str = LAST_MONTH, kinds: list[str] | None = None,
        gus: list[str] | None = None, *, refresh: bool = False, root: Path = RAW,
        log: Path = FETCH_LOG) -> dict:
    audit: dict = {"months": [first, last], "calls": 0, "pages": [], "failures": [], "status": "running"}
    try:
        for month in month_range(first, last):
            for kind in kinds or SERVICES:
                for gu in gus or DISTRICTS:
                    fetch_group(kind, gu, month, audit, refresh=refresh, root=root)
    except (FetchError, ValueError):
        audit["status"] = "failed"
        raise
    else:
        audit["status"] = "complete"
    finally:
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-month", default=FIRST_MONTH)
    parser.add_argument("--to-month", default=LAST_MONTH)
    parser.add_argument("--kind", choices=SERVICES)
    parser.add_argument("--gu", choices=DISTRICTS)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    try:
        audit = run(args.from_month, args.to_month,
                    [args.kind] if args.kind else None, [args.gu] if args.gu else None,
                    refresh=args.refresh)
    except (FetchError, ValueError) as exc:
        print(f"수집 중단: {exc}; 호출 수는 outputs/audit/rtms_fetch_log.json 참조")
        raise SystemExit(1) from None
    print(f"수집 완료: 호출 {audit['calls']}회, 저장·재사용 페이지 {len(audit['pages'])}개")


if __name__ == "__main__":
    main()
