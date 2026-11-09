"""Audit Jeonju RTMS exports, retaining the verified 2021-2025 baseline."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "audit"
OUTPUTS = ROOT / "outputs"
TYPES = {
    "아파트": "apartment",
    "연립다세대": "multifamily",
    "단독다가구": "detached_multiunit",
    "오피스텔": "officetel",
}
GUS = {"전주시 완산구": "wansan", "전주시 덕진구": "deokjin"}
BASELINE_YEARS = range(2021, 2026)
YEARS = range(2021, 2027)
PARTIAL_YEAR = 2026
RECENT_INCOMPLETE_MONTHS = {9, 10}
CANDIDATE_TOP_DONGS_PER_GU = 5
CAMPUS_DONGS = {"효자동2가", "효자동3가"}
CAMPUS_AREAS = {
    "효자동권": {"gu": "wansan", "dongs": ("효자동2가", "효자동3가")},
    "전북대권": {"gu": "deokjin", "dongs": ("덕진동1가", "금암동")},
}
CAMPUS_GROUPS = (
    ("효자동권", "전주대학교·전주비전대학교", "효자동2가", "wansan"),
    ("전북대권", "전북대학교", "덕진동1가", "deokjin"),
)
AREA_COLUMNS = {
    "apartment": ("전용면적(㎡)", "전용"),
    "multifamily": ("전용면적(㎡)", "전용"),
    "officetel": ("전용면적(㎡)", "전용"),
    "detached_multiunit": ("계약면적(㎡)", "계약"),
}
MIN_AREA_SQM = 15
MAX_AREA_SQM = 45
MONTHLY_BIN_EDGES = (20, 30, 40, 50)  # 만 원; 하한 포함, 상한 미포함


def number(value: str) -> float | None:
    try:
        return float(value.replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def read_csv(path: Path):
    with path.open(encoding="cp949", newline="") as fh:
        lines = fh.readlines()
    try:
        header = next(i for i, line in enumerate(lines) if line.startswith('"NO",'))
    except StopIteration as exc:
        raise RuntimeError(f"Missing CSV header: {path}") from exc
    notes = "".join(lines[:header])
    reader = csv.DictReader(lines[header:])
    fields = reader.fieldnames or []
    return notes, fields, list(reader)


def validate_export(path: Path, notes: str, fields: list[str], kind: str, gu: str, year: int):
    """Fail closed if the downloaded search filters or D-011 inputs differ."""
    search_lines = [item[0].strip() for item in csv.reader(notes.splitlines()) if item]
    if not any("검색조건" in line for line in search_lines):
        raise RuntimeError(f"Missing search conditions: {path}")
    filters = dict(line.split(":", 1) for line in search_lines if ":" in line)
    filters = {key.strip(): value.strip() for key, value in filters.items()}
    kind_ko = next(label for label, code in TYPES.items() if code == kind)
    gu_ko = next(label for label, code in GUS.items() if code == gu)
    end = "10-31" if year == PARTIAL_YEAR else "12-31"
    expected_filters = {
        "계약일자": f"{year}-01-01 ~ {year}-{end}",
        "실거래구분": f"{kind_ko}(전월세)",
        "주소구분": "지번주소",
        "시군구": gu_ko,
        "읍면동": "전체",
        "면적": "전체",
        "금액선택": "전체",
    }
    for key, expected in expected_filters.items():
        if filters.get(key) != expected:
            raise RuntimeError(f"Wrong {key} in {path}: {filters.get(key)!r}")
    required = {
        "NO", "시군구", "계약년월", "계약일", "전월세구분",
        "보증금(만원)", "월세금(만원)", "계약구분", AREA_COLUMNS[kind][0],
    }
    missing = required - set(fields)
    if missing or len(fields) != len(set(fields)):
        raise RuntimeError(f"Invalid CSV columns in {path}: missing={sorted(missing)}")


def area_with_basis(kind: str, row: dict[str, str]) -> tuple[float | None, str]:
    column, basis = AREA_COLUMNS[kind]
    return number(row.get(column, "")), basis


def contract_label(value: str) -> str:
    value = value.strip()
    return "미기재" if value in {"", "-"} else value


def valid_small_monthly(row: dict) -> bool:
    return (
        row["area"] is not None
        and MIN_AREA_SQM <= row["area"] <= MAX_AREA_SQM
        and row["deposit"] is not None
        and row["deposit"] >= 0
        and row["monthly"] is not None
        and row["monthly"] > 0
        and row["tenure"] == "월세"
    )


def analytic(row: dict) -> bool:
    return row["dong"] in CAMPUS_DONGS and valid_small_monthly(row)


def period_flags(year: int, month: int) -> dict[str, bool]:
    return {
        "partial_year": year == PARTIAL_YEAR,
        "incomplete_recent": year == PARTIAL_YEAR and month in RECENT_INCOMPLETE_MONTHS,
    }


def monthly_bin(monthly: float) -> str:
    if monthly < MONTHLY_BIN_EDGES[0]:
        return "under_20"
    if monthly < MONTHLY_BIN_EDGES[1]:
        return "20_to_29"
    if monthly < MONTHLY_BIN_EDGES[2]:
        return "30_to_39"
    if monthly < MONTHLY_BIN_EDGES[3]:
        return "40_to_49"
    return "50_plus"


def campus_area_of(row: dict) -> str | None:
    """Return the D-017 legal-dong proxy, preserving gu boundaries."""
    for name, area in CAMPUS_AREAS.items():
        if row["gu"] == area["gu"] and row["dong"] in area["dongs"]:
            return name
    return None


def summarize_campus_areas(rows: list[dict]) -> dict:
    """Count D-011 samples and masked address combinations in each D-017 area."""
    result = {}
    for name, area in CAMPUS_AREAS.items():
        valid = [r for r in rows if campus_area_of(r) == name and valid_small_monthly(r)]
        by_year = [
            {
                "year": year,
                "partial_year": year == PARTIAL_YEAR,
                "count": sum(r["year"] == year for r in valid),
                "by_type": {
                    kind: sum(r["year"] == year and r["type"] == kind for r in valid)
                    for kind in TYPES.values()
                },
            }
            for year in YEARS
        ]
        address_rows = [r for r in valid if r["road"] and r["lot"]]
        addresses = Counter((r["dong"], r["road"], r["lot"]) for r in address_rows)
        top3 = sorted(addresses.items(), key=lambda item: (-item[1], item[0]))[:3]
        result[name] = {
            "gu": area["gu"],
            "dongs": list(area["dongs"]),
            "total_valid_small_monthly": len(valid),
            "by_year": by_year,
            "by_type": {kind: sum(r["type"] == kind for r in valid) for kind in TYPES.values()},
            "address_concentration": {
                "address_rule": "법정동+원본 도로명+원본 번지 문자열; 마스킹 번지는 개별 건물 식별 불가",
                "address_present_rows": len(address_rows),
                "address_missing_rows": len(valid) - len(address_rows),
                "masked_lot_rows": sum("*" in r["lot"] for r in valid),
                "top3": [
                    {"dong": dong, "road": road, "lot": lot, "count": count}
                    for (dong, road, lot), count in top3
                ],
                "top3_rows": sum(count for _, count in top3),
                "top3_share_pct_of_all": round(100 * sum(count for _, count in top3) / len(valid), 2)
                if valid else 0.0,
            },
        }
    return result


def write_rationale_outputs(rows: list[dict], counts: dict) -> None:
    """Write T9 monthly shares and T10 D-011 trends from the same validated rows."""
    target = OUTPUTS / "rationale"
    target.mkdir(parents=True, exist_ok=True)
    excluded_complexes = {
        item["name"] for item in counts["apartment_deokjin_2026_april"]["top_complexes"][:2]
    }
    excluded_name_lots = {
        (item["name"], item["lot"])
        for item in counts["apartment_deokjin_top_two_all_years"]["complexes"]
    }

    def excluded_all_years(row: dict) -> bool:
        return (
            row["gu"] == "deokjin" and row["type"] == "apartment"
            and (row["complex"], row["lot"]) in excluded_name_lots
        )

    def excluded_april_complex(row: dict) -> bool:
        return (
            row["year"] == PARTIAL_YEAR and row["month"] == 4
            and row["gu"] == "deokjin" and row["type"] == "apartment"
            and row["complex"] in excluded_complexes
        )

    with (target / "monthly_share.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "scope", "variant", "year", "partial_year", "monthly_rows", "total_rows", "monthly_share_pct",
        ])
        writer.writeheader()
        for year in YEARS:
            annual = [r for r in rows if r["year"] == year]
            groups = [
                ("완산·덕진 전체", "포함", annual),
                ("완산·덕진 전체", "상위 두 단지 제외", [r for r in annual if not excluded_april_complex(r)]),
                *((name, "전체", [r for r in annual if campus_area_of(r) == name]) for name in CAMPUS_AREAS),
            ]
            for scope, variant, subset in groups:
                monthly_rows = sum(r["tenure"] == "월세" for r in subset)
                writer.writerow({
                    "scope": scope, "variant": variant, "year": year,
                    "partial_year": str(year == PARTIAL_YEAR).lower(),
                    "monthly_rows": monthly_rows, "total_rows": len(subset),
                    "monthly_share_pct": round(100 * monthly_rows / len(subset), 2) if subset else "",
                })
            subset = [r for r in annual if not excluded_all_years(r)]
            monthly_rows = sum(r["tenure"] == "월세" for r in subset)
            writer.writerow({
                "scope": "완산·덕진 전체", "variant": "두 단지 전 기간 제외", "year": year,
                "partial_year": str(year == PARTIAL_YEAR).lower(),
                "monthly_rows": monthly_rows, "total_rows": len(subset),
                "monthly_share_pct": round(100 * monthly_rows / len(subset), 2) if subset else "",
            })

    city_by_year = Counter(r["year"] for r in rows)
    city_jan_oct = Counter(r["year"] for r in rows if r["month"] <= 10)
    campus_jan_oct = Counter(
        (campus_area_of(r), r["year"]) for r in rows
        if r["month"] <= 10 and valid_small_monthly(r) and campus_area_of(r)
    )
    with (target / "campus_trend.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "scope", "year", "partial_year", "valid_small_monthly", "change_from_2021_pct",
            "city_public_rows", "city_change_from_2021_pct",
            "jan_oct_valid_small_monthly", "jan_oct_change_from_2021_pct",
            "jan_oct_city_public_rows", "jan_oct_city_change_from_2021_pct",
        ])
        writer.writeheader()
        for scope, area in counts["campus_areas"].items():
            baseline = area["by_year"][0]["count"]
            for entry in area["by_year"]:
                year = entry["year"]
                writer.writerow({
                    "scope": scope, "year": year,
                    "partial_year": str(year == PARTIAL_YEAR).lower(),
                    "valid_small_monthly": entry["count"],
                    "change_from_2021_pct": round(100 * (entry["count"] / baseline - 1), 2)
                    if baseline else "",
                    "city_public_rows": city_by_year[year],
                    "city_change_from_2021_pct": round(
                        100 * (city_by_year[year] / city_by_year[2021] - 1), 2
                    ),
                    "jan_oct_valid_small_monthly": campus_jan_oct[(scope, year)],
                    "jan_oct_change_from_2021_pct": round(
                        100 * (campus_jan_oct[(scope, year)] / campus_jan_oct[(scope, 2021)] - 1), 2
                    ) if campus_jan_oct[(scope, 2021)] else "",
                    "jan_oct_city_public_rows": city_jan_oct[year],
                    "jan_oct_city_change_from_2021_pct": round(
                        100 * (city_jan_oct[year] / city_jan_oct[2021] - 1), 2
                    ),
                })
    write_duplicate_sensitivity(rows, target)
    write_report_obligation(rows, target)


def duplicate_key(row: dict) -> tuple:
    """Treat NO-only differences within one export as sensitivity candidates."""
    return (row["type"], row["gu"], row["year"], tuple(
        (key, value) for key, value in row["raw"].items() if key != "NO"
    ))


def write_duplicate_sensitivity(rows: list[dict], target: Path) -> None:
    seen = set()
    retained = []
    for row in rows:
        key = duplicate_key(row)
        if key not in seen:
            retained.append(row)
            seen.add(key)
    columns = [
        "record_kind", "scope", "year", "housing_type", "original_rows", "duplicate_extra_rows",
        "deduplicated_rows", "original_monthly_rows", "deduplicated_monthly_rows",
        "original_monthly_share_pct", "deduplicated_monthly_share_pct",
        "original_valid_small_monthly", "deduplicated_valid_small_monthly",
    ]
    with (target / "duplicate_sensitivity.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        for year in YEARS:
            for kind in TYPES.values():
                original = [r for r in rows if r["year"] == year and r["type"] == kind]
                dedup = [r for r in retained if r["year"] == year and r["type"] == kind]
                writer.writerow({
                    "record_kind": "주택유형·연도", "scope": "완산·덕진 전체", "year": year,
                    "housing_type": kind, "original_rows": len(original),
                    "duplicate_extra_rows": len(original) - len(dedup), "deduplicated_rows": len(dedup),
                })
            for scope in ("완산·덕진 전체", *CAMPUS_AREAS):
                original = [r for r in rows if r["year"] == year and (
                    scope == "완산·덕진 전체" or campus_area_of(r) == scope
                )]
                dedup = [r for r in retained if r["year"] == year and (
                    scope == "완산·덕진 전체" or campus_area_of(r) == scope
                )]
                original_monthly = sum(r["tenure"] == "월세" for r in original)
                dedup_monthly = sum(r["tenure"] == "월세" for r in dedup)
                writer.writerow({
                    "record_kind": "범위·연도", "scope": scope, "year": year,
                    "original_rows": len(original), "duplicate_extra_rows": len(original) - len(dedup),
                    "deduplicated_rows": len(dedup), "original_monthly_rows": original_monthly,
                    "deduplicated_monthly_rows": dedup_monthly,
                    "original_monthly_share_pct": round(100 * original_monthly / len(original), 2) if original else "",
                    "deduplicated_monthly_share_pct": round(100 * dedup_monthly / len(dedup), 2) if dedup else "",
                    "original_valid_small_monthly": sum(valid_small_monthly(r) for r in original) if scope != "완산·덕진 전체" else "",
                    "deduplicated_valid_small_monthly": sum(valid_small_monthly(r) for r in dedup) if scope != "완산·덕진 전체" else "",
                })


def reporting_category(row: dict) -> str:
    """Classify contracts against the stated rent-reporting threshold."""
    if row["contract_date"] < "2021-06-01":
        return "제도 시행 전"
    return "신고 대상" if row["deposit"] > 6000 or row["monthly"] > 30 else "신고 비대상"


def write_report_obligation(rows: list[dict], target: Path) -> None:
    grouped = Counter(
        (campus_area_of(r), r["year"], 1 if r["month"] <= 6 else 2, reporting_category(r))
        for r in rows if campus_area_of(r) and valid_small_monthly(r)
    )
    with (target / "report_obligation.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["scope", "year", "half_year", "reporting_category", "rows"])
        writer.writeheader()
        for key, count in sorted(grouped.items()):
            scope, year, half, category = key
            writer.writerow({"scope": scope, "year": year, "half_year": half,
                             "reporting_category": category, "rows": count})


def write_campus_candidates(rows: list[dict], path: Path):
    """List high-sample legal dongs as candidates, without claiming adjacency."""
    valid = [r for r in rows if r["dong"] and valid_small_monthly(r)]
    by_gu_dong = Counter((r["gu"], r["dong"]) for r in valid)
    by_year_type = Counter((r["gu"], r["dong"], r["year"], r["type"]) for r in valid)
    columns = [
        "대학가", "캠퍼스", "캠퍼스_소재_법정동", "후보_법정동", "후보_선정_근거",
        "연도", "partial_year", "유효_표본_수", "아파트", "연립다세대",
        "단독다가구", "오피스텔",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        for group, campus, campus_dong, gu in CAMPUS_GROUPS:
            ranked = sorted(
                (dong for candidate_gu, dong in by_gu_dong if candidate_gu == gu),
                key=lambda dong: (-by_gu_dong[(gu, dong)], dong),
            )[:CANDIDATE_TOP_DONGS_PER_GU]
            for dong in sorted(set(ranked) | {campus_dong}):
                reason = "캠퍼스 소재" if dong == campus_dong else "구내 유효 표본 상위"
                for year in YEARS:
                    by_type = {
                        kind: by_year_type[(gu, dong, year, kind)] for kind in TYPES.values()
                    }
                    writer.writerow({
                        "대학가": group, "캠퍼스": campus,
                        "캠퍼스_소재_법정동": campus_dong,
                        "후보_법정동": dong, "후보_선정_근거": reason,
                        "연도": year, "partial_year": str(year == PARTIAL_YEAR).lower(),
                        "유효_표본_수": sum(by_type.values()),
                        "아파트": by_type["apartment"],
                        "연립다세대": by_type["multifamily"],
                        "단독다가구": by_type["detached_multiunit"],
                        "오피스텔": by_type["officetel"],
                    })


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    inputs = sorted(RAW.glob("*.csv"))
    expected_names = {
        f"{kind}_{gu}_{year}.csv"
        for kind in TYPES.values() for gu in GUS.values() for year in YEARS
    }
    if {path.name for path in inputs} != expected_names:
        raise RuntimeError(f"RTMS export set differs: missing={sorted(expected_names - {p.name for p in inputs})}")
    manifest = []
    summaries = []
    all_rows = []
    seen = set()

    for source in inputs:
        kind, gu, filename_year = source.stem.rsplit("_", 2)
        year = int(filename_year)
        notes, fields, rows = read_csv(source)
        validate_export(source, notes, fields, kind, gu, year)
        if year == PARTIAL_YEAR:
            baseline_path = RAW / f"{kind}_{gu}_2025.csv"
            _, baseline_fields, _ = read_csv(baseline_path)
            if fields != baseline_fields:
                raise RuntimeError(f"2026 columns differ from {baseline_path}: {source}")
        gu_ko = next(label for label, code in GUS.items() if code == gu)
        key = (kind, gu, year)
        if key in seen:
            raise RuntimeError(f"Duplicate export: {key}")
        seen.add(key)
        manifest_entry = {
            "type": kind, "gu": gu, "year": year, "rows": len(rows),
            "filename": source.name, "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        }
        if year == PARTIAL_YEAR:
            manifest_entry["partial_year"] = True
        manifest.append(manifest_entry)
        identical = Counter(tuple((k, v) for k, v in row.items() if k != "NO") for row in rows)
        year_bad = 0
        gu_bad = 0
        for row in rows:
            area, area_basis = area_with_basis(kind, row)
            deposit = number(row.get("보증금(만원)", ""))
            monthly = number(row.get("월세금(만원)", ""))
            contract_ym = row.get("계약년월", "").strip()
            contract_day = row.get("계약일", "").strip()
            try:
                if not re.fullmatch(r"\d{6}", contract_ym):
                    raise ValueError("invalid year-month")
                contract_date = date(int(contract_ym[:4]), int(contract_ym[4:]), int(contract_day))
            except ValueError as exc:
                raise RuntimeError(f"Invalid contract date in {source}: {contract_ym}/{contract_day}") from exc
            if year == PARTIAL_YEAR and not date(year, 1, 1) <= contract_date <= date(year, 10, 31):
                raise RuntimeError(f"2026 contract outside search period in {source}: {contract_date}")
            location = row.get("시군구", "").strip()
            dong = location.split()[-1] if location else ""
            if contract_ym[:4] != str(year):
                year_bad += 1
            if gu_ko not in location:
                gu_bad += 1
            all_rows.append({
                "type": kind, "gu": gu, "year": year, "dong": dong,
                "month": contract_date.month, "contract_ym": contract_ym,
                "contract_date": contract_date.isoformat(),
                **period_flags(year, contract_date.month),
                "area": area, "area_basis": area_basis,
                "deposit": deposit, "monthly": monthly,
                "tenure": row.get("전월세구분", "").strip(),
                "contract": contract_label(row.get("계약구분", "")),
                "road": row.get("도로명", "").strip(),
                "lot": row.get("번지", "").strip(),
                "complex": row.get("단지명", "").strip(),
                "raw": row,
            })
        summaries.append({
            "type": kind, "gu": gu, "year": year, "rows": len(rows),
            "year_mismatch": year_bad, "gu_mismatch": gu_bad,
            "identical_extra_rows": sum(n - 1 for n in identical.values() if n > 1),
            "empty": {col: sum(not r.get(col, "").strip() for r in rows) for col in rows[0] if col != "NO"} if rows else {},
        })

    expected = {(t, g, y) for t in TYPES.values() for g in GUS.values() for y in YEARS}
    if seen != expected:
        raise RuntimeError(f"Missing exports: {expected - seen}")

    baseline_rows = [r for r in all_rows if r["year"] in BASELINE_YEARS]
    current_rows = [r for r in all_rows if r["year"] == PARTIAL_YEAR]

    by_year_gu = defaultdict(int)
    by_year_type = defaultdict(int)
    by_stage = Counter()
    by_type = Counter()
    by_area_basis = Counter()
    by_dong = Counter()
    analytic_rows = []
    for r in baseline_rows:
        by_year_gu[(r["year"], r["gu"])] += 1
        by_year_type[(r["year"], r["type"])] += 1
        if r["dong"] in CAMPUS_DONGS:
            by_stage["campus_dongs_all"] += 1
            by_dong[r["dong"]] += 1
            if r["tenure"] == "월세":
                by_stage["campus_dongs_monthly"] += 1
            if analytic(r):
                by_stage["analytic"] += 1
                by_type[r["type"]] += 1
                by_area_basis[r["area_basis"]] += 1
                analytic_rows.append(r)
                if r["contract"] == "신규":
                    by_stage["analytic_new"] += 1
                elif r["contract"] == "갱신":
                    by_stage["analytic_renewal"] += 1
                else:
                    by_stage["analytic_contract_unknown"] += 1

    comparison = sorted(r["monthly"] for r in analytic_rows
                        if r["year"] == 2025 and r["dong"] == "효자동3가"
                        and r["type"] == "detached_multiunit" and 20 <= r["area"] < 30
                        and 300 <= r["deposit"] <= 700 and r["contract"] == "신규")

    def percentile(values, p):
        if not values:
            return None
        at = (len(values) - 1) * p
        low = int(at)
        high = min(low + 1, len(values) - 1)
        return values[low] * (high - at) + values[high] * (at - low)

    counts = {
        "total": len(baseline_rows),
        "year_gu": [{"year": y, "gu": g, "count": by_year_gu[(y, g)]}
                    for y in BASELINE_YEARS for g in GUS.values()],
        "year_type": [{"year": y, "type": t, "count": by_year_type[(y, t)]}
                      for y in BASELINE_YEARS for t in TYPES.values()],
        "campus_dong_counts": dict(by_dong),
        "stages": dict(by_stage),
        "analytic_by_type": dict(by_type),
        "analytic_by_area_basis": {basis: by_area_basis[basis] for basis in ("전용", "계약")},
        "analytic_by_year": {str(y): sum(r["year"] == y for r in analytic_rows) for y in BASELINE_YEARS},
        "analytic_by_contract": dict(Counter(r["contract"] for r in analytic_rows)),
        "median_monthly_2025": median(r["monthly"] for r in analytic_rows if r["year"] == 2025),
        "median_deposit_2025": median(r["deposit"] for r in analytic_rows if r["year"] == 2025),
        "analytic_2025_by_type": dict(Counter(r["type"] for r in analytic_rows if r["year"] == 2025)),
        "analytic_2025_by_dong": dict(Counter(r["dong"] for r in analytic_rows if r["year"] == 2025)),
        "analytic_2025_monthly_bins": {
            key: sum(r["year"] == 2025 and monthly_bin(r["monthly"]) == key for r in analytic_rows)
            for key in ("under_20", "20_to_29", "30_to_39", "40_to_49", "50_plus")
        },
        "analytic_2025_contract": dict(Counter(r["contract"] for r in analytic_rows if r["year"] == 2025)),
        "example_cohort": {
            "n": len(comparison), "monthly_p25": percentile(comparison, 0.25),
            "monthly_median": percentile(comparison, 0.5),
            "monthly_p75": percentile(comparison, 0.75),
            "example_40_above_or_equal": sum(v >= 40 for v in comparison),
        },
        "missing_area_campus": sum(r["dong"] in CAMPUS_DONGS and r["area"] is None for r in baseline_rows),
        "missing_price_campus": sum(r["dong"] in CAMPUS_DONGS and (r["deposit"] is None or r["monthly"] is None) for r in baseline_rows),
        "detached_rows": sum(r["type"] == "detached_multiunit" for r in baseline_rows),
        "detached_masked_lot": sum(r["type"] == "detached_multiunit" and "*" in r["lot"] for r in baseline_rows),
        "jeonju_detached_lot_masking": {
            "masked": sum(r["type"] == "detached_multiunit" and "*" in r["lot"] for r in baseline_rows),
            "total": sum(r["type"] == "detached_multiunit" for r in baseline_rows),
        },
        "campus_detached_rows": sum(r["type"] == "detached_multiunit" and r["dong"] in CAMPUS_DONGS for r in baseline_rows),
        "campus_detached_masked_lot": sum(r["type"] == "detached_multiunit" and r["dong"] in CAMPUS_DONGS and "*" in r["lot"] for r in baseline_rows),
        "detached_lot_mask_examples": Counter(r["lot"] for r in baseline_rows if r["type"] == "detached_multiunit").most_common(5),
    }
    analytic_2026 = [r for r in current_rows if analytic(r)]
    all_analytic = analytic_rows + analytic_2026
    counts["contract_by_year"] = [
        {
            "year": year, "partial_year": year == PARTIAL_YEAR,
            **{label: sum(r["year"] == year and r["contract"] == label for r in all_analytic)
               for label in ("신규", "갱신", "미기재")},
            "total": sum(r["year"] == year for r in all_analytic),
        }
        for year in YEARS
    ]
    april = [r for r in current_rows if r["type"] == "apartment" and r["gu"] == "deokjin" and r["month"] == 4]
    complex_counts = Counter(r["complex"] or "미기재" for r in april)
    top_complex, top_count = complex_counts.most_common(1)[0] if april else (None, 0)
    top_two_count = sum(count for _, count in complex_counts.most_common(2))
    other_apartment = [
        r for r in current_rows
        if r["type"] == "apartment" and r["gu"] == "deokjin" and r["month"] != 4
    ]
    counts["apartment_deokjin_2026_april"] = {
        "monthly_rows": [
            {"month": month, "count": sum(r["month"] == month for r in current_rows
                                        if r["type"] == "apartment" and r["gu"] == "deokjin")}
            for month in range(1, 11)
        ],
        "april_rows": len(april),
        "top_complex": top_complex,
        "top_complex_rows": top_count,
        "top_complex_share_pct": round(100 * top_count / len(april), 1) if april else None,
        "top_complexes": [
            {"name": name, "count": count} for name, count in complex_counts.most_common(5)
        ],
        "top_two_complexes_rows": top_two_count,
        "top_two_complexes_share_pct": round(100 * top_two_count / len(april), 1) if april else None,
        "majority_single_complex": top_count > len(april) / 2,
        "top_complex_other_months_rows": sum(r["complex"] == top_complex for r in other_apartment),
    }
    top_name_lots = []
    for name, _ in complex_counts.most_common(2):
        april_lots = {r["lot"] for r in april if r["complex"] == name}
        if len(april_lots) != 1:
            raise RuntimeError(f"N-013 complex has ambiguous April lots: {name}")
        top_name_lots.append({"name": name, "lot": next(iter(april_lots))})
    pairs = {(item["name"], item["lot"]) for item in top_name_lots}
    counts["apartment_deokjin_top_two_all_years"] = {
        "complexes": top_name_lots,
        "by_year": [
            {"year": year, "rows": sum(
                r["year"] == year and r["type"] == "apartment" and r["gu"] == "deokjin"
                and (r["complex"], r["lot"]) in pairs for r in all_rows
            )} for year in YEARS
        ],
    }
    counts["year_2026"] = {
        "partial_year": True,
        "period": "2026-01-01~2026-10-31",
        "total": len(current_rows),
        "analytic": len(analytic_2026),
        "year_gu": {gu: sum(r["gu"] == gu for r in current_rows) for gu in GUS.values()},
        "year_type": {kind: sum(r["type"] == kind for r in current_rows) for kind in TYPES.values()},
        "analytic_by_type": dict(Counter(r["type"] for r in analytic_2026)),
        "months": [
            {"month": month, "count": sum(r["month"] == month for r in current_rows),
             **period_flags(PARTIAL_YEAR, month)}
            for month in range(1, 11)
        ],
    }
    counts["campus_areas"] = summarize_campus_areas(all_rows)
    write_rationale_outputs(all_rows, counts)
    write_campus_candidates(all_rows, OUTPUTS / "campus_dong_candidates.csv")
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "file_audit.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "counts.json").write_text(json.dumps(counts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(counts, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
