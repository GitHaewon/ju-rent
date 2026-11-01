"""Reproduce the Jeonju RTMS CSV audit (2021-2025, downloaded 2026-11-02)."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "audit"
TYPES = {
    "아파트": "apartment",
    "연립다세대": "multifamily",
    "단독다가구": "detached_multiunit",
    "오피스텔": "officetel",
}
GUS = {"전주시 완산구": "wansan", "전주시 덕진구": "deokjin"}
YEARS = range(2021, 2026)
CAMPUS_DONGS = {"효자동2가", "효자동3가"}


def number(value: str) -> float | None:
    try:
        return float(value.replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def read_csv(path: Path):
    with path.open(encoding="cp949", newline="") as fh:
        lines = fh.readlines()
    header = next(i for i, line in enumerate(lines) if line.startswith('"NO",'))
    notes = "".join(lines[:header])
    rows = list(csv.DictReader(lines[header:]))
    return notes, rows


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    inputs = sorted(RAW.glob("*.csv"))
    if len(inputs) != 40:
        raise RuntimeError(f"Expected 40 RTMS exports, found {len(inputs)}")
    manifest = []
    summaries = []
    all_rows = []
    seen = set()

    for source in inputs:
        kind, gu, filename_year = source.stem.rsplit("_", 2)
        notes, rows = read_csv(source)
        m_date = re.search(r"계약일자\s*:\s*(\d{4})-01-01\s*~\s*(\d{4})-12-31", notes)
        m_gu = re.search(r"시군구\s*:\s*(전주시\s*(?:완산구|덕진구))", notes)
        if not m_date or not m_gu or m_date.group(1) != m_date.group(2):
            raise RuntimeError(f"Unexpected filter metadata: {source}")
        year = int(m_date.group(1))
        gu_ko = re.sub(r"\s+", " ", m_gu.group(1))
        if gu != GUS[gu_ko] or filename_year != str(year):
            raise RuntimeError(f"Filename and export metadata disagree: {source}")
        key = (kind, gu, year)
        if key in seen:
            raise RuntimeError(f"Duplicate export: {key}")
        seen.add(key)
        manifest.append({
            "type": kind, "gu": gu, "year": year, "rows": len(rows),
            "filename": source.name, "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        })
        identical = Counter(tuple((k, v) for k, v in row.items() if k != "NO") for row in rows)
        year_bad = 0
        gu_bad = 0
        for row in rows:
            area = number(row.get("전용면적(㎡)", row.get("계약면적(㎡)", "")))
            deposit = number(row.get("보증금(만원)", ""))
            monthly = number(row.get("월세금(만원)", ""))
            contract_ym = row.get("계약년월", "").strip()
            location = row.get("시군구", "").strip()
            dong = location.split()[-1] if location else ""
            if contract_ym[:4] != str(year):
                year_bad += 1
            if gu_ko not in location:
                gu_bad += 1
            all_rows.append({
                "type": kind, "gu": gu, "year": year, "dong": dong,
                "area": area, "deposit": deposit, "monthly": monthly,
                "tenure": row.get("전월세구분", "").strip(),
                "contract": row.get("계약구분", "").strip(),
                "road": row.get("도로명", "").strip(),
                "lot": row.get("번지", "").strip(),
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

    def analytic(r):
        return (r["dong"] in CAMPUS_DONGS and r["area"] is not None
                and 15 <= r["area"] <= 45 and r["deposit"] is not None
                and r["deposit"] >= 0 and r["monthly"] is not None
                and r["monthly"] > 0 and r["tenure"] == "월세")

    by_year_gu = defaultdict(int)
    by_year_type = defaultdict(int)
    by_stage = Counter()
    by_type = Counter()
    by_dong = Counter()
    analytic_rows = []
    for r in all_rows:
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
        "total": len(all_rows),
        "year_gu": [{"year": y, "gu": g, "count": by_year_gu[(y, g)]}
                    for y in YEARS for g in GUS.values()],
        "year_type": [{"year": y, "type": t, "count": by_year_type[(y, t)]}
                      for y in YEARS for t in TYPES.values()],
        "campus_dong_counts": dict(by_dong),
        "stages": dict(by_stage),
        "analytic_by_type": dict(by_type),
        "analytic_by_year": {str(y): sum(r["year"] == y for r in analytic_rows) for y in YEARS},
        "analytic_by_contract": dict(Counter(r["contract"] or "미기재" for r in analytic_rows)),
        "median_monthly_2025": median(r["monthly"] for r in analytic_rows if r["year"] == 2025),
        "median_deposit_2025": median(r["deposit"] for r in analytic_rows if r["year"] == 2025),
        "analytic_2025_by_type": dict(Counter(r["type"] for r in analytic_rows if r["year"] == 2025)),
        "analytic_2025_by_dong": dict(Counter(r["dong"] for r in analytic_rows if r["year"] == 2025)),
        "analytic_2025_monthly_bins": {
            "under_20": sum(r["year"] == 2025 and r["monthly"] < 20 for r in analytic_rows),
            "20_to_29": sum(r["year"] == 2025 and 20 <= r["monthly"] < 30 for r in analytic_rows),
            "30_to_39": sum(r["year"] == 2025 and 30 <= r["monthly"] < 40 for r in analytic_rows),
            "40_to_49": sum(r["year"] == 2025 and 40 <= r["monthly"] < 50 for r in analytic_rows),
            "50_plus": sum(r["year"] == 2025 and r["monthly"] >= 50 for r in analytic_rows),
        },
        "analytic_2025_contract": dict(Counter(r["contract"] or "미기재" for r in analytic_rows if r["year"] == 2025)),
        "example_cohort": {
            "n": len(comparison), "monthly_p25": percentile(comparison, 0.25),
            "monthly_median": percentile(comparison, 0.5),
            "monthly_p75": percentile(comparison, 0.75),
            "example_40_above_or_equal": sum(v >= 40 for v in comparison),
        },
        "missing_area_campus": sum(r["dong"] in CAMPUS_DONGS and r["area"] is None for r in all_rows),
        "missing_price_campus": sum(r["dong"] in CAMPUS_DONGS and (r["deposit"] is None or r["monthly"] is None) for r in all_rows),
        "detached_rows": sum(r["type"] == "detached_multiunit" for r in all_rows),
        "detached_masked_lot": sum(r["type"] == "detached_multiunit" and "*" in r["lot"] for r in all_rows),
        "campus_detached_rows": sum(r["type"] == "detached_multiunit" and r["dong"] in CAMPUS_DONGS for r in all_rows),
        "campus_detached_masked_lot": sum(r["type"] == "detached_multiunit" and r["dong"] in CAMPUS_DONGS and "*" in r["lot"] for r in all_rows),
        "detached_lot_mask_examples": Counter(r["lot"] for r in all_rows if r["type"] == "detached_multiunit").most_common(5),
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "file_audit.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "counts.json").write_text(json.dumps(counts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(counts, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
