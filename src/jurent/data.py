"""Build a reproducible D-011 rental table from the preserved RTMS exports."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter
from datetime import date
from pathlib import Path

from src import analyze_rentals as audit

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
MANIFEST = ROOT / "data" / "audit" / "manifest.json"
PROCESSED = ROOT / "data" / "processed" / "valid_small_monthly.csv"
PROCESSED_AUDIT = ROOT / "data" / "processed" / "valid_small_monthly_audit.json"
APARTMENT_PROCESSED = ROOT / "data" / "processed" / "valid_apartment_monthly.csv"
APARTMENT_AUDIT = ROOT / "data" / "processed" / "valid_apartment_monthly_audit.json"
DATE_START = date(2021, 1, 1)
DATE_END = date(2026, 10, 31)
APARTMENT_MIN_AREA_SQM = 40
APARTMENT_MAX_AREA_SQM = 132
AGE_BANDS = ("5년 미만", "5~9년", "10~19년", "20년 이상", "미기재")
COLUMNS = (
    "계약일", "대학가", "법정동", "주택유형", "면적", "면적기준", "보증금", "월세",
    "계약구분", "건축년도", "경과연수", "경과연수구간", "완전중복여부", "incomplete_recent", "단지명", "번지",
)


def age_band(age: int | None) -> str:
    if age is None:
        return "미기재"
    if age < 5:
        return "5년 미만"
    if age < 10:
        return "5~9년"
    if age < 20:
        return "10~19년"
    return "20년 이상"


def construction_year(value: str) -> int | None:
    parsed = audit.number(value)
    if parsed is None or not parsed.is_integer() or parsed <= 0:
        return None
    return int(parsed)


def valid_apartment_monthly(item: dict) -> bool:
    return (
        item["type"] == "apartment"
        and item["area"] is not None
        and math.isfinite(item["area"])
        and APARTMENT_MIN_AREA_SQM <= item["area"] <= APARTMENT_MAX_AREA_SQM
        and item["deposit"] is not None
        and math.isfinite(item["deposit"])
        and item["deposit"] >= 0
        and item["monthly"] is not None
        and math.isfinite(item["monthly"])
        and item["monthly"] > 0
        and item["tenure"] == "월세"
    )


def normalized_rows() -> tuple[list[dict], list[dict]]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    expected = {entry["filename"]: entry for entry in manifest}
    files = sorted(RAW.glob("*.csv"))
    if {path.name for path in files} != set(expected):
        raise RuntimeError("Raw CSV set does not match manifest")
    small_rows = []
    apartment_rows = []
    for path in files:
        entry = expected[path.name]
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise RuntimeError(f"Raw CSV hash differs: {path.name}")
        kind, gu, year_text = path.stem.rsplit("_", 2)
        year = int(year_text)
        notes, fields, rows = audit.read_csv(path)
        audit.validate_export(path, notes, fields, kind, gu, year)
        if year == audit.PARTIAL_YEAR:
            _, prior_fields, _ = audit.read_csv(RAW / f"{kind}_{gu}_2025.csv")
            if fields != prior_fields:
                raise RuntimeError(f"2026 columns differ from 2025: {path.name}")
        if len(rows) != entry["rows"]:
            raise RuntimeError(f"Raw CSV row count differs: {path.name}")
        duplicates = Counter(tuple((key, value) for key, value in row.items() if key != "NO") for row in rows)
        for row in rows:
            contract_ym = row["계약년월"].strip()
            contract_day = row["계약일"].strip()
            try:
                signed_on = date(int(contract_ym[:4]), int(contract_ym[4:]), int(contract_day))
            except ValueError as exc:
                raise RuntimeError(f"Invalid contract date: {path.name}") from exc
            if signed_on.year != year or not DATE_START <= signed_on <= DATE_END:
                raise RuntimeError(f"Contract outside export period: {path.name}")
            location = row["시군구"].strip()
            gu_name = next(label for label, code in audit.GUS.items() if code == gu)
            if gu_name not in location:
                raise RuntimeError(f"Wrong gu in row: {path.name}")
            area, basis = audit.area_with_basis(kind, row)
            item = {
                "type": kind, "gu": gu, "dong": location.split()[-1],
                "area": area, "area_basis": basis,
                "deposit": audit.number(row["보증금(만원)"]),
                "monthly": audit.number(row["월세금(만원)"]),
                "tenure": row["전월세구분"].strip(),
            }
            is_small = audit.valid_small_monthly(item)
            is_apartment = valid_apartment_monthly(item)
            if not is_small and not is_apartment:
                continue
            built_year = construction_year(row.get("건축년도", ""))
            age = signed_on.year - built_year if built_year is not None else None
            fingerprint = tuple((key, value) for key, value in row.items() if key != "NO")
            normalized = {
                "계약일": signed_on.isoformat(),
                "대학가": audit.campus_area_of(item) or "",
                "법정동": item["dong"], "주택유형": kind,
                "면적": area, "면적기준": basis,
                "보증금": item["deposit"], "월세": item["monthly"],
                "계약구분": audit.contract_label(row.get("계약구분", "")),
                "건축년도": built_year if built_year is not None else "",
                "경과연수": age if age is not None else "",
                "경과연수구간": age_band(age),
                "완전중복여부": str(duplicates[fingerprint] > 1).lower(),
                "incomplete_recent": str(audit.period_flags(signed_on.year, signed_on.month)["incomplete_recent"]).lower(),
                "단지명": ("" if kind == "detached_multiunit" else
                        row.get("건물명", "") if kind == "multifamily" else row.get("단지명", "")),
                "번지": row.get("번지", ""),
            }
            if is_small:
                small_rows.append(normalized)
            if is_apartment:
                apartment_rows.append(normalized)
    return small_rows, apartment_rows


def build_processed() -> Path:
    rows, apartment_rows = normalized_rows()
    negative_age = [row for row in rows if row["경과연수"] != "" and row["경과연수"] < 0]
    if any(row["경과연수"] != -1 for row in negative_age):
        raise RuntimeError("D-031 only defines the minus-one construction-year case")
    PROCESSED.parent.mkdir(parents=True, exist_ok=True)
    with PROCESSED.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    with APARTMENT_PROCESSED.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(apartment_rows)
    summary = {
        "source_manifest": "data/audit/manifest.json",
        "processed_sha256": hashlib.sha256(PROCESSED.read_bytes()).hexdigest(),
        "total_rows": len(rows),
        "by_year": {str(year): sum(row["계약일"].startswith(str(year)) for row in rows)
                    for year in audit.YEARS},
        "by_campus": {campus: sum(row["대학가"] == campus for row in rows)
                      for campus in audit.CAMPUS_AREAS},
        "negative_age_rows": len(negative_age),
        "negative_age_values": {"-1": len(negative_age)},
        "negative_age_by_type": {kind: sum(row["주택유형"] == kind for row in negative_age)
                                 for kind in audit.TYPES.values()},
    }
    PROCESSED_AUDIT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    apartment_summary = {
        "source_manifest": "data/audit/manifest.json",
        "processed_sha256": hashlib.sha256(APARTMENT_PROCESSED.read_bytes()).hexdigest(),
        "total_rows": len(apartment_rows),
        "by_year": {str(year): sum(row["계약일"].startswith(str(year)) for row in apartment_rows)
                    for year in audit.YEARS},
    }
    APARTMENT_AUDIT.write_text(json.dumps(apartment_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return PROCESSED


def load_processed(path: Path = PROCESSED) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


if __name__ == "__main__":
    build_processed()
