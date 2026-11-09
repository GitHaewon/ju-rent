"""Extract the official AcademyInfo dormitory disclosure spreadsheets."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import zipfile
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "academyinfo"
OUT = ROOT / "outputs" / "rationale"
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
SCHOOLS = {"전북대학교", "전주대학교", "전주비전대학교"}


def read_rows(path: Path) -> list[dict[str, str]]:
    """Read the single-sheet, inline-string XLSX export without altering it."""
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(item.itertext()) for item in strings.findall(f"{NS}si")]
    data = []
    for row in root.findall(f".//{NS}sheetData/{NS}row"):
        record = {}
        for cell in row.findall(f"{NS}c"):
            column = re.match(r"[A-Z]+", cell.attrib["r"]).group()
            value = cell.find(f"{NS}v")
            if cell.attrib.get("t") == "inlineStr":
                inline = cell.find(f"{NS}is")
                text = "".join(inline.itertext()) if inline is not None else ""
            elif cell.attrib.get("t") == "s" and value is not None:
                text = shared[int(value.text)]
            else:
                text = value.text if value is not None else ""
            record[column] = text.strip()
        data.append(record)
    if not data:
        raise RuntimeError(f"Empty spreadsheet: {path.name}")
    header = data[0]
    return [{header[column]: value for column, value in row.items()} for row in data[1:]]


def main() -> None:
    paths = sorted(RAW.glob("14-마-1. 기숙사 수용 현황_*.xlsx"))
    if len(paths) != 2:
        raise RuntimeError("Expected the university and junior-college dormitory files")
    all_rows = []
    sources = []
    for path in paths:
        rows = read_rows(path)
        sources.append({"filename": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "rows": len(rows)})
        all_rows.extend(rows)
    if not all_rows:
        raise RuntimeError("No disclosure rows")
    columns = [
        "공시연도", "기준년도", "학교명", "본분교명", "재학생수", "수용가능인원",
        "기숙사수용률", "기숙사 밖 재학생 수",
    ]
    selected = []
    for row in all_rows:
        if row.get("학교명") not in SCHOOLS or row.get("본분교명") != "본교":
            continue
        year = int(row["공시연도"])
        if year not in range(2021, 2027):
            continue
        students = int(row["재학생수"].replace(",", ""))
        capacity = int(row["수용가능인원"].replace(",", ""))
        selected.append({
            **{key: row[key] for key in columns[:-1]},
            "기숙사 밖 재학생 수": students - capacity,
        })
    if len(selected) != 18 or len({(r["공시연도"], r["학교명"]) for r in selected}) != 18:
        raise RuntimeError("Expected one home-campus disclosure per school and year")
    selected.sort(key=lambda row: (int(row["공시연도"]), row["학교명"]))
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "dorm_capacity.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        writer.writerows(selected)
    (OUT / "dorm_capacity_sources.json").write_text(json.dumps({
        "source": "대학알리미 14-마-1. 기숙사 수용 현황",
        "source_url": "https://www.academyinfo.go.kr/main/main0830/main0830.do",
        "downloaded_on": "확인 불가",
        "processed_on": date.today().isoformat(),
        "raw_files": sources,
    }, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
