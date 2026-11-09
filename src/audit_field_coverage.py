"""Audit construction-year coverage in the preserved RTMS CSV exports."""

from __future__ import annotations

import json

from src.analyze_rentals import GUS, OUTPUTS, RAW, TYPES, YEARS, read_csv

YEAR_COLUMN = "건축년도"
MISSING_VALUES = {"", "-"}


def coverage_for_type(kind: str) -> dict[str, int | float | bool]:
    """Count missing values across both gu and every available analysis year."""
    files = 0
    files_with_column = 0
    rows = 0
    missing_rows = 0
    for gu in GUS.values():
        for year in YEARS:
            source = RAW / f"{kind}_{gu}_{year}.csv"
            if not source.is_file():
                raise FileNotFoundError(source)
            _, fields, records = read_csv(source)
            files += 1
            present = YEAR_COLUMN in fields
            files_with_column += present
            rows += len(records)
            missing_rows += sum(
                not present or record.get(YEAR_COLUMN, "").strip() in MISSING_VALUES
                for record in records
            )
    return {
        "files": files,
        "files_with_column": files_with_column,
        "column_in_all_files": files_with_column == files,
        "rows": rows,
        "missing_rows": missing_rows,
        "missing_rate_pct": round(missing_rows / rows * 100, 2) if rows else 0.0,
    }


def main() -> None:
    result = {
        "scope": "2021-01~2026-10, 전주시 완산구·덕진구 전월세 원본 전체 행",
        "field": YEAR_COLUMN,
        "missing_rule": "열이 없거나 값이 빈 문자열 또는 '-'인 행",
        "by_type": {kind: coverage_for_type(kind) for kind in TYPES.values()},
    }
    OUTPUTS.mkdir(exist_ok=True)
    (OUTPUTS / "field_coverage.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
