"""Track official bus and legal-dong raw hashes separately from rental CSVs."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw"
BUS_MANIFEST = ROOT / "data/audit/bus_manifest.json"
SOURCES = {
    "bus_tago": "https://www.data.go.kr/data/15098529/openapi.do ; https://www.data.go.kr/data/15098534/openapi.do",
    "bus_gw": "https://www.data.go.kr/data/15158979/openapi.do ; https://www.data.go.kr/data/15159001/openapi.do",
    "legal_dong_boundary": "https://www.vworld.kr/dtmk/dtmk_ntads_s002.do?svcCde=MK&dsId=30603",
}


def new_entries(raw_root=RAW):
    entries = []
    paths = [*raw_root.glob("bus/*.xml"), *raw_root.glob("bus/tago/*.xml"), *raw_root.glob("boundary/LSMD_ADM_SECT_UMD_*.zip")]
    for path in sorted(paths, key=lambda item: str(item).casefold()):
        relative = path.relative_to(raw_root).as_posix()
        if relative.startswith("boundary/"):
            category = "legal_dong_boundary"
        elif relative.startswith("bus/tago/") and not path.name.startswith("gw_"):
            category = "bus_tago"
        else:
            category = "bus_gw"
        entries.append(
            {
                "type": category,
                "filename": relative,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "source_url": SOURCES[category],
                "checked_date": "2026-11-13",
            }
        )
    return entries


def build_manifest(manifest=BUS_MANIFEST, raw_root=RAW):
    bus_entries = new_entries(raw_root)
    manifest.write_text(json.dumps(bus_entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"bus_and_boundary_entries": len(bus_entries)}


if __name__ == "__main__":
    print(json.dumps(build_manifest(), ensure_ascii=True))
