"""Audit every D-050 overlap cell, then apply the transaction and build-year gates."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

from src import analyze_rentals as audit
from src import fetch_rtms, rtms_to_rows
from src.jurent import commute

OUT = audit.ROOT / "outputs/audit/rtms_api_vs_csv.json"
FIELDS = ("계약일", "법정동", "면적", "보증금", "월세", "전월세구분", "계약구분",
          "번지", "단지명", "건축년도")
TRANSACTION_FIELDS = FIELDS[:-1]
MAX_BUILD_YEAR_DIFFERENCE_PCT = 1
MAX_API_ONLY_PCT = Decimal("0.5")


def _decimal(value: str) -> str:
    try:
        return format(Decimal(value.replace(",", "").strip()).normalize(), "f")
    except InvalidOperation:
        return value.strip()


def core(row: dict[str, str], kind: str) -> tuple[str, ...]:
    """Use comparable complex fields and keep repeats (D-023)."""
    ym, day = row["계약년월"].strip(), row["계약일"].strip()
    signed = f"{ym[:4]}-{ym[4:]}-{int(day):02d}"
    area = audit.AREA_COLUMNS[kind][0]
    # Detached API responses have no lot or building name. The masked CSV lot
    # remains in the audit record but cannot be used as a cross-source key.
    _, lot, name = _complex(row, kind)
    if kind == "detached_multiunit":
        lot, name = "", ""
    return (signed, row["시군구"].split()[-1], _decimal(row[area]),
            _decimal(row["보증금(만원)"]), _decimal(row["월세금(만원)"]),
            row["전월세구분"].strip(), audit.contract_label(row["계약구분"]),
            lot, name, row.get("건축년도", "").strip())


def differences(csv_rows: list[dict[str, str]], api_rows: list[dict[str, str]], kind: str) -> dict:
    csv_keys = Counter(core(row, kind) for row in csv_rows)
    api_keys = Counter(core(row, kind) for row in api_rows)
    csv_only, api_only = csv_keys - api_keys, api_keys - csv_keys
    csv_transactions = Counter(key[:-1] for key in csv_keys.elements())
    api_transactions = Counter(key[:-1] for key in api_keys.elements())
    csv_transaction_only = csv_transactions - api_transactions
    api_transaction_only = api_transactions - csv_transactions
    year_changes, unmatched_csv, unmatched_api = pair_records(csv_rows, api_rows, kind)

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
            "differing_fields": differing_fields,
            "transaction_csv_only_rows": len(unmatched_csv),
            "transaction_api_only_rows": len(unmatched_api),
            "transaction_csv_only_examples": [
                {"fields": dict(zip(TRANSACTION_FIELDS, key, strict=True)), "count": count}
                for key, count in sorted(csv_transaction_only.items())[:5]
            ],
            "transaction_api_only_examples": [
                {"fields": dict(zip(TRANSACTION_FIELDS, key, strict=True)), "count": count}
                for key, count in sorted(api_transaction_only.items())[:5]
            ],
            "csv_only_transactions": [unmatched_transaction(row, kind) for row in unmatched_csv],
            "api_only_transactions": [unmatched_transaction(row, kind) for row in unmatched_api],
            "build_year_changed_rows": len(year_changes),
            "build_year_change_examples": year_changes[:5]}


def _complex(row: dict[str, str], kind: str) -> tuple[str, str, str]:
    name_field = "건물명" if kind == "multifamily" else "단지명"
    return (row["시군구"].split()[-1], row.get("번지", "").strip(), row.get(name_field, "").strip())


def unmatched_transaction(row: dict[str, str], kind: str) -> dict:
    dong, lot, name = _complex(row, kind)
    return {"fields": dict(zip(TRANSACTION_FIELDS, core(row, kind)[:-1], strict=True)),
            "건축년도": row.get("건축년도", "").strip(), "법정동": dong, "번지": lot, "단지명": name}


def _pair_candidates(left_rows: list[dict[str, str]], right_rows: list[dict[str, str]],
                     unused_left: set[int], unused_right: set[int]) -> list[tuple[int, int]]:
    candidates = []
    for left_index, left in enumerate(left_rows):
        for right_index, right in enumerate(right_rows):
            years_match = left.get("건축년도", "").strip() == right.get("건축년도", "").strip()
            floor = (bool(left.get("층", "").strip())
                     and left.get("층", "").strip() == right.get("층", "").strip())
            term = (left.get("계약기간", "").strip() not in ("", "-")
                    and left.get("계약기간", "").strip() == right.get("계약기간", "").strip())
            candidates.append((-int(floor and term), -int(floor), -int(term), -int(years_match),
                               left_index, right_index))
    pairs = []
    for _, _, _, _, left_index, right_index in sorted(candidates):
        if left_index in unused_left and right_index in unused_right:
            unused_left.remove(left_index)
            unused_right.remove(right_index)
            pairs.append((left_index, right_index))
    return pairs


def match_records(csv_rows: list[dict[str, str]], api_rows: list[dict[str, str]], kind: str
                  ) -> tuple[list[tuple[dict[str, str], dict[str, str]]],
                             list[dict[str, str]], list[dict[str, str]]]:
    """Pair rows within the same transaction and complex for D-050 and D-053."""
    groups: dict[tuple[str, ...], dict[str, list[dict[str, str]]]] = defaultdict(
        lambda: {"csv": [], "api": []}
    )
    for side, rows in (("csv", csv_rows), ("api", api_rows)):
        for row in rows:
            groups[core(row, kind)[:-1]][side].append(row)
    matches = []
    csv_only = []
    api_only = []
    for _, group in sorted(groups.items()):
        left_rows = sorted(group["csv"], key=lambda row: (_complex(row, kind),
                                                            row.get("층", ""),
                                                            row.get("계약기간", ""),
                                                            row.get("건축년도", "")))
        right_rows = sorted(group["api"], key=lambda row: (_complex(row, kind),
                                                             row.get("층", ""),
                                                             row.get("계약기간", ""),
                                                             row.get("건축년도", "")))
        unused_left = set(range(len(left_rows)))
        unused_right = set(range(len(right_rows)))
        for left_index, right_index in _pair_candidates(
                left_rows, right_rows, unused_left, unused_right):
            matches.append((left_rows[left_index], right_rows[right_index]))
        csv_only.extend(left_rows[index] for index in sorted(unused_left))
        api_only.extend(right_rows[index] for index in sorted(unused_right))
    return matches, csv_only, api_only


def pair_records(csv_rows: list[dict[str, str]], api_rows: list[dict[str, str]], kind: str
                 ) -> tuple[list[dict], list[dict[str, str]], list[dict[str, str]]]:
    """Record build-year changes without losing the row pairing used by refresh."""
    matches, csv_only, api_only = match_records(csv_rows, api_rows, kind)
    changes = []
    for left, right in matches:
        if left.get("건축년도", "").strip() == right.get("건축년도", "").strip():
            continue
        csv_complex = _complex(left, kind)
        api_complex = _complex(right, kind)
        changes.append({
            "transaction": dict(zip(TRANSACTION_FIELDS, core(left, kind)[:-1], strict=True)),
            "csv_build_year": left.get("건축년도", "").strip(),
            "api_build_year": right.get("건축년도", "").strip(),
            "csv_floor": left.get("층", "").strip(),
            "api_floor": right.get("층", "").strip(),
            "csv_contract_term": left.get("계약기간", "").strip(),
            "api_contract_term": right.get("계약기간", "").strip(),
            "csv_complex": dict(zip(("법정동", "번지", "단지명"), csv_complex, strict=True)),
            "api_complex": dict(zip(("법정동", "번지", "단지명"), api_complex, strict=True)),
            "complex_matches": csv_complex == api_complex,
        })
    return changes, csv_only, api_only


def build_year_changes(csv_rows: list[dict[str, str]], api_rows: list[dict[str, str]],
                       kind: str) -> list[dict]:
    return pair_records(csv_rows, api_rows, kind)[0]


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
    counts = {}
    for name, dongs in selections.items():
        csv_count = sum(row is not None and row["dong"] in dongs for row in left)
        api_count = sum(row is not None and row["dong"] in dongs for row in right)
        counts[name] = {"csv": csv_count, "api": api_count, "difference": api_count - csv_count}
    return counts


def save(result: dict, path: Path = OUT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def summarize(result: dict, changes: list[dict]) -> None:
    checked = result["checked"]
    total_rows = sum(row["csv_rows"] for row in checked)
    transaction_difference_groups = []
    api_only_transactions = []
    valid_scope_totals: dict[str, dict[str, int]] = {}
    for row in checked:
        scope_differences = {name: value for name, value in row["valid_scope_counts"].items()
                             if value["csv"] != value["api"]}
        for name, value in row["valid_scope_counts"].items():
            total = valid_scope_totals.setdefault(name, {"csv": 0, "api": 0, "difference": 0})
            total["csv"] += value["csv"]
            total["api"] += value["api"]
            total["difference"] += value["api"] - value["csv"]
        api_only_transactions.extend({"month": row["month"], "housing_type": row["housing_type"],
                                      "gu": row["gu"], **transaction}
                                     for transaction in row["api_only_transactions"])
        if row["transaction_csv_only_rows"] or row["transaction_api_only_rows"]:
            transaction_difference_groups.append({
                "month": row["month"], "housing_type": row["housing_type"], "gu": row["gu"],
                "csv_rows": row["csv_rows"], "api_rows": row["api_rows"],
                "transaction_csv_only_rows": row["transaction_csv_only_rows"],
                "transaction_api_only_rows": row["transaction_api_only_rows"],
                "differing_fields": [field for field in row["differing_fields"]
                                     if field["field"] != "건축년도"],
                "valid_scope_differences": scope_differences,
            })
    by_complex: Counter = Counter()
    for change in changes:
        complex_key = change["csv_complex"]
        key = (change["housing_type"], change["gu"], complex_key["법정동"],
               complex_key["번지"], complex_key["단지명"])
        by_complex[key] += 1
    result["build_year_by_complex"] = [
        {"housing_type": kind, "gu": gu, "법정동": dong, "번지": lot, "단지명": name,
         "changed_rows": count, "share_of_all_rows_pct": round(100 * count / total_rows, 4) if total_rows else 0}
        for (kind, gu, dong, lot, name), count in sorted(by_complex.items(),
                                                        key=lambda item: (-item[1], item[0]))
    ]
    result["build_year_changes"] = changes
    changed_count = len(changes)
    csv_only_count = sum(row["transaction_csv_only_rows"] for row in checked)
    api_only_count = sum(row["transaction_api_only_rows"] for row in checked)
    expected_groups = (len(fetch_rtms.month_range(*result["period"]))
                       * len(fetch_rtms.SERVICES) * len(fetch_rtms.DISTRICTS))
    complete = len(checked) == expected_groups and total_rows > 0
    csv_only_passed = csv_only_count == 0
    api_only_passed = (Decimal(api_only_count) * 100
                       <= Decimal(total_rows) * MAX_API_ONLY_PCT) if total_rows else False
    build_year_passed = (changed_count * 100 <= total_rows * MAX_BUILD_YEAR_DIFFERENCE_PCT
                         if total_rows else False)
    result["criteria"] = {
        "complete": {"checked_groups": len(checked), "expected_groups": expected_groups,
                     "passed": complete},
        "csv_only": {"rows": csv_only_count, "maximum_rows": 0, "passed": csv_only_passed},
        "api_only": {"rows": api_only_count,
                     "pct": round(100 * api_only_count / total_rows, 6) if total_rows else 0,
                     "maximum_pct": float(MAX_API_ONLY_PCT), "passed": api_only_passed},
        "build_year": {"rows": changed_count,
                       "pct": round(100 * changed_count / total_rows, 6) if total_rows else 0,
                       "maximum_pct": MAX_BUILD_YEAR_DIFFERENCE_PCT,
                       "passed": build_year_passed},
    }
    result["summary"] = {
        "checked_groups": len(checked), "expected_groups": expected_groups,
        "csv_rows": total_rows, "api_rows": sum(row["api_rows"] for row in checked),
        "transaction_difference_groups": len(transaction_difference_groups),
        "transaction_csv_only_rows": csv_only_count,
        "transaction_api_only_rows": api_only_count,
        "transaction_api_only_pct": result["criteria"]["api_only"]["pct"],
        "build_year_changed_rows": changed_count,
        "build_year_changed_pct": result["criteria"]["build_year"]["pct"],
        "build_year_limit_pct": MAX_BUILD_YEAR_DIFFERENCE_PCT,
        "build_year_identity_uncertain_rows": sum(not change["complex_matches"] for change in changes),
    }
    result["transaction_difference_groups"] = transaction_difference_groups
    result["api_only_transactions"] = api_only_transactions
    result["valid_scope_totals"] = valid_scope_totals
    result["status"] = "통과" if all(item["passed"] for item in result["criteria"].values()) else "불일치"


def compare(*, first: str = fetch_rtms.FIRST_MONTH, last: str = fetch_rtms.LAST_MONTH,
            raw_root: Path = fetch_rtms.RAW, out: Path = OUT) -> dict:
    result: dict = {"period": [first, last], "status": "진행 중", "checked": [],
                    "calls_this_run": 0, "failures": []}
    fetch_audit: dict = {"calls": 0, "pages": [], "failures": []}
    year_changes = []
    try:
        for month in fetch_rtms.month_range(first, last):
            for kind in fetch_rtms.SERVICES:
                for gu in fetch_rtms.DISTRICTS:
                    _, _, source = audit.read_csv(audit.RAW / f"{kind}_{gu}_{month[:4]}.csv")
                    csv_rows = [row for row in source if row["계약년월"].strip() == month]
                    items = fetch_rtms.fetch_group(kind, gu, month, fetch_audit, offline=True, root=raw_root)
                    api_rows = [rtms_to_rows.convert_item(item, kind, gu, month, number)
                                for number, item in enumerate(items, 1)]
                    diff = differences(csv_rows, api_rows, kind)
                    scopes = scope_counts(csv_rows, api_rows, kind, gu)
                    entry = {"month": month, "housing_type": kind, "gu": gu, **diff,
                             "valid_scope_counts": scopes}
                    result["checked"].append(entry)
                    for change in build_year_changes(csv_rows, api_rows, kind):
                        year_changes.append({"month": month, "housing_type": kind, "gu": gu, **change})
        summarize(result, year_changes)
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
    try:
        result = compare()
    except (fetch_rtms.FetchError, ValueError) as exc:
        print(f"T4 확인 불가: {exc}; 저장본과 outputs/audit/rtms_api_vs_csv.json 확인")
        raise SystemExit(1) from None
    summary = result["summary"]
    print(f"T4 {result['status']}: 대조 {summary['checked_groups']}그룹, "
          f"CSV에만 {summary['transaction_csv_only_rows']}행, "
          f"API에만 {summary['transaction_api_only_rows']}행 "
          f"({summary['transaction_api_only_pct']}%), "
          f"건축년도 차이 {summary['build_year_changed_rows']}행 "
          f"({summary['build_year_changed_pct']}%), 추가 호출 {result['calls_this_run']}회")
    if result["status"] == "불일치":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
