"""Convert saved RTMS XML items to the preserved export's CSV columns."""

from __future__ import annotations

import argparse
import csv
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path

from src import analyze_rentals as audit
from src import fetch_rtms

TYPE_LABEL = {
    "apartment": "아파트",
    "multifamily": "연립다세대",
    "detached_multiunit": "단독다가구",
    "officetel": "오피스텔",
}
GU_LABEL = {"wansan": "완산구", "deokjin": "덕진구"}
AREA_FIELD = {
    "apartment": "excluUseAr",
    "multifamily": "excluUseAr",
    "detached_multiunit": "totalFloorAr",
    "officetel": "excluUseAr",
}
NAME_FIELD = {"apartment": "aptNm", "multifamily": "mhouseNm", "officetel": "offiNm"}
TERM = re.compile(r"^(\d{2})\.(\d{2})~(\d{2})\.(\d{2})$")
LOT = re.compile(r"^(\d+)(?:-(\d+))?$")


@lru_cache(maxsize=4)
def csv_columns(kind: str) -> tuple[str, ...]:
    if kind not in TYPE_LABEL:
        raise ValueError("Unknown housing type")
    reference = audit.RAW / f"{kind}_wansan_2025.csv"
    return tuple(audit.read_csv(reference)[1])


def _amount(value: str) -> Decimal | None:
    try:
        return Decimal(value.replace(",", "").strip())
    except InvalidOperation:
        return None


def _term(value: str) -> str:
    match = TERM.fullmatch(value.strip())
    return "-" if not match else f"20{match[1]}{match[2]}~20{match[3]}{match[4]}"


def _area(value: str, kind: str) -> str:
    cleaned = value.strip()
    places = "0.01" if kind == "detached_multiunit" else "0.0001"
    try:
        area = Decimal(cleaned).quantize(Decimal(places), rounding=ROUND_HALF_UP)
        return f"{area:.2f}" if kind == "detached_multiunit" else f"{area:.4f}"
    except InvalidOperation:
        return cleaned


def convert_item(item: dict[str, str], kind: str, gu: str, month: str, sequence: int) -> dict[str, str]:
    """Build one export-shaped row, keeping API values in their original ten-thousand-won unit."""
    if kind not in TYPE_LABEL or gu not in GU_LABEL:
        raise ValueError("Unknown housing type or district")
    if item.get("sggCd", "").strip() != fetch_rtms.DISTRICTS[gu]:
        raise ValueError("API district differs from request")
    year, deal_month, day = (item.get(key, "").strip() for key in ("dealYear", "dealMonth", "dealDay"))
    if not (year.isdigit() and deal_month.isdigit() and day.isdigit()
            and f"{int(year):04d}{int(deal_month):02d}" == month):
        raise ValueError("API contract month differs from request")
    monthly = _amount(item.get("monthlyRent", ""))
    jibun = item.get("jibun", "").strip()
    lot = LOT.fullmatch(jibun)
    contract_type = item.get("contractType", "").strip() or "-"
    right = item.get("useRRRight", "").strip() or "-"
    values = {
        "NO": str(sequence),
        "시군구": f"전북특별자치도 전주시 {GU_LABEL[gu]} {item.get('umdNm', '').strip()}",
        "번지": jibun,
        "본번": lot[1].zfill(4) if lot else "",
        "부번": (lot[2] or "0").zfill(4) if lot else "",
        "단지명": item.get(NAME_FIELD.get(kind, ""), "").strip(),
        "건물명": item.get("mhouseNm", "").strip(),
        "전월세구분": "월세" if monthly is not None and monthly > 0 else "전세" if monthly == 0 else "",
        audit.AREA_COLUMNS[kind][0]: _area(item.get(AREA_FIELD[kind], ""), kind),
        "계약년월": month,
        "계약일": str(int(day)),
        "보증금(만원)": item.get("deposit", "").strip(),
        "월세금(만원)": item.get("monthlyRent", "").strip(),
        "층": item.get("floor", "").strip(),
        "건축년도": item.get("buildYear", "").strip(),
        "도로명": item.get("roadnm", "").strip(),
        "계약기간": _term(item.get("contractTerm", "")),
        "계약구분": contract_type,
        "갱신요구권 사용": right,
        "종전계약 보증금(만원)": item.get("preDeposit", "").strip(),
        "종전계약 월세(만원)": item.get("preMonthlyRent", "").strip(),
        "도로조건": "",
        "주택유형": TYPE_LABEL[kind],
    }
    return {column: values.get(column, "") for column in csv_columns(kind)}


def convert_group(kind: str, gu: str, month: str, *, raw_root: Path = fetch_rtms.RAW) -> list[dict[str, str]]:
    audit_log: dict = {"calls": 0, "pages": [], "failures": []}
    items = fetch_rtms.fetch_group(kind, gu, month, audit_log, offline=True, root=raw_root)
    return [convert_item(item, kind, gu, month, index) for index, item in enumerate(items, 1)]


def write_csv(rows: list[dict[str, str]], kind: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_columns(kind))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--month", required=True)
    parser.add_argument("--kind", choices=TYPE_LABEL, required=True)
    parser.add_argument("--gu", choices=GU_LABEL, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = convert_group(args.kind, args.gu, args.month)
    write_csv(rows, args.kind, args.output)
    print(f"변환 완료: {len(rows)}행")


if __name__ == "__main__":
    main()
