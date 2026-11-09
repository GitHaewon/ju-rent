"""Summarize officially downloaded KOSIS city-age household CSV archives."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "kosis"
OUTPUT = ROOT / "outputs" / "rationale"
TABLE_ID = "DT_1PL1502"
SOURCE_URL = (
    "https://kosis.kr/statisticsList/mass/mass_list.jsp?"
    "org_id=101&process=statHtml&tbl_id=DT_1PL1502&vw_cd=MT_ZTITLE"
)
RETRIEVED_ON = "2026-11-09"
YEARS = range(2021, 2026)
JEONJU_CODE = "35010"
AGE_CODES = {"025": "age_20_to_24", "030": "age_25_to_29"}


def integer(value: str) -> int:
    parsed = Decimal(value)
    if not parsed.is_finite() or parsed != int(parsed):
        raise ValueError(f"Non-integer KOSIS count: {value!r}")
    return int(parsed)


def read_year(year: int) -> tuple[dict, dict]:
    path = RAW / f"101_{TABLE_ID}_Y_{year}.zip"
    if not path.is_file():
        raise FileNotFoundError(path)
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if names != [f"101_{TABLE_ID}_Y_{year}.csv"]:
            raise ValueError(f"Unexpected KOSIS archive contents: {path}")
        text = archive.read(names[0]).decode("cp949")
    rows = list(csv.reader(io.StringIO(text)))
    if rows[0] != ["성 및 연령별 1인가구 - 시군구"] or rows[2][4:6] != ["시점", "1인가구"]:
        raise ValueError(f"Unexpected KOSIS table header: {path}")
    selected = {}
    for row in rows[3:]:
        if len(row) < 8 or row[0].lstrip("'") != JEONJU_CODE:
            continue
        age_code = row[2].lstrip("'")
        if age_code not in AGE_CODES:
            continue
        if row[1].strip() != "전주시" or row[4] != str(year) or age_code in selected:
            raise ValueError(f"Unexpected Jeonju age row: {path}: {row}")
        value = integer(row[5])
        if value != integer(row[6]) + integer(row[7]):
            raise ValueError(f"KOSIS sex totals differ: {path}: {row}")
        selected[age_code] = value
    if set(selected) != set(AGE_CODES):
        raise ValueError(f"Missing Jeonju 20s age group: {path}")
    result = {
        "year": year,
        "region_code": JEONJU_CODE,
        "region": "전주시",
        "age_20_to_24": selected["025"],
        "age_25_to_29": selected["030"],
        "age_20s_total": sum(selected.values()),
        "source_table_id": TABLE_ID,
        "retrieved_on": RETRIEVED_ON,
    }
    source = {
        "year": year,
        "filename": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    return result, source


def main() -> None:
    extracted = [read_year(year) for year in YEARS]
    rows = [row for row, _ in extracted]
    sources = [source for _, source in extracted]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with (OUTPUT / "single_households.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (OUTPUT / "single_households_sources.json").write_text(
        json.dumps({
            "institution": "국가데이터처 KOSIS 인구총조사",
            "table_id": TABLE_ID,
            "source_url": SOURCE_URL,
            "retrieved_on": RETRIEVED_ON,
            "region_code": JEONJU_CODE,
            "age_codes": AGE_CODES,
            "raw_files": sources,
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
