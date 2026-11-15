"""Stop at the first D-050 mismatch between saved CSV and official RTMS API."""

from __future__ import annotations

import json
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

from src import analyze_rentals as audit
from src import fetch_rtms, rtms_to_rows
from src.jurent import commute

OUT = audit.ROOT / "outputs/audit/rtms_api_vs_csv.json"
FIELDS = ("계약일", "법정동", "면적", "보증금", "월세", "전월세구분", "계약구분", "건축년도")


def _decimal(value: str) -> str:
    try:
        return str(Decimal(value.replace(",", "").strip()).normalize())
    except InvalidOperation:
        return value.strip()


def core(row: dict[str, str], kind: str) -> tuple[str, ...]:
    """Keep repeats: D-023 forbids de-duplicating identical contracts."""
    ym, day = row["계약년월"].strip(), row["계약일"].strip()
    signed = f"{ym[:4]}-{ym[4:]}-{int(day):02d}"
    area = audit.AREA_COLUMNS[kind][0]
    return (signed, row["시군구"].split()[-1], _decimal(row[area]),
            _decimal(row["보증금(만원)"]), _decimal(row["월세금(만원)"]),
            row["전월세구분"].strip(), audit.contract_label(row["계약구분"]),
            row.get("건축년도", "").strip())


def differences(csv_rows: list[dict[str, str]], api_rows: list[dict[str, str]], kind: str) -> dict:
    csv_keys = Counter(core(row, kind) for row in csv_rows)
    api_keys = Counter(core(row, kind) for row in api_rows)
    csv_only, api_only = csv_keys - api_keys, api_keys - csv_keys

    def examples(counter: Counter) -> list[dict]:
        return [{"fields": dict(zip(FIELDS, key, strict=True)), "count": count}
                for key, count in sorted(counter.items())[:5]]

    differing_fields = []
    for index, field in enumerate(FIELDS):
        left = Counter(key[index] for key in csv_keys.elements())
        right = Counter(key[index] for key in api_keys.elements())
        if left != right:
            differing_fields.append({"field": field,
                                     "csv_only": sum((left - right).values()),
                                     "api_only": sum((right - left).values()),
                                     "csv_examples": sorted((left - right).items())[:5],
                                     "api_examples": sorted((right - left).items())[:5]})
    return {"csv_rows": len(csv_rows), "api_rows": len(api_rows),
            "csv_only_rows": sum(csv_only.values()), "api_only_rows": sum(api_only.values()),
            "csv_only_examples": examples(csv_only), "api_only_examples": examples(api_only),
            "differing_fields": differing_fields}


def _valid(row: dict[str, str], kind: str, gu: str) -> dict | None:
    area, _ = audit.area_with_basis(kind, row)
    item = {"type": kind, "gu": gu, "dong": row["시군구"].split()[-1], "area": area,
            "deposit": audit.number(row["보증금(만원)"]), "monthly": audit.number(row["월세금(만원)"]),
            "tenure": row["전월세구분"].strip()}
    return item if audit.valid_small_monthly(item) else None


def scope_counts(csv_rows: list[dict[str, str]], api_rows: list[dict[str, str]], kind: str, gu: str) -> dict:
    """D-011 valid rows in each D-017 campus and school-specific D-045 commute-only area."""
    selections = {}
    for campus, place in audit.CAMPUS_AREAS.items():
        if place["gu"] != gu:
            continue
        selections[f"campus:{campus}"] = set(place["dongs"])
        for school in commute.SCHOOLS_BY_CAMPUS[campus]:
            selections[f"commute:{school}"] = {
                entry["dong"] for entry in commute.commute_rows(campus, school)
                if not entry["campus_area"]
            }
    left = [_valid(row, kind, gu) for row in csv_rows]
    right = [_valid(row, kind, gu) for row in api_rows]
    return {name: {"csv": sum(row is not None and row["dong"] in dongs for row in left),
                   "api": sum(row is not None and row["dong"] in dongs for row in right)}
            for name, dongs in selections.items()}


def save(result: dict, path: Path = OUT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def compare(*, first: str = fetch_rtms.FIRST_MONTH, last: str = fetch_rtms.LAST_MONTH,
            raw_root: Path = fetch_rtms.RAW, out: Path = OUT) -> dict:
    result: dict = {"period": [first, last], "status": "진행 중", "checked": [],
                    "calls_this_run": 0, "failures": []}
    fetch_audit: dict = {"calls": 0, "pages": [], "failures": []}
    try:
        for month in fetch_rtms.month_range(first, last):
            for kind in fetch_rtms.SERVICES:
                for gu in fetch_rtms.DISTRICTS:
                    _, _, source = audit.read_csv(audit.RAW / f"{kind}_{gu}_{month[:4]}.csv")
                    csv_rows = [row for row in source if row["계약년월"].strip() == month]
                    items = fetch_rtms.fetch_group(kind, gu, month, fetch_audit, root=raw_root)
                    api_rows = [rtms_to_rows.convert_item(item, kind, gu, month, number)
                                for number, item in enumerate(items, 1)]
                    diff = differences(csv_rows, api_rows, kind)
                    scopes = scope_counts(csv_rows, api_rows, kind, gu)
                    entry = {"month": month, "housing_type": kind, "gu": gu, **diff,
                             "valid_scope_counts": scopes}
                    result["checked"].append(entry)
                    if (diff["csv_rows"] != diff["api_rows"] or diff["csv_only_rows"]
                            or diff["api_only_rows"] or any(v["csv"] != v["api"] for v in scopes.values())):
                        result["status"] = "불일치"
                        result["first_mismatch"] = {"month": month, "housing_type": kind,
                                                    "gu": gu, "differing_fields": diff["differing_fields"]}
                        return result
        result["status"] = "일치"
        return result
    except (fetch_rtms.FetchError, ValueError) as exc:
        result["status"] = "확인 불가"
        result["reason"] = str(exc)
        raise
    finally:
        result["calls_this_run"] = fetch_audit["calls"]
        result["failures"] = fetch_audit["failures"]
        result["saved_page_count"] = len(list(raw_root.glob("*/*.xml")))
        save(result, out)


def main() -> None:
    result = compare()
    print(f"T4 {result['status']}: 대조 {len(result['checked'])}그룹, 호출 {result['calls_this_run']}회")
    if result["status"] == "불일치":
        first = result["first_mismatch"]
        fields = ", ".join(row["field"] for row in first["differing_fields"])
        print(f"첫 불일치: {first['month']} {first['housing_type']} {first['gu']}, 필드: {fields or '행 조합'}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
