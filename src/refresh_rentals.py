"""Refresh service rentals from preserved CSV rows and checked RTMS API pages."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import tempfile
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src import analyze_rentals as audit
from src import compare_rtms_csv, fetch_rtms, rtms_to_rows
from src.jurent import data, dataset

ROOT = Path(__file__).resolve().parents[1]
PROCESSED_ROOT = ROOT / "data/processed"
CURRENT = PROCESSED_ROOT / "current"
REFRESH_LOG = ROOT / "outputs/audit/refresh_log.json"
RECONCILE = ROOT / "outputs/audit/current_reconcile.json"
CSV_END_MONTH = "202608"
API_FIRST_MONTH = "202609"
FIRST_MONTH = "202101"


class RefreshError(RuntimeError):
    """A refresh gate failed; the previous current directory remains available."""


def today_kst() -> date:
    return datetime.now(ZoneInfo("Asia/Seoul")).date()


def _fingerprint(row: dict[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple((key, value) for key, value in row.items() if key != "NO")


def csv_groups() -> dict[tuple[str, str, int], list[dict[str, str]]]:
    """Read and verify the original annual exports without changing them."""
    manifest = json.loads(data.MANIFEST.read_text(encoding="utf-8"))
    expected = {entry["filename"]: entry for entry in manifest}
    files = sorted(audit.RAW.glob("*.csv"))
    if {path.name for path in files} != set(expected):
        raise RefreshError("Original CSV set differs from manifest")
    groups = {}
    for path in files:
        entry = expected[path.name]
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise RefreshError(f"Original CSV hash differs: {path.name}")
        kind, gu, year_text = path.stem.rsplit("_", 2)
        year = int(year_text)
        notes, fields, rows = audit.read_csv(path)
        audit.validate_export(path, notes, fields, kind, gu, year)
        if len(rows) != entry["rows"]:
            raise RefreshError(f"Original CSV row count differs: {path.name}")
        groups[kind, gu, year] = [
            row for row in rows if FIRST_MONTH <= row["계약년월"].strip() <= CSV_END_MONTH
        ]
    return groups


def _api_group(kind: str, gu: str, month: str, fetch_audit: dict,
               *, refresh: bool = False) -> list[dict[str, str]]:
    items = fetch_rtms.fetch_group(kind, gu, month, fetch_audit, refresh=refresh)
    return [rtms_to_rows.convert_item(item, kind, gu, month, index)
            for index, item in enumerate(items, 1)]


def collect_api(through_month: str, fetch_audit: dict) -> dict[tuple[str, str, str], list[dict[str, str]]]:
    """Reuse overlap pages; refetch every API-built month in the latest three."""
    groups = {}
    for month in fetch_rtms.month_range(API_FIRST_MONTH, through_month):
        refresh = month >= dataset.shift_month(through_month, -2)
        for kind in fetch_rtms.SERVICES:
            for gu in fetch_rtms.DISTRICTS:
                groups[kind, gu, month] = _api_group(kind, gu, month, fetch_audit, refresh=refresh)
    end_month = max((month for (_, _, month), rows in groups.items() if rows), default=CSV_END_MONTH)
    # The requested month can be empty. In that case the last three populated
    # API months, rather than the last three requested months, must be refreshed.
    if end_month >= API_FIRST_MONTH:
        for month in fetch_rtms.month_range(max(API_FIRST_MONTH, dataset.shift_month(end_month, -2)), end_month):
            if month >= dataset.shift_month(through_month, -2):
                continue
            for kind in fetch_rtms.SERVICES:
                for gu in fetch_rtms.DISTRICTS:
                    groups[kind, gu, month] = _api_group(kind, gu, month, fetch_audit, refresh=True)
    first = max(FIRST_MONTH, dataset.shift_month(end_month, -23))
    last = min(CSV_END_MONTH, end_month)
    if first <= last:
        for month in fetch_rtms.month_range(first, last):
            for kind in fetch_rtms.SERVICES:
                for gu in fetch_rtms.DISTRICTS:
                    key = kind, gu, month
                    if key not in groups:
                        groups[key] = _api_group(kind, gu, month, fetch_audit)
    # Previously checked pages remain the source for older CSV build-year corrections.
    for month in fetch_rtms.month_range("202501", CSV_END_MONTH):
        for kind in fetch_rtms.SERVICES:
            for gu in fetch_rtms.DISTRICTS:
                key = kind, gu, month
                if key not in groups and fetch_rtms.raw_path(kind, gu, month, 1).exists():
                    groups[key] = _api_group(kind, gu, month, fetch_audit)
    return groups


def reconcile_recent(end_month: str) -> dict:
    first = max(FIRST_MONTH, dataset.shift_month(end_month, -23))
    last = min(CSV_END_MONTH, end_month)
    if first > last:
        return {"status": "통과", "period": [], "summary": {"checked_groups": 0},
                "criteria": {"no_csv_overlap": {"passed": True}}}
    result = compare_rtms_csv.compare(first=first, last=last, out=RECONCILE)
    if result["status"] != "통과":
        raise RefreshError(f"D-050 recheck failed for {first}~{last}; previous current retained")
    return result


def merge_source_rows(
    originals: dict[tuple[str, str, int], list[dict[str, str]]],
    api_groups: dict[tuple[str, str, str], list[dict[str, str]]],
    end_month: str,
) -> tuple[dict[tuple[str, str, int], list[tuple[dict[str, str], str]]], dict]:
    """Keep CSV rows, update matched years, add late disclosures, then use API months."""
    replacements: dict[int, dict[str, str]] = {}
    additions: dict[tuple[str, str, int], list[tuple[dict[str, str], str]]] = defaultdict(list)
    monthly: dict[str, Counter] = defaultdict(Counter)
    age_band_changes = 0
    for (kind, gu, year), rows in originals.items():
        for row in rows:
            monthly[row["계약년월"].strip()]["csv_retained"] += 1
        for month in sorted({row["계약년월"].strip() for row in rows}):
            api_rows = api_groups.get((kind, gu, month))
            if api_rows is None:
                continue
            csv_month = [row for row in rows if row["계약년월"].strip() == month]
            pairs, missing_csv, api_only = compare_rtms_csv.match_records(csv_month, api_rows, kind)
            # The D-050 gate has already rejected missing CSV rows in its recent window.
            monthly[month]["csv_unmatched_to_api"] += len(missing_csv)
            for left, right in pairs:
                old_year = left.get("건축년도", "").strip()
                new_year = right.get("건축년도", "").strip()
                if old_year != new_year:
                    replacements[id(left)] = {**left, "건축년도": new_year}
                    monthly[month]["build_year_updated"] += 1
                    signed_year = int(month[:4])
                    old_age = signed_year - data.construction_year(old_year) if data.construction_year(old_year) else None
                    new_age = signed_year - data.construction_year(new_year) if data.construction_year(new_year) else None
                    age_band_changes += data.age_band(old_age) != data.age_band(new_age)
            additions[kind, gu, year].extend((row, "api_only") for row in api_only)
            monthly[month]["api_only_added"] += len(api_only)
    for (kind, gu, month), rows in api_groups.items():
        if API_FIRST_MONTH <= month <= end_month:
            additions[kind, gu, int(month[:4])].extend((row, "api_month") for row in rows)
            monthly[month]["api_month_rows"] += len(rows)
    merged = {
        key: [(replacements.get(id(row), row), "csv") for row in rows] + additions.pop(key, [])
        for key, rows in originals.items()
    }
    for key, rows in additions.items():
        merged[key] = rows
    return merged, {"by_month": {month: dict(monthly[month]) for month in sorted(monthly)},
                    "age_band_changes_from_build_year": age_band_changes}


def normalize_row(row: dict[str, str], kind: str, gu: str, duplicates: Counter,
                  end_month: str) -> tuple[dict, bool, bool] | None:
    """Apply the same D-011 rules as the fixed snapshot to one source row."""
    month = row["계약년월"].strip()
    signed = date(int(month[:4]), int(month[4:]), int(row["계약일"].strip()))
    location = row["시군구"].strip()
    gu_name = next(label for label, code in audit.GUS.items() if code == gu)
    if gu_name not in location or not FIRST_MONTH <= month <= end_month:
        raise RefreshError("Source district or contract month differs from group")
    area, basis = audit.area_with_basis(kind, row)
    item = {"type": kind, "gu": gu, "dong": location.split()[-1],
            "area": area, "area_basis": basis,
            "deposit": audit.number(row["보증금(만원)"]),
            "monthly": audit.number(row["월세금(만원)"]),
            "tenure": row["전월세구분"].strip()}
    small = audit.valid_small_monthly(item)
    apartment = data.valid_apartment_monthly(item)
    if not small and not apartment:
        return None
    built_year = data.construction_year(row.get("건축년도", ""))
    age = signed.year - built_year if built_year is not None else None
    if small and age is not None and age < -1:
        raise RefreshError(f"Construction year {built_year} is after {signed.isoformat()} "
                           f"for {kind}/{gu}; D-031 has no rule beyond minus one")
    normalized = {
        "계약일": signed.isoformat(), "대학가": audit.campus_area_of(item) or "",
        "법정동": item["dong"], "주택유형": kind, "면적": area, "면적기준": basis,
        "보증금": item["deposit"], "월세": item["monthly"],
        "계약구분": audit.contract_label(row.get("계약구분", "")),
        "건축년도": built_year if built_year is not None else "",
        "경과연수": age if age is not None else "", "경과연수구간": data.age_band(age),
        "완전중복여부": str(duplicates[_fingerprint(row)] > 1).lower(),
        "incomplete_recent": str(month in {dataset.shift_month(end_month, -1), end_month}).lower(),
        "단지명": ("" if kind == "detached_multiunit" else
                row.get("건물명", "") if kind == "multifamily" else row.get("단지명", "")),
        "번지": row.get("번지", ""),
    }
    return normalized, small, apartment


def normalize_groups(groups: dict[tuple[str, str, int], list[tuple[dict[str, str], str]]],
                     end_month: str) -> tuple[list[dict], list[dict], dict]:
    small_rows: list[dict] = []
    apartment_rows: list[dict] = []
    origin_stats: dict[str, Counter] = defaultdict(Counter)
    for (kind, gu, _), tagged in sorted(groups.items()):
        duplicates = Counter(_fingerprint(row) for row, _ in tagged)
        for row, origin in tagged:
            result = normalize_row(row, kind, gu, duplicates, end_month)
            if result is None:
                continue
            normalized, small, apartment = result
            if small:
                small_rows.append(normalized)
            if apartment:
                apartment_rows.append(normalized)
            stats = origin_stats[origin]
            instances = int(small) + int(apartment)
            stats["processed_rows"] += instances
            stats["empty_lot"] += instances * (not normalized["번지"].strip())
            stats["duplicate_true"] += instances * (normalized["완전중복여부"] == "true")
            stats["incomplete_recent_true"] += instances * (normalized["incomplete_recent"] == "true")
    snapshot_rows = data.load_processed(data.PROCESSED) + data.load_processed(data.APARTMENT_PROCESSED)
    current_rows = small_rows + apartment_rows
    derived = {
        "by_source": {origin: dict(values) for origin, values in sorted(origin_stats.items())},
        "snapshot_duplicate_true": sum(row["완전중복여부"] == "true" for row in snapshot_rows),
        "current_duplicate_true": sum(row["완전중복여부"] == "true" for row in current_rows),
        "snapshot_incomplete_recent_true": sum(row["incomplete_recent"] == "true" for row in snapshot_rows),
        "current_incomplete_recent_true": sum(row["incomplete_recent"] == "true" for row in current_rows),
        "snapshot_empty_lot": sum(not row["번지"].strip() for row in snapshot_rows),
        "current_empty_lot": sum(not row["번지"].strip() for row in current_rows),
        "note": "전체 집계 차이에는 API 추가·최근 달 이동이 함께 포함됨; 원본 CSV 기간의 주소 열은 보존",
    }
    return small_rows, apartment_rows, derived


def _write_table(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=data.COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def publish_current(small_rows: list[dict], apartment_rows: list[dict],
                    end_month: str, refreshed_on: str) -> None:
    """Build both tables off to the side and restore old current if replacement fails."""
    PROCESSED_ROOT.mkdir(parents=True, exist_ok=True)
    backup = PROCESSED_ROOT / ".current-previous"
    if backup.exists():
        raise RefreshError("Previous current backup exists; inspect before refreshing")
    staging = Path(tempfile.mkdtemp(prefix="refresh-", dir=PROCESSED_ROOT))
    try:
        _write_table(staging / "valid_small_monthly.csv", small_rows)
        _write_table(staging / "valid_apartment_monthly.csv", apartment_rows)
        metadata = {"data_end_month": end_month, "data_as_of": dataset.month_end(end_month),
                    "refreshed_on": refreshed_on, "source": "RTMS API + preserved CSV (D-053)"}
        (staging / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if CURRENT.exists():
            os.replace(CURRENT, backup)
        try:
            os.replace(staging, CURRENT)
        except OSError:
            if backup.exists():
                os.replace(backup, CURRENT)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if staging.exists() and staging.parent == PROCESSED_ROOT:
            shutil.rmtree(staging)


def _append_log(entry: dict, path: Path = REFRESH_LOG) -> None:
    history = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"runs": []}
    history["runs"].append(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def refresh(through_month: str | None = None) -> dict:
    """Run one checked refresh; never replace current before the D-050 gate passes."""
    now = today_kst()
    through = through_month or now.strftime("%Y%m")
    fetch_rtms.month_range(through, through)
    if not API_FIRST_MONTH <= through <= now.strftime("%Y%m"):
        raise RefreshError("Through month must be between 2026-09 and the current month")
    fetch_audit: dict = {"calls": 0, "pages": [], "failures": []}
    entry: dict = {"run_date": now.isoformat(), "through_month": through, "status": "running"}
    try:
        originals = csv_groups()
        api_groups = collect_api(through, fetch_audit)
        end_month = max((month for (_, _, month), rows in api_groups.items()
                         if month >= API_FIRST_MONTH and rows), default=CSV_END_MONTH)
        if CURRENT.exists():
            previous = json.loads((CURRENT / "metadata.json").read_text(encoding="utf-8"))["data_end_month"]
            if end_month < previous:
                raise RefreshError("API data end moved backward; previous current retained")
        reconcile = reconcile_recent(end_month)
        merged, source_summary = merge_source_rows(originals, api_groups, end_month)
        small_rows, apartment_rows, derived = normalize_groups(merged, end_month)
        publish_current(small_rows, apartment_rows, end_month, now.isoformat())
        entry.update(status="complete", data_end_month=end_month, data_as_of=dataset.month_end(end_month),
                     source_summary=source_summary, derived_columns={**derived,
                     "age_band_changes_from_build_year": source_summary["age_band_changes_from_build_year"]},
                     processed_rows={"small": len(small_rows), "apartment": len(apartment_rows)},
                     d050={"period": reconcile["period"], "status": reconcile["status"],
                           "summary": reconcile["summary"], "criteria": reconcile["criteria"]})
    except (RefreshError, fetch_rtms.FetchError, ValueError, OSError) as exc:
        entry.update(status="failed", reason=str(exc))
        raise
    finally:
        entry["api_calls"] = fetch_audit["calls"]
        entry["api_failures"] = fetch_audit["failures"]
        _append_log(entry)
    return entry


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--through-month", help="Last contract month to request (YYYYMM; default current KST month)")
    args = parser.parse_args()
    try:
        result = refresh(args.through_month)
    except (RefreshError, fetch_rtms.FetchError, ValueError, OSError) as exc:
        print(f"갱신 중단: {exc}; 기존 current 유지, outputs/audit/refresh_log.json 확인")
        raise SystemExit(1) from None
    print(f"갱신 완료: {result['data_end_month']}, API 호출 {result['api_calls']}회; "
          "달별 수치는 outputs/audit/refresh_log.json 확인")


if __name__ == "__main__":
    main()
