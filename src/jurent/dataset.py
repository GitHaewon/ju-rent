"""D-051 service/current and fixed evidence snapshot windows."""

from __future__ import annotations

import calendar
import json
from dataclasses import dataclass
from pathlib import Path

from src.jurent import data

ROOT = Path(__file__).resolve().parents[2]
CURRENT = ROOT / "data/processed/current"
SNAPSHOT_END_MONTH = "202610"
SNAPSHOT_REFRESHED_ON = "2026-11-07"


def shift_month(month: str, offset: int) -> str:
    if len(month) != 6 or not month.isdigit() or not 1 <= int(month[4:]) <= 12:
        raise ValueError("Month must be YYYYMM")
    index = int(month[:4]) * 12 + int(month[4:]) - 1 + offset
    return f"{index // 12:04d}{index % 12 + 1:02d}"


def month_end(month: str) -> str:
    year, number = int(month[:4]), int(month[4:])
    return f"{year:04d}-{number:02d}-{calendar.monthrange(year, number)[1]:02d}"


@dataclass(frozen=True)
class RentalDataset:
    mode: str
    directory: Path
    end_month: str
    refreshed_on: str

    @property
    def small_path(self) -> Path:
        return self.directory / "valid_small_monthly.csv"

    @property
    def apartment_path(self) -> Path:
        return self.directory / "valid_apartment_monthly.csv"

    @property
    def data_end(self) -> str:
        return month_end(self.end_month)

    @property
    def recent_start(self) -> str:
        first = shift_month(self.end_month, -23)
        return f"{first[:4]}-{first[4:]}-01"

    @property
    def incomplete_months(self) -> tuple[str, str]:
        return shift_month(self.end_month, -1), self.end_month

    @property
    def partial_year(self) -> int | None:
        return int(self.end_month[:4]) if self.end_month[4:] != "12" else None

    @property
    def incomplete_warning(self) -> str:
        previous, current = self.incomplete_months
        if previous[:4] == current[:4]:
            period = f"{current[:4]}년 {int(previous[4:])}~{int(current[4:])}월"
        else:
            period = f"{previous[:4]}년 {int(previous[4:])}월~{current[:4]}년 {int(current[4:])}월"
        return f"{period} 계약은 아직 신고가 덜 들어왔을 수 있어요."


SNAPSHOT = RentalDataset("snapshot", data.SNAPSHOT, SNAPSHOT_END_MONTH, SNAPSHOT_REFRESHED_ON)


def select(mode: str = "snapshot") -> RentalDataset:
    if mode == "snapshot":
        return SNAPSHOT
    if mode != "current":
        raise ValueError("Unknown rental dataset")
    metadata = json.loads((CURRENT / "metadata.json").read_text(encoding="utf-8"))
    return RentalDataset("current", CURRENT, metadata["data_end_month"], metadata["refreshed_on"])
