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
    write_campus_candidates(all_rows, OUTPUTS / "campus_dong_candidates.csv")
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "file_audit.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "counts.json").write_text(json.dumps(counts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(counts, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
